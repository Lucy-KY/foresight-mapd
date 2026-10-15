# Experiment configs

Each `.toml` file describes one batch: `python experiments/run.py <config> --out results/<name>.csv --jobs 4`.

```toml
map = "maps/warehouse_small.map"   # relative to the repository root
n_tasks = 500
agents = [10, 30, 50]
arrival_rates = [0.2, 1, 5]        # tasks released per timestep
seeds = [0, 1, 2]
planner = "tp"                     # optional: tp (default), tpts, stub
max_timesteps = 100000             # optional

[methods.foresight_st]             # one table per method in foresight.costs.METHODS
lam = [0.5, 1.0, 2.0]              # a list is swept: one job per value
delta = 2
```

The batch runs every method × parameter combination × agent count × rate × seed.
Re-running with the same `--out` skips jobs that already succeeded and retries failed ones;
`--limit N` runs only N jobs, which is handy for timing a batch first.

## Seeds

Tuning and testing use different seeds, so parameters are never chosen on the runs we report:

| Files | Seeds | Use |
|---|---|---|
| `tune_*.toml` | 100–104 | choosing λ, μ, δ, w_H, β, γ |
| everything else | 0–9 | reported results |

`tests/test_configs.py` enforces this split.

| File | Purpose |
|---|---|
| `smoke.toml` | Pipeline check on the toy map with TP |
| `ma2017_midterm.toml` | Mid-term results: M0, M1, M3, M4, M5, 27 runs each |
| `ma2017_small.toml` | Full reproduction of Ma et al. (2017), Section 6 |
