# S_ij parameter tuning

Configs: `experiments/configs/tune_sij_{warehouse_small,narrow_corridor}.toml`.
Tuning seeds 100-104 only; 30 agents at 1 and 5 tasks/step, 500 tasks, TP routing
(unit cost). These runs are never reported as results.

Grid: beta in {5, 10, 20, 40} x gamma in {0.01, 0.05, 0.1}; alpha = 1 and the Cong
window (5, M3's) are fixed. beta is on the scale of a route length because h and age
are in timesteps while Cong is a density in [0, 1].

## Selection rule (fixed 2026-11-24, before any tuning run)

Applied separately per map, as for M3-M5 (`tune_foresight.md`). A setting's score is
computed over its 10 runs (2 rates x 5 seeds).

1. **Score** = mean service time over the 10 runs.
2. **Near-best set** = settings with score <= 1.005 x the best score.
3. From the near-best set, pick the setting with the **lowest mean 95th-percentile
   service time** (the age term exists for the slow tail). Ties (equal to 1 decimal)
   go to the smaller beta, then the smaller gamma.
4. If the chosen setting is slower than TP (nearest pickup) on mean service time, it is
   still chosen and that is stated. Head-on encounters, wait fraction, maximum service
   time and planning time are reported but not used for selection.

The chosen (beta, gamma) per map are then used unchanged for TP + S_ij, M3 + S_ij
and M5 + S_ij in the main experiments.
