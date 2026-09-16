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

### Approach 1 — Practice attempt: PELT baseline

**Goal:** turn Day 1's manual observation (app-switch + clipboard events signal a task boundary) into working, automated segmentation code using PELT, and validate it against real ground truth.

**Feature engineering:**
- Built three numeric features per event: gap_since_prev_sec (time since last event), is_app_switch (0/1 flag), is_clipboard (0/1 flag)
- Fed these into ruptures' PELT algorithm (model='rbf') to detect boundaries automatically

**Environment issues hit and fixed (in order):**
1. ModuleNotFoundError: No module named 'ruptures' — VS Code/Cursor was running a different Python installation than the one libraries were originally installed into (multiple Pythons present on the machine). Fixed by explicitly targeting the correct interpreter with python.exe -m pip install ...
2. ruptures failed to build ("Microsoft Visual C++ 14.0 required") — occurred when trying to install into Python 3.14; no pre-built package exists yet for that Python version this new, so pip tried compiling from source and needed a C++ compiler not present on Windows by default. Resolved by switching VS Code's selected interpreter to an older, working Python (3.13) instead of installing a full compiler toolchain.
3. UnicodeDecodeError (cp1252 codec) reading events.jsonl — Windows' default file-reading encoding can't handle the Japanese text present in the dataset. Fixed by explicitly opening all .jsonl/.json files with encoding='utf-8' — applied as a standing rule for the rest of the project, not just this one file.
4. FileNotFoundError for data/sample_events.jsonl — leftover dead code from an earlier draft of the script pointing at a path that no longer applied. Removed.
5. Duplicate output (each result line printing twice) — root cause: two separate if __name__ == "__main__": blocks in segment.py. Fixed by merging into one block and consolidating all imports to the top of the file.

**Multi-chunk session stitching:**
- Built load_session_events() to find all chunk_* folders within a session folder, load and combine every chunk's events.jsonl, then sort the combined result by timestamp_ms
- Validated on real session ses_20260701-005920-yuvraj (2 chunks): correctly combined 3 + 2,638 = 2,641 events, exactly matching the sum from both chunks' manifests
- Key realization: a session's chunk files must be fully stitched before any analysis — using a single chunk in isolation (as done by accident on Day 1) produces misleadingly incomplete results when compared against ground truth, since ground truth spans the whole session

**Data-quality abnormality found:**
- This session's chunk 2 manifest has next_chunk_id: null (implying no further chunks) but also is_session_end: false (implying the session isn't actually complete) — a genuine internal contradiction in the provided metadata
- Decision: treating currently available chunks as complete for analysis purposes, explicitly flagging this metadata inconsistency as a known caveat rather than silently ignoring it

**Segmentation results:**
- Session 1 (Siddhi, single 7-min chunk, tested Day 1-2): 18 real boundaries in-window, 14 PELT guesses, median distance 3.3 sec, 10/18 (56%) within 5 sec
- Session 2 (yuvraj, full 2-chunk session, complete): 58 real boundaries, 53 PELT guesses, median distance 4.1 sec, 30/58 (52%) within 5 sec, 38/58 (66%) within 10 sec

**Cross-session finding:** performance was similar across two independent sessions (56% vs 52% within 5 sec), suggesting the observed signal is not specific to a single session. Broader cross-session validation is still required before claiming full generalization.

**Git hygiene issue found and fixed:**
- Accidentally committed the entire raw dataset (hundreds of files, ~10,000+ git objects) in early commits, discovered when a git push attempt hung uploading it
- Fixed by resetting git history and adding a .gitignore excluding data/ before recommitting
- Lesson: always set up .gitignore for large/raw data folders BEFORE the first commit, not after

**Runtime/scalability issue found:**
- Current per-event feature signal (one row per raw event, 2,641 rows for one session) made pen-tuning slow, and pen=1 was computationally impractical (multi-minute runtime)
- Root cause: deviated from the original plan of time-windowed features (bucketing activity per fixed window) into per-event rows, which doesn't scale to "huge" Dataset B
- Decision: redesign feature extraction to use fixed time-window bucketing instead of per-event rows in the final approach (see Approach 3 below)

**Pen tuning results (session ses_20260701-005920-yuvraj, 58 real boundaries):**

| pen | found | within 5 sec |
|---|---|---|
| 2 | 70 | 31/58 |
| 3 | 53 | 30/58 |
| 5 | 32 | 29/58 |
| 8-10 | 3 | 2/58 |
| 15-20 | 0 | 0/58 |

- Chose pen=3: near-identical hit-rate to pen=2 (30 vs 31) but boundary count (53) much closer to ground truth (58) than pen=2's (70) — pen=2 achieves similar accuracy mainly by over-guessing, a weaker method despite the marginally higher raw score
- Sharp accuracy cliff between pen=5 and pen=8 — useful range for this data is roughly 2-5

**Status:** KEEP this pipeline as one component (the "PELT" signal) inside the final locked approach — see Approach 3. Not pursuing further PELT-only tuning beyond this.

### Approach 2 — Supervised boundary detection (considered, not chosen)

**Idea:** use Dataset A's ground truth to train a model that directly learns what a true process boundary looks like, rather than relying on an unsupervised change-point detector.

**Pipeline considered:**
richer temporal + application/context + interaction + sequence features -> candidate generation -> trained boundary classifier (e.g. XGBoost/LightGBM) -> post-processing -> final segments.

**Why it's attractive:** directly learns the difference between true and false boundaries from labelled data; potentially more accurate and more adaptable than pure PELT, and fully exploits the fact that Dataset A has ground truth at all.

**Why NOT chosen as the primary approach:** building this properly (15-30 engineered features, candidate generation, model training, session-level train/validation split, post-processing) is realistically a multi-day effort on its own. With two more full stages (Step 2 process/ROI analysis, Step 3 automation prototype) still ahead in the 7-day window, committing to this risks consuming time the rest of the submission needs. The assignment explicitly evaluates judgment and ROI, not technical sophistication for its own sake.

**Decision:** do not build the full supervised pipeline. Borrow its core insight (combine multiple signals, learn relative weights) in a lightweight, time-boxed form instead — see Approach 3.

### Approach 3 — LOCKED final segmentation approach

**Goal:** capture the main benefit of Approach 2 (combining multiple signals, weighted by evidence) without turning Step 1 into a multi-day ML project.

**Pipeline:**

RAW SESSION
|
Stitch all chunks + sort by timestamp
|
Small feature set (time-windowed, not per-event)
|
PELT change | Big-gap detector | App/context change | Sequence/behavior change
|
UNION OF CANDIDATES
|
DEDUPE / MERGE NEARBY
|
OPTIONAL lightweight Logistic Regression (only if it clearly improves GT)
|
Simple post-processing
|
FINAL SEGMENTS
|
Dataset B / Step 2


**Four candidate signals:**
- PELT: detects broad behavioral/statistical change (the Approach 1 baseline, now one input among several).
- Big gap: detects strong inactivity/pause.
- App/context change: detects change in working environment.
- Sequence/behavior change: compares short pre/post action patterns; catches task changes even when the same app remains open.

**Candidate union:** each signal only proposes a possible boundary; nearby proposals from different signals are merged into one candidate before final selection.

**Optional Logistic Regression:** a lightweight final scorer using the candidate features. Hard time-boxed experiment (half a day maximum); keep only if it clearly beats the simpler hybrid on held-out Dataset A sessions, otherwise drop it without further tuning.

**Post-processing:** remove/merge noisy nearby boundaries and implausibly tiny fragments using thresholds validated on Dataset A.

**Non-goals:** no large deep-learning model, no screenshot/vision pipeline unless later needed for an ambiguous case, no per-event feature signal (replaced by time-windowed bucketing to fix the Day 2 runtime issue).

**LOCK:** implement this approach, validate quickly on Dataset A, generate segments.jsonl for Dataset B, then move immediately to Step 2.

### Decision principle

Optimize for overall 7-day submission ROI, not maximum Step-1 sophistication. Approach 1's work is not discarded — it remains the documented first practical attempt and one live component (the PELT signal) inside the final locked pipeline. Approach 3 is an evidence-driven refinement of Approach 1, not a restart.

### Carried forward to Day 3
- Test the locked pipeline (Approach 3) on 1-2 more Dataset A sessions before considering it validated
- Implement time-windowed feature bucketing (replacing per-event rows) as part of the new pipeline
- Build the big-gap, app/context-change, and sequence-change candidate generators
