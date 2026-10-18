# ==============================================================================
# E3 - preliminary threshold rule on the corrected PMP (decision D16), and its evaluation
#
# Reads the corrected matrices (E1 end-aligned + E2 fixes); nothing is recomputed.
#
# Three kinds of rules are compared, all without labels and in both directions (valleys and
# mountains). STATIC rules take their limits from the BASELINE day:
#   rule "band" (D16 as written): for every feature and window length m >= 50,
#        low/high = 1st/99th percentile of MP / sqrt(m) on the baseline day; band score =
#        share of window lengths outside [low, high], per minute; a feature FIRES when >= BAND_LIMIT
#   rule "smooth<W>": height per minute (median over m >= 50 of MP / sqrt(m), as in
#        compare_days.py), causal moving average over the last W minutes; a feature FIRES when
#        it is outside the 1st/99th percentile of the same smoothed height on the baseline day
# The DYNAMIC rule ("dynamic<K>", supervisor's mu + K sigma, time-based) needs no baseline day:
#        the 10-min smoothed height is compared with the SAME day's recent past (minutes
#        t-130 .. t-10); robust z = (value - median) / (1.4826 * MAD); a feature FIRES when |z| >= K.
#        Median/MAD instead of mean/std because the heights are skewed, not normal.
# ALARM in a minute when >= k features fire, for PERSIST minutes in a row
# (causal: only the current and earlier minutes are used, like a live detector)
#
# Features left out: all zeros on a day, or mostly-zero profiles (the "(!)" sparse case).
#
# EVALUATION against the published event windows (incident reports, CNSM paper, TFG):
#    delay      = minutes from the event start to the first alarm
#    precision  = alarm minutes inside the window / all alarm minutes of the anomaly day
#    recall     = alarm minutes inside the window / minutes of the window
#    false_alarm_pct_before = % of the minutes BEFORE the event start that raise an alarm
#                             (normal traffic not used for the limits: honest estimate)
#    false_alarm_pct_baseline = % of baseline-day minutes with an alarm
#                             (static rules: the limits come from this day, optimistic;
#                              dynamic rule: a genuine normal day)
#
# Output: results/e3/summary.csv (all rules, all k), results/e3/top_features.csv,
#         results/e3/<rule>_<event>_minutes.csv, results/e3/tradeoff.png,
#         results/e3/alarm_timeline_<rule>_k<k>.png (one per --plots entry)
#
# Run from the repository root:
#   python scripts/e3/threshold_rule.py
# ==============================================================================

import argparse
import os
import warnings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'step0'))
from compare_days import block_heights

warnings.simplefilter('ignore', RuntimeWarning)

# event: (anomaly day, baseline day, window start, window end)  - published event windows, UTC
EVENTS = {
    'slammer':          ('anomaly_25jan', 'baseline_18jan', '05:31', '20:00'),
    'codered':          ('anomaly_19jul', 'baseline_12jul', '10:00', '16:30'),
    'moscow_blackout':  ('anomaly_25may', 'baseline_18may', '03:00', '07:00'),
    'telekom_malaysia': ('anomaly_12jun', 'baseline_5jun',  '08:43', '11:15'),
    'nimda':            ('anomaly_18sep', 'baseline_11sep', '13:19', '24:00'),
    'wannacrypt':       ('anomaly_12may', 'baseline_5may',  '07:44', '24:00'),
}
NAMES = {'slammer': 'Slammer (2003)', 'codered': 'Code Red I (2001)', 'moscow_blackout': 'Moscow blackout (2005)',
         'telekom_malaysia': 'Telekom Malaysia leak (2015)', 'nimda': 'Nimda (2001)', 'wannacrypt': 'WannaCrypt (2017)'}

MIN_WINDOW = 50       # window lengths used (as in the Step 0 analysis)
LOW_Q, HIGH_Q = 1, 99 # percentiles of the baseline day that define "normal"
BAND_LIMIT = 0.5      # a feature fires when at least half of its window lengths are outside
PERSIST = 2           # minutes in a row before an alarm is raised
WARMUP = 30           # first minutes of each day ignored: after end-alignment the long windows have no
                      # values yet and the moving average is still filling (a live detector would
                      # have the previous day); used neither for the limits nor for alarms
K_VALUES = range(1, 7)
DYN_SMOOTH = 10       # dynamic rule: minutes of smoothing of the height
DYN_REF = 120         # dynamic rule: length of the reference (recent past), minutes
DYN_GAP = 10          # dynamic rule: the last minutes are left out of the reference
RULES = ['band', 'smooth10', 'smooth30', 'dynamic3', 'dynamic4']
MINUTES = pd.date_range('2000-01-01', periods=1440, freq='1min').strftime('%H:%M')


def minute_index(hhmm):
    h, m = map(int, hhmm.split(':'))
    return h * 60 + m


def load(path):
    """MP / sqrt(m) for the rows m >= MIN_WINDOW, and the time of each second."""
    d = np.load(path)
    w = d['windows']
    keep = w >= MIN_WINDOW
    norm = d['pmp'][keep].astype(float) / np.sqrt(w[keep])[:, None]
    return norm, pd.to_datetime(d['time'])


def band_per_minute(norm, time, low, high):
    """Per-minute band score: share of window lengths outside [low, high]."""
    valid = ~np.isnan(norm)
    outside = ((norm < low[:, None]) | (norm > high[:, None])) & valid
    n_valid = valid.sum(axis=0)
    score = np.where(n_valid > 0, outside.sum(axis=0) / np.maximum(n_valid, 1), np.nan)
    s = pd.Series(score, index=time).resample('1min').mean()
    s = s[s.index.normalize() == s.index[0].normalize()]
    s.index = s.index.strftime('%H:%M')
    return s.reindex(MINUTES)


def smoothed_height(path, win):
    """Height per minute (as compare_days.py), causal moving average over the last win minutes."""
    s = block_heights(path, block='1min').reindex(MINUTES)
    return s.rolling(win, min_periods=win // 2).mean()


def robust_z(s):
    """(value - median) / (1.4826 * MAD) of the same series over minutes t-DYN_REF-DYN_GAP .. t-DYN_GAP."""
    ref = s.shift(DYN_GAP).rolling(DYN_REF, min_periods=DYN_REF // 2)
    median = ref.median()
    mad = ref.apply(lambda x: np.nanmedian(np.abs(x - np.nanmedian(x))), raw=True) * 1.4826
    return (s - median) / mad.replace(0, np.nan)


def warmup(rule):
    """Minutes at the start of the day without alarms (the dynamic rule first needs its reference)."""
    return DYN_REF + DYN_GAP if rule.startswith('dynamic') else WARMUP


def firing_table(root, event, anomaly, baseline, rule):
    """Minute x feature tables (True = feature fires) for the anomaly and the baseline day."""
    a_dir = os.path.join(root, event, anomaly, 'matrices')
    b_dir = os.path.join(root, event, baseline, 'matrices')
    fire_a, fire_b, skipped = {}, {}, []
    for f in sorted(os.listdir(a_dir)):
        name = f[:-4]
        if not os.path.exists(os.path.join(b_dir, f)):
            skipped.append(f'{name} (all zeros on the baseline day)')
            continue
        a_norm, a_time = load(os.path.join(a_dir, f))
        b_norm, b_time = load(os.path.join(b_dir, f))
        if np.nanmean(a_norm < 1e-6) > 0.5 or np.nanmean(b_norm < 1e-6) > 0.5:
            skipped.append(f'{name} (mostly-zero profile)')
            continue
        if rule == 'band':
            low = np.nanpercentile(b_norm[:, WARMUP * 60:], LOW_Q, axis=1)
            high = np.nanpercentile(b_norm[:, WARMUP * 60:], HIGH_Q, axis=1)
            fire_a[name] = band_per_minute(a_norm, a_time, low, high) >= BAND_LIMIT
            fire_b[name] = band_per_minute(b_norm, b_time, low, high) >= BAND_LIMIT
        elif rule.startswith('dynamic'):
            k_sigma = int(rule.replace('dynamic', ''))
            za = robust_z(smoothed_height(os.path.join(a_dir, f), DYN_SMOOTH))
            zb = robust_z(smoothed_height(os.path.join(b_dir, f), DYN_SMOOTH))
            fire_a[name] = za.abs() >= k_sigma
            fire_b[name] = zb.abs() >= k_sigma
        else:
            win = int(rule.replace('smooth', ''))
            a = smoothed_height(os.path.join(a_dir, f), win)
            b = smoothed_height(os.path.join(b_dir, f), win)
            low, high = np.nanpercentile(b[WARMUP:], LOW_Q), np.nanpercentile(b[WARMUP:], HIGH_Q)
            fire_a[name] = (a < low) | (a > high)
            fire_b[name] = (b < low) | (b > high)
    return pd.DataFrame(fire_a), pd.DataFrame(fire_b), skipped


def alarms(count, k):
    """Alarm minutes: >= k features fire in this minute and the PERSIST-1 minutes before."""
    ok = (count >= k).values
    out = ok.copy()
    for lag in range(1, PERSIST):
        out[lag:] &= ok[:-lag]
        out[:lag] = False
    return out


def evaluate(alarm_a, alarm_b, start, end, warm):
    inside = np.zeros(1440, dtype=bool)
    inside[start:end] = True
    tp = int((alarm_a & inside).sum())
    fp = int((alarm_a & ~inside).sum())
    after = np.where(alarm_a[start:end])[0]
    return {
        'delay_min': int(after[0]) if len(after) else None,
        'precision': round(tp / (tp + fp), 2) if tp + fp else None,
        'recall': round(tp / (end - start), 2),
        'false_alarm_pct_before': round(100 * alarm_a[warm:start].mean(), 1) if start > warm else None,
        'false_alarm_pct_baseline': round(100 * alarm_b[warm:].mean(), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="E3: preliminary threshold rule and evaluation")
    parser.add_argument('--root', default=os.path.join('results', 'corrected'), help='corrected matrices')
    parser.add_argument('--out', default=os.path.join('results', 'e3'), help='output folder')
    parser.add_argument('--plots', nargs='*', default=['smooth10:3', 'dynamic4:2'],
                        help='timeline figures to draw, as rule:k (default smooth10:3 dynamic4:2)')
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    rows, tops, counts = [], [], {}
    for rule in RULES:
        for event, (anomaly, baseline, start_s, end_s) in EVENTS.items():
            fire_a, fire_b, skipped = firing_table(args.root, event, anomaly, baseline, rule)
            start, end = minute_index(start_s), minute_index(end_s)
            count_a, count_b = fire_a.sum(axis=1), fire_b.sum(axis=1)
            warm = warmup(rule)
            count_a.iloc[:warm] = 0            # warm-up: no alarms in the first minutes of the day
            count_b.iloc[:warm] = 0
            counts[(rule, event)] = (count_a, count_b, start, end)
            if rule == RULES[0]:
                print(f'{event}: {fire_a.shape[1]} features used; left out: {", ".join(skipped) if skipped else "none"}')

            pd.DataFrame({'features_firing_anomaly': count_a, 'features_firing_baseline': count_b,
                          'firing_anomaly': fire_a.apply(lambda r: ' '.join(r.index[r]), axis=1)}
                         ).to_csv(os.path.join(args.out, f'{rule}_{event}_minutes.csv'))

            for k in K_VALUES:
                r = evaluate(alarms(count_a, k), alarms(count_b, k), start, end, warm)
                rows.append({'rule': rule, 'event': event, 'k': k, **r})

            # which features separate the event window from the rest of the anomaly day
            inside = np.zeros(1440, dtype=bool)
            inside[start:end] = True
            rate_in, rate_out = fire_a[inside].mean(), fire_a[~inside].mean()
            for f in (rate_in - rate_out).sort_values(ascending=False).index[:5]:
                tops.append({'rule': rule, 'event': event, 'feature': f,
                             'firing_in_window': round(rate_in[f], 2), 'firing_outside': round(rate_out[f], 2)})
            print(f'  rule {rule}: {event} done', flush=True)      # progress (the whole run takes ~6 min)

    summary = pd.DataFrame(rows)
    summary.to_csv(os.path.join(args.out, 'summary.csv'), index=False)
    pd.DataFrame(tops).to_csv(os.path.join(args.out, 'top_features.csv'), index=False)

    # averages over the 6 events, per rule and k
    avg = (summary.assign(detected=summary.delay_min.notna())
           .groupby(['rule', 'k'])
           .agg(events_detected=('detected', 'sum'), mean_recall=('recall', 'mean'),
                median_delay_min=('delay_min', 'median'), mean_false_alarm_pct_before=('false_alarm_pct_before', 'mean'),
                mean_false_alarm_pct_baseline=('false_alarm_pct_baseline', 'mean'))
           .round(2).reset_index())
    avg.to_csv(os.path.join(args.out, 'summary_average.csv'), index=False)
    with pd.option_context('display.width', 220, 'display.max_rows', 300):
        print('\n=== Average over the 6 events ===')
        print(avg.to_string(index=False))
        for rule in RULES:
            for k in (2, 3, 4):
                print(f'\n=== rule {rule}, k = {k} features at once, {PERSIST} minutes in a row ===')
                print(summary[(summary.rule == rule) & (summary.k == k)].drop(columns=['rule', 'k']).to_string(index=False))
        print('\n=== Features that fire most inside the event window (vs the rest of the day) ===')
        t = pd.DataFrame(tops)
        print(t[t.rule == args.plots[0].split(':')[0]].drop(columns='rule').to_string(index=False))

    # ---------- trade-off figure: recall vs false alarms ----------
    fig, ax = plt.subplots(figsize=(8, 6))
    for rule, marker in zip(RULES, ['o', 's', '^', 'D', 'v']):
        a = avg[avg.rule == rule]
        ax.plot(a.mean_false_alarm_pct_before, a.mean_recall, marker=marker, label=rule)
        for _, r in a.iterrows():
            ax.annotate(f"k={int(r.k)}", (r.mean_false_alarm_pct_before, r.mean_recall),
                        textcoords='offset points', xytext=(5, 3), fontsize=8)
    ax.set_xlabel('False alarms: % of normal minutes before the event (mean of 6 events)')
    ax.set_ylabel('Recall: share of the event window detected (mean of 6 events)')
    ax.set_title('Detection vs false alarms (6 events, k = features at once)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, 'tradeoff.png'), dpi=150)
    plt.close(fig)

    # ---------- timeline figures ----------
    hours = np.arange(1440) / 60
    for plot in args.plots:
        rule, k = plot.split(':')
        k = int(k)
        fig, axes = plt.subplots(len(EVENTS), 1, figsize=(16, 2.6 * len(EVENTS)), sharex=True)
        for ax, event in zip(axes, EVENTS):
            count_a, count_b, start, end = counts[(rule, event)]
            ax.axvspan(0, warmup(rule) / 60, color='lightgrey', alpha=0.5, label='warm-up (ignored)')
            ax.axvspan(start / 60, end / 60, color='tab:orange', alpha=0.2, label='published event window')
            ax.step(hours, count_b.values, where='post', color='grey', linewidth=0.8, label='baseline day')
            ax.step(hours, count_a.values, where='post', color='tab:blue', linewidth=1.0, label='event day')
            ax.axhline(k, color='black', linestyle='--', linewidth=0.8, label=f'k = {k}')
            alarm_minutes = np.where(alarms(count_a, k))[0]
            ax.plot(alarm_minutes / 60, np.full(len(alarm_minutes), -0.6), '|', color='red',
                    markersize=8, label='alarm')
            ax.set_ylim(-1.2, max(count_a.max(), count_b.max(), k) + 1)
            ax.set_ylabel('features\nfiring')
            ax.set_title(NAMES[event], loc='left', fontsize=12, fontweight='bold')
        axes[0].legend(loc='upper right', ncol=6, fontsize=9)
        axes[-1].set_xticks(range(0, 25, 2))
        axes[-1].set_xlabel('Time of day (UTC, hours)')
        fig.suptitle(f'Rule {rule}, alarm when >= {k} features fire for {PERSIST} minutes', fontsize=13)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, f'alarm_timeline_{rule}_k{k}.png'), dpi=150)
        plt.close(fig)
    print(f'\nwritten: {args.out}/summary.csv, summary_average.csv, top_features.csv, tradeoff.png, '
          f'alarm_timeline_<rule>_k<k>.png for {", ".join(args.plots)}')


if __name__ == '__main__':
    main()
