# From Desktop Operation Logs to a Review First Automation Prototype

**Dhruv Rohra**
Indian Institute of Technology Goa, Electrical Engineering
Round 1 email: `dhruv.kamal.24042@iitgoa.ac.in`

## Project outcome

This repository documents an end-to-end process-discovery and automation exercise. It starts with continuous desktop-operation logs, validates a segmentation method on labelled Dataset A, applies that method to unlabelled Dataset B, reconstructs recurring work candidates, manually validates them through screenshots, and implements a working prototype for the strongest validated opportunity.

The final selected workflow is **`process_003`: HR new-hire onboarding verification**. The local prototype accepts normalized mock case data, applies deterministic checks to required onboarding items, writes a Word review checklist and suggested note, and records an audit event. A human reviewer remains responsible for completing, flagging, or holding the HR portal case.

The final choice was not simply the highest score. `process_001`, the numerically highest-ranked candidate, was rejected after screenshot review showed unrelated finance adjustment, purchase-order, and contract-reference work mixed inside one cluster. An earlier `process_002` hypothesis was also rejected because it was mostly navigation and application-switch fragments. The evidence-supported target is final `process_003` only.

## The question addressed

The assignment is a chain of evidence, rather than a single classification problem:

```text
desktop events
  -> repaired session timeline
  -> process-boundary hypotheses
  -> recurring activity candidates
  -> inferred business executions
  -> screenshot validation
  -> scoped automation prototype
```

Dataset A supplies annotated boundaries and is used for model selection. Dataset B has no ground-truth boundaries or authoritative workflow labels. Its clusters are therefore treated as review hypotheses, not as proven business processes.

## Evidence at a glance

| Area | Result | Interpretation |
|---|---:|---|
| Dataset A | 63 sessions | Source for segmentation development and holdout evaluation |
| Dataset B | 15 sessions | Unlabelled source for workflow discovery |
| Raw Dataset B fragments | 339 | Technical segmentation evidence |
| Inferred executions | 264 | Conservative merging of compatible adjacent fragments |
| Raw recurring groups | 71 | Candidate hypotheses before recurrence screening |
| Review shortlist | 18 groups | At least five inferred executions |
| Final target | `process_003` | HR onboarding verification, manually validated |
| Prototype cases | 3 | Complete, missing-evidence, and conflicting-evidence paths |

## Step 1: segmentation method

### Timeline reconstruction before modelling

Recorder chunks are storage units, not business-task boundaries. Each session is reconstructed by following chunk references and sorting all events by `timestamp_ms` before feature creation. This was necessary because raw file order was not reliable for temporal analysis: one inspected sequence had 87 out-of-order adjacent pairs out of 765. UTF-8 is used explicitly because the event content includes Japanese text.

PELT was established as an interpretable baseline over timing-gap, application-switch, and clipboard behavior. It was useful as a high-recall source of likely behavior transitions, but it was not treated as the final business-boundary answer.

### Architecture selection and held-out result

The final architecture keeps PELT as an anchor generator. A `HistGradientBoostingClassifier` scores events in a plus/minus five-second neighborhood around every PELT proposal using local before-and-after evidence: interaction-type ratios, timing gaps, app-switch and clipboard activity, sequence-change signals, and distance from the anchor. A nearby event replaces the original anchor only when it is scored as more plausible.

| Approach considered | Finding | Decision |
|---|---|---|
| PELT only | Transparent baseline, limited strict localization | Retained as anchor generator |
| Candidate union | High recall but too many false boundaries | Rejected |
| Two-signal voting | Lost valid signals that were slightly time-offset | Rejected |
| Logistic candidate scorer | Underperformed PELT after correcting its formulation | Rejected |
| Fixed-weight fusion and temporal NMS | Did not reliably improve strict localization | Rejected |
| Standalone rich classifier | Improved F1@5s but lost broader F1@10s coverage | Rejected |
| PELT-centered local reranker | Better strict localization with comparable coverage | Selected |

Architecture selection used a fixed session-level 51-session development and 12-session holdout split, preventing events from one session from leaking into both sides of evaluation.

| Method | F1 within 5 seconds | F1 within 10 seconds |
|---|---:|---:|
| PELT-only baseline | 0.358 | 0.589 |
| Final local reranker | 0.466 | 0.593 |

The five-second improvement is evidence that the final method better locates annotated Dataset A boundaries. It is not presented as proof that a Dataset B cluster has correct business meaning. That separate question required context reconstruction and screenshot review.

## Step 2: Dataset B discovery and validation

The final model was retrained on all 63 Dataset A sessions and applied to Dataset B. It produced 339 raw fragments. Each fragment is represented with application, title, browser host, page route, event type, and interaction-pattern information; TF-IDF plus cosine-distance agglomerative clustering then creates recurring-work hypotheses.

Context extraction was corrected during development. A single broad text stream allowed incidental window text to dominate similarity, so application, title, browser host, and route were retained as separate sources. Raw fragments are merged only when directly adjacent, in the same cluster, compatible in page context, and within a ten-second gap. This conservative rule produced 264 inferred executions while retaining the raw fragment evidence for audit.

Candidate ranking combines recurrence, observed workload, operator breadth, consistency, and readiness as a transparent review screen. It is not treated as an objective business-value score. Groups with fewer than five inferred executions are removed from the review shortlist, leaving 18 of 71 groups.

### Screenshot review changed the outcome

`src/spot_check.py` sampled four intervals per shortlisted candidate across the available sessions. It reads documented screenshot references from events inside the selected interval, copies only those screenshots, and writes an evidence index containing the session, time range, interaction pattern, and applications. The evidence is retained in `outputs/spot_check/`.

| Candidate | Manual finding | Decision |
|---|---|---|
| `process_001` | Finance adjustment, purchase-order, and contract-reference work mixed together | Rejected despite highest apparent workload |
| Earlier `process_002` | Short navigation, clicks, and application-switch fragments | Rejected as incomplete workflow evidence |
| Final `process_003` | HR case review, required-item cross-checking, and Word checklist use | Selected |
| `process_004` | Repeatable payroll or compensation review | Deferred pending financial-control requirements |

Final `process_003` contains 12 inferred executions from 22 raw fragments, 9.48 observed minutes, and activity across four operators or machines. One reviewed sample crossed from purchase-order activity into the onboarding portal. That spillover was recorded rather than ignored and narrowed the automation scope to the stable onboarding-review portion only.

## Step 3: review-first onboarding prototype

The prototype is deliberately bounded. A case adapter exposes normalized mock data; deterministic rules evaluate required onboarding evidence; and the system produces a reviewer-ready Word checklist, exception summary, suggested verification note, and CSV audit record.

| Case | Prototype result | Remaining human work |
|---|---|---|
| `ONB-1001` | Ready for human completion | Verify source information and complete the portal case |
| `ONB-1002` | Human review required because evidence is missing | Resolve the exception or request evidence |
| `ONB-1003` | Human review required because evidence conflicts | Judge the conflict and complete or flag the case |

The rule engine uses explicit `PASS`, `MISSING`, `REQUIRES REVIEW`, and `NOT APPLICABLE` states. Four regression tests cover complete evidence, missing evidence, conflicting evidence, and not-applicable items. The tests validate the rule outcomes independently from document generation.

### Why deterministic Python was the right first implementation

The observed workflow is structured retrieval, required-item checking, exception identification, and document preparation. Deterministic rules were therefore more suitable than an LLM-led core decision path.

| Implementation form | Decision | Rationale |
|---|---|---|
| Deterministic Python assistant | Selected | Auditable, testable, and directly suited to structured checks |
| LLM agent | Deferred | No demonstrated need for probabilistic language interpretation; adds hallucination and governance risk |
| Workflow platform | Deferred | Adds configuration overhead without solving the demonstrated prototype need |
| Full browser RPA | Deferred | Production selectors and credentials are unavailable; reusable business logic is the stronger proof of value |

In a production setting, an authenticated API adapter would be preferable when available. A UI or RPA adapter could sit around the same normalized case model and deterministic rule layer where the source system is UI-only.

## Decision history

The final result reflects several corrections made during the project:

1. Timeline reconstruction was made explicit after finding out-of-order raw events.
2. Candidate union, voting, logistic ranking, fixed-weight fusion, and a standalone classifier were tested and rejected for specific recall, precision, or localization trade-offs.
3. Noisy context extraction was corrected before interpreting cluster identity.
4. Raw technical fragments were separated from inferred business executions through conservative merging.
5. An early lookup-to-document prototype direction was replaced when screenshot evidence invalidated the earlier `process_002` interpretation.
6. `process_001` was rejected despite attractive observed duration because a mixed cluster cannot support a reliable automation or ROI claim.

The important conclusion is not that clustering alone discovered a workflow. Clustering prioritized what to inspect; manual validation determined whether a candidate was coherent enough to automate.

## Repository guide

| Path | Purpose |
|---|---|
| `src/segment.py` | Dataset A session reconstruction, segmentation experiments, and holdout evaluation |
| `src/dataset_b_pipeline.py` | Dataset B inference, context extraction, clustering, and execution inference |
| `src/filter_candidates.py` | Recurrence screen for candidate review |
| `src/automation_candidate.py` | Quantitative and manual candidate-decision layer |
| `src/spot_check.py` | Screenshot sampling and evidence-index generation |
| `src/automation_prototype.py` | Local onboarding-review prototype |
| `tests/test_automation_prototype.py` | Deterministic rule-outcome regression tests |
| `outputs/segments.jsonl` | Required final Dataset B output |
| `outputs/spot_check/` | Selected manual-review evidence |
| `prototype_output/` | Generated review checklists and audit log |
| `FINAL_REPORT.docx` | Full technical and business report |
| `work_log.md` | Day-by-day experiments, pivots, and decisions |

## Reproducibility and execution record

The project was executed with Python 3.13 and the pinned dependencies in `requirements.txt`. Raw source data is intentionally excluded from the repository. With Dataset A and Dataset B present under `data/dataset_a` and `data/dataset_b` (or the supported nested layout), the following command sequence reproduces the pipeline:

```powershell
python -m pip install -r requirements.txt
python src\dataset_b_pipeline.py
python src\filter_candidates.py
python src\automation_candidate.py
python src\spot_check.py process_001 process_003 process_004
python src\automation_prototype.py
python -m unittest discover -s tests -v
```

The Dataset B submission artifact is `outputs/segments.jsonl`. It contains 264 inferred business executions with `session_id`, `start`, `end`, and `label` fields.

## Scope and path to production

This is a credible prototype rather than a production HR approval system.

- Dataset B has no authoritative process labels or boundaries; screenshot validation reduces but does not eliminate uncertainty.
- The observed Dataset B durations are comparative evidence in a compressed test environment, not production ROI or annual-savings claims.
- The prototype uses mock source data and has no connection to a production HR system.
- Production deployment requires HR-owned rules, approved credentials, field mapping, privacy and retention controls, integration contract tests, and reviewer feedback.
- The appropriate first rollout is shadow mode: generate checklists without portal write access, compare outcomes with reviewers, measure missed exceptions and false-ready cases, and only then consider wider automation.

The core result is a traceable decision process: validate segmentation on labelled data, use clustering to generate hypotheses rather than assert truth, reject misleading high-ranked candidates through manual evidence, and implement only the narrow automation that the available evidence can responsibly support.
