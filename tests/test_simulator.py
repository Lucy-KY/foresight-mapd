from pathlib import Path as FsPath

import pytest

from foresight.costs import UnitCost
from foresight.costs.base import BaseCostModel
from foresight.interfaces import AgentStatus, Decision, Path, Planner, Task
from foresight.sim.grid import GridMap
from foresight.sim.instance import MapdInstance, make_instance
from foresight.sim.metrics import RunResult
from foresight.sim.simulator import PlannerError, Simulator
from foresight.sim.stubs import IdlePlanner, OneAtATimePlanner, bfs

MAPS = FsPath(__file__).resolve().parents[1] / "maps"

# r = start cells (0,0) and (2,0); e = task endpoints (0,2), (0,4), (2,4)
SMALL = GridMap.from_lines(["r.e.e", ".....", "r...e"])
A, B, C = (0, 2), (0, 4), (2, 4)


def instance(tasks):
    return MapdInstance(SMALL, ((0, 0), (2, 0)), tuple(tasks))


def path(agent, start, cells):
    return Path(agent_id=agent, start_time=start, cells=tuple(cells))


class Scripted:
    """Returns ``script[t](agents, open_tasks)`` at t, records what it saw."""

    def __init__(self, script):
        self.script = script
        self.seen_open = {}

    def reset(self, instance, cost_model):
        pass

    def step(self, t, agents, open_tasks):
        self.seen_open[t] = [task.task_id for task in open_tasks]
        return self.script[t](agents, open_tasks) if t in self.script else []


class RecordingCost(BaseCostModel):
    def __init__(self):
        self.calls = []

    def on_timestep(self, t, positions):
        self.calls.append((t, dict(positions)))


def run(planner, tasks, max_timesteps=50, check=True):
    return Simulator(instance(tasks), planner, UnitCost(), max_timesteps).run(check=check)


TASK0 = Task(0, A, B, release_time=0)  # (0,0) -> (0,2) -> (0,4)
TO_A_THEN_B = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]


def test_planners_satisfy_the_protocol():
    assert isinstance(IdlePlanner(), Planner)
    assert isinstance(OneAtATimePlanner(), Planner)


def test_one_task_lifecycle_produces_a_record():
    planner = Scripted({0: lambda agents, _: [Decision(0, path(0, 0, TO_A_THEN_B), TASK0, pickup_time=2)]})
    log = run(planner, [TASK0])
    assert log.completed and log.n_timesteps == 4
    (rec,) = log.records
    assert (rec.agent_id, rec.assigned_time, rec.pickup_time, rec.delivery_time) == (0, 0, 2, 4)
    assert log.paths[0].cells == tuple(TO_A_THEN_B)
    assert log.paths[1].cells == ((2, 0),) * 5  # idle agent stays put


def test_status_changes_at_pickup_and_delivery():
    seen = {}

    def watch(t):
        def f(agents, _):
            seen[t] = (agents[0].status, agents[0].location)
            return [Decision(0, path(0, 0, TO_A_THEN_B), TASK0, 2)] if t == 0 else []
        return f

    run(Scripted({t: watch(t) for t in range(4)}), [TASK0])
    assert seen[1] == (AgentStatus.TO_PICKUP, (0, 1))
    assert seen[2] == (AgentStatus.TO_DELIVERY, (0, 2))
    assert seen[3] == (AgentStatus.TO_DELIVERY, (0, 3))


def test_only_released_tasks_are_offered():
    late = Task(1, A, C, release_time=3)
    planner = Scripted({})
    run(planner, [TASK0, late], max_timesteps=5)
    assert planner.seen_open[2] == [0] and planner.seen_open[3] == [0, 1]


def test_giving_up_a_task_puts_it_back_in_open():
    planner = Scripted({
        0: lambda a, _: [Decision(0, path(0, 0, [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]), TASK0, 2)],
        1: lambda a, _: [Decision(0, path(0, 1, [(0, 1), (0, 0)]))],
    })
    log = run(planner, [TASK0], max_timesteps=4)
    assert planner.seen_open[1] == [] and planner.seen_open[2] == [0]
    assert not log.completed


def test_pickup_at_assignment_time():
    task = Task(0, (0, 0), A, release_time=0)  # agent 0 already stands on the pickup
    planner = Scripted({0: lambda a, _: [Decision(0, path(0, 0, [(0, 0), (0, 1), (0, 2)]), task, 0)]})
    log = run(planner, [task])
    assert log.records[0].pickup_time == 0 and log.records[0].delivery_time == 2


def test_cost_model_sees_every_timestep():
    cost = RecordingCost()
    planner = Scripted({0: lambda a, _: [Decision(0, path(0, 0, TO_A_THEN_B), TASK0, 2)]})
    Simulator(instance([TASK0]), planner, cost).run()
    assert [t for t, _ in cost.calls] == [0, 1, 2, 3, 4]
    assert cost.calls[2][1] == {0: (0, 2), 1: (2, 0)}


def test_idle_planner_hits_the_step_limit():
    log = run(IdlePlanner(), [TASK0], max_timesteps=10)
    assert not log.completed and log.n_timesteps == 10
    assert len(log.plan_times_ms) == 10
    assert all(len(p.cells) == 11 for p in log.paths)


@pytest.mark.parametrize(
    "decision, message",
    [
        (Decision(0, path(0, 1, TO_A_THEN_B), TASK0, 2), "must start at t=0"),
        (Decision(0, path(0, 0, [(1, 1), (0, 1)]), None), "must start at t=0"),
        (Decision(0, path(0, 0, [(0, 0), (1, 0)]), None), "not an endpoint"),
        (Decision(0, path(0, 0, TO_A_THEN_B), TASK0, 1), "not at pickup"),
        (Decision(0, path(0, 0, TO_A_THEN_B), TASK0, None), "needs a pickup_time"),
        (Decision(0, path(0, 0, TO_A_THEN_B[:3]), TASK0, 2), "must end at delivery"),
        (Decision(0, path(0, 0, TO_A_THEN_B), Task(9, A, B, 0), 2), "not released or not open"),
        (Decision(7, path(7, 0, [(0, 0)]), None), "unknown agent"),
    ],
)
def test_invalid_decisions_are_rejected(decision, message):
    with pytest.raises(PlannerError, match=message):
        run(Scripted({0: lambda a, _: [decision]}), [TASK0])


def test_two_decisions_for_one_agent_are_rejected():
    d = Decision(0, path(0, 0, [(0, 0)]))
    with pytest.raises(PlannerError, match="two decisions"):
        run(Scripted({0: lambda a, _: [d, d]}), [TASK0])


def test_carrying_agent_cannot_be_replanned():
    planner = Scripted({
        0: lambda a, _: [Decision(0, path(0, 0, TO_A_THEN_B), TASK0, 2)],
        3: lambda a, _: [Decision(0, path(0, 3, [(0, 3), (0, 4)]))],
    })
    with pytest.raises(PlannerError, match="carrying"):
        run(planner, [TASK0])


def test_task_swap_needs_a_decision_for_the_old_holder():
    swap_only = Scripted({
        0: lambda a, _: [Decision(0, path(0, 0, TO_A_THEN_B), TASK0, 2)],
        1: lambda a, _: [Decision(1, path(1, 1, [(2, 0), (1, 0), (1, 1), (1, 2), (0, 2), (0, 3), (0, 4)]), TASK0, 5)],
    })
    with pytest.raises(PlannerError, match="held by agents"):
        run(swap_only, [TASK0])


def test_task_swap_with_both_decisions():
    swap = Scripted({
        0: lambda a, _: [Decision(0, path(0, 0, TO_A_THEN_B), TASK0, 2)],
        1: lambda a, _: [
            Decision(1, path(1, 1, [(2, 0), (1, 0), (1, 1), (1, 2), (0, 2), (0, 3), (0, 4)]), TASK0, 5),
            Decision(0, path(0, 1, [(0, 1), (0, 0)])),
        ],
    })
    log = run(swap, [TASK0])
    (rec,) = log.records
    assert (rec.agent_id, rec.assigned_time, rec.pickup_time, rec.delivery_time) == (1, 1, 5, 7)


def test_conflicting_trajectories_raise_unless_check_is_off():
    # Agent 0 waits two steps at (0, 0); agent 1 walks onto (0, 0) at t=2.
    collide = {
        0: lambda a, _: [
            Decision(0, path(0, 0, [(0, 0), (0, 0), (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]), TASK0, 4),
            Decision(1, path(1, 0, [(2, 0), (1, 0), (0, 0)])),
        ],
    }
    with pytest.raises(AssertionError, match="vertex conflict"):
        run(Scripted(collide), [TASK0])
    log = run(Scripted(collide), [TASK0], check=False)
    assert log.completed
    assert log.to_result(RunResult("x", "small", 2, 1, 0)).n_conflicts == 1


def test_bfs_avoids_blocked_cells():
    assert bfs(SMALL, (0, 0), (0, 2), blocked={(0, 1)}) == [(0, 0), (1, 0), (1, 1), (1, 2), (0, 2)]
    assert bfs(SMALL, (0, 0), (0, 2), blocked={(0, 2)}) is None


@pytest.mark.parametrize(
    "map_name, n_agents, n_tasks, rate",
    [("toy_corridor.map", 2, 10, 0.5), ("warehouse_small.map", 5, 20, 1), ("narrow_corridor.map", 5, 20, 1)],
)
def test_one_at_a_time_planner_completes_real_instances(map_name, n_agents, n_tasks, rate):
    grid = GridMap.load(MAPS / map_name)
    inst = make_instance(grid, n_agents=n_agents, n_tasks=n_tasks, arrival_rate=rate, seed=0)
    log = Simulator(inst, OneAtATimePlanner(), UnitCost(), max_timesteps=20_000).run()
    assert log.completed
    assert sorted(r.task.task_id for r in log.records) == list(range(n_tasks))
    for r in log.records:
        assert r.task.release_time <= r.assigned_time <= r.pickup_time < r.delivery_time
    result = log.to_result(RunResult("stub", map_name, n_agents, rate, 0))
    assert result.completed and result.n_conflicts == 0
    assert result.makespan == log.n_timesteps
