import csv

import pytest

from foresight.experiment import columns, expand, job_key, param_grid, run_all, run_job

TINY = {
    "map": "maps/toy_corridor.map",
    "n_tasks": 4,
    "agents": [2],
    "arrival_rates": [1],
    "seeds": [0, 1],
    "planner": "stub",
    "methods": {"tp": {}, "foresight": {"lam": [0.5, 1.0], "window": 5}},
}


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_param_grid_sweeps_lists_only():
    assert param_grid({"lam": [1, 2], "window": 5}) == [{"lam": 1, "window": 5}, {"lam": 2, "window": 5}]
    assert param_grid({}) == [{}]


def test_expand_counts_every_combination():
    jobs = expand(TINY)
    assert len(jobs) == 2 + 2 * 2  # tp: 2 seeds; foresight: 2 lam x 2 seeds
    assert {j["planner"] for j in jobs} == {"stub"}


def test_unknown_method_is_rejected():
    with pytest.raises(ValueError, match="unknown method"):
        expand({**TINY, "methods": {"nope": {}}})


def test_job_key_ignores_dict_order():
    a = {"x": 1, "params": {"lam": 1, "window": 5}}
    b = {"params": {"window": 5, "lam": 1}, "x": 1}
    assert job_key(a) == job_key(b)


def test_header_has_every_param_column():
    header = columns(expand(TINY))
    assert "param_lam" in header and "param_window" in header
    assert header[0] == "job_key" and header[-1] == "git_commit"


def test_run_job_success_row():
    row = run_job(expand(TINY)[0])
    assert row["error"] == "" and row["completed"] is True
    assert row["tasks_completed"] == 4 and row["n_conflicts"] == 0


def test_run_job_records_failures_instead_of_raising():
    job = {**expand(TINY)[0], "method": "highway", "params": {"w_h": 1.5, "directions": "x"}}
    row = run_job(job)
    assert row["error"].startswith("NotImplementedError")


@pytest.mark.parametrize("workers", [1, 2])
def test_run_all_writes_resumes_and_retries(tmp_path, workers):
    out = tmp_path / "out.csv"
    config = {**TINY, "methods": {**TINY["methods"], "highway": {"w_h": 1.5, "directions": "x"}}}

    first = run_all(config, out, n_workers=workers, progress=lambda _: None)
    assert first == {"total": 8, "skipped": 0, "ran": 8, "failed": 2}  # 2 highway jobs fail
    rows = read(out)
    assert len(rows) == 8 and sum(1 for r in rows if r["error"]) == 2

    again = run_all(config, out, n_workers=workers, progress=lambda _: None)
    assert again == {"total": 8, "skipped": 6, "ran": 2, "failed": 2}  # only failures retried
    assert len(read(out)) == 8


def test_limit_and_header_mismatch(tmp_path):
    out = tmp_path / "out.csv"
    assert run_all(TINY, out, limit=1, progress=lambda _: None)["ran"] == 1
    assert len(read(out)) == 1
    with pytest.raises(ValueError, match="different config"):
        run_all({**TINY, "methods": {"tp": {}}}, out, progress=lambda _: None)
