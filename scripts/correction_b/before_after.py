# ==============================================================================
# Before / after: Step 0 next to the corrected PMP (E1 end-alignment + E2 fixes)
#
# Reads the saved matrices of both versions; nothing is recomputed.
# One figure per feature and day, both versions on the SAME colour scale:
#   top row   : 2D heatmap of PMP / sqrt(m)       Step 0 | corrected
#   bottom row: 3D surface, per-minute max        Step 0 | corrected
# PNG + interactive HTML (the HTML uses the per-minute max also for the 2D,
# a full 1-second heatmap would make the file about 100 MB).
#
# Output: <after root>/<event>/<day>/before_after/<feature>.png and .html
#
# Run from the repository root, e.g.:
#   python scripts/correction_b/before_after.py --day slammer/anomaly_25jan --date "25 Jan 2003" --jobs 8
# ==============================================================================

import argparse
import os
import sys
import warnings
from multiprocessing import Pool

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'step0'))
from pmp_sqrt_m import normalise_sqrt_m, per_minute_max


def load(npz_path):
    """Normalised PMP, windows, time, and the per-minute 3D data (complete minutes only)."""
    d = np.load(npz_path)
    windows = d['windows']
    time = pd.to_datetime(d['time'])
    norm = normalise_sqrt_m(d['pmp'].astype(float))
    z = per_minute_max(norm)
    start_hour = (time[0] - time[0].normalize()).total_seconds() / 3600
    hours = start_hour + np.arange(z.shape[1]) / 60
    complete = ~np.isnan(z).any(axis=0)
    return norm, windows, time, hours[complete], z[:, complete]


def draw(task):
    name, before_path, after_path, date_label, out_dir = task
    b_norm, windows, b_time, b_hours, b_z = load(before_path)
    a_norm, _, a_time, a_hours, a_z = load(after_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        vmax = max(np.nanpercentile(b_norm, 99), np.nanpercentile(a_norm, 99))   # one scale for both
    if not vmax > 0:
        vmax = 2

    # ---------- static picture ----------
    fig = plt.figure(figsize=(26, 16))
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 1.2], hspace=0.15, wspace=0.08,
                            left=0.05, right=0.97, top=0.93, bottom=0.04)
    for col, (label, norm, time, hours, z) in enumerate([
            ('Step 0 (original)', b_norm, b_time, b_hours, b_z),
            ('Corrected (E1 end-aligned + E2 fixes)', a_norm, a_time, a_hours, a_z)]):
        ax = fig.add_subplot(grid[0, col])
        c = ax.pcolormesh(time, windows, norm, cmap='inferno', shading='auto', vmin=0, vmax=vmax)
        ax.set_title(f'{label} - 2D', fontweight='bold', fontsize=14)
        ax.set_ylabel('Window m (s)')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.colorbar(c, ax=ax, label='Distance / sqrt(m)')

        ax3 = fig.add_subplot(grid[1, col], projection='3d')
        x_grid, y_grid = np.meshgrid(hours, windows)
        ax3.plot_surface(x_grid, y_grid, np.clip(z, 0, vmax), cmap='inferno', vmin=0, vmax=vmax,
                         rstride=1, cstride=2, linewidth=0, antialiased=False)
        ax3.set_title(f'{label} - 3D, per-minute max', fontweight='bold', fontsize=14)
        ax3.set_xlabel('Time (UTC hours)')
        ax3.set_ylabel('Window m (s)')
        ax3.set_zlabel('Distance / sqrt(m)')
        ax3.set_xlim(0, 24)
        ax3.set_zlim(0, vmax)
        ax3.invert_yaxis()
        ax3.view_init(elev=35, azim=-60)
    fig.suptitle(f'{name} - {date_label}: Step 0 vs corrected (same colour scale)', fontsize=18)
    fig.savefig(os.path.join(out_dir, f'{name}.png'), dpi=90)
    plt.close(fig)

    # ---------- interactive version ----------
    fig = make_subplots(rows=2, cols=2, vertical_spacing=0.08,
                        specs=[[{'type': 'heatmap'}, {'type': 'heatmap'}],
                               [{'type': 'scene'}, {'type': 'scene'}]],
                        subplot_titles=('Step 0 - 2D (per-minute max)', 'Corrected - 2D (per-minute max)',
                                        'Step 0 - 3D', 'Corrected - 3D'))
    for col, (hours, z) in enumerate([(b_hours, b_z), (a_hours, a_z)], 1):
        fig.add_trace(go.Heatmap(x=hours, y=windows, z=z, colorscale='Inferno', zmin=0, zmax=vmax,
                                 showscale=(col == 2), colorbar=dict(title='Distance / sqrt(m)', len=0.45, y=0.78)),
                      row=1, col=col)
        fig.add_trace(go.Surface(x=hours, y=windows, z=np.clip(z, 0, vmax), colorscale='Inferno',
                                 cmin=0, cmax=vmax, showscale=False), row=2, col=col)
    scene = dict(xaxis_title='Time (UTC hours)', yaxis_title='Window m (s)', zaxis_title='Distance / sqrt(m)',
                 zaxis=dict(range=[0, vmax]))
    fig.update_xaxes(title_text='Time (UTC hours)', row=1)
    fig.update_yaxes(title_text='Window m (s)', row=1)
    fig.update_layout(title=f'{name} - {date_label}: Step 0 vs corrected (same colour scale)',
                      height=1100, scene=scene, scene2=scene)
    fig.write_html(os.path.join(out_dir, f'{name}.html'), include_plotlyjs='cdn')
    return f'{name}: done'


def main():
    parser = argparse.ArgumentParser(description="Step 0 vs corrected PMP, per feature, 2D and 3D")
    parser.add_argument('--day', required=True, help='<event>/<day>, e.g. slammer/anomaly_25jan')
    parser.add_argument('--date', required=True, help='date shown in the titles, e.g. "25 Jan 2003"')
    parser.add_argument('--before', default=os.path.join('results', 'step0'), help='root of the original version')
    parser.add_argument('--after', default=os.path.join('results', 'corrected'), help='root of the corrected version')
    parser.add_argument('--jobs', type=int, default=1, help='features drawn in parallel (default 1)')
    args = parser.parse_args()

    before_dir = os.path.join(args.before, args.day, 'matrices')
    after_dir = os.path.join(args.after, args.day, 'matrices')
    out_dir = os.path.join(args.after, args.day, 'before_after')
    os.makedirs(out_dir, exist_ok=True)

    tasks = []
    for f in sorted(set(os.listdir(before_dir)) | set(os.listdir(after_dir))):
        if not f.endswith('.npz'):
            continue
        b, a = os.path.join(before_dir, f), os.path.join(after_dir, f)
        if os.path.exists(b) and os.path.exists(a):
            tasks.append((f[:-4], b, a, args.date, out_dir))
        else:
            print(f'{f[:-4]}: only in one version, skipped', flush=True)

    print(f'{len(tasks)} features of {args.day}, {args.jobs} in parallel', flush=True)
    with Pool(args.jobs) as pool:
        for i, msg in enumerate(pool.imap_unordered(draw, tasks), 1):
            print(f'[{i}/{len(tasks)}] {msg}', flush=True)
    print(f'Finished. Results in {out_dir}')


if __name__ == '__main__':
    main()
