# M3-M5 parameter tuning

Configs: `experiments/configs/tune_foresight_{warehouse_small,narrow_corridor}.toml`.
Tuning seeds 100-104 only; 30 agents at 1 and 5 tasks/step, 500 tasks (same setting as
the M1 / M2 tuning in `baseline_tuning.md`). These runs are never reported as results.

## Selection rule (fixed 2026-11-24, before any tuning run was looked at)

Applied separately per map and per method. A *setting* is one parameter combination;
its score is computed over its 10 runs (2 rates x 5 seeds).

1. **Score** = mean service time over the 10 runs (the M1 / M2 criterion).
2. **Near-best set** = settings with score <= 1.005 x the best score of that method
   (within 0.5%, which is below the seed-to-seed noise of the mean at 10 runs).
3. **Waiting cap**: from the near-best set, pick the setting with the **lowest mean wait
   fraction**. Ties (equal to 3 decimals) go to the smaller lam, then the smaller
   window / delta / mu.
4. **Two stages for M5.** Stage 1 tunes M3 and M4 as above. Stage 2 fixes M5's delta to
   M4's chosen delta (delta_dir stays 2) and tunes lam x mu with the same rule. If M4's
   chosen delta is 2, the M5 runs in the tuning configs already are stage 2; otherwise
   M5 is re-run on the tuning seeds with the new delta.
5. Head-on encounters and planning time are reported in the tables but are **not** used
   for selection. If a chosen setting is slower than TP on service time, it is still
   chosen and that fact is stated.

Why the waiting cap: at the mid-term (untuned lam = 1) M4 / M5 raised the wait share by
56% (warehouse) and 162% (narrow) at equal service time. Among settings that serve tasks
equally fast, we prefer the one that waits least, so that we don't pick parameters
that only look good because waiting is cheap.

Note: M1 / M2 were chosen by step 1 alone. Steps 2-3 would have changed only M2 on
warehouse_small (eta 0.99 -> 0.95 at lam = 1, 90.8 vs 91.0, wait 0.050 vs 0.048).
We keep M2 as tuned by member 2.
