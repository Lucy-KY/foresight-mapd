"""Lane-emergence metrics for single-lane corridors (results/summary/lanes.md).

Owner: member 3.

A corridor is one grid row between two columns. A *corridor move* is a
horizontal move inside it (waits and vertical moves into pockets are not
counted). Time is cut into windows; in each (corridor, window) the moves
going in the more common direction are the majority. The lane share

    L = sum max(E, W) / sum (E + W)

is 1 when every corridor is one-way in every window and 0.5 for balanced
two-way traffic.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from foresight.interfaces import Path

# narrow_corridor.map: the four interior single-lane aisles, columns 7-27,
# plus the side-aisle cells (6 and 28) they are entered from.
NARROW_CORRIDOR_ROWS = (4, 8, 12, 16)
NARROW_CORRIDOR_COLS = (6, 28)

# warehouse_small.map: four interior aisle bands of three rows each (endpoint
# row, aisle row, endpoint row), same columns. Row -> band index.
WAREHOUSE_BANDS = {r: k for k, rows in enumerate([(3, 4, 5), (7, 8, 9), (11, 12, 13), (15, 16, 17)]) for r in rows}
WAREHOUSE_AISLE_ROWS = (4, 8, 12, 16)
WAREHOUSE_COLS = (6, 28)


@dataclass(frozen=True)
class CorridorMove:
    row: int
    t: int  # departure time of the move u -> v
    east: bool


def corridor_moves(
    paths: list[Path],
    rows: tuple[int, ...] = NARROW_CORRIDOR_ROWS,
    cols: tuple[int, int] = NARROW_CORRIDOR_COLS,
) -> list[CorridorMove]:
    """Every horizontal move with both cells in one of ``rows`` and both
    columns in ``cols[0]..cols[1]`` (inclusive)."""
    lo, hi = cols
    wanted = set(rows)
    out = []
    for p in paths:
        for (r0, c0), (r1, c1), t in p.moves():
            if r0 == r1 and r0 in wanted and c0 != c1 and lo <= min(c0, c1) and max(c0, c1) <= hi:
                out.append(CorridorMove(r0, t, c1 > c0))
    return out


def window_counts(
    moves: list[CorridorMove], window: int, group: dict[int, int] | None = None
) -> dict[tuple[int, int], tuple[int, int]]:
    """(corridor, window index) -> (east moves, west moves). A corridor is a
    row, or ``group[row]`` when rows are grouped (e.g. into aisle bands)."""
    counts: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    for m in moves:
        corridor = group[m.row] if group is not None else m.row
        counts[(corridor, m.t // window)][0 if m.east else 1] += 1
    return {k: (e, w) for k, (e, w) in counts.items()}


def lane_share(moves: list[CorridorMove], window: int = 50, group: dict[int, int] | None = None) -> float:
    """Share of corridor moves in their (corridor, window)'s majority
    direction; nan if there are no corridor moves. ``group`` merges rows
    into one corridor (see ``window_counts``)."""
    counts = window_counts(moves, window, group).values()
    total = sum(e + w for e, w in counts)
    return sum(max(e, w) for e, w in counts) / total if total else float("nan")


def flip_rate(moves: list[CorridorMove], window: int = 50, min_moves: int = 5) -> float:
    """Among consecutive windows of the same corridor that both have at
    least ``min_moves`` moves and a strict majority, the share in which the
    majority direction changes; nan if there are no such pairs."""
    counts = window_counts(moves, window)
    flips = pairs = 0
    for (row, k), (e, w) in counts.items():
        nxt = counts.get((row, k + 1))
        if nxt is None or e + w < min_moves or sum(nxt) < min_moves or e == w or nxt[0] == nxt[1]:
            continue
        pairs += 1
        flips += (e > w) != (nxt[0] > nxt[1])
    return flips / pairs if pairs else float("nan")


def lane_share_series(moves: list[CorridorMove], window: int = 50) -> dict[int, tuple[int, int]]:
    """Window index -> (majority moves, all moves), summed over corridors,
    so L over time can be averaged across runs."""
    series: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for (_, k), (e, w) in window_counts(moves, window).items():
        series[k][0] += max(e, w)
        series[k][1] += e + w
    return {k: (a, b) for k, (a, b) in sorted(series.items())}
