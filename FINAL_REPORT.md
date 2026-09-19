# From Operation Logs to a Review First Automation Proposal

## Executive summary

I transformed raw desktop-operation logs into inferred work executions, identified repeated work in Dataset B, and built a working prototype for the most defensible opportunity: **HR new-hire onboarding verification**. The prototype retrieves structured case data through an adapter, evaluates transparent completeness rules, produces a checklist and exception summary, and records an audit event. A reviewer still decides whether to complete or flag the HR case.

This scope was selected for its credible implementation path, not merely its statistical rank. The highest-volume cluster was rejected because screenshot review showed different finance, purchasing, and contract workflows inside it. Dataset B has no ground truth, so clustering is a workflow hypothesis generator, not proof of business-process identity.

## Problem framing

The task is a chain of decisions rather than one classification problem:

`raw events -> boundaries -> work executions -> recurring workflow hypotheses -> automation decision -> bounded prototype`.

Dataset A supplies process-boundary ground truth and was used to develop and evaluate segmentation. Dataset B has no ground truth and uses different departments and applications, so it was used for unsupervised discovery, screenshot validation, and business prioritisation.

## Step 1 Segmentation

### Preparation and final method

Each session is reconstructed by stitching chunks and sorting by `timestamp_ms`. Chunks are recorder storage units, not work boundaries, and raw JSONL order was observed to be non-chronological: one inspected sample had 87 out-of-order adjacent pairs out of 765. Files are read with explicit UTF-8 because the data includes Japanese text.

The final model uses PELT (`pen=3`) as a high-recall anchor generator on timing-gap, app-switch, and clipboard features. For every anchor, a `HistGradientBoostingClassifier` scores nearby events in a plus/minus five-second window using local before/after features: event-type ratios, click/key/clipboard behavior, timing gaps, app-switch activity, PELT offset, and sequence-change signal. An anchor moves only if a nearby event receives a higher probability; no arbitrary two-second movement cap is applied.

### Evaluation

Architecture selection used a fixed 51-session development / 12-session holdout split of Dataset A, at session level to prevent event leakage.

| Method | F1 within 5 seconds | F1 within 10 seconds |
|---|---:|---:|
| PELT-only baseline | 0.358 | 0.589 |
| PELT-centered local reranker | 0.466 | 0.593 |

The strict-localization improvement is 0.108 F1 while wider-tolerance performance is maintained. After selection, the model was trained on all 63 Dataset A sessions for Dataset B inference. That all-data model is not presented as a new held-out evaluation claim.

### What the F1 result does and does not establish

The F1 result is important because it validates the boundary-location decision on held-out Dataset A sessions. It is not the full value of the work. The practical contribution was the sequence of diagnoses that made a reasonable final method possible: raw event ordering was unsafe; chunks could not be treated as work boundaries; a behavior change was not automatically a process change; and a high-recall candidate set needed a local decision mechanism rather than a larger collection of heuristic rules.

The final design therefore has a deliberate division of responsibility. PELT proposes where a transition may exist. The local classifier uses evidence immediately before and after that point to decide which nearby event is the most plausible boundary. This is more transferable than application-specific rules because Dataset B uses different applications from Dataset A. It also avoids claiming that an F1 score alone can recover business semantics.

### Approaches considered and rejected

| Approach | Result | Decision |
|---|---|---|
| PELT-only | Useful transparent baseline; insufficient strict localization | Retained as anchor generator |
| Full supervised segmentation pipeline | Plausibly stronger but disproportionate cost in a seven-day task | Rejected on time-to-value grounds |
| Any-signal union | Strong candidate recall but many false positives | Rejected |
| Two-signal voting | Better precision, but misses signals that are not time-aligned | Rejected |
| Logistic-regression candidate scorer | Underperformed PELT after correcting the candidate formulation | Rejected |
| Fixed-weight fusion plus temporal NMS | Did not reliably improve strict localization | Rejected |
| Standalone rich-feature classifier | F1@5s 0.485 vs 0.358, but F1@10s 0.505 vs 0.589 | Diagnosed localization/detection trade-off; replaced |
| Two-second reranking cap | F1@5s/F1@10s 0.398/0.601 | Rejected for unrestricted reranking, 0.466/0.593 |
| Per-application weights | Cannot plausibly transfer to Dataset B's unseen applications | Rejected before implementation |

The rejected experiments were not discarded effort. Candidate union demonstrated that useful signals existed but could not be safely flattened into yes/no decisions. Voting showed that real signals were often close in time but not exactly aligned. The standalone rich classifier showed that local context improved strict localization but could lose useful PELT coverage. Together, those findings led to the final PELT-centered reranker rather than a generic "more ML" solution.

## Step 2 Dataset B discovery and prioritisation

The final pipeline produced 339 raw segments from 15 Dataset B sessions. A TF-IDF representation of application, title, page route, event-type, and interaction-pattern tokens was clustered with cosine-distance agglomerative clustering. Raw fragments were conservatively merged only when directly adjacent, assigned to the same cluster, and compatible in page context. This produced 264 inferred business executions while retaining raw evidence in `outputs/segment_event_recognition.csv`.

Seventy-one raw groups were found. Groups with fewer than five inferred executions were excluded from the shortlist, leaving 18 recurring candidates. This is a screening rule, not a claim that small clusters cannot represent work.

### Manual screenshot review

Dataset B has no process-boundary ground truth, so the clustering output was treated as a shortlist rather than a final answer. I used `src/spot_check.py` to choose four occurrences per candidate across the available sessions. For every chosen interval, the helper reads documented `payload.file_reference.filename` fields from screenshot events, copies only screenshots inside the interval, and writes an index containing the session, time range, interaction pattern, and applications. I then reconstructed what the worker was doing from the screenshots and the index rather than inferring workflow meaning from a score.

This review was consequential. It rejected the numerically prominent `process_001` cluster because its screenshots crossed finance adjustment, purchase-order, and contract-reference work. It also rejected the earlier `process_002` hypothesis because it consisted largely of short transitions rather than a complete repeatable task. Fresh final `process_003` samples repeatedly showed an HR onboarding case in the portal and a new-hire checklist in Word. One sampled interval crossed from purchase-order work into onboarding; this was recorded as boundary spillover and narrowed the prototype scope to the stable onboarding-review portion.

| Candidate | Evidence | Decision |
|---|---|---|
| `process_001` | 15 executions, 31.5 observed minutes, four operators; screenshots showed mixed finance, purchase-order, and contract work | Rejected as incoherent despite high apparent impact |
| Earlier `process_002` | Short navigation, click, and application-switch fragments | Rejected |
| Final `process_003` | 12 executions, 22 raw fragments, 9.5 observed minutes, four operators; screenshots showed a repeated onboarding review workflow | Selected |
| `process_004` | 11 executions, 11.0 observed minutes, four operators; payroll/compensation review | Deferred because financial-control risk needs deeper validation |

The resulting implementation priority was: (1) final `process_003` onboarding verification, because it combines repeatable structured checks with a low-risk human approval boundary; (2) `process_004` only after finance-control requirements are understood; and (3) all other candidates deferred or rejected because they were mixed, fragmentary, too small, or not manually validated. This ordering deliberately overrides the raw score when the workflow evidence is weak.

The process labels changed during iterative clustering; this report uses **`process_003` only** as the final submission-facing name for onboarding verification. An earlier `process_002` hypothesis was rejected after review because it contained fragmentary activity, not a coherent business workflow. Refreshed `process_003` samples show HR onboarding and the Word checklist pattern. One sample begins in the purchase-order/inventory portal and ends in the HR onboarding portal, indicating boundary spillover rather than a shared workflow. The prototype therefore targets only the repeatedly observed onboarding-review portion: a worker reviews an HR portal case, checks required items, uses a Word checklist, and completes or flags the case.

## Step 3 Prototype

The deterministic Python assistant supports a complete case, a missing-evidence case, and a conflicting-evidence case. It assigns `PASS`, `MISSING`, `REQUIRES REVIEW`, or `NOT APPLICABLE` to each checklist item; creates a Word review checklist; writes a suggested verification note; and appends a CSV audit record.

The deterministic rule outcomes are covered by standard-library regression tests for the complete, missing-evidence, conflicting-evidence, and not-applicable paths. The local end-to-end run also generated all three reviewer checklists and audit records.

| Case | Result |
|---|---|
| `ONB-1001` | Ready for human completion |
| `ONB-1002` | Human review required because evidence is missing |
| `ONB-1003` | Human review required because evidence conflicts |

The tool does not submit a portal action. The logs do not provide production credentials, authoritative HR rules, API contracts, or approval policy. Treating their absence as permission to automate approval would be unjustified.

### Why deterministic rules instead of an LLM agent

The observed task is structured: required fields and evidence status map to explainable checks. Deterministic logic is easier to validate, test, audit, and revise with HR stakeholders. An LLM could later help with unstructured attachments or exception summaries, but it is not needed for the first-value workflow and would add avoidable governance risk.

### Why this implementation form

| Form | Decision | Rationale |
|---|---|---|
| Deterministic Python assistant | Selected | Fits structured retrieval, rule checks, document generation, and local demonstration |
| LLM agent | Deferred for core logic | No demonstrated need for probabilistic interpretation; would add cost, latency, and hallucination risk |
| Workflow platform | Deferred | Adds orchestration/configuration overhead without solving a demonstrated prototype need |
| Full RPA/browser replay | Deferred | Production UI access and selectors are unknown; it would show click replay rather than the reusable business rules |

The production architecture is deliberately adapter-based. An authenticated API adapter would be preferred when a source-system API exists. If the real system is UI-only, an RPA adapter can be added around the same normalized case model and deterministic validation layer. This keeps business rules separate from a volatile integration surface.

## Expected impact and manual work remaining

The sample contains 12 inferred onboarding-review executions totaling 9.5 observed minutes. Test-environment waiting time is compressed, so this is **relative prioritisation evidence**, not a production savings forecast. The expected first-release value is reduced preparation and more consistent exception identification, not elimination of human accountability.

The reviewer still verifies source records, resolves missing or ambiguous evidence, applies policy exceptions, and completes or flags the portal case. A production pilot should measure reviewer preparation time, exception rate, correction rate, and completion time before claiming financial ROI.

## Risks and rollout

| Risk | Evidence or rationale | Mitigation |
|---|---|---|
| Dataset B labels may be wrong | Dataset B has no ground truth | Screenshot sampling, reviewer feedback, and versioned label mappings |
| Cluster/boundary spillover | One selected-cluster sample begins in a purchase-order portal before the onboarding flow | Scope the prototype to the repeated onboarding portion; add route-aware post-processing before production |
| Over-segmentation | Raw fragments exceeded inferred executions | Preserve raw evidence and merge only adjacent same-context fragments |
| HR-policy mismatch | Logs do not contain authoritative rules | Configure rules with HR owners and retain human approval |
| Source-system changes | Prototype uses a mock adapter | Stable adapter, contract tests, and change monitoring |
| Incorrect portal action | Approval has business impact | Keep complete/flag action human-controlled initially |
| Sensitive employee data | Onboarding includes personal information | Least privilege, audit logging, encryption, retention limits, access review |

Recommended rollout: shadow-run on completed or live cases without submission rights; compare findings with reviewers; tune HR-owned rules; deploy as a preparation assistant with audit logging; then consider wider automation only after measured accuracy and control ownership are established.

## Seven day allocation

| Days | Main work | Why this allocation was appropriate |
|---|---|---|
| 1–2 | Data orientation, timeline repair, chunk stitching, and PELT baseline | Correct event ordering and session reconstruction were prerequisites for every later claim |
| 3–4 | Boundary experiments and holdout evaluation | Several fusion and classifier variants were tested to select a method by evidence rather than novelty |
| 5 | Train final model on Dataset A and discover Dataset B workflow candidates | Dataset B analysis was deferred until the segmentation method was fixed |
| 6 | Execution merging, candidate ranking, and screenshot reconstruction | Business-process meaning could not be inferred from unsupervised labels alone |
| 7 | Prototype, regression tests, report, README, and work log | A bounded working tool and an honest account of limitations were more valuable than unfinished breadth |

The allocation intentionally avoided spending the full week optimizing one metric. The assignment asks for a working automation proposal with credible ROI reasoning; validation, manual reconstruction, and a finished prototype were therefore protected as first-class work.

## Conclusion

The project favors a defensible automation boundary over a broad but unsupported claim. It uses validated segmentation to structure raw telemetry, clustering to generate rather than assert Dataset B workflow hypotheses, screenshot review to reject a misleading top-ranked cluster, and a working onboarding-review assistant whose remaining human work is explicit. That is the highest-confidence route to practical ROI from the available evidence.
