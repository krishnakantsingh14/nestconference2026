# HPC Container Recipes

Container definitions for High-Performance Computing environments, primarily for NEST neural simulation software.

## Structure

- **CVMFS/** - Container definitions for CernVM-FS distributed filesystem deployment
- **Portable/** - Standalone container definitions for portable HPC deployments
  - **monolithic/** - Single-image containers
    - `nest.def` - Full NEST build with UCX assertions enabled
    - **no-assertion/** - Variant without UCX assertions for stricter validation
  - **benchmarking/slurm/** - Slurm job outputs from container performance tests

## Usage

Build with Singularity/Apptainer:
```bash
singularity build nest.sif CVMFS/nestzen2.def
singularity build nest.sif Portable/monolithic/nest.def
```
