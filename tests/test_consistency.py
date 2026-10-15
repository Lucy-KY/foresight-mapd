"""Integration check: with lam = mu = 0, M3-M5 must reproduce TP exactly.

This is the test that the three parts of the project fit together: the
simulator, the token / TP / space-time A* shared by every method, and the
reservation table with the M3-M5 cost models. With zero weights every step
costs exactly 1.0, so A* sees the same costs and breaks ties the same way
as with ``UnitCost``, and every agent's executed trajectory must be
identical to TP's.
"""

from functools import lru_cache
from pathlib import Path as FsPath

import pytest

from foresight.costs import (
    ForesightCost,
    SpatioTemporalCost,
    SpatioTemporalDirectionalCost,
    UnitCost,
)
from foresight.planner.tp import TokenPassing
from foresight.sim.grid import GridMap
from foresight.sim.instance import make_instance
from foresight.sim.simulator import Simulator

MAPS = FsPath(__file__).resolve().parents[1] / "maps"

ZERO_WEIGHT_MODELS = [
    lambda: ForesightCost(lam=0.0, window=5),
    lambda: SpatioTemporalCost(lam=0.0, delta=2),
    lambda: SpatioTemporalDirectionalCost(lam=0.0, delta=2, mu=0.0, delta_dir=2),
]

NONZERO_WEIGHT_MODELS = [
    lambda: ForesightCost(lam=1.0, window=5),
    lambda: SpatioTemporalCost(lam=1.0, delta=2),
    lambda: SpatioTemporalDirectionalCost(lam=1.0, delta=2, mu=1.0, delta_dir=2),
]

# (map, agents, tasks, task frequency): small enough for CI, busy enough
# that agents keep running into each other's committed paths.
CASES = [
    ("toy_corridor.map", 3, 30, 1),
    ("warehouse_small.map", 10, 50, 1),
    ("warehouse_small.map", 30, 100, 5),
    ("narrow_corridor.map", 10, 60, 1),
]
SEEDS = [0, 1]


@lru_cache(maxsize=None)
def instance(map_name, n_agents, n_tasks, rate, seed):
    return make_instance(GridMap.load(MAPS / map_name), n_agents, n_tasks, rate, seed)


@lru_cache(maxsize=None)
def tp_paths(*case):
    log = Simulator(instance(*case), TokenPassing(), UnitCost()).run()
    assert log.completed
    return log.paths


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("map_name, n_agents, n_tasks, rate", CASES)
@pytest.mark.parametrize("make_model", ZERO_WEIGHT_MODELS)
def test_zero_weights_match_tp(make_model, map_name, n_agents, n_tasks, rate, seed):
    case = (map_name, n_agents, n_tasks, rate, seed)
    model = make_model()
    log = Simulator(instance(*case), TokenPassing(), model).run()  # runs assert_valid
    assert log.completed
    assert log.paths == tp_paths(*case)
    # Every commit and release reached the cost model: one path per agent is left.
    assert model.reservations.n_paths == n_agents


@pytest.mark.parametrize("make_model", NONZERO_WEIGHT_MODELS)
def test_nonzero_weights_change_trajectories(make_model):
    """Control for the test above: the planner really uses the cost model,
    so positive weights must change some agent's path."""
    case = ("warehouse_small.map", 30, 100, 5, 0)
    log = Simulator(instance(*case), TokenPassing(), make_model()).run()
    assert log.completed
    assert log.paths != tp_paths(*case)


def test_delta_zero_is_rejected():
    with pytest.raises(ValueError):
        SpatioTemporalCost(lam=1.0, delta=0)
