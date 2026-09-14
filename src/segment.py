import json
import pandas as pd
import ruptures as rpt
from pathlib import Path

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

if __name__ == "__main__":
    df = load_session_events(r"C:\Users\Dhruv Rohra\imbesideyou-submission\data\dataset_a-20260912T094204Z-1-001\dataset_a\ses_20260701-005920-yuvraj")
    print(f"Total events after joining all chunks: {len(df)}")
    df = df.sort_values('timestamp_ms').reset_index(drop=True)
    df = build_features(df)
    boundaries = find_boundaries(df)
    print(f"Found {len(boundaries)} boundaries")













from datetime import datetime

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

if __name__ == "__main__":
    session_path = r"C:\Users\Dhruv Rohra\imbesideyou-submission\data\dataset_a-20260912T094204Z-1-001\dataset_a\ses_20260701-005920-yuvraj"

    df = load_session_events(session_path)
    print(f"Total events after joining all chunks: {len(df)}")

    df = build_features(df)
    breakpoints = find_boundaries(df)
    print(f"Found {len(breakpoints)} boundaries")

    gt_times = load_ground_truth_boundaries(session_path + r"\gt.jsonl")
    print(f"Real boundaries in ground truth: {len(gt_times)}")

    distances = compare_to_ground_truth(df, breakpoints, gt_times)
    import statistics
    print(f"Median distance to nearest guess: {statistics.median(distances):.1f} sec")
    print(f"Within 5 sec: {sum(1 for d in distances if d <= 5)}/{len(distances)}")
    print(f"Within 10 sec: {sum(1 for d in distances if d <= 10)}/{len(distances)}")