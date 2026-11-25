"""M3-M5 sensitivity sweeps and the matched-window M3 -> M4 comparison
(design: results/summary/sensitivity.md).

Usage:
    python experiments/sensitivity.py run --out results/sensitivity.csv --jobs 10
    python experiments/sensitivity.py summarize results/sensitivity.csv --out results/summary/sensitivity

Owner: member 3.
"""

from __future__ import annotations

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.experiment import DEFAULT_MAX_TIMESTEPS, git_commit, run_job  # noqa: E402

AGENTS, RATE, SEEDS, N_TASKS = 30, 1, list(range(10)), 500  # medium configuration, test seeds
TUNED = {  # results/summary/tune_foresight.md
    "narrow_corridor": {"lam": 0.5, "delta": 2, "mu": 0.5, "delta_dir": 2},
    "warehouse_small": {"lam": 2.0, "delta": 10, "mu": 4.0, "delta_dir": 2},
}
SWEEPS = {
    "lam": [0, 0.25, 0.5, 1, 2, 4, 8],
    "delta": [1, 2, 3, 5, 10, 20],
    "mu": [0, 0.5, 1, 2, 4, 8, 16],
    "delta_dir": [1, 2, 5, 10],
    "matched": [1, 2, 5, 10],  # delta; span s = 2 * delta + 1 = M3's window
}
METRICS = [
    ("service_time_mean", "mean service time", "{:.1f}"),
    ("head_on_per_task", "head-on per task", "{:.3f}"),
    ("wait_fraction", "wait fraction", "{:.3f}"),
    ("plan_time_mean_ms", "ms/step", "{:.2f}"),
]


def settings(map_name: str) -> list[tuple[str, str, float, str, dict]]:
    """(sweep, label, x, method, params) for every setting on one map."""
    t = TUNED[map_name]
    out = [("tp", "TP", 0, "tp", {})]
    for lam in SWEEPS["lam"]:
        out.append(("lam", "M4", lam, "foresight_st", {"lam": float(lam), "delta": t["delta"]}))
    for delta in SWEEPS["delta"]:
        out.append(("delta", "M4", delta, "foresight_st", {"lam": t["lam"], "delta": delta}))
    for mu in SWEEPS["mu"]:
        out.append(("mu", "M5", mu, "foresight_std",
                    {"lam": t["lam"], "delta": t["delta"], "mu": float(mu), "delta_dir": t["delta_dir"]}))
    for dd in SWEEPS["delta_dir"]:
        out.append(("delta_dir", "M5", dd, "foresight_std",
                    {"lam": t["lam"], "delta": t["delta"], "mu": t["mu"], "delta_dir": dd}))
    for delta in SWEEPS["matched"]:
        span = 2 * delta + 1
        out.append(("matched", "M3", span, "foresight", {"lam": t["lam"], "window": span}))
        out.append(("matched", "M4", span, "foresight_st", {"lam": t["lam"], "delta": delta}))
    return out


def _run(args: tuple[str, str, float, str, dict, int, str]) -> dict:
    map_name, sweep, label, x, method, params, seed, commit = args
    job = {"map": f"maps/{map_name}.map", "n_tasks": N_TASKS, "planner": "tp", "max_timesteps": DEFAULT_MAX_TIMESTEPS,
           "method": method, "params": params, "n_agents": AGENTS, "arrival_rate": RATE, "seed": seed}
    row = run_job(job, commit)
    keep = ["completed", "n_conflicts", "error", *[m for m, _, _ in METRICS]]
    return {"map_name": map_name, "sweep": sweep, "label": label, "x": x, "seed": seed,
            "params": str(params), **{k: row.get(k) for k in keep}}


def cmd_run(args: argparse.Namespace) -> None:
    commit = git_commit()
    jobs = [(m, *s, seed, commit) for m in TUNED for s in settings(m) for seed in SEEDS]
    with Pool(args.jobs) as pool:
        rows = pool.map(_run, jobs, chunksize=1)
    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    ok = df["completed"].astype(str).str.lower().eq("true") & (df["n_conflicts"] == 0) & df["error"].fillna("").eq("")
    print(f"{len(df)} runs, {(~ok).sum()} failed, incomplete or conflicting -> {args.out}")


def mean_ci(v: pd.Series) -> tuple[float, float]:
    v = v.dropna()
    return v.mean(), 1.96 * v.std(ddof=1) / np.sqrt(len(v))


def cmd_summarize(args: argparse.Namespace) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker  # noqa: F401
    from scipy.stats import wilcoxon

    df = pd.read_csv(args.csv)
    ok = df["completed"].astype(str).str.lower().eq("true") & (df["n_conflicts"] == 0) & df["error"].fillna("").eq("")
    if (~ok).any():
        sys.exit(f"{(~ok).sum()} runs failed, incomplete or conflicting; fix before summarizing")

    lines = ["", "# Results", "",
             f"{len(df)} runs (test seeds 0-9, 30 agents, rate 1), all complete with 0 conflicts. Produced by "
             f"`python experiments/sensitivity.py summarize {args.csv} --out {args.out}`. Cells: mean ± 95% CI.", ""]
    figs = []
    for map_name in TUNED:
        on_map = df[df.map_name == map_name]
        tp = on_map[on_map.sweep == "tp"]
        lines += [f"## {map_name}", "", "TP: " + ", ".join(
            f"{name} {fmt.format(mean_ci(tp[m])[0])}" for m, name, fmt in METRICS) + ".", ""]
        for sweep in SWEEPS:
            sub = on_map[on_map.sweep == sweep]
            labels = list(dict.fromkeys(sub.label))
            xname = "span s = W = 2 delta + 1" if sweep == "matched" else sweep
            lines += [f"### {sweep}", "", f"| method | {xname} | " + " | ".join(n for _, n, _ in METRICS) + " |",
                      "|---|---:|" + "---:|" * len(METRICS)]
            for (x, lab), g in sub.groupby(["x", "label"], sort=True):
                cells = [f"{fmt.format(mean_ci(g[m])[0])} ± {fmt.format(mean_ci(g[m])[1])}" for m, _, fmt in METRICS]
                lines.append(f"| {lab} | {x:g} | " + " | ".join(cells) + " |")
            lines.append("")
            del labels

        # Matched-window tests.
        lines += ["### Matched-window tests (M4 - M3, paired by seed)", "",
                  "| test | metric | span | pairs | mean M4 - M3 | relative | M4 lower | p (Wilcoxon) |",
                  "|---|---|---|---:|---:|---:|---:|---:|"]
        m = on_map[on_map.sweep == "matched"]
        for test, metric in [("A1", "head_on_per_task"), ("A2", "service_time_mean")]:
            piv = m.pivot_table(index=["x", "seed"], columns="label", values=metric)
            scopes = [("pooled", piv)] + [(f"{s:g}", piv.xs(s, level="x", drop_level=False)) for s in sorted(m.x.unique())]
            for scope, p in scopes:
                d = p["M4"] - p["M3"]
                pv = wilcoxon(d).pvalue if (d != 0).any() else 1.0
                lines.append(f"| {test} | {metric} | {scope} | {len(d)} | {d.mean():+.4f} | "
                             f"{d.mean() / p['M3'].mean():+.1%} | {(d < 0).sum()}/{len(d)} | {pv:.3g} |")
        lines.append("")

        # Figure: rows = sweeps, columns = service time / head-on / wait.
        sweeps = list(SWEEPS)
        fig, axes = plt.subplots(len(sweeps), 3, figsize=(10, 2.3 * len(sweeps)), squeeze=False)
        colors = {"M3": "#1baf7a", "M4": "#2a78d6", "M5": "#eb6834"}
        for i, sweep in enumerate(sweeps):
            sub = on_map[on_map.sweep == sweep]
            for j, (metric, name, _) in enumerate(METRICS[:3]):
                ax = axes[i][j]
                for lab, g in sub.groupby("label"):
                    stats = g.groupby("x")[metric].apply(lambda v: pd.Series(mean_ci(v), index=["m", "ci"])).unstack()
                    ax.errorbar(stats.index, stats["m"], yerr=stats["ci"], marker="o", ms=3.5, lw=1.5,
                                capsize=2, color=colors[lab], label=lab)
                ax.axhline(mean_ci(tp[metric])[0], color="#52514e", lw=1, ls="--", label="TP")
                if sweep in ("lam", "mu"):
                    ax.set_xscale("symlog", linthresh=0.25)
                    ax.set_xlim(left=-0.05)
                    ax.set_xticks([0, 0.25, 1, 4, 16 if sweep == "mu" else 8])
                    ax.get_xaxis().set_major_formatter(matplotlib.ticker.FormatStrFormatter("%g"))
                elif sweep in ("delta", "matched"):
                    ax.set_xscale("log")
                    ax.set_xticks(sorted(sub.x.unique()))
                    ax.get_xaxis().set_major_formatter(matplotlib.ticker.FormatStrFormatter("%g"))
                    ax.minorticks_off()
                ax.set_xlabel("span s" if sweep == "matched" else sweep, fontsize=8)
                if i == 0:
                    ax.set_title(name, loc="left", fontsize=10)
                ax.spines[["top", "right"]].set_visible(False)
                ax.tick_params(labelsize=7)
            axes[i][0].legend(frameon=False, fontsize=7)
        fig.suptitle(map_name, x=0.01, ha="left", fontsize=11)
        fig.tight_layout()
        png = args.out.parent / f"{args.out.name}_{map_name}.png"
        fig.savefig(png, dpi=140)
        figs.append(png)

    lines += ["## Figures", ""] + [f"![{p.stem}]({p.name})\n" for p in figs]
    md = args.out.with_suffix(".md")
    head = md.read_text(encoding="utf-8").split("\n# Results\n")[0].rstrip("\n")
    md.write_text(head + "\n" + "\n".join(lines), encoding="utf-8")  # replaces an earlier Results section
    print(f"wrote results to {md}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=1)
    p.set_defaults(func=cmd_run)
    s = sub.add_parser("summarize")
    s.add_argument("csv", type=Path)
    s.add_argument("--out", type=Path, required=True)
    s.set_defaults(func=cmd_summarize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
