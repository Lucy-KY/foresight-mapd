from pathlib import Path

import pytest

from foresight.sim.grid import GridMap

TOY = Path(__file__).resolve().parents[1] / "maps" / "toy_corridor.map"


def test_load_toy_map():
    g = GridMap.load(TOY)
    assert (g.height, g.width) == (5, 9)
    assert len(g.task_endpoints) == 3
    assert len(g.homes) == 4


def test_neighbors_skip_obstacles_and_bounds():
    g = GridMap.load(TOY)
    assert sorted(g.neighbors((0, 0))) == [(0, 1), (1, 0)]
    assert not g.passable((1, 1))
    assert not g.passable((-1, 0))


def test_rejects_ragged_rows():
    with pytest.raises(ValueError):
        GridMap.from_lines(["...", ".."])
