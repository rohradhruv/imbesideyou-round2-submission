# Step 1 Segmentation Validation

## Evaluation design

Dataset A contains labelled process-boundary timestamps. I split its 63 sessions at the session level into 51 development sessions and 12 holdout sessions using a fixed seed (`42`). The holdout sessions were not used for architecture selection or parameter tuning.

The final method uses PELT (`pen=3`) to propose high-recall boundary anchors, then a `HistGradientBoostingClassifier` re-ranks events within plus or minus five seconds of each anchor using local interaction features. These include event-type mix, app-switch and clipboard activity, timing gaps, local activity density, and behaviour-change score.

## Held-out boundary localisation results

| Method | F1 within 5 seconds | F1 within 10 seconds |
|---|---:|---:|
| PELT-only baseline | 0.358 | 0.589 |
| PELT plus learned local reranker | 0.466 | 0.593 |

The reranker improves strict five-second localisation by 0.108 F1 while preserving comparable performance at the more forgiving ten-second tolerance. I therefore selected it for Dataset B exploratory segmentation.

## Interpretation and limits

- This measures timestamp proximity to Dataset A process-boundary ground truth, using greedy one-to-one matching; it does not validate Dataset B business labels.
- Dataset B has no ground truth. Clustering there proposes workflow hypotheses only; screenshot review was used before selecting an automation target.
- The result is adequate for exploratory workload discovery, not a claim of production-grade process-mining accuracy.
- Events were stitched across chunks and sorted by `timestamp_ms` before feature construction because raw file order was observed to be non-chronological.
- Dataset B durations are relative comparisons only because the test environment compresses waiting time.
