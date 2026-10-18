# ==============================================================================
# RIPE 93 poster - figures at poster quality (large fonts, aligned panels)
#
# Reads only saved results; nothing is recomputed:
#   results/corrected/...npz          (corrected PMP: E1 end-aligned + E2 fixes)
#   results/e3/<rule>_<event>_minutes.csv, summary.csv, summary_average.csv  (from threshold_rule.py)
#
# Output: results/poster/fig_*.png (300 dpi)
#   fig_slammer_pmp.png     what the method sees: one feature, one day (series + PMP/sqrt(m) heatmap)
#   fig_slammer_3d.png      the same as a 3D landscape
#   fig_alarms.png          alarms of the two rules for the six events, with the published event windows
#   fig_tradeoff.png        detection vs false alarms, all rules and k
#
# Run from the repository root:
#   python scripts/poster/figures.py
# ==============================================================================

import argparse
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'step0'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'e3'))
from pmp_sqrt_m import normalise_sqrt_m, per_minute_max
import threshold_rule as T

ROOT = os.path.join('results', 'corrected')
E3 = os.path.join('results', 'e3')
OUT = os.path.join('results', 'poster')
plt.rcParams.update({'font.size': 18, 'axes.titlesize': 22, 'axes.labelsize': 20,
                     'xtick.labelsize': 17, 'ytick.labelsize': 17, 'legend.fontsize': 16})

# the two rules shown on the poster: (rule, k, label)
SHOWN = [('smooth10', 3, 'Static limits (normal day), 3 features'),
         ('dynamic4', 2, 'Dynamic limits (last 2 h, 4σ), 2 features')]


def fig_slammer_pmp():
    d = np.load(os.path.join(ROOT, 'slammer', 'anomaly_25jan', 'matrices', 'rare_ases_avg.npz'))
    time = pd.to_datetime(d['time'])
    norm = normalise_sqrt_m(d['pmp'].astype(float))
    series = pd.Series(d['series'], index=time).resample('1min').mean()
    onset = pd.Timestamp('2003-01-25 05:31')

    fig = plt.figure(figsize=(16, 9))
    grid = fig.add_gridspec(2, 2, width_ratios=[40, 1], height_ratios=[1, 2.2], hspace=0.22, wspace=0.03)
    ax1 = fig.add_subplot(grid[0, 0])
    ax2 = fig.add_subplot(grid[1, 0], sharex=ax1)
    cax = fig.add_subplot(grid[1, 1])
    ax1.plot(series.index, series.values, color='tab:blue', linewidth=1.2)
    ax1.set_ylabel('rare ASes\n(avg / s)')
    ax1.set_title('     What RRC04 saw: rare ASes in AS paths, every second', loc='left')
    ax1.text(0.0, 1.13, '1', transform=ax1.transAxes, fontsize=20, fontweight='bold', color='white',
             va='center', bbox=dict(boxstyle='circle,pad=0.25', facecolor='#E07B00', edgecolor='none'))
    plt.setp(ax1.get_xticklabels(), visible=False)
    vmax = np.nanpercentile(norm, 99)
    c = ax2.pcolormesh(time[::5], d['windows'], norm[:, ::5], cmap='inferno', shading='auto', vmin=0, vmax=vmax,
                       rasterized=True)
    ax2.set_ylabel('window length m (s)')
    ax2.set_ylim(50, d['windows'][-1])           # m < 50: sparse-data effects, not used by the detector
    ax2.set_xlabel('time (UTC)')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    for ax in (ax1, ax2):
        ax.axvline(onset, color='cyan', linestyle='--', linewidth=2)
    ax2.text(onset, d['windows'][-1] * 0.95, '  worm starts 05:31', color='cyan', fontsize=18, va='top')
    ax2.annotate('05:31 worm hits:\nthe feed turns monotonous\nfor hours', xy=(pd.Timestamp('2003-01-25 07:00'), 150),
                 xytext=(pd.Timestamp('2003-01-25 11:30'), 230), color='white', fontsize=17, fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='white', linewidth=2.5))
    ax2.text(0.0, 1.04, '2', transform=ax2.transAxes, fontsize=20, fontweight='bold', color='white',
             va='center', bbox=dict(boxstyle='circle,pad=0.25', facecolor='#E07B00', edgecolor='none'))
    ax2.set_title('     Have we seen this traffic before today?   bright = new,  dark = seen many times', loc='left')
    fig.colorbar(c, cax=cax, label='how unusual (distance / √m)')
    fig.savefig(os.path.join(OUT, 'fig_slammer_pmp.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)


def fig_slammer_3d():
    d = np.load(os.path.join(ROOT, 'slammer', 'anomaly_25jan', 'matrices', 'rare_ases_avg.npz'))
    keep = d['windows'] >= 50                      # as the detector: m >= 50
    z = per_minute_max(normalise_sqrt_m(d['pmp'].astype(float)))[keep]
    hours = np.arange(z.shape[1]) / 60
    complete = ~np.isnan(z).any(axis=0)
    z, hours = z[:, complete], hours[complete]
    x, y = np.meshgrid(hours, d['windows'][keep])
    fig = plt.figure(figsize=(13, 9))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(x, y, z, cmap='inferno', vmin=0, vmax=np.nanpercentile(z, 99),
                    rstride=1, cstride=2, linewidth=0, antialiased=False, rasterized=True)
    ax.set_xlabel('time (UTC hours)', labelpad=14)
    ax.set_ylabel('window m (s)', labelpad=14)
    ax.set_zlabel('how unusual', labelpad=10)
    ax.invert_yaxis()
    ax.view_init(elev=35, azim=-60)
    ax.set_title('Slammer in 3D: the worm digs a trench at 05:31', pad=10, fontsize=24, fontweight='bold')
    fig.text(0.08, 0.93, '3', fontsize=22, fontweight='bold', color='white', va='center', bbox=dict(boxstyle='circle,pad=0.25', facecolor='#E07B00', edgecolor='none'))
    fig.savefig(os.path.join(OUT, 'fig_slammer_3d.png'), dpi=300, bbox_inches='tight', pad_inches=0.5)
    plt.close(fig)


def fig_alarms():
    events = list(T.EVENTS)
    fig, ax = plt.subplots(figsize=(15, 8.5))
    row_h = 1.0
    yticks, ylabels = [], []
    colours = ['tab:red', 'tab:purple']
    for i, event in enumerate(events):
        anomaly, baseline, s0, e0 = T.EVENTS[event]
        start, end = T.minute_index(s0), T.minute_index(e0)
        y0 = (len(events) - 1 - i) * 3 * row_h
        ax.add_patch(plt.Rectangle((start / 60, y0 - 0.4), (end - start) / 60, 2 * row_h + 0.3,
                                   color='tab:orange', alpha=0.25, linewidth=0))
        ax.plot([start / 60] * 2, [y0 - 0.4, y0 + 2 * row_h - 0.1], color='tab:orange', linewidth=3)
        for j, (rule, k, label) in enumerate(SHOWN):
            counts = pd.read_csv(os.path.join(E3, f'{rule}_{event}_minutes.csv'), index_col=0)['features_firing_anomaly']
            alarm = T.alarms(counts, k)
            m = np.where(alarm)[0]
            ax.plot(m / 60, np.full(len(m), y0 + j * row_h + 0.3), '|', color=colours[j], markersize=22,
                    markeredgewidth=2.2, label=label if i == 0 else None)
        yticks.append(y0 + 0.8)
        ylabels.append(T.NAMES[event])
    ax.add_patch(plt.Rectangle((0, 0), 0, 0, color='tab:orange', alpha=0.25, label='published event window'))
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xlabel('time of day (UTC, hours)')
    ax.set_ylim(-1, len(events) * 3 * row_h)
    ax.grid(True, axis='x', alpha=0.3)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=False)
    ax.set_title('Alarms on the event day (each tick = one alarm minute)', loc='left')
    fig.savefig(os.path.join(OUT, 'fig_alarms.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)


def fig_tradeoff():
    avg = pd.read_csv(os.path.join(E3, 'summary_average.csv'))
    labels = {'band': 'static, per second (D16)', 'smooth10': 'static, 10-min smoothed',
              'smooth30': 'static, 30-min smoothed', 'dynamic3': 'dynamic, 3σ', 'dynamic4': 'dynamic, 4σ'}
    fig, ax = plt.subplots(figsize=(11, 9))
    for rule, marker in zip(labels, ['o', 's', '^', 'D', 'v']):
        a = avg[avg.rule == rule]
        ax.plot(a.mean_false_alarm_pct_before, a.mean_recall, marker=marker, markersize=10, linewidth=2.5,
                label=labels[rule])
        for _, r in a.iterrows():
            if r.k <= 4:
                ax.annotate(f'k={int(r.k)}', (r.mean_false_alarm_pct_before, r.mean_recall),
                            textcoords='offset points', xytext=(7, 4), fontsize=13)
    ax.set_xlabel('false alarms (% of normal minutes)')
    ax.set_ylabel('share of the event window detected')
    ax.set_title('More detection costs more false alarms', loc='left')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='lower right')
    fig.savefig(os.path.join(OUT, 'fig_tradeoff.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)


def main():
    global E3, OUT
    parser = argparse.ArgumentParser(description="Poster figures")
    parser.add_argument('--e3', default=E3, help='E3 results folder (default results/e3)')
    parser.add_argument('--out', default=OUT, help='output folder (default results/poster)')
    args = parser.parse_args()
    E3, OUT = args.e3, args.out
    os.makedirs(OUT, exist_ok=True)
    for f in (fig_slammer_pmp, fig_slammer_3d, fig_alarms, fig_tradeoff):
        f()
        print(f'{f.__name__}: done', flush=True)
    print(f'Finished. Figures in {OUT}')


if __name__ == '__main__':
    main()
