import json
import pandas as pd
import ruptures as rpt
import statistics
from pathlib import Path
from datetime import datetime

def load_session_events(session_folder):
    """
    Loads and combines ALL chunks for one session, sorted by time.
    session_folder should contain one or more chunk_* subfolders,
    each with its own events.jsonl.
    """
    all_events = []
    chunk_folders = sorted(Path(session_folder).glob("chunk_*"))
    for chunk_dir in chunk_folders:
        events_file = chunk_dir / "events.jsonl"
        if events_file.exists():
            with open(events_file, encoding='utf-8') as f:
                for line in f:
                    all_events.append(json.loads(line))
    df = pd.DataFrame(all_events)
    df = df.sort_values('timestamp_ms').reset_index(drop=True)
    return df

def build_features(df):
    df['gap_since_prev_sec'] = df['timestamp_ms'].diff().fillna(0) / 1000
    df['is_app_switch'] = (df['event_type'] == 'app_switch').astype(int)
    df['is_clipboard'] = (df['event_type'] == 'clipboard_change').astype(int)
    return df

def find_boundaries(df, pen=3):
    signal = df[['gap_since_prev_sec', 'is_app_switch', 'is_clipboard']].values
    algo = rpt.Pelt(model='rbf').fit(signal)
    breakpoints = algo.predict(pen=pen)
    return breakpoints

def load_ground_truth_boundaries(gt_file):
    """Reads gt.jsonl and pulls out just the real task-boundary timestamps."""
    with open(gt_file, encoding='utf-8') as f:
        gt = [json.loads(line) for line in f]
    boundary_events = [e for e in gt if e.get('event') in ('process_started', 'process_switched_out')]
    times = [datetime.fromisoformat(e['ts_utc']) for e in boundary_events]
    return sorted(times)

def compare_to_ground_truth(df, breakpoints, gt_times):
    """For each real boundary, find how close (in seconds) the nearest PELT guess is."""
    pelt_times = [datetime.fromisoformat(df.iloc[bp]['timestamp_iso'].replace('Z', '+00:00'))
                  for bp in breakpoints if bp < len(df)]
    distances = []
    for gt_t in gt_times:
        closest = min(abs((gt_t - p).total_seconds()) for p in pelt_times)
        distances.append(closest)
    return distances

def tune_pen(df, gt_times, pen_values):
    """Tries several pen values, returns accuracy for each so we can compare."""
    results = []
    for pen in pen_values:
        breakpoints = find_boundaries(df, pen=pen)
        distances = compare_to_ground_truth(df, breakpoints, gt_times)
        median_dist = statistics.median(distances)
        within_5 = sum(1 for d in distances if d <= 5)
        results.append({
            'pen': pen,
            'num_boundaries_found': len(breakpoints),
            'median_distance_sec': round(median_dist, 1),
            'within_5_sec': f"{within_5}/{len(distances)}"
        })
    return results

def tune_pen(df, gt_times, pen_values):
    results = []
    for pen in pen_values:
        print(f"Testing pen={pen}...")
        breakpoints = find_boundaries(df, pen=pen)
        distances = compare_to_ground_truth(df, breakpoints, gt_times)

        if not distances:
            results.append({
                'pen': pen,
                'num_boundaries_found': len(breakpoints) - 1,  # subtract the automatic end-point
                'median_distance_sec': 'N/A (no boundaries found)',
                'within_5_sec': 'N/A'
            })
            continue

        median_dist = statistics.median(distances)
        within_5 = sum(1 for d in distances if d <= 5)
        results.append({
            'pen': pen,
            'num_boundaries_found': len(breakpoints),
            'median_distance_sec': round(median_dist, 1),
            'within_5_sec': f"{within_5}/{len(distances)}"
        })
    return results

def compare_to_ground_truth(df, breakpoints, gt_times):
    """For each real boundary, find how close (in seconds) the nearest PELT guess is."""
    pelt_times = [datetime.fromisoformat(df.iloc[bp]['timestamp_iso'].replace('Z', '+00:00'))
                  for bp in breakpoints if bp < len(df)]

    if not pelt_times:
        # No boundaries found at all — return an empty list rather than crashing
        return []

    distances = []
    for gt_t in gt_times:
        closest = min(abs((gt_t - p).total_seconds()) for p in pelt_times)
        distances.append(closest)

    return distances

def build_windowed_features(df, window_seconds=5):
    """
    Instead of one row per raw event, bucket events into fixed time
    windows and count activity per window. Shrinks a 2,641-event
    session down to maybe 300 rows -- much faster for PELT, and
    arguably a more meaningful signal (activity RATE, not single clicks).
    """
    df['time_bucket'] = (df['timestamp_ms'] // (window_seconds * 1000))

    windowed = df.groupby('time_bucket').agg(
        event_count=('event_type', 'count'),
        app_switch_count=('event_type', lambda x: (x == 'app_switch').sum()),
        clipboard_count=('event_type', lambda x: (x == 'clipboard_change').sum()),
        first_timestamp_iso=('timestamp_iso', 'first')
    ).reset_index()

    return windowed


if __name__ == "__main__":
    session_path = r"C:\Users\Dhruv Rohra\imbesideyou-submission\data\dataset_a-20260912T094204Z-1-001\dataset_a\ses_20260701-005920-yuvraj"

    df = load_session_events(session_path)
    print(f"Total events after joining all chunks: {len(df)}")

    df = build_features(df)
    gt_times = load_ground_truth_boundaries(session_path + r"\gt.jsonl")
    print(f"Real boundaries in ground truth: {len(gt_times)}")

    pen_values_to_try = [2, 3, 5, 8, 10, 15,20]
    tuning_results = tune_pen(df, gt_times, pen_values_to_try)

    print("\n--- Pen tuning results ---")
    for r in tuning_results:
        print(r) 
