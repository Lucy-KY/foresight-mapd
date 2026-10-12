from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from foresight.costs import UnitCost  # noqa: E402
from foresight.sim.grid import GridMap  # noqa: E402
from foresight.sim.instance import make_instance  # noqa: E402
from foresight.sim.simulator import Simulator  # noqa: E402
from foresight.sim.stubs import OneAtATimePlanner  # noqa: E402
from foresight.viz import animate, carrying, map_codes, save_visit_heatmaps  # noqa: E402

MAPS = Path(__file__).resolve().parents[1] / "maps"


@pytest.fixture(scope="module")
def log():
    inst = make_instance(GridMap.load(MAPS / "toy_corridor.map"), 2, 3, 1, seed=0)
    return Simulator(inst, OneAtATimePlanner(), UnitCost()).run()


def test_map_codes():
    codes = map_codes(GridMap.from_lines([".@", "er"]))
    assert codes.tolist() == [[0, 1], [2, 3]]


def test_carrying_spans_match_records(log):
    spans = carrying(log)
    assert sum(len(v) for v in spans.values()) == len(log.records)


def test_gif_and_heatmap_are_written(tmp_path, log):
    gif = animate(log, tmp_path / "run.gif", every=2, fps=10, title="stub")
    png = save_visit_heatmaps({"a": log, "b": log}, tmp_path / "visits.png")
    assert gif.stat().st_size > 1000 and png.stat().st_size > 1000
    assert gif.read_bytes()[:3] == b"GIF"
