# NEST 3.9 issues `MPI_Allgather` from an OpenMP thread under `MPI_THREAD_FUNNELED` (aborts on assertions-enabled UCX)

## Summary

In a hybrid (MPI + OpenMP) run, NEST 3.9 issues an `MPI_Allgather` from inside an
OpenMP parallel region during connection setup. NEST initializes MPI with
`MPI_THREAD_FUNNELED`, which promises that **only the main thread calls MPI**.
Calling a collective from an OpenMP worker thread violates that contract.

On an MPI/UCX stack built **with assertions enabled**, UCX detects the
non-owner-thread access to its worker and aborts the process (`SIGABRT`, exit
134). On production stacks where UCX is built `--disable-assertions` (e.g. EESSI,
ParaStation), the same off-thread access happens but is not checked, so the run
proceeds — masking what appears to be a genuine threading-contract violation.

This looks like a latent thread-safety bug rather than a problem with any
particular MPI/UCX build. Filing as a question to maintainers, since you hold the
context on why this collective is issued from within the parallel region.

## Environment

| | |
|---|---|
| NEST | 3.9 (`-Dwith-mpi=ON -Dwith-openmp=ON`) |
| MPI | OpenMPI 5.0.5 (`--with-pmix --with-ucx`), reports `MPI_THREAD_MULTIPLE: yes` |
| UCX | 1.19.0 (`--enable-mt --with-verbs --with-rdmacm`, **assertions enabled**) |
| PMIx | 5.0.3 |
| Launcher | `srun --mpi=pspmix` |
| System | JSC JUSUF, AMD EPYC 7742 (dual-socket, 128 cores), InfiniBand (ConnectX) |
| Packaging | Apptainer container, Rocky Linux base, GCC 14 |
| Layout | 2 MPI ranks × 64 OpenMP threads (`local_num_threads = 64`) |

## Steps to reproduce

1. Build NEST 3.9 with MPI + OpenMP against an MPI stack using the UCX PML, where
   UCX is compiled **with assertions** (stock `./configure` without
   `--disable-assertions`).
2. Run any hybrid configuration with ≥ 1 OpenMP thread per rank across ≥ 2 ranks,
   e.g. the standard `hpc_benchmark.py`:
   ```bash
   #SBATCH --nodes=1
   #SBATCH --ntasks-per-node=2
   #SBATCH --cpus-per-task=64
   srun --mpi=pspmix apptainer exec nest.sif python3 hpc_benchmark.py
   ```
   with `nest.local_num_threads = 64` in the script.
3. The run builds nodes and edges, then aborts at the first inter-rank collective
   in `update_connection_infrastructure`.

## Observed backtrace

Both ranks abort identically:

```text
tag_recv.c:238  Assertion `ucs_async_check_owner_thread(&(worker)->async)' failed
==== backtrace (tid: 23017) ====
 3  ucp_tag_recv_nbx                          (libucp)
 4  mca_pml_ucx_irecv                         (libmpi)
 5  ompi_coll_base_sendrecv_actual            (libmpi)
 6  ompi_coll_base_allgather_intra_two_procs  (libmpi)
 7  ompi_coll_tuned_allgather_intra_dec_fixed (libmpi)
 8  PMPI_Allgather                            (libmpi)
 9  nest::MPIManager::communicate_Allgather(std::vector<long>&)            (libnest)
10  nest::ConnectionManager::compute_target_data_buffer_size()            (libnest)
11  nest::SimulationManager::update_connection_infrastructure(unsigned long) (libnest)
13  libgomp.so.1 (+0x22318)                   <-- OpenMP runtime frame
14  libc clone / start_thread
=> Process aborted, signal 6, exit code 134
```

Two things to note in the trace:

- Frame 13 is `libgomp` — the collective runs on an **OpenMP worker thread**, not
  the process main thread.
- The aborting thread ID (`23017`) differs from the thread that created the UCX
  worker at MPI init (the main thread). UCX's owner-thread check is what fires.

## Why this appears to be a contract violation

`MPI_Init_thread` with `MPI_THREAD_FUNNELED` guarantees that only the main thread
will make MPI calls. The OpenMPI UCX PML therefore creates a **single-threaded**
UCX worker (`UCS_THREAD_MODE_SINGLE`), owned by the initializing thread. When a
different (OpenMP) thread later drives a transfer on that worker, UCX's
`ucs_async_check_owner_thread` assertion correctly flags the unsynchronized
access and aborts.

Verified that neither library lacks multi-threading capability — the
single-thread worker is purely a consequence of the requested level:

```text
ucx_info -b  | grep ENABLE_MT       ->  #define ENABLE_MT 1
ompi_info    | grep 'Thread support'->  MPI_THREAD_MULTIPLE: yes, OPAL support: yes
```

So the worker could have been multi-thread-safe had a higher level been
requested; with `FUNNELED` it is not, and calling the collective off-thread is
outside the contract.

## Minimal reproducer (no NEST)

This ~30-line program emits the same backtrace, confirming the issue is the
threading pattern (FUNNELED + off-thread collective), not anything NEST-specific:

```c
/* mpicc -fopenmp -O2 funneled_offthread.c -o funneled_offthread
 * OMPI_MCA_pml=ucx mpirun -np 2 ./funneled_offthread   (UCX built WITH assertions) */
#include <mpi.h>
#include <omp.h>
#include <stdlib.h>
#include <stdio.h>

int main(int argc, char **argv) {
    int provided;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);  /* as NEST */
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    int s = rank, *r = malloc(size * sizeof(int));
    #pragma omp parallel num_threads(2)
    {
        if (omp_get_thread_num() == 1)                       /* NOT the main thread */
            MPI_Allgather(&s, 1, MPI_INT, r, 1, MPI_INT, MPI_COMM_WORLD);
    }
    if (rank == 0) printf("completed without abort\n");
    free(r); MPI_Finalize(); return 0;
}
```

Behavior across transports (same off-thread access in every case):

| Configuration | Result |
|---|---|
| UCX PML, assertions **enabled** | aborts at `tag_recv.c:238` |
| UCX PML, assertions **disabled** (EESSI / ParaStation) | completes (unchecked) |
| `OMPI_MCA_pml=ob1` | completes (BTLs have no owner-thread check) |

## Questions for maintainers

1. Is the `MPI_Allgather` in `compute_target_data_buffer_size` /
   `update_connection_infrastructure` intended to run inside the OpenMP parallel
   region, or should it be funneled to the main thread to honor the declared
   `MPI_THREAD_FUNNELED` level?
2. If off-thread MPI is intentional here, should `MPIManager` request a higher
   thread level (`SERIALIZED` / `MULTIPLE`) — with the corresponding guarantee
   that the collective is never issued concurrently on the same communicator?
3. Is there a known reason NEST pins `FUNNELED` (e.g. performance on stacks where
   raising the level adds locking)?

## Notes

- Not asking to special-case any MPI stack. The assertions-enabled build simply
  surfaces a latent issue that assertions-disabled production builds tolerate
  silently. The off-thread access is present on all of them.
- A naive `FUNNELED → MULTIPLE` change would silence the abort but is not
  obviously safe on its own, since MPI forbids concurrent collectives on a single
  communicator regardless of thread level. Hence filing as a question rather than
  a PR.

## Workaround (for anyone hitting this)

Run pure-MPI — one thread per rank — so no non-main thread exists to issue the
collective:

```python
nest.local_num_threads = 1   # NEST ignores OMP_NUM_THREADS
```
```bash
#SBATCH --ntasks-per-node=128
#SBATCH --cpus-per-task=1
```

This honors the `FUNNELED` contract and runs cleanly over UCX/InfiniBand at any
node count, with the same total virtual-process count as the hybrid layout.
