"""Shared interfaces for all modules.

These types were agreed on by the whole team in step 0. Every module codes
against them, which is what lets the simulator, planner and congestion work
proceed in parallel. Change this file only after the team agrees.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Protocol, runtime_checkable

Cell = tuple[int, int]
"""A grid cell as (row, col)."""

Timestep = int


@dataclass(frozen=True)
class Path:
    """A space-time path: ``cells[k]`` is occupied at time ``start_time + k``.

    Waiting is represented by repeating a cell. After ``end_time`` the agent
    is assumed to stay at its last cell (TP parks agents at their endpoint).
    """

    agent_id: int
    start_time: Timestep
    cells: tuple[Cell, ...]

    @property
    def end_time(self) -> Timestep:
        return self.start_time + len(self.cells) - 1

    def at(self, t: Timestep) -> Cell:
        """Cell occupied at time ``t`` (clamped to the first/last cell)."""
        k = t - self.start_time
        if k <= 0:
            return self.cells[0]
        if k >= len(self.cells):
            return self.cells[-1]
        return self.cells[k]

    def moves(self) -> Iterator[tuple[Cell, Cell, Timestep]]:
        """Yield ``(u, v, t)``: the agent moves from u at t to v at t + 1."""
        for k in range(len(self.cells) - 1):
            yield self.cells[k], self.cells[k + 1], self.start_time + k


@dataclass(frozen=True)
class Task:
    task_id: int
    pickup: Cell
    delivery: Cell
    release_time: Timestep


class AgentStatus(Enum):
    IDLE = "idle"
    TO_PICKUP = "to_pickup"
    TO_DELIVERY = "to_delivery"


@runtime_checkable
class CostModel(Protocol):
    """Step cost used by the space-time A* planner.

    This is the only thing that differs between methods M0-M5: every method
    runs the same token-passing loop and the same planner, and plugs in its
    own ``cost``. Paths are fixed once committed; methods never replan.
    """

    name: str

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        """Cost of moving from ``u`` at time ``t`` to ``v`` at ``t + 1``.

        ``u == v`` is a wait action. Must return a finite value >= 1 so that
        the true-distance heuristic stays admissible.
        """
        ...

    def on_path_committed(self, path: Path) -> None:
        """Called after a path is written into the token."""
        ...

    def on_path_released(self, path: Path) -> None:
        """Called when a path is removed from the token."""
        ...

    def on_timestep(self, t: Timestep, positions: dict[int, Cell]) -> None:
        """Called once per simulated timestep with every agent's position."""
        ...
