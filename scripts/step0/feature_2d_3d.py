# ==============================================================================
# Step 0 - 2D and 3D of the normalised PMP in ONE figure, per feature
#
# Reads the saved PMP matrices (.npz) written by pmp_sqrt_m.py; nothing is recomputed.
# For every feature of one day:
#   left : series (top) + 2D heatmap of PMP / sqrt(m)    (same as the normalised/ figure)
#   right: 3D surface of PMP / sqrt(m), per-minute max  (same as the 3d/ figure)
# Both sides use the SAME colour scale, so a colour means the same height in 2D and 3D.
#
# Output (next to original/, normalised/, 3d/):
#   <day folder>/2d_3d/<feature>.png    static picture
#   <day folder>/2d_3d/<feature>.html   interactive: 2D heatmap + rotatable 3D side by side
#                                       (both per-minute max, a full 1-second heatmap
#                                        would make the HTML about 100 MB)
#
# Run from the repository root, e.g.:
#   python scripts/step0/feature_2d_3d.py --day results/step0/slammer/anomaly_25jan --date "25 Jan 2003" --jobs 8
# ==============================================================================

import argparse
import os
from multiprocessing import Pool

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pmp_sqrt_m import normalise_sqrt_m, per_minute_max


def draw_feature(task):
    npz_path, date_label, out_dir = task
    name = os.path.basename(npz_path)[:-4]
    d = np.load(npz_path)
    windows = d['windows']
    time = pd.to_datetime(d['time'])
    pmp_norm = normalise_sqrt_m(d['pmp'].astype(float))
    vmax = np.nanpercentile(pmp_norm, 99) if not np.isnan(pmp_norm).all() else 2   # as the original

    # per-minute max for the 3D (and the HTML), only complete minutes (as in plot_3d)
    z = per_minute_max(pmp_norm)
    start_hour = (time[0] - time[0].normalize()).total_seconds() / 3600
    hours = start_hour + np.arange(z.shape[1]) / 60
    complete = ~np.isnan(z).any(axis=0)
    z, hours = z[:, complete], hours[complete]

    # ---------- static picture ----------
    fig = plt.figure(figsize=(24, 9))
    grid = fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[1, 2.5])
    ax_series = fig.add_subplot(grid[0, 0])
    ax_2d = fig.add_subplot(grid[1, 0], sharex=ax_series)
    ax_3d = fig.add_subplot(grid[:, 1], projection='3d')

    ax_series.plot(time, d['series'], color='tab:blue', linewidth=1)
    ax_series.set_title(f'BGP Volume ({name}) - {date_label}', fontweight='bold')
    ax_series.set_ylabel('Value / s')
    ax_series.grid(True, linestyle='--', alpha=0.5)
    plt.setp(ax_series.get_xticklabels(), visible=False)

    c = ax_2d.pcolormesh(time, windows, pmp_norm, cmap='inferno', shading='auto', vmin=0, vmax=vmax)
    ax_2d.set_title(f'Pan Matrix Profile / sqrt(m) - {name}', fontweight='bold')
    ax_2d.set_ylabel('Window m (s)')
    ax_2d.set_xlabel('Local Time (UTC)', fontweight='bold')
    ax_2d.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.colorbar(c, ax=ax_2d, label='Euclidean Distance / sqrt(m)')

    x_grid, y_grid = np.meshgrid(hours, windows)
    ax_3d.plot_surface(x_grid, y_grid, z, cmap='inferno', vmin=0, vmax=vmax,
                       rstride=1, cstride=2, linewidth=0, antialiased=False)
    ax_3d.set_xlabel('Time (UTC hours)')
    ax_3d.set_ylabel('Window m (s)')
    ax_3d.set_zlabel('Distance / sqrt(m)')
    ax_3d.set_title('3D, per-minute max', fontweight='bold')
    ax_3d.invert_yaxis()
    ax_3d.view_init(elev=35, azim=-60)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, f'{name}.png'), dpi=120)
    plt.close(fig)

    # ---------- interactive version ----------
    fig = make_subplots(rows=1, cols=2, column_widths=[0.45, 0.55],
                        specs=[[{'type': 'heatmap'}, {'type': 'scene'}]],
                        subplot_titles=('2D, per-minute max', '3D, per-minute max (rotate with the mouse)'))
    fig.add_trace(go.Heatmap(x=hours, y=windows, z=z, colorscale='Inferno', zmin=0, zmax=vmax,
                             colorbar=dict(title='Distance / sqrt(m)')), row=1, col=1)
    fig.add_trace(go.Surface(x=hours, y=windows, z=z, colorscale='Inferno', cmin=0, cmax=vmax,
                             showscale=False), row=1, col=2)
    fig.update_xaxes(title_text='Time (UTC hours)', row=1, col=1)
    fig.update_yaxes(title_text='Window m (s)', row=1, col=1)
    fig.update_layout(title=f'Pan Matrix Profile / sqrt(m) - {name} - {date_label}',
                      scene=dict(xaxis_title='Time (UTC hours)', yaxis_title='Window m (s)',
                                 zaxis_title='Distance / sqrt(m)'))
    fig.write_html(os.path.join(out_dir, f'{name}.html'), include_plotlyjs='cdn')
    return f'{name}: done'


def main():
    parser = argparse.ArgumentParser(description="2D + 3D of the normalised PMP in one figure, per feature")
    parser.add_argument('--day', required=True, help='day folder, e.g. results/step0/slammer/anomaly_25jan')
    parser.add_argument('--date', required=True, help='date shown in the titles, e.g. "25 Jan 2003"')
    parser.add_argument('--jobs', type=int, default=1, help='features drawn in parallel (default 1)')
    args = parser.parse_args()

    matrices = os.path.join(args.day, 'matrices')
    out_dir = os.path.join(args.day, '2d_3d')
    os.makedirs(out_dir, exist_ok=True)
    tasks = [(os.path.join(matrices, f), args.date, out_dir)
             for f in sorted(os.listdir(matrices)) if f.endswith('.npz')]

    print(f'{len(tasks)} features from {matrices}, {args.jobs} in parallel', flush=True)
    with Pool(args.jobs) as pool:
        for i, msg in enumerate(pool.imap_unordered(draw_feature, tasks), 1):
            print(f'[{i}/{len(tasks)}] {msg}', flush=True)
    print(f'Finished. Results in {out_dir}')


if __name__ == '__main__':
    main()
