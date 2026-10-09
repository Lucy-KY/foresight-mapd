import pytest

from foresight.interfaces import Path
from foresight.sim.collision import (
    Conflict,
    assert_valid,
    find_conflicts,
    find_invalid_moves,
)
from foresight.sim.grid import GridMap

OPEN = GridMap.from_lines(["....", "....", "...."])


def path(agent, cells, start=0):
    return Path(agent_id=agent, start_time=start, cells=tuple(cells))


def test_disjoint_paths_have_no_conflicts():
    a = path(0, [(0, 0), (0, 1), (0, 2)])
    b = path(1, [(2, 0), (2, 1), (2, 2)])
    assert find_conflicts([a, b]) == []


def test_vertex_conflict():
    a = path(0, [(0, 0), (0, 1)])
    b = path(1, [(0, 2), (0, 1)])
    assert find_conflicts([a, b]) == [Conflict("vertex", (0, 1), 1, ((0, 1),))]


def test_swap_conflict():
    a = path(0, [(0, 0), (0, 1)])
    b = path(1, [(0, 1), (0, 0)])
    assert find_conflicts([a, b]) == [Conflict("swap", (0, 1), 0, ((0, 0), (0, 1)))]


def test_following_is_allowed():
    leader = path(0, [(0, 1), (0, 2), (0, 3)])
    follower = path(1, [(0, 0), (0, 1), (0, 2)])
    assert find_conflicts([leader, follower]) == []


def test_three_agents_in_one_cell_give_three_pairs():
    paths = [
        path(0, [(1, 0), (1, 1)]),
        path(1, [(0, 1), (1, 1)]),
        path(2, [(1, 2), (1, 1)]),
    ]
    pairs = sorted(c.agents for c in find_conflicts(paths))
    assert pairs == [(0, 1), (0, 2), (1, 2)]


def test_parked_agent_blocks_its_last_cell():
    parked = path(0, [(0, 0), (0, 1)])  # stays at (0, 1) from t=1 on
    passer = path(1, [(1, 3), (0, 3), (0, 2), (0, 1)])
    conflicts = find_conflicts([parked, passer])
    assert conflicts == [Conflict("vertex", (0, 1), 3, ((0, 1),))]


def test_agent_is_not_checked_before_its_start_time():
    early = path(0, [(0, 0), (0, 1), (0, 2)])
    late = path(1, [(0, 1), (1, 1)], start=3)  # starts after agent 0 left (0, 1)
    assert find_conflicts([early, late]) == []


def test_duplicate_agent_ids_are_rejected():
    with pytest.raises(ValueError):
        find_conflicts([path(0, [(0, 0)]), path(0, [(1, 1)])])


def test_invalid_moves():
    g = GridMap.from_lines(["..@", "...", "..."])
    jump = path(0, [(0, 0), (0, 1), (2, 1)])  # second step jumps two rows
    into_wall = path(1, [(1, 2), (0, 2)])
    diagonal = path(2, [(2, 0), (1, 1)])
    reasons = sorted((m.agent, m.reason) for m in find_invalid_moves(g, [jump, into_wall, diagonal]))
    assert reasons == [
        (0, "not a 4-neighbor move"),
        (1, "moves into a blocked cell"),
        (2, "not a 4-neighbor move"),
    ]


def test_waits_are_valid_moves():
    assert find_invalid_moves(OPEN, [path(0, [(1, 1), (1, 1), (1, 2)])]) == []


def test_assert_valid_reports_problems():
    a = path(0, [(0, 0), (0, 1)])
    b = path(1, [(0, 1), (0, 0)])
    with pytest.raises(AssertionError, match="swap conflict"):
        assert_valid([a, b], OPEN)
    assert_valid([path(0, [(0, 0), (0, 1)])], OPEN)
