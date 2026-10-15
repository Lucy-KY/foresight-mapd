"""Member 2's experiments: TP / TPTS reproduction and M1 / M2 baselines.

Usage:
    python experiments/baselines.py repro   --jobs 8   # TP + TPTS on the Ma et al. grid
    python experiments/baselines.py sweep   --jobs 8   # tune w_h, lam, eta on tuning seeds
    python experiments/baselines.py midterm --jobs 8   # M0 / M1 / M2 on the mid-term subset
    python experiments/baselines.py summarize          # tables and figures in results/summary/

Raw rows go to ``results/<command>.csv`` (git-ignored) and are resumable:
jobs already in the CSV are skipped. This is a stop-gap until
``experiments/run.py`` (member 1) runs jobs; it builds the same objects.

Owner: member 2.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import subprocess
import time
import tomllib
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SUMMARY = RESULTS / "summary"

TUNING_SEEDS = [100, 101, 102, 103, 104]
SWEEP_CONFIGS = [(30, 1), (30, 5)]  # (agents, arrival rate): medium difficulty
SWEEP_GRID = {
    "highway": [{"w_h": w} for w in (1.2, 1.5, 2, 3)],
    "heatmap": [{"lam": lam, "eta": eta} for lam in (0.5, 1, 2, 4) for eta in (0.95, 0.99)],
}
MAPS = ["warehouse_small", "narrow_corridor"]


# --------------------------------------------------------------------------- jobs


def make_cost(method: str, params: dict, map_name: str, grid):
    from foresight.costs import HeatmapCost, HighwayCost, UnitCost

    if method == "tp":
        return UnitCost()
    if method == "highway":
        return HighwayCost.from_file(ROOT / "maps" / f"{map_name}.highway.json", grid, params["w_h"])
    if method == "heatmap":
        return HeatmapCost(params["lam"], params.get("eta", 0.99))
    raise ValueError(f"unknown method {method}")


def run_job(job: dict) -> dict:
    from foresight.planner.tp import TokenPassing
    from foresight.planner.tpts import TokenPassingWithSwaps
    from foresight.sim.grid import GridMap
    from foresight.sim.instance import make_instance
    from foresight.sim.metrics import RunResult
    from foresight.sim.simulator import Simulator

    grid = GridMap.load(ROOT / "maps" / f"{job['map']}.map")
    inst = make_instance(grid, job["n_agents"], job["n_tasks"], job["arrival_rate"], job["seed"])
    planner = TokenPassingWithSwaps() if job["planner"] == "tpts" else TokenPassing()
    cost = make_cost(job["method"], job["params"], job["map"], grid)
    start = time.perf_counter()
    log = Simulator(inst, planner, cost, max_timesteps=job.get("max_timesteps", 20_000)).run()
    result = RunResult(job["method"], job["map"], job["n_agents"], job["arrival_rate"], job["seed"], job["params"])
    row = {k: v for k, v in log.to_result(result).to_row().items() if not k.startswith("param_")}
    row.update(planner=job["planner"], params=json.dumps(job["params"], sort_keys=True),
               wall_s=round(time.perf_counter() - start, 2), commit=job["commit"])
    return row


def job_key(job: dict) -> tuple:
    params = job["params"] if isinstance(job["params"], str) else json.dumps(job["params"], sort_keys=True)
    map_name = job.get("map") or job["map_name"]  # job dict or a row read back from the CSV
    return (job["planner"], job["method"], params, map_name, int(job["n_agents"]),
            float(job["arrival_rate"]), int(job["seed"]))


def run_all(jobs: list[dict], out: Path, n_procs: int) -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True, cwd=ROOT).stdout.strip()
    done = set()
    if out.exists():
        with open(out, newline="") as f:
            done = {job_key(r) for r in csv.DictReader(f)}
    todo = [dict(j, commit=commit) for j in jobs if job_key(j) not in done]
    print(f"{len(jobs)} jobs, {len(jobs) - len(todo)} already in {out}, running {len(todo)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = None
    if out.exists() and done:
        with open(out, newline="") as f:
            fields = next(csv.reader(f))
    with open(out, "a", newline="") as f, Pool(n_procs) as pool:
        writer = None
        for k, row in enumerate(pool.imap_unordered(run_job, todo), 1):
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=fields or list(row), extrasaction="ignore")
                if not fields:
                    writer.writeheader()
            writer.writerow(row)
            f.flush()
            ok = "ok" if row["tasks_completed"] == row["n_tasks"] and row["n_conflicts"] == 0 else "INCOMPLETE"
            print(f"[{k}/{len(todo)}] {row['planner']} {row['method']} {row['params']} {row['map_name']} "
                  f"a={row['n_agents']} f={row['arrival_rate']} s={row['seed']} "
                  f"st={row['service_time_mean']:.1f} {row['wall_s']}s {ok}", flush=True)


def grid_jobs(config: Path, planners, methods: dict[str, list[dict]], maps=None, seeds=None) -> list[dict]:
    with open(config, "rb") as f:
        cfg = tomllib.load(f)
    maps = maps or [Path(cfg["map"]).stem]
    seeds = seeds or cfg["seeds"]
    jobs = []
    for planner, (method, plist), m, a, r, s in itertools.product(
        planners, methods.items(), maps, cfg["agents"], cfg["arrival_rates"], seeds
    ):
        for params in plist:
            jobs.append(dict(planner=planner, method=method, params=params, map=m, n_agents=a,
                             arrival_rate=r, seed=s, n_tasks=cfg["n_tasks"]))
    return jobs


def best_params() -> dict[tuple[str, str], dict]:
    """(map, method) -> params with the lowest mean service time in the sweep."""
    import pandas as pd

    df = pd.read_csv(RESULTS / "sweep.csv")
    df = df[df.tasks_completed == df.n_tasks]
    means = df.groupby(["map_name", "method", "params"]).service_time_mean.mean().reset_index()
    best = means.loc[means.groupby(["map_name", "method"]).service_time_mean.idxmin()]
    return {(r.map_name, r.method): json.loads(r.params) for r in best.itertuples()}


# ---------------------------------------------------------------------- commands


def cmd_repro(args) -> None:
    jobs = grid_jobs(ROOT / "experiments/configs/ma2017_small.toml", args.planners.split(","), {"tp": [{}]})
    run_all(jobs, RESULTS / "repro.csv", args.jobs)


def cmd_sweep(args) -> None:
    jobs = []
    for (method, plist), m, (a, r), s in itertools.product(
        SWEEP_GRID.items(), MAPS, SWEEP_CONFIGS, TUNING_SEEDS
    ):
        for params in plist:
            jobs.append(dict(planner="tp", method=method, params=params, map=m, n_agents=a,
                             arrival_rate=r, seed=s, n_tasks=500))
    for m, (a, r), s in itertools.product(MAPS, SWEEP_CONFIGS, TUNING_SEEDS):
        jobs.append(dict(planner="tp", method="tp", params={}, map=m, n_agents=a,
                         arrival_rate=r, seed=s, n_tasks=500))
    run_all(jobs, RESULTS / "sweep.csv", args.jobs)


def cmd_midterm(args) -> None:
    best = best_params()
    jobs = []
    for m in MAPS:
        methods = {"tp": [{}], "highway": [best[(m, "highway")]], "heatmap": [best[(m, "heatmap")]]}
        jobs += grid_jobs(ROOT / "experiments/configs/ma2017_midterm.toml", ["tp"], methods, maps=[m])
    run_all(jobs, RESULTS / "midterm_baselines.csv", args.jobs)


def cmd_summarize(args) -> None:
    import summarize_baselines

    summarize_baselines.main(RESULTS, SUMMARY, ROOT / "experiments/ma2017_table1.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("repro", cmd_repro), ("sweep", cmd_sweep), ("midterm", cmd_midterm),
                     ("summarize", cmd_summarize)]:
        p = sub.add_parser(name)
        p.add_argument("--jobs", type=int, default=4, help="parallel worker processes")
        p.set_defaults(fn=fn)
        if name == "repro":
            p.add_argument("--planners", default="tp,tpts")
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
