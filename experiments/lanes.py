"""Lane-emergence studies (designs: results/summary/lanes.md, lanes_warehouse.md).

Usage:
    python experiments/lanes.py run --map narrow_corridor --out results/lanes --jobs 10
    python experiments/lanes.py summarize results/lanes --map narrow_corridor --out results/summary/lanes
    python experiments/lanes.py run --map warehouse_small --out results/lanes_warehouse --jobs 10
    python experiments/lanes.py summarize results/lanes_warehouse --map warehouse_small --out results/summary/lanes_warehouse

``run`` simulates every (method, agents, rate, seed), keeps the trajectories
in memory only, and writes <out>_runs.csv (one row per run) and
<out>_series.csv (majority moves per 50-step window). ``summarize`` writes
the tables, paired tests and figures into the Results section of <out>.md
(everything above it, the design and any findings, is kept). Owner: member 3.
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
from foresight.lanes import (  # noqa: E402
    NARROW_CORRIDOR_COLS,
    NARROW_CORRIDOR_ROWS,
    WAREHOUSE_AISLE_ROWS,
    WAREHOUSE_BANDS,
    WAREHOUSE_COLS,
    corridor_moves,
    flip_rate,
    lane_share,
    window_counts,
)
from foresight.sim.instance import make_instance  # noqa: E402
from foresight.sim.metrics import RunResult  # noqa: E402
from foresight.sim.simulator import Simulator  # noqa: E402

N_TASKS = 500
AGENTS = [30, 50]
RATES = [1, 5]
SEEDS = list(range(10))  # test seeds
WINDOWS = [25, 50, 100]
SERIES_WINDOW = 50

# Per map: corridors, methods (label -> (method, params), see each design's
# Methods table), tables, the metric the hypotheses are tested on, and tests.
STUDIES = {
    "narrow_corridor": {
        "rows": NARROW_CORRIDOR_ROWS,
        "cols": NARROW_CORRIDOR_COLS,
        "bands": None,
        "methods": {
            "TP": ("tp", {}),
            "Highway": ("highway", {"w_h": 1.2, "directions": "maps/narrow_corridor.highway.json"}),
            "M4": ("foresight_st", {"lam": 0.5, "delta": 2}),
            "M5": ("foresight_std", {"lam": 0.5, "delta": 2, "mu": 0.5, "delta_dir": 2}),
            "M5-dir": ("foresight_std", {"lam": 0.0, "delta": 2, "mu": 0.5, "delta_dir": 2}),
        },
        "tables": [
            ("lane_share_50", "Lane share L (window 50; 0.5 = balanced, 1 = one-way)", "{:.3f}"),
            ("head_on_per_task", "Head-on encounters per task", "{:.3f}"),
            ("flip_rate_50", "Flip rate (window 50)", "{:.3f}"),
            ("lane_share_25", "Lane share, window 25", "{:.3f}"),
            ("lane_share_100", "Lane share, window 100", "{:.3f}"),
            ("service_time_mean", "Mean service time", "{:.1f}"),
            ("wait_fraction", "Wait fraction", "{:.3f}"),
        ],
        "tested": [("lane_share_50", "L (window 50)")],
        "tests": [("M5", "M4", "H1"), ("M5-dir", "TP", "H2"), ("M4", "TP", "H3")],
        "bar": ("lane_share_50", "Lane share L (window 50)", (0.5, 1.0)),
    },
    "warehouse_small": {
        "rows": tuple(WAREHOUSE_BANDS),
        "cols": WAREHOUSE_COLS,
        "bands": WAREHOUSE_BANDS,
        "methods": {
            "TP": ("tp", {}),
            "Highway": ("highway", {"w_h": 1.5, "directions": "maps/warehouse_small.highway.json"}),
            "M4": ("foresight_st", {"lam": 2.0, "delta": 10}),
            "M5": ("foresight_std", {"lam": 2.0, "delta": 10, "mu": 4.0, "delta_dir": 2}),
            "M5-dir": ("foresight_std", {"lam": 0.0, "delta": 10, "mu": 0.5, "delta_dir": 2}),
        },
        "tables": [
            ("segregation_50", "Segregation S = L_row - L_band (window 50)", "{:.3f}"),
            ("lane_share_row_50", "L_row (each row its own corridor, window 50)", "{:.3f}"),
            ("lane_share_band_50", "L_band (each 3-row band one corridor, window 50)", "{:.3f}"),
            ("head_on_per_task", "Head-on encounters per task", "{:.3f}"),
            ("middle_row_share", "Share of band moves on the middle (aisle) row", "{:.3f}"),
            ("flip_rate_50", "Flip rate per row (window 50)", "{:.3f}"),
            ("segregation_25", "Segregation, window 25", "{:.3f}"),
            ("segregation_100", "Segregation, window 100", "{:.3f}"),
            ("service_time_mean", "Mean service time", "{:.1f}"),
            ("wait_fraction", "Wait fraction", "{:.3f}"),
        ],
        "tested": [("segregation_50", "S (window 50)"), ("lane_share_row_50", "L_row (window 50)")],
        "tests": [("M5", "M4", "W1"), ("M5-dir", "TP", "W2"), ("M4", "TP", "W3")],
        "bar": ("segregation_50", "Segregation S (window 50)", None),
    },
}
COLORS = {"TP": "#52514e", "Highway": "#b3b1aa", "M4": "#2a78d6", "M5": "#eb6834", "M5-dir": "#1baf7a"}


def run_one(job: tuple[str, str, int, int, int]) -> tuple[dict, list[dict]]:
    map_name, label, n_agents, rate, seed = job
    study = STUDIES[map_name]
    method, params = study["methods"][label]
    grid = _grid(f"maps/{map_name}.map")
    instance = make_instance(grid, n_agents, N_TASKS, rate, seed)
    log = Simulator(instance, planners()["tp"](), build_cost_model(method, params, grid)).run(check=False)
    result = log.to_result(RunResult(method, map_name, n_agents, rate, seed, params))
    moves = corridor_moves(log.paths, study["rows"], study["cols"])
    key = {"label": label, "n_agents": n_agents, "arrival_rate": rate, "seed": seed}
    row = {**key}
    bands = study["bands"]
    if bands is None:
        row.update({f"lane_share_{w}": lane_share(moves, w) for w in WINDOWS})
    else:
        for w in WINDOWS:
            l_row, l_band = lane_share(moves, w), lane_share(moves, w, bands)
            row.update({f"lane_share_row_{w}": l_row, f"lane_share_band_{w}": l_band, f"segregation_{w}": l_row - l_band})
        row["middle_row_share"] = sum(m.row in WAREHOUSE_AISLE_ROWS for m in moves) / len(moves) if moves else np.nan
    row.update({
        "flip_rate_50": flip_rate(moves, 50),
        "corridor_moves": len(moves),
        "head_on_per_task": result.head_on_per_task,
        "service_time_mean": result.service_time_mean,
        "wait_fraction": result.wait_fraction,
        "completed": log.completed,
        "n_conflicts": result.n_conflicts,
    })
    per_window: dict[int, dict] = {}
    for (_, k), (e, w) in window_counts(moves, SERIES_WINDOW).items():
        d = per_window.setdefault(k, {"majority": 0, "majority_band": 0, "moves": 0})
        d["majority"] += max(e, w)
        d["moves"] += e + w
    for (_, k), (e, w) in window_counts(moves, SERIES_WINDOW, bands).items():
        per_window[k]["majority_band"] += max(e, w)
    series = [{**key, "window": k, **d} for k, d in sorted(per_window.items())]
    return row, series


def cmd_run(args: argparse.Namespace) -> None:
    jobs = list(itertools.product([args.map], STUDIES[args.map]["methods"], AGENTS, RATES, SEEDS))
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


def mean_ci(v: pd.Series) -> tuple[float, float]:
    v = v.dropna()
    return v.mean(), 1.96 * v.std(ddof=1) / np.sqrt(len(v))


def cmd_summarize(args: argparse.Namespace) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    study = STUDIES[args.map]
    order = list(study["methods"])
    runs = pd.read_csv(f"{args.prefix}_runs.csv")
    series = pd.read_csv(f"{args.prefix}_series.csv")
    bad = runs[~runs["completed"] | (runs["n_conflicts"] != 0)]
    if len(bad):
        sys.exit(f"{len(bad)} runs incomplete or conflicting; fix before summarizing")
    configs = sorted(runs.groupby(["n_agents", "arrival_rate"]).groups)
    cmd = f"python experiments/lanes.py summarize {args.prefix} --map {args.map} --out {args.out}"

    lines = ["", "# Results", "", f"Test seeds 0-9, {len(runs)} runs, all complete with 0 conflicts. "
             f"Produced by `{cmd}`.", ""]
    for metric, label, fmt in study["tables"]:
        lines += [f"## {label}", "", "| agents | rate | " + " | ".join(order) + " |",
                  "|---:|---:|" + "---:|" * len(order)]
        for n, r in configs:
            sub = runs[(runs.n_agents == n) & (runs.arrival_rate == r)]
            cells = []
            for lab in order:
                m, ci = mean_ci(sub[sub.label == lab][metric])
                cells.append(f"{fmt.format(m)} ± {fmt.format(ci)}")
            lines.append(f"| {n} | {r} | " + " | ".join(cells) + " |")
        lines.append("")

    for metric, name in study["tested"]:
        lines += [f"## Paired tests on {name}", "",
                  "Wilcoxon signed-rank, two-sided, paired by (agents, rate, seed). "
                  "\"a higher\" = pairs where the first method's value is higher.", "",
                  "| hypothesis | comparison | configuration | pairs | mean difference | a higher | p |",
                  "|---|---|---|---:|---:|---:|---:|"]
        for a, b, h in study["tests"]:
            scopes = [("pooled", runs)] + [
                (f"{n} agents, rate {r}", runs[(runs.n_agents == n) & (runs.arrival_rate == r)]) for n, r in configs
            ]
            for scope, sub in scopes:
                t = paired(sub, a, b, metric)
                lines.append(f"| {h} | {a} vs {b} | {scope} | {t['n']} | {t['mean_diff']:+.4f} | "
                             f"{t['a_better']}/{t['n']} | {t['p']:.3g} |")
        lines.append("")

    # Figures: the primary metric and head-on per configuration; the primary metric over time.
    bar_metric, bar_title, bar_ylim = study["bar"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    x = np.arange(len(configs))
    width = 0.16
    for k, lab in enumerate(order):
        for ax, metric in zip(axes, [bar_metric, "head_on_per_task"]):
            stats = [mean_ci(runs[(runs.label == lab) & (runs.n_agents == n) & (runs.arrival_rate == r)][metric])
                     for n, r in configs]
            ax.bar(x + (k - 2) * width, [s[0] for s in stats], width, yerr=[s[1] for s in stats],
                   color=COLORS[lab], label=lab, capsize=2)
    for ax, title in zip(axes, [bar_title, "Head-on encounters per task"]):
        ax.set_xticks(x, [f"{n} agents\nrate {r}" for n, r in configs])
        ax.set_title(title, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
    if bar_ylim:
        axes[0].set_ylim(*bar_ylim)
    axes[0].legend(frameon=False, ncol=5, fontsize=8, loc="upper left")
    fig.tight_layout()
    bars = args.out.parent / f"{args.out.name}_bars.png"
    fig.savefig(bars, dpi=150)

    n, r = configs[-1]
    banded = study["bands"] is not None
    fig, ax = plt.subplots(figsize=(6, 3.4))
    for lab in order:
        s = series[(series.label == lab) & (series.n_agents == n) & (series.arrival_rate == r)]
        agg = s.groupby("window")[["majority", "majority_band", "moves"]].sum()
        # Skip sparse windows (start-up, the tail after the last tasks): few moves push L up.
        agg = agg[agg["moves"] >= 0.5 * agg["moves"].median()]
        y = (agg["majority"] - agg["majority_band"]) / agg["moves"] if banded else agg["majority"] / agg["moves"]
        ax.plot(agg.index * SERIES_WINDOW, y, color=COLORS[lab], label=lab, lw=1.6)
    ax.set_xlabel("timestep")
    ax.set_ylabel("segregation S" if banded else "lane share L")
    ax.set_title(f"{'S' if banded else 'L'} per {SERIES_WINDOW}-step window, {n} agents, rate {r} "
                 "(pooled over seeds)", loc="left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, ncol=5)
    fig.tight_layout()
    over_time = args.out.parent / f"{args.out.name}_over_time.png"
    fig.savefig(over_time, dpi=150)

    lines += ["## Figures", "", f"![bars]({bars.name})", "", f"![over time]({over_time.name})", ""]
    md = args.out.with_suffix(".md")
    head = md.read_text(encoding="utf-8").split("\n# Results\n")[0].rstrip("\n")
    md.write_text(head + "\n" + "\n".join(lines), encoding="utf-8")  # replaces an earlier Results section
    print(f"wrote results to {md}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--map", choices=sorted(STUDIES), required=True)
    p.add_argument("--out", type=Path, required=True, help="output prefix, e.g. results/lanes")
    p.add_argument("--jobs", type=int, default=1)
    p.set_defaults(func=cmd_run)
    s = sub.add_parser("summarize")
    s.add_argument("prefix", help="prefix given to run, e.g. results/lanes")
    s.add_argument("--map", choices=sorted(STUDIES), required=True)
    s.add_argument("--out", type=Path, required=True, help="e.g. results/summary/lanes (rewrites its Results section)")
    s.set_defaults(func=cmd_summarize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
