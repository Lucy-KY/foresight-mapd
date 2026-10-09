"""MAPD instances: a map, agent start locations and a task stream.

Owner: member 1.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from foresight.interfaces import Cell, Task
from foresight.sim.grid import GridMap
from foresight.sim.tasks import generate_task_stream


@dataclass(frozen=True)
class MapdInstance:
    grid: GridMap
    initial_locations: tuple[Cell, ...]
    tasks: tuple[Task, ...]

    @property
    def n_agents(self) -> int:
        return len(self.initial_locations)

    @property
    def task_endpoints(self) -> list[Cell]:
        return self.grid.task_endpoints

    @property
    def non_task_endpoints(self) -> list[Cell]:
        """As in Ma et al. (2017), the start locations are the only non-task
        endpoints; unused ``r`` cells are ordinary free cells."""
        return list(self.initial_locations)

    @property
    def endpoints(self) -> list[Cell]:
        return self.task_endpoints + self.non_task_endpoints


def sample_initial_locations(grid: GridMap, n_agents: int, seed: int) -> list[Cell]:
    """Pick ``n_agents`` distinct start cells among the map's ``r`` cells.

    The candidate cells are shuffled once per seed and the first ``n_agents``
    are taken, so for a fixed seed the 10-agent start set is a subset of the
    20-agent one, and so on.
    """
    homes = grid.homes
    if n_agents > len(homes):
        raise ValueError(f"{n_agents} agents but only {len(homes)} start cells")
    order = list(homes)
    random.Random(seed).shuffle(order)
    return order[:n_agents]


def make_instance(
    grid: GridMap, n_agents: int, n_tasks: int, arrival_rate: float, seed: int
) -> MapdInstance:
    instance = MapdInstance(
        grid=grid,
        initial_locations=tuple(sample_initial_locations(grid, n_agents, seed)),
        tasks=tuple(generate_task_stream(grid, n_tasks, arrival_rate, seed)),
    )
    problems = well_formedness_problems(grid, instance.endpoints, n_agents)
    if problems:
        raise ValueError("instance is not well-formed: " + "; ".join(problems))
    return instance


def well_formedness_problems(
    grid: GridMap, endpoints: list[Cell], n_agents: int
) -> list[str]:
    """Check Definition 1 of Ma et al. (2017) and return what is violated.

    The number of non-task endpoints must be at least the number of agents
    (the caller passes start locations as non-task endpoints, so this holds
    by construction), and every pair of endpoints must be connected by a
    path that traverses no other endpoint. The finite-task condition holds
    because task streams are finite.
    """
    problems = []
    endpoint_set = set(endpoints)
    non_task = endpoint_set - set(grid.task_endpoints)
    if len(non_task) < n_agents:
        problems.append(f"{len(non_task)} non-task endpoints for {n_agents} agents")

    # Label connected components of the free cells that are not endpoints.
    component: dict[Cell, int] = {}
    label = -1
    for r in range(grid.height):
        for c in range(grid.width):
            start = (r, c)
            if start in component or start in endpoint_set or not grid.passable(start):
                continue
            label += 1
            stack = [start]
            component[start] = label
            while stack:
                u = stack.pop()
                for v in grid.neighbors(u):
                    if v not in component and v not in endpoint_set:
                        component[v] = label
                        stack.append(v)

    touches = {
        e: {component[n] for n in grid.neighbors(e) if n in component} for e in endpoints
    }
    ordered = sorted(endpoint_set)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            adjacent = b in grid.neighbors(a)
            if not adjacent and not (touches[a] & touches[b]):
                problems.append(f"no endpoint-free path between {a} and {b}")
                if len(problems) >= 5:
                    return problems
    return problems
