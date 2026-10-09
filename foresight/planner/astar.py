"""Space-time A* with a pluggable step cost.

Owner: member 2. This module is on the critical path: TP and all congestion
methods depend on it, so it should be finished first.
"""

from __future__ import annotations

from foresight.interfaces import Cell, CostModel, Path, Timestep
from foresight.sim.grid import GridMap


def space_time_astar(
    grid: GridMap,
    agent_id: int,
    start: Cell,
    goal: Cell,
    start_time: Timestep,
    cost_model: CostModel,
    is_blocked,
    max_time: int,
) -> Path | None:
    """Find a minimum-cost path from ``start`` at ``start_time`` to ``goal``.

    Args:
        is_blocked: ``is_blocked(u, v, t) -> bool``. True if the move from u
            at t to v at t + 1 collides with a path already in the token
            (vertex or swap conflict). These are hard constraints; congestion
            only enters through ``cost_model.cost``.
        max_time: give up after this many timesteps past ``start_time``.

    Uses the true distance to ``goal`` as the heuristic, which stays
    admissible because every step cost is >= 1. Returns ``None`` if no path
    exists within ``max_time``.

    Unit-test this on a static grid with a stub ``is_blocked``; it does not
    need the simulator.
    """
    raise NotImplementedError
