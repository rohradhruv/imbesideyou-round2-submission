"""
Filters process_summary.csv down to groups that are genuinely repeated
processes (execution_count >= MIN_EXECUTIONS), dropping the singleton/size-2
clusters that are clustering noise, not real automation candidates.

Run from the same place you ran dataset_b_pipeline.py (so OUTPUT_DIR
resolves the same way). Produces:
  outputs/process_summary_filtered.csv
  outputs/step2_candidates_filtered.md
"""

from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]   # was: .parent
OUTPUT_DIR = REPO_ROOT / "outputs"

# Drop any process group with fewer than this many inferred executions.
# 5 is a reasonable starting cutoff -- raise/lower and re-run cheaply,
# no need to re-run the pipeline itself.
MIN_EXECUTIONS = 5


def main():
    summary_path = OUTPUT_DIR / "process_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"Run dataset_b_pipeline.py first -- {summary_path} not found")

    summary = pd.read_csv(summary_path)
    before = len(summary)

    filtered = summary[summary["execution_count"] >= MIN_EXECUTIONS].copy()
    filtered = filtered.sort_values("priority_score", ascending=False).reset_index(drop=True)

    dropped = summary[summary["execution_count"] < MIN_EXECUTIONS]
    after = len(filtered)

    print(f"process_summary.csv: {before} groups -> {after} groups (dropped {before - after} with < {MIN_EXECUTIONS} executions)")
    print("\nDropped groups (for reference -- these are the singleton/noise clusters):")
    print(dropped[["label", "execution_count", "raw_segment_count", "total_minutes"]].to_string(index=False))

    filtered.to_csv(OUTPUT_DIR / "process_summary_filtered.csv", index=False, encoding="utf-8-sig")

    # Rewrite the human-readable shortlist using only the filtered groups
    with open(OUTPUT_DIR / "step2_candidates_filtered.md", "w", encoding="utf-8") as f:
        f.write("# Dataset B — Step 2 Automation Candidates (filtered)\n\n")
        f.write(f"Groups with fewer than {MIN_EXECUTIONS} inferred executions were dropped as clustering noise, "
                f"not genuine repeated processes ({before - after} of {before} groups removed).\n\n")
        f.write("| Rank | Label | Executions | Raw segments | Total min | Actors/Machines | Consistency | Readiness | Priority |\n")
        f.write("|---:|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for i, r in filtered.head(15).iterrows():
            f.write(f"| {i+1} | {r['label']} | {int(r['execution_count'])} | {int(r['raw_segment_count'])} | {r['total_minutes']:.1f} | "
                    f"{int(r['unique_actors_or_machines'])} | {r['consistency']:.2f} | "
                    f"{r['readiness']:.2f} | {r['priority_score']:.1f} |\n")
        f.write("\n## Caveats\n\n")
        f.write("- Dataset B has no ground truth, so process groups are inferred from recurring event/application signatures.\n")
        f.write(f"- Groups with fewer than {MIN_EXECUTIONS} inferred executions were excluded here as likely clustering noise "
                f"rather than genuine repeated business processes; see process_summary.csv for the unfiltered list.\n")
        f.write("- Test-environment waiting times are shortened; compare processes relatively rather than treating observed duration as production duration.\n")

    print(f"\nWrote {OUTPUT_DIR / 'process_summary_filtered.csv'}")
    print(f"Wrote {OUTPUT_DIR / 'step2_candidates_filtered.md'}")


if __name__ == "__main__":
    main()
