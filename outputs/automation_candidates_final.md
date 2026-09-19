# Step 2 Final Automation Candidate Analysis

Counts are inferred business executions after conservative merging of adjacent same-workflow fragments. Clustering proposes candidates; manual screenshot review establishes workflow meaning.

## Two-axis assessment

| Label | Executions | Raw fragments | Total min | Actors | Impact | Feasibility | Review outcome |
|---|---:|---:|---:|---:|---:|---:|---|
| process_001 | 15 | 16 | 31.5 | 4 | 1.00 | 0.70 | Reject -- mixed workflows, not a valid process group |
| process_002_fragment | 14 | 25 | 7.9 | 3 | 0.63 | 0.73 | Reject -- activity fragments, not a coherent execution |
| process_003 | 12 | 22 | 9.5 | 4 | 0.60 | 0.73 | Selected -- review-first automation candidate |
| process_005 | 13 | 14 | 7.4 | 3 | 0.58 | 0.68 | Defer -- workflow meaning not manually validated |
| process_004 | 11 | 11 | 11.0 | 4 | 0.57 | 0.69 | Phase 2 candidate -- validate controls before automation |
| process_006 | 10 | 12 | 2.8 | 4 | 0.43 | 0.75 | Defer -- workflow meaning not manually validated |
| process_008 | 8 | 8 | 10.3 | 4 | 0.41 | 0.65 | Defer -- workflow meaning not manually validated |
| process_009 | 9 | 13 | 5.1 | 3 | 0.35 | 0.74 | Defer -- workflow meaning not manually validated |
| process_007 | 9 | 15 | 3.7 | 3 | 0.34 | 0.82 | Defer -- workflow meaning not manually validated |
| process_011 | 11 | 18 | 3.5 | 1 | 0.33 | 0.73 | Defer -- workflow meaning not manually validated |
| process_013 | 6 | 6 | 11.8 | 2 | 0.23 | 0.68 | Defer -- workflow meaning not manually validated |
| process_014 | 8 | 9 | 5.4 | 1 | 0.21 | 0.80 | Defer -- workflow meaning not manually validated |
| process_010 | 6 | 10 | 3.3 | 3 | 0.18 | 0.89 | Defer -- workflow meaning not manually validated |
| process_012 | 5 | 5 | 3.2 | 4 | 0.18 | 0.70 | Defer -- workflow meaning not manually validated |
| process_020 | 7 | 14 | 6.3 | 1 | 0.17 | 0.74 | Defer -- workflow meaning not manually validated |
| process_019 | 5 | 5 | 8.7 | 2 | 0.14 | 0.70 | Defer -- workflow meaning not manually validated |
| process_027 | 5 | 5 | 0.7 | 1 | 0.00 | 0.96 | Defer -- workflow meaning not manually validated |
| process_026 | 5 | 5 | 0.4 | 1 | 0.00 | 0.98 | Defer -- workflow meaning not manually validated |

## Manual validation notes

- **process_001**: Rejected: mixes finance adjustment, purchase-order management, and contract-reference work.
- **process_002_fragment**: Rejected: fragmented payroll/navigation activity rather than a coherent business execution.
- **process_003**: Validated HR new-hire onboarding verification: portal case review, required-item cross-check, and Word checklist use before complete/flag action. One sampled segment begins in the purchase-order portal before moving into the onboarding workflow, so its boundary is treated as spillover rather than evidence that the two workflows are the same.
- **process_005**: Not manually validated; do not treat this cluster as a business process.
- **process_004**: HR payroll/compensation-change case handling with confirm/hold actions; stronger financial-control risk than onboarding.
- **process_006**: Not manually validated; do not treat this cluster as a business process.
- **process_008**: Not manually validated; do not treat this cluster as a business process.
- **process_009**: Not manually validated; do not treat this cluster as a business process.
- **process_007**: Not manually validated; do not treat this cluster as a business process.
- **process_011**: Not manually validated; do not treat this cluster as a business process.
- **process_013**: Not manually validated; do not treat this cluster as a business process.
- **process_014**: Not manually validated; do not treat this cluster as a business process.
- **process_010**: Not manually validated; do not treat this cluster as a business process.
- **process_012**: Not manually validated; do not treat this cluster as a business process.
- **process_020**: Not manually validated; do not treat this cluster as a business process.
- **process_019**: Not manually validated; do not treat this cluster as a business process.
- **process_027**: Not manually validated; do not treat this cluster as a business process.
- **process_026**: Not manually validated; do not treat this cluster as a business process.

## Final decision

**Chosen target:** process_003 -- HR new-hire onboarding verification

**Scope:** Given an HR onboarding case ID, retrieve employee and required-item data, apply deterministic completeness checks, and prepare a review checklist, exception summary, and suggested verification note. A human reviewer judges exceptions and completes or flags the portal case.

**Why this one:** Screenshot validation identified an onboarding-review subworkflow across multiple operators (4) within this 12-execution cluster. It represents 22 raw fragments and 9.5 observed minutes. One sampled boundary has purchase-order spillover, so the prototype targets the visually repeated onboarding portion only. That portion has repeatable checks, structured case data, and a clear human approval boundary.

**Implementation form:** Use a deterministic Python review assistant, not an LLM agent. The demonstrated work is structured retrieval, rule checks, and checklist/exception preparation; final judgment and portal submission remain human-controlled.

**Known limitation:** Logs do not provide production credentials, API contracts, authoritative rules, or approval policy. The prototype therefore uses local mock adapters and requires human review.

**Caveat:** Dataset B has no ground truth. Observed durations are used for relative prioritisation only because test-environment wait times are shortened.
