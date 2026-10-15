from pathlib import Path as FsPath

import pytest

from foresight.costs.unit import UnitCost
from foresight.interfaces import AgentState, AgentStatus, Path, Planner, Task
from foresight.planner.tp import TokenPassing
from foresight.planner.tpts import TokenPassingWithSwaps
from foresight.sim.grid import GridMap
from foresight.sim.instance import MapdInstance, make_instance
from foresight.sim.simulator import Simulator

MAPS = FsPath(__file__).resolve().parents[1] / "maps"

# r = start cells (0,0) and (2,0); e = task endpoints (0,2), (0,4), (2,4)
SMALL = GridMap.from_lines(["r.e.e", ".....", "r...e"])
TASK = Task(0, (0, 2), (2, 4), release_time=0)
INSTANCE = MapdInstance(SMALL, ((0, 0), (2, 0)), (TASK,))


def idle(i, loc):
    return AgentState(i, loc, AgentStatus.IDLE, None, Path(i, 0, (loc,)), None)


def setup(holder_cells, pickup_time):
    """Agent 0 idle at (0, 0); agent 1 already holds TASK on ``holder_cells``."""
    tpts = TokenPassingWithSwaps()
    tpts.reset(INSTANCE, UnitCost())
    path1 = Path(1, 0, tuple(holder_cells))
    tpts.token.commit(path1)
    holder = AgentState(1, holder_cells[0], AgentStatus.TO_PICKUP, TASK, path1, pickup_time)
    return tpts, [idle(0, (0, 0)), holder]


def apply(agents, decisions):
    """Run the simulator's own contract checks on the decisions."""
    return Simulator._apply(0, agents, decisions, {}, {}, {}, set(INSTANCE.endpoints))


def test_satisfies_planner_protocol():
    assert isinstance(TokenPassingWithSwaps(), Planner)


def test_takes_task_from_slower_agent():
    # Agent 1 dawdles for 5 steps and reaches the pickup at t = 9; agent 0
    # is 2 steps away.
    slow = [(2, 0)] * 6 + [(1, 0), (1, 1), (1, 2), (0, 2), (1, 2), (1, 3), (1, 4), (2, 4)]
    tpts, agents = setup(slow, pickup_time=9)
    decisions = tpts.step(0, agents, [])
    by_agent = {d.agent_id: d for d in decisions}
    assert by_agent[0].task == TASK and by_agent[0].pickup_time == 2
    assert by_agent[1].task is None  # gave it up; rests at its start cell
    assert by_agent[1].path.cells == ((2, 0),)
    new = apply(agents, decisions)
    assert new[0].task == TASK and new[1].status is AgentStatus.IDLE
    assert tpts.token.paths[0] == by_agent[0].path
    assert tpts.token.paths[1] == by_agent[1].path


def test_keeps_assignment_when_holder_is_not_slower():
    fast = [(1, 2), (0, 2), (1, 2), (1, 3), (1, 4), (2, 4)]
    tpts, agents = setup(fast, pickup_time=1)
    before = dict(tpts.token.paths)
    assert tpts.step(0, agents, []) == []
    assert tpts.token.paths == before


def test_victim_mid_corridor_moves_to_a_free_endpoint():
    # Agent 1 is in the middle row (not an endpoint) when it loses the task.
    slow = [(1, 1)] * 8 + [(1, 2), (0, 2), (1, 2), (1, 3), (1, 4), (2, 4)]
    tpts, agents = setup(slow, pickup_time=9)
    by_agent = {d.agent_id: d for d in tpts.step(0, agents, [])}
    assert by_agent[0].task == TASK
    victim = by_agent[1]
    assert victim.task is None and victim.path.cells[0] == (1, 1)
    assert victim.path.cells[-1] in INSTANCE.endpoints
    apply(agents, list(by_agent.values()))


@pytest.mark.parametrize(
    "map_name, n_agents, rate, n_tasks",
    [
        ("toy_corridor.map", 3, 1, 30),
        ("warehouse_small.map", 30, 1, 150),
        ("narrow_corridor.map", 20, 5, 100),
    ],
)
def test_full_runs_complete_without_conflicts(map_name, n_agents, rate, n_tasks):
    grid = GridMap.load(MAPS / map_name)
    inst = make_instance(grid, n_agents, n_tasks, rate, seed=1)
    log = Simulator(inst, TokenPassingWithSwaps(), UnitCost(), max_timesteps=5000).run()
    assert log.completed


def test_swaps_shorten_service_time():
    grid = GridMap.load(MAPS / "warehouse_small.map")
    inst = make_instance(grid, 20, 150, 0.5, seed=0)
    mean = lambda log: sum(r.service_time for r in log.records) / len(log.records)  # noqa: E731
    tp = Simulator(inst, TokenPassing(), UnitCost()).run()
    tpts = Simulator(inst, TokenPassingWithSwaps(), UnitCost()).run()
    assert mean(tpts) < mean(tp)
