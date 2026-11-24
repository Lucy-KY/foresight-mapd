"""S_ij: congestion-aware task assignment (proposal section 3.3).

Owner: member 1.

An agent holding the token takes the candidate task with the smallest

    S_ij = alpha * h + beta * Cong - gamma * age

- ``h``: individual-agent distance from the agent to the pickup (TP's key).
- ``Cong``: mean ``rho(v)`` over the cells of a shortest route
  agent -> pickup -> delivery, where ``rho`` is M3's: the share of the next
  ``window`` timesteps in which v is reserved by *other* agents' committed
  paths. Read from a reservation table of the selector's own, so it works
  under any cost model, including TP's unit cost.
- ``age``: timesteps since the task was released, so that tasks in crowded
  corners are not starved.

With ``beta = gamma = 0`` the ranking is exactly TP's nearest-pickup rule.

Cost control: ``Cong`` needs a route per task, so it is only computed for
the most promising tasks. ``Cong >= 0`` gives the lower bound
``alpha * h - gamma * age`` on the score; tasks are scored exactly in order
of that bound until no remaining task can beat the best score found, or
``max_scored`` tasks have been scored. Unlike "the k nearest tasks", an old
task far away can still be scored first, which is what the age term is for.
"""

from __future__ import annotations

from foresight.congestion.reservations import ReservationTable
from foresight.interfaces import Cell, Task
from foresight.planner.assignment import BaseTaskSelector, SelectionContext, SelectorSetup


class CongestionAwareAssignment(BaseTaskSelector):
    """The S_ij score. ``alpha`` is the weight of the distance (fixed to 1
    in our experiments); ``beta`` and ``gamma`` are tuned."""

    name = "sij"

    def __init__(
        self,
        beta: float,
        gamma: float,
        alpha: float = 1.0,
        window: int = 5,
        max_scored: int = 20,
    ) -> None:
        if alpha <= 0 or beta < 0 or gamma < 0:
            raise ValueError("need alpha > 0 and beta, gamma >= 0")
        if window < 1 or max_scored < 1:
            raise ValueError("window and max_scored must be >= 1")
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.window = window
        self.max_scored = max_scored

    def reset(self, setup: SelectorSetup) -> None:
        super().reset(setup)
        self.reservations = ReservationTable()
        setup.token.add_listener(self.reservations)
        self.grid = setup.instance.grid

    def rank(self, ctx: SelectionContext, candidates: list[Task]) -> list[Task]:
        def bound(task: Task) -> float:
            return self.alpha * ctx.dist(ctx.location, task.pickup) - self.gamma * (ctx.t - task.release_time)

        by_bound = sorted(candidates, key=lambda task: (bound(task), task.task_id))
        if self.beta == 0:  # Cong does not matter: the bound is the score
            return by_bound
        scored: list[tuple[float, int, Task]] = []
        rho_cache: dict[Cell, float] = {}
        for k, task in enumerate(by_bound):
            if k == self.max_scored or (scored and bound(task) > min(scored)[0]):
                rest = by_bound[k:]
                break
            s = bound(task) + self.beta * self.congestion(ctx, task, rho_cache)
            scored.append((s, task.task_id, task))
        else:
            rest = []
        return [task for _, _, task in sorted(scored, key=lambda x: x[:2])] + rest

    # -- Cong -------------------------------------------------------------

    def congestion(self, ctx: SelectionContext, task: Task, rho_cache: dict[Cell, float] | None = None) -> float:
        """Mean rho over the cells of the route agent -> pickup -> delivery."""
        route = self.route(ctx, ctx.location, task.pickup) + self.route(ctx, task.pickup, task.delivery)[1:]
        if rho_cache is None:
            rho_cache = {}
        total = 0.0
        for v in route:
            r = rho_cache.get(v)
            if r is None:
                r = rho_cache[v] = self.rho(ctx, v)
            total += r
        return total / len(route)

    def rho(self, ctx: SelectionContext, v: Cell) -> float:
        """M3's rho(v) at ``ctx.t``, counting only other agents' paths.

        When ``rank`` is called the asking agent's own old path is still in
        the token (and so in the table); its cells are subtracted here.
        """
        t_from, t_to = ctx.t, ctx.t + self.window - 1
        n = self.reservations.vertex_window(v, t_from, t_to)
        own = self.setup.token.paths.get(ctx.agent_id)
        if own is not None:
            n -= sum(1 for k, c in enumerate(own.cells) if c == v and t_from <= own.start_time + k <= t_to)
        return n / self.window

    def route(self, ctx: SelectionContext, a: Cell, b: Cell) -> list[Cell]:
        """One shortest route a -> b (both included), read back from the BFS
        distance table: always step to the first neighbour, in the grid's
        neighbour order, that is one step closer to b."""
        to_b = ctx.dist.to(b)
        route = [a]
        while route[-1] != b:
            here = to_b[route[-1]]
            route.append(next(n for n in self.grid.neighbors(route[-1]) if to_b.get(n) == here - 1))
        return route
