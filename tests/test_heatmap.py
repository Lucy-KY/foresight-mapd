import random
from pathlib import Path as FsPath

import pytest

from foresight.costs.heatmap import HeatmapCost
from foresight.planner.tp import TokenPassing
from foresight.sim.grid import GridMap
from foresight.sim.instance import make_instance
from foresight.sim.simulator import Simulator

MAPS = FsPath(__file__).resolve().parents[1] / "maps"


def test_rejects_bad_parameters():
    with pytest.raises(ValueError):
        HeatmapCost(lam=-1)
    with pytest.raises(ValueError):
        HeatmapCost(lam=1, eta=0)


def test_no_history_costs_one():
    assert HeatmapCost(lam=4).cost((0, 0), (0, 1), 0) == 1.0


def test_hand_computed_heat():
    cost = HeatmapCost(lam=2, eta=0.5)
    cost.on_timestep(0, {0: (0, 0), 1: (0, 1)})  # H = {a: 1, b: 1}
    cost.on_timestep(1, {0: (0, 0)})  # H = {a: 1.5, b: 0.5}
    assert cost.heat((0, 0)) == pytest.approx(1.5)
    assert cost.heat((0, 1)) == pytest.approx(0.5)
    assert cost.cost((1, 0), (0, 0), 2) == pytest.approx(3.0)  # 1 + 2 * 1.5 / 1.5
    assert cost.cost((1, 1), (0, 1), 2) == pytest.approx(1 + 2 * 0.5 / 1.5)
    assert cost.cost((1, 0), (1, 1), 2) == 1.0  # never visited


def test_waits_and_zero_lambda_cost_exactly_one():
    cost = HeatmapCost(lam=0)
    cost.on_timestep(0, {0: (0, 0)})
    assert cost.cost((0, 1), (0, 0), 1) == 1.0
    hot = HeatmapCost(lam=3)
    hot.on_timestep(0, {0: (0, 0)})
    assert hot.cost((0, 0), (0, 0), 1) == 1.0


@pytest.mark.parametrize("eta", [0.5, 0.95, 0.99])
def test_matches_eager_decay_including_rescaling(eta):
    rng = random.Random(0)
    cells = [(r, c) for r in range(3) for c in range(3)]
    lazy = HeatmapCost(lam=1, eta=eta)
    eager = {}
    for t in range(600):  # 0.5 ** 600 forces several rescales
        occupied = rng.sample(cells, 3)
        eager = {v: h * eta for v, h in eager.items()}
        for v in occupied:
            eager[v] = eager.get(v, 0.0) + 1
        lazy.on_timestep(t, dict(enumerate(occupied)))
    top = max(eager.values())
    for v in cells:
        assert lazy.heat(v) == pytest.approx(eager.get(v, 0.0))
        assert lazy.cost((9, 9), v, 0) == pytest.approx(1 + eager.get(v, 0.0) / top)


def test_heatmap_tp_run_is_valid():
    grid = GridMap.load(MAPS / "warehouse_small.map")
    inst = make_instance(grid, 20, 100, 2, seed=0)
    assert Simulator(inst, TokenPassing(), HeatmapCost(lam=2, eta=0.95)).run().completed
