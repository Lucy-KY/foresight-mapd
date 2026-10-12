"""Token Passing with Task Swaps (Ma et al., 2017). Optional.

Owner: member 2.
"""

from __future__ import annotations

from foresight.interfaces import AgentState, Decision, Task, Timestep
from foresight.planner.tp import TokenPassing


class TokenPassingWithSwaps(TokenPassing):
    """TP plus task swaps: an agent may take a task from another agent still
    on its way to the pickup if it can get there sooner."""

    def step(self, t: Timestep, agents: list[AgentState], open_tasks: list[Task]) -> list[Decision]:
        """Like TP, but a task taken from another agent also needs a
        ``Decision`` for that agent (the simulator checks this)."""
        raise NotImplementedError
