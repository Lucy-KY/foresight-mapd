"""M2: history-based heatmap. A control baseline designed by us.

Owner: member 2.

It isolates the effect of looking forward: it is dynamic like Foresight,
but it only knows where agents have been, not where they will be.
"""

from __future__ import annotations

from foresight.costs.base import BaseCostModel
from foresight.interfaces import Cell, Timestep


class HeatmapCost(BaseCostModel):
    """``cost = 1 + lam * H(v) / max(H)``, where ``H(v)`` is a decayed count
    of past visits to v, updated in ``on_timestep`` (``H *= eta`` then +1 for
    every occupied cell). Waits cost 1.
    """

    name = "heatmap"

    def __init__(self, lam: float, eta: float = 0.99) -> None:
        self.lam = lam
        self.eta = eta

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        raise NotImplementedError

    def on_timestep(self, t: Timestep, positions: dict[int, Cell]) -> None:
        raise NotImplementedError
