#!/usr/bin/env python3
"""
tools/make_nud.py

Create a ROMS-compatible nudging coefficients NetCDF file using a resolved config dict.

This writes:
  - tracer_NudgeCoef   : generic tracer inverse nudging coefficients
  - M3_NudgeCoef       : 3D momentum inverse nudging coefficients

Important:
- Values are written in day^-1, consistent with ROMS varinfo.yaml.
- A coefficient of 1/tau_days corresponds to a nudging timescale tau_days.
- Outside nudging zones, coefficients are zero.

This version supports a plateau-shaped nudging zone:
  taper up -> flat strong core -> taper down

Preferred usage (from orchestrator):
    from tools.make_nud import make_nud_from_config
    nud_path = make_nud_from_config(cfg_dict)

CLI fallback:
    python tools/make_nud.py path/to/config.yaml
"""

import os
import sys
import numpy as np
import netCDF4 as nc
import yaml


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def inverse_days(timescale_days: float) -> float:
    """
    Convert a nudging timescale in days to an inverse timescale in day^-1.
    """
    if timescale_days <= 0.0:
        raise ValueError(f"timescale_days must be > 0, got {timescale_days}")
    return 1.0 / timescale_days


def plateau_zone_profile(
    xi_rho: int,
    start: int,
    taper_width: int,
    core_width: int,
    tau_core_days: float,
    tau_edge_days: float,
) -> np.ndarray:
    """
    Build a 1D plateau-shaped nudging coefficient profile on xi_rho points.

    Shape:
        taper up -> flat core -> taper down

    Parameters
    ----------
    xi_rho : int
        Domain length in xi direction.
    start : int
        Starting xi-index of the whole zone (including taper + core + taper).
    taper_width : int
        Number of grid cells in each taper.
    core_width : int
        Number of grid cells in the flat strong core.
    tau_core_days : float
        Strong restoring timescale in the core [days].
    tau_edge_days : float
        Weak restoring timescale at the inner edges of the taper [days].

    Returns
    -------
    coef : ndarray, shape (xi_rho,)
        Nudging coefficient in day^-1.
    """
    coef = np.zeros(xi_rho, dtype=np.float64)

    if taper_width < 0 or core_width < 0:
        raise ValueError("taper_width and core_width must be >= 0")

    total_width = 2 * taper_width + core_width
    if total_width <= 0:
        return coef

    end = start + total_width
    if start < 0 or end > xi_rho:
        raise ValueError(
            f"Nudging zone [{start}:{end}] is outside domain [0:{xi_rho}]"
        )

    lam_core = inverse_days(tau_core_days)
    lam_edge = inverse_days(tau_edge_days)

    # Left taper: from weak edge -> strong core
    if taper_width > 0:
        for n in range(taper_width):
            r = (n + 1) / taper_width
            i = start + n
            coef[i] = lam_edge + r * (lam_core - lam_edge)

    # Flat core
    for n in range(core_width):
        i = start + taper_width + n
        coef[i] = lam_core

    # Right taper: from strong core -> weak edge
    if taper_width > 0:
        for n in range(taper_width):
            r = (n + 1) / taper_width
            i = start + taper_width + core_width + n
            coef[i] = lam_core + r * (lam_edge - lam_core)

    return coef


def make_2d_from_x_profile(x_profile: np.ndarray, eta_rho: int) -> np.ndarray:
    """
    Expand a 1D x-profile into a 2D rho-grid field by repeating in eta.
    """
    return np.repeat(x_profile[np.newaxis, :], eta_rho, axis=0)


def make_3d_from_2d(field_2d: np.ndarray, N: int) -> np.ndarray:
    """
    Expand a 2D field into a 3D field by repeating in s_rho.
    """
    return np.repeat(field_2d[np.newaxis, :, :], N, axis=0)


# ---------------------------------------------------------------------------
# Nudging field builders
# ---------------------------------------------------------------------------

def tracer_nudging_field(eta_rho: int, xi_rho: int, N: int, cfg: dict) -> np.ndarray:
    """
    Create tracer_NudgeCoef field, shape (s_rho, eta_rho, xi_rho), in day^-1.

    Expected config block:
      nudging:
        tracer:
          zone_start: 0
          taper_width: 5
          core_width: 10
          tau_core_days: 2.0
          tau_edge_days: 20.0
    """
    nud = cfg["nudging"]["tracer"]

    zone_start = int(nud["zone_start"])
    taper_width = int(nud["taper_width"])
    core_width = int(nud["core_width"])
    tau_core_days = float(nud["tau_core_days"])
    tau_edge_days = float(nud["tau_edge_days"])

    coef_1d = plateau_zone_profile(
        xi_rho=xi_rho,
        start=zone_start,
        taper_width=taper_width,
        core_width=core_width,
        tau_core_days=tau_core_days,
        tau_edge_days=tau_edge_days,
    )

    coef_2d = make_2d_from_x_profile(coef_1d, eta_rho)
    coef_3d = make_3d_from_2d(coef_2d, N)

    return coef_3d


def m3_nudging_field(eta_rho: int, xi_rho: int, N: int, cfg: dict) -> np.ndarray:
    """
    Create M3_NudgeCoef field, shape (s_rho, eta_rho, xi_rho), in day^-1.

    Expected config block:
      nudging:
        m3:
          zone_start: 0
          taper_width: 5
          core_width: 10
          tau_core_days: 4.0
          tau_edge_days: 30.0
    """
    nud = cfg["nudging"]["m3"]

    zone_start = int(nud["zone_start"])
    taper_width = int(nud["taper_width"])
    core_width = int(nud["core_width"])
    tau_core_days = float(nud["tau_core_days"])
    tau_edge_days = float(nud["tau_edge_days"])

    coef_1d = plateau_zone_profile(
        xi_rho=xi_rho,
        start=zone_start,
        taper_width=taper_width,
        core_width=core_width,
        tau_core_days=tau_core_days,
        tau_edge_days=tau_edge_days,
    )

    coef_2d = make_2d_from_x_profile(coef_1d, eta_rho)
    coef_3d = make_3d_from_2d(coef_2d, N)

    return coef_3d


# ---------------------------------------------------------------------------
# Main file creation function
# ---------------------------------------------------------------------------

def make_nud_from_config(cfg: dict) -> str:
    """
    Create the nudging coefficients file using values from a resolved config dict.
    """
    input_dir = cfg["io"]["input_dir"]
    grd_name = cfg["files"]["grd"]
    nud_name = cfg["files"]["nud"]

    grd_path = os.path.join(input_dir, grd_name)
    nud_path = os.path.join(input_dir, nud_name)
    os.makedirs(os.path.dirname(nud_path) or ".", exist_ok=True)

    N = int(cfg["grid"]["N"])

    # Read grid size from ROMS grid file
    with nc.Dataset(grd_path, "r") as grd:
        xi_rho = len(grd.dimensions["xi_rho"])
        eta_rho = len(grd.dimensions["eta_rho"])

    # Build nudging coefficient fields
    tracer_coef = tracer_nudging_field(eta_rho, xi_rho, N, cfg)
    m3_coef = m3_nudging_field(eta_rho, xi_rho, N, cfg)

    # Write output NetCDF
    with nc.Dataset(nud_path, "w", format="NETCDF4") as f:
        # Global attributes
        f.title = "ROMS nudging coefficients"
        f.history = "Created by tools/make_nud.py"
        f.description = "Spatially varying tracer and 3D momentum inverse nudging coefficients"
        f.source = "Generated from grid file and config"

        # Dimensions
        f.createDimension("xi_rho", xi_rho)
        f.createDimension("eta_rho", eta_rho)
        f.createDimension("s_rho", N)

        # tracer_NudgeCoef
        vtrc = f.createVariable("tracer_NudgeCoef", "f8", ("s_rho", "eta_rho", "xi_rho"))
        vtrc.long_name = "generic tracer inverse nudging coefficients"
        vtrc.units = "day-1"
        vtrc.coordinates = "s_rho"
        vtrc.field = "tracer nudging scale"
        vtrc[:, :, :] = tracer_coef

        # M3_NudgeCoef
        vm3 = f.createVariable("M3_NudgeCoef", "f8", ("s_rho", "eta_rho", "xi_rho"))
        vm3.long_name = "3D momentum inverse nudging coefficients"
        vm3.units = "day-1"
        vm3.coordinates = "s_rho"
        vm3.field = "momentum nudging scale"
        vm3[:, :, :] = m3_coef

    return nud_path


# ---------------------------------------------------------------------------
# CLI fallback
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/make_nud.py path/to/config.yaml", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        cfg = yaml.safe_load(f)

    make_nud_from_config(cfg)