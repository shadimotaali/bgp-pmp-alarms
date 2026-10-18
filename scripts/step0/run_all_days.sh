#!/bin/bash
# ==============================================================================
# Step 0 - run pmp_sqrt_m.py for the 12 days, one day after another.
# Each day: 8 features at the same time x 4 cores each = 32 cores.
#
# Run from the repository root:
#   nohup bash scripts/step0/run_all_days.sh > results/step0/run_all_days.log 2>&1 &
# Follow progress:
#   tail -f results/step0/run_all_days.log        (Ctrl+C stops watching, not the run)
# ==============================================================================

cd "$(dirname "$0")/../.."          # repository root
PY=${PY:-python}                     # override: PY=/path/to/python bash ...
export OMP_NUM_THREADS=1

# run <feature CSV> <output folder> <date for the titles>
run() {
  echo "=== $(date '+%H:%M:%S') start $2"
  $PY -W ignore scripts/step0/pmp_sqrt_m.py --csv "$1" --out "$2" --date "$3" --jobs 8 --threads 4
}

run data/cnsm/slammer/slammer_anomaly_25jan_features_1s.csv            results/step0/slammer/anomaly_25jan           "25 Jan 2003"
run data/cnsm/slammer/slammer_baseline_18jan_features_1s.csv           results/step0/slammer/baseline_18jan          "18 Jan 2003"
run data/cnsm/codered/codered_anomaly_19jul_features_1s.csv            results/step0/codered/anomaly_19jul           "19 Jul 2001"
run data/cnsm/codered/codered_baseline_12jul_features_1s.csv           results/step0/codered/baseline_12jul          "12 Jul 2001"
run data/cnsm/moscow_blackout/moscow_blackout_25may_features_1s.csv    results/step0/moscow_blackout/anomaly_25may   "25 May 2005"
run data/cnsm/moscow_blackout/moscow_baseline_18may_features_1s.csv    results/step0/moscow_blackout/baseline_18may  "18 May 2005"
run data/cnsm/telekom_malaysia/telekom_malaysia_12jun_features_1s.csv  results/step0/telekom_malaysia/anomaly_12jun  "12 Jun 2015"
run data/cnsm/telekom_malaysia/telekom_malaysia_5jun_features_1s.csv   results/step0/telekom_malaysia/baseline_5jun  "5 Jun 2015"
run data/cnsm/nimda/nimda_anomaly_18sept_features_1s.csv               results/step0/nimda/anomaly_18sep             "18 Sep 2001"
run data/cnsm/nimda/nimda_baseline_11sept_features_1s.csv              results/step0/nimda/baseline_11sep            "11 Sep 2001"
run data/cnsm/wannacrypt/wannacrypt_anomaly_12may_features_1s.csv      results/step0/wannacrypt/anomaly_12may        "12 May 2017"
run data/cnsm/wannacrypt/wannacrypt_baseline_5may_features_1s.csv      results/step0/wannacrypt/baseline_5may        "5 May 2017"

echo "=== $(date '+%H:%M:%S') all 12 days finished"
