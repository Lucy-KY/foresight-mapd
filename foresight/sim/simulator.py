"""Lifelong MAPD simulator main loop.

Owner: member 1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from foresight.interfaces import (
    AgentState,
    AgentStatus,
    Cell,
    CostModel,
    Decision,
    Path,
    Planner,
    Task,
    Timestep,
)
from foresight.sim.collision import assert_valid
from foresight.sim.instance import MapdInstance
from foresight.sim.metrics import RunResult, TaskRecord, fill_metrics


class PlannerError(RuntimeError):
    """A planner returned a decision that breaks the planner contract."""


@dataclass
class SimulationLog:
    """Everything one run produced; metrics are computed from it."""

    instance: MapdInstance
    paths: list[Path]  # one executed trajectory per agent, from t = 0
    records: list[TaskRecord]  # one per completed task, in completion order
    plan_times_ms: list[float]  # wall time of planner.step per timestep
    n_timesteps: int

    @property
    def completed(self) -> bool:
        return len(self.records) == len(self.instance.tasks)

    def to_result(self, result: RunResult) -> RunResult:
        """Fill ``result`` (method, map, seed, ... already set) with metrics."""
        return fill_metrics(
            result,
            self.instance.grid,
            self.paths,
            self.records,
            self.plan_times_ms,
            n_tasks=len(self.instance.tasks),
        )


class Simulator:
    """Runs one finite task stream until every task is done.

    Each timestep t:
      1. release tasks whose ``release_time`` has come;
      2. call ``planner.step`` (timed) and apply its decisions, checking
         each one against the planner contract;
      3. move every agent to ``path.at(t + 1)`` and update its status
         (pickup at ``pickup_time``, completion at the end of a path that
         ends at the task's delivery);
      4. call ``cost_model.on_timestep(t + 1, positions)``.

    The run stops when every task is completed or after ``max_timesteps``;
    the latter is an incomplete run (``SimulationLog.completed`` is False).
    """

    def __init__(
        self,
        instance: MapdInstance,
        planner: Planner,
        cost_model: CostModel,
        max_timesteps: int = 100_000,
    ) -> None:
        self.instance = instance
        self.planner = planner
        self.cost_model = cost_model
        self.max_timesteps = max_timesteps

    def run(self, check: bool = True) -> SimulationLog:
        """Simulate the instance. With ``check`` (the default) the executed
        trajectories go through ``assert_valid`` at the end, so a planner
        bug raises instead of producing numbers."""
        instance = self.instance
        endpoints = set(instance.endpoints)
        pending = sorted(instance.tasks, key=lambda task: (task.release_time, task.task_id))
        next_release = 0
        open_tasks: dict[int, Task] = {}
        assigned_at: dict[int, Timestep] = {}  # task_id -> when its holder took it
        picked_at: dict[int, Timestep] = {}  # task_id -> pickup time
        records: list[TaskRecord] = []
        plan_times_ms: list[float] = []

        agents = [
            AgentState(i, loc, AgentStatus.IDLE, None, Path(i, 0, (loc,)), None)
            for i, loc in enumerate(instance.initial_locations)
        ]
        trajectories: list[list[Cell]] = [[a.location] for a in agents]

        self.planner.reset(instance, self.cost_model)
        self.cost_model.on_timestep(0, {a.agent_id: a.location for a in agents})

        t = 0
        while len(records) < len(instance.tasks) and t < self.max_timesteps:
            while next_release < len(pending) and pending[next_release].release_time <= t:
                task = pending[next_release]
                open_tasks[task.task_id] = task
                next_release += 1

            offered = [open_tasks[k] for k in sorted(open_tasks)]
            start = time.perf_counter()
            decisions = self.planner.step(t, list(agents), offered)
            plan_times_ms.append((time.perf_counter() - start) * 1000)

            agents = self._apply(t, agents, decisions, open_tasks, assigned_at, picked_at, endpoints)

            moved = []
            for a in agents:
                loc = a.path.at(t + 1)
                trajectories[a.agent_id].append(loc)
                a = replace(a, location=loc)
                if a.status is AgentStatus.TO_PICKUP and a.pickup_time == t + 1:
                    a = replace(a, status=AgentStatus.TO_DELIVERY)
                    picked_at[a.task.task_id] = t + 1
                if (
                    a.status is AgentStatus.TO_DELIVERY
                    and a.at_path_end(t + 1)
                    and loc == a.task.delivery
                ):
                    task = a.task
                    records.append(
                        TaskRecord(task, a.agent_id, assigned_at[task.task_id], picked_at[task.task_id], t + 1)
                    )
                    a = replace(a, status=AgentStatus.IDLE, task=None, pickup_time=None)
                moved.append(a)
            agents = moved
            t += 1
            self.cost_model.on_timestep(t, {a.agent_id: a.location for a in agents})

        paths = [Path(i, 0, tuple(cells)) for i, cells in enumerate(trajectories)]
        if check:
            assert_valid(paths, instance.grid)
        return SimulationLog(instance, paths, records, plan_times_ms, n_timesteps=t)

    @staticmethod
    def _apply(
        t: Timestep,
        agents: list[AgentState],
        decisions: list[Decision],
        open_tasks: dict[int, Task],
        assigned_at: dict[int, Timestep],
        picked_at: dict[int, Timestep],
        endpoints: set[Cell],
    ) -> list[AgentState]:
        """Validate and apply decisions; keep ``open_tasks`` in sync."""
        new = list(agents)
        decided = set()
        for d in decisions:
            if not 0 <= d.agent_id < len(new):
                raise PlannerError(f"t={t}: decision for unknown agent {d.agent_id}")
            if d.agent_id in decided:
                raise PlannerError(f"t={t}: two decisions for agent {d.agent_id}")
            decided.add(d.agent_id)
            a = new[d.agent_id]
            if a.status is AgentStatus.TO_DELIVERY:
                raise PlannerError(f"t={t}: agent {a.agent_id} is carrying task {a.task.task_id} and cannot be replanned")
            p = d.path
            if p.agent_id != d.agent_id or p.start_time != t or p.cells[0] != a.location:
                raise PlannerError(
                    f"t={t}: path for agent {d.agent_id} must start at t={t} from {a.location}, "
                    f"got agent {p.agent_id}, t={p.start_time}, {p.cells[0]}"
                )
            if p.cells[-1] not in endpoints:
                raise PlannerError(f"t={t}: path for agent {d.agent_id} ends at {p.cells[-1]}, not an endpoint")
            if d.task is not None:
                task = d.task
                if task.task_id in picked_at:
                    raise PlannerError(f"t={t}: task {task.task_id} was already picked up")
                held_by_self = a.task is not None and a.task.task_id == task.task_id
                held_by_other = any(
                    b.task is not None and b.task.task_id == task.task_id and b.agent_id != a.agent_id
                    for b in new
                )
                if task.task_id not in open_tasks and not held_by_self and not held_by_other:
                    raise PlannerError(f"t={t}: task {task.task_id} is not released or not open")
                if d.pickup_time is None or not p.start_time <= d.pickup_time <= p.end_time:
                    raise PlannerError(f"t={t}: task {task.task_id} needs a pickup_time on the path")
                if p.at(d.pickup_time) != task.pickup:
                    raise PlannerError(
                        f"t={t}: path of agent {d.agent_id} is at {p.at(d.pickup_time)} at pickup_time "
                        f"{d.pickup_time}, not at pickup {task.pickup}"
                    )
                if p.cells[-1] != task.delivery:
                    raise PlannerError(f"t={t}: path of agent {d.agent_id} must end at delivery {task.delivery}")

            old = a.task
            if d.task is None:
                a = replace(a, status=AgentStatus.IDLE, task=None, path=p, pickup_time=None)
            else:
                open_tasks.pop(d.task.task_id, None)
                if not (old is not None and old.task_id == d.task.task_id):
                    assigned_at[d.task.task_id] = t
                a = replace(a, status=AgentStatus.TO_PICKUP, task=d.task, path=p, pickup_time=d.pickup_time)
                if d.pickup_time == t:
                    a = replace(a, status=AgentStatus.TO_DELIVERY)
                    picked_at[d.task.task_id] = t
            new[d.agent_id] = a
            if old is not None and (d.task is None or old.task_id != d.task.task_id):
                open_tasks[old.task_id] = old  # given up; back to open unless someone else holds it

        holders: dict[int, int] = {}
        for a in new:
            if a.task is None:
                continue
            if a.task.task_id in holders:
                raise PlannerError(
                    f"t={t}: task {a.task.task_id} held by agents {holders[a.task.task_id]} and {a.agent_id}; "
                    "the agent it was taken from needs a decision too"
                )
            holders[a.task.task_id] = a.agent_id
            open_tasks.pop(a.task.task_id, None)
        return new
