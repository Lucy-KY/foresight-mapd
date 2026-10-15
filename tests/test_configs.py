"""Every experiment config parses, expands, and respects the seed split."""

import tomllib
from pathlib import Path

import pytest

from foresight.costs import METHODS
from foresight.experiment import expand, param_grid, planners

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = sorted((ROOT / "experiments" / "configs").glob("*.toml"))


def load(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


@pytest.mark.parametrize("config_path", CONFIGS, ids=lambda p: p.name)
def test_config_is_valid(config_path):
    config = load(config_path)
    assert (ROOT / config["map"]).exists()
    assert set(config["methods"]) <= set(METHODS)
    assert config.get("planner", "tp") in planners()
    per_method = len(config["agents"]) * len(config["arrival_rates"]) * len(config["seeds"])
    combos = sum(len(param_grid(p)) for p in config["methods"].values())
    assert len(expand(config)) == per_method * combos


@pytest.mark.parametrize("config_path", CONFIGS, ids=lambda p: p.name)
def test_tuning_and_test_seeds_are_separate(config_path):
    seeds = load(config_path)["seeds"]
    if config_path.name.startswith("tune_"):
        assert all(s >= 100 for s in seeds), "tuning configs use seeds 100+"
    else:
        assert all(s < 100 for s in seeds), "seeds 100+ are reserved for tuning"


def test_midterm_config_is_27_runs_per_method():
    jobs = expand(load(ROOT / "experiments" / "configs" / "ma2017_midterm.toml"))
    assert {j["method"] for j in jobs} == {"tp", "highway", "foresight", "foresight_st", "foresight_std"}
    assert len([j for j in jobs if j["method"] == "tp"]) == 27
