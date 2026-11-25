"""S_ij congestion-aware task assignment (foresight/planner/congestion_assignment.py)."""

from pathlib import Path as FsPath

import pytest

from foresight.costs.unit import UnitCost
from foresight.experiment import expand, run_job
from foresight.interfaces import Path, Task
from foresight.planner.assignment import SELECTORS, SelectionContext, build_selector
from foresight.planner.congestion_assignment import CongestionAwareAssignment
from foresight.planner.tp import TokenPassing
from foresight.planner.tpts import TokenPassingWithSwaps
from foresight.sim.grid import GridMap
from foresight.sim.instance import MapdInstance, make_instance
from foresight.sim.simulator import Simulator

MAPS = FsPath(__file__).resolve().parents[1] / "maps"

# Agent 0 starts at (0, 4), four steps from both pickups (0, 0) and (0, 8).
# The only shortest routes run along row 0 and then down a side column.
GRID = GridMap.from_lines([
    "e...r...e",
    ".........",
    "e...r...e",
])
LEFT = Task(0, (0, 0), (2, 0), 0)
RIGHT = Task(1, (0, 8), (2, 8), 0)


def setup(selector, starts=((0, 4), (2, 4)), tasks=(LEFT, RIGHT)):
    tp = TokenPassing(selector=selector)
    tp.reset(MapdInstance(GRID, starts, tasks), UnitCost())
    return tp


def ctx(tp, t=0, agent=0, loc=(0, 4)):
    return SelectionContext(t, agent, loc, tp.dist)


def test_registered_as_sij():
    assert SELECTORS["sij"] is CongestionAwareAssignment
    assert isinstance(build_selector("sij", {"beta": 10, "gamma": 0.05}), CongestionAwareAssignment)


@pytest.mark.parametrize("kwargs", [{"beta": -1, "gamma": 0}, {"beta": 0, "gamma": -1},
                                    {"beta": 0, "gamma": 0, "alpha": 0}, {"beta": 1, "gamma": 0, "window": 0}])
def test_rejects_bad_parameters(kwargs):
    with pytest.raises(ValueError):
        CongestionAwareAssignment(**kwargs)


def test_equally_near_tasks_go_to_the_uncongested_route():
    sel = CongestionAwareAssignment(beta=10, gamma=0)
    tp = setup(sel)
    tp.token.commit(Path(1, 0, ((2, 4), (1, 4), (1, 3), (1, 2), (0, 2), *[(0, 2)] * 8)))  # sits on row 0
    assert sel.rho(ctx(tp), (0, 2)) == pytest.approx(1 / 5)  # reserved at t = 4 only, window [0, 4]
    assert sel.congestion(ctx(tp), LEFT) > 0 and sel.congestion(ctx(tp), RIGHT) == 0
    assert sel.rank(ctx(tp), [LEFT, RIGHT])[0] == RIGHT
    # TP's rule breaks the tie by task id instead
    assert build_selector("nearest").rank(ctx(tp), [LEFT, RIGHT])[0] == LEFT


def test_a_task_that_waited_long_beats_a_slightly_nearer_new_one():
    near_new, far_old = Task(0, (0, 2), (2, 0), 10), Task(1, (0, 8), (2, 8), 0)  # 2 vs 4 steps away
    for gamma, first in [(0.0, near_new), (0.5, far_old)]:
        sel = CongestionAwareAssignment(beta=0, gamma=gamma)
        tp = setup(sel, tasks=(near_new, far_old))
        assert sel.rank(ctx(tp, t=10), [near_new, far_old])[0] == first


def test_own_old_path_is_not_congestion():
    sel = CongestionAwareAssignment(beta=10, gamma=0)
    tp = setup(sel)
    tp.token.commit(Path(0, 0, ((0, 3), (0, 4))))  # agent 0's own path, ends at t = 1
    assert sel.reservations.vertex_count((0, 4), 1) == 1
    assert sel.rho(ctx(tp, t=1), (0, 4)) == 0


def test_route_is_a_shortest_connected_route():
    inst = make_instance(GridMap.load(MAPS / "narrow_corridor.map"), 5, 10, 1, 0)
    sel = CongestionAwareAssignment(beta=1, gamma=0)
    tp = TokenPassing(selector=sel)
    tp.reset(inst, UnitCost())
    a, (b, c) = inst.initial_locations[0], inst.grid.task_endpoints[:2]
    for s, g in [(a, b), (b, c), (b, b)]:
        route = sel.route(ctx(tp, loc=s), s, g)
        assert route[0] == s and route[-1] == g and len(route) == tp.dist(s, g) + 1
        assert all(v in inst.grid.neighbors(u) for u, v in zip(route, route[1:]))


@pytest.mark.parametrize("planner", [TokenPassing, TokenPassingWithSwaps])
@pytest.mark.parametrize("map_name, n_agents, n_tasks, rate", [
    ("warehouse_small.map", 20, 80, 5),
    ("narrow_corridor.map", 10, 60, 1),
])
def test_zero_weights_reproduce_tp(planner, map_name, n_agents, n_tasks, rate):
    """beta = gamma = 0 must take exactly TP's tasks, so every path is TP's."""
    inst = make_instance(GridMap.load(MAPS / map_name), n_agents, n_tasks, rate, 0)
    tp = Simulator(inst, planner(), UnitCost()).run()
    sij = Simulator(inst, planner(selector=CongestionAwareAssignment(beta=0, gamma=0)), UnitCost()).run()
    assert tp.completed and sij.paths == tp.paths


class Checked(CongestionAwareAssignment):
    """Asserts that the pruned ranking puts the true minimum of S_ij first."""

    def rank(self, ctx, candidates):
        ranked = super().rank(ctx, candidates)
        score = {t.task_id: self.alpha * ctx.dist(ctx.location, t.pickup) + self.beta * self.congestion(ctx, t)
                 - self.gamma * (ctx.t - t.release_time) for t in candidates}
        best = min(score.values())
        assert score[ranked[0].task_id] == pytest.approx(best)
        assert sorted(t.task_id for t in ranked) == sorted(t.task_id for t in candidates)
        self.calls = getattr(self, "calls", 0) + 1
        return ranked


def test_pruning_finds_the_true_minimum():
    inst = make_instance(GridMap.load(MAPS / "warehouse_small.map"), 30, 120, 5, 0)
    sel = Checked(beta=20, gamma=0.05, max_scored=10**6)
    log = Simulator(inst, TokenPassing(selector=sel), UnitCost()).run()
    assert log.completed and sel.calls > 100


def test_nonzero_weights_change_assignments_and_runs_stay_valid():
    inst = make_instance(GridMap.load(MAPS / "narrow_corridor.map"), 30, 150, 5, 0)
    tp = Simulator(inst, TokenPassing(), UnitCost()).run()
    sij = Simulator(inst, TokenPassing(selector=CongestionAwareAssignment(beta=20, gamma=0.05)), UnitCost()).run()
    assert sij.completed and sij.paths != tp.paths  # run() checks conflicts


def test_config_and_run_job():
    config = {"map": "maps/toy_corridor.map", "n_tasks": 6, "agents": [2], "arrival_rates": [1], "seeds": [0],
              "methods": {"foresight": {"lam": 1.0, "window": 5}},
              "assignment": {"sij": {"beta": [5.0, 10.0], "gamma": 0.05}}}
    jobs = expand(config)
    assert [j["assignment_params"]["beta"] for j in jobs] == [5.0, 10.0]
    row = run_job(jobs[0])
    assert row["error"] == "" and row["completed"] and row["assignment"] == "sij"
    assert row["service_time_max"] >= row["service_time_p95"]
