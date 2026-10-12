"""Simulate one run and save it as a GIF plus a visit heatmap.

Usage:
    python experiments/visualize.py --map maps/warehouse_small.map --planner stub \
        --agents 10 --tasks 30 --rate 1 --out results/demo

writes results/demo.gif and results/demo_visits.png. Owner: member 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foresight.experiment import build_cost_model, planners  # noqa: E402
from foresight.sim.grid import GridMap  # noqa: E402
from foresight.sim.instance import make_instance  # noqa: E402
from foresight.sim.simulator import Simulator  # noqa: E402
from foresight.viz import animate, save_visit_heatmaps  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", default="maps/warehouse_small.map")
    parser.add_argument("--planner", default="tp", help="tp, tpts or stub")
    parser.add_argument("--method", default="tp", help="cost model, e.g. tp, foresight_st")
    parser.add_argument("--params", default="{}", help='cost-model parameters as JSON, e.g. \'{"lam": 1, "delta": 2}\'')
    parser.add_argument("--agents", type=int, default=10)
    parser.add_argument("--tasks", type=int, default=30)
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--frames", type=int, default=300, help="at most this many timesteps in the GIF")
    parser.add_argument("--every", type=int, default=1, help="draw every n-th timestep")
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--out", type=Path, default=Path("results/demo"), help="output path without extension")
    args = parser.parse_args()

    instance = make_instance(GridMap.load(args.map), args.agents, args.tasks, args.rate, args.seed)
    cost_model = build_cost_model(args.method, json.loads(args.params))
    log = Simulator(instance, planners()[args.planner](), cost_model).run()
    print(f"{len(log.records)}/{len(instance.tasks)} tasks done in {log.n_timesteps} timesteps")

    label = f"{args.method} ({args.planner})"
    gif = animate(log, args.out.with_suffix(".gif"), t_to=args.frames, every=args.every, fps=args.fps, title=label)
    png = save_visit_heatmaps({label: log}, args.out.parent / f"{args.out.name}_visits.png")
    print(f"wrote {gif} and {png}")


if __name__ == "__main__":
    main()
