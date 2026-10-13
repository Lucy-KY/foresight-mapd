from pathlib import Path as FsPath

import pytest

from foresight.costs.base import BaseCostModel
from foresight.costs.unit import UnitCost
from foresight.interfaces import AgentState, AgentStatus, Path, Planner, Task
from foresight.planner.tp import TokenPassing
from foresight.sim.grid import GridMap
from foresight.sim.instance import MapdInstance, make_instance
from foresight.sim.simulator import Simulator

MAPS = FsPath(__file__).resolve().parents[1] / "maps"

# r = start cells (0,0) and (2,0); e = task endpoints (0,2), (0,4), (2,4)
SMALL = GridMap.from_lines(["r.e.e", ".....", "r...e"])
A, B, C = (0, 2), (0, 4), (2, 4)


def instance(tasks, starts=((0, 0), (2, 0))):
    return MapdInstance(SMALL, tuple(starts), tuple(tasks))


def idle(i, loc, t=0):
    return AgentState(i, loc, AgentStatus.IDLE, None, Path(i, t, (loc,)), None)


def planner_for(inst, cost=None):
    tp = TokenPassing()
    tp.reset(inst, cost or UnitCost())
    return tp


def test_satisfies_planner_protocol():
    assert isinstance(TokenPassing(), Planner)


def test_single_agent_picks_up_and_delivers():
    task = Task(0, A, B, 0)
    inst = instance([task], starts=[(0, 0)])
    (d,) = planner_for(inst).step(0, [idle(0, (0, 0))], [task])
    assert d.task == task
    assert d.path.cells == ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4))
    assert d.pickup_time == 2


def test_takes_task_with_nearest_pickup():
    near, far = Task(0, C, A, 0), Task(1, A, C, 0)
    inst = instance([near, far], starts=[(0, 0)])
    (d,) = planner_for(inst).step(0, [idle(0, (0, 0))], [near, far])
    assert d.task == far  # its pickup (0, 2) is 2 steps away, (2, 4) is 6


def test_agents_request_in_id_order_and_take_different_tasks():
    t0, t1 = Task(0, A, B, 0), Task(1, C, A, 0)
    inst = instance([t0, t1])
    agents = [idle(0, (0, 0)), idle(1, (2, 0))]
    decisions = planner_for(inst).step(0, agents, [t0, t1])
    assert [d.agent_id for d in decisions] == [0, 1]
    assert {d.task.task_id for d in decisions} == {0, 1}


def test_skips_tasks_ending_where_another_agent_parks():
    blocked, ok = Task(0, A, B, 0), Task(1, C, A, 0)
    inst = instance([blocked, ok])
    tp = planner_for(inst)
    tp.token.commit(Path(1, 0, ((2, 0), (1, 0), (1, 1), (1, 2), (1, 3), (1, 4), (0, 4))))
    (d,) = tp.step(0, [idle(0, (0, 0))], [blocked, ok])
    assert d.task == ok


def test_stays_put_without_tasks():
    inst = instance([])
    assert planner_for(inst).step(0, [idle(0, (0, 0)), idle(1, (2, 0))], []) == []


def test_moves_off_the_delivery_of_an_open_task():
    # Agent 1 sits on (0, 2), the delivery of a task whose pickup is under
    # agent 0's parked path end, so nobody can take it; agent 1 must leave.
    task = Task(0, B, A, 0)
    inst = MapdInstance(SMALL, ((0, 0), (2, 0)), (task,))
    tp = planner_for(inst)
    tp.token.release(0)
    tp.token.commit(Path(0, 0, ((0, 4),)))
    tp.token.release(1)
    tp.token.commit(Path(1, 0, ((0, 2),)))
    (d,) = tp.step(0, [idle(1, (0, 2))], [task])
    assert d.agent_id == 1 and d.task is None
    end = d.path.cells[-1]
    assert end in inst.endpoints and end not in {(0, 2), (0, 4)}


class ReleaseCheck(BaseCostModel):
    """Fails if agent 0 still has a path committed while it is being planned."""

    def __init__(self):
        self.committed = {}

    def on_path_committed(self, p):
        self.committed[p.agent_id] = p

    def on_path_released(self, p):
        assert self.committed.pop(p.agent_id) == p

    def cost(self, u, v, t):
        assert 0 not in self.committed
        return 1.0


def test_old_path_is_released_before_planning():
    task = Task(0, A, B, 0)
    inst = instance([task], starts=[(0, 0)])
    cost = ReleaseCheck()
    (d,) = planner_for(inst, cost).step(0, [idle(0, (0, 0))], [task])
    assert cost.committed[0] == d.path


@pytest.mark.parametrize(
    "map_name, n_agents, rate, n_tasks",
    [
        ("toy_corridor.map", 3, 1, 30),
        ("warehouse_small.map", 20, 2, 100),
        ("narrow_corridor.map", 10, 1, 60),
    ],
)
def test_full_runs_complete_without_conflicts(map_name, n_agents, rate, n_tasks):
    grid = GridMap.load(MAPS / map_name)
    inst = make_instance(grid, n_agents, n_tasks, rate, seed=0)
    log = Simulator(inst, TokenPassing(), UnitCost(), max_timesteps=5000).run()  # runs assert_valid
    assert log.completed


def test_runs_are_deterministic():
    grid = GridMap.load(MAPS / "warehouse_small.map")
    inst = make_instance(grid, 10, 40, 1, seed=3)
    a = Simulator(inst, TokenPassing(), UnitCost()).run()
    b = Simulator(inst, TokenPassing(), UnitCost()).run()
    assert a.paths == b.paths
