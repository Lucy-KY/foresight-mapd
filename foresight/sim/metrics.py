"""Run results and metric helpers.

Owner: member 1.

Every metric is computed after a run from three things the simulator
records: one trajectory per agent (a ``Path`` from t = 0), one
``TaskRecord`` per completed task, and the planner's wall time per timestep.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from foresight.interfaces import Cell, Path, Task, Timestep
from foresight.sim.collision import find_conflicts, find_invalid_moves
from foresight.sim.grid import GridMap


@dataclass(frozen=True)
class TaskRecord:
    """Lifecycle of one completed task.

    ``assigned_time`` is when the agent took the task (its new path starts
    there), ``pickup_time`` when it reached the pickup, ``delivery_time``
    when it reached the delivery and the task was completed.
    """

    task: Task
    agent_id: int
    assigned_time: Timestep
    pickup_time: Timestep
    delivery_time: Timestep

    @property
    def service_time(self) -> int:
        """Timesteps from release to completion (Ma et al., 2017)."""
        return self.delivery_time - self.task.release_time


@dataclass
class RunResult:
    """One simulation run. Each field becomes one CSV column."""

    method: str
    map_name: str
    n_agents: int
    arrival_rate: float
    seed: int
    params: dict[str, Any] = field(default_factory=dict)

    n_tasks: int | None = None
    tasks_completed: int | None = None
    makespan: int | None = None
    service_time_mean: float | None = None
    service_time_p95: float | None = None
    throughput: float | None = None
    total_path_cost: int | None = None
    wait_fraction: float | None = None
    head_on_encounters: int | None = None
    head_on_per_task: float | None = None
    visit_gini: float | None = None
    visit_max: int | None = None
    plan_time_mean_ms: float | None = None
    plan_time_max_ms: float | None = None
    n_conflicts: int | None = None

    @property
    def completed(self) -> bool:
        return self.n_tasks is not None and self.tasks_completed == self.n_tasks

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        params = row.pop("params")
        row.update({f"param_{k}": v for k, v in params.items()})
        return row


def gini(values: list[float]) -> float:
    """Gini coefficient of non-negative values (0 = perfectly even)."""
    xs = sorted(values)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0:
        return 0.0
    weighted = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * weighted) / (n * total) - (n + 1) / n


def percentile(values: list[float], q: float) -> float:
    """``q``-quantile (0 <= q <= 1) with linear interpolation between
    order statistics, the same as ``numpy.percentile``'s default."""
    if not values:
        raise ValueError("percentile of an empty list")
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    xs = sorted(values)
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def makespan(records: list[TaskRecord]) -> int:
    """Timestep at which the last task was completed."""
    return max(r.delivery_time for r in records)


def throughput_series(records: list[TaskRecord], horizon: int, window: int = 100) -> list[int]:
    """Tasks completed in the window [t - window + 1, t] for t = 0..horizon,
    as in Figure 5 of Ma et al. (2017)."""
    done = Counter(r.delivery_time for r in records)
    series, running = [], 0
    for t in range(horizon + 1):
        running += done.get(t, 0) - done.get(t - window, 0)
        series.append(running)
    return series


def busy_actions(paths: list[Path], records: list[TaskRecord]) -> tuple[int, int]:
    """Return ``(actions, waits)`` taken while agents carry out tasks.

    An agent is busy on a task from ``assigned_time`` until
    ``delivery_time``; each timestep in between is one action (a move or a
    wait). Idle parking and moves without a task are not counted.
    """
    by_agent = {p.agent_id: p for p in paths}
    actions = waits = 0
    for r in records:
        p = by_agent[r.agent_id]
        for t in range(r.assigned_time, r.delivery_time):
            actions += 1
            if p.at(t) == p.at(t + 1):
                waits += 1
    return actions, waits


def cell_entries(paths: list[Path]) -> Counter[Cell]:
    """How many times agents moved into each cell (waits are not entries).
    Measures where traffic flows, unlike occupancy, which parked agents
    would dominate."""
    entries: Counter[Cell] = Counter()
    for p in paths:
        for u, v, _ in p.moves():
            if u != v:
                entries[v] += 1
    return entries


def count_head_on_encounters(grid: GridMap, paths: list[Path]) -> int:
    """Count head-on encounters, with the rule the team agreed on in the PRD
    ("对向相遇判定规则").

    Agents i and j have a head-on encounter at timestep t when:
      1. they are in the same row or column, 1 or 2 cells apart;
      2. the cell between them (if any) is passable and empty at t;
      3. both moved one cell along that line towards each other from t - 1
         to t;
      4. the pair did not already meet conditions 1-3 at t - 1 (each
         encounter counts once, at its start).

    No "someone yields afterwards" condition is needed: collision-free paths
    cannot both keep going, so one of them must wait, back off or turn. A
    parked agent blocking a corridor is not counted here.
    """
    if not paths:
        return 0
    horizon = max(p.end_time for p in paths)
    count = 0
    previous: set[tuple[int, int]] = set()
    for t in range(1, horizon + 1):
        here = {p.agent_id: p.at(t) for p in paths}
        occupant = {cell: a for a, cell in here.items()}
        step = {}
        for p in paths:
            (r0, c0), (r1, c1) = p.at(t - 1), here[p.agent_id]
            if (r0, c0) != (r1, c1):
                step[p.agent_id] = (r1 - r0, c1 - c0)

        current = set()
        for i, (dr, dc) in step.items():
            r, c = here[i]
            for gap in (1, 2):
                j = occupant.get((r + gap * dr, c + gap * dc))
                if j is None:
                    continue
                if step.get(j) == (-dr, -dc):
                    middle = (r + dr, c + dc)
                    if gap == 1 or (grid.passable(middle) and middle not in occupant):
                        current.add((min(i, j), max(i, j)))
                break  # the nearest agent ahead blocks the line of sight
        count += len(current - previous)
        previous = current
    return count


def fill_metrics(
    result: RunResult,
    grid: GridMap,
    paths: list[Path],
    records: list[TaskRecord],
    plan_times_ms: list[float],
    n_tasks: int,
) -> RunResult:
    """Compute every implemented metric of one run into ``result``.

    Task-based metrics are left as ``None`` when no task was completed. A
    run that did not complete every task is still filled in, but
    ``result.completed`` is False and it must not be averaged with
    completed runs. The visit Gini covers every passable cell, so cells no
    agent entered count as 0. ``n_conflicts`` counts collisions plus
    invalid moves and must be 0.
    """
    result.n_tasks = n_tasks
    result.tasks_completed = len(records)

    if records:
        services = [r.service_time for r in records]
        result.makespan = makespan(records)
        result.service_time_mean = sum(services) / len(services)
        result.service_time_p95 = percentile(services, 0.95)
        result.throughput = len(records) / result.makespan if result.makespan else None
        actions, waits = busy_actions(paths, records)
        result.total_path_cost = actions
        result.wait_fraction = waits / actions if actions else 0.0

    result.head_on_encounters = count_head_on_encounters(grid, paths)
    if records:
        result.head_on_per_task = result.head_on_encounters / len(records)

    entries = cell_entries(paths)
    passable = [(r, c) for r in range(grid.height) for c in range(grid.width) if grid.passable((r, c))]
    result.visit_gini = gini([entries.get(cell, 0) for cell in passable])
    result.visit_max = max(entries.values(), default=0)

    if plan_times_ms:
        result.plan_time_mean_ms = sum(plan_times_ms) / len(plan_times_ms)
        result.plan_time_max_ms = max(plan_times_ms)

    result.n_conflicts = len(find_conflicts(paths)) + len(find_invalid_moves(grid, paths))
    return result
