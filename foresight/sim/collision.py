"""Independent collision checker.

Owner: member 1.

Every run is checked after the fact, regardless of which planner produced
it. A non-empty result means a planner bug, never an acceptable outcome.
"""

from __future__ import annotations

from dataclasses import dataclass

from foresight.interfaces import Cell, Path, Timestep


@dataclass(frozen=True)
class Conflict:
    kind: str  # "vertex" or "swap"
    agents: tuple[int, int]
    time: Timestep
    cells: tuple[Cell, ...]


def find_conflicts(paths: list[Path]) -> list[Conflict]:
    """Return all vertex conflicts (two agents in one cell at the same time)
    and swap conflicts (two agents exchanging cells between t and t + 1)."""
    raise NotImplementedError
