#!/bin/bash
# =============================================================================
# run_bench_cvmfs.slurm — NEST HPC benchmark inside the CVMFS/EESSI container
# Container: monolithicNestNoUcxAssertion.sif  (EESSI stack from /cvmfs, OpenMPI + PMIx)
#
# Submit one run:   sbatch run_bench_cvmfs.slurm
# Submit a sweep:   ./submit_sweep.sh
# =============================================================================

#SBATCH --account=<>
#SBATCH --partition=batch
#SBATCH --nodes=1                     # overridden by submit_sweep.sh
#SBATCH --ntasks-per-node=2
#SBATCH --cpus-per-task=64
#SBATCH --hint=nomultithread          # one thread per physical core
#SBATCH --time=00:30:00
#SBATCH --job-name=nest_noassert_n1   # overridden by submit_sweep.sh → carries node count
#SBATCH --output=benchmarkingResults/%x_%j.out   # %x = job name (n<N>), %j = job id
#SBATCH --error=benchmarkingResults/%x_%j.err

# --- Paths -----------------------------------------------------------------
SIF="$PWD/nest_default_ucx.sif"
BENCH="$PWD/nest_hpc_bench.py"

BENCH_DIR="$( cd "$( dirname "$BENCH" )" && pwd )"
BENCH_FILE="$( basename "$BENCH" )"

# --- Threading (exported INTO the container via APPTAINERENV_) -------------
export APPTAINERENV_OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}    # 64
export APPTAINERENV_OMP_PROC_BIND=TRUE
export APPTAINERENV_OMP_PLACES=cores

# --- Benchmark parameters (read by the params dict inside the container) ----
export APPTAINERENV_NEST_NUM_THREADS=${SLURM_CPUS_PER_TASK}   # local_num_threads = 64
export APPTAINERENV_NEST_SCALE=$(( 16 * SLURM_JOB_NUM_NODES )) # WEAK scaling: 16/node held constant
export APPTAINERENV_NEST_SIMTIME=1000
export APPTAINERENV_NEST_PRESIMTIME=100
export APPTAINERENV_NEST_RECORD=memory
export APPTAINERENV_NEST_OUTDIR=/scratch/results_${SLURM_JOB_ID}

# Host output dir mapped to /scratch inside the container
HOST_OUTDIR="$PWD/results_${SLURM_JOB_ID}"
mkdir -p "$HOST_OUTDIR"

echo "Job:       $SLURM_JOB_NAME  (id $SLURM_JOB_ID)"
echo "Container: $SIF"
echo "Bench:     $BENCH_DIR/$BENCH_FILE"
echo "Nodes=${SLURM_JOB_NUM_NODES}  Ranks=${SLURM_NTASKS}  Threads/rank=${SLURM_CPUS_PER_TASK}  VPs=$((SLURM_NTASKS * SLURM_CPUS_PER_TASK))"
echo "Scale=${APPTAINERENV_NEST_SCALE} (= scale*11250 = $((APPTAINERENV_NEST_SCALE * 11250)) neurons)  Simtime=${APPTAINERENV_NEST_SIMTIME}ms"

# --- Run -------------------------------------------------------------------
srun --mpi=pspmix --cpu-bind=cores \
    apptainer exec --sharens \
        --bind "$BENCH_DIR":"$BENCH_DIR" \
        "$SIF" \
        python3 "$BENCH"
