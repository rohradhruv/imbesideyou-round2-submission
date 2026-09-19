# From Operation Logs to an Automation Proposal

This repository is my submission for the I'mbesideyou AI Engineer take-home. The work starts with continuous desktop-operation logs and ends with a working, review-first automation prototype. The objective was not to build the most complex model possible; it was to recover recurring work reliably enough to make a defensible automation decision.

## Final outcome

The final selected workflow is **`process_003`: HR new-hire onboarding verification**. The prototype takes a case ID, retrieves structured mock case data, checks required onboarding items with deterministic rules, writes a reviewer-ready Word checklist and exception note, and appends an audit-log record. The reviewer remains responsible for the final complete, flag, or hold decision.

This was an evidence-driven choice. The highest-ranked cluster, `process_001`, was rejected after screenshot review showed finance adjustment, purchase-order, and contract-reference work mixed together. An earlier `process_002` hypothesis was rejected as fragmented navigation/click activity. After context cleanup, execution merging, and fresh screenshot review, final `process_003` was the strongest validated onboarding-review candidate.

## End-to-end approach

```text
Dataset A ground truth
  -> stitch chunks and sort timestamps
  -> develop and validate boundary detection
  -> PELT anchors plus local supervised reranking
  -> train final model on all Dataset A

Dataset B without ground truth
  -> segment raw events
  -> extract application, page, title, and interaction signatures
  -> cluster recurring patterns
  -> merge compatible adjacent fragments into inferred executions
  -> rank candidates and manually inspect screenshots
  -> select a bounded automation target
  -> run a review-first onboarding prototype
```

## Why the final segmentation method was chosen

Raw JSONL order could not be trusted for temporal analysis: one inspected sample had 87 out-of-order adjacent pairs out of 765. Sessions can also span multiple recorder chunks. Every session is therefore stitched and sorted by `timestamp_ms` before feature construction.

PELT was the initial baseline because it offers a practical, interpretable way to identify behavior changes. It was not treated as a complete solution. I tested candidate union, voting, logistic-regression ranking, weighted fusion, a standalone rich classifier, and a two-second movement cap. These experiments either introduced too many false boundaries, lost recall through timestamp misalignment, or did not improve the main localization objective consistently.

The final method keeps PELT as a high-recall anchor generator and uses a `HistGradientBoostingClassifier` to score nearby events from local timing, interaction, app-switch, clipboard, and sequence-change features. The best local event may replace the original PELT anchor. On a fixed 51-session development / 12-session holdout split of Dataset A, this improved F1 within five seconds from **0.358** to **0.466** while retaining comparable F1 within ten seconds (**0.589** to **0.593**).

These scores are validation evidence, not the whole story. They measure timestamp proximity on Dataset A; they do not prove that Dataset B clusters have correct business meaning. That is why the Dataset B decision also required manual workflow reconstruction.

## Dataset B process discovery and screenshot validation

The final Dataset B run processed 15 sessions into 339 raw segmentation fragments. Clustering uses TF-IDF features derived from event types, application names, window titles, browser hosts, page routes, and interaction transitions. Because a technical boundary can split one business case into several pieces, only directly adjacent fragments with the same cluster and compatible page context are merged. This produced **264 inferred business executions**.

Candidate ranking uses execution frequency, observed workload, actor breadth, consistency, and application stability. It is a transparent screening heuristic, not a claim of objective business value.

For manual validation, `src/spot_check.py` sampled four occurrences per candidate across sessions, copied the screenshots that fell inside each segment interval, and generated an index showing interval, event pattern, and applications. I inspected samples from `process_001`, final `process_003`, and `process_004`. This review rejected mixed/noisy groups and established the HR portal plus Word-checklist pattern behind the final onboarding scope. A selected-cluster sample that crossed from purchase-order work into onboarding was recorded as boundary spillover; the prototype intentionally targets only the stable onboarding-review portion.

## Decision history and corrections

This repository preserves the important corrections made during the project instead of presenting the final result as if it were obvious from the first run.

1. **Timeline repair came before modelling.** Session chunks were stitched and all events sorted before calculating gaps or interaction transitions. Without this correction, raw event order would have created false timing and sequence features.
2. **More boundary rules did not produce better boundaries.** Candidate union produced too many false positives; two-signal voting lost real but slightly time-offset signals; fixed-weight fusion and a standalone classifier exposed a strict-localisation versus broader-coverage trade-off. Those failures motivated local reranking around PELT anchors.
3. **Noisy context extraction was corrected before interpreting clusters.** Application, title, browser host, and page route were separated so incidental window text could not dominate process similarity.
4. **Raw segments were not mistaken for business executions.** Conservative adjacency and context-aware merging reduced 339 technical fragments to 264 inferred executions while preserving the underlying raw evidence.
5. **The first attractive automation choice was rejected.** `process_001` had the largest apparent workload, but screenshot evidence showed several unrelated finance, purchasing, and contract activities. The earlier `process_002` idea was also withdrawn because it was fragmentary navigation rather than a complete workflow.
6. **The prototype changed with the evidence.** An earlier lookup-to-document direction was replaced by onboarding verification only after final `process_003` showed a repeated HR case-review and Word-checklist pattern. The label `process_003` is the only final target name used in this repository.

This sequence is the main result of the project: quantitative ranking was useful for prioritising what to inspect, but manual validation determined whether a proposed cluster was safe to treat as an automation opportunity.

## Why deterministic Python automation

The selected boundary is structured retrieval, status checking, exception identification, and document generation. Deterministic Python rules were a better first implementation than an LLM agent, full RPA, or a workflow platform:

| Option | Decision | Reason |
|---|---|---|
| Deterministic Python | Selected | Small, auditable, testable, and directly fits structured checks |
| LLM agent | Deferred | No demonstrated need for probabilistic language reasoning; adds cost and hallucination risk |
| Workflow platform | Deferred | Adds configuration overhead for a small local prototype |
| Browser/RPA automation | Deferred | Production UI selectors and access were unavailable; business logic is more valuable to demonstrate first |

An API adapter is preferred for a production system where an API exists; browser automation remains a possible integration choice where UI-only access is unavoidable.

## Repository map

- `src/segment.py` — Dataset A segmentation development and holdout evaluation.
- `src/dataset_b_pipeline.py` — Dataset B inference, process recognition, clustering, and execution merging.
- `src/filter_candidates.py` — minimum-frequency candidate screen.
- `src/automation_candidate.py` — quantitative and manual candidate decision layer.
- `src/spot_check.py` — screenshot sampling and evidence index generation.
- `src/automation_prototype.py` — local onboarding-review prototype.
- `outputs/` — required segments plus intermediate audit artifacts.
- `prototype_output/` — generated checklists and audit log.
- `FINAL_REPORT.md` / `FINAL_REPORT.docx` — full technical and business rationale.
- `work_log.md` — day-by-day checklist of experiments, pivots, and results.

## Reproduce

Use Python 3.13 and install the pinned dependencies:

```powershell
python -m pip install -r requirements.txt
python src\dataset_b_pipeline.py
python src\filter_candidates.py
python src\automation_candidate.py
python src\spot_check.py process_001 process_003 process_004
python src\automation_prototype.py
python -m unittest discover -s tests -v
```

The raw data must be available under `data/dataset_a` and `data/dataset_b`, or the provided nested dataset layout. Raw data is intentionally excluded from Git.

For the separate Step 1 submission, upload `outputs/segments.jsonl` with the filename `segments.jsonl`.

## Limitations

- Dataset B has no ground-truth boundaries or authoritative process labels.
- Observed Dataset B durations are comparative only because the test environment shortens waiting time.
- The prototype uses mock source-system data and a generated Word template; it does not access a production HR system.
- Production deployment requires authoritative HR rules, approved credentials, field mapping, API or UI integration, security review, and pilot measurement.
- The prototype prepares evidence and exceptions; it does not make HR approval decisions.

## Submission identity

- Full name: **Dhruv Rohra**
- University: **Indian Institute of Technology Goa**
- Department or major: **Electrical Engineering**
- Round 1 email: **dhruv.kamal.24042@iitgoa.ac.in**

The repository is private. The same Round 1 email is used here and in the submission form.
