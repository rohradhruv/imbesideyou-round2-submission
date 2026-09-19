"""
Manual spot-check helper.

Samples segments from selected labels and copies screenshots that fall inside
each interval. The generated index records the interval, event pattern, and
applications to support manual Dataset B workflow reconstruction.

Run from your repo root (same place dataset_b_pipeline.py runs from).

  python spot_check.py process_001 process_003 process_004

If you don't pass labels, it defaults to the top 3 rows of
process_summary_filtered.csv (falls back to process_summary.csv if
you haven't run filter_candidates.py yet).
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "outputs"
REVIEW_DIR = OUTPUT_DIR / "spot_check"

SAMPLES_PER_LABEL = 4
MAX_SCREENSHOTS_PER_SEGMENT = 6

def find_dataset_root(name: str) -> Path:
    direct = DATA_DIR / name
    if direct.exists():
        return direct
    candidates = sorted(DATA_DIR.glob(f"{name}*/{name}"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"Could not find {name} under {DATA_DIR}")


def load_screenshot_events(session_dir: Path):
    """Load screenshot events using the documented payload.file_reference.

    DATA_SCHEMA.md defines this field, so the helper intentionally avoids a
    permissive recursive search that could accidentally select unrelated data.
    """
    events = []
    for chunk_dir in sorted(session_dir.glob("chunk_*")):
        events_file = chunk_dir / "events.jsonl"
        if not events_file.exists():
            continue
        with open(events_file, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                et = str(e.get("event_type", ""))
                if "screenshot" in et.lower():
                    path = e.get("payload", {}).get("file_reference", {}).get("filename")
                    events.append({
                        "timestamp_ms": e.get("timestamp_ms"),
                        "timestamp_iso": e.get("timestamp_iso"),
                        "raw_path": path,
                        "chunk_dir": chunk_dir,
                        "raw_event": e,
                    })
    return events


def resolve_screenshot_file(chunk_dir: Path, raw_path: str):
    """raw_path might be a bare filename, a relative path, or something
    odd -- try a few reasonable resolutions against this chunk's
    screenshots/ folder."""
    if not raw_path:
        return None
    candidates = [
        chunk_dir / raw_path,
        chunk_dir / "screenshots" / raw_path,
        chunk_dir / "screenshots" / Path(raw_path).name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def pick_samples(seg_df: pd.DataFrame, label: str, n: int):
    rows = seg_df[seg_df["label"] == label]
    if rows.empty:
        return rows
    if len(rows) <= n:
        return rows
    # Spread samples across the label instead of taking only the earliest rows.
    step = max(len(rows) // n, 1)
    return rows.iloc[::step].head(n)


def main():
    labels = sys.argv[1:]

    rec_path = OUTPUT_DIR / "segment_event_recognition.csv"
    if not rec_path.exists():
        raise FileNotFoundError(f"Run dataset_b_pipeline.py first -- {rec_path} not found")
    seg_df = pd.read_csv(rec_path)

    if not labels:
        summary_path = OUTPUT_DIR / "process_summary_filtered.csv"
        if not summary_path.exists():
            summary_path = OUTPUT_DIR / "process_summary.csv"
        summary = pd.read_csv(summary_path)
        labels = summary.sort_values("priority_score", ascending=False)["label"].head(3).tolist()
        print(f"No labels given -- defaulting to top 3: {labels}")

    b_root = find_dataset_root("dataset_b")
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    session_cache = {}
    for label in labels:
        samples = pick_samples(seg_df, label, SAMPLES_PER_LABEL)
        if samples.empty:
            print(f"\n{label}: no segments found in segment_event_recognition.csv -- check the label spelling")
            continue

        label_dir = REVIEW_DIR / label
        label_dir.mkdir(parents=True, exist_ok=True)
        index_lines = [f"# Spot-check: {label}\n"]

        print(f"\n{label}: sampling {len(samples)} of its segments")

        for i, row in samples.reset_index(drop=True).iterrows():
            session_id = row["session_id"]
            start = datetime.fromisoformat(row["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(row["end"].replace("Z", "+00:00"))

            if session_id not in session_cache:
                session_cache[session_id] = load_screenshot_events(b_root / session_id)
            shots = session_cache[session_id]

            in_window = [s for s in shots
                         if s["timestamp_iso"] and start <= datetime.fromisoformat(
                             s["timestamp_iso"].replace("Z", "+00:00")) <= end]
            in_window = in_window[:MAX_SCREENSHOTS_PER_SEGMENT]

            seg_folder = label_dir / f"sample{i+1}_{session_id}_seg{row['segment_number']}"
            seg_folder.mkdir(parents=True, exist_ok=True)

            index_lines.append(f"\n## Sample {i+1}: {session_id} segment {row['segment_number']} "
                                f"({row['start']} to {row['end']}, {row['duration_sec']:.1f}s)\n")
            index_lines.append(f"- Pattern: `{row['pattern_signature']}`\n")
            index_lines.append(f"- Apps: `{row['apps']}`\n")

            copied = 0
            for s in in_window:
                resolved = resolve_screenshot_file(s["chunk_dir"], s["raw_path"])
                if resolved is None:
                    if s["raw_path"] is None:
                        print("  WARNING: screenshot event has no payload.file_reference.filename")
                    continue
                dest = seg_folder / resolved.name
                shutil.copy2(resolved, dest)
                index_lines.append(f"  - {dest.relative_to(REVIEW_DIR)}\n")
                copied += 1

            print(f"  sample {i+1}: {session_id} seg {row['segment_number']} -> {copied} screenshots copied")

        with open(label_dir / "index.md", "w", encoding="utf-8") as f:
            f.writelines(index_lines)

    print(f"\nDone. Review images under {REVIEW_DIR}")
    print("For each label's folder: do the sampled segments actually look like the same repeated task?")


if __name__ == "__main__":
    main()
