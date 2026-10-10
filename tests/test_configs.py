"""Every experiment config parses and expands to the expected jobs."""

import importlib.util
import tomllib
from pathlib import Path

import pytest

from foresight.costs import METHODS

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = sorted((ROOT / "experiments" / "configs").glob("*.toml"))

_spec = importlib.util.spec_from_file_location("run", ROOT / "experiments" / "run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)


def load(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


@pytest.mark.parametrize("config_path", CONFIGS, ids=lambda p: p.name)
def test_config_is_valid(config_path):
    config = load(config_path)
    assert (ROOT / config["map"]).exists()
    assert set(config["methods"]) <= set(METHODS)
    jobs = run.expand(config)
    per_method = len(config["agents"]) * len(config["arrival_rates"]) * len(config["seeds"])
    assert len(jobs) == per_method * len(config["methods"])


def test_midterm_config_is_27_runs_per_method():
    config = load(ROOT / "experiments" / "configs" / "ma2017_midterm.toml")
    jobs = run.expand(config)
    assert set(config["methods"]) == {"tp", "highway", "foresight", "foresight_st"}
    assert len([j for j in jobs if j["method"] == "tp"]) == 27
