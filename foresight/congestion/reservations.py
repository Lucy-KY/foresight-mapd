"""Reservation counts built from committed paths.

Owner: member 3.

This is the "foresight" in Foresight: because committed paths never
change, their reservations are an exact forecast of where agents will be.
Unit-test it with hand-written paths; it does not need the planner.
"""

from __future__ import annotations

from typing import Iterator

from foresight.interfaces import Cell, Path, Timestep

Edge = tuple[Cell, Cell]

_NONE: dict[Timestep, int] = {}  # shared empty lookup result; never mutated


class ReservationTable:
    """Incrementally maintained counts.

    - ``R[v][t]``: number of committed paths occupying cell v at time t
    - ``E[(u, v)][t]``: number of committed paths moving u -> v during [t, t + 1]

    Paths of other agents only: the agent being planned must not see its
    own (old) path as congestion. TP releases an agent's path from the
    token, and so from this table, before it replans that agent.

    Only the cells a path lists are counted. An agent parked at its last
    cell after ``end_time`` is a hard obstacle for the token, not
    congestion. A wait counts in ``R`` (the cell is occupied) but not in
    ``E`` (nothing moves). Zero counts are dropped, so the table only ever
    holds the paths currently committed.
    """

    def __init__(self) -> None:
        self._vertex: dict[Cell, dict[Timestep, int]] = {}
        self._edge: dict[Edge, dict[Timestep, int]] = {}
        self.n_paths = 0  # paths currently in the table

    def add_path(self, path: Path) -> None:
        for v, t in _occupancy(path):
            counts = self._vertex.setdefault(v, {})
            counts[t] = counts.get(t, 0) + 1
        for e, t in _moves(path):
            counts = self._edge.setdefault(e, {})
            counts[t] = counts.get(t, 0) + 1
        self.n_paths += 1

    def remove_path(self, path: Path) -> None:
        """Undo ``add_path(path)``.

        Raises ``ValueError`` and leaves the table unchanged if a count
        would go negative, which means the path was never added or was
        removed twice.
        """
        occupancy = list(_occupancy(path))
        moves = list(_moves(path))
        missing = [(v, t) for v, t in occupancy if not self._vertex.get(v, _NONE).get(t)]
        missing += [(e, t) for e, t in moves if not self._edge.get(e, _NONE).get(t)]
        if missing:
            raise ValueError(
                f"cannot remove path of agent {path.agent_id}: reservation {missing[0]} "
                "is not in the table (path never added, or removed twice)"
            )
        for v, t in occupancy:
            _decrement(self._vertex, v, t)
        for e, t in moves:
            _decrement(self._edge, e, t)
        self.n_paths -= 1

    def vertex_count(self, v: Cell, t: Timestep) -> int:
        return self._vertex.get(v, _NONE).get(t, 0)

    def edge_count(self, u: Cell, v: Cell, t: Timestep) -> int:
        return self._edge.get((u, v), _NONE).get(t, 0)

    def vertex_window(self, v: Cell, t_from: Timestep, t_to: Timestep) -> int:
        """Sum of ``vertex_count(v, t)`` for t in [t_from, t_to]."""
        return _window(self._vertex.get(v), t_from, t_to)

    def edge_window(self, u: Cell, v: Cell, t_from: Timestep, t_to: Timestep) -> int:
        """Sum of ``edge_count(u, v, t)`` for t in [t_from, t_to]."""
        return _window(self._edge.get((u, v)), t_from, t_to)


def _occupancy(path: Path) -> Iterator[tuple[Cell, Timestep]]:
    for k, v in enumerate(path.cells):
        yield v, path.start_time + k


def _moves(path: Path) -> Iterator[tuple[Edge, Timestep]]:
    for u, v, t in path.moves():
        if u != v:
            yield (u, v), t


def _decrement(table: dict, key, t: Timestep) -> None:
    counts = table[key]
    n = counts[t] - 1
    if n:
        counts[t] = n
    else:
        del counts[t]
        if not counts:
            del table[key]


def _window(counts: dict[Timestep, int] | None, t_from: Timestep, t_to: Timestep) -> int:
    if not counts or t_to < t_from:
        return 0
    # Walk whichever is shorter: the window, or the times this key is reserved.
    if t_to - t_from + 1 <= len(counts):
        return sum(counts.get(t, 0) for t in range(t_from, t_to + 1))
    return sum(n for t, n in counts.items() if t_from <= t <= t_to)
