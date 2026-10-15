"""Run M0 (TP), M1 (Highway) and M5 (Foresight-STD) on the same instance
and save their visit heatmaps side by side on one colour scale.

Usage:
    python experiments/compare_visits.py --map maps/narrow_corridor.map --w-h 1.2 \
        --out results/summary/visits_narrow_corridor.png

Highway uses the map's own lane file (maps/<map>.highway.json). Owner:
member 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.experiment import ROOT, build_cost_model, planners  # noqa: E402
from foresight.sim.grid import GridMap  # noqa: E402
from foresight.sim.instance import make_instance  # noqa: E402
from foresight.sim.metrics import RunResult  # noqa: E402
from foresight.sim.simulator import Simulator  # noqa: E402
from foresight.viz import save_visit_heatmaps  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", default="maps/warehouse_small.map")
    parser.add_argument("--agents", type=int, default=30)
    parser.add_argument("--tasks", type=int, default=500)
    parser.add_argument("--rate", type=float, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--w-h", type=float, default=1.5, help="Highway penalty (tuned: 1.5 warehouse, 1.2 narrow)")
    parser.add_argument("--m5", default='{"lam": 1.0, "delta": 2, "mu": 1.0, "delta_dir": 2}', help="M5 parameters as JSON")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    map_path = Path(args.map)
    grid = GridMap.load(ROOT / map_path)
    instance = make_instance(grid, args.agents, args.tasks, args.rate, args.seed)
    lanes = str(map_path.with_name(f"{map_path.stem}.highway.json"))
    methods = {
        "M0 TP": ("tp", {}),
        f"M1 Highway (w_h={args.w_h:g})": ("highway", {"directions": lanes, "w_h": args.w_h}),
        "M5 Foresight-STD": ("foresight_std", json.loads(args.m5)),
    }

    logs = {}
    for label, (method, params) in methods.items():
        log = Simulator(instance, planners()["tp"](), build_cost_model(method, params, grid)).run()
        r = log.to_result(RunResult(method, map_path.stem, args.agents, args.rate, args.seed, params))
        logs[f"{label}\nservice {r.service_time_mean:.1f} · head-on {r.head_on_per_task:.2f}/task"] = log
        print(f"{label:28} service {r.service_time_mean:7.1f}  head-on/task {r.head_on_per_task:.3f}  "
              f"wait {r.wait_fraction:.3f}  visit Gini {r.visit_gini:.3f}")

    out = save_visit_heatmaps(logs, args.out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
