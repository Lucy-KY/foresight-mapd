from foresight.costs.base import BaseCostModel
from foresight.costs.unit import UnitCost
from foresight.interfaces import Path
from foresight.planner.astar import DistanceTable, bfs_distances, space_time_astar
from foresight.sim.collision import find_conflicts, find_invalid_moves
from foresight.sim.grid import GridMap

OPEN = GridMap.from_lines(["....", "....", "...."])


def path(agent, cells, start=0):
    return Path(agent_id=agent, start_time=start, cells=tuple(cells))


def blocked_by(others):
    """Brute-force stand-in for ``Token.is_blocked``."""

    def is_blocked(u, v, t):
        for p in others:
            if p.at(t + 1) == v:
                return True
            if u != v and p.at(t) == v and p.at(t + 1) == u:
                return True
        return False

    return is_blocked


def stay_allowed_by(others):
    """Brute-force stand-in for ``Token.can_stay``."""

    def can_stay(cell, t):
        return all(
            cell not in p.cells[max(0, t - p.start_time) :] and p.cells[-1] != cell for p in others
        )

    return can_stay


def plan(grid, start, goal, others=(), cost=None, max_time=50, park=False, start_time=0):
    return space_time_astar(
        grid,
        agent_id=9,
        start=start,
        goal=goal,
        start_time=start_time,
        cost_model=cost or UnitCost(),
        is_blocked=blocked_by(others),
        max_time=max_time,
        can_stay=stay_allowed_by(others) if park else None,
    )


def assert_ok(grid, p, others=()):
    assert find_invalid_moves(grid, [p]) == []
    assert find_conflicts([p, *others]) == []


def test_bfs_distances():
    grid = GridMap.from_lines(["...", "@@.", "..."])
    d = bfs_distances(grid, (2, 0))
    assert d[(2, 0)] == 0
    assert d[(0, 0)] == 6
    assert (1, 0) not in d


def test_distance_table_caches_and_reports_unreachable():
    grid = GridMap.from_lines([".@."])
    table = DistanceTable(grid)
    assert table((0, 0), (0, 0)) == 0
    assert table((0, 2), (0, 0)) is None
    assert table.to((0, 0)) is table.to((0, 0))


def test_shortest_path_on_open_grid():
    p = plan(OPEN, (0, 0), (2, 3))
    assert p.start_time == 0 and p.cells[0] == (0, 0) and p.cells[-1] == (2, 3)
    assert p.end_time == 5
    assert_ok(OPEN, p)


def test_start_time_is_kept():
    p = plan(OPEN, (0, 0), (0, 2), start_time=7)
    assert p.start_time == 7 and p.end_time == 9


def test_detours_around_obstacles():
    grid = GridMap.from_lines(["...", "@@.", "..."])
    p = plan(grid, (0, 0), (2, 0))
    assert p.end_time == 6
    assert_ok(grid, p)


def test_start_equals_goal():
    assert plan(OPEN, (1, 1), (1, 1)).cells == ((1, 1),)


def test_unreachable_goal_returns_none():
    grid = GridMap.from_lines([".@."])
    assert plan(grid, (0, 0), (0, 2)) is None


def test_waits_for_vertex_blocker_in_corridor():
    grid = GridMap.from_lines([".....", "@@.@@"])
    other = path(0, [(0, 2), (0, 2), (0, 2), (1, 2)])  # leaves the corridor at t = 3
    p = plan(grid, (0, 0), (0, 4), others=[other])
    assert p.end_time == 5  # enters (0, 2) at t = 3, right after it is vacated
    assert_ok(grid, p, [other])


def test_avoids_swap_conflict():
    grid = GridMap.from_lines(["...", "..."])
    other = path(0, [(0, 1), (0, 0)])  # moves into our start and parks there
    p = plan(grid, (0, 0), (0, 2), others=[other])
    assert p.cells[1] != (0, 1)
    assert p.end_time == 4
    assert_ok(grid, p, [other])


def test_following_is_not_blocked():
    grid = GridMap.from_lines(["...."])
    leader = path(0, [(0, 1), (0, 2), (0, 3)])
    p = plan(grid, (0, 0), (0, 2), others=[leader])
    assert p.cells == ((0, 0), (0, 1), (0, 2))


def test_goal_must_be_free_forever_when_parking():
    other = path(0, [(0, 1)] * 5 + [(1, 1), (2, 1)])  # crosses our goal at t = 5
    assert plan(OPEN, (1, 0), (1, 1), others=[other]).end_time == 1
    p = plan(OPEN, (1, 0), (1, 1), others=[other], park=True)
    assert p.end_time >= 6
    assert stay_allowed_by([other])(p.cells[-1], p.end_time)
    assert_ok(OPEN, p, [other])


def test_gives_up_after_max_time():
    parked = path(0, [(0, 3)])  # sits on our goal forever
    assert plan(OPEN, (0, 0), (0, 3), others=[parked], max_time=10) is None


def test_reaches_goal_exactly_at_max_time():
    assert plan(OPEN, (0, 0), (0, 3), max_time=3).end_time == 3
    assert plan(OPEN, (0, 0), (0, 3), max_time=2) is None


class AvoidCells(BaseCostModel):
    name = "avoid"

    def __init__(self, cells, penalty):
        self.cells = set(cells)
        self.penalty = penalty

    def cost(self, u, v, t):
        return 1.0 + (self.penalty if v in self.cells and u != v else 0.0)


def test_cost_model_steers_around_expensive_cells():
    grid = GridMap.from_lines(["...", "..."])
    p = plan(grid, (0, 0), (0, 2), cost=AvoidCells([(0, 1)], penalty=10))
    assert (0, 1) not in p.cells
    assert p.end_time == 4


def test_takes_short_route_when_penalty_is_small():
    grid = GridMap.from_lines(["...", "..."])
    p = plan(grid, (0, 0), (0, 2), cost=AvoidCells([(0, 1)], penalty=1))
    assert p.cells == ((0, 0), (0, 1), (0, 2))


def test_waiting_is_charged_by_the_cost_model():
    class ExpensiveWait(BaseCostModel):
        def cost(self, u, v, t):
            return 5.0 if u == v else 1.0

    grid = GridMap.from_lines([".....", "@@.@@"])
    other = path(0, [(0, 2), (0, 2), (0, 2), (1, 2)])
    p = plan(grid, (0, 0), (0, 4), others=[other], cost=ExpensiveWait())
    waits = sum(a == b for a, b in zip(p.cells, p.cells[1:]))
    # Stepping back and forth costs 6 and arrives one step later than the
    # unit-cost plan, which waits once (5 + 4 moves = 9 here).
    assert waits == 0
    assert p.end_time == 6
    assert_ok(grid, p, [other])


def test_deterministic_tie_breaking():
    runs = {plan(OPEN, (0, 0), (2, 3)).cells for _ in range(5)}
    assert len(runs) == 1


def test_precomputed_distances_give_same_path():
    table = DistanceTable(OPEN)
    p = space_time_astar(
        OPEN, 9, (0, 0), (2, 3), 0, UnitCost(), blocked_by([]), 50, distances=table.to((2, 3))
    )
    assert p == plan(OPEN, (0, 0), (2, 3))
