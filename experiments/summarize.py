"""Summarize run CSVs into tables, paired tests and plots.

Usage:
    python experiments/summarize.py results/midterm.csv --out results/summary/midterm

writes results/summary/midterm.md (tables + tests), midterm_summary.csv
(every metric, mean and 95% CI) and one midterm_<map>.png per map.
Owner: member 1; the logic lives in ``foresight/analysis.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.analysis import (  # noqa: E402
    METRICS,
    load_runs,
    markdown_table,
    markdown_tests,
    order_variants,
    paired_tests,
    plot_metric,
    summarize,
)

DEFAULT_TESTS = "service_time_mean,service_time_p95,wait_fraction,head_on_per_task,plan_time_mean_ms"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", nargs="+", type=Path, help="CSV files written by experiments/run.py")
    parser.add_argument("--out", type=Path, required=True, help="output path prefix, without extension")
    parser.add_argument("--reference", default="tp", help="variant every other one is compared with")
    parser.add_argument("--metric", default="service_time_mean", choices=sorted(METRICS), help="metric in the main table and plot")
    parser.add_argument("--tests", default=DEFAULT_TESTS, help="comma-separated metrics for the paired tests")
    args = parser.parse_args()

    tested = [m.strip() for m in args.tests.split(",") if m.strip()]
    unknown = sorted(set(tested) - set(METRICS))
    if unknown:
        parser.error(f"unknown metrics {unknown}; known: {sorted(METRICS)}")

    valid, excluded = load_runs(args.csv)
    if valid.empty:
        sys.exit("no completed, error-free runs to summarize")
    summary = summarize(valid, sorted(METRICS))
    tests = paired_tests(valid, args.reference, tested)
    variants = order_variants(valid["variant"], args.reference)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out.parent / f"{args.out.name}_summary.csv", index=False)

    lines = [
        f"# {args.out.name}",
        "",
        f"Source: {', '.join(str(p) for p in args.csv)}. {len(valid)} runs used"
        + (f", {len(excluded)} excluded (failed or incomplete)." if len(excluded) else "."),
        f"Cells: {METRICS[args.metric].label}, mean ± 95% CI over seeds. Tests pair each variant with "
        f"`{args.reference}` on the same (agents, rate, seed); change is the mean relative difference.",
    ]
    for map_name in sorted(valid["map_name"].unique()):
        on_map = [v for v in variants if v in set(valid[valid["map_name"] == map_name]["variant"])]
        png = plot_metric(summary, map_name, args.metric, on_map, args.out.parent / f"{args.out.name}_{map_name}.png")
        lines += [
            "",
            f"## {map_name}",
            "",
            markdown_table(summary, map_name, args.metric, on_map),
            "",
            f"![{map_name}]({png.name})",
            "",
            f"### Paired tests vs `{args.reference}`",
            "",
            markdown_tests(tests, map_name),
        ]
    md = args.out.with_suffix(".md")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(valid)} runs used, {len(excluded)} excluded -> {md}")
    if len(excluded):
        print("excluded runs, first errors:")
        for err in excluded["error"].replace("", "incomplete").value_counts().head(5).index:
            print(f"  {err}")


if __name__ == "__main__":
    main()
