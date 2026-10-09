"""4-connected grid maps.

Map file format (one character per cell, one row per line):

    .  free cell
    @  obstacle
    e  task endpoint (pickup / delivery locations)
    r  non-task endpoint (agent home / parking location)

Lines starting with ``#`` are comments.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path as FsPath

from foresight.interfaces import Cell

FREE, OBSTACLE, TASK_ENDPOINT, HOME = ".", "@", "e", "r"
_VALID = {FREE, OBSTACLE, TASK_ENDPOINT, HOME}


@dataclass
class GridMap:
    rows: list[str]

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("map is empty")
        width = len(self.rows[0])
        for r, line in enumerate(self.rows):
            if len(line) != width:
                raise ValueError(f"row {r} has length {len(line)}, expected {width}")
            bad = set(line) - _VALID
            if bad:
                raise ValueError(f"row {r} has unknown characters {sorted(bad)}")

    @classmethod
    def from_lines(cls, lines: list[str]) -> GridMap:
        rows = [ln.rstrip("\n") for ln in lines]
        rows = [ln for ln in rows if ln and not ln.startswith("#")]
        return cls(rows)

    @classmethod
    def load(cls, path: str | FsPath) -> GridMap:
        with open(path, encoding="utf-8") as f:
            return cls.from_lines(f.readlines())

    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int:
        return len(self.rows[0])

    def in_bounds(self, c: Cell) -> bool:
        r, col = c
        return 0 <= r < self.height and 0 <= col < self.width

    def passable(self, c: Cell) -> bool:
        return self.in_bounds(c) and self.rows[c[0]][c[1]] != OBSTACLE

    def neighbors(self, c: Cell) -> list[Cell]:
        """Passable 4-neighbors of ``c`` (not including ``c`` itself)."""
        r, col = c
        cand = [(r - 1, col), (r + 1, col), (r, col - 1), (r, col + 1)]
        return [n for n in cand if self.passable(n)]

    def cells_of(self, kind: str) -> list[Cell]:
        return [
            (r, c)
            for r, line in enumerate(self.rows)
            for c, ch in enumerate(line)
            if ch == kind
        ]

    @property
    def task_endpoints(self) -> list[Cell]:
        return self.cells_of(TASK_ENDPOINT)

    @property
    def homes(self) -> list[Cell]:
        return self.cells_of(HOME)
