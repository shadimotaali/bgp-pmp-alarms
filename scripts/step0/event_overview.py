# ==============================================================================
# Step 0 - event overview: all 27 features of one event in one picture
#
# Reads the saved PMP matrices (.npz) written by pmp_sqrt_m.py; nothing is recomputed.
# Uses the same "height" as compare_days.py:
#   height of each second = median over m >= 50 of MP / sqrt(m)
# here averaged per minute (1440 columns per day; --block changes it, e.g. 1s, 10min, 30min).
#
# Three rows, each as 2D (left, one line per feature) and 3D (right, axes time x feature x height):
#   1. anomaly day height
#   2. baseline day height
#   3. difference anomaly - baseline at the same time of day
#      red  = anomaly higher (mountain direction)
#      blue = anomaly lower  (valley direction)
# Grey (2D) / gap (3D) = feature is all zeros on that day (no matrix saved).
# The 3D uses at most 1-minute resolution (a 1-second surface would be too heavy to draw).
# Also an interactive HTML with the three 3D views (rotate with the mouse).
# "(!)" after a feature name = more than half of its MP values (m >= 50) are 0 on one
# of the two days: the all-zero-window problem (see step0_analysis.md), do not trust it.
#
# Run from the repository root, e.g.:
#   python scripts/step0/event_overview.py --event slammer --anomaly anomaly_25jan --baseline baseline_18jan --mark 05:30
# ==============================================================================

import argparse
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from compare_days import block_heights, MIN_WINDOW

# same order as the columns of the feature CSVs
FEATURES = [
    'announcements', 'withdrawals', 'nlri_ann', 'dups', 'origin_0', 'origin_2', 'origin_changes',
    'as_path_max', 'unique_as_path_max', 'edit_distance_avg', 'edit_distance_max',
    'edit_distance_dict_0', 'edit_distance_dict_1', 'edit_distance_dict_2', 'edit_distance_dict_3',
    'edit_distance_dict_4', 'edit_distance_dict_5', 'edit_distance_dict_6',
    'edit_distance_unique_dict_0', 'edit_distance_unique_dict_1',
    'imp_wd', 'imp_wd_spath', 'imp_wd_dpath', 'number_rare_ases', 'rare_ases_avg', 'flaps', 'nadas',
]
HEIGHT_MAX = 1.5     # colour scale of the heights (1.41 = all-zero window)
DIFF_LIMIT = 0.3     # colour scale of the difference panel: -0.3 ... +0.3
MAX_3D_BLOCK = '1min'  # finest resolution used for the 3D


def day_matrix(matrices_dir, block):
    """Feature x block matrix of heights for one day, and which features look broken."""
    n_blocks = int(pd.Timedelta('1D') / pd.Timedelta(block))
    columns = pd.date_range('2000-01-01', periods=n_blocks, freq=block).strftime('%H:%M:%S')
    rows, broken = [], []
    for f in FEATURES:
        path = os.path.join(matrices_dir, f + '.npz')
        if not os.path.exists(path):          # all zeros on this day: nothing was saved
            rows.append(np.full(n_blocks, np.nan))
            broken.append(False)
            continue
        rows.append(block_heights(path, block=block, time_format='%H:%M:%S').reindex(columns).values)
        d = np.load(path)
        pmp = d['pmp'][d['windows'] >= MIN_WINDOW]
        broken.append(np.nanmean(pmp < 1e-6) > 0.5)
    return np.array(rows), broken


def main():
    parser = argparse.ArgumentParser(description="All features of one event in one picture")
    parser.add_argument('--root', default=os.path.join('results', 'step0'),
                        help='results root (default results/step0; results/corrected for end-aligned)')
    parser.add_argument('--event', required=True, help='folder name under the root, e.g. slammer')
    parser.add_argument('--anomaly', required=True, help='anomaly day folder, e.g. anomaly_25jan')
    parser.add_argument('--baseline', required=True, help='baseline day folder, e.g. baseline_18jan')
    parser.add_argument('--mark', nargs='*', default=[], help='times to mark with a dashed line, e.g. 05:30 11:15')
    parser.add_argument('--block', default='1min', help='time resolution, e.g. 1s, 1min, 10min, 30min (default 1min)')
    parser.add_argument('--out', default=None, help='output PNG (default results/step0/<event>/overview_<event>_<block>.png)')
    args = parser.parse_args()

    base_dir = os.path.join(args.root, args.event)
    out = args.out or os.path.join(base_dir, f'overview_{args.event}_{args.block}.png')

    a, a_broken = day_matrix(os.path.join(base_dir, args.anomaly, 'matrices'), args.block)
    b, b_broken = day_matrix(os.path.join(base_dir, args.baseline, 'matrices'), args.block)
    diff = a - b
    labels = [f + (' (!)' if x or y else '') for f, x, y in zip(FEATURES, a_broken, b_broken)]

    # 3D: same values, but never finer than 1 minute
    if pd.Timedelta(args.block) < pd.Timedelta(MAX_3D_BLOCK):
        block_3d = MAX_3D_BLOCK
        a3, _ = day_matrix(os.path.join(base_dir, args.anomaly, 'matrices'), block_3d)
        b3, _ = day_matrix(os.path.join(base_dir, args.baseline, 'matrices'), block_3d)
    else:
        block_3d, a3, b3 = args.block, a, b
    step_h = pd.Timedelta(block_3d) / pd.Timedelta('1h')
    hours_3d = np.arange(a3.shape[1]) * step_h            # x axis of the 3D: block start, in hours

    n = len(FEATURES)
    extent = [0, 24, n - 0.5, -0.5]            # x axis in hours
    heights_cmap = plt.get_cmap('viridis').copy()
    heights_cmap.set_bad('lightgrey')
    diff_cmap = plt.get_cmap('RdBu_r').copy()
    diff_cmap.set_bad('lightgrey')

    panels = [
        (a, a3, heights_cmap, 0, HEIGHT_MAX, f'Anomaly day ({args.anomaly})', 'height (MP / sqrt(m))'),
        (b, b3, heights_cmap, 0, HEIGHT_MAX, f'Baseline day ({args.baseline})', 'height (MP / sqrt(m))'),
        (diff, a3 - b3, diff_cmap, -DIFF_LIMIT, DIFF_LIMIT,
         'Difference: anomaly - baseline (red = higher, blue = lower)', 'height anomaly - height baseline'),
    ]

    # ---------- static picture: 2D left, 3D right ----------
    fig = plt.figure(figsize=(34, 27))
    grid = fig.add_gridspec(3, 2, width_ratios=[1, 1], left=0.07, right=0.98, top=0.95, bottom=0.04,
                            wspace=0.08, hspace=0.18)
    x_grid, y_grid = np.meshgrid(hours_3d, np.arange(n))
    for row, (data, data_3d, cmap, vmin, vmax, title, zlabel) in enumerate(panels):
        ax = fig.add_subplot(grid[row, 0])
        image = ax.imshow(data, aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax,
                          extent=extent, interpolation='antialiased')
        ax.set_title(title, fontsize=14)
        ax.set_yticks(range(n))
        ax.set_yticklabels(labels, fontsize=10)
        ax.set_xticks(range(0, 25, 1))
        ax.set_xlabel('Time of day (UTC, hours)', fontsize=11)
        for t in args.mark:
            h, m = map(int, t.split(':'))
            ax.axvline(h + m / 60, color='red', linestyle='--', linewidth=1.2)
        fig.colorbar(image, ax=ax, label=zlabel)

        ax3 = fig.add_subplot(grid[row, 1], projection='3d')
        clipped = np.clip(data_3d, vmin, vmax)          # keep the surface inside the z range
        ax3.plot_surface(x_grid, y_grid, clipped, cmap=cmap, vmin=vmin, vmax=vmax,
                         rstride=1, cstride=1, linewidth=0, antialiased=False)
        ax3.set_title(f'{title} - 3D ({block_3d})', fontsize=13)
        ax3.set_xlabel('Time (UTC hours)')
        ax3.set_ylabel('Feature', labelpad=40)
        ax3.set_yticks(range(n))
        ax3.set_yticklabels(labels, fontsize=7)
        ax3.set_box_aspect((2, 1.4, 0.6))               # longer feature axis, so the names are readable
        ax3.set_zlabel(zlabel)
        ax3.set_zlim(vmin, vmax)
        ax3.view_init(elev=55, azim=-70)               # seen from higher up, so the feature axis opens
    fig.suptitle(f'{args.event}: all features, resolution {args.block} (3D: {block_3d})', fontsize=18)
    fig.savefig(out, dpi=90)
    plt.close(fig)
    print(f'written: {out}')

    # ---------- interactive 3D (HTML) ----------
    html = out[:-4] + '_3d.html'
    fig = make_subplots(rows=1, cols=3, specs=[[{'type': 'scene'}] * 3],
                        subplot_titles=[p[5] for p in panels])
    plotly_scales = ['Viridis', 'Viridis', 'RdBu_r']
    for col, ((_, data_3d, _, vmin, vmax, _, zlabel), scale) in enumerate(zip(panels, plotly_scales), 1):
        fig.add_trace(go.Surface(x=hours_3d, y=list(range(n)), z=np.clip(data_3d, vmin, vmax), colorscale=scale,
                                 cmin=vmin, cmax=vmax, showscale=(col != 2),
                                 colorbar=dict(x=0.62 if col == 1 else 1.0, len=0.6, title=zlabel)),
                      row=1, col=col)
    scenes = {}
    for col, (_, _, _, _, _, _, zlabel) in enumerate(panels, 1):
        scenes['scene' if col == 1 else f'scene{col}'] = dict(
            xaxis_title='Time (UTC hours)', zaxis_title=zlabel, aspectmode='manual',
            aspectratio=dict(x=2, y=1.4, z=0.6),
            yaxis=dict(title='Feature', tickvals=list(range(n)), ticktext=labels, tickfont=dict(size=8)))
    fig.update_layout(title=f'{args.event}: all features, 3D ({block_3d}); '
                            f'height = median over m >= {MIN_WINDOW} of MP / sqrt(m)',
                      height=750, **scenes)
    fig.write_html(html, include_plotlyjs='cdn')
    print(f'written: {html}')


if __name__ == '__main__':
    main()
