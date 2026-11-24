# Lane emergence on narrow_corridor

Question: do robots in the same single-lane aisle end up moving in the same direction
under M5 (Foresight-STD), without a lane rule given in advance? This is the most direct
evidence for contribution 2 (the directional term c_opp).

## Design (fixed 2026-11-24, before any run of this study)

### Corridors

The four interior single-lane aisles of `maps/narrow_corridor.map`: rows 4, 8, 12 and 16,
columns 7-27 (21 cells, entered only from the side aisles in columns 6 and 28). The outer
ring (rows 0, 20) and the vertical aisles are left out: they are not the single-lane
bottlenecks the map was built for, and they connect to everything else.

A **corridor move** is a horizontal move (u -> v, u != v) inside one aisle row, with both
columns in 6-28. That includes stepping in from or out to a side aisle. Moves into and out
of pockets are vertical, so they are not counted. Waits are not moves.

### Primary metric: majority-direction share L

Cut time into windows of 50 steps. For each (corridor, window), let E and W be the numbers
of east and west corridor moves. Then

    L = sum over (corridor, window) of max(E, W)  /  sum over (corridor, window) of (E + W)

per run, i.e. the share of all corridor moves that go in their window's majority
direction. 1 = every aisle is one-way within each window, 0.5 = balanced two-way traffic.
Small windows push L above 0.5 even for random traffic. The bias is the same for every
method on the same seed, so we compare methods by **paired differences**, not by
distance from 0.5.

### Secondary metrics (descriptive; no claims rest on them)

- L with windows of 25 and 100 steps (robustness to the window choice).
- **Flip rate**: for consecutive windows of the same corridor that both have >= 5 moves,
  the share where the majority direction changes. Low = a lane, once formed, persists.
- **L over time**: L per window index, averaged over seeds, to see whether lanes *form*
  during a run or are there from the start.
- Head-on encounters per task (the team's official definition, from the run metrics),
  plotted next to L.

### Methods

| label | method | params | source |
|---|---|---|---|
| TP | M0 | - | - |
| Highway | M1 | w_h = 1.2, `narrow_corridor.highway.json` | `baseline_tuning.md`; imposed one-way aisles, the reference for "full lanes" |
| M4 | Foresight-ST | lam = 0.5, delta = 2 | `tune_foresight.md` |
| M5 | Foresight-STD | lam = 0.5, delta = 2, mu = 0.5, delta_dir = 2 | `tune_foresight.md` |
| M5-dir | Foresight-STD, direction only | lam = 0, delta_dir = 2, mu tuned | see below |

M5-dir (lam = 0) is tuned the same way as M3-M5: tuning seeds 100-104, 30 agents, rates
1 and 5, mu in {0.5, 1, 2, 4}, and the rule in `tune_foresight.md`.

### Runs

Test seeds 0-9; narrow_corridor; 500 tasks; agents {30, 50} x rates {1, 5} (medium and
high load: lanes need traffic). 4 configurations x 10 seeds x 5 methods = 200 runs. Every
run must complete all tasks with 0 conflicts.

### Tests and hypotheses

Paired by (agents, rate, seed); Wilcoxon signed-rank, two-sided, on L (window 50):

- **H1 (contribution 2, main):** L(M5) > L(M4).
- **H2:** L(M5-dir) > L(TP).
- **H3:** L(M4) > L(TP) (time-resolved density alone already separates flows).

Reported per configuration and pooled over all four (40 pairs). Nothing is dropped if a
hypothesis fails; a null H1 is reported as such.
