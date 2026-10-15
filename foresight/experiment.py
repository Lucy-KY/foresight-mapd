"""Batch experiments: expand a config into jobs, run them, write one CSV row
per run.

Owner: member 1. ``experiments/run.py`` is the command-line entry point.

Config format (TOML), see ``experiments/configs/README.md``:

    map = "maps/warehouse_small.map"
    n_tasks = 500
    agents = [10, 30, 50]
    arrival_rates = [0.2, 1, 5]
    seeds = [0, 1, 2]
    planner = "tp"            # optional, default "tp"
    max_timesteps = 100000    # optional

    [methods.foresight]
    lam = [0.5, 1.0, 2.0]     # a list is swept: one job per value
    window = 5
"""

from __future__ import annotations

import csv
import itertools
import json
import subprocess
import time
from dataclasses import fields
from multiprocessing import Pool
from pathlib import Path as FsPath
from typing import Any, Callable

from foresight.costs import METHODS, HighwayCost
from foresight.interfaces import CostModel, Planner
from foresight.sim.grid import GridMap
from foresight.sim.instance import make_instance
from foresight.sim.metrics import RunResult
from foresight.sim.simulator import Simulator

ROOT = FsPath(__file__).resolve().parents[1]
DEFAULT_PLANNER = "tp"
DEFAULT_MAX_TIMESTEPS = 100_000

_IDENTITY = ["job_key", "method", "planner", "map_name", "n_agents", "arrival_rate", "seed", "n_tasks"]
_EXTRAS = ["completed", "error", "wall_time_s", "git_commit"]


def planners() -> dict[str, Callable[[], Planner]]:
    """Planner name -> constructor. ``stub`` runs the pipeline before TP
    exists; its numbers mean nothing."""
    from foresight.planner.tp import TokenPassing
    from foresight.planner.tpts import TokenPassingWithSwaps
    from foresight.sim.stubs import OneAtATimePlanner

    return {"tp": TokenPassing, "tpts": TokenPassingWithSwaps, "stub": OneAtATimePlanner}


def expand(config: dict) -> list[dict]:
    """One job per (method, parameter combination, n_agents, arrival_rate,
    seed). A parameter given as a list is swept."""
    jobs = []
    for method, params in config["methods"].items():
        if method not in METHODS:
            raise ValueError(f"unknown method {method!r}; known: {sorted(METHODS)}")
        for combo in param_grid(params):
            for n_agents, rate, seed in itertools.product(
                config["agents"], config["arrival_rates"], config["seeds"]
            ):
                jobs.append(
                    {
                        "map": config["map"],
                        "n_tasks": config["n_tasks"],
                        "planner": config.get("planner", DEFAULT_PLANNER),
                        "max_timesteps": config.get("max_timesteps", DEFAULT_MAX_TIMESTEPS),
                        "method": method,
                        "params": combo,
                        "n_agents": n_agents,
                        "arrival_rate": rate,
                        "seed": seed,
                    }
                )
    return jobs


def param_grid(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Cartesian product over the list-valued parameters."""
    keys = sorted(params)
    values = [params[k] if isinstance(params[k], list) else [params[k]] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def job_key(job: dict) -> str:
    """Stable identity of a job, used to skip finished jobs on resume."""
    return json.dumps(job, sort_keys=True, separators=(",", ":"))


def columns(jobs: list[dict]) -> list[str]:
    """CSV header: identity, metrics, every parameter seen in the jobs,
    bookkeeping. Fixed per config, so rows from resumed runs line up."""
    skip = set(_IDENTITY) | {"params"}
    metric_cols = [f.name for f in fields(RunResult) if f.name not in skip]
    param_cols = sorted({f"param_{k}" for job in jobs for k in job["params"]})
    return _IDENTITY + metric_cols + param_cols + _EXTRAS


def build_cost_model(method: str, params: dict[str, Any], grid: GridMap) -> CostModel:
    """Cost model for ``method``. Highway takes ``directions`` (a lane file
    such as ``maps/warehouse_small.highway.json``) and ``w_h``."""
    if method == "highway":
        return HighwayCost.from_file(ROOT / params["directions"], grid, params["w_h"])
    return METHODS[method](**params)


_grids: dict[str, GridMap] = {}


def _grid(path: str) -> GridMap:
    if path not in _grids:
        _grids[path] = GridMap.load(ROOT / path)
    return _grids[path]


def run_job(job: dict, git_commit: str = "") -> dict[str, Any]:
    """Run one job and return its CSV row. Never raises: a failure ends up
    in the ``error`` column, so one bad job does not stop a batch. A run
    with conflicts also counts as failed."""
    start = time.perf_counter()
    row: dict[str, Any] = {
        "job_key": job_key(job),
        "method": job["method"],
        "planner": job["planner"],
        "map_name": FsPath(job["map"]).stem,
        "n_agents": job["n_agents"],
        "arrival_rate": job["arrival_rate"],
        "seed": job["seed"],
        "n_tasks": job["n_tasks"],
        **{f"param_{k}": v for k, v in job["params"].items()},
        "git_commit": git_commit,
        "error": "",
    }
    try:
        grid = _grid(job["map"])
        instance = make_instance(grid, job["n_agents"], job["n_tasks"], job["arrival_rate"], job["seed"])
        cost_model = build_cost_model(job["method"], job["params"], grid)
        planner = planners()[job["planner"]]()
        log = Simulator(instance, planner, cost_model, job["max_timesteps"]).run(check=False)
        result = log.to_result(
            RunResult(row["method"], row["map_name"], row["n_agents"], row["arrival_rate"], row["seed"], job["params"])
        )
        row.update(result.to_row())
        row["completed"] = result.completed
        if result.n_conflicts:
            row["error"] = f"{result.n_conflicts} conflicts"
    except Exception as e:  # noqa: BLE001 - recorded, not swallowed
        row["error"] = f"{type(e).__name__}: {e}"
    row["wall_time_s"] = round(time.perf_counter() - start, 3)
    return row


def _run_job_star(args: tuple[dict, str]) -> dict[str, Any]:
    return run_job(*args)


def git_commit() -> str:
    """Short commit hash of the code being run, ``-dirty`` if uncommitted
    changes exist, empty outside a git checkout."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "foresight"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return ""


def run_all(
    config: dict,
    out: FsPath,
    n_workers: int = 1,
    resume: bool = True,
    limit: int | None = None,
    progress: Callable[[str], None] = print,
) -> dict[str, int]:
    """Run every job of ``config`` not yet in ``out`` and append its rows.

    With ``resume``, successful rows already in ``out`` are kept and their
    jobs skipped; failed rows are dropped and retried. ``limit`` caps how
    many jobs run this time (useful to time a few before a full batch).
    Rows are written as soon as each job finishes.
    """
    jobs = expand(config)
    header = columns(jobs)
    out = FsPath(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    kept: list[dict[str, str]] = []
    if resume and out.exists():
        with open(out, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != header:
                raise ValueError(f"{out} was written by a different config; use another --out")
            kept = [row for row in reader if not row["error"]]
    done = {row["job_key"] for row in kept}
    todo = [job for job in jobs if job_key(job) not in done]
    skipped = len(jobs) - len(todo)
    if limit is not None:
        todo = todo[:limit]

    commit = git_commit()
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(kept)
        f.flush()

        failed = 0

        def record(i: int, row: dict[str, Any]) -> None:
            nonlocal failed
            writer.writerow(row)
            f.flush()
            failed += bool(row["error"])
            status = row["error"] or f"mean service time {row.get('service_time_mean')}"
            progress(
                f"[{i}/{len(todo)}] {row['method']} agents={row['n_agents']} rate={row['arrival_rate']} "
                f"seed={row['seed']} ({row['wall_time_s']}s): {status}"
            )

        args = [(job, commit) for job in todo]
        if n_workers <= 1:
            for i, row in enumerate(map(_run_job_star, args), 1):
                record(i, row)
        else:
            with Pool(n_workers) as pool:
                for i, row in enumerate(pool.imap_unordered(_run_job_star, args), 1):
                    record(i, row)

    return {"total": len(jobs), "skipped": skipped, "ran": len(todo), "failed": failed}
