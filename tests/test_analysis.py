import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from foresight.analysis import (
    ci95,
    load_runs,
    markdown_table,
    markdown_tests,
    order_variants,
    paired_tests,
    summarize,
    variant_label,
)
from foresight.experiment import run_all

ROOT = Path(__file__).resolve().parents[1]


def runs(rows):
    """Minimal run rows as experiments/run.py writes them."""
    base = {"map_name": "m", "planner": "tp", "n_tasks": 10, "error": "", "completed": True}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_ci95_matches_the_t_distribution():
    # mean 2, sd 1, n 3: t(0.975, 2) = 4.3027 -> 4.3027 / sqrt(3)
    assert ci95([1, 2, 3]) == pytest.approx(4.3027 / math.sqrt(3), rel=1e-4)
    assert math.isnan(ci95([5]))
    assert ci95([4, 4, 4]) == 0


def test_variant_label_includes_only_its_params():
    row = pd.Series({"method": "foresight", "param_lam": 1.0, "param_window": 5, "param_w_h": float("nan")})
    assert variant_label(row) == "foresight(lam=1, window=5)"
    assert variant_label(pd.Series({"method": "tp", "param_lam": float("nan")})) == "tp"
    hw = pd.Series({"method": "highway", "param_directions": "maps/warehouse_small.highway.json", "param_w_h": 1.5})
    assert variant_label(hw) == "highway(directions=warehouse_small.highway, w_h=1.5)"


def test_load_runs_excludes_failed_and_incomplete(tmp_path):
    df = runs([
        {"method": "tp", "n_agents": 2, "arrival_rate": 1, "seed": 0, "service_time_mean": 10},
        {"method": "tp", "n_agents": 2, "arrival_rate": 1, "seed": 1, "service_time_mean": 99, "completed": False},
        {"method": "tp", "n_agents": 2, "arrival_rate": 1, "seed": 2, "service_time_mean": 99, "error": "3 conflicts"},
    ])
    path = tmp_path / "r.csv"
    df.to_csv(path, index=False)
    valid, excluded = load_runs([path])
    assert len(valid) == 1 and len(excluded) == 2
    assert valid["variant"].tolist() == ["tp"]


def test_summarize_groups_seeds():
    df = runs([{"method": "tp", "n_agents": 2, "arrival_rate": 1, "seed": s, "service_time_mean": v} for s, v in enumerate([1, 2, 3])])
    df["variant"] = "tp"
    s = summarize(df, ["service_time_mean"])
    assert len(s) == 1 and s.loc[0, "n_seeds"] == 3
    assert s.loc[0, "service_time_mean_mean"] == 2


def test_paired_tests_against_the_reference():
    rows = []
    for seed in range(6):
        ref = 100 + seed
        rows.append({"method": "tp", "variant": "tp", "n_agents": 2, "arrival_rate": 1, "seed": seed, "service_time_mean": ref, "throughput": 1.0})
        rows.append({"method": "x", "variant": "x", "n_agents": 2, "arrival_rate": 1, "seed": seed, "service_time_mean": ref * 0.9, "throughput": 1.1})
    t = paired_tests(runs(rows), "tp", ["service_time_mean", "throughput"]).set_index("metric")
    assert t.loc["service_time_mean", "n_pairs"] == 6
    assert t.loc["service_time_mean", "change_pct"] == pytest.approx(-10)
    assert t.loc["service_time_mean", "n_better"] == 6  # lower is better
    assert t.loc["throughput", "n_better"] == 6  # higher is better
    assert t.loc["service_time_mean", "p_value"] == pytest.approx(2 / 64)  # exact two-sided, n = 6


def test_identical_runs_give_p_one():
    rows = [{"method": m, "variant": m, "n_agents": 2, "arrival_rate": 1, "seed": s, "service_time_mean": 5} for m in ("tp", "x") for s in range(3)]
    t = paired_tests(runs(rows), "tp", ["service_time_mean"])
    assert t.loc[0, "p_value"] == 1.0 and t.loc[0, "change_pct"] == 0


def test_order_puts_the_reference_first_then_m0_to_m5():
    vs = ["foresight_std(mu=1)", "heatmap(lam=1)", "tp", "foresight(lam=1)", "highway(w_h=1.5)"]
    assert order_variants(vs, "tp") == ["tp", "highway(w_h=1.5)", "heatmap(lam=1)", "foresight(lam=1)", "foresight_std(mu=1)"]


def test_markdown_renders_mean_and_ci():
    df = runs([{"method": "tp", "variant": "tp", "n_agents": 2, "arrival_rate": 1, "seed": s, "service_time_mean": v} for s, v in enumerate([1, 2, 3])])
    table = markdown_table(summarize(df, ["service_time_mean"]), "m", "service_time_mean", ["tp"])
    assert "| 2 | 1 | 2.0 ± 2.5 |" in table


TINY = {
    "map": "maps/toy_corridor.map",
    "n_tasks": 6,
    "agents": [2, 3],
    "arrival_rates": [1],
    "seeds": [0, 1, 2],
    "methods": {"tp": {}, "foresight": {"lam": 1.0, "window": 5}},
}


def test_runner_csv_feeds_the_summary(tmp_path):
    """The columns RunResult.to_row() writes are the ones the summary reads."""
    csv = tmp_path / "tiny.csv"
    run_all(TINY, csv, progress=lambda _: None)
    valid, excluded = load_runs([csv])
    assert len(valid) == 12 and excluded.empty
    tests = paired_tests(valid, "tp", ["service_time_mean", "head_on_per_task"])
    assert set(tests["variant"]) == {"foresight(lam=1, window=5)"}
    assert (tests["n_pairs"] == 6).all()
    assert "foresight(lam=1, window=5)" in markdown_tests(tests, "toy_corridor")


def test_cli_writes_report_csv_and_plot(tmp_path):
    pytest.importorskip("matplotlib")
    csv = tmp_path / "tiny.csv"
    run_all(TINY, csv, progress=lambda _: None)
    out = tmp_path / "summary" / "tiny"
    subprocess.run([sys.executable, str(ROOT / "experiments" / "summarize.py"), str(csv), "--out", str(out)], check=True, capture_output=True)
    report = (out.parent / "tiny.md").read_text()
    assert "## toy_corridor" in report and "Paired tests vs `tp`" in report
    assert (out.parent / "tiny_summary.csv").exists()
    assert (out.parent / "tiny_toy_corridor.png").stat().st_size > 1000
