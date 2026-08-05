#!/usr/bin/env python3
import os
import sys
import yaml
import hashlib
from copy import deepcopy
from jinja2 import Environment, FileSystemLoader

# Project root (repo root), anchored to this file's location
THIS_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# All runs will be placed under <ROOT_DIR>/runs/<name>
RUNS_ROOT = os.path.join(ROOT_DIR, "runs")

# Tools
from tools.make_grd import make_grid_from_config
from tools.make_ini import make_ini_from_config


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def config_hash(cfg: dict) -> str:
    """Exact hash of the fully resolved config."""
    dumped = yaml.safe_dump(cfg, sort_keys=True)
    return _sha256_hex(dumped)[:12]

def deep_merge(a: dict, b: dict) -> dict:
    """Deep-merge dict b into a and return a new dict (b overrides a)."""
    out = deepcopy(a)
    for k, v in (b or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out

def resolve_config(baseline_path: str, override_path: str | None = None) -> dict:
    """Load baseline (+ optional override) and return resolved config."""
    with open(baseline_path, "r") as f:
        base = yaml.safe_load(f) or {}
    over = {}
    if override_path:
        with open(override_path, "r") as f:
            over = yaml.safe_load(f) or {}
    return deep_merge(base, over)

def prepare_run_dirs(cfg: dict) -> tuple[str, str, str, str]:
    """
    Create <ROOT_DIR>/runs/<name>/{input,output,logs} and
    return (run_dir, input_dir, output_dir, logs_dir).
    """
    run_name = cfg["run"]["name"]
    run_dir = os.path.join(RUNS_ROOT, run_name)
    input_dir = os.path.join(run_dir, "input")
    output_dir = os.path.join(run_dir, "output")
    logs_dir = os.path.join(run_dir, "logs")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    return run_dir, input_dir, output_dir, logs_dir

def write_resolved_config(cfg: dict, run_dir: str) -> str:
    """Write resolved_config.yaml into the run directory and return its path."""
    resolved_path = os.path.join(run_dir, "resolved_config.yaml")
    with open(resolved_path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    return resolved_path

def render_roms_input(cfg: dict, input_dir: str, template_name: str = "mixtest_3d.in.j2") -> str:
    """Render ROMS input file into <run>/input/mixtest_3d.in and return its path."""
    template_dir = os.path.join(ROOT_DIR, "templates")
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
    tmpl = env.get_template(template_name)
    rendered = tmpl.render(**cfg)
    out_in_path = os.path.join(input_dir, "mixtest_3d.in")
    with open(out_in_path, "w") as f:
        f.write(rendered)
    return out_in_path

def prepare_run_from_resolved(cfg: dict) -> dict:
    """
    - Creates <ROOT_DIR>/runs/<name>/{input,output,logs}
    - Sets cfg['io'].input_dir/output_dir to absolute paths
    - Writes resolved_config.yaml
    - Generates grid, ini
    - Renders input file
    """
    # 1) Create run directories under a single fixed root
    run_dir, input_dir, output_dir, logs_dir = prepare_run_dirs(cfg)

    # 2) Inject absolute paths for templates and runner
    cfg.setdefault("io", {})
    cfg["io"]["input_dir"] = input_dir
    cfg["io"]["output_dir"] = output_dir

    # 3) Hash after paths are set
    cfg.setdefault("_meta", {})
    cfg["_meta"]["hash"] = {"exact": config_hash(cfg)}

    # 4) Persist resolved config
    resolved_path = write_resolved_config(cfg, run_dir)

    # 5) Generate artifacts
    grid_path = make_grid_from_config(cfg)
    ini_path = make_ini_from_config(cfg)

    # 6) Render ROMS input file
    in_path = render_roms_input(cfg, input_dir)

    return {
        "run_dir": run_dir,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "logs_dir": logs_dir,
        "resolved_config": resolved_path,
        "grid": grid_path,
        "ini": ini_path,
        "in_file": in_path,
        "hash_exact": cfg["_meta"]["hash"]["exact"],
    }

def main():
    """CLI entry point: resolve baseline + optional override, then prepare the run."""
    baseline_path = sys.argv[1] if len(sys.argv) > 1 else "configs/baseline.yaml"
    override_path = sys.argv[2] if len(sys.argv) > 2 else None
    cfg = resolve_config(baseline_path, override_path)
    prepare_run_from_resolved(cfg)

if __name__ == "__main__":
    main()