#!/bin/bash
# ==============================================================================
# Step 0 - all 2D + 3D figures from the saved .npz matrices (nothing is recomputed)
#
# Part 1: event overview (all features of one event: 2D left, 3D right) for the 6 events,
#         at 3 time resolutions: 1s (the CNSM resolution), 10min, 30min (same blocks as
#         compare_days.py / step0_analysis.md)
#         -> results/step0/<event>/overview_<event>_<resolution>.png
#            results/step0/<event>/overview_<event>_<resolution>_3d.html
# Part 2: per feature, 2D and 3D of the normalised PMP in one figure, for the 12 days
#         -> results/step0/<event>/<day>/2d_3d/<feature>.png and .html
#
# Takes about 15 minutes. Run from the repository root:
#   nohup bash scripts/step0/run_overviews.sh > results/step0/run_overviews.log 2>&1 &
# Follow progress:
#   tail -f results/step0/run_overviews.log        (Ctrl+C stops watching, not the run)
# ==============================================================================

cd "$(dirname "$0")/../.."          # repository root
PY=${PY:-python}                     # override: PY=/path/to/python bash ...

# ---------- Part 1: event overviews ----------
# overview <event> <anomaly day folder> <baseline day folder> <times to mark ...>
overview() {
  event=$1; anomaly=$2; baseline=$3; shift 3
  for block in 1s 10min 30min; do
    echo "=== $(date '+%H:%M:%S') overview $event $block"
    $PY -W ignore scripts/step0/event_overview.py --event "$event" --anomaly "$anomaly" --baseline "$baseline" \
        --block "$block" --mark "$@"
  done
}

overview slammer          anomaly_25jan  baseline_18jan  05:31
overview codered          anomaly_19jul  baseline_12jul  11:00 16:30
overview moscow_blackout  anomaly_25may  baseline_18may  04:30 07:30
overview telekom_malaysia anomaly_12jun  baseline_5jun   08:43 11:15
overview nimda            anomaly_18sep  baseline_11sep  13:19 19:00
overview wannacrypt       anomaly_12may  baseline_5may   04:30 07:44

# ---------- Part 2: per feature 2D + 3D ----------
# feature_figures <day folder> <date for the titles>
feature_figures() {
  echo "=== $(date '+%H:%M:%S') 2D+3D per feature $1"
  $PY -W ignore scripts/step0/feature_2d_3d.py --day "$1" --date "$2" --jobs 8
}

feature_figures results/step0/slammer/anomaly_25jan           "25 Jan 2003"
feature_figures results/step0/slammer/baseline_18jan          "18 Jan 2003"
feature_figures results/step0/codered/anomaly_19jul           "19 Jul 2001"
feature_figures results/step0/codered/baseline_12jul          "12 Jul 2001"
feature_figures results/step0/moscow_blackout/anomaly_25may   "25 May 2005"
feature_figures results/step0/moscow_blackout/baseline_18may  "18 May 2005"
feature_figures results/step0/telekom_malaysia/anomaly_12jun  "12 Jun 2015"
feature_figures results/step0/telekom_malaysia/baseline_5jun  "5 Jun 2015"
feature_figures results/step0/nimda/anomaly_18sep             "18 Sep 2001"
feature_figures results/step0/nimda/baseline_11sep            "11 Sep 2001"
feature_figures results/step0/wannacrypt/anomaly_12may        "12 May 2017"
feature_figures results/step0/wannacrypt/baseline_5may        "5 May 2017"

echo "=== $(date '+%H:%M:%S') all finished"
