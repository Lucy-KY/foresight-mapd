"""Unit tests for M3 (ForesightCost) and M4 (SpatioTemporalCost).

Costs are checked by hand on single reservations, then plugged into the
real space-time A* to check that they steer paths the intended way.
"""

import pytest

from foresight.costs import METHODS, ForesightCost, SpatioTemporalCost, UnitCost
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
        lambda: SpatioTemporalCost(lam=-0.5, delta=1),
        lambda: SpatioTemporalCost(lam=1.0, delta=0),
    ],
)
def test_invalid_parameters_are_rejected(make):
    with pytest.raises(ValueError):
        make()


def test_built_from_experiment_config_keys():
    # Same keys as [methods.foresight] / [methods.foresight_st] in the TOML configs.
    assert isinstance(METHODS["foresight"](lam=1.0, window=5), ForesightCost)
    assert isinstance(METHODS["foresight_st"](lam=1.0, delta=2), SpatioTemporalCost)


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


# --- M4 ---------------------------------------------------------------------


def test_m4_zero_lambda_costs_exactly_one():
    m = committed(SpatioTemporalCost(lam=0.0, delta=2), path(5, 0, [V, V, V]))
    assert m.cost(U, V, 0) == 1.0


def test_m4_waits_cost_one():
    m = committed(SpatioTemporalCost(lam=4.0, delta=2), path(5, 0, [V, V, V]))
    assert m.cost(V, V, 0) == 1.0


def test_m4_counts_reservations_around_arrival_time():
    m = committed(SpatioTemporalCost(lam=3.0, delta=1), path(5, 6, [V]))  # V at t=6 only
    # Moving at t arrives at t + 1, so t + 1 in [5, 7] sees the reservation.
    assert m.cost(U, V, 3) == 1.0
    assert m.cost(U, V, 4) == pytest.approx(2.0)
    assert m.cost(U, V, 5) == pytest.approx(2.0)
    assert m.cost(U, V, 6) == pytest.approx(2.0)
    assert m.cost(U, V, 7) == 1.0


def test_m4_divides_by_full_window():
    m = committed(SpatioTemporalCost(lam=1.0, delta=2), path(5, 3, [V]), path(6, 7, [V]))
    assert m.rho(V, 5) == pytest.approx(2 / 5)  # window [3, 7]
    assert m.cost(U, V, 4) == pytest.approx(1.4)


def test_m4_ignores_reservations_before_t_now():
    m = committed(SpatioTemporalCost(lam=1.0, delta=2), path(5, 3, [V]))  # V at t=3
    assert m.cost(U, V, 3) == pytest.approx(1.2)  # t_now = 0: window [2, 6]
    m.on_timestep(4, {})
    assert m.cost(U, V, 3) == 1.0  # window [4, 6]: t=3 is the past


def test_m4_cache_follows_commits_and_releases():
    m = SpatioTemporalCost(lam=1.0, delta=1)
    p = path(5, 2, [V])
    assert m.cost(U, V, 1) == 1.0
    m.on_path_committed(p)
    assert m.cost(U, V, 1) == pytest.approx(1 + 1 / 3)
    m.on_path_released(p)
    assert m.cost(U, V, 1) == 1.0


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
@pytest.mark.parametrize(
    "make", [lambda: ForesightCost(lam=0.0, window=5), lambda: SpatioTemporalCost(lam=0.0, delta=1)]
)
def test_zero_weight_gives_the_unit_cost_path(make, traffic):
    assert plan(make(), traffic) == UNIT


def test_m3_avoids_cells_reserved_in_the_window():
    p = plan(ForesightCost(lam=1.0, window=5), EARLY)
    assert not uses(p, BUSY)
    assert p.end_time == UNIT.end_time  # the other row is just as short


def test_m4_ignores_traffic_that_is_gone_when_it_arrives():
    # Contribution 1: M3 would detour here (test above), M4 knows the
    # corridor is empty by the time the agent gets there.
    assert plan(SpatioTemporalCost(lam=1.0, delta=1), EARLY) == UNIT


def test_m4_avoids_traffic_that_is_there_when_it_arrives():
    p = plan(SpatioTemporalCost(lam=1.0, delta=1), ON_TIME)
    assert not uses(p, BUSY)
    assert p.end_time == UNIT.end_time
