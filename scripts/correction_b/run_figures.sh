#!/bin/bash
# ==============================================================================
# All figures for the corrected matrices (E1 end-alignment + E2 fixes) in results/corrected,
# the same set as in results/step0, so both can be compared side by side.
# Reads the saved .npz matrices only; nothing is recomputed (about 30 minutes in total).
#
#   Part 1: per feature original/ normalised/ 3d/   (redraw_figures.py, as pmp_sqrt_m.py drew them)
#   Part 2: per feature 2d_3d/                      (feature_2d_3d.py)
#   Part 3: event overviews at 1s, 10min, 30min     (event_overview.py --root results/corrected)
#
# Run from the repository root:
#   nohup bash scripts/correction_b/run_figures.sh > results/corrected/run_figures.log 2>&1 &
# Follow progress:
#   tail -f results/corrected/run_figures.log        (Ctrl+C stops watching, not the run)
# ==============================================================================

cd "$(dirname "$0")/../.."          # repository root
PY=${PY:-python}                     # override: PY=/path/to/python bash ...
ROOT=results/corrected

# ---------- Parts 1 and 2: per feature ----------
# day_figures <event/day> <date for the titles>
day_figures() {
  echo "=== $(date '+%H:%M:%S') per feature $1"
  $PY -W ignore scripts/correction_b/redraw_figures.py --day "$ROOT/$1" --date "$2 - corrected" --jobs 8
  $PY -W ignore scripts/step0/feature_2d_3d.py         --day "$ROOT/$1" --date "$2 - corrected" --jobs 8
}

day_figures slammer/anomaly_25jan           "25 Jan 2003"
day_figures slammer/baseline_18jan          "18 Jan 2003"
day_figures codered/anomaly_19jul           "19 Jul 2001"
day_figures codered/baseline_12jul          "12 Jul 2001"
day_figures moscow_blackout/anomaly_25may   "25 May 2005"
day_figures moscow_blackout/baseline_18may  "18 May 2005"
day_figures telekom_malaysia/anomaly_12jun  "12 Jun 2015"
day_figures telekom_malaysia/baseline_5jun  "5 Jun 2015"
day_figures nimda/anomaly_18sep             "18 Sep 2001"
day_figures nimda/baseline_11sep            "11 Sep 2001"
day_figures wannacrypt/anomaly_12may        "12 May 2017"
day_figures wannacrypt/baseline_5may        "5 May 2017"

# ---------- Part 3: event overviews ----------
# overview <event> <anomaly day folder> <baseline day folder> <times to mark ...>
overview() {
  event=$1; anomaly=$2; baseline=$3; shift 3
  for block in 1s 10min 30min; do
    echo "=== $(date '+%H:%M:%S') overview $event $block"
    $PY -W ignore scripts/step0/event_overview.py --root "$ROOT" --event "$event" --anomaly "$anomaly" \
        --baseline "$baseline" --block "$block" --mark "$@"
  done
}

overview slammer          anomaly_25jan  baseline_18jan  05:31
overview codered          anomaly_19jul  baseline_12jul  11:00 16:30
overview moscow_blackout  anomaly_25may  baseline_18may  04:30 07:30
overview telekom_malaysia anomaly_12jun  baseline_5jun   08:43 11:15
overview nimda            anomaly_18sep  baseline_11sep  13:19 19:00
overview wannacrypt       anomaly_12may  baseline_5may   04:30 07:44

echo "=== $(date '+%H:%M:%S') all finished"
