"""Tables and figures for member 2's experiments (see baselines.py).

Owner: member 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Reference categorical palette, slots 1-3 (validated all-pairs, light mode).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 10, "axes.titleweight": "bold", "legend.frameon": False,
})


def ci95(x: pd.Series) -> float:
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    bad = df[(df.tasks_completed != df.n_tasks) | (df.n_conflicts != 0)]
    if len(bad):
        print(f"warning: dropping {len(bad)} incomplete or conflicting runs from {path.name}")
    return df.drop(bad.index)


def small_multiples(panels, series, ylabel, title, out: Path, ncols=3, baseline=None):
    """panels: list of (panel title, {series name: (x, y, err)}). Colors follow
    the position in ``series``. With ``baseline`` (a label), y is a change
    relative to that baseline, drawn as a line at 0."""
    nrows = int(np.ceil(len(panels) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 2.6 * nrows + 0.7), squeeze=False)
    for ax, (ptitle, lines) in zip(axes.flat, panels):
        for k, name in enumerate(series):
            if name not in lines:
                continue
            x, y, err = lines[name]
            ax.plot(x, y, color=SERIES[k], lw=2, marker="o", ms=5, mec=SURFACE, mew=1.5, label=name)
            if err is not None:
                ax.fill_between(x, np.array(y) - err, np.array(y) + err, color=SERIES[k], alpha=0.12, lw=0)
        ax.set_title(ptitle, loc="left", color=INK)
        ax.set_xlabel("agents")
        if baseline is None:
            ax.set_ylim(bottom=0)
        else:
            ax.axhline(0, color=INK_2, lw=1.2, ls="--", label=baseline, zorder=1)
    for ax in axes.flat[len(panels):]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.suptitle(title, x=0.01, y=0.99, ha="left", va="top", fontweight="bold", fontsize=12)
    h = fig.get_figheight()  # title, then legend, then panels, spaced in inches
    fig.legend(handles, labels, loc="upper left", ncol=len(labels), bbox_to_anchor=(0.005, 1 - 0.3 / h))
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.65 / h))
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"wrote {out}")


def reproduction(results: Path, summary: Path, table1: Path) -> None:
    df = load(results / "repro.csv")
    paper = pd.read_csv(table1, comment="#")
    agg = (df.groupby(["planner", "arrival_rate", "n_agents"])
             .agg(makespan=("makespan", "mean"), st=("service_time_mean", "mean"),
                  st_ci=("service_time_mean", ci95), plan_ms=("plan_time_mean_ms", "mean"),
                  runs=("seed", "count"))
             .reset_index())
    tp = agg[agg.planner == "tp"].set_index(["arrival_rate", "n_agents"])
    tpts = agg[agg.planner == "tpts"].set_index(["arrival_rate", "n_agents"])
    p = paper.set_index(["arrival_rate", "n_agents"])

    lines = [
        "# TP / TPTS reproduction vs. Ma et al. (2017), Table 1",
        "",
        f"Small warehouse, 500 tasks, mean over {int(tp.runs.max())} seeds per row. "
        "Service time in timesteps; ratio = TPTS / TP service time. "
        "Our runtimes are Python on a different machine, so only trends are comparable.",
        "",
        "| freq | agents | makespan paper | makespan ours | service paper | service ours (±95% CI) "
        "| TPTS ratio paper | TPTS ratio ours | ms/step ours (TP / TPTS) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in p.index:
        if key not in tp.index:
            continue
        o, q = tp.loc[key], p.loc[key]
        ratio = f"{tpts.loc[key].st / o.st:.2f}" if key in tpts.index else "-"
        tpts_ms = f"{tpts.loc[key].plan_ms:.2f}" if key in tpts.index else "-"
        lines.append(
            f"| {key[0]:g} | {key[1]} | {q.tp_makespan:,.0f} | {o.makespan:,.0f} | {q.tp_service_time:.1f} "
            f"| {o.st:.1f} ± {o.st_ci:.1f} | {q.tpts_service_time / q.tp_service_time:.2f} | {ratio} "
            f"| {o.plan_ms:.2f} / {tpts_ms} |"
        )
    (summary / "ma2017_reproduction.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {summary / 'ma2017_reproduction.md'}")

    rates = sorted(paper.arrival_rate.unique())
    for metric, col, ylabel in [("service_time", ("st", "tp_service_time"), "service time"),
                                ("makespan", ("makespan", "tp_makespan"), "makespan")]:
        panels = []
        for r in rates:
            ours = tp.loc[r] if r in tp.index.get_level_values(0) else None
            pr = p.loc[r]
            lines_ = {"Ma et al. 2017 (TP)": (pr.index, pr[col[1]], None)}
            if ours is not None:
                err = ours.st_ci if metric == "service_time" else None
                lines_["ours (TP)"] = (ours.index, ours[col[0]], err)
            panels.append((f"{r:g} tasks / step", lines_))
        small_multiples(panels, ["ours (TP)", "Ma et al. 2017 (TP)"], ylabel,
                        f"TP reproduction: {ylabel} by task frequency",
                        summary / f"ma2017_tp_{metric}.png")


def tuning(results: Path, summary: Path) -> None:
    df = load(results / "sweep.csv")
    agg = (df.groupby(["map_name", "method", "params"])
             .agg(st=("service_time_mean", "mean"), wait=("wait_fraction", "mean"),
                  plan_ms=("plan_time_mean_ms", "mean"), runs=("seed", "count"))
             .reset_index())
    lines = ["# M1 / M2 parameter tuning",
             "",
             "Tuning seeds 100-104; 30 agents at 1 and 5 tasks/step, 500 tasks. "
             "Mean service time over both configurations; **bold** = chosen.",
             ""]
    for m, g in agg.groupby("map_name"):
        base = g[g.method == "tp"].st.mean()
        lines += [f"## {m}", "", f"TP (M0) reference: {base:.1f}", "",
                  "| method | params | service time | vs TP | wait fraction | ms/step |",
                  "|---|---|---:|---:|---:|---:|"]
        for method, gm in g[g.method != "tp"].groupby("method"):
            best = gm.st.idxmin()
            for i, r in gm.sort_values("params").iterrows():
                cell = f"{r.st:.1f}" if i != best else f"**{r.st:.1f}**"
                lines.append(f"| {method} | `{r.params}` | {cell} | {r.st / base - 1:+.1%} "
                             f"| {r.wait:.3f} | {r.plan_ms:.2f} |")
        lines.append("")
    (summary / "baseline_tuning.md").write_text("\n".join(lines))
    print(f"wrote {summary / 'baseline_tuning.md'}")


def midterm(results: Path, summary: Path) -> None:
    df = load(results / "midterm_baselines.csv")
    names = {"tp": "M0 TP", "highway": "M1 Highway", "heatmap": "M2 Heatmap"}
    agg = (df.groupby(["map_name", "method", "arrival_rate", "n_agents"])
             .agg(st=("service_time_mean", "mean"), st_ci=("service_time_mean", ci95),
                  makespan=("makespan", "mean"), wait=("wait_fraction", "mean"),
                  gini=("visit_gini", "mean"), plan_ms=("plan_time_mean_ms", "mean"),
                  params=("params", "first"))
             .reset_index())
    lines = ["# Mid-term baselines: M0 / M1 / M2", "",
             "Mid-term subset (`ma2017_midterm.toml`): 500 tasks, seeds 0-2. "
             "Parameters from `baseline_tuning.md`. Service time ± 95% CI over seeds.", ""]
    for m, g in agg.groupby("map_name"):
        params = {r.method: r.params for r in g.itertuples()}
        lines += [f"## {m}", "",
                  "Parameters: " + ", ".join(f"{names[k]} `{v}`" for k, v in params.items() if k != "tp"), "",
                  "| freq | agents | " + " | ".join(f"{names[k]} service" for k in names)
                  + " | " + " | ".join(f"{names[k]} wait" for k in names) + " | "
                  + " | ".join(f"{names[k]} ms/step" for k in names) + " |",
                  "|---:|---:|" + "---:|" * 9]
        for (r, a), gg in g.groupby(["arrival_rate", "n_agents"]):
            row = gg.set_index("method")
            get = lambda k, c, fmt: format(row.loc[k, c], fmt) if k in row.index else "-"  # noqa: E731
            sts = [f"{get(k, 'st', '.1f')} ± {get(k, 'st_ci', '.1f')}" for k in names]
            lines.append(f"| {r:g} | {a} | " + " | ".join(sts) + " | "
                         + " | ".join(get(k, "wait", ".3f") for k in names) + " | "
                         + " | ".join(get(k, "plan_ms", ".2f") for k in names) + " |")
        lines.append("")
        panels = []
        for r, gr in g.groupby("arrival_rate"):
            base = gr[gr.method == "tp"].set_index("n_agents").st
            lines_ = {}
            for k, gk in gr[gr.method != "tp"].groupby("method"):
                gk = gk.set_index("n_agents")
                lines_[names[k]] = (gk.index, 100 * (gk.st / base - 1), 100 * gk.st_ci / base)
            panels.append((f"{r:g} tasks / step", lines_))
        small_multiples(panels, list(names.values()), "service time vs. M0 (%)",
                        f"{m}: M1 and M2 service time relative to TP (lower is better)",
                        summary / f"midterm_baselines_{m}.png", baseline="M0 TP")
    (summary / "midterm_baselines.md").write_text("\n".join(lines))
    print(f"wrote {summary / 'midterm_baselines.md'}")


def main(results: Path, summary: Path, table1: Path) -> None:
    summary.mkdir(parents=True, exist_ok=True)
    for name, fn, args in [("repro.csv", reproduction, (results, summary, table1)),
                           ("sweep.csv", tuning, (results, summary)),
                           ("midterm_baselines.csv", midterm, (results, summary))]:
        if (results / name).exists():
            fn(*args)
        else:
            print(f"skipping {name}: not run yet")
