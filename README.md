# Foresight

**Forward-looking congestion maps for lifelong multi-agent pickup and delivery.**

[![tests](https://github.com/Lucy-KY/foresight-mapd/actions/workflows/tests.yml/badge.svg)](https://github.com/Lucy-KY/foresight-mapd/actions/workflows/tests.yml)

In an automated warehouse, hundreds of robots continuously pick up and deliver
items on a shared grid. The standard decoupled algorithm for this setting,
Token Passing (TP) [Ma et al., 2017], plans one agent at a time and fixes each
path once it is planned. It treats the paths already committed by other agents
purely as obstacles to avoid colliding with, and routes on distance alone. As a
result, it cannot tell an empty aisle from an equally short aisle that is about
to fill up.

Foresight keeps TP's sequential, fixed-path structure and changes one thing:
it reads the committed paths as a **forecast** as well as a set of obstacles.
Because paths in the token never change, they say exactly where every agent will
be and when. Foresight converts that forecast into a congestion cost that steers
each newly planned agent away from cells and corridors that will be busy when
it gets there.

> Status: course project for CSE 5106 (Multi-Agent Systems), Washington
> University in St. Louis, Fall 2026. Work in progress; see the
> [roadmap](#roadmap).

## Key ideas

1. **Forward-looking congestion.** Congestion is estimated from reservations
   that agents have already committed in the token, not from past traffic.
2. **Spatio-temporal congestion** `ρ(v, t)`. The planner asks whether a cell
   will be busy *when this agent arrives*, not merely sometime in the next few
   steps. A corridor that is crowded at t = 3 but empty by t = 8 is not
   penalized for an agent arriving at t = 8.
3. **Directional congestion** `c_opp(u → v, t)`. Head-on encounters in narrow
   corridors are the most expensive kind of congestion. Moving against
   committed traffic is penalized, so one-way lanes **emerge from the traffic
   itself** rather than being designed offline per map, as highways are.

No agent ever replans. Every congestion term is computed at planning time for
the one agent being planned, which keeps the method about as cheap as TP.

## Methods compared

All methods share the same simulator, token, task assignment and space-time A*.
The **only** difference between them is the step cost `w` used by A*, which
makes the comparison controlled.

| ID | Method | Step cost `w` | Congestion source | Role |
|---|---|---|---|---|
| M0 | TP | `1` | none | Reproduction of Ma et al. (2017) |
| M1 | Highway-TP | `1` along the highway, `w_H` against it | static, designed offline | Reproduction of Cohen et al. (2015), adapted to TP |
| M2 | Heatmap-TP | `1 + λ·H(v)` | past visits (looks backward) | Control baseline |
| M3 | Foresight | `1 + λ·ρ(v)` | committed reservations in a window | Ours: base |
| M4 | Foresight-ST | `1 + λ·ρ(v, t)` | reservations around arrival time | Ours: + contribution 1 |
| M5 | Foresight-STD | `1 + λ·ρ(v, t) + μ·c_opp(u → v, t)` | + opposite-direction moves | Ours: full method |

M3 → M4 → M5 doubles as an ablation, and M2 isolates the value of looking
forward rather than backward. With `λ = μ = 0`, M3–M5 reduce exactly to M0,
which the test suite checks.

Wait actions cost 1 in every method. All costs are finite and at least 1, so the
true-distance heuristic stays admissible and congestion changes only which
feasible path is preferred, never which paths are feasible.

## Repository layout

```
foresight/
  interfaces.py     Shared types: Cell, Path, Task, CostModel protocol
  sim/              Grid maps, task streams, simulator loop, collision checker, metrics
  planner/          Space-time A*, token, TP, TPTS
  congestion/       Reservation table R[v][t] and E[(u, v)][t]
  costs/            One CostModel per method (M0-M5)
maps/               Map files (format in maps/README.md)
experiments/        Batch runner and TOML experiment configs
results/            Raw outputs (git-ignored except results/summary/)
tests/              Unit tests and the λ = μ = 0 consistency test
```

## Getting started

Requires Python 3.11+.

```bash
git clone https://github.com/Lucy-KY/foresight-mapd.git
cd foresight-mapd
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

List the jobs in an experiment config without running them:

```bash
python experiments/run.py experiments/configs/smoke.toml --out results/smoke.csv --dry-run
```

## Adding a method

Implement the `CostModel` protocol in `foresight/interfaces.py`, usually by
subclassing `foresight.costs.base.BaseCostModel`, and register the class in
`foresight/costs/__init__.py`:

```python
class MyCost(BaseCostModel):
    name = "my_cost"

    def cost(self, u, v, t):          # move u at t -> v at t + 1; u == v is a wait
        return 1.0 + ...

    def on_path_committed(self, path): # keep any reservation state up to date
        ...
```

The token calls `on_path_committed` and `on_path_released`; the simulator calls
`on_timestep` once per step.

## Evaluation plan

- **Maps:** the warehouse map of Ma et al. (2017) and a narrow-corridor
  stress-test map.
- **Variables:** number of agents, task arrival rate (low / medium / high).
- **Metrics:** makespan, mean and 95th-percentile service time, throughput,
  total path cost, wait-action fraction, head-on encounters, congestion
  concentration (Gini of per-cell visits), and planning time per timestep.
- **Protocol:** 10 seeds per configuration. All methods see identical task
  streams for a given seed, and comparisons are paired. Each method's own
  strength parameter (`w_H`, `λ`, `μ`, windows) is tuned on a separate set of
  seeds before testing, so no baseline is handicapped.

## Roadmap

- [x] Shared interfaces and repository skeleton
- [x] Grid map loader
- [ ] Task stream generator and simulator loop
- [ ] Collision checker and metrics
- [ ] Space-time A* with pluggable cost
- [ ] TP reproduction, validated against the trends in Ma et al. (2017)
- [ ] M1 Highway-TP and M2 Heatmap-TP
- [ ] Reservation table and M3 Foresight
- [ ] M4 Foresight-ST and M5 Foresight-STD
- [ ] λ = μ = 0 consistency test enabled
- [ ] Parameter tuning, main experiments and ablations
- [ ] Optional: TPTS; congestion-aware task assignment

## Team

Yiyang Sun · Kaiyuan Xu · Sicheng Yu

## References

1. H. Ma, J. Li, T. K. S. Kumar, S. Koenig. *Lifelong Multi-Agent Path Finding
   for Online Pickup and Delivery Tasks.* AAMAS 2017.
2. L. Cohen, T. Uras, S. Koenig. *Feasibility Study: Using Highways for
   Bounded-Suboptimal Multi-Agent Path Finding.* SoCS 2015.
3. G. Sharon, R. Stern, A. Felner, N. R. Sturtevant. *Conflict-Based Search for
   Optimal Multi-Agent Pathfinding.* Artificial Intelligence 219, 2015.
4. W. Hönig, S. Kiesel, A. Tinka, J. W. Durham, N. Ayanian. *Conflict-Based
   Search with Optimal Task Assignment.* AAMAS 2018.

## License

To be decided.
