"""The M3-M5 selection rule in experiments/select_tuning.py (results/summary/tune_foresight.md)."""

import importlib.util
from pathlib import Path

import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "select_tuning", Path(__file__).resolve().parents[1] / "experiments" / "select_tuning.py"
)
select_tuning = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(select_tuning)


def _table(rows):
    return pd.DataFrame(rows, columns=["variant", "param_lam", "param_window", "service_time_mean", "wait_fraction"])


def test_lowest_wait_within_tolerance_wins_over_fastest():
    table = _table([
        ("a", 1.0, 5, 100.0, 0.09),   # fastest
        ("b", 2.0, 5, 100.4, 0.05),   # within 0.5%, waits least -> chosen
        ("c", 0.5, 5, 100.6, 0.01),   # outside 0.5%
    ])
    near, chosen = select_tuning.select(table)
    assert list(near) == [True, True, False]
    assert chosen["variant"] == "b"


def test_wait_ties_go_to_smaller_lam_then_window():
    table = _table([
        ("a", 2.0, 2, 100.0, 0.0501),
        ("b", 1.0, 10, 100.1, 0.0499),  # same wait to 3 decimals, smaller lam
        ("c", 1.0, 5, 100.2, 0.0504),   # same wait and lam, smaller window -> chosen
    ])
    _, chosen = select_tuning.select(table)
    assert chosen["variant"] == "c"
