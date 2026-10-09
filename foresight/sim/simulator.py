"""Lifelong MAPD simulator main loop.

Owner: member 1.
"""

from __future__ import annotations

from foresight.interfaces import CostModel, Task
from foresight.sim.grid import GridMap
from foresight.sim.metrics import RunResult


class Simulator:
    """Runs one finite task stream to completion.

    Each timestep:
      1. release tasks whose ``release_time`` has come,
      2. let the planner (TP / TPTS) assign tasks and plan paths for agents
         that need one,
      3. advance every agent one step along its committed path,
      4. call ``cost_model.on_timestep`` and record metrics.

    The planner must be swappable with a stub, so the simulator can be
    tested before the real TP exists.
    """

    def __init__(
        self,
        grid: GridMap,
        tasks: list[Task],
        n_agents: int,
        planner,
        cost_model: CostModel,
        max_timesteps: int = 100_000,
    ) -> None:
        self.grid = grid
        self.tasks = tasks
        self.n_agents = n_agents
        self.planner = planner
        self.cost_model = cost_model
        self.max_timesteps = max_timesteps

    def run(self) -> RunResult:
        raise NotImplementedError
