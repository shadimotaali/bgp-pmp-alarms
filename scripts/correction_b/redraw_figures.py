# ==============================================================================
# Redraw the per-feature figures of pmp_sqrt_m.py from saved matrices (no recomputation)
#
# Same three figures and the same drawing functions as Step 0:
#   original/<feature>.png     PMP as in the CNSM paper
#   normalised/<feature>.png   PMP / sqrt(m)
#   3d/<feature>.png + .html   3D of PMP / sqrt(m), per-minute max
# Used for the corrected matrices (E1 end-alignment + E2 fixes) in results/corrected,
# so they can be compared with results/step0 side by side.
# The date label in the titles says which version it is (e.g. "25 Jan 2003 - corrected").
#
# Note: end-aligned rows start with m-1 empty seconds, and the WannaCrypt 12 May gap is
# empty, so the 3D (which keeps only complete minutes) skips those minutes.
#
# Run from the repository root, e.g.:
#   python scripts/correction_b/redraw_figures.py --day results/corrected/slammer/anomaly_25jan --date "25 Jan 2003 - corrected" --jobs 8
# ==============================================================================

import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'step0'))
from pmp_sqrt_m import plot_2d, plot_3d, normalise_sqrt_m


def redraw(task):
    npz_path, date_label, day_dir = task
    name = os.path.basename(npz_path)[:-4]
    d = np.load(npz_path)
    ts_data = pd.Series(d['series'], index=pd.to_datetime(d['time']))
    pmp = d['pmp'].astype(float)

    plot_2d(ts_data, pmp, name, date_label, 'Euclidean Distance',
            os.path.join(day_dir, 'original', f'{name}.png'))
    pmp_norm = normalise_sqrt_m(pmp)
    plot_2d(ts_data, pmp_norm, name, date_label, 'Euclidean Distance / sqrt(m)',
            os.path.join(day_dir, 'normalised', f'{name}.png'))
    plot_3d(ts_data, pmp_norm, name, date_label,
            os.path.join(day_dir, '3d', f'{name}.png'),
            os.path.join(day_dir, '3d', f'{name}.html'))
    return f'{name}: done'


def main():
    parser = argparse.ArgumentParser(description="Redraw original / normalised / 3D figures from saved matrices")
    parser.add_argument('--day', required=True, help='day folder, e.g. results/corrected/slammer/anomaly_25jan')
    parser.add_argument('--date', required=True, help='date shown in the titles, e.g. "25 Jan 2003 - corrected"')
    parser.add_argument('--jobs', type=int, default=1, help='features drawn in parallel (default 1)')
    args = parser.parse_args()

    for sub in ('original', 'normalised', '3d'):
        os.makedirs(os.path.join(args.day, sub), exist_ok=True)
    matrices = os.path.join(args.day, 'matrices')
    tasks = [(os.path.join(matrices, f), args.date, args.day)
             for f in sorted(os.listdir(matrices)) if f.endswith('.npz')]

    print(f'{len(tasks)} features from {matrices}, {args.jobs} in parallel', flush=True)
    with Pool(args.jobs) as pool:
        for i, msg in enumerate(pool.imap_unordered(redraw, tasks), 1):
            print(f'[{i}/{len(tasks)}] {msg}', flush=True)
    print(f'Finished. Results in {args.day}')


if __name__ == '__main__':
    main()
