"""The pluggable task selector in TP / TPTS (foresight/planner/assignment.py)."""

from pathlib import Path as FsPath

import pandas as pd
import pytest

from foresight.analysis import variant_label
from foresight.costs.unit import UnitCost
from foresight.experiment import columns, expand, job_key, run_job
from foresight.interfaces import AgentState, AgentStatus, Path, Task
from foresight.planner import assignment
from foresight.planner.assignment import (
    SELECTORS,
    BaseTaskSelector,
    NearestPickup,
    TaskSelector,
    build_selector,
)
from foresight.planner.token import Token
from foresight.planner.tp import TokenPassing
from foresight.planner.tpts import TokenPassingWithSwaps
from foresight.sim.grid import GridMap
from foresight.sim.instance import MapdInstance, make_instance
from foresight.sim.simulator import Simulator

MAPS = FsPath(__file__).resolve().parents[1] / "maps"

# r = start cells (0,0) and (2,0); e = task endpoints (0,2), (0,4), (2,4)
SMALL = GridMap.from_lines(["r.e.e", ".....", "r...e"])
A, B, C = (0, 2), (0, 4), (2, 4)


def idle(i, loc, t=0):
    return AgentState(i, loc, AgentStatus.IDLE, None, Path(i, t, (loc,)), None)


class FarthestPickup(BaseTaskSelector):
    """The opposite of TP's rule, to show the selector is really used."""

    name = "farthest"

    def rank(self, ctx, candidates):
        return sorted(candidates, key=lambda task: (-ctx.dist(ctx.location, task.pickup), task.task_id))


class Recorder(NearestPickup):
    """TP's rule, remembering what it was asked."""

    def __init__(self):
        self.calls = []
        self.committed, self.released = [], []

    def reset(self, setup):
        super().reset(setup)
        setup.token.add_listener(self)

    def rank(self, ctx, candidates):
        self.calls.append((ctx, list(candidates)))
        return super().rank(ctx, candidates)

    def on_path_committed(self, path):
        self.committed.append(path)

    def on_path_released(self, path):
        self.released.append(path)


def test_default_selector_is_nearest_pickup():
    assert isinstance(TokenPassing().selector, NearestPickup)
    assert isinstance(NearestPickup(), TaskSelector)
    assert SELECTORS[assignment.DEFAULT_SELECTOR] is NearestPickup


def test_custom_selector_changes_the_task_taken():
    near, far = Task(0, A, C, 0), Task(1, C, A, 0)  # pickups 2 and 6 steps away
    inst = MapdInstance(SMALL, ((0, 0),), (near, far))
    for selector, expected in [(None, near), (FarthestPickup(), far)]:
        tp = TokenPassing(selector=selector)
        tp.reset(inst, UnitCost())
        (d,) = tp.step(0, [idle(0, (0, 0))], [near, far])
        assert d.task == expected


def test_selector_sees_the_requesting_agent_and_filtered_candidates():
    blocked, ok = Task(0, A, B, 0), Task(1, C, A, 0)
    inst = MapdInstance(SMALL, ((0, 0), (2, 0)), (blocked, ok))
    rec = Recorder()
    tp = TokenPassing(selector=rec)
    tp.reset(inst, UnitCost())
    assert rec.setup.instance is inst and rec.setup.token is tp.token and rec.setup.dist is tp.dist
    # agent 1 parks at B, the delivery of `blocked`
    tp.token.commit(Path(1, 0, ((2, 0), (1, 0), (1, 1), (1, 2), (1, 3), (1, 4), (0, 4))))
    tp.step(3, [idle(0, (0, 0), t=3)], [blocked, ok])
    ((ctx, candidates),) = rec.calls
    assert (ctx.t, ctx.agent_id, ctx.location) == (3, 0, (0, 0))
    assert ctx.dist((0, 0), A) == 2
    assert candidates == [ok]


def test_selector_is_not_called_without_candidates():
    rec = Recorder()
    tp = TokenPassing(selector=rec)
    tp.reset(MapdInstance(SMALL, ((0, 0),), ()), UnitCost())
    assert tp.step(0, [idle(0, (0, 0))], []) == []
    assert rec.calls == []


def test_empty_ranking_is_an_error():
    class Nothing(BaseTaskSelector):
        def rank(self, ctx, candidates):
            return []

    task = Task(0, A, B, 0)
    tp = TokenPassing(selector=Nothing())
    tp.reset(MapdInstance(SMALL, ((0, 0),), (task,)), UnitCost())
    with pytest.raises(ValueError, match="returned no task"):
        tp.step(0, [idle(0, (0, 0))], [task])


def test_token_listener_gets_existing_and_later_paths():
    token = Token(UnitCost())
    p0, p1 = Path(0, 0, ((0, 0),)), Path(1, 0, ((2, 0),))
    token.commit(p0)
    rec = Recorder()
    token.add_listener(rec)
    assert rec.committed == [p0]  # replayed
    token.commit(p1)
    moved = Path(1, 0, ((2, 0), (2, 1)))
    token.commit(moved)  # replaces p1: release, then commit
    token.release(0)
    assert rec.committed == [p0, p1, moved]
    assert rec.released == [p1, p0]


def test_reservation_table_can_listen_to_the_token():
    from foresight.congestion.reservations import ReservationTable

    token, table = Token(UnitCost()), ReservationTable()
    token.commit(Path(0, 0, ((0, 0), (0, 1))))
    token.add_listener(table)
    token.commit(Path(1, 0, ((2, 0), (2, 1))))
    assert table.vertex_count((0, 1), 1) == 1 and table.vertex_count((2, 1), 1) == 1
    token.release(1)
    assert table.vertex_count((2, 1), 1) == 0 and table.n_paths == 1


@pytest.mark.parametrize("planner", [TokenPassing, TokenPassingWithSwaps])
@pytest.mark.parametrize("map_name, n_agents, n_tasks, rate", [
    ("warehouse_small.map", 20, 80, 5),
    ("narrow_corridor.map", 10, 60, 1),
])
def test_explicit_nearest_pickup_reproduces_tp_and_tpts(planner, map_name, n_agents, n_tasks, rate):
    inst = make_instance(GridMap.load(MAPS / map_name), n_agents, n_tasks, rate, 0)
    default = Simulator(inst, planner(), UnitCost()).run()
    explicit = Simulator(inst, planner(selector=build_selector("nearest")), UnitCost()).run()
    assert default.completed and explicit.paths == default.paths


@pytest.mark.parametrize("planner", [TokenPassing, TokenPassingWithSwaps])
def test_other_selectors_still_give_valid_runs(planner):
    inst = make_instance(GridMap.load(MAPS / "warehouse_small.map"), 20, 80, 5, 0)
    log = Simulator(inst, planner(selector=FarthestPickup()), UnitCost()).run()  # runs assert_valid
    assert log.completed


def test_build_selector_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown task selector"):
        build_selector("nope")


# --- experiment configs -----------------------------------------------------

BASE = {
    "map": "maps/toy_corridor.map",
    "n_tasks": 4,
    "agents": [2],
    "arrival_rates": [1],
    "seeds": [0],
    "methods": {"tp": {}},
}


@pytest.fixture
def farthest(monkeypatch):
    monkeypatch.setitem(SELECTORS, "farthest", FarthestPickup)


def test_configs_without_assignment_keep_their_job_keys():
    (job,) = expand(BASE)
    assert "assignment" not in job and "assignment" not in columns([job])
    assert job_key(job) == job_key({k: job[k] for k in sorted(job)})


def test_assignment_table_is_swept_like_methods(farthest):
    config = {**BASE, "assignment": {"nearest": {}, "farthest": {}}}
    jobs = expand(config)
    assert [(j["assignment"], j["assignment_params"]) for j in jobs] == [("nearest", {}), ("farthest", {})]
    assert "assignment" in columns(jobs)
    with pytest.raises(ValueError, match="unknown task selector"):
        expand({**BASE, "assignment": {"nope": {}}})


def test_run_job_uses_the_selector(farthest):
    (job,) = expand({**BASE, "assignment": {"farthest": {}}})
    row = run_job(job)
    assert row["error"] == "" and row["completed"] and row["assignment"] == "farthest"


def test_variant_label_names_non_default_selectors():
    row = pd.Series({"method": "tp", "param_lam": float("nan"), "assignment": "sij", "aparam_beta": 10.0})
    assert variant_label(row) == "tp + sij(beta=10)"
    assert variant_label(pd.Series({"method": "tp", "assignment": "nearest"})) == "tp"
    assert variant_label(pd.Series({"method": "foresight", "param_lam": 1.0})) == "foresight(lam=1)"
