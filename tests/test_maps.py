from pathlib import Path

import pytest

from foresight.sim.grid import GridMap
from foresight.sim.instance import (
    make_instance,
    sample_initial_locations,
    well_formedness_problems,
)

MAPS = Path(__file__).resolve().parents[1] / "maps"


def test_warehouse_small_matches_ma_2017():
    g = GridMap.load(MAPS / "warehouse_small.map")
    assert (g.height, g.width) == (21, 35)
    assert len(g.task_endpoints) == 200
    assert len(g.homes) == 152


def test_narrow_corridor_has_single_lane_aisles():
    g = GridMap.load(MAPS / "narrow_corridor.map")
    assert (g.height, g.width) == (21, 35)
    assert len(g.task_endpoints) == 110
    # Task endpoints are dead-end pockets off an aisle, so endpoint rows cannot
    # be used as extra lanes. The end pockets (columns 7 and 27) also touch the
    # vertical connector, which does not create a lane.
    for e in g.task_endpoints:
        expected = 2 if e[1] in (7, 27) else 1
        assert len(g.neighbors(e)) == expected
    # No cross-aisle: between the two end connectors (columns 6 and 28) no
    # aisle cell connects to the aisle above or below except through a pocket.
    for row in (4, 8, 12, 16):
        for col in range(7, 28):
            for n in ((row - 1, col), (row + 1, col)):
                assert not g.passable(n) or n in g.task_endpoints


@pytest.mark.parametrize("name", ["warehouse_small.map", "narrow_corridor.map"])
@pytest.mark.parametrize("n_agents", [10, 50, 100])
def test_maps_are_well_formed(name, n_agents):
    g = GridMap.load(MAPS / name)
    starts = sample_initial_locations(g, n_agents, seed=0)
    assert well_formedness_problems(g, g.task_endpoints + starts, n_agents) == []


def test_start_sets_are_nested_across_agent_counts():
    g = GridMap.load(MAPS / "warehouse_small.map")
    s10 = sample_initial_locations(g, 10, seed=4)
    s30 = sample_initial_locations(g, 30, seed=4)
    assert s30[:10] == s10
    assert len(set(s30)) == 30


def test_too_many_agents_is_rejected():
    g = GridMap.load(MAPS / "warehouse_small.map")
    with pytest.raises(ValueError):
        sample_initial_locations(g, 153, seed=0)


def test_detects_endpoint_cut_off_by_other_endpoints():
    # The middle endpoint can only be reached through the other two.
    g = GridMap.from_lines(["@@@@@", "@eee@", "@@@@@"])
    problems = well_formedness_problems(g, g.task_endpoints, n_agents=0)
    assert problems


def test_make_instance():
    g = GridMap.load(MAPS / "warehouse_small.map")
    inst = make_instance(g, n_agents=20, n_tasks=500, arrival_rate=2, seed=1)
    assert inst.n_agents == 20
    assert len(inst.tasks) == 500
    assert set(inst.non_task_endpoints) <= set(g.homes)
