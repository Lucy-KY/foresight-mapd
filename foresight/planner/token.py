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
    """

    def __init__(self, cost_model: CostModel) -> None:
        self.cost_model = cost_model
        self.paths: dict[int, Path] = {}

    def commit(self, path: Path) -> None:
        old = self.paths.get(path.agent_id)
        if old is not None:
            self.cost_model.on_path_released(old)
        self.paths[path.agent_id] = path
        self.cost_model.on_path_committed(path)

    def release(self, agent_id: int) -> None:
        old = self.paths.pop(agent_id, None)
        if old is not None:
            self.cost_model.on_path_released(old)

    def is_blocked(self, agent_id: int, u: Cell, v: Cell, t: Timestep) -> bool:
        """True if moving u -> v during [t, t + 1] conflicts with another
        agent's committed path. Passed to ``space_time_astar``."""
        raise NotImplementedError
