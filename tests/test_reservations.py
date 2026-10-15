import random

import pytest

from foresight.congestion.reservations import ReservationTable
from foresight.interfaces import Path


def path(agent, start, cells):
    return Path(agent_id=agent, start_time=start, cells=tuple(cells))


# (0,0) at t=2, (0,1) at t=3 and t=4 (a wait), (0,2) at t=5
A = path(0, 2, [(0, 0), (0, 1), (0, 1), (0, 2)])
# (0,1) at t=4, (1,1) at t=5
B = path(1, 4, [(0, 1), (1, 1)])


def table(*paths):
    t = ReservationTable()
    for p in paths:
        t.add_path(p)
    return t


def test_empty_table_counts_zero():
    t = ReservationTable()
    assert t.vertex_count((0, 0), 0) == 0
    assert t.edge_count((0, 0), (0, 1), 0) == 0
    assert t.vertex_window((0, 0), -10, 10) == 0
    assert t.edge_window((0, 0), (0, 1), -10, 10) == 0
    assert t.n_paths == 0


def test_counts_every_occupied_timestep_including_waits():
    t = table(A)
    assert t.vertex_count((0, 0), 2) == 1
    assert t.vertex_count((0, 1), 3) == 1
    assert t.vertex_count((0, 1), 4) == 1
    assert t.vertex_count((0, 2), 5) == 1
    assert t.vertex_count((0, 0), 3) == 0
    assert t.n_paths == 1


def test_waits_are_not_moves():
    t = table(A)
    assert t.edge_count((0, 0), (0, 1), 2) == 1
    assert t.edge_count((0, 1), (0, 2), 4) == 1
    assert t.edge_count((0, 1), (0, 1), 3) == 0  # the wait
    assert t.edge_count((0, 1), (0, 2), 3) == 0  # still waiting at t=3


def test_edges_are_directed():
    t = table(A)
    assert t.edge_count((0, 1), (0, 0), 2) == 0


def test_nothing_is_counted_before_start_or_while_parked():
    t = table(A)
    assert t.vertex_count((0, 0), 1) == 0  # before start_time
    assert t.vertex_count((0, 2), 6) == 0  # parked after end_time
    assert t.vertex_window((0, 2), 6, 100) == 0


def test_counts_from_several_paths_add_up():
    t = table(A, B)
    assert t.vertex_count((0, 1), 4) == 2
    assert t.vertex_count((0, 1), 3) == 1
    assert t.edge_count((0, 1), (1, 1), 4) == 1
    assert t.n_paths == 2


def test_remove_undoes_add():
    t = table(A, B)
    t.remove_path(A)
    assert t.vertex_count((0, 1), 4) == 1
    assert t.vertex_count((0, 1), 3) == 0
    assert t.edge_count((0, 0), (0, 1), 2) == 0
    assert t.edge_count((0, 1), (1, 1), 4) == 1
    t.remove_path(B)
    assert t.n_paths == 0
    assert t.vertex_window((0, 1), -100, 100) == 0
    assert not t._vertex and not t._edge  # no empty entries left behind


def test_removing_twice_raises_and_leaves_table_unchanged():
    t = table(A, B)
    t.remove_path(A)
    with pytest.raises(ValueError, match="agent 0"):
        t.remove_path(A)
    assert t.vertex_count((0, 1), 4) == 1  # B untouched
    assert t.n_paths == 1


def test_removing_a_path_never_added_raises():
    t = table(A)
    with pytest.raises(ValueError):
        t.remove_path(B)
    assert t.vertex_count((0, 1), 3) == 1
    assert t.n_paths == 1


def test_vertex_window_is_inclusive():
    t = table(A)  # (0,1) reserved at t=3 and t=4
    assert t.vertex_window((0, 1), 3, 4) == 2
    assert t.vertex_window((0, 1), 3, 3) == 1
    assert t.vertex_window((0, 1), 4, 10) == 1
    assert t.vertex_window((0, 1), 0, 2) == 0
    assert t.vertex_window((0, 1), 5, 10) == 0
    assert t.vertex_window((0, 1), 4, 3) == 0  # empty window


def test_edge_window_is_inclusive():
    t = table(A)  # (0,0) -> (0,1) during [2, 3]
    assert t.edge_window((0, 0), (0, 1), 2, 2) == 1
    assert t.edge_window((0, 0), (0, 1), 0, 1) == 0
    assert t.edge_window((0, 0), (0, 1), 3, 9) == 0
    assert t.edge_window((0, 1), (0, 0), 0, 9) == 0


def _random_path(rng, agent, size=4):
    cell = (rng.randrange(size), rng.randrange(size))
    cells = [cell]
    for _ in range(rng.randrange(8)):
        r, c = cell
        options = [(r, c), (r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
        cell = rng.choice([(a, b) for a, b in options if 0 <= a < size and 0 <= b < size])
        cells.append(cell)
    return path(agent, rng.randrange(10), cells)


def test_matches_brute_force_on_random_paths():
    rng = random.Random(0)
    paths = [_random_path(rng, i) for i in range(40)]
    t = table(*paths)
    for p in rng.sample(paths, 20):
        t.remove_path(p)
        paths.remove(p)

    def vertex(v, s):
        return sum(1 for p in paths if p.start_time <= s <= p.end_time and p.at(s) == v)

    def edge(u, v, s):
        return sum(1 for p in paths for a, b, k in p.moves() if a != b and (a, b, k) == (u, v, s))

    cells = [(r, c) for r in range(4) for c in range(4)]
    for v in cells:
        for s in range(-1, 19):
            assert t.vertex_count(v, s) == vertex(v, s)
        for lo, hi in [(0, 0), (2, 6), (5, 30), (-5, 100)]:
            assert t.vertex_window(v, lo, hi) == sum(vertex(v, s) for s in range(lo, hi + 1))
        for u in cells:
            if abs(u[0] - v[0]) + abs(u[1] - v[1]) != 1:
                continue
            for lo, hi in [(3, 3), (0, 7), (-5, 100)]:
                assert t.edge_window(u, v, lo, hi) == sum(edge(u, v, s) for s in range(lo, hi + 1))
    assert t.n_paths == 20
