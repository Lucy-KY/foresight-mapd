"""M1: highways (Cohen, Uras & Koenig, 2015), adapted to lifelong MAPD / TP.

Owner: member 2.

Cohen et al. use highways with ECBS in one-shot MAPF; plugging them into
TP's planner is our adaptation and should be described as such.

What Cohen et al. do: a highway is a set of directed edges, and the
low-level search uses the inflated heuristic ``h_hwy(s)``, the cheapest
path to the goal when every edge *not* on the highway costs w and highway
edges cost 1. Edge costs themselves are unchanged; the search behaves like
weighted A*, with solutions at most w times optimal.

What we do: keep the true-distance heuristic and put the penalty on the
step cost instead, charging ``w_h`` only for moving *against* a highway
edge. This keeps the one-difference-only design (every method differs only
in its step cost) and is the "penalize moves against highway edges"
variant that Cohen et al. list as future work (similar to direction maps,
Jansen & Sturtevant 2008).
"""

from __future__ import annotations

import json
from pathlib import Path as FsPath

from foresight.costs.base import BaseCostModel
from foresight.interfaces import Cell, Timestep
from foresight.sim.grid import GridMap

COMPASS = {"N": (-1, 0), "S": (1, 0), "E": (0, 1), "W": (0, -1)}


def load_directions(path: str | FsPath, grid: GridMap) -> dict[Cell, set[tuple[int, int]]]:
    """Read a highway file and expand it to per-cell directions.

    The file is JSON with whole rows and columns as one-way lanes::

        {"rows": {"0": "W", "4": "E"}, "cols": {"0": "S", "34": "N"}}

    Every passable cell of a listed row or column gets that direction; a
    cell where a row lane crosses a column lane gets both. Other keys (such
    as ``"description"``) are ignored.
    """
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    directions: dict[Cell, set[tuple[int, int]]] = {}
    for r, d in spec.get("rows", {}).items():
        for c in range(grid.width):
            if grid.passable((int(r), c)):
                directions.setdefault((int(r), c), set()).add(COMPASS[d])
    for c, d in spec.get("cols", {}).items():
        for r in range(grid.height):
            if grid.passable((r, int(c))):
                directions.setdefault((r, int(c)), set()).add(COMPASS[d])
    return directions


class HighwayCost(BaseCostModel):
    """Moves along the designed highway direction cost 1; moves against it
    cost ``w_h`` (> 1). Moves on cells without a direction, and waits, cost 1.

    A cell with direction D makes the edge ``cell -> cell + D`` a highway
    edge. Moving u -> v is against the highway if v -> u is a highway edge
    and u -> v is not; entering or crossing a lane sideways costs 1.

    Args:
        directions: maps a cell to its allowed move directions, e.g.
            ``{(3, 5): {(0, 1)}}`` for "row 3 flows east". Built offline per
            map (e.g. alternating one-way aisles); see ``load_directions``.
        w_h: penalty for moving against the highway. Swept in tuning.
    """

    name = "highway"

    def __init__(self, directions: dict[Cell, set[tuple[int, int]]], w_h: float) -> None:
        if w_h < 1:
            raise ValueError("w_h must be >= 1")
        self.directions = directions
        self.w_h = w_h

    @classmethod
    def from_file(cls, path: str | FsPath, grid: GridMap, w_h: float) -> HighwayCost:
        """Build from a highway file such as ``maps/warehouse_small.highway.json``."""
        return cls(load_directions(path, grid), w_h)

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        if u == v:
            return 1.0
        d = (v[0] - u[0], v[1] - u[1])
        back = (-d[0], -d[1])
        if back in self.directions.get(v, ()) and d not in self.directions.get(u, ()):
            return self.w_h
        return 1.0
