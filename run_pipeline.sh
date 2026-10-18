#!/bin/bash
# ==============================================================================
# Full pipeline: 12 feature CSVs (data/cnsm) -> Pan Matrix Profiles -> corrections -> alarms -> figures
#
#   bash run_pipeline.sh                 (uses "python"; or: PY=/path/to/python bash run_pipeline.sh)
#
# Step 1 is the heavy one: 12 days x 27 features, 8 features in parallel x 4 cores each
# (about 2.5 h on 32 cores). All later steps take minutes and only read saved results.
# ==============================================================================
set -e
cd "$(dirname "$0")"
export PY=${PY:-python}
export OMP_NUM_THREADS=1

echo "=== 1/6 Pan Matrix Profile for 12 days x 27 features -> results/step0"
bash scripts/step0/run_all_days.sh

echo "=== 2/6 end-alignment (each value at the end of its window) -> results/corrected"
$PY scripts/correction_b/end_align.py

echo "=== 3/6 recompute where needed: all-zero windows of fractional features, data gaps -> results/e2"
$PY -W ignore scripts/e2/fix_recompute.py --jobs 8 --threads 4

echo "=== 4/6 end-align the recomputed matrices into results/corrected"
$PY scripts/correction_b/end_align.py --src results/e2 --dst results/corrected

echo "=== 5/6 alarm rules and evaluation against the published event windows -> results/e3"
$PY scripts/e3/threshold_rule.py

echo "=== 6/6 figures -> results/poster"
$PY -W ignore scripts/poster/figures.py

echo "=== done"
