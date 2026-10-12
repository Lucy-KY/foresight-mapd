"""Run every job of an experiment config and write one CSV row per run.

Usage:
    python experiments/run.py experiments/configs/smoke.toml --out results/smoke.csv --jobs 4

Re-running with the same --out skips jobs that already succeeded and
retries failed ones. Owner: member 1; the logic lives in
``foresight/experiment.py``.
"""

from __future__ import annotations

import argparse
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.experiment import expand, run_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1, help="parallel worker processes")
    parser.add_argument("--dry-run", action="store_true", help="list jobs and exit")
    parser.add_argument("--no-resume", action="store_true", help="start the CSV over")
    parser.add_argument("--limit", type=int, help="run at most this many jobs (for timing)")
    args = parser.parse_args()

    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    if args.dry_run:
        jobs = expand(config)
        for job in jobs:
            print(job)
        print(f"{len(jobs)} jobs")
        return

    start = time.perf_counter()
    summary = run_all(config, args.out, n_workers=args.jobs, resume=not args.no_resume, limit=args.limit)
    elapsed = time.perf_counter() - start
    print(
        f"{summary['ran']} ran, {summary['skipped']} skipped (already done), "
        f"{summary['failed']} failed, {summary['total']} jobs in config; {elapsed:.1f}s -> {args.out}"
    )
    if summary["ran"] and summary["ran"] < summary["total"] - summary["skipped"]:
        per_job = elapsed / summary["ran"]
        remaining = summary["total"] - summary["skipped"] - summary["ran"]
        print(f"about {per_job:.1f}s per job here; {remaining} left, ~{per_job * remaining / 60:.0f} min at --jobs {args.jobs}")


if __name__ == "__main__":
    main()
