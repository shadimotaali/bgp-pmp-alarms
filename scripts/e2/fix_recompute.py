# ==============================================================================
# E2 - recompute the PMP where Step 0 was wrong, with two fixes
#
# Fix 1 - zero-window problem (fractional features, e.g. rare_ases_avg, edit_distance_avg):
#   matrixprofile computes window means with running sums; with fractional values tiny
#   rounding errors give all-zero windows a 1/std of about 1e15 instead of 0, and then
#   every window matches them at distance 0.
#   Fix: multiply by 1e6 and round to whole numbers before computing. Sums of whole numbers
#   are exact, so all-zero windows get exactly 0 (the library's 1.41 rule works again).
#   The z-normalised distance does not depend on the scale, so nothing else changes.
#
# Fix 2 - data gaps (missing data filled with 0 in Step 0):
#   a run of >= 60 missing seconds in the feature CSV is a gap in the data (in our 12 days
#   quiet runs are at most 27 s; the only gap is WannaCrypt 12 May 13:30, 299 s).
#   The gap stays 0 in the input (NaN cannot be used: one NaN spoils matrixprofile's running
#   sums for the whole rest of the day, every later window gets the maximum distance).
#   With whole numbers (fix 1) an all-zero gap window gets the library's fixed value and can
#   never be a perfect twin. Afterwards the MP of every window that touches the gap is set
#   to NaN (no value, instead of a fake mountain).
#
# Only the (feature, day) pairs that need a fix are recomputed:
#   fractional features on every day + every feature on days with a gap.
# Everything else is identical to pmp_sqrt_m.py (same series, same windows, same compute_pmp).
#
# Output: results/e2/<event>/<day>/matrices/<feature>.npz (start-aligned, same format)
# Then end-align them into the corrected set:
#   python scripts/correction_b/end_align.py --src results/e2 --dst results/corrected
#
# Run from the repository root:
#   nohup python -W ignore scripts/e2/fix_recompute.py --jobs 8 --threads 4 > results/e2_run.log 2>&1 &
# ==============================================================================

import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'step0'))
from pmp_sqrt_m import compute_pmp, COLUMNS_TO_ANALYZE, WINDOWS_TO_TEST

SCALE = 1e6        # fractional -> whole numbers
GAP_MIN = 60       # seconds; a missing run at least this long is a data gap

# (feature CSV, event folder, day folder) - same 12 days as run_all_days.sh
DAYS = [
    ('data/cnsm/slammer/slammer_anomaly_25jan_features_1s.csv',           'slammer',          'anomaly_25jan'),
    ('data/cnsm/slammer/slammer_baseline_18jan_features_1s.csv',          'slammer',          'baseline_18jan'),
    ('data/cnsm/codered/codered_anomaly_19jul_features_1s.csv',           'codered',          'anomaly_19jul'),
    ('data/cnsm/codered/codered_baseline_12jul_features_1s.csv',          'codered',          'baseline_12jul'),
    ('data/cnsm/moscow_blackout/moscow_blackout_25may_features_1s.csv',   'moscow_blackout',  'anomaly_25may'),
    ('data/cnsm/moscow_blackout/moscow_baseline_18may_features_1s.csv',   'moscow_blackout',  'baseline_18may'),
    ('data/cnsm/telekom_malaysia/telekom_malaysia_12jun_features_1s.csv', 'telekom_malaysia', 'anomaly_12jun'),
    ('data/cnsm/telekom_malaysia/telekom_malaysia_5jun_features_1s.csv',  'telekom_malaysia', 'baseline_5jun'),
    ('data/cnsm/nimda/nimda_anomaly_18sept_features_1s.csv',              'nimda',            'anomaly_18sep'),
    ('data/cnsm/nimda/nimda_baseline_11sept_features_1s.csv',             'nimda',            'baseline_11sep'),
    ('data/cnsm/wannacrypt/wannacrypt_anomaly_12may_features_1s.csv',     'wannacrypt',       'anomaly_12may'),
    ('data/cnsm/wannacrypt/wannacrypt_baseline_5may_features_1s.csv',     'wannacrypt',       'baseline_5may'),
]


def gap_seconds(df_index, full_index):
    """True for every second that belongs to a run of >= GAP_MIN missing seconds."""
    present = pd.Series(False, index=full_index)
    present[present.index.isin(df_index)] = True
    missing = ~present.values
    gap = np.zeros(len(missing), dtype=bool)
    start = None
    for i, miss in enumerate(np.append(missing, False)):
        if miss and start is None:
            start = i
        elif not miss and start is not None:
            if i - start >= GAP_MIN:
                gap[start:i] = True
            start = None
    return gap


def fix_feature(task):
    name, values, time, gap, out_path, threads = task
    x = values.astype(float)
    fractional = bool(np.any(x != np.round(x)))
    calc = np.round(x * SCALE) if fractional else x.copy()      # fix 1 (gap seconds stay 0)

    pmp = compute_pmp(calc, name, threads)

    if gap.any():                                                # fix 2 (output)
        n = len(x)
        cum = np.concatenate([[0], np.cumsum(gap)])
        for row, m in enumerate(WINDOWS_TO_TEST):
            touches_gap = (cum[m:] - cum[:n - m + 1]) > 0        # window [i, i+m-1] contains a gap second
            pmp[row, :n - m + 1][touches_gap] = np.nan

    series = x.copy()
    series[gap] = np.nan                                         # missing data shown as missing
    np.savez(out_path, pmp=pmp.astype(np.float32), windows=np.array(list(WINDOWS_TO_TEST)),
             time=time, series=series)
    fixes = (['fractional -> whole numbers'] if fractional else []) + (['gap windows -> NaN'] if gap.any() else [])
    return f'{out_path}: {", ".join(fixes)}'


def main():
    parser = argparse.ArgumentParser(description="E2: recompute the PMP with the zero-window and gap fixes")
    parser.add_argument('--out', default=os.path.join('results', 'e2'), help='output root (default results/e2)')
    parser.add_argument('--events', nargs='*', default=None, help='only these events (default: all)')
    parser.add_argument('--features', nargs='*', default=COLUMNS_TO_ANALYZE, help='only these features (default: all 27)')
    parser.add_argument('--jobs', type=int, default=1, help='features computed in parallel')
    parser.add_argument('--threads', type=int, default=1, help='CPU cores for each matrix profile')
    args = parser.parse_args()

    tasks = []
    for csv, event, day in DAYS:
        if args.events and event not in args.events:
            continue
        df = pd.read_csv(csv)
        df['window_start'] = pd.to_datetime(df['window_start'])
        df.set_index('window_start', inplace=True)
        out_dir = os.path.join(args.out, event, day, 'matrices')
        os.makedirs(out_dir, exist_ok=True)

        first = None
        for name in args.features:
            ts = df[name].resample('1s').sum().fillna(0)          # same series as pmp_sqrt_m.py
            if first is None:
                first = ts
                gap = gap_seconds(df.index, ts.index)
                print(f'{event}/{day}: {int(gap.sum())} gap seconds', flush=True)
            x = ts.values.astype(float)
            if np.nanmax(x) == 0:                                  # same rule as the original
                continue
            fractional = np.any(x != np.round(x))
            if fractional or gap.any():
                tasks.append((name, x, ts.index.values, gap,
                              os.path.join(out_dir, f'{name}.npz'), args.threads))

    print(f'{len(tasks)} matrices to recompute, {args.jobs} in parallel x {args.threads} cores', flush=True)
    with Pool(args.jobs) as pool:
        for i, msg in enumerate(pool.imap_unordered(fix_feature, tasks), 1):
            print(f'[{i}/{len(tasks)}] {msg}', flush=True)
    print(f'Finished. Results in {args.out}')


if __name__ == '__main__':
    main()
