# Work Log — I'mbesideyou AI Engineer Take-Home

## Day 1 — Sept 13, 2026

**Environment setup:**
- Installed and sanity-checked: pandas, ruptures (PELT), pm4py
- Verified PELT correctly detects a known synthetic boundary before touching real data
- Note: pm4py is AGPL v3 licensed (community version) — fine for this evaluation use, flagging for completeness

**Manual data exploration (Dataset A, sample session):**
- Manually traced one ground-truth task instance against raw events.jsonl
- Confirmed the abstract gt pattern is directly visible in raw signal: app_switch sequence + clipboard_change events + Ctrl+F/Ctrl+V shortcut bursts
- Naive hypothesis going in: app-switch + clipboard events would be the strongest boundary signal — confirmed on this instance, to be tested at scale on Day 2

**Data quality issue found:**
- events.jsonl is NOT stored in strict chronological order — verified 87 of 765 consecutive event pairs are out of timestamp order
- File appears ordered by capture arrival (sequence_number), not timestamp_ms — likely because screenshot (L1) capture lags behind click/keystroke (L2/L3) capture
- Implication: MUST explicitly sort by timestamp_ms before any idle-gap/time-based feature engineering, or PELT input will be corrupted
- Caught by manually inspecting the file, not from the schema docs

**Next up (Day 2):** build the feature extraction pipeline (with explicit timestamp sort) and run PELT on Dataset A.

## Day 2 — Sept 14, 2026

### Goal
Turn yesterday's manual observation (app-switch + clipboard events signal a task boundary) into working, automated segmentation code using PELT, and validate it against real ground truth.

### Feature engineering
- Built three numeric features per event: gap_since_prev_sec (time since last event), is_app_switch (0/1 flag), is_clipboard (0/1 flag)
- Fed these into ruptures' PELT algorithm (model='rbf') to detect boundaries automatically

### Environment issues hit and fixed (in order)
1. ModuleNotFoundError: No module named 'ruptures' — VS Code/Cursor was running a different Python installation than the one libraries were originally installed into (multiple Pythons present on the machine). Fixed by explicitly targeting the correct interpreter with python.exe -m pip install ...
2. ruptures failed to build ("Microsoft Visual C++ 14.0 required") — occurred when trying to install into Python 3.14; no pre-built package exists yet for that Python version this new, so pip tried compiling from source and needed a C++ compiler not present on Windows by default. Resolved by switching VS Code's selected interpreter to an older, working Python (3.13) instead of installing a full compiler toolchain.
3. UnicodeDecodeError (cp1252 codec) reading events.jsonl — Windows' default file-reading encoding can't handle the Japanese text present in the dataset. Fixed by explicitly opening all .jsonl/.json files with encoding='utf-8' — applied as a standing rule for the rest of the project, not just this one file.
4. FileNotFoundError for data/sample_events.jsonl — leftover dead code from an earlier draft of the script pointing at a path that no longer applied. Identified and marked for removal.
5. Duplicate output (each result line printing twice) — leftover duplicated code block in segment.py, not yet fully cleaned up — carrying into Day 3 as a to-do.

### Multi-chunk session stitching
- Built load_session_events() to find all chunk_* folders within a session folder, load and combine every chunk's events.jsonl, then sort the combined result by timestamp_ms
- Validated on real session ses_20260701-005920-yuvraj (2 chunks): correctly combined 3 + 2,638 = 2,641 events, exactly matching the sum from both chunks' manifests
- Key realization: a session's chunk files must be fully stitched before any analysis — using a single chunk in isolation (as done by accident on Day 1) produces misleadingly incomplete results when compared against ground truth, since ground truth spans the whole session

### Data-quality abnormality found
- This session's chunk 2 manifest has next_chunk_id: null (implying no further chunks) but also is_session_end: false (implying the session isn't actually complete) — a genuine internal contradiction in the provided metadata
- Decision: treating currently available chunks as complete for analysis purposes, explicitly flagging this metadata inconsistency as a known caveat rather than silently ignoring it

### Segmentation results
Session 1 (Siddhi, single 7-min chunk, tested Day 1-2):
- 18 real boundaries in-window, 14 PELT guesses, median distance 3.3 sec, 10/18 (56%) within 5 sec

Session 2 (yuvraj, full 2-chunk session, complete):
- 58 real boundaries, 53 PELT guesses, median distance 4.1 sec
- 30/58 (52%) within 5 sec, 38/58 (66%) within 10 sec

### Cross-session generalization finding (important)
- Accuracy is nearly identical across two independent sessions from different people/tasks (56% vs 52% within 5 sec) — suggests this simple 3-feature approach is not overfit to one example and generalizes reasonably, which directly supports the "will this transfer to Dataset B" requirement from the original problem statement

### Open items for Day 3
- Clean up duplicate print bug in segment.py
- Try tuning PELT's pen parameter to see if accuracy improves
- Test on 1-2 more sessions before considering the method validated
- Still need to run the rule-based heuristic baseline for the promised comparison

### Git hygiene issue found and fixed (Day 2)
- Accidentally committed the entire raw dataset (hundreds of files, ~10,000+ git objects) in early commits, discovered when a git push attempt hung uploading it
- Fixed by resetting git history and adding a .gitignore excluding data/ before recommitting
- Lesson: always set up .gitignore for large/raw data folders BEFORE the first commit, not after

### Runtime/scalability issue found (Day 2)
- Current per-event feature signal (one row per raw event, 2,641 rows for one session) made pen-tuning slow, and pen=1 was computationally impractical (multi-minute runtime)
- Root cause: deviated from the original plan of time-windowed features (bucketing activity per fixed window) into per-event rows, which doesn't scale to "huge" Dataset B
- Decision: redesign feature extraction to use fixed time-window bucketing (e.g., 5-sec windows) instead of per-event rows -- planned for Day 3, will both fix runtime and better match the "activity pattern" concept we're trying to detect

### Pen tuning results (session ses_20260701-005920-yuvraj, 58 real boundaries)
| pen | found | within 5 sec |
|---|---|---|
| 2 | 70 | 31/58 |
| 3 | 53 | 30/58 |
| 5 | 32 | 29/58 |
| 8-10 | 3 | 2/58 |
| 15-20 | 0 | 0/58 |

- Chose pen=3: near-identical hit-rate to pen=2 (30 vs 31) but boundary count (53) much closer to ground truth (58) than pen=2's (70) -- pen=2 achieves similar accuracy mainly by over-guessing, a weaker method despite the marginally higher raw score
- Sharp accuracy cliff between pen=5 and pen=8 -- useful range for this data is roughly 2-5

### Runtime/scalability issue found (Day 2)
- Current per-event feature signal (one row per raw event, 2,641 rows for one session) made pen-tuning slow, and pen=1 was computationally impractical (multi-minute runtime)
- Root cause: deviated from the original plan of time-windowed features (bucketing activity per fixed window) into per-event rows, which doesn't scale to "huge" Dataset B
- Decision: redesign feature extraction to use fixed time-window bucketing (e.g., 5-sec windows) instead of per-event rows -- planned for Day 3, will both fix runtime and better match the "activity pattern" concept we're trying to detect

### Pen tuning results (session ses_20260701-005920-yuvraj, 58 real boundaries)
| pen | found | within 5 sec |
|---|---|---|
| 2 | 70 | 31/58 |
| 3 | 53 | 30/58 |
| 5 | 32 | 29/58 |
| 8-10 | 3 | 2/58 |
| 15-20 | 0 | 0/58 |

- Chose pen=3: near-identical hit-rate to pen=2 (30 vs 31) but boundary count (53) much closer to ground truth (58) than pen=2's (70) -- pen=2 achieves similar accuracy mainly by over-guessing, a weaker method despite the marginally higher raw score
- Sharp accuracy cliff between pen=5 and pen=8 -- useful range for this data is roughly 2-5

### Runtime/scalability issue found (Day 2)
- Current per-event feature signal (one row per raw event, 2,641 rows for one session) made pen-tuning slow, and pen=1 was computationally impractical (multi-minute runtime)
- Root cause: deviated from the original plan of time-windowed features (bucketing activity per fixed window) into per-event rows, which doesn't scale to "huge" Dataset B
- Decision: redesign feature extraction to use fixed time-window bucketing (e.g., 5-sec windows) instead of per-event rows -- planned for Day 3, will both fix runtime and better match the "activity pattern" concept we're trying to detect

### Pen tuning results (session ses_20260701-005920-yuvraj, 58 real boundaries)
| pen | found | within 5 sec |
|---|---|---|
| 2 | 70 | 31/58 |
| 3 | 53 | 30/58 |
| 5 | 32 | 29/58 |
| 8-10 | 3 | 2/58 |
| 15-20 | 0 | 0/58 |

- Chose pen=3: near-identical hit-rate to pen=2 (30 vs 31) but boundary count (53) much closer to ground truth (58) than pen=2's (70) -- pen=2 achieves similar accuracy mainly by over-guessing, a weaker method despite the marginally higher raw score
- Sharp accuracy cliff between pen=5 and pen=8 -- useful range for this data is roughly 2-5
