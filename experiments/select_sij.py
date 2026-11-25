"""Apply the S_ij selection rule (results/summary/tune_sij.md) to tuning CSVs.

Usage:
    python experiments/select_sij.py results/tune_sij_warehouse_small.csv results/tune_sij_narrow_corridor.csv

prints one Markdown table per map: every (beta, gamma) setting's means over its
runs, the near-best set marked with a dot and the chosen setting in bold.
Owner: member 1.
"""

from __future__ import annotations

import argparse

import pandas as pd

TOLERANCE = 0.005
COLUMNS = ["service_time_mean", "service_time_p95", "service_time_max", "wait_fraction", "head_on_per_task",
           "plan_time_mean_ms"]


def table(runs: pd.DataFrame) -> pd.DataFrame:
    runs = runs.assign(aparam_beta=runs["aparam_beta"].fillna(0.0), aparam_gamma=runs["aparam_gamma"].fillna(0.0))
    t = runs.groupby(["assignment", "aparam_beta", "aparam_gamma"]).agg(
        n_runs=("seed", "size"), conflicts=("n_conflicts", "sum"), **{c: (c, "mean") for c in COLUMNS})
    return t.reset_index()


def select(t: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    sij = t[t["assignment"] == "sij"]
    best = sij["service_time_mean"].min()
    near = sij["service_time_mean"] <= (1 + TOLERANCE) * best
    chosen = (sij[near].assign(p95=sij["service_time_p95"].round(1))
              .sort_values(["p95", "aparam_beta", "aparam_gamma"]).iloc[0])
    return near.reindex(t.index, fill_value=False), chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", nargs="+")
    args = parser.parse_args()
    runs = pd.concat([pd.read_csv(p) for p in args.csv], ignore_index=True)
    assert (runs["error"].astype(object).fillna("") == "").all(), "some runs failed"
    for map_name, on_map in runs.groupby("map_name"):
        t = table(on_map)
        near, chosen = select(t)
        tp = t[t["assignment"] == "nearest"].iloc[0]
        print(f"## {map_name}\n")
        print(f"TP (nearest pickup): service {tp.service_time_mean:.1f}, p95 {tp.service_time_p95:.1f}, "
              f"max {tp.service_time_max:.1f}, wait {tp.wait_fraction:.3f}, head-on/task {tp.head_on_per_task:.3f} "
              f"({tp.n_runs} runs, {int(t.conflicts.sum())} conflicts in all runs).\n")
        print("| beta | gamma | service | vs TP | p95 | max | wait | head-on/task | ms/step |")
        print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for i, r in t[t["assignment"] == "sij"].iterrows():
            mark = " •" if near[i] else ""
            cells = [f"{r.aparam_beta:g}", f"{r.aparam_gamma:g}", f"{r.service_time_mean:.1f}{mark}",
                     f"{100 * (r.service_time_mean / tp.service_time_mean - 1):+.1f}%", f"{r.service_time_p95:.1f}",
                     f"{r.service_time_max:.1f}", f"{r.wait_fraction:.3f}", f"{r.head_on_per_task:.3f}",
                     f"{r.plan_time_mean_ms:.2f}"]
            if r.aparam_beta == chosen.aparam_beta and r.aparam_gamma == chosen.aparam_gamma:
                cells = [f"**{c}**" for c in cells]
            print("| " + " | ".join(cells) + " |")
        print(f"\nChosen: beta = {chosen.aparam_beta:g}, gamma = {chosen.aparam_gamma:g}.\n")


if __name__ == "__main__":
    main()
