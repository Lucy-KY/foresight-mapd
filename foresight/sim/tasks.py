"""Task stream generation.

Owner: member 1.
"""

from __future__ import annotations

from foresight.interfaces import Task
from foresight.sim.grid import GridMap


def generate_task_stream(
    grid: GridMap, n_tasks: int, arrival_rate: float, seed: int
) -> list[Task]:
    """Generate a finite stream of ``n_tasks`` tasks.

    ``arrival_rate`` is the number of tasks released per timestep (it may be
    below 1, e.g. 0.5 means one task every two timesteps). Pickup and
    delivery are distinct cells drawn uniformly from ``grid.task_endpoints``.

    The same ``seed`` must give the same stream, because every method is
    evaluated on identical streams (common random numbers).

    TODO: check the arrival rates and task counts used by Ma et al. (2017).
    """
    raise NotImplementedError
