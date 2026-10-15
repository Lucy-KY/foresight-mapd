"""Unit tests for M3 (ForesightCost).

Costs are checked by hand on single reservations, then plugged into the
real space-time A* to check that they steer paths the intended way.
"""

import pytest

from foresight.costs import METHODS, ForesightCost, UnitCost
from foresight.interfaces import Path
from foresight.planner.astar import space_time_astar
from foresight.sim.grid import GridMap

U, V = (0, 0), (0, 1)


def path(agent, start, cells):
    return Path(agent_id=agent, start_time=start, cells=tuple(cells))


def committed(model, *paths):
    for p in paths:
        model.on_path_committed(p)
    return model


# --- parameters -------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: ForesightCost(lam=-1.0, window=5),
        lambda: ForesightCost(lam=1.0, window=0),
    ],
)
def test_invalid_parameters_are_rejected(make):
    with pytest.raises(ValueError):
        make()


def test_built_from_experiment_config_keys():
    # Same keys as [methods.foresight] in the TOML configs.
    assert isinstance(METHODS["foresight"](lam=1.0, window=5), ForesightCost)


# --- M3 ---------------------------------------------------------------------


def test_m3_zero_lambda_costs_exactly_one():
    m = committed(ForesightCost(lam=0.0, window=5), path(5, 0, [V, V, V]))
    assert m.cost(U, V, 0) == 1.0


def test_m3_waits_cost_one():
    m = committed(ForesightCost(lam=4.0, window=5), path(5, 0, [V, V, V]))
    assert m.cost(V, V, 0) == 1.0


def test_m3_cost_is_share_of_window_reserved():
    m = committed(ForesightCost(lam=2.0, window=5), path(5, 1, [V, V]))  # V at t=1, 2
    assert m.rho(V) == pytest.approx(2 / 5)
    assert m.cost(U, V, 0) == pytest.approx(1.0 + 2.0 * 2 / 5)
    assert m.cost(V, U, 0) == 1.0  # U is free


def test_m3_window_is_half_open():
    m = committed(ForesightCost(lam=1.0, window=5), path(5, 5, [V]))  # V at t=5 only
    assert m.cost(U, V, 0) == 1.0
    m.on_path_committed(path(6, 4, [V]))  # V at t=4
    assert m.cost(U, V, 0) == pytest.approx(1.2)


def test_m3_does_not_depend_on_arrival_time():
    m = committed(ForesightCost(lam=1.0, window=5), path(5, 1, [V, V]))
    assert m.cost(U, V, 0) == m.cost(U, V, 3) == m.cost(U, V, 40) > 1.0


def test_m3_window_moves_with_t_now():
    m = committed(ForesightCost(lam=1.0, window=5), path(5, 1, [V, V]))
    assert m.cost(U, V, 0) > 1.0
    m.on_timestep(10, {})
    assert m.cost(U, V, 10) == 1.0
    m.on_path_committed(path(6, 12, [V]))
    assert m.cost(U, V, 10) == pytest.approx(1.2)


def test_m3_cache_follows_commits_and_releases():
    m = ForesightCost(lam=1.0, window=5)
    p = path(5, 0, [V, V])
    assert m.cost(U, V, 0) == 1.0
    m.on_path_committed(p)
    assert m.cost(U, V, 0) == pytest.approx(1.4)
    m.on_path_released(p)
    assert m.cost(U, V, 0) == 1.0


# --- plugged into space-time A* ---------------------------------------------

# Two equally short routes from S to G: along the top row or the bottom row.
GRID = GridMap.from_lines([".....", ".@@@.", "....."])
S, G = (1, 0), (1, 4)


def plan(cost_model, *others):
    committed(cost_model, *others)
    return space_time_astar(GRID, 9, S, G, 0, cost_model, lambda u, v, t: False, 50)


UNIT = plan(UnitCost())
ROW = UNIT.cells[1][0]  # the row unit-cost A* happens to pick
BUSY = [(ROW, 1), (ROW, 2), (ROW, 3)]  # UNIT reaches them at t = 2, 3, 4
EARLY = path(5, 0, BUSY)  # crosses those cells at t = 0, 1, 2: gone before we arrive
ON_TIME = path(5, 3, BUSY)  # one step behind us: there when we arrive


def uses(p, cells):
    return bool(set(p.cells) & set(cells))


@pytest.mark.parametrize("traffic", [EARLY, ON_TIME])
@pytest.mark.parametrize("make", [lambda: ForesightCost(lam=0.0, window=5)])
def test_zero_weight_gives_the_unit_cost_path(make, traffic):
    assert plan(make(), traffic) == UNIT


def test_m3_avoids_cells_reserved_in_the_window():
    p = plan(ForesightCost(lam=1.0, window=5), EARLY)
    assert not uses(p, BUSY)
    assert p.end_time == UNIT.end_time  # the other row is just as short
