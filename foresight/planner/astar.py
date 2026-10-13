"""Space-time A* with a pluggable step cost.

Owner: member 2. This module is on the critical path: TP and all congestion
methods depend on it, so it should be finished first.
"""

from __future__ import annotations

import heapq
from collections import deque
from itertools import count
from typing import Callable

from foresight.interfaces import Cell, CostModel, Path, Timestep
from foresight.sim.grid import GridMap

IsBlocked = Callable[[Cell, Cell, Timestep], bool]
CanStay = Callable[[Cell, Timestep], bool]


def bfs_distances(grid: GridMap, goal: Cell) -> dict[Cell, int]:
    """Shortest 4-connected distance from every reachable cell to ``goal``,
    ignoring other agents."""
    dist = {goal: 0}
    frontier = deque([goal])
    while frontier:
        u = frontier.popleft()
        for v in grid.neighbors(u):
            if v not in dist:
                dist[v] = dist[u] + 1
                frontier.append(v)
    return dist


class DistanceTable:
    """True distances to goal cells, computed by one BFS per goal and cached.

    Ma et al. (2017) precompute the distances to every endpoint; call
    ``precompute(instance.endpoints)`` to do the same, or let goals be
    filled in lazily on first use.
    """

    def __init__(self, grid: GridMap) -> None:
        self.grid = grid
        self._tables: dict[Cell, dict[Cell, int]] = {}

    def precompute(self, goals: list[Cell]) -> None:
        for g in goals:
            self.to(g)

    def to(self, goal: Cell) -> dict[Cell, int]:
        table = self._tables.get(goal)
        if table is None:
            table = self._tables[goal] = bfs_distances(self.grid, goal)
        return table

    def __call__(self, a: Cell, b: Cell) -> int | None:
        """Distance from ``a`` to ``b``, or ``None`` if unreachable."""
        return self.to(b).get(a)


def space_time_astar(
    grid: GridMap,
    agent_id: int,
    start: Cell,
    goal: Cell,
    start_time: Timestep,
    cost_model: CostModel,
    is_blocked: IsBlocked,
    max_time: int,
    can_stay: CanStay | None = None,
    distances: dict[Cell, int] | None = None,
) -> Path | None:
    """Find a minimum-cost path from ``start`` at ``start_time`` to ``goal``.

    Args:
        is_blocked: ``is_blocked(u, v, t) -> bool``. True if the move from u
            at t to v at t + 1 collides with a path already in the token
            (vertex or swap conflict). These are hard constraints; congestion
            only enters through ``cost_model.cost``.
        max_time: give up after this many timesteps past ``start_time``.
        can_stay: ``can_stay(goal, t) -> bool``. If given, the path may only
            end at ``goal`` at a time t from which the agent can stay there
            forever, i.e. no other committed path enters ``goal`` at or
            after t. Needed for the last leg of a TP path, which parks at an
            endpoint; leave it out for an intermediate goal such as a pickup.
        distances: true distances to ``goal`` (e.g. ``DistanceTable.to``);
            computed with a BFS if not given.

    Uses the true distance to ``goal`` as the heuristic, which stays
    admissible (and consistent) because every step cost is >= 1. Ties on f
    are broken by smaller h, then by insertion order, so the result is
    deterministic. Returns ``None`` if no path exists within ``max_time``.
    """
    if distances is None:
        distances = bfs_distances(grid, goal)
    h0 = distances.get(start)
    if h0 is None:
        return None
    deadline = start_time + max_time

    neighbors: dict[Cell, list[Cell]] = {}
    tie = count()
    root = (start, start_time)
    g_best: dict[tuple[Cell, Timestep], float] = {root: 0.0}
    parent: dict[tuple[Cell, Timestep], tuple[Cell, Timestep] | None] = {root: None}
    open_heap = [(float(h0), h0, next(tie), 0.0, start, start_time)]
    closed: set[tuple[Cell, Timestep]] = set()

    while open_heap:
        _, _, _, g, u, t = heapq.heappop(open_heap)
        state = (u, t)
        if state in closed:
            continue
        closed.add(state)

        if u == goal and (can_stay is None or can_stay(goal, t)):
            cells = []
            node: tuple[Cell, Timestep] | None = state
            while node is not None:
                cells.append(node[0])
                node = parent[node]
            return Path(agent_id, start_time, tuple(reversed(cells)))

        if t >= deadline:
            continue
        succ = neighbors.get(u)
        if succ is None:
            succ = neighbors[u] = [u, *grid.neighbors(u)]
        for v in succ:
            nxt = (v, t + 1)
            if nxt in closed:
                continue
            h = distances.get(v)
            if h is None or is_blocked(u, v, t):
                continue
            g2 = g + cost_model.cost(u, v, t)
            if g2 < g_best.get(nxt, float("inf")):
                g_best[nxt] = g2
                parent[nxt] = state
                heapq.heappush(open_heap, (g2 + h, h, next(tie), g2, v, t + 1))
    return None
