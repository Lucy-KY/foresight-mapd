"""Apply the M3-M5 selection rule (results/summary/tune_foresight.md) to tuning CSVs.

Usage:
    python experiments/select_tuning.py results/tune_foresight_warehouse_small.csv \
        results/tune_foresight_narrow_corridor.csv

prints one Markdown section per map: every setting's mean service time, wait
fraction, head-on encounters per task and planning time over its runs, with the
near-best set marked and the chosen setting in bold. Owner: member 3.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.analysis import load_runs  # noqa: E402

TOLERANCE = 0.005  # near-best: score <= (1 + TOLERANCE) * best
METHODS = ["foresight", "foresight_st", "foresight_std"]
# Tie-break order after wait fraction: smaller lam, then window / delta / mu.
TIE_BREAK = ["param_lam", "param_window", "param_delta", "param_mu"]
COLUMNS = ["service_time_mean", "wait_fraction", "head_on_per_task", "plan_time_mean_ms"]


def settings(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per setting (variant): means over its runs, plus the run count."""
    params = [c for c in runs.columns if c.startswith("param_")]
    agg = runs.groupby("variant").agg(
        method=("method", "first"),
        n_runs=("seed", "size"),
        **{c: (c, "first") for c in params},
        **{c: (c, "mean") for c in COLUMNS},
    )
    return agg.reset_index()


def select(table: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Steps 1-3 of the rule. Returns (near-best mask, chosen row)."""
    best = table["service_time_mean"].min()
    near = table["service_time_mean"] <= (1 + TOLERANCE) * best
    candidates = table[near].assign(wait_rounded=table["wait_fraction"].round(3))
    keys = ["wait_rounded", *[c for c in TIE_BREAK if c in candidates]]
    chosen = candidates.sort_values(keys, na_position="first").iloc[0]
    return near, chosen


def params_of(row: pd.Series) -> str:
    parts = [f"{c[len('param_'):]}={row[c]:g}" for c in row.index if c.startswith("param_") and pd.notna(row[c])]
    return ", ".join(parts)


def section(runs: pd.DataFrame, map_name: str) -> tuple[list[str], dict[str, str]]:
    on_map = runs[runs["map_name"] == map_name]
    table = settings(on_map)
    tp = table[table["method"] == "tp"]
    if tp.empty:
        sys.exit(f"{map_name}: no TP runs to compare with")
    tp = tp.iloc[0]
    lines = [
        f"## {map_name}",
        "",
        f"TP (M0) reference: service time {tp.service_time_mean:.1f}, wait fraction "
        f"{tp.wait_fraction:.3f}, head-on/task {tp.head_on_per_task:.3f}, {tp.plan_time_mean_ms:.2f} ms/step "
        f"({tp.n_runs} runs).",
        "",
    ]
    chosen_by_method: dict[str, str] = {}
    for method in METHODS:
        rows = table[table["method"] == method]
        note = ""
        if method == "foresight_std":
            m4 = chosen_by_method.get("foresight_st_row")
            stage2 = rows[rows["param_delta"] == m4["param_delta"]] if m4 is not None else rows.iloc[0:0]
            if stage2.empty:
                lines += [f"### {method}", "", f"Stage 2 needs a re-run with delta = {m4['param_delta']:g}.", ""]
                continue
            note = f" Stage 2: delta fixed to M4's chosen delta = {m4['param_delta']:g}."
            rows = stage2
        if rows.empty:
            continue
        near, chosen = select(rows)
        chosen_by_method[method] = params_of(chosen)
        if method == "foresight_st":
            chosen_by_method["foresight_st_row"] = chosen
        lines += [
            f"### {method}",
            "",
            f"Near-best = within {TOLERANCE:.1%} of the best service time ({near.sum()} of {len(rows)} settings, "
            f"marked •); chosen in **bold**.{note}",
            "",
            "| params | runs | service time | vs TP | wait fraction | vs TP | head-on/task | vs TP | ms/step |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for idx, row in rows.sort_values(TIE_BREAK[: len(TIE_BREAK)], na_position="first").iterrows():
            is_chosen = row["variant"] == chosen["variant"]
            b = "**" if is_chosen else ""
            mark = " •" if near[idx] else ""
            lines.append(
                f"| {b}`{params_of(row)}`{b}{mark} | {row.n_runs} | {b}{row.service_time_mean:.1f}{b} | "
                f"{row.service_time_mean / tp.service_time_mean - 1:+.1%} | {row.wait_fraction:.3f} | "
                f"{row.wait_fraction / tp.wait_fraction - 1:+.0%} | {row.head_on_per_task:.3f} | "
                f"{row.head_on_per_task / tp.head_on_per_task - 1:+.0%} | {row.plan_time_mean_ms:.2f} |"
            )
        lines.append("")
    chosen_by_method.pop("foresight_st_row", None)
    return lines, chosen_by_method


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", nargs="+", type=Path)
    args = parser.parse_args()
    runs, excluded = load_runs(args.csv)
    runs = runs[runs["n_conflicts"] == 0]
    out: list[str] = []
    summary: list[str] = ["## Chosen parameters", "", "| map | method | params |", "|---|---|---|"]
    for map_name in sorted(runs["map_name"].unique()):
        lines, chosen = section(runs, map_name)
        out += lines
        summary += [f"| {map_name} | {m} | `{p}` |" for m, p in chosen.items()]
    print("\n".join(summary + [""] + out))
    if len(excluded):
        print(f"<!-- {len(excluded)} runs excluded (failed or incomplete) -->")


if __name__ == "__main__":
    main()
