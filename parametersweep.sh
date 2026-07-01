#   usage: ./submit_sweep.sh <script> <tag>
#   e.g.   ./submit_sweep.sh nest_single_node.sh sys
#          ./submit_sweep.sh run_bench_cvmfs.slurm noassert
set -euo pipefail
SCRIPT=${1:?usage: $0 <script> <tag>}
TAG=${2:?usage: $0 <script> <tag>}
for N in 1 2 4 8 16 32; do
    sbatch --nodes=${N} --job-name=nest_${TAG}_n${N} "${SCRIPT}"
    echo "submitted: ${N} node(s) → nest_${TAG}_n${N}"
done
