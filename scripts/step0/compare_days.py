# ==============================================================================
# Step 0 - compare the anomaly day with its baseline day, for every feature
#
# Reads the saved PMP matrices (.npz) written by pmp_sqrt_m.py; nothing is recomputed.
#
# For each feature:
#   1. divide the PMP by sqrt(m) (MADRID suggestion 1)
#   2. "height" of each second = median over the window lengths m >= 50
#      (rows below m = 50 are left out: they are dominated by the sparse-data
#       effects of correction A, not by BGP behaviour)
#   3. average the height over 30-minute blocks (48 blocks per day)
#   4. the baseline day gives the normal range [lowest block, highest block]
#   5. an anomaly-day block is:  VALLEY  if below the baseline range
#                                MOUNTAIN if above the baseline range
#
# Output: one table (CSV) per event, one row per feature, plus the block values.
#
# Run from the repository root, e.g.:
#   python scripts/step0/compare_days.py --event slammer --anomaly anomaly_25jan --baseline baseline_18jan
# ==============================================================================

import argparse
import os
import warnings

import numpy as np
import pandas as pd

MIN_WINDOW = 50      # rows with m >= 50 are used for the height
BLOCK = '30min'      # time block for the comparison


def block_heights(npz_path, block=BLOCK, time_format='%H:%M'):
    """Block heights (default 30 min) of the sqrt(m)-normalised PMP (index = block start time)."""
    d = np.load(npz_path)
    windows = d['windows']
    norm = d['pmp'] / np.sqrt(windows)[:, None]
    rows = windows >= MIN_WINDOW
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        height = np.nanmedian(norm[rows], axis=0)
    t = pd.to_datetime(d['time'])
    s = pd.Series(height, index=t).resample(block).mean()
    # some files run a few minutes into the next day (e.g. 00:06 -> 00:06):
    # keep only the blocks of the day itself, otherwise "00:00" would appear twice
    s = s[s.index.normalize() == s.index[0].normalize()]
    s.index = s.index.strftime(time_format)   # keep only the time of day, so both days line up
    return s


def longest_run(flags, labels):
    """Longest stretch of consecutive True flags -> 'start–end' text and its length in blocks."""
    best, start, best_start = 0, None, None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        if not f and start is not None:
            if i - start > best:
                best, best_start = i - start, start
            start = None
    if best == 0:
        return '', 0
    end_label = labels[best_start + best] if best_start + best < len(labels) else '24:00'
    return f'{labels[best_start]}–{end_label}', best


def main():
    parser = argparse.ArgumentParser(description="Compare anomaly and baseline day, all features")
    parser.add_argument('--root', default=os.path.join('results', 'step0'),
                        help='results root (default results/step0; results/corrected for end-aligned)')
    parser.add_argument('--event', required=True, help='folder name under the root, e.g. slammer')
    parser.add_argument('--anomaly', required=True, help='anomaly day folder, e.g. anomaly_25jan')
    parser.add_argument('--baseline', required=True, help='baseline day folder, e.g. baseline_18jan')
    args = parser.parse_args()

    base_dir = os.path.join(args.root, args.event)
    a_dir = os.path.join(base_dir, args.anomaly, 'matrices')
    b_dir = os.path.join(base_dir, args.baseline, 'matrices')
    features = sorted(set(os.listdir(a_dir)) | set(os.listdir(b_dir)))

    rows, blocks = [], {}
    for f in features:
        name = f[:-4]
        a_path, b_path = os.path.join(a_dir, f), os.path.join(b_dir, f)
        if not (os.path.exists(a_path) and os.path.exists(b_path)):
            rows.append({'feature': name, 'note': 'all zeros on one of the two days'})
            continue
        a, b = block_heights(a_path), block_heights(b_path)
        a, b = a.align(b, join='outer')
        lo, hi = np.nanmin(b.values), np.nanmax(b.values)
        valley, mountain = a < lo, a > hi
        labels = list(a.index)
        v_run, v_len = longest_run(valley.values, labels)
        m_run, m_len = longest_run(mountain.values, labels)
        rows.append({
            'feature': name,
            'baseline_median': round(np.nanmedian(b.values), 2),
            'baseline_range': f'{lo:.2f}–{hi:.2f}',
            'anomaly_min': round(np.nanmin(a.values), 2),
            'anomaly_max': round(np.nanmax(a.values), 2),
            'valley_blocks': int(valley.sum()),
            'longest_valley': v_run,
            'mountain_blocks': int(mountain.sum()),
            'longest_mountain': m_run,
            'note': '',
        })
        blocks[f'{name}_anomaly'] = a.round(2)
        blocks[f'{name}_baseline'] = b.round(2)

    table = pd.DataFrame(rows)
    out_table = os.path.join(base_dir, 'compare_features.csv')
    out_blocks = os.path.join(base_dir, 'compare_blocks.csv')
    table.to_csv(out_table, index=False)
    pd.DataFrame(blocks).to_csv(out_blocks)
    with pd.option_context('display.width', 250, 'display.max_columns', 20):
        print(table.to_string(index=False))
    print(f'\nwritten: {out_table}\n         {out_blocks}')


if __name__ == '__main__':
    main()
