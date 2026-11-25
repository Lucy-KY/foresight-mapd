"""Lane-emergence metrics (foresight/lanes.py)."""

import math

from foresight.interfaces import Path
from foresight.lanes import corridor_moves, flip_rate, lane_share, lane_share_series


def _east(agent, row, c0, c1, start=0):
    return Path(agent, start, tuple((row, c) for c in range(c0, c1 + 1)))


def _west(agent, row, c0, c1, start=0):
    return Path(agent, start, tuple((row, c) for c in range(c0, c1 - 1, -1)))


def test_only_horizontal_moves_inside_the_corridor_count():
    path = Path(0, 0, ((3, 7), (4, 7), (4, 7), (4, 8), (4, 9), (5, 9), (4, 9), (4, 28), (4, 29)))
    # (3,7)->(4,7) vertical; wait; two east moves; pocket in/out vertical;
    # (4,9)->(4,28) is a (fake) jump inside cols 6-28 -> counts; (4,28)->(4,29) leaves -> not counted
    moves = corridor_moves([path])
    assert [(m.t, m.east) for m in moves] == [(2, True), (3, True), (6, True)]


def test_rows_outside_the_aisles_are_ignored():
    assert corridor_moves([_east(0, 0, 7, 12), _east(1, 5, 7, 12)]) == []


def test_one_way_traffic_scores_one_and_balanced_scores_half():
    one_way = corridor_moves([_east(0, 4, 7, 17), _east(1, 4, 8, 18)])
    assert lane_share(one_way) == 1.0
    balanced = corridor_moves([_east(0, 4, 7, 17), _west(1, 4, 27, 17)])
    assert lane_share(balanced) == 0.5


def test_majority_is_taken_per_window_and_per_corridor():
    # Window 0: row 4 east x10; window 1: row 4 west x10 -> both one-way.
    moves = corridor_moves([_east(0, 4, 7, 17, start=0), _west(1, 4, 27, 17, start=50)])
    assert lane_share(moves, window=50) == 1.0
    assert lane_share(moves, window=100) == 0.5
    assert flip_rate(moves, window=50) == 1.0


def test_flip_rate_zero_when_direction_persists_and_nan_without_pairs():
    moves = corridor_moves([_east(0, 4, 7, 27, start=40)])  # moves at t = 40..59
    assert flip_rate(moves, window=10) == 0.0
    assert math.isnan(flip_rate([], window=10))
    assert math.isnan(lane_share([]))


def test_series_sums_over_corridors():
    moves = corridor_moves([_east(0, 4, 7, 9), _west(1, 8, 27, 25), _west(2, 8, 26, 25)])
    assert lane_share_series(moves, window=50) == {0: (5, 5)}


def test_band_grouping_and_segregation_on_warehouse_rows():
    from foresight.lanes import WAREHOUSE_BANDS, WAREHOUSE_COLS

    rows = tuple(WAREHOUSE_BANDS)
    # Side-by-side lanes in band 0: east on row 3, west on row 5, 5 moves each.
    side_by_side = corridor_moves([_east(0, 3, 7, 12), _west(1, 5, 27, 22)], rows, WAREHOUSE_COLS)
    assert lane_share(side_by_side) == 1.0                         # each row one-way
    assert lane_share(side_by_side, group=WAREHOUSE_BANDS) == 0.5  # band balanced
    # Both directions on the aisle row: every split is equally mixed.
    mixed = corridor_moves([_east(0, 4, 7, 12), _west(1, 4, 27, 22)], rows, WAREHOUSE_COLS)
    assert lane_share(mixed) == lane_share(mixed, group=WAREHOUSE_BANDS) == 0.5
