#!/usr/bin/env python3
"""
tools/make_ini.py

Create a ROMS-compatible initial conditions NetCDF using a resolved config dict.

Preferred usage (from orchestrator):
    from tools.make_ini import make_ini_from_config
    ini_path = make_ini_from_config(cfg_dict)

CLI fallback:
    python tools/make_ini.py path/to/config.yaml
"""

import os
import sys
import numpy as np
import netCDF4 as nc
import yaml
from utils.utils import compute_z_r

# ---------------------------------------------------------------------------
# Initialization Functions
# ---------------------------------------------------------------------------

def zeta_initial(x_rho, y_rho, cfg):
    """
    Initial free surface elevation (zeta). Currently zero everywhere (flat surface).

    To add a slope, e.g. for a pressure-driven flow test, you could use:
        zeta_slope = cfg["initial"].get("zeta_slope", 0.0)
        return zeta_slope * x_rho
    """
    return np.zeros_like(x_rho, dtype=np.float64)

def ubar_initial(x_u, y_u, cfg):
    """
    Initial depth-averaged u-velocity (ubar). Currently zero (no background flow).

    To add a uniform barotropic current, use:
        return np.full_like(x_u, cfg["initial"]["ubar0"], dtype=np.float64)
    """
    return np.zeros_like(x_u, dtype=np.float64)


def vbar_initial(x_v, y_v, cfg):
    """
    Initial depth-averaged v-velocity (vbar). Currently zero (no background flow).

    To add a uniform barotropic current, use:
        return np.full_like(x_v, cfg["initial"]["vbar0"], dtype=np.float64)
    """
    return np.zeros_like(x_v, dtype=np.float64)


def u_initial(z_r, cfg):
    """
    Initial 3D u-velocity.

    Supported options under cfg["initial"]["u_type"]:

      1. "uniform"
         Required:
           - u0

      2. "tanh_shear"
         Required:
           - u0      : upper-layer velocity [m/s]
           - u_deep  : deep velocity [m/s]
           - u_zt    : transition depth [m, positive down]
           - u_ht    : transition half-thickness [m]
    """
    u_type = cfg["initial"].get("u_type", "uniform")

    if u_type == "uniform":
        u0 = float(cfg["initial"]["u0"])
        return np.full_like(z_r, u0, dtype=np.float64)

    elif u_type == "tanh_shear":
        u0 = float(cfg["initial"]["u0"])
        u_deep = float(cfg["initial"]["u_deep"])
        u_zt = float(cfg["initial"]["u_zt"])
        u_ht = float(cfg["initial"]["u_ht"])

        # Near surface: approximately u0
        # At depth: approximately u_deep
        return u_deep + 0.5 * (u0 - u_deep) * (1.0 + np.tanh((z_r + u_zt) / u_ht))

    else:
        raise ValueError(f"Unsupported initial u_type: {u_type}")


def v_initial(z_r, cfg):
    """
    Initial 3D v-velocity field. Currently zero (no background shear).

    To add a depth-varying shear profile, see u_initial for the approach.
    """
    return np.zeros_like(z_r, dtype=np.float64)

def temp_initial(z_r, cfg):
    """
    Initial temperature profile using a hyperbolic tangent thermocline.

    The profile is parameterized by four values in cfg["initial"]:
      - T0 : surface temperature (°C)
      - dT : total temperature drop across the thermocline (°C)
      - zt : depth of the thermocline centre (m, positive down)
      - ht : half-thickness of the thermocline (m)

    The formula is:
        T(z) = (T0 - dT) + (dT/2) * (1 + tanh((z + zt) / ht))

    This gives T0 near the surface, T0-dT below the thermocline, and a smooth
    transition of width ~ht centred at depth zt.

    To use a linear stratification instead:
        N2 = cfg["initial"]["N2"]   # buoyancy frequency squared [s^-2]
        alpha = ...                  # thermal expansion coefficient
        return T0 + (N2 / (g * alpha)) * z_r
    """
    T0 = cfg["initial"]["T0"]
    dT = cfg["initial"]["dT"]
    zt = cfg["initial"]["zt"]
    ht = cfg["initial"]["ht"]
    return (T0 - dT) + (dT / 2.0) * (1 + np.tanh((z_r + zt) / ht))


def salt_initial(z_r, cfg):
    """
    Initial salinity profile. Currently uniform (no halocline).

    The constant value is set by cfg["initial"]["salt_S0"] (psu).

    To add a halocline, use the same tanh parameterization as temp_initial,
    with separate salt_S0, salt_dS, salt_zs, salt_hs parameters.
    """
    salt_S0 = cfg["initial"]["salt_S0"]
    return np.full_like(z_r, salt_S0, dtype=np.float64)

# ---------------------------------------------------------------------------
# Main Initial Conditions File Creation Function
# ---------------------------------------------------------------------------

def make_ini_from_config(cfg: dict) -> str:
    """
    Create the initial conditions file using values from a resolved config dict.
    """
    input_dir = cfg["io"]["input_dir"]
    grd_name  = cfg["files"]["grd"]
    ini_name  = cfg["files"]["ini"]

    grd_path = os.path.join(input_dir, grd_name)
    ini_path = os.path.join(input_dir, ini_name)
    os.makedirs(os.path.dirname(ini_path) or ".", exist_ok=True)

    # Read required config values
    N = int(cfg["grid"]["N"])

    Vtransform  = int(cfg["vertical"]["Vtransform"])
    Vstretching = int(cfg["vertical"]["Vstretching"])
    THETA_S     = float(cfg["vertical"]["THETA_S"])
    THETA_B     = float(cfg["vertical"]["THETA_B"])
    HC          = float(cfg["vertical"]["HC"])

    ocean_time_seconds = float(cfg["initial"]["ocean_time_seconds"])

    # Read grid geometry
    with nc.Dataset(grd_path, "r") as grd:
        h     = grd.variables["h"][:]
        x_rho = grd.variables["x_rho"][:]
        y_rho = grd.variables["y_rho"][:]
        x_u   = grd.variables["x_u"][:]
        y_u   = grd.variables["y_u"][:]
        x_v   = grd.variables["x_v"][:]
        y_v   = grd.variables["y_v"][:]

        xi_rho  = len(grd.dimensions["xi_rho"])
        eta_rho = len(grd.dimensions["eta_rho"])
        xi_u    = xi_rho - 1
        eta_u   = eta_rho
        xi_v    = xi_rho
        eta_v   = eta_rho - 1

    # Compute vertical coordinates at RHO-points
    z_r = compute_z_r(h, HC, THETA_S, THETA_B, N)  # shape: (N, eta_rho, xi_rho)

    # Interpolate z_r to staggered points
    z_r_u = 0.5 * (z_r[:, :, :-1] + z_r[:, :, 1:])  # (N, eta_u, xi_u)
    z_r_v = 0.5 * (z_r[:, :-1, :] + z_r[:, 1:, :])  # (N, eta_v, xi_v)

    # Allocate initial fields using parameterized functions
    zeta = zeta_initial(x_rho, y_rho, cfg)
    ubar = ubar_initial(x_u, y_u, cfg)
    vbar = vbar_initial(x_v, y_v, cfg)
    u_3d = u_initial(z_r_u, cfg)
    v_3d = v_initial(z_r_v, cfg)
    temp = temp_initial(z_r, cfg)
    salt = salt_initial(z_r, cfg)

    # Write initial conditions NetCDF
    with nc.Dataset(ini_path, "w", format="NETCDF4") as f:
        # Global attributes
        f.title = "ROMS Initial Conditions (parameterized)"
        f.history = "Created by tools/make_ini.py"
        f.description = "Initial conditions with parameterized functions for initialization"
        f.source = "Generated from grid file"

        # Dimensions
        f.createDimension("xi_rho", xi_rho)
        f.createDimension("eta_rho", eta_rho)
        f.createDimension("xi_u",   xi_u)
        f.createDimension("eta_u",  eta_u)
        f.createDimension("xi_v",   xi_v)
        f.createDimension("eta_v",  eta_v)
        f.createDimension("s_rho",  N)
        f.createDimension("ocean_time", None)

        # ocean_time
        ocean_time = f.createVariable("ocean_time", "f8", ("ocean_time",))
        ocean_time.long_name = "time since simulation start"
        ocean_time.units = "seconds since 0001-01-01 00:00:00"
        ocean_time.calendar = "360.0 days in every year"
        ocean_time[0] = ocean_time_seconds

        # Variables
        f.createVariable("zeta", "f8", ("ocean_time", "eta_rho", "xi_rho"))[0, :, :] = zeta
        f.createVariable("ubar", "f8", ("ocean_time", "eta_u", "xi_u"))[0, :, :] = ubar
        f.createVariable("vbar", "f8", ("ocean_time", "eta_v", "xi_v"))[0, :, :] = vbar
        f.createVariable("u", "f8", ("ocean_time", "s_rho", "eta_u", "xi_u"))[0, :, :, :] = u_3d
        f.createVariable("v", "f8", ("ocean_time", "s_rho", "eta_v", "xi_v"))[0, :, :, :] = v_3d
        f.createVariable("temp", "f8", ("ocean_time", "s_rho", "eta_rho", "xi_rho"))[0, :, :, :] = temp
        f.createVariable("salt", "f8", ("ocean_time", "s_rho", "eta_rho", "xi_rho"))[0, :, :, :] = salt

    #print(f"Initial conditions file written: {ini_path}")
    return ini_path


if __name__ == "__main__":
    # CLI fallback: accept a single config path
    if len(sys.argv) != 2:
        print("Usage: python tools/make_ini.py path/to/config.yaml", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], "r") as f:
        cfg = yaml.safe_load(f)
    make_ini_from_config(cfg)