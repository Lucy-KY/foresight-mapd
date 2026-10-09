from foresight.costs import METHODS, UnitCost
from foresight.interfaces import CostModel, Path


def test_path_at_and_end_time():
    p = Path(agent_id=0, start_time=5, cells=((0, 0), (0, 1), (0, 1), (1, 1)))
    assert p.end_time == 8
    assert p.at(4) == (0, 0)
    assert p.at(6) == (0, 1)
    assert p.at(8) == (1, 1)
    assert p.at(100) == (1, 1)


def test_path_moves_include_waits():
    p = Path(agent_id=0, start_time=0, cells=((0, 0), (0, 0), (0, 1)))
    assert list(p.moves()) == [((0, 0), (0, 0), 0), ((0, 0), (0, 1), 1)]


def test_unit_cost_is_one_everywhere():
    c = UnitCost()
    assert isinstance(c, CostModel)
    assert c.cost((0, 0), (0, 1), 3) == 1.0
    assert c.cost((0, 0), (0, 0), 3) == 1.0


def test_all_six_methods_registered():
    assert list(METHODS) == [
        "tp",
        "highway",
        "heatmap",
        "foresight",
        "foresight_st",
        "foresight_std",
    ]
