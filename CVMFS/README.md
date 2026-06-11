# CVMFS Container Definition

**File:** `nestzen2.def`

**Description:** NEST 3.9 built against EESSI 2025.06 (GCC 14.3.0, OpenMPI 5.0.8 + PMIx) using CernVM-FS for software distribution.

## Key Features

- Uses CVMFS to access EESSI software stack at `/cvmfs/software.eessi.io/`
- Bootstrap from Rocky Linux 9
- Requires `--bind /cvmfs:/cvmfs` at build time

## Building

```bash
apptainer build nest.sif nestzen2.def
# If CVMFS not visible, bind mount:
apptainer build --fakeroot --bind /cvmfs:/cvmfs nest.sif nestzen2.def
```

## Usage

```bash
apptainer run --bind /cvmfs:/cvmfs nest.sif
```
