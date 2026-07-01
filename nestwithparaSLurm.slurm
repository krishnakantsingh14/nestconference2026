#!/bin/bash
# =============================================================================
# run_bench.sh — single-node NEST HPC benchmark using a source-built NEST.
# Sources activate.sh from your build (ParaStation or OpenMPI), not the module.
#
# Submit:  sbatch run_bench.sh
# Switch flavor: edit ACTIVATE below to point at the other build.
# =============================================================================

#SBATCH --job-name=nest-bench-para2nodes
#SBATCH --account=slns
#SBATCH --partition=batch
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=2           # 2 MPI ranks (one per socket)
#SBATCH --cpus-per-task=64            # 64 OpenMP threads per rank
#SBATCH --hint=nomultithread          # one thread per physical core
#SBATCH --time=00:30:00
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err

# --- Pick which build to benchmark -----------------------------------------
ACTIVATE="$PWD/nest_build_with_para/activate.sh"
# ACTIVATE="$PWD/nest_build_with_OpenMPI/activate.sh"

# --- Load the build's environment (modules + nest_vars.sh) -----------------
source "$ACTIVATE"

# --- Threading -------------------------------------------------------------
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}    # 64
export OMP_PROC_BIND=TRUE
export OMP_PLACES=cores

# --- Benchmark parameters (read by the modular params dict in the script) --
export NEST_NUM_THREADS=${OMP_NUM_THREADS}
export NEST_SCALE=$(( 16 * SLURM_JOB_NUM_NODES ))
export NEST_SIMTIME=1000
export NEST_PRESIMTIME=100
export NEST_RECORD=memory
export NEST_OUTDIR="$PWD/results_${SLURM_JOB_ID}"

mkdir -p "$NEST_OUTDIR"

echo "Build:  $ACTIVATE"
echo "NEST:   $(which nest 2>/dev/null || echo via-python)"
echo "Ranks=${SLURM_NTASKS}  Threads/rank=${OMP_NUM_THREADS}  VPs=$((SLURM_NTASKS * OMP_NUM_THREADS))"
echo "Scale=${NEST_SCALE}  Simtime=${NEST_SIMTIME}ms"

# --- Run -------------------------------------------------------------------
srun --cpu-bind=cores python3 nest_hpc_bench.py
