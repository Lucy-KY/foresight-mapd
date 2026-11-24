# M3-M5 sensitivity and the matched-window M3 -> M4 comparison

## Design (fixed 2026-11-24, before any run of this study)

**Purpose.** Show how much the results depend on lam, delta, mu and delta_dir, and
compare M3 with M4 at equal window length. Tuning on narrow_corridor gave M3 a 2-step
window and M4 a 5-step span (delta = 2), so comparing the tuned methods mixes window
size with time resolution. These runs use **test seeds**, but nothing from them changes
the parameters chosen in `tune_foresight.md`; they are reported as they come out.

**Setting.** Both maps; one medium configuration: 30 agents, 1 task per step, 500
tasks; test seeds 0-9. Every run must complete with 0 conflicts.

**One-at-a-time sweeps** around each map's tuned point (narrow: M4 lam = 0.5, delta = 2;
M5 adds mu = 0.5. Warehouse: M4 lam = 2, delta = 10; M5 adds mu = 4. delta_dir = 2):

| sweep | method | varied | values | fixed |
|---|---|---|---|---|
| lam | M4 | lam | 0, 0.25, 0.5, 1, 2, 4, 8 | tuned delta |
| delta | M4 | delta | 1, 2, 3, 5, 10, 20 | tuned lam |
| mu | M5 | mu | 0, 0.5, 1, 2, 4, 8, 16 | tuned lam, delta |
| delta_dir | M5 | delta_dir | 1, 2, 5, 10 | tuned lam, delta, mu |
| matched | M3 and M4 | span s = W = 2 delta + 1 | s = 3, 5, 11, 21 (delta = 1, 2, 5, 10) | lam = M4's tuned lam |

lam = 0 (M4) and mu = 0 (M5) are exactly TP and M4, by the consistency test; they anchor
the curves. delta_dir was never tuned (fixed at 2), so its sweep also shows whether that
choice matters.

**Metrics.** Mean service time, head-on encounters per task and wait fraction (mean and
95% CI over the 10 seeds), with TP as a reference line; planning time per step.

**Matched-window test (the M3 -> M4 ablation).** For each map and span s, paired by
seed, Wilcoxon signed-rank, two-sided:

- **A1:** head-on encounters per task, M4 < M3.
- **A2:** mean service time, M4 vs M3 (no direction predicted).

Reported per span and pooled over the four spans (40 pairs per map). A1 is the claim
"time resolution, not window size, removes the extra encounters".
