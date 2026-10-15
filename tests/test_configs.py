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


@pytest.mark.parametrize("name", ["ma2017_midterm.toml", "ma2017_midterm_narrow.toml"])
def test_midterm_configs_run_m0_to_m5_27_times_each(name):
    jobs = expand(load(ROOT / "experiments" / "configs" / name))
    assert {j["method"] for j in jobs} == {"tp", "highway", "heatmap", "foresight", "foresight_st", "foresight_std"}
    assert all(len([j for j in jobs if j["method"] == m]) == 27 for m in {j["method"] for j in jobs})
