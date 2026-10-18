# ==============================================================================
# Correction B - end-alignment of the saved PMP matrices (no recomputation)
#
# The original code stores the MP value of a window at the window's FIRST second
# (start-alignment): the value at 05:30:00 for m = 300 describes 05:30:00-05:34:59,
# i.e. it already "sees" 5 minutes into the future. A live detector cannot do that.
#
# End-alignment stores the same value at the window's LAST second instead:
#   start-aligned: value of window [i, i+m-1] at position i
#   end-aligned  : value of window [i, i+m-1] at position i+m-1
# So row m is shifted right by m-1 seconds. The first m-1 seconds of each row
# become NaN (no complete window ends there yet); the NaN padding at the end disappears.
# The values themselves do not change, only their position in time.
#
# Input : results/step0/<event>/<day>/matrices/<feature>.npz   (from pmp_sqrt_m.py)
# Output: results/corrected/<event>/<day>/matrices/<feature>.npz (same format)
#         so compare_days.py / event_overview.py / feature_2d_3d.py can read them
#
# Run from the repository root:
#   python scripts/correction_b/end_align.py
# ==============================================================================

import argparse
import glob
import os

import numpy as np


def end_align(pmp, windows):
    """Shift row m right by m-1 seconds (start-aligned -> end-aligned)."""
    n = pmp.shape[1]
    aligned = np.full(pmp.shape, np.nan, dtype=pmp.dtype)
    for row, m in enumerate(windows):
        valid = n - m + 1                           # number of complete windows of length m
        aligned[row, m - 1:] = pmp[row, :valid]
    return aligned


def main():
    parser = argparse.ArgumentParser(description="End-align the saved PMP matrices")
    parser.add_argument('--src', default=os.path.join('results', 'step0'), help='input root (default results/step0)')
    parser.add_argument('--dst', default=os.path.join('results', 'corrected'), help='output root (default results/corrected)')
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.src, '*', '*', 'matrices', '*.npz')))
    print(f'{len(files)} matrices found under {args.src}', flush=True)
    for i, path in enumerate(files, 1):
        d = np.load(path)
        out_path = os.path.join(args.dst, os.path.relpath(path, args.src))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        np.savez(out_path,
                 pmp=end_align(d['pmp'], d['windows']),
                 windows=d['windows'], time=d['time'], series=d['series'])
        if i % 25 == 0 or i == len(files):
            print(f'[{i}/{len(files)}] {out_path}', flush=True)
    print(f'Finished. Results in {args.dst}')


if __name__ == '__main__':
    main()
