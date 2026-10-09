from pathlib import Path

import pytest

from foresight.sim.grid import GridMap
from foresight.sim.tasks import generate_task_stream, release_times

MAPS = Path(__file__).resolve().parents[1] / "maps"


@pytest.mark.parametrize(
    "rate, expected",
    [
        (0.2, [0, 5, 10, 15, 20]),
        (0.5, [0, 2, 4, 6, 8]),
        (1, [0, 1, 2, 3, 4]),
        (2, [0, 0, 1, 1, 2]),
        (10, [0, 0, 0, 0, 0]),
    ],
)
def test_release_times_match_paper_rates(rate, expected):
    assert release_times(5, rate) == expected


def test_release_times_reject_non_positive_rate():
    with pytest.raises(ValueError):
        release_times(5, 0)


def test_stream_is_deterministic_and_valid():
    grid = GridMap.load(MAPS / "warehouse_small.map")
    a = generate_task_stream(grid, 500, 1, seed=3)
    b = generate_task_stream(grid, 500, 1, seed=3)
    assert a == b
    endpoints = set(grid.task_endpoints)
    for task in a:
        assert task.pickup in endpoints and task.delivery in endpoints
        assert task.pickup != task.delivery
    assert [t.task_id for t in a] == list(range(500))


def test_same_seed_same_locations_at_every_rate():
    grid = GridMap.load(MAPS / "warehouse_small.map")
    slow = generate_task_stream(grid, 50, 0.2, seed=7)
    fast = generate_task_stream(grid, 50, 10, seed=7)
    assert [(t.pickup, t.delivery) for t in slow] == [(t.pickup, t.delivery) for t in fast]
    assert generate_task_stream(grid, 50, 1, seed=8) != generate_task_stream(grid, 50, 1, seed=7)
