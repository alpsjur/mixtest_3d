#!/usr/bin/env python3
"""
tools/make_clm.py

Create a ROMS-compatible climatology NetCDF using a resolved config dict.

This version writes a simple stationary climatology with:
  - temp
  - u
  - v

It is intended for use with:
  - tracer nudging (LnudgeTCLM)
  - 3D momentum nudging (LnudgeM3CLM)

and without direct 2D/barotropic nudging.

Preferred usage (from orchestrator):
    from tools.make_clm import make_clm_from_config
    clm_path = make_clm_from_config(cfg_dict)

CLI fallback:
    python tools/make_clm.py path/to/config.yaml
"""

import os
import sys
import numpy as np
import netCDF4 as nc
import yaml
from utils.utils import compute_z_r
from tools.make_ini import temp_initial, u_initial, v_initial


# ---------------------------------------------------------------------------
# Climatology profile functions
# ---------------------------------------------------------------------------

# currently, initial profiles are used




# ---------------------------------------------------------------------------
# Main climatology file creation function
# ---------------------------------------------------------------------------

def make_clm_from_config(cfg: dict) -> str:
    """
    Create the climatology file using values from a resolved config dict.
    """
    input_dir = cfg["io"]["input_dir"]
    grd_name = cfg["files"]["grd"]
    clm_name = cfg["files"]["clm"]

    grd_path = os.path.join(input_dir, grd_name)
    clm_path = os.path.join(input_dir, clm_name)
    os.makedirs(os.path.dirname(clm_path) or ".", exist_ok=True)

    # Read required config values
    N = int(cfg["grid"]["N"])

    Vtransform = int(cfg["vertical"]["Vtransform"])
    Vstretching = int(cfg["vertical"]["Vstretching"])
    THETA_S = float(cfg["vertical"]["THETA_S"])
    THETA_B = float(cfg["vertical"]["THETA_B"])
    HC = float(cfg["vertical"]["HC"])

    clm_time_days = 0.0

    # Read grid geometry
    with nc.Dataset(grd_path, "r") as grd:
        h = grd.variables["h"][:]

        xi_rho = len(grd.dimensions["xi_rho"])
        eta_rho = len(grd.dimensions["eta_rho"])
        xi_u = len(grd.dimensions["xi_u"])
        eta_u = len(grd.dimensions["eta_u"])
        xi_v = len(grd.dimensions["xi_v"])
        eta_v = len(grd.dimensions["eta_v"])

    # Compute vertical coordinates at rho-points
    # shape: (N, eta_rho, xi_rho)
    z_r = compute_z_r(h, HC, THETA_S, THETA_B, N)

    # Interpolate z_r to staggered points
    # shape: (N, eta_u, xi_u)
    z_r_u = 0.5 * (z_r[:, :, :-1] + z_r[:, :, 1:])

    # shape: (N, eta_v, xi_v)
    z_r_v = 0.5 * (z_r[:, :-1, :] + z_r[:, 1:, :])

    # Allocate climatology fields
    temp = temp_initial(z_r, cfg)
    u = u_initial(z_r_u, cfg)
    v = v_initial(z_r_v, cfg)

    # Write climatology NetCDF
    with nc.Dataset(clm_path, "w", format="NETCDF4") as f:
        # Global attributes
        f.title = "ROMS Climatology (parameterized)"
        f.history = "Created by tools/make_clm.py"
        f.description = "Stationary climatology for tracer and 3D momentum nudging"
        f.source = "Generated from grid file"

        # Dimensions
        f.createDimension("xi_rho", xi_rho)
        f.createDimension("eta_rho", eta_rho)
        f.createDimension("xi_u", xi_u)
        f.createDimension("eta_u", eta_u)
        f.createDimension("xi_v", xi_v)
        f.createDimension("eta_v", eta_v)
        f.createDimension("s_rho", N)

        f.createDimension("temp_time", None)
        f.createDimension("v3d_time", None)

        # Time variables
        temp_time = f.createVariable("temp_time", "f8", ("temp_time",))
        temp_time.long_name = "time for temperature climatology"
        temp_time.units = "days"
        temp_time.calendar = "360.0 days in every year"
        temp_time[0] = clm_time_days

        v3d_time = f.createVariable("v3d_time", "f8", ("v3d_time",))
        v3d_time.long_name = "time for 3D momentum climatology"
        v3d_time.units = "days"
        v3d_time.calendar = "360.0 days in every year"
        v3d_time[0] = clm_time_days

        # temp
        vtemp = f.createVariable("temp", "f8", ("temp_time", "s_rho", "eta_rho", "xi_rho"))
        vtemp.long_name = "potential temperature climatology"
        vtemp.units = "Celsius"
        vtemp.field = "temperature, scalar, series"
        vtemp[0, :, :, :] = temp

        # u
        vu = f.createVariable("u", "f8", ("v3d_time", "s_rho", "eta_u", "xi_u"))
        vu.long_name = "u-momentum component climatology"
        vu.units = "meter second-1"
        vu.field = "u-velocity, scalar, series"
        vu[0, :, :, :] = u

        # v
        vv = f.createVariable("v", "f8", ("v3d_time", "s_rho", "eta_v", "xi_v"))
        vv.long_name = "v-momentum component climatology"
        vv.units = "meter second-1"
        vv.field = "v-velocity, scalar, series"
        vv[0, :, :, :] = v

    return clm_path


if __name__ == "__main__":
    # CLI fallback: accept a single config path
    if len(sys.argv) != 2:
        print("Usage: python tools/make_clm.py path/to/config.yaml", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        cfg = yaml.safe_load(f)

    make_clm_from_config(cfg)