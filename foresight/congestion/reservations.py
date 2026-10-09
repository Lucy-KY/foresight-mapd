"""Reservation counts built from committed paths.

Owner: member 3.

This is the "foresight" in Foresight: because committed paths never
change, their reservations are an exact forecast of where agents will be.
Unit-test it with hand-written paths; it does not need the planner.
"""

from __future__ import annotations

from foresight.interfaces import Cell, Path, Timestep


class ReservationTable:
    """Incrementally maintained counts.

    - ``R[v][t]``: number of committed paths occupying cell v at time t
    - ``E[(u, v)][t]``: number of committed paths moving u -> v during [t, t + 1]

    Paths of other agents only: the agent being planned must not see its
    own (old) path as congestion.
    """

    def add_path(self, path: Path) -> None:
        raise NotImplementedError

    def remove_path(self, path: Path) -> None:
        raise NotImplementedError

    def vertex_count(self, v: Cell, t: Timestep) -> int:
        raise NotImplementedError

    def edge_count(self, u: Cell, v: Cell, t: Timestep) -> int:
        raise NotImplementedError

    def vertex_window(self, v: Cell, t_from: Timestep, t_to: Timestep) -> int:
        """Sum of ``vertex_count(v, t)`` for t in [t_from, t_to]."""
        raise NotImplementedError

    def edge_window(self, u: Cell, v: Cell, t_from: Timestep, t_to: Timestep) -> int:
        """Sum of ``edge_count(u, v, t)`` for t in [t_from, t_to]."""
        raise NotImplementedError
