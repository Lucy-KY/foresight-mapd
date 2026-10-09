"""M1: highways (Cohen, Uras & Koenig, 2015), adapted to lifelong MAPD / TP.

Owner: member 2.

Cohen et al. use highways with ECBS in one-shot MAPF; plugging them into
TP's planner is our adaptation and should be described as such.
"""

from __future__ import annotations

from foresight.costs.base import BaseCostModel
from foresight.interfaces import Cell, Timestep


class HighwayCost(BaseCostModel):
    """Moves along the designed highway direction cost 1; moves against it
    cost ``w_h`` (> 1). Moves on cells without a direction, and waits, cost 1.

    Args:
        directions: maps a cell to its allowed move directions, e.g.
            ``{(3, 5): {(0, 1)}}`` for "row 3 flows east". Built offline per
            map (e.g. alternating one-way aisles).
        w_h: penalty for moving against the highway. Swept in tuning.
    """

    name = "highway"

    def __init__(self, directions: dict[Cell, set[tuple[int, int]]], w_h: float) -> None:
        if w_h < 1:
            raise ValueError("w_h must be >= 1")
        self.directions = directions
        self.w_h = w_h

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        raise NotImplementedError
