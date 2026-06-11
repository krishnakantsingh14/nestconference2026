# Why NEST Crashes with UCX: The `tag_recv.c:238` Assertion

A beginner-friendly explanation of a threading crash hit while running NEST 3.9
in a self-built Apptainer container (OpenMPI 5.0.5 + UCX 1.19.0) on JSC's JUSUF
cluster, using the **2 ranks × 64 threads** hybrid layout.

---

## The symptom

NEST starts fine, builds its neurons and connections, then aborts right at the
first big communication step:

```
tag_recv.c:238  Assertion `ucs_async_check_owner_thread(&(worker)->async)' failed
...
PMPI_Allgather
nest::MPIManager::communicate_Allgather
nest::ConnectionManager::compute_target_data_buffer_size
nest::SimulationManager::update_connection_infrastructure
libgomp.so.1            <-- an OpenMP thread
```

The job dies with exit code 134 (an abort).

---

## The 30-second version

NEST told MPI *"only my main thread will make MPI calls"*, but then actually made
an MPI call **from a different thread** (an OpenMP worker thread). UCX noticed,
and deliberately crashed the program to warn you.

It is **not** a broken container. It is NEST breaking a promise it made to MPI,
and UCX being honest enough to catch it.

---

## The longer version, step by step

### 1. Two kinds of parallelism at once ("hybrid")

NEST can run in parallel two ways at the same time:

- **MPI** — separate processes ("ranks"), possibly on different machines, that
  talk to each other over the network.
- **OpenMP** — multiple threads *inside* one process, sharing memory.

The "2 × 64" layout means: **2 MPI ranks**, each running **64 OpenMP threads**.
This is the layout NEST officially recommends for a dual-socket node.

### 2. MPI has thread "rules"

When a program starts MPI, it must declare *how* it intends to use threads.
It picks one of these levels:

| Level | Promise the program makes |
|---|---|
| `SINGLE` | I have only one thread. |
| **`FUNNELED`** | I have many threads, but **only the main thread will call MPI.** |
| `SERIALIZED` | Many threads may call MPI, but never two at the same time. |
| `MULTIPLE` | Any thread may call MPI, anytime. |

MPI then sets itself up based on that promise. If you promise `FUNNELED`, MPI
optimizes for "only one thread will ever touch me" and **does not** add the
extra safety locking needed for many threads.

### 3. NEST promises `FUNNELED`

NEST initializes MPI asking for the **`FUNNELED`** level. So MPI (and UCX
underneath it) builds a lightweight, single-thread "worker" — because NEST
promised only the main thread would use it.

> Think of the UCX worker like a library book checked out to *one specific
> person* (the main thread). Only that person is allowed to use it.

### 4. ...but then NEST calls MPI from an OpenMP thread

Look at the crash stack again — the bottom frame is `libgomp` (the OpenMP
runtime). That means the `MPI_Allgather` call happened **inside an OpenMP
parallel region**, on a *worker* thread, not the main thread.

That breaks the `FUNNELED` promise: a thread that wasn't supposed to call MPI
just called MPI.

### 5. UCX catches it and aborts

UCX records which thread "owns" the worker. When a *different* thread tries to
use it, this check fires:

```
ucs_async_check_owner_thread(&(worker)->async)
```

It fails, and UCX intentionally aborts the program. The assertion is a
**safety feature** — using that single-thread worker from two threads could
silently corrupt data, so UCX stops you loudly instead.

---

## Why does it work on the cluster's own MPI but not mine?

This is the surprising part. The system stacks (EESSI, ParaStation) run the
*same* NEST hybrid layout without crashing. So why does your container crash?

Because the system versions of UCX are compiled with **assertions turned off**:

```
--disable-assertions
```

The exact same illegal off-thread access happens on their stacks too — but the
check that catches it was **compiled out**, so nothing complains. The program
keeps running.

> Your container isn't worse than theirs. It's actually *stricter*: it ships
> with assertions **on**, so it tells you the truth about a bug the other stacks
> silently tolerate.

This is worth sitting with: "it works on the cluster build" does not always mean
"it's correct." Sometimes it means "the cluster build doesn't check."

---

## How to confirm it yourself

Two quick checks, no rebuild needed.

**Is UCX multi-thread capable?** (Yes — so UCX isn't the problem.)

```bash
ucx_info -b | grep -i ENABLE_MT
# #define ENABLE_MT  1
```

**Does my OpenMPI support thread-multiple?** (Yes — so OpenMPI isn't the problem.)

```bash
ompi_info | grep -i 'Thread support'
# Thread support: posix (MPI_THREAD_MULTIPLE: yes, ...)
```

Both say "yes". The capability is there. The problem is purely that **NEST asks
for `FUNNELED`**, so the worker is built single-thread no matter what the
libraries *could* do. There is no environment variable that overrides the level
an application requests at startup.

---

## Background: how OpenMPI picks a transport (and why it's UCX)

To understand why the *same NEST run* aborts on one path and not another, you need
a quick picture of how OpenMPI moves a message.

### The PML — "who carries point-to-point messages"

When NEST calls `MPI_Send` / `MPI_Allgather`, OpenMPI hands the work to a
**PML** (Point-to-point Messaging Layer). The PML is the component that actually
gets bytes from rank A to rank B. OpenMPI ships more than one, and picks **one**
at startup:

| PML | What it uses | Typical role today |
|---|---|---|
| **`ucx`** | The UCX library (RDMA, InfiniBand, shared mem) | **Default on modern HPC** |
| `ob1` | OpenMPI's own **BTL** transports (see below) | Older / fallback path |
| `cm` | A single **MTL** (e.g. OFI/libfabric, PSM2) | Vendor-fabric path |

Only one PML drives a run. You saw both in your tests:
`OMPI_MCA_pml=ucx` (crashes) vs `OMPI_MCA_pml=ob1` (completes).

### What `ob1` uses underneath — BTLs

`ob1` doesn't talk to the network directly; it loads **BTLs** (Byte Transfer
Layers), one per transport:

| BTL | Carries traffic over |
|---|---|
| `self` | A rank talking to itself (loopback) |
| `sm` / `vader` | **Shared memory** — ranks on the *same node* |
| `tcp` | Ordinary **TCP/IP** sockets (slow, but works anywhere) |
| `openib` | Legacy InfiniBand verbs (deprecated, replaced by UCX) |

So `OMPI_MCA_pml=ob1 OMPI_MCA_btl=self,sm,tcp` means: same-node messages go
through shared memory, cross-node messages go over TCP. No UCX involved.

### Why UCX is the default

OpenMPI assigns each PML a **priority**, and the highest one that successfully
initializes wins. On any cluster with InfiniBand/RoCE hardware, UCX initializes
and advertises a high priority (you can see it: `pml_ucx_priority = 51`), which
beats `ob1`. That's deliberate — UCX is preferred because it:

1. **Speaks RDMA natively** — InfiniBand / RoCE one-sided transfers, the fast
   path on HPC fabrics. `ob1`+`tcp` can't touch that performance.
2. **Auto-selects the best transport per peer** — shared memory for on-node
   ranks, `rc_mlx5`/`dc_mlx5` verbs for off-node, all transparently.
3. **Scales to many nodes** — the `dc` (Dynamically Connected) transport keeps
   connection state bounded as rank counts grow; classic verbs does not.
4. **Is the actively maintained path** — the old `openib` BTL is deprecated, so
   for IB hardware UCX is effectively *the* supported route.

In short: on JUSUF (ConnectX HCAs over InfiniBand), UCX is chosen automatically
because it's the only path that uses the fast hardware properly. `ob1` is what
you fall back to, and on this fabric its only cross-node option is TCP.

### How this connects to the crash

This is the key insight that ties the whole document together:

- The crash is **transport-specific only by accident.** The illegal off-thread
  collective happens on *every* path. UCX is simply the only one whose worker
  carries an **owner-thread assertion** that catches it.
- `ob1` "works" not because it's correct, but because its BTLs don't perform
  that check — exactly like an assertions-off UCX. Your `ob1` run printing
  *"completed WITHOUT aborting"* is the proof: same off-thread access, no guard.
- So **switching PML to dodge the crash is not a fix** — it's choosing a quieter
  transport. Worse, on this fabric `ob1` means **TCP cross-node**, which would
  cripple your benchmark and make the container look slower than the system
  stacks for reasons that have nothing to do with the real bug.

| Run with... | Behavior | Why |
|---|---|---|
| `pml=ucx` (assertions **on**) | **Aborts** at `tag_recv.c:238` | UCX worker checks owner thread |
| `pml=ucx` (assertions **off**) | Completes | Same access, check compiled out |
| `pml=ob1` | Completes | BTLs have no owner-thread check; but cross-node = TCP |
| `pml=cm` + OFI | Usually completes (provider-dependent) | Most OFI providers don't carry the check |

The takeaway: keep UCX as the PML (you *want* the fast fabric), and fix the
problem at the layer where it actually lives — the threading, not the transport.

---

## How to fix it

### Option A — Run "pure MPI" (recommended, no rebuild)

If there are no OpenMP threads, no thread can break the `FUNNELED` promise.
Use one thread per rank and more ranks instead:

- SLURM: `--ntasks-per-node=128`, one thread per rank
- In your NEST script: `nest.local_num_threads = 1`

On a 128-core node that's 128 ranks × 1 thread = 128 virtual processes — same
total parallelism, but now every MPI call genuinely comes from its rank's main
thread. Runs cleanly over UCX/InfiniBand at any number of nodes.

> Note: NEST ignores `OMP_NUM_THREADS`. You **must** set `local_num_threads`
> inside the simulation script.

### Option B — Match the cluster builds (rebuild UCX with assertions off)

If you specifically need the 2 × 64 hybrid layout (e.g. to compare fairly against
the EESSI / ParaStation stacks that use it), rebuild **only UCX** to match them:

```bash
./configure --prefix=/opt/ucx \
    --enable-mt --enable-cma \
    --with-verbs --with-rdmacm \
    --disable-assertions
```

This silences the assertion exactly the way the system stacks do. Be honest with
yourself about what this means: the off-thread access still happens — you're
just choosing to tolerate it, as the big sites implicitly do. Defensible *because*
it reproduces the reference environment, but it is not a true fix of the
underlying behavior.

### Option C — Report it upstream

The real root cause is in NEST: it issues an MPI collective from an OpenMP
thread while only having requested `FUNNELED`. That is a bug worth reporting to
the [NEST simulator project](https://github.com/nest/nest-simulator). Your
assertions-on UCX produced a cleaner reproduction than the production clusters
ever would.

---

## One-line summary

> NEST promised MPI that only its main thread would communicate (`FUNNELED`),
> then broke that promise by communicating from an OpenMP thread. Your UCX caught
> the lie and stopped. The clusters don't catch it only because they compiled the
> check out. Either stop using threads for MPI work (pure MPI), or compile the
> check out like they do.

---

## Quick reference

| Question | Answer |
|---|---|
| Is the container broken? | No. |
| Is UCX the problem? | No — it's multi-thread capable (`ENABLE_MT 1`). |
| Is OpenMPI the problem? | No — `MPI_THREAD_MULTIPLE: yes`. |
| What's the real cause? | NEST requests `FUNNELED` but calls MPI from an OpenMP thread. |
| Why no crash on EESSI/ParaStation? | Their UCX is built `--disable-assertions`. |
| Why is UCX the default transport? | Highest PML priority on IB hardware; only path that uses RDMA. |
| Why does `pml=ob1` not crash? | Its BTLs have no owner-thread check — but cross-node falls back to TCP. |
| Is switching to ob1/OFI a fix? | No — it just hides the bug on a slower transport. |
| Fastest fix? | Pure MPI: 1 thread per rank, `local_num_threads = 1`. |
| Fix for keeping 2×64 hybrid? | Rebuild UCX with `--disable-assertions`. |
| Proper long-term fix? | Report the FUNNELED violation to NEST upstream. |
