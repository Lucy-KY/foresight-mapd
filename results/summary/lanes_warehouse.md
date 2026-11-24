# Lane emergence on warehouse_small

Follow-up to `lanes.md`. On narrow_corridor no lanes formed, but its aisles are one cell
wide, so robots can only time-share them. In warehouse_small each aisle is effectively
three cells wide (the endpoint rows above and below are walkable). Here lanes could form
**side by side**: eastbound robots in one row, westbound robots in another.

## Design (fixed 2026-11-24, before any run of this study)

### Aisle bands

Four interior bands of `maps/warehouse_small.map`, each three rows: {3, 4, 5}, {7, 8, 9},
{11, 12, 13}, {15, 16, 17} (endpoint row, aisle row, endpoint row), columns 6-28. The
outer ring bands (rows 0-1 and 19-20) are left out, as on narrow_corridor. A
**corridor move** is a horizontal move with both cells in one band row and both columns
in 6-28. Waits and vertical moves are not counted.

### Metrics (windows of 50 steps)

- **L_row**: the narrow_corridor lane share computed with each of the 12 rows as its own
  corridor: sum over (row, window) of max(E, W) / sum of (E + W).
- **L_band**: the same with each band (3 rows together) as one corridor.
- **Segregation S = L_row - L_band** (primary). S >= 0 always. S is large when opposing
  flows use different rows of the same band (side-by-side lanes) while the band as a
  whole carries both directions; S = 0 when each row is as mixed as its band.
- Descriptive: share of band moves on the middle (aisle) row, head-on encounters per
  task, wait fraction, mean service time, flip rate per row.

Finer splits give fewer moves per cell, which pushes L_row (and so S) up even for random
traffic. The bias is the same for every method on the same seed, so methods are compared
by paired differences.

### Methods

| label | method | params | source |
|---|---|---|---|
| TP | M0 | - | - |
| Highway | M1 | w_h = 1.5, `warehouse_small.highway.json` | `baseline_tuning.md` (only the aisle rows have a direction) |
| M4 | Foresight-ST | lam = 2, delta = 10 | `tune_foresight.md` |
| M5 | Foresight-STD | lam = 2, delta = 10, mu = 4, delta_dir = 2 | `tune_foresight.md` |
| M5-dir | Foresight-STD, lam = 0 | delta_dir = 2, mu tuned | tuning seeds 100-104, 30 agents, rates 1 and 5, mu in {0.5, 1, 2, 4}, rule of `tune_foresight.md` |

### Runs

Test seeds 0-9; 500 tasks; agents {30, 50} x rates {1, 5}; 200 runs, all of which must
complete with 0 conflicts.

### Hypotheses

Paired by (agents, rate, seed); Wilcoxon signed-rank, two-sided, on S:

- **W1 (main):** S(M5) > S(M4). The directional term sorts opposing flows into rows.
- **W2:** S(M5-dir) > S(TP).
- **W3:** S(M4) > S(TP).

Also reported, same tests, on L_row. Per configuration and pooled (40 pairs). Nothing is
dropped if a hypothesis fails.
