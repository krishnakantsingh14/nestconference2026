# NEST 3.9 — Off-Thread MPI Collective Under `MPI_THREAD_FUNNELED`

**Technical report.** A reproducible abort in NEST 3.9's hybrid (MPI + OpenMP)
execution, surfaced by an assertions-enabled UCX build. The root cause is an MPI
thread-safety contract violation in NEST, not a defect in the MPI/UCX stack.

| | |
|---|---|
| **Component** | NEST 3.9 (`libnest.so`) |
| **Trigger** | Hybrid run, ≥1 OpenMP thread per rank, UCX PML, assertions enabled |
| **Observed on** | JSC JUSUF (AMD EPYC 7742), Apptainer container, OpenMPI 5.0.5 + UCX 1.19.0 + PMIx 5.0.3 |
| **Failure mode** | `SIGABRT` (exit 134) at first inter-rank collective in connection setup |
| **Severity** | Latent data race on stacks that do *not* abort; hard failure on stacks that do |
| **Status** | Worked around (run-time); not yet fixed upstream |

---

## 1. Summary

NEST initializes MPI requesting `MPI_THREAD_FUNNELED`, which is a promise that
**only the main thread issues MPI calls**. During
`SimulationManager::update_connection_infrastructure`, NEST issues an
`MPI_Allgather` from inside an OpenMP parallel region — i.e. from a non-main
thread. This violates the FUNNELED contract.

With the UCX PML, OpenMPI creates a single-threaded UCX worker owned by the
initializing (main) thread. When a different thread drives a transfer on that
worker, UCX's owner-thread assertion fires and aborts the process. Stacks built
with `--disable-assertions` (EESSI, ParaStation) do not abort — the same illegal
access occurs but is unchecked.

---

## 2. Environment

| Layer | Version / config |
|---|---|
| Cluster | JSC JUSUF, AMD EPYC 7742 (dual-socket, 128 cores), Mellanox/NVIDIA ConnectX (`mlx5_0:1`, `mlx5_1:1`), InfiniBand |
| Container | Apptainer, Rocky Linux base |
| Compiler | GCC 14 |
| PMIx | 5.0.3 |
| UCX | 1.19.0 — `--enable-mt --with-verbs --with-rdmacm` (**assertions enabled**) |
| OpenMPI | 5.0.5 — `--with-pmix --with-ucx`; reports `MPI_THREAD_MULTIPLE: yes` |
| NEST | 3.9, `-Dwith-mpi=ON -Dwith-openmp=ON` |
| Layout | 2 MPI ranks × 64 OpenMP threads = 128 virtual processes |
| Launch | `srun --mpi=pspmix` |

Relevant capability facts (all verified, all *not* the cause):

```text
ucx_info -b | grep ENABLE_MT      ->  #define ENABLE_MT 1
ompi_info | grep 'Thread support' ->  MPI_THREAD_MULTIPLE: yes, OPAL support: yes
```

Both the UCX library and the OpenMPI build are fully multi-thread capable. The
single-threaded worker is a *consequence of the requested thread level*, not of
a missing capability.

---

## 3. Observed failure

```text
tag_recv.c:238  Assertion `ucs_async_check_owner_thread(&(worker)->async)' failed
==== backtrace (tid: 22324) ====
  ucp_tag_recv_nbx                          (libucp)
  mca_pml_ucx_irecv                         (libmpi)
  ompi_coll_base_sendrecv_actual            (libmpi)
  ompi_coll_base_allgather_intra_two_procs  (libmpi)
  ompi_coll_tuned_allgather_intra_dec_fixed (libmpi)
  PMPI_Allgather                            (libmpi)
  nest::MPIManager::communicate_Allgather                       (libnest)
  nest::ConnectionManager::compute_target_data_buffer_size      (libnest)
  nest::SimulationManager::update_connection_infrastructure     (libnest)
  libgomp.so.1 (+0x22318)                   <-- OpenMP runtime frame
  libc clone/start_thread
=> Process aborted, signal 6, exit code 134
```

Two diagnostic signals in the trace:

1. **`libgomp` is on the stack below NEST.** The collective executes on a thread
   spawned by the OpenMP runtime — a worker thread, not the process main thread.
2. **The thread ID differs from the worker's owner.** The UCX worker was created
   on the main thread during MPI init; the aborting TID is a different thread.

The abort occurs at the *first* inter-rank collective after node/edge
construction completes — earlier purely local phases run fine, consistent with
the fault being communication-path-specific.

---

## 4. Root-cause analysis

### 4.1 The MPI threading contract

`MPI_Init_thread` negotiates a thread-support level. The relevant ones:

| Level | Application guarantee |
|---|---|
| `MPI_THREAD_SINGLE` | One thread total. |
| `MPI_THREAD_FUNNELED` | Multi-threaded, but **only the main thread calls MPI**. |
| `MPI_THREAD_SERIALIZED` | Multiple threads may call MPI, never concurrently. |
| `MPI_THREAD_MULTIPLE` | Any thread may call MPI at any time. |

NEST requests `FUNNELED`. The provided level returned at init is `FUNNELED`.

### 4.2 How the UCX worker is sized

OpenMPI's `pml_ucx` creates the UCX worker with a thread mode derived from the
requested MPI thread level:

- `FUNNELED` / `SINGLE` → `UCS_THREAD_MODE_SINGLE` (single-thread worker, owner =
  initializing thread).
- `MULTIPLE` → `UCS_THREAD_MODE_MULTI` (thread-safe worker).

Because NEST asks for `FUNNELED`, the worker is single-thread regardless of the
fact that both UCX (`ENABLE_MT 1`) and OpenMPI (`MPI_THREAD_MULTIPLE: yes`) could
support a multi-thread worker. **No environment variable or MCA parameter
overrides this** — it is fixed by the level the application passes at init.

### 4.3 The violation

NEST then issues `MPI_Allgather` from an OpenMP worker thread inside
`update_connection_infrastructure`. That worker thread drives `ucp_tag_recv_nbx`
on a worker it does not own. UCX validates ownership:

```c
ucs_async_check_owner_thread(&(worker)->async)   /* tag_recv.c:238 */
```

The check fails → `ucs_fatal_error` → `abort()`.

### 4.4 Why it is a real bug, not over-strict checking

The owner-thread assertion protects against concurrent/unsynchronized access to
a non-thread-safe object. Using a `SINGLE`-mode worker from multiple threads can
corrupt internal request/queue state silently. The assertion converts a latent
race into a deterministic, diagnosable abort. The defect is that NEST drives MPI
off the main thread after promising it would not.

---

## 5. Why production stacks (EESSI, ParaStation) do not abort

The system UCX builds disable assertions:

```text
EESSI 1.19.0:       ... --enable-mt --enable-cma --disable-assertions
                        --disable-params-check --disable-debug --disable-logging ...
ParaStation:        ... --enable-mt --enable-cma --disable-assertions
                        --disable-params-check ...
```

With `--disable-assertions`, `ucs_async_check_owner_thread` is compiled out. The
identical off-thread access still happens; nothing reports it. The simulation
proceeds and, in practice, has not been observed to produce incorrect results —
but this is **tolerance, not correctness**. The container build differs only in
keeping assertions enabled, which is why it alone surfaces the latent issue.

> This is an instance of a general HPC hazard: "passes on the production build"
> can mean "the production build does not check," not "the code is correct."

---

## 6. Minimal reproducer

NEST is not required. The following ~60-line program reproduces the identical
backtrace.

```c
/* funneled_offthread.c
 * Build: mpicc -fopenmp -O2 funneled_offthread.c -o funneled_offthread
 * Run:   OMPI_MCA_pml=ucx OMP_NUM_THREADS=4 mpirun -np 2 ./funneled_offthread
 *        (or: srun --mpi=pspmix -n 2 ./funneled_offthread)
 * -np 2 matches NEST's two-rank allgather path (allgather_intra_two_procs).
 */
#include <mpi.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    int provided = 0;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);  /* as NEST */

    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    int sendval = rank;
    int *recv = malloc((size_t)size * sizeof(int));

    #pragma omp parallel num_threads(2)
    {
        if (omp_get_thread_num() == 1) {           /* worker thread, NOT owner */
            MPI_Allgather(&sendval, 1, MPI_INT, recv, 1, MPI_INT, MPI_COMM_WORLD);
        }
    }
    /* assertions-ON UCX never reaches here */

    if (rank == 0) printf("completed without abort\n");
    free(recv);
    MPI_Finalize();
    return 0;
}
```

### Behavior matrix

| Configuration | Result | Interpretation |
|---|---|---|
| UCX PML, assertions **on** (container) | **abort** at `tag_recv.c:238` | violation detected |
| UCX PML, assertions **off** (EESSI/ParaStation) | completes | violation unchecked |
| `OMPI_MCA_pml=ob1` (any) | completes | BTLs have no owner-thread check |
| `OMPI_MCA_pml=cm` + OFI | completes (provider-dependent) | most OFI providers do not check |

The matrix demonstrates the fault is application-level: changing the transport
changes only *whether the violation is detected*, never *whether it occurs*.

---

## 7. Impact

- **Single node:** intra-node ranks communicate via shared memory; the UCX
  worker path may not be exercised the same way, so the abort can be absent. The
  2×64 layout on one node typically runs.
- **Multi-node:** inter-rank collectives traverse the InfiniBand fabric through
  the UCX worker. The off-thread access is then on the critical path, so the
  abort (assertions on) or the latent race (assertions off) is present at every
  node count in a scaling sweep (2, 8, 16, …).
- **Benchmarking risk:** working around it by forcing `ob1`/OFI moves cross-node
  traffic to TCP (no RDMA), which depresses performance for reasons unrelated to
  the bug and invalidates a fair comparison against RDMA-based system stacks.

---

## 8. Workarounds and fixes

Ordered from least to most invasive. (1) is recommended for correctness; (2) for
reproducing the reference-stack behavior in a benchmark.

### 8.1 (Recommended) Pure-MPI layout — no rebuild

Eliminate the OpenMP region so no thread other than the main thread exists to
call MPI. The FUNNELED contract then holds.

```bash
#SBATCH --ntasks-per-node=128      # one rank per core
#SBATCH --cpus-per-task=1
```
```python
nest.local_num_threads = 1          # NEST ignores OMP_NUM_THREADS
```

Total parallelism is unchanged (128 virtual processes on a 128-core node), runs
cleanly over UCX/IB at all node counts, and is the only listed option that is
*correct* rather than *tolerant*. Trade-off: abandons the NEST-recommended
hybrid layout.

### 8.2 Match the reference stacks — rebuild UCX with assertions off

```bash
./configure --prefix=/opt/ucx \
    --enable-mt --enable-cma --enable-optimizations \
    --with-verbs --with-rdmacm \
    --disable-assertions --disable-params-check --disable-debug --disable-logging
```

Reproduces EESSI/ParaStation behavior exactly; the 2×64 hybrid layout then runs.
Defensible **only** as "matching the reference environment for comparison." The
off-thread access still occurs; this suppresses the detector, not the cause. Keep
an assertions-enabled build for diagnostics.

Verify:
```bash
/opt/ucx/bin/ucx_info -b | grep CONFIGURE_FLAGS   # must contain --disable-assertions
```

### 8.3 (Upstream, non-trivial) Fix the threading in NEST

Two correct directions, both source-level:

- **Funnel the collective to the main thread.** Hoist the `Allgather` in
  `update_connection_infrastructure` / `compute_target_data_buffer_size` out of
  the OpenMP parallel region so it executes on the main thread, honoring the
  declared FUNNELED level. Preferred; matches the existing contract.
- **Raise the requested thread level** to `SERIALIZED` or `MULTIPLE` in
  `MPIManager` **and** prove the collective is never issued concurrently on the
  same communicator from multiple threads (MPI forbids concurrent collectives on
  one communicator regardless of level). More invasive; risks added locking
  overhead on the benchmarked communication path.

> The naive one-line change (FUNNELED → MULTIPLE) is **not** a safe fix on its
> own: it removes the assertion without establishing that the access is actually
> serialized, converting a deterministic abort into a potential silent race.

---

## 9. Recommended actions

1. **Benchmarking:** use 8.2 to match EESSI/ParaStation, ensuring all three
   stacks share NEST build flags, layout, and pinning so any delta is
   attributable to the MPI stack rather than the compiler or transport.
2. **Correctness baseline:** keep an 8.1 (pure-MPI) run as the
   contract-honoring reference.
3. **Upstream:** report to `nest/nest-simulator` with the §6 reproducer, the §3
   backtrace, and the §5 assertions observation — framed as a question to
   maintainers on whether the connection-setup collective should be
   main-thread-only, since they hold the context on why it is issued from within
   the parallel region.

---

## 10. References (verify before citing)

- NEST threading documentation — hybrid MPI+OpenMP guidance, "one thread per
  core" recommendation.
- MPI standard — `MPI_Init_thread`, thread-support levels.
- UCX — `ucs_async_check_owner_thread`, worker thread modes
  (`UCS_THREAD_MODE_SINGLE` / `MULTI`).
- OpenMPI `pml_ucx` — worker creation and thread-mode selection.

---

*Prepared from first-hand debugging of a NEST 3.9 + OpenMPI 5.0.5 + UCX 1.19.0
Apptainer container on JSC JUSUF. The §6 reproducer was confirmed to emit the
§3 backtrace under the assertions-enabled UCX build, and to complete cleanly
under `ob1`.*
