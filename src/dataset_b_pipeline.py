import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity

from segment import (
    load_session_events,
    build_features,
    pelt_candidates,
    sequence_change_scores,
    train_pelt_reranker,
    compute_rerank_features,
    RERANK_FEATURE_COLS,
    _event_seconds,
)

# Final inference configuration
WINDOW_SEC = 5.0
WINDOW_EVENTS = 8
MOVE_DELTA = 0.0
# The two-second cap was tested and rejected during validation.
DISTANCE_GRID = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
# Step 1 boundaries can split one business case into multiple activity
# fragments. Only directly adjacent, same-cluster fragments are eligible for
# execution-level merging; do not bridge across a differently labelled segment.
MAX_EXECUTION_GAP_SEC = 10.0

# Rank labels are not stable across clustering reruns. Preserve final names for
# manually reviewed clusters: cluster 22 is onboarding; cluster 5 is fragmentary.
FINAL_LABEL_OVERRIDES = {
    22: "process_003",
    5: "process_002_fragment",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "outputs"
MODEL_DIR = REPO_ROOT / "models"


def find_dataset_root(name: str) -> Path:
    direct = DATA_DIR / name
    if direct.exists():
        return direct
    candidates = sorted(DATA_DIR.glob(f"{name}*/{name}"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"Could not find {name} under {DATA_DIR}")


def sessions(root: Path):
    out = sorted(root.glob("ses_*"))
    if not out:
        raise RuntimeError(f"No sessions found under {root}")
    return out


def rerank_unrestricted(df, model, pelt_idx, seq_raw):
    """Final locked inference: PELT anchor + learned local rerank, no 2s cap."""
    if not pelt_idx:
        return []

    times = _event_seconds(df)
    all_iso = [
        datetime.fromisoformat(x.replace("Z", "+00:00"))
        for x in df["timestamp_iso"]
    ]

    rows, mapping = [], []
    for a_pos, p_idx in enumerate(pelt_idx):
        t0 = times[p_idx]
        local = np.where(np.abs(times - t0) <= WINDOW_SEC)[0]
        for idx in local:
            rows.append(
                compute_rerank_features(
                    df, int(idx), times, t0, seq_raw,
                    window_events=WINDOW_EVENTS,
                )
            )
            mapping.append((a_pos, int(idx)))

    if not rows:
        return [all_iso[i] for i in pelt_idx]

    X = pd.DataFrame(rows)
    probs = model.predict_proba(X[RERANK_FEATURE_COLS])[:, 1]

    by_anchor = defaultdict(list)
    for (a_pos, idx), prob in zip(mapping, probs):
        by_anchor[a_pos].append((idx, float(prob)))

    chosen = []
    for a_pos, p_idx in enumerate(pelt_idx):
        entries = by_anchor.get(a_pos, [])
        if not entries:
            chosen.append(p_idx)
            continue
        best_idx, best_prob = max(entries, key=lambda z: z[1])
        orig_prob = next((p for idx, p in entries if idx == p_idx), 0.0)
        chosen.append(best_idx if best_prob - orig_prob >= MOVE_DELTA else p_idx)

    chosen = sorted(set(chosen))
    return [all_iso[i] for i in chosen]


def make_segments(df, boundaries):
    if df.empty:
        return []
    start = datetime.fromisoformat(df.iloc[0]["timestamp_iso"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(df.iloc[-1]["timestamp_iso"].replace("Z", "+00:00"))
    bs = sorted({b for b in boundaries if start < b < end})
    out = []
    cur = start
    for b in bs:
        if b > cur:
            out.append((cur, b))
            cur = b
    if cur < end:
        out.append((cur, end))
    return out


def segment_indices(df, intervals):
    ts = df["timestamp_ms"].to_numpy()
    out = []
    for start, end in intervals:
        lo = start.timestamp() * 1000.0
        hi = end.timestamp() * 1000.0
        out.append(np.where((ts >= lo) & (ts <= hi))[0].tolist())
    return out


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+")


def clean_text(v):
    """Normalize a single scalar value for clustering.

    Never stringify a dict/list here: doing so previously turned the complete
    ``active_app`` object into a noisy feature and mixed app, title, and other
    metadata together.
    """
    if v is None or isinstance(v, (dict, list)):
        return ""
    s = str(v)
    s = re.sub(r"https?://\S+", "", s, flags=re.I)
    s = re.sub(r"\b[0-9a-f]{8,}\b", "ID", s, flags=re.I)
    s = re.sub(r"\d+", "#", s)
    return re.sub(r"\s+", " ", s).strip().lower()[:80]


def first_text(mapping, *keys):
    """Return the first non-empty scalar value from a schema mapping."""
    if not isinstance(mapping, dict):
        return ""
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "") and not isinstance(value, (dict, list)):
            return clean_text(value)
    return ""


def page_identifier(raw_url):
    """Keep the stable page route for SPA URLs such as ``#/onboarding``."""
    if not raw_url or isinstance(raw_url, (dict, list)):
        return ""
    try:
        parsed = urlparse(str(raw_url))
    except ValueError:
        return ""

    # Most supplied business portals are single-page apps, where the useful
    # workflow route is in the fragment rather than the path.
    route = parsed.fragment or parsed.path
    return clean_text(route.strip("/"))


def event_context(event):
    """Extract only documented context fields; never recursively search events.

    Returns clean, independent values rather than a stringified ``active_app``
    dictionary. This preserves the semantic distinction between application,
    page title, portal host, and workflow route.
    """
    context = event.get("context", {})
    if not isinstance(context, dict):
        return "", "", "", ""

    active_app = context.get("active_app", {})
    browser_tab = context.get("active_browser_tab", {})
    if not isinstance(active_app, dict):
        active_app = {}
    if not isinstance(browser_tab, dict):
        browser_tab = {}

    app = first_text(active_app, "app_name", "application_name", "process_name")
    title = first_text(active_app, "window_title", "window_name")
    if not title:
        title = first_text(browser_tab, "title")

    raw_url = browser_tab.get("url") or browser_tab.get("browser_url")
    host = ""
    if raw_url and not isinstance(raw_url, (dict, list)):
        try:
            host = urlparse(str(raw_url)).netloc.lower()
        except ValueError:
            host = ""

    return app, title, host, page_identifier(raw_url)


def context_tokens(text, prefix):
    if not text:
        return []
    toks = [t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 2]
    return [f"{prefix}:{t}" for t in toks[:8]]


def recognize_segment(df, idxs):
    if not idxs:
        return {"text": "", "pattern": "", "apps": [], "hosts": [], "pages": []}

    types = []
    apps, hosts, pages, tokens = [], [], [], []
    for i in idxs:
        e = df.iloc[int(i)].to_dict()
        et = str(e.get("event_type", "unknown"))
        types.append(et)
        tokens.append(f"etype:{et}")
        app, title, host, page = event_context(e)
        if app:
            apps.append(app)
            tokens.extend(context_tokens(app, "app"))
        if title:
            tokens.extend(context_tokens(title, "title"))
        if host:
            hosts.append(host)
            tokens.extend(context_tokens(host, "host"))
        if page:
            pages.append(page)
            tokens.extend(context_tokens(page, "page"))

    for a, b in zip(types, types[1:]):
        tokens.append(f"trans:{a}>{b}")

    unique_apps = []
    for app in apps:
        if not unique_apps or unique_apps[-1] != app:
            unique_apps.append(app)
    for a, b in zip(unique_apps, unique_apps[1:]):
        tokens.append(f"apptrans:{a}>{b}")

    c = Counter(types)
    pattern = ">".join(k for k, _ in c.most_common(6))
    return {
        "text": " ".join(tokens),
        "pattern": pattern,
        "apps": sorted(set(apps)),
        "hosts": sorted(set(hosts)),
        "pages": sorted(set(pages)),
    }


def json_list(value):
    """Read list-valued CSV fields defensively for execution aggregation."""
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def compatible_page_context(left, right):
    """Allow app hand-offs (HR portal -> Word), but reject conflicting routes.

    A Word/Notepad fragment normally has no browser route, so an empty route is
    compatible with its neighbouring portal fragment. If both fragments expose
    routes, they must share at least one route to be merged.
    """
    left_pages = set(json_list(left["pages"]))
    right_pages = set(json_list(right["pages"]))
    return not left_pages or not right_pages or bool(left_pages & right_pages)


def merge_adjacent_segments(seg_df):
    """Return raw fragments with execution IDs and conservative merged executions.

    The deliverable should approximate coherent business executions, while the
    raw segmentation must remain available for audit and error analysis.
    """
    raw = seg_df.sort_values(["session_id", "segment_number"]).copy()
    raw["execution_id"] = ""
    execution_rows = []

    for session_id, session_rows in raw.groupby("session_id", sort=False):
        current = None
        execution_number = 0

        def close_current():
            nonlocal current, execution_number
            if current is None:
                return
            execution_number += 1
            member_indices = current["member_indices"]
            members = raw.loc[member_indices]
            execution_id = f"{session_id}_exec_{execution_number:03d}"
            raw.loc[member_indices, "execution_id"] = execution_id

            def union_json(column):
                return sorted({item for value in members[column] for item in json_list(value)})

            execution_rows.append({
                "execution_id": execution_id,
                "session_id": session_id,
                "cluster_raw": current["cluster_raw"],
                "start": current["start"],
                "end": current["end"],
                "duration_sec": (current["end_dt"] - current["start_dt"]).total_seconds(),
                "raw_segment_count": len(member_indices),
                "raw_segment_numbers": json.dumps(members["segment_number"].astype(int).tolist()),
                "event_count": int(members["event_count"].sum()),
                "actor_or_machine": current["actor_or_machine"],
                # Retain a representative interaction pattern so existing
                # process-summary diagnostics continue to work at execution
                # level. The mode is more robust than concatenating fragments.
                "pattern_signature": members["pattern_signature"].mode().iloc[0],
                "apps": json.dumps(union_json("apps"), ensure_ascii=False),
                "hosts": json.dumps(union_json("hosts"), ensure_ascii=False),
                "pages": json.dumps(union_json("pages"), ensure_ascii=False),
                "app_count": len(union_json("apps")),
                "within_cluster_similarity": float(members["within_cluster_similarity"].mean()),
            })
            current = None

        for row_index, row in session_rows.iterrows():
            row_start = datetime.fromisoformat(row["start"].replace("Z", "+00:00"))
            row_end = datetime.fromisoformat(row["end"].replace("Z", "+00:00"))
            can_extend = (
                current is not None
                and row["cluster_raw"] == current["cluster_raw"]
                and int(row["segment_number"]) == current["last_segment_number"] + 1
                and (row_start - current["end_dt"]).total_seconds() <= MAX_EXECUTION_GAP_SEC
                and compatible_page_context(current["last_row"], row)
            )
            if can_extend:
                current["end"] = row["end"]
                current["end_dt"] = row_end
                current["last_segment_number"] = int(row["segment_number"])
                current["last_row"] = row
                current["member_indices"].append(row_index)
                continue

            close_current()
            current = {
                "cluster_raw": row["cluster_raw"],
                "start": row["start"],
                "end": row["end"],
                "start_dt": row_start,
                "end_dt": row_end,
                "last_segment_number": int(row["segment_number"]),
                "last_row": row,
                "member_indices": [row_index],
                "actor_or_machine": row["actor_or_machine"],
            }
        close_current()

    return raw, pd.DataFrame(execution_rows)


def actor_or_machine(session_id):
    parts = session_id.split("-")
    return "-".join(parts[2:]) if len(parts) >= 3 else session_id


def cluster_segments(seg_df):
    texts = seg_df["signature_text"].fillna("").tolist()
    vec = TfidfVectorizer(
        tokenizer=str.split,
        token_pattern=None,
        lowercase=False,
        min_df=2,
        sublinear_tf=True,
    )
    # AgglomerativeClustering in this sklearn environment requires dense input.
    # Dataset B has only 339 segments, so densifying the TF-IDF matrix is small/safe here.
    X = vec.fit_transform(texts).toarray()

    if len(seg_df) < 3:
        seg_df = seg_df.copy()
        seg_df["cluster_raw"] = 0
        return seg_df, 0.50, X

    best = None
    for dist in DISTANCE_GRID:
        model = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=dist,
            metric="cosine",
            linkage="average",
        )
        labels = model.fit_predict(X)
        k = len(np.unique(labels))
        if k < 2 or k >= len(labels):
            continue
        try:
            score = silhouette_score(X, labels, metric="cosine")
        except Exception:
            continue
        if best is None or score > best[0]:
            best = (score, dist, labels)

    if best is None:
        model = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=0.50,
            metric="cosine",
            linkage="average",
        )
        labels = model.fit_predict(X)
        dist = 0.50
    else:
        _, dist, labels = best

    seg_df = seg_df.copy()
    seg_df["cluster_raw"] = labels
    return seg_df, dist, X


def add_cluster_stats(seg_df, X):
    labels = seg_df["cluster_raw"].to_numpy()
    sims = {}
    for c in np.unique(labels):
        idx = np.where(labels == c)[0]
        if len(idx) <= 1:
            sims[c] = 1.0
            continue
        centroid = X[idx].mean(axis=0, keepdims=True)  # was: axis=0 (returns 1D)
        sims[c] = float(cosine_similarity(X[idx], centroid).mean())
    seg_df = seg_df.copy()
    seg_df["within_cluster_similarity"] = [sims[c] for c in labels]
    return seg_df


def mm(s):
    s = pd.Series(s, dtype=float)
    if s.max() - s.min() < 1e-9:
        return pd.Series(np.ones(len(s)), index=s.index)
    return (s - s.min()) / (s.max() - s.min())


def process_summary(seg_df):
    rows = []
    for c, g in seg_df.groupby("cluster_raw"):
        app_stability = 1.0 / max(g["app_count"].mean(), 1.0)
        rows.append({
            "cluster_raw": c,
            "execution_count": len(g),
            "raw_segment_count": int(g["raw_segment_count"].sum()),
            "total_minutes": g["duration_sec"].sum() / 60.0,
            "median_duration_sec": g["duration_sec"].median(),
            "unique_actors_or_machines": g["actor_or_machine"].nunique(),
            "median_events": g["event_count"].median(),
            "mean_apps": g["app_count"].mean(),
            "consistency": g["within_cluster_similarity"].mean(),
            "dominant_pattern_share": g["pattern_signature"].value_counts(normalize=True).iloc[0],
            "app_stability": app_stability,
        })
    s = pd.DataFrame(rows)
    if s.empty:
        return s

    s["impact"] = (
        0.50 * mm(s["execution_count"])
        + 0.30 * mm(s["total_minutes"])
        + 0.20 * mm(s["unique_actors_or_machines"])
    )
    s["readiness"] = (
        0.70 * s["consistency"].clip(0, 1)
        + 0.30 * mm(s["app_stability"])
    )
    s["priority_score"] = 100 * s["impact"] * s["readiness"]
    s = s.sort_values("priority_score", ascending=False).reset_index(drop=True)
    s["label"] = [f"process_{i+1:03d}" for i in range(len(s))]
    return s


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    MODEL_DIR.mkdir(exist_ok=True)

    a_root = find_dataset_root("dataset_a")
    b_root = find_dataset_root("dataset_b")
    a_sessions = sessions(a_root)
    b_sessions = sessions(b_root)

    print(f"Dataset A: {len(a_sessions)} sessions")
    print(f"Dataset B: {len(b_sessions)} sessions")

    # 1) Fit final model on ALL labeled Dataset A after architecture freeze.
    print("\n--- Training final reranker on all Dataset A ---")
    model = train_pelt_reranker(
        a_sessions,
        window_sec=WINDOW_SEC,
        window_events=WINDOW_EVENTS,
    )

    try:
        import joblib
        joblib.dump(model, MODEL_DIR / "pelt_reranker_final.joblib")
        print(f"Saved {MODEL_DIR / 'pelt_reranker_final.joblib'}")
    except Exception as exc:
        print(f"Model save skipped: {exc}")

    # 2) Segment Dataset B.
    print("\n--- Segmenting Dataset B ---")
    rows = []
    for n, session_path in enumerate(b_sessions, 1):
        print(f"  {n}/{len(b_sessions)} {session_path.name}")
        df = build_features(load_session_events(session_path))
        if df.empty:
            continue
        pelt_idx = pelt_candidates(df, pen=3)
        seq_raw = sequence_change_scores(df, window=10)
        boundaries = rerank_unrestricted(df, model, pelt_idx, seq_raw)
        intervals = make_segments(df, boundaries)
        idx_groups = segment_indices(df, intervals)

        for seg_no, ((start, end), idxs) in enumerate(zip(intervals, idx_groups), 1):
            rec = recognize_segment(df, idxs)
            rows.append({
                "session_id": session_path.name,
                "segment_number": seg_no,
                "start": start.isoformat().replace("+00:00", "Z"),
                "end": end.isoformat().replace("+00:00", "Z"),
                "duration_sec": (end - start).total_seconds(),
                "event_count": len(idxs),
                "actor_or_machine": actor_or_machine(session_path.name),
                "signature_text": rec["text"],
                "pattern_signature": rec["pattern"],
                "apps": json.dumps(rec["apps"], ensure_ascii=False),
                "hosts": json.dumps(rec["hosts"], ensure_ascii=False),
                "pages": json.dumps(rec["pages"], ensure_ascii=False),
                "app_count": len(rec["apps"]),
            })

    seg = pd.DataFrame(rows)
    if seg.empty:
        raise RuntimeError("No Dataset B segments produced")

    print(f"Produced {len(seg)} segments")

    # 3) Event/process recognition by recurring action signatures.
    print("\n--- Recognizing repeated processes ---")
    seg, dist, X = cluster_segments(seg)
    seg = add_cluster_stats(seg, X)
    print(f"Selected cosine distance threshold: {dist:.2f}")
    print(f"Recognized process groups: {seg['cluster_raw'].nunique()}")

    # 4) Merge directly adjacent same-workflow fragments into inferred
    # business executions. The raw fragments stay in the recognition CSV.
    seg, executions = merge_adjacent_segments(seg)
    summary = process_summary(executions)
    summary["label"] = summary.apply(
        lambda row: FINAL_LABEL_OVERRIDES.get(int(row["cluster_raw"]), row["label"]),
        axis=1,
    )
    label_map = dict(zip(summary["cluster_raw"], summary["label"]))
    seg["label"] = seg["cluster_raw"].map(label_map)
    executions["label"] = executions["cluster_raw"].map(label_map)
    print(f"Inferred business executions: {len(executions)} from {len(seg)} raw segments")

    # 5) Required deliverable: segments.jsonl contains inferred executions,
    # not technical fragments.
    with open(OUTPUT_DIR / "segments.jsonl", "w", encoding="utf-8") as f:
        for r in executions.itertuples(index=False):
            f.write(json.dumps({
                "session_id": r.session_id,
                "start": r.start,
                "end": r.end,
                "label": r.label,
            }, ensure_ascii=False) + "\n")

    # 6) Detailed raw-fragment output for auditing segmentation quality.
    seg[[
        "session_id", "segment_number", "start", "end", "label",
        "duration_sec", "event_count", "actor_or_machine",
        "execution_id", "pattern_signature", "apps", "hosts", "pages",
        "within_cluster_similarity"
    ]].to_csv(
        OUTPUT_DIR / "segment_event_recognition.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 7) Execution-level output and Step 2 process summary.
    executions.to_csv(
        OUTPUT_DIR / "inferred_executions.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary.to_csv(
        OUTPUT_DIR / "process_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 8) Human-readable shortlist.
    with open(OUTPUT_DIR / "step2_candidates.md", "w", encoding="utf-8") as f:
        f.write("# Dataset B — Step 2 Automation Candidates\n\n")
        f.write(f"Sessions: {len(b_sessions)}\n\n")
        f.write(f"Raw segmentation fragments: {len(seg)}\n\n")
        f.write(f"Inferred business executions: {len(executions)}\n\n")
        f.write(f"Recognized process groups: {len(summary)}\n\n")
        f.write("Priority combines workload impact (frequency, observed time, breadth) and repeatability/readiness (within-process similarity and application stability). It is a transparent heuristic, not ground truth.\n\n")
        f.write("| Rank | Label | Executions | Raw segments | Total min | Actors/Machines | Consistency | Readiness | Priority |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for i, r in summary.head(15).iterrows():
            f.write(f"| {i+1} | {r['label']} | {int(r['execution_count'])} | {int(r['raw_segment_count'])} | {r['total_minutes']:.1f} | {int(r['unique_actors_or_machines'])} | {r['consistency']:.2f} | {r['readiness']:.2f} | {r['priority_score']:.1f} |\n")
        f.write("\n## Caveats\n\n")
        f.write("- Dataset B has no ground truth, so process groups are inferred from recurring event/application signatures.\n")
        f.write("- The session-name suffix is treated as an operator/machine identifier, not guaranteed human identity.\n")
        f.write("- Test-environment waiting times are shortened; compare processes relatively rather than treating observed duration as production duration.\n")

    print("\n--- Outputs ---")
    for p in [
        OUTPUT_DIR / "segments.jsonl",
        OUTPUT_DIR / "segment_event_recognition.csv",
        OUTPUT_DIR / "inferred_executions.csv",
        OUTPUT_DIR / "process_summary.csv",
        OUTPUT_DIR / "step2_candidates.md",
    ]:
        print(p)

    print("\n--- Top candidates ---")
    print(summary[[
        "label", "execution_count", "raw_segment_count", "total_minutes",
        "unique_actors_or_machines", "consistency",
        "readiness", "priority_score"
    ]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
