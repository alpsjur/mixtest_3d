# mixtest_3d

**Idealized 3D ROMS application for testing turbulence closure / mixing schemes.**

The project provides a fully scripted workflow for running the [ROMS](https://www.myroms.org/) ocean model in an idealized setup: building input files, running simulations, sweeping over parameter combinations, and analysing/plotting results.

---

## Overview

The physical setup is an idealized periodic channel forced by surface stress in the x-direction. The goal is to do a sensistivity testing of a parameterization that represents the effect of subgrid-scale structures (e.g. wind turbine foundations) on flow and turbulence.

### Key concepts

| Concept | Description |
|---|---|
| **GLS closure** | General turbulence closure in ROMS, configurable as k-ε, k-ω, GEN, etc. |
| **Structure area density** (`str_a`) | Frontal area per unit volume of in-water structures (m⁻¹) |
| **Structure drag** | Quadratic drag exerted by structures on the flow |
| **Structure production** | Turbulence kinetic energy produced by wakes behind structures |

---

## Repository layout

```
mixtest_3d/
├── configs/
│   ├── baseline.yaml          # Default parameter set — all runs start from here
│   └── variants/              # Per-experiment overrides (merged on top of baseline)
├── templates/
│   ├── mixtest_3d.in.j2       # Jinja2 template for the ROMS input file
│   ├── k-e_sweep.yaml         # Example sweep definition (k-epsilon variations)
│   └── gen_sweep.yaml         # Example sweep definition (GEN closure variations)
├── tools/
│   ├── prep_experiment.py     # Build input files for a single run
│   ├── run_experiment.py      # Execute a single ROMS run
│   ├── make_grd.py            # Generate the ROMS grid NetCDF
│   ├── make_ini.py            # Generate the initial conditions NetCDF
│   ├── prep_sweep.py          # Prepare a cartesian parameter sweep
│   └── run_sweep.py           # Execute all runs in a prepared sweep
├── analysis/
│   ├── plot_sweep.py          # Plot a variable across all runs in a sweep
│   └── wrapper.py             # Top-level script: compare two sweeps side by side
├── utils/
│   └── utils.py               # Shared utilities (YAML I/O, ROMS metrics, dataset loader)
├── roms/                      # ROMS executable and supporting files (do not modify)
└── environment.yml            # Conda environment specification
```

---

## Setup

### 1. Create the conda environment

```bash
conda env create -f environment.yml
conda activate mixtest_3d   # or whatever name is in the yml
```

### 2. ROMS executable

The compiled ROMS executable is expected at `roms/romsS`.  
If you need to (re-)compile ROMS, see `roms/build_roms.sh`.

---

## Workflow

### Single experiment

**Prepare** (creates `runs/<name>/` with grid, IC, and ROMS `.in` file):
```bash
python tools/prep_experiment.py configs/baseline.yaml [configs/variants/my_variant.yaml]
```

**Run:**
```bash
python tools/run_experiment.py runs/<name>/resolved_config.yaml
```

The run produces:
- `runs/<name>/output/mixtest_3d_his.nc` — ROMS history file
- `runs/<name>/logs/simulation.log` — ROMS stdout/stderr
- `runs/<name>/logs/status.yaml` — machine-readable run status

### Parameter sweep

1. Copy and edit a sweep template (e.g. `templates/k-e_sweep.yaml`) into `sweeps/`.
2. **Prepare** all runs:
   ```bash
   python tools/prep_sweep.py sweeps/my_sweep.yaml
   ```
   This creates one run directory per parameter combination and writes `sweeps/my_sweep/manifest.yaml`.
3. **Run** all prepared simulations:
   ```bash
   python tools/run_sweep.py sweeps/my_sweep/manifest.yaml
   ```
   Runs that are already marked `done` are skipped automatically.


```

### Analysis

**Time series or profile for a single run:**
```bash
python analysis/prep_timeseries.py --resolved_config runs/baseline/resolved_config.yaml --variable AKt
```

**Compare two sweeps side by side:**
```bash
python analysis/wrapper.py \
    --sweep1 sweeps/k-e_variations/manifest.yaml \
    --sweep2 sweeps/gen_variations/manifest.yaml \
    --variables AKt temp \
    --save-dir figures
```

---

## Configuration

All configuration lives in YAML files. Runs are built by **deep-merging** `baseline.yaml` with an optional variant file — the variant only needs to contain keys that differ from the baseline.

### Key config sections

| Section | Purpose |
|---|---|
| `run.name` | Name of the run directory under `runs/` |
| `grid` | Domain size (Lm, Mm, N levels), depth H0, grid spacing DX/DY |
| `vertical` | S-coordinate stretching parameters (THETA_S, THETA_B, HC) |
| `time_stepping` | NTIMES, DT (seconds), NHIS (output interval) |
| `GLS` | Turbulence closure coefficients (see ROMS manual) |
| `phys` | Coriolis F0, bottom drag RDRG2 |
| `structure` | `str_a` (area density m⁻¹), `CD` (drag coefficient), `c4` (production coefficient), `depth_zero_below` |
| `initial` | Initial temperature/salinity profile parameters |
| `files` | NetCDF file names for grid, IC, and history output |

---

## How key components fit together

```
baseline.yaml ─┐
variant.yaml  ─┴─► prep_experiment.py ──► make_grd.py  → grid NetCDF
                                      ──► make_ini.py  → IC NetCDF
                                      ──► mixtest_3d.in.j2 → ROMS input file
                                      ──► resolved_config.yaml

resolved_config.yaml ──► run_experiment.py ──► roms/romsS → history NetCDF

history NetCDF + resolved_config.yaml ──► open_roms_dataset()
                                       ──► prep_timeseries / prep_profiles
                                       ──► plot_sweep / wrapper.py
```

`utils/utils.py` is the shared foundation used by all scripts:
- `load_yaml` / `save_yaml` / `ensure_dir` — basic file I/O helpers
- `compute_stretching` / `compute_depths` — ROMS S-coordinate geometry
- `prep_ds` — attaches xgcm grid metrics (dx, dy, dz, dA, dV) to a dataset
- `open_roms_dataset` — one-call shortcut: load config → open NetCDF → prep_ds


