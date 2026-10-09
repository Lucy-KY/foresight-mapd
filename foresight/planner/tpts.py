"""Token Passing with Task Swaps (Ma et al., 2017). Optional.

Owner: member 2.
"""

from __future__ import annotations

from foresight.planner.tp import TokenPassing


class TokenPassingWithSwaps(TokenPassing):
    """TP plus task swaps: an agent may take a task from another agent still
    on its way to the pickup if it can get there sooner."""

    def step(self, t, agents, open_tasks) -> None:
        raise NotImplementedError
