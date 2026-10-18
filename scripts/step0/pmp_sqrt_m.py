# ==============================================================================
# Step 0 - Pan Matrix Profile with the two suggestions of the MADRID authors
#
# Based on: bgp-anomaly-detection-tfg/PMP - All features/<event>/pmp_all_features.py
#           (Óscar Cuevas Martínez, UAM)
#
# UNCHANGED from the original:
#   - how the 1-second series is built (resample 1 s, sum, missing seconds = 0)
#   - how the PMP is computed (matrixprofile, m = 5..300 s step 5, NaN padding)
#   - the original 2-panel figure
#
# NEW:
#   1. each row of the PMP divided by sqrt(m)             (MADRID suggestion 1)
#   2. 3D plot of the normalised PMP (PNG + interactive)  (MADRID suggestion 2)
#   3. the PMP matrix is saved (.npz), so figures can be redrawn later
#      without recomputing (the original only saved PNGs)
#   4. input file, output folder and date come from the command line,
#      so one script serves all events instead of one copy per event
# ==============================================================================

import argparse
import os
import warnings
from multiprocessing import Pool

import matplotlib
matplotlib.use("Agg")  # draw to files only, no window (we run on a server)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matrixprofile as mp
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURATION (same as the original) ---
WINDOWS_TO_TEST = range(5, 305, 5)

COLUMNS_TO_ANALYZE = [
    "announcements", "withdrawals", "nlri_ann", "dups", "origin_0",
    "origin_2", "origin_changes", "as_path_max", "unique_as_path_max",
    "edit_distance_avg", "edit_distance_max", "edit_distance_dict_0",
    "edit_distance_dict_1", "edit_distance_dict_2", "edit_distance_dict_3",
    "edit_distance_dict_4", "edit_distance_dict_5", "edit_distance_dict_6",
    "edit_distance_unique_dict_0", "edit_distance_unique_dict_1", "imp_wd",
    "imp_wd_spath", "imp_wd_dpath", "number_rare_ases", "rare_ases_avg",
    "flaps", "nadas"
]


# ------------------------------------------------------------------------------
# PMP computation - UNCHANGED (the loop of section 2.2 in the original)
# ------------------------------------------------------------------------------
def compute_pmp(data_values, column_name="", threads=1):
    pmp_matrix = []
    for idx, w in enumerate(WINDOWS_TO_TEST, 1):
        if idx % 20 == 0 or idx == 1:   # progress message, as in the original
            print(f"  {column_name}: window m={w}s ...", flush=True)
        # NEW: n_jobs = CPU cores for one matrix profile (the original used the default, 1).
        # Same numbers, only faster.
        profile = mp.compute(data_values, windows=w, n_jobs=threads)
        mp_values = profile['mp']
        pad_length = len(data_values) - len(mp_values)
        mp_padded = np.pad(mp_values, (0, pad_length), constant_values=np.nan)
        pmp_matrix.append(mp_padded)
    return np.array(pmp_matrix)


# ------------------------------------------------------------------------------
# NEW 1 - MADRID suggestion 1: divide every row (one window length m) by sqrt(m)
# A z-normalised distance of length m is at most 2*sqrt(m), so without this the
# rows with large m are always brighter. After dividing, every row is in [0, 2].
# ------------------------------------------------------------------------------
def normalise_sqrt_m(pmp_matrix):
    m = np.array(list(WINDOWS_TO_TEST), dtype=float)
    return pmp_matrix / np.sqrt(m)[:, None]   # [:, None] = divide row by row


# ------------------------------------------------------------------------------
# 2-panel figure - UNCHANGED from section 2.3 of the original
# (only the colour-bar label is a parameter, so the normalised figure says "/ sqrt(m)")
# ------------------------------------------------------------------------------
def plot_2d(ts_data, pmp_matrix, column_name, date_label, colorbar_label, output_filename):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                   gridspec_kw={'height_ratios': [1, 2.5]})

    ax1.plot(ts_data.index, ts_data.values, color='tab:blue', linewidth=1)
    ax1.set_title(f'BGP Volume ({column_name}) - {date_label}', fontweight='bold')
    ax1.set_ylabel('Value / s')
    ax1.grid(True, linestyle='--', alpha=0.5)

    cmap = plt.cm.inferno
    vmax_auto = np.nanpercentile(pmp_matrix, 99) if not np.isnan(pmp_matrix).all() else 25
    c = ax2.pcolormesh(ts_data.index, list(WINDOWS_TO_TEST), pmp_matrix, cmap=cmap,
                       shading='auto', vmin=0, vmax=vmax_auto)
    ax2.set_title(f'Pan Matrix Profile - {column_name}', fontweight='bold')
    ax2.set_ylabel('Window m (s)')
    ax2.set_xlabel('Local Time (UTC)', fontweight='bold')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    fig.colorbar(c, ax=ax2, label=colorbar_label)

    plt.tight_layout()
    plt.savefig(output_filename, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------------------
# NEW 2 - MADRID suggestion 2: 3D plot of the normalised PMP
# A day has 86,400 columns: too many for a 3D surface. We keep the MAXIMUM of
# each minute (1,440 columns), so a short spike is never averaged away.
# ------------------------------------------------------------------------------
def per_minute_max(pmp_matrix):
    rows, n = pmp_matrix.shape
    n_minutes = int(np.ceil(n / 60))
    padded = np.full((rows, n_minutes * 60), np.nan)
    padded[:, :n] = pmp_matrix
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # minutes that are all NaN stay NaN
        return np.nanmax(padded.reshape(rows, n_minutes, 60), axis=2)


def plot_3d(ts_data, pmp_norm, column_name, date_label, png_filename, html_filename):
    z = per_minute_max(pmp_norm)
    start = ts_data.index[0]
    start_hour = (start - start.normalize()).total_seconds() / 3600
    hours = start_hour + np.arange(z.shape[1]) / 60           # x axis: time in UTC hours
    windows = np.array(list(WINDOWS_TO_TEST), dtype=float)    # y axis: window m

    # the last m-1 seconds of each row are NaN (padding of the original code);
    # keep only the minutes where every row has a value, so the plot has no fake zeros
    complete = ~np.isnan(z).any(axis=0)
    z, hours = z[:, complete], hours[complete]
    title = f'Pan Matrix Profile / sqrt(m) - {column_name} - {date_label}'

    # static picture (matplotlib)
    x_grid, y_grid = np.meshgrid(hours, windows)
    fig = plt.figure(figsize=(14, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(x_grid, y_grid, z, cmap='inferno',
                    rstride=1, cstride=2, linewidth=0, antialiased=False)
    ax.set_xlabel('Time (UTC hours)')
    ax.set_ylabel('Window m (s)')
    ax.set_zlabel('Distance / sqrt(m)')
    ax.set_title(title, fontweight='bold')
    ax.invert_yaxis()                 # small m at the back, so it does not hide the rest
    ax.view_init(elev=35, azim=-60)
    plt.savefig(png_filename, dpi=150)
    plt.close(fig)

    # interactive version (plotly): open the .html in a browser and rotate it with the mouse
    fig = go.Figure(go.Surface(x=hours, y=windows, z=z, colorscale='Inferno'))
    fig.update_layout(title=title, scene=dict(xaxis_title='Time (UTC hours)',
                                              yaxis_title='Window m (s)',
                                              zaxis_title='Distance / sqrt(m)'))
    fig.write_html(html_filename, include_plotlyjs='cdn')


# ------------------------------------------------------------------------------
# One feature: compute once, save the matrix, draw the three figures
# ------------------------------------------------------------------------------
def analyse_feature(task):
    column_name, ts_data, date_label, out_dir, threads = task
    data_values = ts_data.values.astype(float)

    # same rule as the original: a feature that is always 0 is skipped
    if np.max(data_values) == 0:
        return f"{column_name}: only zeros, skipped"

    pmp_matrix = compute_pmp(data_values, column_name, threads)

    # NEW 3: save the matrix (float32 is enough and halves the file size)
    np.savez(os.path.join(out_dir, 'matrices', f'{column_name}.npz'),
             pmp=pmp_matrix.astype(np.float32),
             windows=np.array(list(WINDOWS_TO_TEST)),
             time=ts_data.index.values,
             series=data_values)

    # figure 1: original (as in the CNSM paper)
    plot_2d(ts_data, pmp_matrix, column_name, date_label, 'Euclidean Distance',
            os.path.join(out_dir, 'original', f'{column_name}.png'))

    # figure 2: normalised by sqrt(m)
    pmp_norm = normalise_sqrt_m(pmp_matrix)
    plot_2d(ts_data, pmp_norm, column_name, date_label, 'Euclidean Distance / sqrt(m)',
            os.path.join(out_dir, 'normalised', f'{column_name}.png'))

    # figure 3: 3D of the normalised PMP
    plot_3d(ts_data, pmp_norm, column_name, date_label,
            os.path.join(out_dir, '3d', f'{column_name}.png'),
            os.path.join(out_dir, '3d', f'{column_name}.html'))

    return f"{column_name}: done"


def main():
    parser = argparse.ArgumentParser(description="PMP with sqrt(m) normalisation and 3D plots")
    parser.add_argument('--csv', required=True, help='feature CSV (output of feature_extractor_1s.py)')
    parser.add_argument('--out', required=True, help='output folder for this day')
    parser.add_argument('--date', required=True, help='date shown in the titles, e.g. "25 Jan 2003"')
    parser.add_argument('--features', nargs='*', default=COLUMNS_TO_ANALYZE,
                        help='only these features (default: all 27)')
    parser.add_argument('--jobs', type=int, default=1,
                        help='features computed in parallel (default 1 = one after another)')
    parser.add_argument('--threads', type=int, default=1,
                        help='CPU cores for each matrix profile (default 1, as the original). '
                             'Total cores used = jobs x threads')
    args = parser.parse_args()

    for sub in ('original', 'normalised', '3d', 'matrices'):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)

    print(f"Loading {args.csv} ...")
    df = pd.read_csv(args.csv)
    df['window_start'] = pd.to_datetime(df['window_start'])
    df.set_index('window_start', inplace=True)

    tasks = []
    for column_name in args.features:
        if column_name not in df.columns:
            print(f"  WARNING: column {column_name} not in the CSV, skipped")
            continue
        ts_data = df[column_name].resample('1s').sum().fillna(0)   # same as original ('1S')
        tasks.append((column_name, ts_data, args.date, args.out, args.threads))

    print(f"{len(tasks)} features, {args.jobs} in parallel, {args.threads} core(s) each "
          f"= {args.jobs * args.threads} cores")
    if args.jobs == 1:
        for i, task in enumerate(tasks, 1):
            print(f"[{i}/{len(tasks)}] {analyse_feature(task)}", flush=True)
    else:
        with Pool(args.jobs) as pool:
            for i, msg in enumerate(pool.imap_unordered(analyse_feature, tasks), 1):
                print(f"[{i}/{len(tasks)}] {msg}", flush=True)

    print(f"Finished. Results in {args.out}")


if __name__ == '__main__':
    main()
