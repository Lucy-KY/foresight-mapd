"""Lane-emergence study on narrow_corridor (design: results/summary/lanes.md).

Usage:
    python experiments/lanes.py run --out results/lanes --jobs 10
    python experiments/lanes.py summarize results/lanes --out results/summary/lanes

``run`` simulates every (method, agents, rate, seed), keeps the trajectories
in memory only, and writes <out>_runs.csv (one row per run) and
<out>_series.csv (lane share per 50-step window). ``summarize`` writes the
tables, paired tests and figures into the Results section of
<out>.md (everything above it, the design, is kept). Owner: member 3.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.experiment import _grid, build_cost_model, planners  # noqa: E402
from foresight.lanes import corridor_moves, flip_rate, lane_share, lane_share_series  # noqa: E402
from foresight.sim.instance import make_instance  # noqa: E402
from foresight.sim.metrics import RunResult  # noqa: E402
from foresight.sim.simulator import Simulator  # noqa: E402

MAP = "maps/narrow_corridor.map"
N_TASKS = 500
AGENTS = [30, 50]
RATES = [1, 5]
SEEDS = list(range(10))  # test seeds
WINDOWS = [25, 50, 100]
# label -> (method, params); see the Methods table in results/summary/lanes.md
METHODS = {
    "TP": ("tp", {}),
    "Highway": ("highway", {"w_h": 1.2, "directions": "maps/narrow_corridor.highway.json"}),
    "M4": ("foresight_st", {"lam": 0.5, "delta": 2}),
    "M5": ("foresight_std", {"lam": 0.5, "delta": 2, "mu": 0.5, "delta_dir": 2}),
    "M5-dir": ("foresight_std", {"lam": 0.0, "delta": 2, "mu": 0.5, "delta_dir": 2}),
}
ORDER = list(METHODS)
TESTS = [("M5", "M4", "H1"), ("M5-dir", "TP", "H2"), ("M4", "TP", "H3")]


def run_one(job: tuple[str, int, int, int]) -> tuple[dict, list[dict]]:
    label, n_agents, rate, seed = job
    method, params = METHODS[label]
    grid = _grid(MAP)
    instance = make_instance(grid, n_agents, N_TASKS, rate, seed)
    log = Simulator(instance, planners()["tp"](), build_cost_model(method, params, grid)).run(check=False)
    result = log.to_result(RunResult(method, "narrow_corridor", n_agents, rate, seed, params))
    moves = corridor_moves(log.paths)
    key = {"label": label, "n_agents": n_agents, "arrival_rate": rate, "seed": seed}
    row = {
        **key,
        **{f"lane_share_{w}": lane_share(moves, w) for w in WINDOWS},
        "flip_rate_50": flip_rate(moves, 50),
        "corridor_moves": len(moves),
        "head_on_per_task": result.head_on_per_task,
        "service_time_mean": result.service_time_mean,
        "wait_fraction": result.wait_fraction,
        "completed": log.completed,
        "n_conflicts": result.n_conflicts,
    }
    series = [{**key, "window": k, "majority": a, "moves": b} for k, (a, b) in lane_share_series(moves, 50).items()]
    return row, series


def cmd_run(args: argparse.Namespace) -> None:
    jobs = list(itertools.product(ORDER, AGENTS, RATES, SEEDS))
    with Pool(args.jobs) as pool:
        out = pool.map(run_one, jobs, chunksize=1)
    runs = pd.DataFrame([r for r, _ in out])
    series = pd.DataFrame([s for _, ss in out for s in ss])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    runs.to_csv(f"{args.out}_runs.csv", index=False)
    series.to_csv(f"{args.out}_series.csv", index=False)
    bad = runs[~runs["completed"] | (runs["n_conflicts"] != 0)]
    print(f"{len(runs)} runs, {len(bad)} incomplete or conflicting -> {args.out}_runs.csv")


def paired(runs: pd.DataFrame, a: str, b: str, metric: str) -> dict:
    from scipy.stats import wilcoxon

    keys = ["n_agents", "arrival_rate", "seed"]
    x = runs[runs["label"] == a].set_index(keys)[metric]
    y = runs[runs["label"] == b].set_index(keys)[metric].reindex(x.index)
    d = (x - y).dropna()
    p = wilcoxon(d).pvalue if len(d) and (d != 0).any() else 1.0
    return {"n": len(d), "mean_diff": d.mean(), "a_better": int((d > 0).sum()), "p": p}


def cmd_summarize(args: argparse.Namespace) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = pd.read_csv(f"{args.prefix}_runs.csv")
    series = pd.read_csv(f"{args.prefix}_series.csv")
    bad = runs[~runs["completed"] | (runs["n_conflicts"] != 0)]
    if len(bad):
        sys.exit(f"{len(bad)} runs incomplete or conflicting; fix before summarizing")
    configs = sorted(runs.groupby(["n_agents", "arrival_rate"]).groups)

    def mean_ci(v):
        v = v.dropna()
        return v.mean(), 1.96 * v.std(ddof=1) / np.sqrt(len(v))

    lines = ["", "# Results", "", "Test seeds 0-9, 200 runs, all complete with 0 conflicts. "
             "Produced by `python experiments/lanes.py summarize results/lanes --out results/summary/lanes`.", ""]
    for metric, label, fmt in [
        ("lane_share_50", "Lane share L (window 50; 0.5 = balanced, 1 = one-way)", "{:.3f}"),
        ("head_on_per_task", "Head-on encounters per task", "{:.3f}"),
        ("flip_rate_50", "Flip rate (window 50)", "{:.3f}"),
        ("lane_share_25", "Lane share, window 25", "{:.3f}"),
        ("lane_share_100", "Lane share, window 100", "{:.3f}"),
        ("service_time_mean", "Mean service time", "{:.1f}"),
        ("wait_fraction", "Wait fraction", "{:.3f}"),
    ]:
        lines += [f"## {label}", "", "| agents | rate | " + " | ".join(ORDER) + " |",
                  "|---:|---:|" + "---:|" * len(ORDER)]
        for n, r in configs:
            sub = runs[(runs.n_agents == n) & (runs.arrival_rate == r)]
            cells = []
            for lab in ORDER:
                m, ci = mean_ci(sub[sub.label == lab][metric])
                cells.append(f"{fmt.format(m)} ± {fmt.format(ci)}")
            lines.append(f"| {n} | {r} | " + " | ".join(cells) + " |")
        lines.append("")

    lines += ["## Paired tests on L (window 50)", "",
              "Wilcoxon signed-rank, two-sided, paired by (agents, rate, seed). "
              "\"a higher\" = pairs where the first method's L is higher.", "",
              "| hypothesis | comparison | configuration | pairs | mean difference in L | a higher | p |",
              "|---|---|---|---:|---:|---:|---:|"]
    for a, b, h in TESTS:
        scopes = [("pooled", runs)] + [(f"{n} agents, rate {r}", runs[(runs.n_agents == n) & (runs.arrival_rate == r)])
                                       for n, r in configs]
        for name, sub in scopes:
            t = paired(sub, a, b, "lane_share_50")
            lines.append(f"| {h} | {a} vs {b} | {name} | {t['n']} | {t['mean_diff']:+.4f} | "
                         f"{t['a_better']}/{t['n']} | {t['p']:.3g} |")
    lines.append("")

    # Figures: L and head-on per configuration; L over time at the heaviest load.
    colors = {"TP": "#52514e", "Highway": "#b3b1aa", "M4": "#2a78d6", "M5": "#eb6834", "M5-dir": "#1baf7a"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    x = np.arange(len(configs))
    width = 0.16
    for k, lab in enumerate(ORDER):
        for ax, metric in zip(axes, ["lane_share_50", "head_on_per_task"]):
            stats = [mean_ci(runs[(runs.label == lab) & (runs.n_agents == n) & (runs.arrival_rate == r)][metric])
                     for n, r in configs]
            ax.bar(x + (k - 2) * width, [s[0] for s in stats], width, yerr=[s[1] for s in stats],
                   color=colors[lab], label=lab, capsize=2)
    for ax, title in zip(axes, ["Lane share L (window 50)", "Head-on encounters per task"]):
        ax.set_xticks(x, [f"{n} agents\nrate {r}" for n, r in configs])
        ax.set_title(title, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylim(0.5, 1.0)
    axes[0].legend(frameon=False, ncol=5, fontsize=8, loc="upper left")
    fig.tight_layout()
    bars = args.out.parent / f"{args.out.name}_bars.png"
    fig.savefig(bars, dpi=150)

    n, r = configs[-1]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    for lab in ORDER:
        s = series[(series.label == lab) & (series.n_agents == n) & (series.arrival_rate == r)]
        agg = s.groupby("window")[["majority", "moves"]].sum()
        # Skip sparse windows (start-up, the tail after the last tasks): few moves push L up.
        agg = agg[agg["moves"] >= 0.5 * agg["moves"].median()]
        ax.plot(agg.index * 50, agg["majority"] / agg["moves"], color=colors[lab], label=lab, lw=1.6)
    ax.set_xlabel("timestep")
    ax.set_ylabel("lane share L")
    ax.set_title(f"L per 50-step window, {n} agents, rate {r} (pooled over seeds)", loc="left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, ncol=5)
    fig.tight_layout()
    over_time = args.out.parent / f"{args.out.name}_over_time.png"
    fig.savefig(over_time, dpi=150)

    lines += ["## Figures", "", f"![bars]({bars.name})", "", f"![over time]({over_time.name})", ""]
    md = args.out.with_suffix(".md")
    design = md.read_text(encoding="utf-8").split("\n# Results\n")[0].rstrip("\n")
    md.write_text(design + "\n" + "\n".join(lines), encoding="utf-8")  # replaces an earlier Results section
    print(f"wrote results to {md}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--out", type=Path, required=True, help="output prefix, e.g. results/lanes")
    p.add_argument("--jobs", type=int, default=1)
    p.set_defaults(func=cmd_run)
    s = sub.add_parser("summarize")
    s.add_argument("prefix", help="prefix given to run, e.g. results/lanes")
    s.add_argument("--out", type=Path, required=True, help="e.g. results/summary/lanes (appends to lanes.md)")
    s.set_defaults(func=cmd_summarize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
