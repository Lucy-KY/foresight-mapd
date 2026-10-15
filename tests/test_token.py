import pytest

from foresight.costs.base import BaseCostModel
from foresight.costs.unit import UnitCost
from foresight.interfaces import Path
from foresight.planner.token import Token


def path(agent, cells, start=0):
    return Path(agent_id=agent, start_time=start, cells=tuple(cells))


class RecordingCost(BaseCostModel):
    def __init__(self):
        self.events = []

    def on_path_committed(self, p):
        self.events.append(("commit", p.agent_id, p.start_time))

    def on_path_released(self, p):
        self.events.append(("release", p.agent_id, p.start_time))


def token_with(*paths):
    token = Token(UnitCost())
    for p in paths:
        token.commit(p)
    return token


def test_vertex_conflict_is_blocked():
    token = token_with(path(0, [(0, 0), (0, 1), (0, 2)]))
    assert token.is_blocked(1, (1, 1), (0, 1), 0)
    assert not token.is_blocked(1, (1, 1), (0, 1), 1)  # agent 0 has moved on


def test_swap_conflict_is_blocked():
    token = token_with(path(0, [(0, 1), (0, 0)]))
    assert token.is_blocked(1, (0, 0), (0, 1), 0)


def test_following_is_not_blocked():
    token = token_with(path(0, [(0, 1), (0, 2)]))
    assert not token.is_blocked(1, (0, 0), (0, 1), 0)


def test_parked_agent_blocks_forever():
    token = token_with(path(0, [(0, 0), (0, 1)]))
    assert token.is_blocked(1, (1, 1), (0, 1), 100)
    assert token.occupant((0, 1), 100) == 0
    assert token.occupant((0, 1), 0) is None


def test_own_path_never_blocks():
    token = token_with(path(0, [(0, 0), (0, 1)]))
    assert not token.is_blocked(0, (0, 0), (0, 1), 0)
    assert not token.is_blocked(0, (1, 1), (0, 1), 5)


def test_can_stay_waits_for_later_visits():
    token = token_with(path(0, [(0, 0), (0, 1), (0, 2), (0, 3)]))
    assert not token.can_stay(1, (0, 2), 1)
    assert not token.can_stay(1, (0, 2), 2)
    assert token.can_stay(1, (0, 2), 3)
    assert not token.can_stay(1, (0, 3), 50)  # agent 0 parks there
    assert token.can_stay(0, (0, 3), 3)


def test_path_ends():
    token = token_with(path(0, [(0, 0), (0, 1)]), path(1, [(2, 2)]))
    assert token.path_ends() == {(0, 1), (2, 2)}
    assert token.path_ends(exclude=1) == {(0, 1)}


def test_recommit_replaces_old_path():
    token = token_with(path(0, [(0, 0), (0, 1)]))
    token.commit(path(0, [(0, 1), (1, 1)], start=1))
    assert token.path_ends() == {(1, 1)}
    assert token.occupant((0, 0), 0) is None
    assert not token.is_blocked(1, (0, 2), (0, 1), 5)


def test_release_clears_indexes():
    token = token_with(path(0, [(0, 0), (0, 1)]))
    token.release(0)
    assert token.paths == {}
    assert token.path_ends() == set()
    assert not token.is_blocked(1, (1, 1), (0, 1), 3)
    assert token.can_stay(1, (0, 0), 0)
    token.release(0)  # releasing twice is a no-op


def test_colliding_commit_is_rejected():
    token = token_with(path(0, [(0, 0), (0, 1)]))
    with pytest.raises(ValueError):
        token.commit(path(1, [(0, 2), (0, 1)]))
    with pytest.raises(ValueError):
        token.commit(path(1, [(1, 1), (0, 1)], start=5))  # agent 0 is parked there


def test_parking_where_others_pass_later_is_rejected():
    token = token_with(path(0, [(0, 0), (0, 1), (0, 2), (0, 3)]))
    with pytest.raises(ValueError):
        token.commit(path(1, [(1, 2), (0, 2)], start=0))


def test_hooks_are_forwarded():
    cost = RecordingCost()
    token = Token(cost)
    token.commit(path(0, [(0, 0)]))
    token.commit(path(0, [(0, 0), (0, 1)], start=2))
    token.release(0)
    assert cost.events == [
        ("commit", 0, 0),
        ("release", 0, 0),
        ("commit", 0, 2),
        ("release", 0, 2),
    ]
