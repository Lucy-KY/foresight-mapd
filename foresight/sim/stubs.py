"""Stand-in planners for testing the simulator before TP exists.

Owner: member 1. Not for experiments.
"""

from __future__ import annotations

from collections import deque

from foresight.interfaces import (
    AgentState,
    AgentStatus,
    Cell,
    CostModel,
    Decision,
    Path,
    Task,
    Timestep,
)
from foresight.sim.grid import GridMap
from foresight.sim.instance import MapdInstance


class IdlePlanner:
    """Never assigns anything; every agent stays where it starts."""

    def reset(self, instance: MapdInstance, cost_model: CostModel) -> None:
        pass

    def step(self, t: Timestep, agents: list[AgentState], open_tasks: list[Task]) -> list[Decision]:
        return []


def bfs(grid: GridMap, start: Cell, goal: Cell, blocked: set[Cell]) -> list[Cell] | None:
    """Shortest 4-connected path from ``start`` to ``goal`` (both included)
    avoiding ``blocked``; ``None`` if there is none."""
    if goal in blocked:
        return None
    came_from: dict[Cell, Cell | None] = {start: None}
    frontier = deque([start])
    while frontier:
        u = frontier.popleft()
        if u == goal:
            cells = [u]
            while came_from[cells[-1]] is not None:
                cells.append(came_from[cells[-1]])
            return cells[::-1]
        for v in grid.neighbors(u):
            if v not in came_from and v not in blocked:
                came_from[v] = u
                frontier.append(v)
    return None


class OneAtATimePlanner:
    """Lets exactly one agent move at a time, so paths can never collide.

    When every agent is idle and parked, it gives the first open task it can
    route to the nearest agent that can reach it, treating the other parked
    agents as walls. If no task can be routed because a parked agent sits on
    a task endpoint, it moves that agent to a free start cell. Hopelessly
    slow by design: it only exercises the simulator.
    """

    def reset(self, instance: MapdInstance, cost_model: CostModel) -> None:
        self.instance = instance
        self.grid = instance.grid

    def step(self, t: Timestep, agents: list[AgentState], open_tasks: list[Task]) -> list[Decision]:
        if any(a.status is not AgentStatus.IDLE or not a.at_path_end(t) for a in agents):
            return []
        occupied = {a.location for a in agents}

        for task in open_tasks:
            by_distance = sorted(agents, key=lambda a: _manhattan(a.location, task.pickup))
            for a in by_distance:
                blocked = occupied - {a.location}
                to_pickup = bfs(self.grid, a.location, task.pickup, blocked)
                to_delivery = bfs(self.grid, task.pickup, task.delivery, blocked)
                if to_pickup and to_delivery:
                    cells = tuple(to_pickup + to_delivery[1:])
                    pickup_time = t + len(to_pickup) - 1
                    return [Decision(a.agent_id, Path(a.agent_id, t, cells), task, pickup_time)]

        task_cells = {c for task in open_tasks for c in (task.pickup, task.delivery)}
        free = [c for c in self.instance.non_task_endpoints if c not in occupied]
        for a in agents:
            if a.location not in task_cells:
                continue
            for target in free:
                route = bfs(self.grid, a.location, target, occupied - {a.location})
                if route:
                    return [Decision(a.agent_id, Path(a.agent_id, t, tuple(route)))]
        return []


def _manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
