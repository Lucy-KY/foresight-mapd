"""Run every (method, agents, arrival rate, seed) combination in a config.

Usage:
    python experiments/run.py experiments/configs/smoke.toml --out results/smoke.csv --jobs 4

Owner: member 1.
"""

from __future__ import annotations

import argparse
import itertools
import tomllib
from pathlib import Path


def expand(config: dict) -> list[dict]:
    """One job per (method, n_agents, arrival_rate, seed)."""
    jobs = []
    for (method, params), n_agents, rate, seed in itertools.product(
        config["methods"].items(),
        config["agents"],
        config["arrival_rates"],
        config["seeds"],
    ):
        jobs.append(
            {
                "map": config["map"],
                "n_tasks": config["n_tasks"],
                "method": method,
                "params": params,
                "n_agents": n_agents,
                "arrival_rate": rate,
                "seed": seed,
            }
        )
    return jobs


def run_job(job: dict) -> dict:
    """Build the grid, task stream, cost model and planner; simulate; return
    ``RunResult.to_row()``. Must also run the collision checker."""
    raise NotImplementedError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1, help="parallel worker processes")
    parser.add_argument("--dry-run", action="store_true", help="list jobs and exit")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)
    jobs = expand(config)

    if args.dry_run:
        for job in jobs:
            print(job)
        print(f"{len(jobs)} jobs")
        return

    raise NotImplementedError("run jobs with multiprocessing and write a CSV")


if __name__ == "__main__":
    main()
