import json
from pathlib import Path as FsPath

import pytest

from foresight.costs.highway import HighwayCost, load_directions
from foresight.planner.tp import TokenPassing
from foresight.sim.grid import GridMap
from foresight.sim.instance import make_instance
from foresight.sim.simulator import Simulator

MAPS = FsPath(__file__).resolve().parents[1] / "maps"
E, W, N, S = (0, 1), (0, -1), (-1, 0), (1, 0)

GRID = GridMap.from_lines(["....", ".@..", "...."])


def test_rejects_w_below_one():
    with pytest.raises(ValueError):
        HighwayCost({}, w_h=0.5)


def test_along_against_and_off_highway():
    cost = HighwayCost({(0, 0): {E}, (0, 1): {E}, (0, 2): {E}}, w_h=3)
    assert cost.cost((0, 0), (0, 1), 0) == 1.0  # along
    assert cost.cost((0, 2), (0, 1), 0) == 3.0  # against
    assert cost.cost((1, 0), (0, 0), 0) == 1.0  # entering sideways
    assert cost.cost((0, 1), (1, 1), 0) == 1.0  # leaving sideways
    assert cost.cost((2, 0), (2, 1), 0) == 1.0  # no highway here
    assert cost.cost((0, 1), (0, 1), 0) == 1.0  # waiting


def test_crossing_cells_allow_both_lanes():
    cost = HighwayCost({(0, 0): {E, S}, (0, 1): {E}, (1, 0): {S}}, w_h=2)
    assert cost.cost((0, 0), (1, 0), 0) == 1.0
    assert cost.cost((1, 0), (0, 0), 0) == 2.0
    assert cost.cost((0, 1), (0, 0), 0) == 2.0


def test_load_directions_expands_rows_and_columns(tmp_path):
    f = tmp_path / "hwy.json"
    f.write_text(json.dumps({"description": "x", "rows": {"0": "E"}, "cols": {"0": "S"}}))
    d = load_directions(f, GRID)
    assert d[(0, 0)] == {E, S}
    assert d[(0, 3)] == {E}
    assert d[(2, 0)] == {S}
    assert (1, 1) not in d  # obstacle
    assert (2, 2) not in d


@pytest.mark.parametrize("name", ["warehouse_small", "narrow_corridor"])
def test_shipped_highways_cover_the_aisles(name):
    grid = GridMap.load(MAPS / f"{name}.map")
    d = load_directions(MAPS / f"{name}.highway.json", grid)
    assert d[(4, 10)] == {E} and d[(8, 10)] == {W}
    assert d[(10, 0)] == {S} and d[(10, 34)] == {N}
    assert all(grid.passable(c) for c in d)


def test_highway_tp_run_is_valid():
    grid = GridMap.load(MAPS / "warehouse_small.map")
    inst = make_instance(grid, 20, 100, 2, seed=0)
    cost = HighwayCost.from_file(MAPS / "warehouse_small.highway.json", grid, w_h=2)
    assert Simulator(inst, TokenPassing(), cost).run().completed
