"""Final-report tables and figures from the main, assignment and heavy-load runs.

Usage:
    python experiments/final_figures.py --out results/summary/final

reads results/final_{map}.csv, results/final_assignment_{map}.csv and
results/final_heavy_{map}.csv for both maps and writes

- final.md: every paired comparison (vs TP, forward vs backward, routing vs
  assignment, heavier load) with mean change, wins and Wilcoxon p-values;
- final_head_on.png: head-on encounters per task, M1-M5 vs TP;
- final_ablation.png: mean and p95 service time, routing only vs + S_ij;
- final_service_curve.png: mean service time vs number of agents, per map
  and task frequency (main and heavy-load runs);
- final_plan_time.png: planning time per timestep vs number of agents;
- final_table.tex: the main results table for the report.

Owner: member 1.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.analysis import METRICS, load_runs  # noqa: E402

MAPS = ["warehouse_small", "narrow_corridor"]
MAP_LABEL = {"warehouse_small": "warehouse_small", "narrow_corridor": "narrow_corridor"}
KEYS = ["n_agents", "arrival_rate", "seed"]
BASE = {"tp": "TP", "highway": "M1 Highway", "heatmap": "M2 Heatmap",
        "foresight": "M3", "foresight_st": "M4", "foresight_std": "M5"}
ROUTING = ["M1 Highway", "M2 Heatmap", "M3", "M4", "M5"]
TABLE_METRICS = ["service_time_mean", "service_time_p95", "service_time_max", "wait_fraction",
                 "head_on_per_task", "plan_time_mean_ms"]
SHORT = {"service_time_mean": "service", "service_time_p95": "p95", "service_time_max": "max",
         "wait_fraction": "wait", "head_on_per_task": "head-on", "plan_time_mean_ms": "ms/step"}
# Slots 1 and 2 of the dataviz reference palette (also the deck's chart colours).
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#1f2937", "#6b7280"
# Curves: categorical slots 1-7 in fixed order (validated with the dataviz
# validator; three slots are below 3:1 on white, so every line also gets its
# own marker and the numbers are tabulated in final.md).
CURVES = [("TP", "#2a78d6", "o"), ("M1 Highway", "#eb6834", "s"), ("M2 Heatmap", "#1baf7a", "^"),
          ("M3", "#eda100", "v"), ("M4", "#e87ba4", "D"), ("M5", "#008300", "P"),
          ("TP + S_ij", "#6250d6", "X")]


def short_name(row: pd.Series) -> str:
    name = BASE[row["method"]]
    if row.get("assignment") == "sij":
        name = name.split()[0] + " + S_ij"
    return name


def load(paths: list[Path]) -> pd.DataFrame:
    runs, excluded = load_runs(paths)
    if len(excluded):
        raise SystemExit(f"{len(excluded)} runs failed or did not finish: {excluded[['variant', *KEYS]].head()}")
    if "assignment" not in runs:
        runs["assignment"] = np.nan
    runs["name"] = runs.apply(short_name, axis=1)
    return runs


def compare(runs: pd.DataFrame, name: str, ref: str, metric: str) -> dict:
    """Pair ``name`` with ``ref`` on (agents, rate, seed): mean % change, its
    95% CI (t), number of pairs where ``name`` is better, Wilcoxon p."""
    a = runs[runs["name"] == name].set_index(KEYS)[metric]
    b = runs[runs["name"] == ref].set_index(KEYS)[metric]
    a, b = a.align(b, join="inner")
    x, r = a.to_numpy(float), b.to_numpy(float)
    ok = r != 0
    pct = (x[ok] - r[ok]) / r[ok] * 100
    diff = x - r
    lower = METRICS[metric].lower_is_better
    better = int(((diff < 0) if lower else (diff > 0)).sum())
    n = len(pct)
    ci = float(stats.t.ppf(0.975, n - 1) * pct.std(ddof=1) / math.sqrt(n)) if n > 1 else math.nan
    p = 1.0 if not diff.any() else float(stats.wilcoxon(diff).pvalue)
    return {"name": name, "ref": ref, "metric": metric, "n": len(x), "change": float(pct.mean()),
            "ci": ci, "better": better, "p": p}


def cell(c: dict) -> str:
    star = "*" if c["p"] < 0.05 else ""
    return f"{c['change']:+.1f}%{star} ({c['better']}/{c['n']})"


def md_table(runs: pd.DataFrame, names: list[str], ref: str, metrics: list[str]) -> str:
    lines = ["| vs " + ref + " | " + " | ".join(SHORT[m] for m in metrics) + " |",
             "|---|" + "---:|" * len(metrics)]
    for name in names:
        lines.append(f"| {name} | " + " | ".join(cell(compare(runs, name, ref, m)) for m in metrics) + " |")
    return "\n".join(lines)


def reference_line(runs: pd.DataFrame, name: str = "TP") -> str:
    r = runs[runs["name"] == name]
    return (f"{name} absolute means over {len(r)} runs: service {r.service_time_mean.mean():.1f}, "
            f"p95 {r.service_time_p95.mean():.1f}, max {r.service_time_max.mean():.0f}, "
            f"wait {r.wait_fraction.mean():.3f}, head-on/task {r.head_on_per_task.mean():.3f}, "
            f"{r.plan_time_mean_ms.mean():.2f} ms/step; {int(r.n_conflicts.sum())} conflicts.")


def bars(ax, groups: list[str], series: list[tuple[str, str, list[dict]]], ylabel: str) -> None:
    """Grouped bars of mean % change with 95% CI; hollow when p >= 0.05."""
    width = 0.8 / len(series)
    x = np.arange(len(groups))
    for k, (label, color, comps) in enumerate(series):
        pos = x - 0.4 + width * (k + 0.5)
        labelled = False
        for xi, c in zip(pos, comps):
            if c is None:
                continue
            sig = c["p"] < 0.05
            ax.bar(xi, c["change"], width * 0.92, color=color if sig else "white", edgecolor=color,
                   linewidth=1.2, label=None if labelled else label)
            labelled = True
            ax.errorbar(xi, c["change"], yerr=c["ci"], color=MUTED, linewidth=1, capsize=2)
    ax.axhline(0, color=INK, linewidth=0.8)
    ax.set_xticks(x, groups, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(colors=INK, labelsize=8)
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def header(fig, title: str, entries: list[tuple[str, str]]) -> None:
    """Title on the first line, a filled-swatch legend on the second."""
    fig.text(0.02, 0.985, title, fontsize=8.5, color=MUTED, ha="left", va="top")
    handles = [Patch(facecolor=c, edgecolor=c, label=label) for label, c in entries]
    fig.legend(handles=handles, frameon=False, fontsize=8, ncol=len(handles), loc="upper left",
               bbox_to_anchor=(0.01, 0.95))


def head_on_figure(main: dict[str, pd.DataFrame], out: Path) -> None:
    fig = Figure(figsize=(6.4, 3.0), dpi=200)
    ax = fig.add_subplot()
    series = [(MAP_LABEL[m], color, [compare(main[m], n, "TP", "head_on_per_task") for n in ROUTING])
              for m, color in zip(MAPS, [BLUE, ORANGE])]
    bars(ax, ROUTING, series, "head-on encounters per task\nvs TP (%)")
    header(fig, "Paired change vs TP, 90 pairs per map (hollow: p ≥ 0.05; whiskers: 95% CI)",
           [(MAP_LABEL[m], c) for m, c in zip(MAPS, [BLUE, ORANGE])])
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(out)


def ablation_figure(both: dict[str, pd.DataFrame], out: Path) -> None:
    groups = ["TP", "M3", "M4", "M5"]
    fig = Figure(figsize=(6.4, 4.6), dpi=200)
    axes = fig.subplots(2, 2, sharex=True)
    for col, m in enumerate(MAPS):
        for row, metric in enumerate(["service_time_mean", "service_time_p95"]):
            ax = axes[row][col]
            routing = [None] + [compare(both[m], g, "TP", metric) for g in groups[1:]]
            with_sij = [compare(both[m], f"{g} + S_ij", "TP", metric) for g in groups]
            bars(ax, groups, [("routing only", BLUE, routing), ("+ S_ij", ORANGE, with_sij)],
                 f"{METRICS[metric].label}\nvs TP (%)" if col == 0 else "")
            if row == 0:
                ax.set_title(MAP_LABEL[m], fontsize=9, color=INK)
    header(fig, "Paired change vs TP, 90 pairs per map (hollow: p ≥ 0.05; whiskers: 95% CI)",
           [("routing only", BLUE), ("+ S_ij", ORANGE)])
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out)


def curve_data(both: dict[str, pd.DataFrame], heavy: dict[str, pd.DataFrame], metric: str) -> pd.DataFrame:
    """Mean of ``metric`` per (map, method, rate, agents) over seeds."""
    frames = []
    for m in MAPS:
        d = pd.concat([both[m], heavy[m]], ignore_index=True)
        d = d[d["name"].isin([n for n, _, _ in CURVES])]
        g = d.groupby(["name", "arrival_rate", "n_agents"])[metric].mean().reset_index()
        g["map"] = m
        frames.append(g)
    return pd.concat(frames, ignore_index=True)


def style(ax) -> None:
    ax.tick_params(colors=INK, labelsize=8)
    ax.grid(color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def curve_legend(fig, y: float) -> None:
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=c, marker=mk, markersize=5, linewidth=2, label=n) for n, c, mk in CURVES]
    fig.legend(handles=handles, frameon=False, fontsize=7.5, ncol=len(handles), loc="upper left",
               bbox_to_anchor=(0.01, y), handlelength=1.6, columnspacing=1.0)


def service_curve_figure(data: pd.DataFrame, out: Path) -> None:
    rates = sorted(data["arrival_rate"].unique())
    fig = Figure(figsize=(7.0, 4.4), dpi=200)
    axes = fig.subplots(len(MAPS), len(rates), sharex=True)
    for i, m in enumerate(MAPS):
        for j, rate in enumerate(rates):
            ax = axes[i][j]
            for name, color, marker in CURVES:
                d = data[(data["map"] == m) & (data["name"] == name) & (data["arrival_rate"] == rate)]
                ax.plot(d["n_agents"], d["service_time_mean"], color=color, marker=marker, markersize=4,
                        linewidth=1.6, markeredgecolor="white", markeredgewidth=0.6)
            ax.set_ylim(0, ax.get_ylim()[1] * 1.08)
            ax.set_xticks([10, 30, 50, 80])
            style(ax)
            if i == 0:
                ax.set_title(f"{rate:g} tasks / step", fontsize=8.5, color=INK)
            if j == 0:
                ax.set_ylabel(f"{MAP_LABEL[m]}\nmean service time", fontsize=8)
            if i == len(MAPS) - 1:
                ax.set_xlabel("agents", fontsize=8)
    fig.text(0.02, 0.985, "Mean service time (timesteps), mean of 10 test seeds; "
             "80 agents only at 1 and 5 tasks/step", fontsize=8.5, color=MUTED, ha="left", va="top")
    curve_legend(fig, 0.955)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(out)


def plan_time_figure(data: pd.DataFrame, out: Path, rate: float = 5) -> None:
    fig = Figure(figsize=(6.4, 2.9), dpi=200)
    axes = fig.subplots(1, len(MAPS), sharey=True)
    for ax, m in zip(axes, MAPS):
        for name, color, marker in CURVES:
            d = data[(data["map"] == m) & (data["name"] == name) & (data["arrival_rate"] == rate)]
            ax.plot(d["n_agents"], d["plan_time_mean_ms"], color=color, marker=marker, markersize=4,
                    linewidth=1.6, markeredgecolor="white", markeredgewidth=0.6)
        ax.set_xticks([10, 30, 50, 80])
        ax.set_ylim(bottom=0)
        ax.set_title(MAP_LABEL[m], fontsize=8.5, color=INK)
        ax.set_xlabel("agents", fontsize=8)
        style(ax)
    axes[0].set_ylabel("planning time\n(ms per timestep)", fontsize=8)
    fig.text(0.02, 0.985, f"Planning time per timestep at {rate:g} tasks/step, mean of 10 test seeds",
             fontsize=8.5, color=MUTED, ha="left", va="top")
    curve_legend(fig, 0.94)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    fig.savefig(out)


def curve_table(data: pd.DataFrame, m: str, metric: str, fmt: str) -> str:
    d = data[data["map"] == m]
    cols = sorted({(r, n) for r, n in zip(d["arrival_rate"], d["n_agents"])})
    lines = ["| method | " + " | ".join(f"{n}a @ {r:g}" for r, n in cols) + " |", "|---|" + "---:|" * len(cols)]
    for name, _, _ in CURVES:
        e = d[d["name"] == name].set_index(["arrival_rate", "n_agents"])[metric]
        lines.append(f"| {name} | " + " | ".join(fmt.format(e[c]) if c in e.index else "" for c in cols) + " |")
    return "\n".join(lines)


def latex_table(main: dict[str, pd.DataFrame], both: dict[str, pd.DataFrame]) -> str:
    metrics = ["service_time_mean", "service_time_p95", "head_on_per_task", "wait_fraction"]
    head = " & ".join(f"\\multicolumn{{2}}{{c}}{{{h}}}" for h in ["Service time", "p95 service", "Head-on / task", "Wait fraction"])
    lines = [
        "% Generated by experiments/final_figures.py -- do not edit by hand.",
        "\\begin{tabular}{l" + "rr" * len(metrics) + "}",
        "\\toprule",
        f" & {head} \\\\",
        " & " + " & ".join(["W", "N"] * len(metrics)) + " \\\\",
        "\\midrule",
    ]

    def row(name: str, data: dict[str, pd.DataFrame]) -> str:
        cells = []
        for metric in metrics:
            for m in MAPS:
                c = compare(data[m], name, "TP", metric)
                txt = f"{c['change']:+.1f}".replace("-", "$-$")
                cells.append(txt + ("$^*$" if c["p"] < 0.05 else ""))
        return name.replace("S_ij", "$S_{ij}$") + " & " + " & ".join(cells) + " \\\\"

    lines += [row(n, main) for n in ROUTING]
    lines.append("\\midrule")
    lines += [row(f"{g} + S_ij", both) for g in ["TP", "M3", "M4", "M5"]]
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--out", type=Path, default=Path("results/summary/final"))
    args = parser.parse_args()
    main_runs = {m: load([args.results / f"final_{m}.csv"]) for m in MAPS}
    both = {m: load([args.results / f"final_{m}.csv", args.results / f"final_assignment_{m}.csv"]) for m in MAPS}
    heavy = {m: load([args.results / f"final_heavy_{m}.csv"]) for m in MAPS}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    service = curve_data(both, heavy, "service_time_mean")
    plan = curve_data(both, heavy, "plan_time_mean_ms")

    md = ["# Final results", "",
          "Produced by `python experiments/final_figures.py`. Test seeds 0-9; 10, 30 and 50 agents at",
          "0.2, 1 and 5 tasks/step (90 pairs per method and map) unless stated. Tuned parameters:",
          "`baseline_tuning.md` (M1, M2), `tune_foresight.md` (M3-M5), `tune_sij.md` (S_ij).",
          "Each cell: mean paired change, `*` = Wilcoxon signed-rank p < 0.05, (pairs better / pairs).", ""]
    for m in MAPS:
        md += [f"## {m}", "", reference_line(main_runs[m]), "",
               "### Path costs vs TP", "", md_table(main_runs[m], ROUTING, "TP", TABLE_METRICS), "",
               "### Looking forward vs looking backward (vs tuned M2 Heatmap)", "",
               md_table(main_runs[m], ["M3", "M4", "M5"], "M2 Heatmap", TABLE_METRICS), "",
               "### Direction term: M5 vs M4 (same rho, plus mu * c_opp)", "",
               md_table(main_runs[m], ["M5"], "M4", TABLE_METRICS), "",
               "### Routing vs assignment (vs TP)", "",
               md_table(both[m], ["TP + S_ij", "M3", "M3 + S_ij", "M4", "M4 + S_ij", "M5", "M5 + S_ij"], "TP",
                        TABLE_METRICS), "",
               "### What adding S_ij changes (each row vs the same routing without S_ij)", ""]
        lines = ["| | " + " | ".join(SHORT[x] for x in TABLE_METRICS) + " |", "|---|" + "---:|" * len(TABLE_METRICS)]
        for g in ["TP", "M3", "M4", "M5"]:
            lines.append(f"| {g} + S_ij vs {g} | " + " | ".join(cell(compare(both[m], f"{g} + S_ij", g, x))
                                                              for x in TABLE_METRICS) + " |")
        md += lines + ["", "### Heavier load: 80 agents at 1 and 5 tasks/step (20 pairs)", "",
                       reference_line(heavy[m]), "",
                       md_table(heavy[m], ROUTING, "TP", TABLE_METRICS), "",
                       md_table(heavy[m], ["M3", "M4", "M5"], "M2 Heatmap", TABLE_METRICS), "",
                       md_table(heavy[m], ["M5"], "M4", TABLE_METRICS), ""]
        md += ["### Mean service time by agents and frequency (table view of final_service_curve.png)", "",
               curve_table(service, m, "service_time_mean", "{:.1f}"), "",
               "### Planning time, ms per timestep (table view of final_plan_time.png)", "",
               curve_table(plan, m, "plan_time_mean_ms", "{:.2f}"), ""]
    Path(f"{args.out}.md").write_text("\n".join(md))
    head_on_figure(main_runs, Path(f"{args.out}_head_on.png"))
    ablation_figure(both, Path(f"{args.out}_ablation.png"))
    service_curve_figure(service, Path(f"{args.out}_service_curve.png"))
    plan_time_figure(plan, Path(f"{args.out}_plan_time.png"))
    Path(f"{args.out}_table.tex").write_text(latex_table(main_runs, both))
    print(f"wrote {args.out}.md, {args.out}_table.tex and the figures "
          f"{args.out}_{{head_on,ablation,service_curve,plan_time}}.png")


if __name__ == "__main__":
    main()
