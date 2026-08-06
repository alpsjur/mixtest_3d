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

def sustr_forcing(ocean_time, eta_u, xi_u, cfg):
    """
    Surface zonal wind stress on u-points (N/m^2).

    Parameters
    ----------
    ocean_time : np.ndarray, shape (n_time,)
        Time axis in seconds since simulation start.
    eta_u, xi_u : int
        Spatial dimensions of the u-grid.
    cfg : dict
        Resolved config dict; use cfg["forcing"] for parameters.

    Returns
    -------
    np.ndarray, shape (n_time, eta_u, xi_u)

    Replace the placeholder with an analytical expression, e.g.:
        tau0 = cfg["forcing"]["sustr_tau0"]
        T    = cfg["forcing"]["sustr_period"]
        tau  = tau0 * np.sin(2 * np.pi * ocean_time / T)  # (n_time,)
        return np.broadcast_to(tau[:, None, None], (len(ocean_time), eta_u, xi_u)).copy()
    """
    n_time = len(ocean_time)
    tau0 = cfg["forcing"].get("sustr_tau0", 0.1)
    return np.full((n_time, eta_u, xi_u), tau0, dtype=np.float64)


def svstr_forcing(ocean_time, eta_v, xi_v, cfg):
    """
    Surface meridional wind stress on v-points (N/m^2).

    Parameters
    ----------
    ocean_time : np.ndarray, shape (n_time,)
        Time axis in seconds since simulation start.
    eta_v, xi_v : int
        Spatial dimensions of the v-grid.
    cfg : dict
        Resolved config dict; use cfg["forcing"] for parameters.

    Returns
    -------
    np.ndarray, shape (n_time, eta_v, xi_v)
    """
    n_time = len(ocean_time)
    tau0 = cfg["forcing"].get("svstr_tau0", 0.0)
    return np.full((n_time, eta_v, xi_v), tau0, dtype=np.float64)

# ---------------------------------------------------------------------------
# Main forcing file creation function
# ---------------------------------------------------------------------------

def make_frc_from_config(cfg: dict) -> str:
    """
    Create the surface forcing file using values from a resolved config dict.

    The forcing has its own time axis defined entirely in cfg["forcing"]:
      - t_start : start time in seconds (default 0)
      - t_end   : end time in seconds (must cover the full simulation)
      - dt_frc  : forcing time step in seconds
    ROMS will interpolate between forcing snapshots at run time.
    """
    input_dir = cfg["io"]["input_dir"]
    grd_name  = cfg["files"]["grd"]
    frc_name  = cfg["files"]["frc"]

    grd_path = os.path.join(input_dir, grd_name)
    frc_path = os.path.join(input_dir, frc_name)
    os.makedirs(os.path.dirname(frc_path) or ".", exist_ok=True)

    # Build forcing time axis — independent of model time stepping resolution,
    # but guaranteed to cover the full simulation duration.
    DT     = float(cfg["time_stepping"]["DT"])
    NTIMES = int(cfg["time_stepping"]["NTIMES"])
    t_start = 0
    t_end   = NTIMES * DT
    dt_frc  = float(cfg["forcing"]["dt_frc"])
    frc_time = np.arange(t_start, t_end + dt_frc, dt_frc)

    # Read grid dimensions
    with nc.Dataset(grd_path, "r") as grd:
        xi_rho  = len(grd.dimensions["xi_rho"])
        eta_rho = len(grd.dimensions["eta_rho"])

    xi_u  = xi_rho - 1
    eta_u = eta_rho
    xi_v  = xi_rho
    eta_v = eta_rho - 1

    # Compute forcing fields — shape (n_time, eta, xi)
    sustr = sustr_forcing(frc_time, eta_u, xi_u, cfg)
    svstr = svstr_forcing(frc_time, eta_v, xi_v, cfg)

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
        f.createDimension("sms_time", None)

        # sms_time — required name for surface momentum stress time coordinate
        ot = f.createVariable("sms_time", "f8", ("sms_time",))
        ot.long_name = "time since simulation start"
        ot.units = "seconds since 0001-01-01 00:00:00"
        ot.calendar = "360.0 days in every year"
        ot[:] = frc_time

        # sustr — surface zonal stress on u-points
        su = f.createVariable("sustr", "f8", ("sms_time", "eta_u", "xi_u"))
        su.long_name = "surface u-momentum stress"
        su.units = "N/m^2"
        su[:] = sustr

        # svstr — surface meridional stress on v-points
        sv = f.createVariable("svstr", "f8", ("sms_time", "eta_v", "xi_v"))
        sv.long_name = "surface v-momentum stress"
        sv.units = "N/m^2"
        sv[:] = svstr

    return frc_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/make_frc.py path/to/config.yaml", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "r") as fh:
        cfg = yaml.safe_load(fh)
    make_frc_from_config(cfg)
