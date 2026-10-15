"""The shared token: every agent's committed path.

Owner: member 2.
"""

from __future__ import annotations

from foresight.interfaces import Cell, CostModel, Path, Timestep


class Token:
    """Holds the committed path of each agent.

    Paths are fixed once committed (sequential planning, no replanning).
    Every commit and release is forwarded to the cost model so congestion
    methods can keep their reservation tables up to date.

    Collision queries are answered from two indexes kept in sync with the
    paths: ``(cell, t) -> agent`` for every timestep a path covers, and
    ``cell -> agent`` for the cell each agent parks at after its path ends.
    """

    def __init__(self, cost_model: CostModel) -> None:
        self.cost_model = cost_model
        self.paths: dict[int, Path] = {}
        self._occupant: dict[tuple[Cell, Timestep], int] = {}
        self._parked: dict[Cell, int] = {}
        self._last_visit: dict[Cell, dict[int, Timestep]] = {}

    def commit(self, path: Path) -> None:
        old = self.paths.get(path.agent_id)
        if old is not None:
            self._unindex(old)
            self.cost_model.on_path_released(old)
        self._index(path)
        self.paths[path.agent_id] = path
        self.cost_model.on_path_committed(path)

    def release(self, agent_id: int) -> None:
        old = self.paths.pop(agent_id, None)
        if old is not None:
            self._unindex(old)
            self.cost_model.on_path_released(old)

    def occupant(self, cell: Cell, t: Timestep) -> int | None:
        """The agent whose committed path is at ``cell`` at time ``t``."""
        a = self._occupant.get((cell, t))
        if a is not None:
            return a
        a = self._parked.get(cell)
        if a is not None and self.paths[a].end_time <= t:
            return a
        return None

    def is_blocked(self, agent_id: int, u: Cell, v: Cell, t: Timestep) -> bool:
        """True if moving u -> v during [t, t + 1] conflicts with another
        agent's committed path. Passed to ``space_time_astar``."""
        b = self.occupant(v, t + 1)
        if b is not None and b != agent_id:
            return True  # vertex conflict
        if u == v:
            return False
        b = self.occupant(v, t)
        return b is not None and b != agent_id and self.occupant(u, t + 1) == b  # swap

    def can_stay(self, agent_id: int, cell: Cell, t: Timestep) -> bool:
        """True if no other agent's committed path is at ``cell`` at any time
        >= ``t``, so ``agent_id`` may park there from ``t`` on."""
        a = self._parked.get(cell)
        if a is not None and a != agent_id:
            return False
        visits = self._last_visit.get(cell)
        if visits:
            return all(last < t for b, last in visits.items() if b != agent_id)
        return True

    def path_ends(self, exclude: int | None = None) -> set[Cell]:
        """Cells where agents' committed paths end (they park there)."""
        return {c for c, a in self._parked.items() if a != exclude}

    def end_owners(self) -> dict[Cell, int]:
        """``cell -> agent`` for the cell each agent's committed path ends in."""
        return dict(self._parked)

    def _index(self, path: Path) -> None:
        a = path.agent_id
        for k, cell in enumerate(path.cells):
            t = path.start_time + k
            other = self.occupant(cell, t)
            if other is not None and other != a:
                raise ValueError(f"path of agent {a} collides with agent {other} at {cell}, t={t}")
            self._occupant[(cell, t)] = a
            visits = self._last_visit.setdefault(cell, {})
            visits[a] = max(visits.get(a, t), t)
        end = path.cells[-1]
        if not self.can_stay(a, end, path.end_time):
            raise ValueError(f"agent {a} parks at {end} from t={path.end_time}, but another path uses it later")
        self._parked[end] = a

    def _unindex(self, path: Path) -> None:
        a = path.agent_id
        for k, cell in enumerate(path.cells):
            t = path.start_time + k
            if self._occupant.get((cell, t)) == a:
                del self._occupant[(cell, t)]
            visits = self._last_visit.get(cell)
            if visits is not None:
                visits.pop(a, None)
                if not visits:
                    del self._last_visit[cell]
        if self._parked.get(path.cells[-1]) == a:
            del self._parked[path.cells[-1]]
