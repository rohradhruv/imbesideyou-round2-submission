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

### Segmentation decision trail

The model was developed as a sequence of falsifiable choices. First, I repaired temporal order and reconstructed complete sessions; without that, both event-gap features and evaluation would have been unreliable. Second, I used PELT to identify areas where interaction behavior changed, because it provided a transparent baseline and useful coverage. Third, I tested whether additional signals should be combined by rules. The answer was no: union was noisy and voting was too brittle when signals arrived a few seconds apart. Finally, I used the richer evidence as local context for a reranker rather than as a global event classifier.

This design has a practical interpretation. PELT answers, "where should I look?" The local model answers, "which event close to that proposed transition best represents the boundary?" It does not invent a boundary far from observed behavior, and it does not depend on hard-coded application names. The approach is therefore more defensible for Dataset B, whose applications and departments differ from Dataset A, than per-application rules would be.

The final score should be read with equal care. F1@5s improved because the reranker made boundaries more precisely located. F1@10s remained close to the baseline, which shows that the method retained broad transition coverage. This is useful validation of the segmentation component, but it does not validate the semantic identity of a Dataset B workflow. That second question is why the pipeline retained event context, grouped segments conservatively, and required screenshot review.

## Step 2 Dataset B discovery and prioritisation

The final pipeline produced 339 raw segments from 15 Dataset B sessions. A TF-IDF representation of application, title, page route, event-type, and interaction-pattern tokens was clustered with cosine-distance agglomerative clustering. Raw fragments were conservatively merged only when directly adjacent, assigned to the same cluster, and compatible in page context. This produced 264 inferred business executions while retaining raw evidence in `outputs/segment_event_recognition.csv`.

Seventy-one raw groups were found. Groups with fewer than five inferred executions were excluded from the shortlist, leaving 18 recurring candidates. This is a screening rule, not a claim that small clusters cannot represent work.

### Manual screenshot review

Dataset B has no process-boundary ground truth, so the clustering output was treated as a shortlist rather than a final answer. I used `src/spot_check.py` to choose four occurrences per candidate across the available sessions. For every chosen interval, the helper reads documented `payload.file_reference.filename` fields from screenshot events, copies only screenshots inside the interval, and writes an index containing the session, time range, interaction pattern, and applications. I then reconstructed what the worker was doing from the screenshots and the index rather than inferring workflow meaning from a score.

This review was consequential. It rejected the numerically prominent `process_001` cluster because its screenshots crossed finance adjustment, purchase-order, and contract-reference work. It also rejected the earlier `process_002` hypothesis because it consisted largely of short transitions rather than a complete repeatable task. Fresh final `process_003` samples repeatedly showed an HR onboarding case in the portal and a new-hire checklist in Word. One sampled interval crossed from purchase-order work into onboarding; this was recorded as boundary spillover and narrowed the prototype scope to the stable onboarding-review portion.

### Why manual review changed the answer

The screen review was not a cosmetic confidence check. The first-ranked candidate had the largest apparent time opportunity, but it was a mixed cluster. A system trained or automated against that label would have combined financially sensitive invoice or expense work, purchase-order management, and contract-reference activity. Even a technically correct click replay would therefore have had an unclear business owner and an invalid ROI denominator.

The earlier `process_002` hypothesis failed for a different reason. Its intervals had some recurring interaction patterns, but they were mostly navigation, clicks, and short application transitions. That can be useful contextual evidence for segmentation, but it is not itself a business workflow with a stable start, input, decision, and output. The final target was chosen because its samples had a clearer semantic unit: open or review an HR onboarding case, cross-check required items, use a checklist, then decide whether the case is ready or needs escalation.

This is also why the report distinguishes raw fragments from inferred business executions. The 339 raw fragments are a truthful representation of technical activity after segmentation. The 264 execution estimate is a conservative analytical layer created only when adjacent fragments shared a cluster and compatible context. Neither number is silently presented as the count of complete production workflows. The separate figures preserve auditability and make the underlying uncertainty visible.

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

### Prototype workflow and test evidence

The prototype follows a narrow preparation workflow: a case adapter provides normalized employee and onboarding-item data; deterministic checks assign an item status; the assistant creates a review document and suggested note; and an audit row records the result. The generated document makes the underlying evidence visible to the reviewer rather than returning an unexplained pass/fail judgment. A complete example is marked ready for human completion, while missing or conflicting evidence is explicitly routed to human review.

The regression tests cover the four core rule outcomes: complete evidence, missing evidence, conflicting evidence, and an item that is not applicable. This is modest by production standards, but it is deliberately aligned with the scope of the prototype. The tests verify business-rule behavior independently of the generated document and provide a safe starting point for later HR-owned policy changes. What is not tested or claimed is live HR portal access, approved policy mapping, real employee data handling, or autonomous portal submission.

## Expected impact and manual work remaining

The sample contains 12 inferred onboarding-review executions totaling 9.5 observed minutes. Test-environment waiting time is compressed, so this is **relative prioritisation evidence**, not a production savings forecast. The expected first-release value is reduced preparation and more consistent exception identification, not elimination of human accountability.

The reviewer still verifies source records, resolves missing or ambiguous evidence, applies policy exceptions, and completes or flags the portal case. A production pilot should measure reviewer preparation time, exception rate, correction rate, and completion time before claiming financial ROI.

### Measurement plan for a production pilot

The first pilot should run in shadow mode. The assistant would produce a checklist for a set of cases already reviewed by staff, without any permission to alter the portal. Its item-level findings would then be compared with the final human disposition. The useful metrics are agreement on routine checks, false-ready rate, missed-exception rate, reviewer preparation time, and percentage of cases needing policy interpretation. These measures are more meaningful than a generic automation percentage because they distinguish safe routine preparation from exceptions that properly remain human work.

Only after shadow-mode agreement is understood should the assistant be used on live cases as a preparation aid. The next release can allow a reviewer to accept the generated checklist and submit the action themselves. A later decision about automated portal action would require explicit control ownership, reliable source integration, audit retention, and measured error rates. This staged plan prevents the local prototype from being mistaken for a production approval system.

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

## Detailed implementation narrative

### Day 1 and Day 2 reconstructing what the recorder actually captured

The first implementation risk was treating the provided files as an already usable event timeline. They were not. The source is stored in chunks, and chunks describe recorder storage rather than the beginning and end of a worker's task. I therefore followed chunk references to reconstruct each session before any feature extraction. I also sorted reconstructed events by `timestamp_ms`. This was not an optional cleanup: in one inspected sequence, 87 of 765 adjacent pairs were out of chronological order in the raw read order. A model using that order would calculate false idle gaps, false event transitions, and unreliable context changes.

The practical work on this stage was deliberately small and inspectable. I used explicit UTF-8 input because the event content included Japanese text and Windows default decoding was unsafe. I preserved a discovered irregularity in the evidence trail: one manifest had `next_chunk_id: null` while `is_session_end` was false. The pipeline handles the data available to it, but that inconsistency means chunk chaining is a dataset assumption that should be monitored in a real ingestion system.

I then built PELT as a baseline over gap, application-switch, and clipboard behavior. The baseline was useful for two reasons. First, it produces an intelligible hypothesis: a boundary is likely near a sustained behavioral change. Second, it made later alternatives comparable. I selected penalty 3 rather than penalty 2 because the lower penalty created more boundaries without a proportionate improvement in alignment. At this point, I did not consider a PELT point a final business-process boundary. It was a candidate location.

### Day 3 learning why a larger rule set was not the answer

The next question was whether better segmentation could come from simply adding more heuristics. I generated candidates from PELT, idle gaps, application/context changes, and sequence changes. The union looked encouraging initially because it covered many annotated boundaries. On inspection, it created too many false positives: normal clicks, temporary context changes, or a short pause could be interpreted as a workflow transition. This was an important failure because it showed that high candidate recall is not equivalent to usable segmentation.

I next tried two-signal voting. That reversed the problem. It reduced some noise, but genuine signals in desktop behavior are not always aligned to the same event timestamp. For example, an application change can occur a few seconds before a clipboard action that makes the boundary visually obvious. A strict voting rule discarded these slightly offset but legitimate cues. A candidate-level logistic-regression formulation was also tried and rejected after correcting the candidate setup because it underperformed the PELT baseline.

These experiments narrowed the design space. The useful information was local and relative, not a collection of universally decisive boolean rules. The eventual model should be allowed to compare nearby events around a plausible transition instead of independently declaring every event to be a boundary.

### Day 4 selecting the final segmentation architecture

I tested fixed-weight fusion with temporal spreading and non-maximum suppression before moving to the final model. It did not consistently improve strict localization; tuning weights also made the behavior harder to explain. I then created richer before-and-after features around candidate points: proportions of click, key, clipboard, and other interaction types; local application-switch activity; timing-gap characteristics; sequence-change information; and distance from the PELT proposal.

A standalone rich classifier produced an apparently attractive F1@5s of 0.485. It was not selected because its F1@10s fell to 0.505, below PELT's 0.589. That comparison mattered. Optimizing only the strict metric would have selected a model that made some boundaries sharper while losing broader coverage. I instead used the rich features as a local reranker for PELT anchors. For each PELT anchor, the reranker evaluates events in a plus/minus five-second window and chooses a more probable nearby boundary when justified. I also compared a two-second movement cap with unrestricted local reranking. The cap yielded 0.398/0.601 at F1@5s/F1@10s; unrestricted reranking yielded 0.466/0.593. The unrestricted model was selected because the substantial strict-localization gain came with nearly unchanged ten-second performance.

The split was done by session: 51 development sessions and 12 holdout sessions, with seed 42. This avoided leakage from events in the same desktop session. Once that decision was locked, I retrained on all 63 Dataset A sessions to create the Dataset B model. I kept the distinction clear in the report: the all-data model is for inference, not a new evaluation result.

### Day 5 discovering why raw labels needed correction

The final Dataset B run processed 15 sessions and yielded 339 raw segments. I constructed textual and interaction-pattern representations using application, title, browser host, page route, event type, and interaction-pattern information, then used TF-IDF and cosine-distance agglomerative clustering. During implementation, the installed scikit-learn version raised a sparse-input compatibility issue. The dataset was small enough for dense conversion, so I made that conversion explicitly rather than changing the clustering logic or silently suppressing the error.

The first clustering outputs were not accepted at face value. A key problem was noisy context: application and page text were mixed into a broad token stream, so incidental labels could dominate similarity. I reworked extraction to retain application, title, browser host, and page route as separate sources. This made it possible to inspect why segments clustered together rather than treating a cosine score as a semantic explanation.

The first regenerated summary had 71 groups. A transparent recurrence screen removed groups with fewer than five observations, retaining 23 groups in the earliest raw-fragment view. At that stage the apparent leading labels included `process_001`, `process_002`, and `process_003`. This was a provisional shortlist only. The high rank of a group measures frequency, observed time, and pattern consistency; it cannot establish that every interval corresponds to the same business task.

### Day 6 correcting the business-execution view and the early target decision

The next correction was conceptual and technical. The 339 items were technical fragments produced by segmentation. A business user does not necessarily start a new task because a short context change happened. I added conservative execution inference: only directly adjacent fragments in the same cluster were merged, page context had to be compatible, and the gap could not exceed ten seconds. The revised output contained 264 inferred executions from the 339 fragments. The merged execution record retained its raw-fragment count, pattern signature, context, and observed duration so the result remained auditable.

The first implementation of the summary after that change exposed a real pipeline error: `process_summary` expected a `pattern_signature` column that had not been carried into the execution table. The run failed with a `KeyError`. I corrected the schema propagation rather than bypassing the metric. The next full run completed, reported 264 inferred executions, and reduced the five-execution shortlist to 18 groups. This is a useful example of why output review mattered: a pipeline can appear sophisticated while a broken intermediate schema invalidates downstream reasoning.

At this point, `process_001` remained top-ranked by observed minutes, with 15 inferred executions, 16 raw fragments, 31.46 observed minutes, and activity across four operators or machines. It would have been easy to select it from the ranking alone. The screenshot evidence contradicted that choice. The sampled intervals included finance invoice or expense adjustment, purchase-order activity, and contract-reference work. The shared digital trace was not a single workflow. I explicitly rejected it even though it had the largest apparent opportunity.

An earlier decision also selected a label called `process_002`, based on a lookup-to-document interpretation. Fresh screenshot samples showed that this label was mostly short navigation, clicking, and application switching rather than an end-to-end repeatable business process. I withdrew that decision. To preserve an honest history, the final labeling reserves `process_003` for the validated onboarding workflow and treats the earlier `process_002` interpretation as rejected. This avoids the common reporting failure of quietly renaming a failed hypothesis as though it had always been the final target.

### Manual screenshot validation procedure

I used the spot-check helper to sample four occurrences from each shortlisted candidate. The helper does not guess file paths from timestamps. It reads the documented screenshot reference in an event payload, selects screenshots that fall inside the sampled interval, copies them into a labelled output folder, and writes an `index.md` with session ID, segment number, interval, interaction pattern, and application trace. The resulting folders are committed under `outputs/spot_check` so the review path can be reproduced from the repository.

The selected `process_003` screenshots repeatedly showed workers reviewing HR onboarding cases, cross-checking required items, and using a Word new-hire onboarding checklist. This gave the candidate an identifiable input, a repeated verification activity, and a meaningful decision outcome: complete, flag, or hold. One sample began in purchase-order activity before moving into the HR portal. I did not ignore that anomaly. It is evidence of boundary spillover, so the prototype excludes any claim to automate the preceding activity and targets only the stable onboarding verification portion. `process_004` also appeared repeatable, but it concerned payroll or compensation work; it was deferred because financial-control requirements and approval ownership are not inferable from screenshots.

### Day 7 changing the prototype to match the validated evidence

The first prototype direction was a lookup-to-Word helper. It was sensible only under the now-rejected earlier `process_002` interpretation. Once the screenshot evidence changed the target, I changed the implementation rather than trying to force the code to justify the first idea. The final prototype is a local HR new-hire onboarding review assistant. It accepts a normalized mock case through an adapter, evaluates required onboarding evidence with deterministic rules, generates a Word checklist and suggested verification note, and adds an audit record to CSV.

Three cases demonstrate the intended control boundary. `ONB-1001` is complete and is marked ready for human completion. `ONB-1002` has missing evidence and is marked for human review. `ONB-1003` has conflicting evidence and is also marked for human review. The execution output reports completion for all three generated review artifacts, not autonomous completion of HR portal cases. This wording matters: the prototype assists preparation and makes exceptions explicit; it does not claim to submit, approve, or overrule a reviewer.

I added four standard-library unit tests covering complete evidence, missing evidence, conflict, and not-applicable cases. These tests were chosen to validate the actual deterministic decision rules rather than superficial document appearance. The prototype uses deterministic logic because the evidence supports structured checks, and deterministic outcomes are easier for HR owners to audit and update. An LLM may later help summarize unstructured exception material, but it is unnecessary for the core first-value path and would introduce avoidable non-determinism.

### What this work demonstrates and what it does not

The completed work demonstrates an evidence trail: a holdout-tested boundary method, a Dataset B discovery pipeline, conservative execution inference, an explicit recurrence screen, manual screenshot validation that overrode weak numerical conclusions, a scoped prototype, and tests for its rules. It also demonstrates a willingness to reject attractive but incoherent candidates. That is the central judgment the assignment asks for: selecting a feasible automation opportunity rather than producing an impressive-sounding label.

It does not demonstrate production ROI, policy completeness, real HR integration, or safe autonomous approval. The observed 9.48 minutes across 12 inferred onboarding-review executions is an indication of relative opportunity in the supplied environment, not a claim of annual savings. A real pilot would require HR-owned rules, approved source access, a data-handling review, a shadow-mode comparison with human reviewers, and measurement of preparation time, exception rate, correction rate, and false-ready outcomes. Those limitations are not omissions from the analysis; they are the correct boundary between a selection-assignment prototype and a production deployment.

## Conclusion

The project favors a defensible automation boundary over a broad but unsupported claim. It uses validated segmentation to structure raw telemetry, clustering to generate rather than assert Dataset B workflow hypotheses, screenshot review to reject a misleading top-ranked cluster, and a working onboarding-review assistant whose remaining human work is explicit. That is the highest-confidence route to practical ROI from the available evidence.
