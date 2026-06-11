# Monolithic Containers

Self-contained container definitions with all dependencies bundled.

## nest.def

**Description:** Self-contained NEST build with PMIx 5.0.3 + UCX 1.19.0 + OpenMPI 5.0.5 + NEST 3.9, zen2-optimized.

**Key Points:**
- Bypasses host MPI stack
- PINS to AMD zen2 microarchitecture (EPYC 7742)
- **Note:** Will fault with "illegal instruction" on non-zen2 CPUs

**Pre-download sources** (uncomment `%files` section and download):
- PMIx 5.0.3
- UCX 1.19.0
- OpenMPI 5.0.5

## no-assertion/nest.def

Variant without UCX assertions for stricter validation scenarios.
