"""Token Passing (Ma et al., 2017).

Owner: member 2.
"""

from __future__ import annotations

from foresight.interfaces import AgentState, CostModel, Decision, Task, Timestep
from foresight.planner.token import Token
from foresight.sim.instance import MapdInstance


class TokenPassing:
    """Reproduction of TP.

    When an agent requests the token it either takes the unassigned task
    whose pickup is nearest (by individual-agent distance) and whose
    endpoints are not the end of another agent's path, or it moves to a
    free endpoint / stays put. Its path is planned with ``space_time_astar``
    against the paths already in the token and then fixed.

    The planner is identical for every method; only ``cost_model`` changes.
    Implements the ``Planner`` protocol in ``foresight/interfaces.py``.
    """

    def reset(self, instance: MapdInstance, cost_model: CostModel) -> None:
        self.instance = instance
        self.grid = instance.grid
        self.endpoints = instance.endpoints
        self.cost_model = cost_model
        self.token = Token(cost_model)

    def step(self, t: Timestep, agents: list[AgentState], open_tasks: list[Task]) -> list[Decision]:
        """Agents with ``agent.at_path_end(t)`` request the token one after
        another; return one ``Decision`` per agent that got a new path."""
        raise NotImplementedError
