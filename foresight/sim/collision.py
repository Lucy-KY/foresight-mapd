"""Independent collision checker.

Owner: member 1.

Every run is checked after the fact, regardless of which planner produced
it. A non-empty result means a planner bug, never an acceptable outcome.

The checker is meant for executed trajectories (one ``Path`` per agent,
covering the whole run), but works on any set of paths with ``Path``
semantics: an agent is checked from its ``start_time`` on and stays at its
last cell after ``end_time``, which is how TP parks agents at endpoints.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from foresight.interfaces import Cell, Path, Timestep
from foresight.sim.grid import GridMap


@dataclass(frozen=True)
class Conflict:
    kind: str  # "vertex" or "swap"
    agents: tuple[int, int]
    time: Timestep
    cells: tuple[Cell, ...]

    def __str__(self) -> str:
        a, b = self.agents
        if self.kind == "vertex":
            return f"vertex conflict: agents {a} and {b} both at {self.cells[0]} at t={self.time}"
        u, v = self.cells
        return f"swap conflict: agents {a} and {b} swap {u} <-> {v} between t={self.time} and t={self.time + 1}"


@dataclass(frozen=True)
class InvalidMove:
    agent: int
    time: Timestep
    u: Cell
    v: Cell
    reason: str

    def __str__(self) -> str:
        return f"invalid move: agent {self.agent} {self.u} -> {self.v} at t={self.time} ({self.reason})"


def find_conflicts(paths: list[Path]) -> list[Conflict]:
    """Return all vertex conflicts (two agents in one cell at the same time)
    and swap conflicts (two agents exchanging cells between t and t + 1).

    These are the two collision types of Ma et al. (2017). Following an
    agent into the cell it just left is allowed. Conflicts are sorted by
    time; three agents in one cell give three pairwise conflicts.
    """
    _check_unique_agents(paths)
    if not paths:
        return []
    t_first = min(p.start_time for p in paths)
    t_last = max(p.end_time for p in paths)

    conflicts = []
    for t in range(t_first, t_last + 1):
        active = [p for p in paths if p.start_time <= t]

        occupants: dict[Cell, list[int]] = defaultdict(list)
        for p in active:
            occupants[p.at(t)].append(p.agent_id)
        for cell, agents in occupants.items():
            for a, b in combinations(sorted(agents), 2):
                conflicts.append(Conflict("vertex", (a, b), t, (cell,)))

        if t == t_last:
            continue
        moves: dict[tuple[Cell, Cell], int] = {}
        for p in active:
            u, v = p.at(t), p.at(t + 1)
            if u != v:
                moves[(u, v)] = p.agent_id
        for (u, v), a in moves.items():
            b = moves.get((v, u))
            if b is not None and a < b:
                conflicts.append(Conflict("swap", (a, b), t, (u, v)))
    return conflicts


def find_invalid_moves(grid: GridMap, paths: list[Path]) -> list[InvalidMove]:
    """Return every step that is not a wait or a move to a passable
    4-neighbor, including starting in a blocked cell."""
    invalid = []
    for p in paths:
        if not grid.passable(p.cells[0]):
            invalid.append(
                InvalidMove(p.agent_id, p.start_time, p.cells[0], p.cells[0], "starts in a blocked cell")
            )
        for u, v, t in p.moves():
            if u == v:
                continue
            if not grid.passable(v):
                invalid.append(InvalidMove(p.agent_id, t, u, v, "moves into a blocked cell"))
            elif abs(u[0] - v[0]) + abs(u[1] - v[1]) != 1:
                invalid.append(InvalidMove(p.agent_id, t, u, v, "not a 4-neighbor move"))
    return invalid


def assert_valid(paths: list[Path], grid: GridMap | None = None, max_shown: int = 10) -> None:
    """Raise ``AssertionError`` listing the problems if any path is invalid
    or any two paths collide. Use this at the end of every simulation run."""
    problems: list[object] = []
    if grid is not None:
        problems += find_invalid_moves(grid, paths)
    problems += find_conflicts(paths)
    if problems:
        shown = "\n  ".join(str(x) for x in problems[:max_shown])
        more = f"\n  ... and {len(problems) - max_shown} more" if len(problems) > max_shown else ""
        raise AssertionError(f"{len(problems)} problem(s):\n  {shown}{more}")


def _check_unique_agents(paths: list[Path]) -> None:
    seen = set()
    for p in paths:
        if p.agent_id in seen:
            raise ValueError(f"agent {p.agent_id} has more than one path; pass one trajectory per agent")
        seen.add(p.agent_id)
