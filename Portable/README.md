# Portable Containers

Standalone container definitions for HPC deployments without CVMFS access.

## Structure

- **monolithic/** - Single-image containers with all dependencies bundled
  - `nest.def` - Full NEST build with UCX assertions enabled
  - **no-assertion/** - Variant without UCX assertions for stricter validation

## Building

```bash
# Standard build
apptainer build nest.sif Portable/monolithic/nest.def

# No-assertion variant
apptainer build nest-no-assert.sif Portable/monolithic/no-assertion/nest.def
```

## Usage

```bash
apptainer run nest.sif
```

## Benchmarking

See `benchmarking/slurm/` for Slurm job outputs from container performance tests.
