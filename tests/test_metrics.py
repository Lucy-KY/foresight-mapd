"""Metrics on hand-built runs whose answers are worked out by hand."""

import pytest

from foresight.interfaces import Path, Task
from foresight.sim.grid import GridMap
from foresight.sim.metrics import (
    RunResult,
    TaskRecord,
    busy_actions,
    cell_entries,
    fill_metrics,
    gini,
    makespan,
    percentile,
    throughput_series,
)

OPEN = GridMap.from_lines(["....", "....", "...."])


def path(agent, cells, start=0):
    return Path(agent_id=agent, start_time=start, cells=tuple(cells))


def record(agent, release, assigned, pickup, delivery, task_id=0):
    task = Task(task_id=task_id, pickup=(0, 0), delivery=(0, 1), release_time=release)
    return TaskRecord(task, agent, assigned, pickup, delivery)


def test_service_time_is_release_to_delivery():
    assert record(0, release=3, assigned=4, pickup=6, delivery=10).service_time == 7


@pytest.mark.parametrize(
    "values, q, expected",
    [
        ([1, 2, 3, 4], 0.5, 2.5),
        ([1, 2, 3, 4], 0.95, 3.85),  # numpy.percentile([1, 2, 3, 4], 95)
        ([7], 0.95, 7),
        ([5, 1, 3], 0.0, 1),
        ([5, 1, 3], 1.0, 5),
    ],
)
def test_percentile_matches_numpy(values, q, expected):
    assert percentile(values, q) == pytest.approx(expected)


def test_percentile_rejects_bad_input():
    with pytest.raises(ValueError):
        percentile([], 0.5)
    with pytest.raises(ValueError):
        percentile([1], 1.5)


def test_makespan_is_last_delivery():
    recs = [record(0, 0, 0, 2, 5), record(1, 0, 1, 3, 9, task_id=1)]
    assert makespan(recs) == 9


def test_throughput_series_counts_a_sliding_window():
    recs = [record(0, 0, 0, 0, 1), record(1, 0, 0, 0, 2, 1), record(2, 0, 0, 0, 5, 2)]
    # window of 3: t=0..6 -> completions in [t-2, t]
    assert throughput_series(recs, horizon=6, window=3) == [0, 1, 2, 2, 1, 1, 1]


def test_busy_actions_count_moves_and_waits_while_on_a_task():
    # Busy from t=1 to t=4: moves (0,0)->(0,0) wait, ->(0,1), ->(0,2).
    p = path(0, [(1, 1), (0, 0), (0, 0), (0, 1), (0, 2), (0, 2)])
    assert busy_actions([p], [record(0, 0, assigned=1, pickup=1, delivery=4)]) == (3, 1)


def test_idle_time_is_not_counted():
    p = path(0, [(0, 0), (0, 0), (0, 0), (0, 1)])
    assert busy_actions([p], [record(0, 0, assigned=2, pickup=2, delivery=3)]) == (1, 0)


def test_cell_entries_ignore_waits():
    p = path(0, [(0, 0), (0, 1), (0, 1), (0, 0), (0, 1)])
    assert cell_entries([p]) == {(0, 1): 2, (0, 0): 1}


def test_gini_extremes():
    assert gini([3, 3, 3, 3]) == 0.0
    assert gini([0, 0, 0, 8]) == pytest.approx(0.75)
    assert gini([]) == 0.0


def test_fill_metrics_on_a_two_agent_run():
    a = path(0, [(0, 0), (0, 1), (0, 2), (0, 2)])
    b = path(1, [(2, 0), (2, 0), (2, 1), (2, 2)])
    recs = [
        record(0, release=0, assigned=0, pickup=1, delivery=2, task_id=0),
        record(1, release=0, assigned=0, pickup=2, delivery=3, task_id=1),
    ]
    result = RunResult(method="tp", map_name="open", n_agents=2, arrival_rate=1, seed=0)
    fill_metrics(result, OPEN, [a, b], recs, plan_times_ms=[1.0, 3.0], n_tasks=2)

    assert result.completed
    assert result.makespan == 3
    assert result.service_time_mean == 2.5
    assert result.service_time_p95 == pytest.approx(2.95)
    assert result.throughput == pytest.approx(2 / 3)
    assert result.total_path_cost == 5  # 2 actions for a, 3 for b
    assert result.wait_fraction == pytest.approx(1 / 5)
    assert result.visit_max == 1
    assert 0 < result.visit_gini < 1  # 4 of 12 cells entered once
    assert result.plan_time_mean_ms == 2.0 and result.plan_time_max_ms == 3.0
    assert result.n_conflicts == 0


def test_fill_metrics_flags_incomplete_runs_and_conflicts():
    a = path(0, [(0, 0), (0, 1)])
    b = path(1, [(0, 1), (0, 0)])  # swap conflict
    result = RunResult(method="tp", map_name="open", n_agents=2, arrival_rate=1, seed=0)
    fill_metrics(result, OPEN, [a, b], records=[], plan_times_ms=[], n_tasks=5)

    assert not result.completed
    assert result.tasks_completed == 0
    assert result.makespan is None and result.service_time_mean is None
    assert result.n_conflicts == 1


def test_to_row_flattens_params():
    result = RunResult(method="foresight", map_name="m", n_agents=1, arrival_rate=1, seed=0, params={"lam": 1.0})
    row = result.to_row()
    assert row["param_lam"] == 1.0 and "params" not in row
