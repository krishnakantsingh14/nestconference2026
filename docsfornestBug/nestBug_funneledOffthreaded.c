/*
 * funneled_offthread.c
 * --------------------------------------------------------------------------
 * Minimal reproducer for the UCX `tag_recv.c:238` owner-thread assertion that
 * NEST 3.9 triggers in its 2-rank x N-thread hybrid layout.
 *
 * It does exactly what NEST does wrong, with no NEST involved:
 *
 *   1. Initialize MPI requesting only MPI_THREAD_FUNNELED.
 *      (FUNNELED = "I have many threads, but ONLY the main thread calls MPI".)
 *      OpenMPI's UCX PML therefore builds a SINGLE-THREAD ucx worker, owned by
 *      the main thread.
 *
 *   2. Enter an OpenMP parallel region and issue an MPI_Allgather from a
 *      *worker* thread (NOT the main thread) — breaking the FUNNELED promise.
 *
 *   3. UCX notices a non-owner thread is using the worker and aborts:
 *        tag_recv.c:238  Assertion
 *        `ucs_async_check_owner_thread(&(worker)->async)' failed
 *
 * EXPECTED RESULTS (the whole point of the reproducer):
 *
 *   - Container UCX built WITH assertions  -> ABORTS (exit 134). Bug exposed.
 *   - EESSI / ParaStation UCX (--disable-assertions) -> runs to completion.
 *       Same illegal access happens; the check was compiled out, so it's silent.
 *   - Non-UCX path (OMPI_MCA_pml=ob1)      -> runs to completion (no UCX worker).
 *
 * So this file also doubles as a litmus test: run it on any stack and it tells
 * you whether that stack's UCX checks the FUNNELED contract or ignores it.
 *
 * --------------------------------------------------------------------------
 * BUILD:
 *   mpicc -fopenmp -O2 funneled_offthread.c -o funneled_offthread
 *
 * RUN (force UCX so it matches NEST's transport):
 *   export OMPI_MCA_pml=ucx
 *   export OMP_NUM_THREADS=4
 *   mpirun -np 2 ./funneled_offthread
 *     # or under Slurm:
 *   srun --mpi=pspmix -n 2 ./funneled_offthread
 *
 * Use -np 2 to match NEST's crash path: the stack shows
 * `ompi_coll_base_allgather_intra_two_procs`, the 2-rank allgather algorithm.
 * --------------------------------------------------------------------------
 */

#include <mpi.h>
#include <omp.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    /* 1. Request FUNNELED — exactly what NEST's MPIManager does. */
    int provided = 0;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);

    int rank = 0, size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    if (rank == 0) {
        const char *level =
            provided == MPI_THREAD_SINGLE     ? "SINGLE"     :
            provided == MPI_THREAD_FUNNELED   ? "FUNNELED"   :
            provided == MPI_THREAD_SERIALIZED ? "SERIALIZED" :
            provided == MPI_THREAD_MULTIPLE   ? "MULTIPLE"   : "UNKNOWN";
        printf("MPI provided thread level: %s\n", level);
        printf("Ranks: %d   OMP threads/rank: %d\n", size, omp_get_max_threads());
        printf("Issuing MPI_Allgather from a NON-main OpenMP thread...\n");
        fflush(stdout);
    }

    /* A do-an-Allgather payload: each rank contributes its rank id. */
    int sendval = rank;
    int *recvbuf = (int *) malloc((size_t) size * sizeof(int));
    if (!recvbuf) { MPI_Abort(MPI_COMM_WORLD, 1); }

    /*
     * 2. Make the collective come from a worker thread, not the main thread.
     *
     * Every rank must call Allgather exactly once (it's collective), so we let
     * exactly ONE thread per rank issue it — and we deliberately pick thread 1
     * (a worker), never thread 0 (the main/owner thread). That single choice is
     * the entire bug: the call leaves the thread that owns the UCX worker.
     */
    #pragma omp parallel num_threads(2)
    {
        int tid = omp_get_thread_num();
        if (tid == 1) {                       /* worker thread, NOT the owner */
            MPI_Allgather(&sendval, 1, MPI_INT,
                          recvbuf,  1, MPI_INT,
                          MPI_COMM_WORLD);
        }
    }
    /* ^ On assertions-ON UCX, execution never reaches past here. */

    if (rank == 0) {
        printf("Allgather completed WITHOUT aborting.\n");
        printf("=> This UCX does NOT enforce the owner-thread check "
               "(assertions compiled out), or PML is not UCX.\n");
        printf("recvbuf:");
        for (int i = 0; i < size; ++i) printf(" %d", recvbuf[i]);
        printf("\n");
        fflush(stdout);
    }

    free(recvbuf);
    MPI_Finalize();
    return 0;
}
