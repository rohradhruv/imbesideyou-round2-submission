"""Final Step 2 automation-candidate analysis using inferred executions."""

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "outputs"
SUMMARY_PATH = OUTPUT_DIR / "process_summary_filtered.csv"

# Labels are rank-based. These findings must be revalidated after every
# clustering rerun; they come from the fresh screenshot spot checks.
MANUAL_CLASSIFICATION = {
    "process_001": {
        "judgment": "mixed_cluster", "has_clear_output": None,
        "note": "Rejected: mixes finance adjustment, purchase-order management, and contract-reference work.",
    },
    "process_002_fragment": {
        "judgment": "fragment_noise", "has_clear_output": False,
        "note": "Rejected: fragmented payroll/navigation activity rather than a coherent business execution.",
    },
    "process_003": {
        "judgment": "rule_guided_review", "has_clear_output": True,
        "note": "Validated HR new-hire onboarding verification: portal case review, required-item cross-check, and Word checklist use before complete/flag action. One sampled segment begins in the purchase-order portal before moving into the onboarding workflow, so its boundary is treated as spillover rather than evidence that the two workflows are the same.",
    },
    "process_004": {
        "judgment": "rule_guided_review", "has_clear_output": True,
        "note": "HR payroll/compensation-change case handling with confirm/hold actions; stronger financial-control risk than onboarding.",
    },
}


def min_max(series):
    series = pd.Series(series, dtype=float)
    span = series.max() - series.min()
    return pd.Series(1.0, index=series.index) if span < 1e-9 else (series - series.min()) / span


def recommendation(row):
    if row["human_judgment"] == "mixed_cluster":
        return "Reject -- mixed workflows, not a valid process group"
    if row["human_judgment"] == "fragment_noise":
        return "Reject -- activity fragments, not a coherent execution"
    if row["label"] == "process_003":
        return "Selected -- review-first automation candidate"
    if row["human_judgment"] == "rule_guided_review":
        return "Phase 2 candidate -- validate controls before automation"
    return "Defer -- workflow meaning not manually validated"


def main():
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Run dataset_b_pipeline.py and filter_candidates.py first: {SUMMARY_PATH}")

    df = pd.read_csv(SUMMARY_PATH).rename(columns={
        "cluster_raw": "cluster_id",
        "unique_actors_or_machines": "unique_actors",
    })
    required = {"execution_count", "raw_segment_count", "total_minutes", "unique_actors"}
    if missing := required - set(df.columns):
        raise RuntimeError("Missing execution-level summary columns: " + ", ".join(sorted(missing)))

    df["human_judgment"] = df["label"].map(
        lambda label: MANUAL_CLASSIFICATION.get(label, {}).get("judgment", "unvalidated")
    )
    df["has_clear_output"] = df["label"].map(
        lambda label: MANUAL_CLASSIFICATION.get(label, {}).get("has_clear_output")
    )
    df["reconstruction_note"] = df["label"].map(
        lambda label: MANUAL_CLASSIFICATION.get(label, {}).get(
            "note", "Not manually validated; do not treat this cluster as a business process."
        )
    )

    # A high statistical score cannot override a manual rejection of a mixed cluster.
    df["impact_score"] = (
        0.50 * min_max(df["execution_count"])
        + 0.35 * min_max(df["total_minutes"])
        + 0.15 * min_max(df["unique_actors"])
    )
    df["feasibility_score"] = (
        0.45 * df["consistency"].clip(0, 1)
        + 0.25 * df["app_stability"].clip(0, 1)
        + 0.30 * df["readiness"].clip(0, 1)
    )
    df["automation_call"] = df.apply(recommendation, axis=1)

    selected = df.loc[df["label"] == "process_003"].iloc[0]
    decision = {
        "target": "process_003 -- HR new-hire onboarding verification",
        "scope": (
            "Given an HR onboarding case ID, retrieve employee and required-item data, "
            "apply deterministic completeness checks, and prepare a review checklist, "
            "exception summary, and suggested verification note. A human reviewer judges "
            "exceptions and completes or flags the portal case."
        ),
        "why": (
            f"Screenshot validation identified an onboarding-review subworkflow across multiple "
            f"operators ({int(selected['unique_actors'])}) within this {int(selected['execution_count'])}-execution "
            f"cluster. It represents "
            f"{int(selected['raw_segment_count'])} raw fragments and {selected['total_minutes']:.1f} "
            "observed minutes. One sampled boundary has purchase-order spillover, so the prototype targets "
            "the visually repeated onboarding portion only. That portion has repeatable checks, structured "
            "case data, and a clear human approval boundary."
        ),
        "implementation": (
            "Use a deterministic Python review assistant, not an LLM agent. The demonstrated work is "
            "structured retrieval, rule checks, and checklist/exception preparation; final judgment and "
            "portal submission remain human-controlled."
        ),
        "limitation": (
            "Logs do not provide production credentials, API contracts, authoritative rules, or approval "
            "policy. The prototype therefore uses local mock adapters and requires human review."
        ),
    }

    columns = [
        "label", "execution_count", "raw_segment_count", "total_minutes", "unique_actors",
        "consistency", "app_stability", "readiness", "human_judgment", "has_clear_output",
        "impact_score", "feasibility_score", "automation_call", "reconstruction_note",
    ]
    out = df[columns].sort_values("impact_score", ascending=False)
    out.to_csv(OUTPUT_DIR / "automation_candidates_final.csv", index=False, encoding="utf-8-sig")

    with open(OUTPUT_DIR / "automation_candidates_final.md", "w", encoding="utf-8") as f:
        f.write("# Step 2 Final Automation Candidate Analysis\n\n")
        f.write("Counts are inferred business executions after conservative merging of adjacent same-workflow fragments. Clustering proposes candidates; manual screenshot review establishes workflow meaning.\n\n")
        f.write("## Two-axis assessment\n\n")
        f.write("| Label | Executions | Raw fragments | Total min | Actors | Impact | Feasibility | Review outcome |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---|\n")
        for _, row in out.iterrows():
            f.write(f"| {row['label']} | {int(row['execution_count'])} | {int(row['raw_segment_count'])} | {row['total_minutes']:.1f} | {int(row['unique_actors'])} | {row['impact_score']:.2f} | {row['feasibility_score']:.2f} | {row['automation_call']} |\n")

        f.write("\n## Manual validation notes\n\n")
        for _, row in out.iterrows():
            f.write(f"- **{row['label']}**: {row['reconstruction_note']}\n")

        f.write("\n## Final decision\n\n")
        f.write(f"**Chosen target:** {decision['target']}\n\n")
        f.write(f"**Scope:** {decision['scope']}\n\n")
        f.write(f"**Why this one:** {decision['why']}\n\n")
        f.write(f"**Implementation form:** {decision['implementation']}\n\n")
        f.write(f"**Known limitation:** {decision['limitation']}\n\n")
        f.write("**Caveat:** Dataset B has no ground truth. Observed durations are used for relative prioritisation only because test-environment wait times are shortened.\n")

    print("Wrote outputs/automation_candidates_final.csv and .md")
    print(f"\nFINAL DECISION: {decision['target']}")
    print(decision["scope"])


if __name__ == "__main__":
    main()
