#!/usr/bin/env python3
"""
tools/run_experiment.py

Execute a single ROMS simulation from a resolved config.

Usage:
    python tools/run_experiment.py runs/<run_name>/resolved_config.yaml
"""
import os
import sys
import datetime
import subprocess
import shlex

# Ensure project root is importable
THIS_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils.utils import load_yaml, save_yaml, ensure_dir

# Always run ROMS from <ROOT_DIR>/roms/romsS
ROMS_EXEC = os.path.join(ROOT_DIR, "roms", "romsS")

def write_run_status(logs_dir: str, status: dict) -> str:
    status_path = os.path.join(logs_dir, "status.yaml")
    save_yaml(status_path, status)
    return status_path

def run_single_resolved(resolved_cfg_path: str) -> dict:
    """
    Run a ROMS simulation from a resolved config.
    Returns: dict with run_dir, log, status_file, returncode, timestamps, state.
    """
    resolved_cfg_path = os.path.abspath(resolved_cfg_path)
    cfg = load_yaml(resolved_cfg_path)

    # Derive run_dir from the location of the resolved config (prep wrote it)
    run_dir = os.path.dirname(resolved_cfg_path)
    logs_dir = os.path.join(run_dir, "logs")
    ensure_dir(logs_dir)

    input_dir = cfg["io"]["input_dir"]  # absolute path injected by prep
    in_file = os.path.join(input_dir, "mixtest_3d.in")
    log_file = os.path.join(logs_dir, "simulation.log")

    # Preflight checks
    if not os.path.isfile(ROMS_EXEC):
        raise FileNotFoundError(f"ROMS executable not found: {ROMS_EXEC}")
    if not os.path.isfile(in_file):
        raise FileNotFoundError(f"Input file not found: {in_file}")

    cmd = [ROMS_EXEC]
    cmd_str = f"{shlex.join(cmd)} < {in_file} > {log_file} (cwd={run_dir})"

    started_at = datetime.datetime.now().isoformat(timespec="seconds")
    status = {"state": "running", "started_at": started_at, "cmd": cmd_str}
    status_file = write_run_status(logs_dir, status)

    try:
        with open(in_file, "rb") as fin, open(log_file, "wb") as flog:
            proc = subprocess.run(
                cmd,
                stdin=fin,
                stdout=flog,
                stderr=subprocess.STDOUT,
                cwd=run_dir,
                check=False,
            )
        returncode = proc.returncode
    except FileNotFoundError as e:
        returncode = -1
        with open(log_file, "ab") as flog:
            flog.write(f"\nERROR: {e}\n".encode("utf-8"))

    finished_at = datetime.datetime.now().isoformat(timespec="seconds")
    state = "done" if returncode == 0 else "failed"
    status.update({"state": state, "finished_at": finished_at, "returncode": returncode})
    write_run_status(logs_dir, status)

    return {
        "run_dir": run_dir,
        "log": log_file,
        "status_file": status_file,
        "returncode": returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "state": state,
    }

def main():
    if len(sys.argv) != 2:
        print("Usage: python tools/run_experiment.py runs/<run_name>/resolved_config.yaml", file=sys.stderr)
        sys.exit(1)
    resolved_cfg_path = sys.argv[1]
    res = run_single_resolved(resolved_cfg_path)
    print(f"Run finished: state={res['state']} returncode={res['returncode']}")
    print(f"Log: {res['log']}")
    print(f"Status: {res['status_file']}")

if __name__ == "__main__":
    main()