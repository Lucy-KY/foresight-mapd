"""Token Passing (Ma et al., 2017).

Owner: member 2.
"""

from __future__ import annotations

from foresight.interfaces import CostModel
from foresight.planner.token import Token
from foresight.sim.grid import GridMap


class TokenPassing:
    """Reproduction of TP.

    When an agent requests the token it either takes the unassigned task
    whose pickup is nearest (by individual-agent distance) and whose
    endpoints are not the end of another agent's path, or it moves to a
    free endpoint / stays put. Its path is planned with ``space_time_astar``
    against the paths already in the token and then fixed.

    The planner is identical for every method; only ``cost_model`` changes.
    """

    def __init__(self, grid: GridMap, cost_model: CostModel) -> None:
        self.grid = grid
        self.cost_model = cost_model
        self.token = Token(cost_model)

    def step(self, t, agents, open_tasks) -> None:
        """Assign tasks and plan paths for every agent that needs one at t."""
        raise NotImplementedError
