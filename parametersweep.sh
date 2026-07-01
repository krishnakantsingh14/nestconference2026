#!/bin/bash
# submit_sweep.sh — weak-scaling node sweep for the NEST CVMFS benchmark
set -euo pipefail

SCRIPT=run_bench_cvmfs.slurm
mkdir -p benchmarkingResults

for N in 2 4 8 16 32; do
    sbatch \
        --nodes=${N} \
        --job-name=nest_noassert_n${N} \
        "${SCRIPT}"
    echo "submitted: ${N} node(s) → nest_noassert_n${N}"
done
