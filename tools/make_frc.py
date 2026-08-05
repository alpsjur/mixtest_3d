#!/usr/bin/env python3
"""
tools/make_frc.py

Create a ROMS-compatible surface forcing NetCDF using a resolved config dict.

Preferred usage (from orchestrator):
    from tools.make_frc import make_frc_from_config
    frc_path = make_frc_from_config(cfg_dict)

CLI fallback:
    python tools/make_frc.py path/to/config.yaml
"""

import os
import sys
import numpy as np
import netCDF4 as nc
import yaml

# ---------------------------------------------------------------------------
# Surface stress functions
# ---------------------------------------------------------------------------

def sustr_forcing(eta_u, xi_u, cfg):
    """
    Surface zonal wind stress on u-points (N/m^2).

    Replace this with an analytical expression using cfg["forcing"] parameters.
    Example:
        tau0 = cfg["forcing"]["sustr_tau0"]
        return np.full((eta_u, xi_u), tau0, dtype=np.float64)
    """
    tau0 = cfg["forcing"].get("sustr_tau0", 0.1)
    return np.full((eta_u, xi_u), tau0, dtype=np.float64)


def svstr_forcing(eta_v, xi_v, cfg):
    """
    Surface meridional wind stress on v-points (N/m^2).

    Replace this with an analytical expression using cfg["forcing"] parameters.
    Example:
        tau0 = cfg["forcing"]["svstr_tau0"]
        return np.full((eta_v, xi_v), tau0, dtype=np.float64)
    """
    tau0 = cfg["forcing"].get("svstr_tau0", 0.0)
    return np.full((eta_v, xi_v), tau0, dtype=np.float64)

# ---------------------------------------------------------------------------
# Main forcing file creation function
# ---------------------------------------------------------------------------

def make_frc_from_config(cfg: dict) -> str:
    """
    Create the surface forcing file using values from a resolved config dict.
    """
    input_dir = cfg["io"]["input_dir"]
    grd_name  = cfg["files"]["grd"]
    frc_name  = cfg["files"]["frc"]

    grd_path = os.path.join(input_dir, grd_name)
    frc_path = os.path.join(input_dir, frc_name)
    os.makedirs(os.path.dirname(frc_path) or ".", exist_ok=True)

    ocean_time_seconds = float(cfg["forcing"].get("ocean_time_seconds", 0.0))

    # Read grid dimensions
    with nc.Dataset(grd_path, "r") as grd:
        xi_rho  = len(grd.dimensions["xi_rho"])
        eta_rho = len(grd.dimensions["eta_rho"])

    xi_u  = xi_rho - 1
    eta_u = eta_rho
    xi_v  = xi_rho
    eta_v = eta_rho - 1

    # Compute forcing fields
    sustr = sustr_forcing(eta_u, xi_u, cfg)
    svstr = svstr_forcing(eta_v, xi_v, cfg)

    # Write forcing NetCDF
    with nc.Dataset(frc_path, "w", format="NETCDF4") as f:
        f.title = "ROMS Surface Forcing"
        f.history = "Created by tools/make_frc.py"
        f.description = "Surface wind stress forcing (sustr, svstr)"

        # Dimensions
        f.createDimension("xi_rho",  xi_rho)
        f.createDimension("eta_rho", eta_rho)
        f.createDimension("xi_u",    xi_u)
        f.createDimension("eta_u",   eta_u)
        f.createDimension("xi_v",    xi_v)
        f.createDimension("eta_v",   eta_v)
        f.createDimension("ocean_time", None)

        # ocean_time
        ot = f.createVariable("ocean_time", "f8", ("ocean_time",))
        ot.long_name = "time since simulation start"
        ot.units = "seconds since 0001-01-01 00:00:00"
        ot.calendar = "360.0 days in every year"
        ot[0] = ocean_time_seconds

        # sustr — surface zonal stress on u-points
        su = f.createVariable("sustr", "f8", ("ocean_time", "eta_u", "xi_u"))
        su.long_name = "surface u-momentum stress"
        su.units = "N/m^2"
        su[0, :, :] = sustr

        # svstr — surface meridional stress on v-points
        sv = f.createVariable("svstr", "f8", ("ocean_time", "eta_v", "xi_v"))
        sv.long_name = "surface v-momentum stress"
        sv.units = "N/m^2"
        sv[0, :, :] = svstr

    return frc_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/make_frc.py path/to/config.yaml", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "r") as fh:
        cfg = yaml.safe_load(fh)
    make_frc_from_config(cfg)
