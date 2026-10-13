"""Token Passing (Ma et al., 2017).

Owner: member 2.
"""

from __future__ import annotations

from functools import partial

from foresight.interfaces import AgentState, Cell, CostModel, Decision, Path, Task, Timestep
from foresight.planner.astar import DistanceTable, space_time_astar
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

    Args:
        max_time: horizon of each A* search, in timesteps past its start.
    """

    def __init__(self, max_time: int = 1000) -> None:
        self.max_time = max_time

    def reset(self, instance: MapdInstance, cost_model: CostModel) -> None:
        self.instance = instance
        self.grid = instance.grid
        self.endpoints = instance.endpoints
        self.cost_model = cost_model
        self.token = Token(cost_model)
        self.dist = DistanceTable(self.grid)
        self.dist.precompute(self.endpoints)
        for i, loc in enumerate(instance.initial_locations):
            self.token.commit(Path(i, 0, (loc,)))

    def step(self, t: Timestep, agents: list[AgentState], open_tasks: list[Task]) -> list[Decision]:
        """Agents with ``agent.at_path_end(t)`` request the token one after
        another; return one ``Decision`` per agent that got a new path."""
        tasks = list(open_tasks)
        decisions = []
        for agent in sorted(agents, key=lambda a: a.agent_id):
            if agent.at_path_end(t):
                d = self._request_token(t, agent, tasks)
                if d is not None:
                    decisions.append(d)
        return decisions

    def _request_token(self, t: Timestep, agent: AgentState, tasks: list[Task]) -> Decision | None:
        """Lines 6-16 of Algorithm 1. Removes the assigned task from ``tasks``."""
        i, loc = agent.agent_id, agent.location
        ends = self.token.path_ends(exclude=i)
        candidates = [task for task in tasks if task.pickup not in ends and task.delivery not in ends]
        if candidates:
            task = min(candidates, key=lambda task: (self.dist(loc, task.pickup), task.task_id))
            d = self._plan_task(t, i, loc, task)
            if d is not None:
                tasks.remove(task)
                return d
        if all(task.delivery != loc for task in tasks):
            return None  # stay where it is; its parked path already says so
        return self._plan_to_free_endpoint(t, i, loc, tasks, ends)

    def _plan_task(self, t: Timestep, i: int, loc: Cell, task: Task) -> Decision | None:
        """Path1: current location -> pickup -> delivery, parking at the delivery.
        On failure the agent's previous path (if any) is put back."""
        old = self.token.paths.get(i)
        self.token.release(i)
        to_pickup = self._astar(i, loc, task.pickup, t, park=False)
        if to_pickup is not None:
            pickup_time = to_pickup.end_time
            to_delivery = self._astar(i, task.pickup, task.delivery, pickup_time, park=True)
            if to_delivery is not None:
                path = Path(i, t, to_pickup.cells + to_delivery.cells[1:])
                self.token.commit(path)
                return Decision(i, path, task, pickup_time)
        if old is not None:
            self.token.commit(old)
        return None

    def _plan_to_free_endpoint(
        self, t: Timestep, i: int, loc: Cell, tasks: list[Task], ends: set[Cell]
    ) -> Decision | None:
        """Path2: move out of the way to the nearest endpoint that is neither
        the delivery of an open task nor the end of another agent's path."""
        deliveries = {task.delivery for task in tasks}
        free = [e for e in self.endpoints if e != loc and e not in deliveries and e not in ends]
        free = [e for e in free if self.dist(loc, e) is not None]
        free.sort(key=lambda e: (self.dist(loc, e), e))
        old = self.token.paths.get(i)
        self.token.release(i)
        for e in free:
            path = self._astar(i, loc, e, t, park=True)
            if path is not None:
                self.token.commit(path)
                return Decision(i, path)
        if old is not None:
            self.token.commit(old)
        return None

    def _astar(self, i: int, start: Cell, goal: Cell, t: Timestep, park: bool) -> Path | None:
        return space_time_astar(
            self.grid,
            i,
            start,
            goal,
            t,
            self.cost_model,
            partial(self.token.is_blocked, i),
            self.max_time,
            can_stay=partial(self.token.can_stay, i) if park else None,
            distances=self.dist.to(goal),
        )
