# Dataset B — Step 2 Automation Candidates

Sessions: 15

Raw segmentation fragments: 339

Inferred business executions: 264

Recognized process groups: 71

Priority combines workload impact (frequency, observed time, breadth) and repeatability/readiness (within-process similarity and application stability). It is a transparent heuristic, not ground truth.

| Rank | Label | Executions | Raw segments | Total min | Actors/Machines | Consistency | Readiness | Priority |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | process_001 | 15 | 16 | 31.5 | 4 | 0.88 | 0.69 | 69.3 |
| 2 | process_003 | 12 | 22 | 9.5 | 4 | 0.89 | 0.72 | 49.2 |
| 3 | process_002_fragment | 14 | 25 | 7.9 | 3 | 0.86 | 0.73 | 48.9 |
| 4 | process_004 | 11 | 11 | 11.0 | 4 | 0.86 | 0.69 | 45.4 |
| 5 | process_005 | 13 | 14 | 7.4 | 3 | 0.89 | 0.68 | 42.7 |
| 6 | process_006 | 10 | 12 | 2.8 | 4 | 0.90 | 0.75 | 40.9 |
| 7 | process_007 | 9 | 15 | 3.7 | 3 | 0.89 | 0.81 | 36.8 |
| 8 | process_008 | 8 | 8 | 10.3 | 4 | 0.85 | 0.65 | 35.5 |
| 9 | process_009 | 9 | 13 | 5.1 | 3 | 0.89 | 0.74 | 34.4 |
| 10 | process_010 | 6 | 10 | 3.3 | 3 | 0.92 | 0.89 | 30.6 |
| 11 | process_011 | 11 | 18 | 3.5 | 1 | 0.89 | 0.73 | 28.4 |
| 12 | process_012 | 5 | 5 | 3.2 | 4 | 0.87 | 0.69 | 25.7 |
| 13 | process_013 | 6 | 6 | 11.8 | 2 | 0.90 | 0.67 | 24.0 |
| 14 | process_014 | 8 | 9 | 5.4 | 1 | 0.90 | 0.79 | 23.8 |
| 15 | process_015 | 4 | 5 | 0.6 | 3 | 0.93 | 0.95 | 23.4 |

## Caveats

- Dataset B has no ground truth, so process groups are inferred from recurring event/application signatures.
- The session-name suffix is treated as an operator/machine identifier, not guaranteed human identity.
- Test-environment waiting times are shortened; compare processes relatively rather than treating observed duration as production duration.
