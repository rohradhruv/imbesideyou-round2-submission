# Work Log — I'mbesideyou AI Engineer Take Home

This log records the actual decision path. Completed boxes indicate work performed; rejected approaches are retained because they informed the final design.

## Day 1 — Understand the data and the business question

- [x] Read the brief and schema; identified the task as process recovery and automation discovery, not just event classification.
- [x] Manually traced Dataset A work against raw events and identified app switches, clipboard activity, shortcuts, and local behavior changes as possible signals.
- [x] Confirmed that a chunk is recorder storage, not a business-process boundary.
- [x] Recorded UTF-8 as mandatory because Japanese text fails under Windows' default cp1252 encoding.

## Day 2 — Repair the event timeline and build a baseline

- [x] Found raw JSONL order was not safe for temporal analysis: 87 of 765 adjacent pairs were out of timestamp order in one inspected sample.
- [x] Implemented full-session chunk stitching and `timestamp_ms` sorting before feature creation.
- [x] Recorded one inconsistent chunk manifest (`next_chunk_id: null` with `is_session_end: false`) as a limitation.
- [x] Built a PELT baseline using event gap, app-switch, and clipboard features.
- [x] Selected `pen=3` over `pen=2`: similar hit rate with fewer unnecessary boundaries.

## Day 3 — Test alternatives instead of assuming PELT is enough

- [x] Considered a full supervised boundary pipeline; rejected it initially because it risked consuming the seven-day budget needed for process analysis and a working prototype.
- [x] Tested candidate union from PELT, idle-gap, app/context, and sequence-change signals.
- [x] Observed high candidate recall but poor precision from binary union.
- [x] Tested two-signal voting; rejected it because valid signals were often offset by seconds and recall fell.
- [x] Tested candidate-level logistic regression; rejected it because it underperformed PELT after correcting the candidate formulation.

## Day 4 — Develop and validate the final segmentation model

- [x] Tested fixed-weight fusion with temporal spreading and non-maximum suppression; rejected it because it did not reliably improve strict localization.
- [x] Built richer local before/after features: interaction ratios, local app-switch activity, timing gaps, PELT offset, and sequence-change signal.
- [x] Tested a standalone rich classifier: F1@5s improved to 0.485 but F1@10s fell to 0.505, so it was not adopted as the final boundary generator.
- [x] Built the final PELT-centered local reranker with `HistGradientBoostingClassifier`.
- [x] Used a session-level 51-development / 12-holdout split (seed 42).
- [x] Selected unrestricted reranking over a two-second cap: 0.466/0.593 vs 0.398/0.601 at F1@5s/F1@10s.
- [x] Locked the final result: PELT-only 0.358/0.589; final reranker 0.466/0.593.

## Day 5 — Apply the locked model to Dataset B

- [x] Retrained the locked reranker on all 63 Dataset A sessions after architecture selection.
- [x] Segmented all 15 Dataset B sessions into 339 raw technical fragments.
- [x] Reworked noisy context extraction to use application, title, browser host, and page route as separate features.
- [x] Used TF-IDF plus cosine-distance agglomerative clustering to generate recurring-work hypotheses.
- [x] Resolved the installed sklearn sparse-input issue by converting the small TF-IDF matrix to dense form.

## Day 6 — Recover business executions and select a candidate

- [x] Recognized that raw technical fragments are not necessarily business executions.
- [x] Added conservative execution merging: directly adjacent, same-cluster fragments only; compatible page context required; maximum ten-second gap.
- [x] Produced 264 inferred executions from 339 raw fragments and retained raw evidence for audit.
- [x] Applied the transparent five-execution screen, retaining 18 of 71 groups for review.
- [x] Rejected `process_001` despite high observed impact because screenshots showed mixed finance, purchasing, and contract work.
- [x] Rejected the **earlier** `process_002` hypothesis because it consisted mainly of short navigation/click/application-switch fragments.
- [x] Manually validated the regenerated final `process_003` as HR new-hire onboarding verification: HR case review, required-item cross-checking, Word checklist use, and a complete/flag/hold decision point.

## Day 7 — Build the final prototype and prepare submission artifacts

- [x] Built an initial lookup-to-Word prototype, then replaced its scope after deeper workflow validation.
- [x] Built the final deterministic, review-first onboarding assistant for final `process_003`.
- [x] Implemented explicit `PASS`, `MISSING`, `REQUIRES REVIEW`, and `NOT APPLICABLE` item states.
- [x] Generated Word review checklists and a CSV audit log for three mock cases.
- [x] Verified the local prototype: one ready case, one missing-evidence case, and one conflicting-evidence case; all final completion/flag actions remain human-controlled.
- [x] Added requirements, portable Dataset A discovery, schema-based screenshot sampling, a final report, README, and this work log.
- [x] Preserved the caveat that Dataset B has no ground truth and test-environment durations are relative rather than production ROI claims.

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
