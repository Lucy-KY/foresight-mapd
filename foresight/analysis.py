"""Summaries of batch results: mean ± 95% CI per configuration and paired
tests against a reference method.

Owner: member 1. ``experiments/summarize.py`` is the command-line entry
point; it reads the CSVs written by ``experiments/run.py``.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from pathlib import Path as FsPath

import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class Metric:
    label: str
    lower_is_better: bool
    fmt: str


METRICS: dict[str, Metric] = {
    "service_time_mean": Metric("mean service time", True, "{:.1f}"),
    "service_time_p95": Metric("95th pct service time", True, "{:.1f}"),
    "makespan": Metric("makespan", True, "{:.0f}"),
    "throughput": Metric("throughput (tasks/step)", False, "{:.3f}"),
    "total_path_cost": Metric("total path cost", True, "{:.0f}"),
    "wait_fraction": Metric("wait fraction", True, "{:.3f}"),
    "head_on_per_task": Metric("head-on encounters per task", True, "{:.3f}"),
    "visit_gini": Metric("visit Gini", True, "{:.3f}"),
    "plan_time_mean_ms": Metric("planning ms per step", True, "{:.2f}"),
}

CONFIG = ["n_agents", "arrival_rate"]


def ci95(values) -> float:
    """Half-width of the 95% confidence interval of the mean (Student t).
    NaN with fewer than two values."""
    xs = [float(v) for v in values if not pd.isna(v)]
    n = len(xs)
    if n < 2:
        return math.nan
    sd = statistics.stdev(xs)
    return float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n))


def _number(v) -> str:
    """Compact parameter value: ``1.0`` -> ``1``; a file path -> its stem
    (``maps/warehouse_small.highway.json`` -> ``warehouse_small.highway``)."""
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, str) and "/" in v:
        return FsPath(v).stem
    return str(v)


def variant_label(row: pd.Series) -> str:
    """``method`` plus its non-empty parameters, e.g. ``foresight(lam=1, window=5)``."""
    params = [
        f"{col[len('param_'):]}={_number(row[col])}"
        for col in sorted(c for c in row.index if c.startswith("param_"))
        if not pd.isna(row[col])
    ]
    return f"{row['method']}({', '.join(params)})" if params else row["method"]


def load_runs(paths: list[str | FsPath]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read run CSVs. Returns ``(valid, excluded)``: a run is excluded when
    it has an error (including conflicts) or did not complete every task,
    because averaging those with completed runs would be misleading."""
    frames = [pd.read_csv(p, keep_default_na=True) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df["error"] = df["error"].fillna("").astype(str)
    df["completed"] = df["completed"].astype(str).str.lower().eq("true")
    df["variant"] = df.apply(variant_label, axis=1)
    ok = df["error"].eq("") & df["completed"]
    return df[ok].copy(), df[~ok].copy()


def summarize(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    """One row per (map, variant, n_agents, arrival_rate): number of seeds,
    and the mean and 95% CI half-width of each metric."""
    rows = []
    for key, group in df.groupby(["map_name", "variant", *CONFIG], sort=True):
        row = dict(zip(["map_name", "variant", *CONFIG], key))
        row["n_seeds"] = len(group)
        for m in metrics:
            row[f"{m}_mean"] = group[m].mean()
            row[f"{m}_ci95"] = ci95(group[m])
        rows.append(row)
    return pd.DataFrame(rows)


def paired_tests(df: pd.DataFrame, reference: str, metrics: list[str]) -> pd.DataFrame:
    """Compare every variant with ``reference`` on the same map, pairing runs
    by (n_agents, arrival_rate, seed), so both saw the same task stream.

    Per map, variant and metric: number of pairs, mean relative change in
    percent (negative = lower than the reference), how many pairs are
    better, and the two-sided Wilcoxon signed-rank p-value over all pairs.
    """
    keys = [*CONFIG, "seed"]
    rows = []
    for map_name, on_map in df.groupby("map_name", sort=True):
        ref = on_map[on_map["variant"] == reference].set_index(keys)
        if ref.empty:
            continue
        for variant, runs in on_map[on_map["variant"] != reference].groupby("variant", sort=True):
            joined = runs.set_index(keys).join(ref, rsuffix="_ref", how="inner")
            for m in metrics:
                pair = joined[[m, f"{m}_ref"]].dropna()
                if pair.empty:
                    continue
                x, r = pair[m].to_numpy(float), pair[f"{m}_ref"].to_numpy(float)
                diff = x - r
                better = (diff < 0) if METRICS[m].lower_is_better else (diff > 0)
                with_ref = r != 0
                change = float(((diff[with_ref] / r[with_ref]).mean()) * 100) if with_ref.any() else math.nan
                rows.append(
                    {
                        "map_name": map_name,
                        "variant": variant,
                        "metric": m,
                        "n_pairs": len(pair),
                        "change_pct": change,
                        "n_better": int(better.sum()),
                        "p_value": _wilcoxon(diff),
                    }
                )
    return pd.DataFrame(rows)


def _wilcoxon(diff) -> float:
    if len(diff) == 0:
        return math.nan
    if all(d == 0 for d in diff):
        return 1.0
    return float(stats.wilcoxon(diff).pvalue)


def _cell(mean: float, ci: float, fmt: str) -> str:
    if pd.isna(mean):
        return ""
    text = fmt.format(mean)
    return text if pd.isna(ci) else f"{text} ± {fmt.format(ci)}"


def markdown_table(summary: pd.DataFrame, map_name: str, metric: str, variants: list[str]) -> str:
    """Rows = (agents, rate), columns = variants, cells = mean ± 95% CI."""
    m = METRICS[metric]
    on_map = summary[summary["map_name"] == map_name]
    header = ["agents", "rate", *variants]
    lines = ["| " + " | ".join(header) + " |", "|" + "---:|" * len(header)]
    for (agents, rate), group in on_map.groupby(CONFIG, sort=True):
        by_variant = group.set_index("variant")
        cells = [
            _cell(by_variant.at[v, f"{metric}_mean"], by_variant.at[v, f"{metric}_ci95"], m.fmt)
            if v in by_variant.index
            else ""
            for v in variants
        ]
        lines.append(f"| {agents} | {_number(rate)} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def markdown_tests(tests: pd.DataFrame, map_name: str) -> str:
    on_map = tests[tests["map_name"] == map_name]
    lines = [
        "| variant | metric | pairs | change vs reference | better in | p (Wilcoxon) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for _, t in on_map.iterrows():
        change = "" if pd.isna(t["change_pct"]) else f"{t['change_pct']:+.1f}%"
        p = "" if pd.isna(t["p_value"]) else f"{t['p_value']:.3g}"
        lines.append(
            f"| {t['variant']} | {METRICS[t['metric']].label} | {t['n_pairs']} | {change} | "
            f"{t['n_better']}/{t['n_pairs']} | {p} |"
        )
    return "\n".join(lines)


def plot_metric(summary: pd.DataFrame, map_name: str, metric: str, variants: list[str], out: str | FsPath) -> FsPath:
    """One panel per arrival rate: metric vs number of agents, one line per
    variant, error bars = 95% CI."""
    from matplotlib.figure import Figure

    on_map = summary[summary["map_name"] == map_name]
    rates = sorted(on_map["arrival_rate"].unique())
    fig = Figure(figsize=(3.6 * len(rates), 3.2), dpi=150)
    axes = fig.subplots(1, len(rates), squeeze=False)[0]
    for ax, rate in zip(axes, rates):
        at_rate = on_map[on_map["arrival_rate"] == rate]
        for i, v in enumerate(variants):
            line = at_rate[at_rate["variant"] == v].sort_values("n_agents")
            if line.empty:
                continue
            ax.errorbar(
                line["n_agents"], line[f"{metric}_mean"], yerr=line[f"{metric}_ci95"].fillna(0),
                marker="o", markersize=3, capsize=2, linewidth=1.2, color=f"C{i}", label=v,
            )
        ax.set_title(f"{_number(rate)} tasks / step", fontsize=9)
        ax.set_xlabel("agents", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.3, linewidth=0.5)
    axes[0].set_ylabel(METRICS[metric].label, fontsize=8)
    axes[-1].legend(fontsize=6, frameon=False)
    fig.suptitle(map_name, fontsize=10)
    fig.tight_layout()
    out = FsPath(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    return out


def order_variants(variants, reference: str) -> list[str]:
    """Reference first, then the rest in method order M0-M5."""
    rank = {"tp": 0, "highway": 1, "heatmap": 2, "foresight": 3, "foresight_st": 4, "foresight_std": 5}
    return sorted(set(variants), key=lambda v: (v != reference, rank.get(v.split("(")[0], 9), v))
