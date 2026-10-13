"""M2: history-based heatmap. A control baseline designed by us.

Owner: member 2.

It isolates the effect of looking forward: it is dynamic like Foresight,
but it only knows where agents have been, not where they will be.
"""

from __future__ import annotations

from foresight.costs.base import BaseCostModel
from foresight.interfaces import Cell, Timestep

_RESCALE_BELOW = 1e-100


class HeatmapCost(BaseCostModel):
    """``cost = 1 + lam * H(v) / max(H)``, where ``H(v)`` is a decayed count
    of past visits to v, updated in ``on_timestep`` (``H *= eta`` then +1 for
    every occupied cell). Waits cost 1.

    Decay is lazy: ``H(v) = raw[v] * scale`` and only ``scale`` shrinks each
    step, so an update costs O(agents) instead of O(cells). ``H(v) / max(H)``
    does not depend on ``scale`` at all. The cost only uses the past, so it
    ignores ``t`` and committed paths.
    """

    name = "heatmap"

    def __init__(self, lam: float, eta: float = 0.99) -> None:
        if lam < 0:
            raise ValueError("lam must be >= 0")
        if not 0 < eta <= 1:
            raise ValueError("eta must be in (0, 1]")
        self.lam = lam
        self.eta = eta
        self._raw: dict[Cell, float] = {}
        self._raw_max = 0.0
        self._scale = 1.0

    def heat(self, v: Cell) -> float:
        """``H(v)``, the decayed visit count."""
        return self._raw.get(v, 0.0) * self._scale

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        if u == v or self.lam == 0 or self._raw_max == 0:
            return 1.0
        return 1.0 + self.lam * self._raw.get(v, 0.0) / self._raw_max

    def on_timestep(self, t: Timestep, positions: dict[int, Cell]) -> None:
        self._scale *= self.eta
        if self._scale < _RESCALE_BELOW:
            self._raw = {v: h * self._scale for v, h in self._raw.items()}
            self._raw_max *= self._scale
            self._scale = 1.0
        bump = 1.0 / self._scale
        for v in positions.values():
            h = self._raw.get(v, 0.0) + bump
            self._raw[v] = h
            if h > self._raw_max:
                self._raw_max = h
