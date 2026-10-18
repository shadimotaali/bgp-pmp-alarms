#!/bin/bash
# ==============================================================================
# Before / after figures (Step 0 vs corrected, 2D and 3D) for all features of the 12 days.
# Reads the saved .npz matrices only; nothing is recomputed (about 10 minutes).
#
# Run from the repository root:
#   nohup bash scripts/correction_b/run_before_after.sh > results/corrected/run_before_after.log 2>&1 &
# Output: results/corrected/<event>/<day>/before_after/<feature>.png and .html
# ==============================================================================

cd "$(dirname "$0")/../.."          # repository root
PY=${PY:-python}                     # override: PY=/path/to/python bash ...

# before_after <event/day> <date for the titles>
before_after() {
  echo "=== $(date '+%H:%M:%S') $1"
  $PY -W ignore scripts/correction_b/before_after.py --day "$1" --date "$2" --jobs 8
}

before_after slammer/anomaly_25jan           "25 Jan 2003"
before_after slammer/baseline_18jan          "18 Jan 2003"
before_after codered/anomaly_19jul           "19 Jul 2001"
before_after codered/baseline_12jul          "12 Jul 2001"
before_after moscow_blackout/anomaly_25may   "25 May 2005"
before_after moscow_blackout/baseline_18may  "18 May 2005"
before_after telekom_malaysia/anomaly_12jun  "12 Jun 2015"
before_after telekom_malaysia/baseline_5jun  "5 Jun 2015"
before_after nimda/anomaly_18sep             "18 Sep 2001"
before_after nimda/baseline_11sep            "11 Sep 2001"
before_after wannacrypt/anomaly_12may        "12 May 2017"
before_after wannacrypt/baseline_5may        "5 May 2017"

echo "=== $(date '+%H:%M:%S') all finished"
