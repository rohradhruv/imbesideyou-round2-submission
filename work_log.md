# Work Log — I'mbesideyou AI Engineer Take Home

This log records the actual decision path. Completed boxes indicate work performed; rejected approaches are retained because they informed the final design.

## Day 1 — Understand the data and the business question

- [x] Read the brief and schema; identified the task as process recovery and automation discovery, not just event classification.
- [x] Separated the assignment into two evidence regimes: Dataset A provides annotated boundaries for model development, while Dataset B has no workflow labels and therefore needs hypothesis generation plus manual validation.
- [x] Manually traced Dataset A work against raw events and identified app switches, clipboard activity, shortcuts, and local behavior changes as possible signals.
- [x] Compared the recorder representation with the business question. A change in application, title, or event type can indicate a transition, but it can also be a normal step within one task; this prevented me from treating every technical change as a business boundary.
- [x] Confirmed that a chunk is recorder storage, not a business-process boundary.
- [x] Recorded UTF-8 as mandatory because Japanese text fails under Windows' default cp1252 encoding.

**Outcome and reasoning.** The first day changed the scope of the solution. The deliverable could not be a generic classifier that emits timestamps: it had to support a credible chain from raw activity to a repeatable workflow decision. This distinction later became important when a high-ranked Dataset B cluster looked valuable numerically but failed manual workflow review.

## Day 2 — Repair the event timeline and build a baseline

- [x] Found raw JSONL order was not safe for temporal analysis: 87 of 765 adjacent pairs were out of timestamp order in one inspected sample.
- [x] Treated this as a data-integrity issue rather than a cosmetic cleanup: gap features, sequence transitions, and boundary evaluation would all be wrong if events were used in file order.
- [x] Implemented full-session chunk stitching and `timestamp_ms` sorting before feature creation.
- [x] Recorded one inconsistent chunk manifest (`next_chunk_id: null` with `is_session_end: false`) as a limitation.
- [x] Built a PELT baseline using event gap, app-switch, and clipboard features.
- [x] Selected `pen=3` over `pen=2`: similar hit rate with fewer unnecessary boundaries.

**What changed because of this day.** I made session reconstruction an explicit pipeline stage rather than assuming each JSONL file was already a valid timeline. PELT was useful because it gave an interpretable starting point and broad coverage, but early examples showed that its proposed locations were often near a real boundary rather than precisely on it. That became the motivation for local refinement rather than abandoning the baseline.

## Day 3 — Test alternatives instead of assuming PELT is enough

- [x] Considered a full supervised boundary pipeline; rejected it initially because it risked consuming the seven-day budget needed for process analysis and a working prototype.
- [x] This was a scope decision, not a claim that supervised sequence models are ineffective. The assignment required an end-to-end decision and prototype, so model complexity had to earn its cost.
- [x] Tested candidate union from PELT, idle-gap, app/context, and sequence-change signals.
- [x] Observed high candidate recall but poor precision from binary union.
- [x] Recorded why the union failed: it treated correlated and weak signals as equally decisive, creating too many boundaries around normal interaction changes.
- [x] Tested two-signal voting; rejected it because valid signals were often offset by seconds and recall fell.
- [x] Tested candidate-level logistic regression; rejected it because it underperformed PELT after correcting the candidate formulation.

**Interpretation.** These attempts established that the problem was not solved by collecting more boundary heuristics. Signals were useful, but their timing and reliability differed. A strict voting rule lost legitimate transitions; a loose union created noise. The next design therefore retained PELT as the candidate generator and asked a learned model to make a local, comparative choice near each proposal.

## Day 4 — Develop and validate the final segmentation model

- [x] Tested fixed-weight fusion with temporal spreading and non-maximum suppression; rejected it because it did not reliably improve strict localization.
- [x] Built richer local before/after features: interaction ratios, local app-switch activity, timing gaps, PELT offset, and sequence-change signal.
- [x] Tested a standalone rich classifier: F1@5s improved to 0.485 but F1@10s fell to 0.505, so it was not adopted as the final boundary generator.
- [x] Built the final PELT-centered local reranker with `HistGradientBoostingClassifier`.
- [x] The reranker scored events in a plus/minus five-second neighborhood around each PELT anchor instead of independently labelling every event in a session. This preserved PELT coverage while allowing local timing evidence to move a boundary.
- [x] Used a session-level 51-development / 12-holdout split (seed 42).
- [x] Chose a session-level split to prevent events from the same work session appearing on both sides of evaluation.
- [x] Selected unrestricted reranking over a two-second cap: 0.466/0.593 vs 0.398/0.601 at F1@5s/F1@10s.
- [x] Locked the final result: PELT-only 0.358/0.589; final reranker 0.466/0.593.

**Decision record.** The final method materially improved strict five-second localization without materially sacrificing the ten-second result. I did not present the higher standalone F1@5s number as a win because its weaker F1@10s exposed a poorer overall boundary trade-off. This was the point at which the segmentation architecture was frozen; Dataset B analysis did not drive another round of model tuning.

## Day 5 — Apply the locked model to Dataset B

- [x] Retrained the locked reranker on all 63 Dataset A sessions after architecture selection.
- [x] Segmented all 15 Dataset B sessions into 339 raw technical fragments.
- [x] Reworked noisy context extraction to use application, title, browser host, and page route as separate features.
- [x] The earlier noisy-token representation could overemphasize incidental window text and create misleading similarity. Separating context sources made cluster features more interpretable and reduced application-title noise.
- [x] Used TF-IDF plus cosine-distance agglomerative clustering to generate recurring-work hypotheses.
- [x] Resolved the installed sklearn sparse-input issue by converting the small TF-IDF matrix to dense form.

**Boundary between algorithm and judgment.** Clustering was intentionally used as a candidate-discovery mechanism, not an automatic business-process labeler. The same computer activity can mean different work in different contexts; the later screenshot review was planned as a required validation step rather than a post-hoc presentation step.

## Day 6 — Recover business executions and select a candidate

- [x] Recognized that raw technical fragments are not necessarily business executions.
- [x] Added conservative execution merging: directly adjacent, same-cluster fragments only; compatible page context required; maximum ten-second gap.
- [x] Produced 264 inferred executions from 339 raw fragments and retained raw evidence for audit.
- [x] Kept the merging rule conservative: only directly adjacent fragments in the same cluster, with compatible page context and at most a ten-second gap, were combined. This avoided manufacturing long workflows from unrelated activity.
- [x] Applied the transparent five-execution screen, retaining 18 of 71 groups for review.
- [x] Rejected `process_001` despite high observed impact because screenshots showed mixed finance, purchasing, and contract work.
- [x] This was the most important prioritisation correction. Its high 31.5 observed minutes made it superficially attractive, but the cluster did not represent one automatable business workflow; an ROI claim based on it would be misleading.
- [x] Rejected the **earlier** `process_002` hypothesis because it consisted mainly of short navigation/click/application-switch fragments.
- [x] Manually validated the regenerated final `process_003` as HR new-hire onboarding verification: HR case review, required-item cross-checking, Word checklist use, and a complete/flag/hold decision point.

**Manual-validation method.** For each shortlisted candidate, I sampled four occurrences across the available sessions. The spot-check helper used documented screenshot references from events inside each interval and produced a small index with session, interval, application, and interaction information. I reviewed the actual visual sequences, not just a keyword list. One final `process_003` sample contained purchase-order activity before switching into onboarding; I recorded this as segmentation spillover and limited the proposed automation to the repeated onboarding review portion.

**Naming correction.** An earlier `process_002` selection was wrong. It described short navigation and application-switch fragments, not a complete workflow. To avoid silently changing history, the final documents call the target `process_003` only and explicitly describe the earlier `process_002` hypothesis as rejected.

## Day 7 — Build the final prototype and prepare submission artifacts

- [x] Built an initial lookup-to-Word prototype, then replaced its scope after deeper workflow validation.
- [x] The initial prototype followed an earlier lookup-to-document hypothesis. I did not preserve it as the final answer after validation showed the stronger opportunity was onboarding verification; changing scope was preferable to defending an unsupported first choice.
- [x] Built the final deterministic, review-first onboarding assistant for final `process_003`.
- [x] Implemented explicit `PASS`, `MISSING`, `REQUIRES REVIEW`, and `NOT APPLICABLE` item states.
- [x] Generated Word review checklists and a CSV audit log for three mock cases.
- [x] Verified the local prototype: one ready case, one missing-evidence case, and one conflicting-evidence case; all final completion/flag actions remain human-controlled.
- [x] Added requirements, portable Dataset A discovery, schema-based screenshot sampling, a final report, README, and this work log.
- [x] Preserved the caveat that Dataset B has no ground truth and test-environment durations are relative rather than production ROI claims.

**Why the prototype is bounded.** The evidence supports structured review preparation, not autonomous HR approval. The assistant normalizes case data through an adapter, runs explicit checks, creates a checklist and suggested note, and records an audit event. A reviewer still handles policy exceptions and completes or flags the portal case. This is a deliberately testable first release, not a claim to replace HR judgment.

**Submission preparation.** I added reproducibility instructions, pinned dependencies, output descriptions, a final report, and this log. I also added standard-library tests for complete, missing-evidence, conflicting-evidence, and not-applicable scenarios. The final repository includes selected screenshot samples as review evidence, rather than the excluded raw data directory.

## Final architecture and deliberate non-goals

- [x] Final segmentation: PELT anchors plus unrestricted supervised local reranking.
- [x] Final target name: `process_003` — HR new-hire onboarding verification. Earlier `process_002` interpretations are historical only and are not used as the final label.
- [x] Final implementation: deterministic Python rules, generated Word checklist, audit log, and human review.
- [ ] Production integration: requires authoritative HR policy, approved credentials, API or UI access, field mapping, and security review.
- [ ] Production ROI measurement: requires real workflow timings, reviewer feedback, exception rates, and correction rates.

## Generative AI use

- [x] Used generative AI as a coding and writing collaborator: to discuss alternative segmentation designs, draft and refine helper code, interpret experiment output, identify inconsistencies, and improve report structure.
- [x] Kept empirical claims tied to repository outputs, Dataset A holdout results, or manual screenshot review. Generative AI did not supply ground truth, inspect production systems, or make HR decisions.
- [x] Manually reviewed the selected Dataset B screenshot samples and retained uncertainty where the evidence showed mixed or spillover activity.

## Final evidence trail

- [x] Dataset A holdout evidence: PELT-only F1@5s/F1@10s of 0.358/0.589; PELT-centered reranker 0.466/0.593.
- [x] Dataset B discovery evidence: 15 sessions, 339 raw fragments, 264 conservatively inferred executions, 71 raw groups, and 18 groups meeting the five-execution review screen.
- [x] Target-selection evidence: four screenshot samples for each shortlisted candidate; `process_003` selected only after `process_001` and the earlier `process_002` were rejected.
- [x] Prototype evidence: three end-to-end mock cases, Word checklist outputs, CSV audit log, and four regression-test paths.
- [x] Evidence not claimed: production time savings, policy completeness, live-system integration reliability, or fully autonomous HR completion.
