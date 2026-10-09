"""Run results and metric helpers.

Owner: member 1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RunResult:
    """One simulation run. Each field becomes one CSV column."""

    method: str
    map_name: str
    n_agents: int
    arrival_rate: float
    seed: int
    params: dict[str, Any] = field(default_factory=dict)

    makespan: int | None = None
    service_time_mean: float | None = None
    service_time_p95: float | None = None
    throughput: float | None = None
    total_path_cost: int | None = None
    wait_fraction: float | None = None
    head_on_encounters: int | None = None
    visit_gini: float | None = None
    visit_max: int | None = None
    plan_time_mean_ms: float | None = None
    plan_time_max_ms: float | None = None
    n_conflicts: int | None = None

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


def count_head_on_encounters(paths: list) -> int:
    """Count head-on encounters: two agents moving towards each other along
    the same corridor where one is forced to wait or detour.

    TODO: the team needs to fix an exact definition before implementing.
    """
    raise NotImplementedError
