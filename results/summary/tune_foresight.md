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

# Results

Produced by
`python experiments/select_tuning.py results/tune_foresight_warehouse_small.csv results/tune_foresight_std_stage2_warehouse_small.csv results/tune_foresight_narrow_corridor.csv`.
All 980 runs completed with 0 failures and 0 conflicts. TP's reference numbers match
`baseline_tuning.md` exactly (140.8 and 93.2), so the batches reproduce. M4 chose delta = 10
on warehouse_small, so M5 stage 2 was re-run there
(`tune_foresight_std_stage2_warehouse_small.toml`, 160 runs). On narrow_corridor M4 chose
delta = 2, so the stage-1 M5 runs are stage 2.

## Observations (tuning seeds; not results)

- **Service time** moves little: narrow -0.4% to -0.7% vs TP, warehouse -1.4% to -2.7%.
  That is in the same range as tuned M2 Heatmap (-0.4% / -2.6%).
- **Head-on encounters per task** vs TP: narrow M3 -21%, M4 -51%, M5 -52%;
  warehouse M3 -42%, M4 -47%, M5 -50%.
- **Waiting**: the cap only helps where waiting varies within the near-best set. Narrow
  M4 / M5 still wait +129% / +131% vs TP. Warehouse M3 -2%, M4 +39%, M5 +26%.
- **M5 vs M4**: differences on every metric are within the seed noise here.
- **Grid edges**: several choices are at the edge of the grid. Narrow: lam = 0.5 and
  window / delta = 2, the smallest values tried. Warehouse: window = 10, delta = 10 and
  mu = 4, the largest values tried. The best setting may lie outside the grid. The rule
  does not extend the grid, so these choices stand.
- **Caveat for the M3 -> M4 ablation**: on narrow_corridor M3 chose window = 2, while
  window = 10 is only 1.1% slower but has half the encounters (-43% vs -21%). Comparing
  tuned M3 with tuned M4 therefore mixes "window size" with "time-resolved". The
  sensitivity study should compare M3 and M4 at matched windows.

## Chosen parameters

| map | method | params |
|---|---|---|
| narrow_corridor | foresight | `lam=0.5, window=2` |
| narrow_corridor | foresight_st | `delta=2, lam=0.5` |
| narrow_corridor | foresight_std | `delta=2, delta_dir=2, lam=0.5, mu=0.5` |
| warehouse_small | foresight | `lam=2, window=10` |
| warehouse_small | foresight_st | `delta=10, lam=2` |
| warehouse_small | foresight_std | `delta=10, delta_dir=2, lam=2, mu=4` |

## narrow_corridor

TP (M0) reference: service time 140.8, wait fraction 0.037, head-on/task 0.937, 0.30 ms/step (10 runs).

### foresight

Near-best = within 0.5% of the best service time (1 of 12 settings, marked •); chosen in **bold**.

| params | runs | service time | vs TP | wait fraction | vs TP | head-on/task | vs TP | ms/step |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`lam=0.5, window=2`** • | 10 | **139.9** | -0.7% | 0.055 | +46% | 0.738 | -21% | 0.48 |
| `lam=0.5, window=5` | 10 | 141.1 | +0.2% | 0.072 | +93% | 0.640 | -32% | 0.51 |
| `lam=0.5, window=10` | 10 | 141.4 | +0.4% | 0.085 | +127% | 0.536 | -43% | 0.51 |
| `lam=1, window=2` | 10 | 140.7 | -0.1% | 0.054 | +43% | 0.764 | -19% | 0.61 |
| `lam=1, window=5` | 10 | 141.9 | +0.8% | 0.075 | +100% | 0.636 | -32% | 0.61 |
| `lam=1, window=10` | 10 | 141.5 | +0.5% | 0.087 | +131% | 0.520 | -45% | 0.63 |
| `lam=2, window=2` | 10 | 143.7 | +2.1% | 0.056 | +49% | 0.743 | -21% | 0.84 |
| `lam=2, window=5` | 10 | 141.9 | +0.8% | 0.071 | +90% | 0.646 | -31% | 0.86 |
| `lam=2, window=10` | 10 | 142.0 | +0.9% | 0.085 | +127% | 0.523 | -44% | 0.94 |
| `lam=4, window=2` | 10 | 145.1 | +3.0% | 0.052 | +38% | 0.793 | -15% | 1.43 |
| `lam=4, window=5` | 10 | 145.1 | +3.1% | 0.069 | +84% | 0.662 | -29% | 1.57 |
| `lam=4, window=10` | 10 | 143.5 | +1.9% | 0.082 | +120% | 0.550 | -41% | 1.54 |

### foresight_st

Near-best = within 0.5% of the best service time (4 of 12 settings, marked •); chosen in **bold**.

| params | runs | service time | vs TP | wait fraction | vs TP | head-on/task | vs TP | ms/step |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`delta=2, lam=0.5`** • | 10 | **140.1** | -0.5% | 0.086 | +129% | 0.461 | -51% | 0.50 |
| `delta=5, lam=0.5` • | 10 | 140.2 | -0.4% | 0.092 | +145% | 0.526 | -44% | 0.53 |
| `delta=10, lam=0.5` • | 10 | 140.6 | -0.1% | 0.090 | +140% | 0.503 | -46% | 0.56 |
| `delta=2, lam=1` | 10 | 142.0 | +0.9% | 0.092 | +145% | 0.476 | -49% | 0.55 |
| `delta=5, lam=1` | 10 | 141.3 | +0.4% | 0.093 | +148% | 0.541 | -42% | 0.60 |
| `delta=10, lam=1` • | 10 | 140.0 | -0.6% | 0.090 | +140% | 0.502 | -46% | 0.61 |
| `delta=2, lam=2` | 10 | 144.6 | +2.7% | 0.102 | +172% | 0.454 | -52% | 0.60 |
| `delta=5, lam=2` | 10 | 141.5 | +0.5% | 0.096 | +156% | 0.556 | -41% | 0.75 |
| `delta=10, lam=2` | 10 | 141.1 | +0.2% | 0.089 | +136% | 0.498 | -47% | 0.69 |
| `delta=2, lam=4` | 10 | 148.6 | +5.5% | 0.117 | +213% | 0.408 | -56% | 0.63 |
| `delta=5, lam=4` | 10 | 145.9 | +3.6% | 0.109 | +190% | 0.546 | -42% | 0.90 |
| `delta=10, lam=4` | 10 | 142.6 | +1.3% | 0.096 | +156% | 0.522 | -44% | 0.90 |

### foresight_std

Near-best = within 0.5% of the best service time (4 of 16 settings, marked •); chosen in **bold**. Stage 2: delta fixed to M4's chosen delta = 2.

| params | runs | service time | vs TP | wait fraction | vs TP | head-on/task | vs TP | ms/step |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`delta=2, delta_dir=2, lam=0.5, mu=0.5`** • | 10 | **140.2** | -0.4% | 0.087 | +131% | 0.453 | -52% | 0.68 |
| `delta=2, delta_dir=2, lam=0.5, mu=1` • | 10 | 140.3 | -0.4% | 0.087 | +132% | 0.482 | -49% | 0.67 |
| `delta=2, delta_dir=2, lam=0.5, mu=2` • | 10 | 140.3 | -0.3% | 0.087 | +132% | 0.469 | -50% | 0.74 |
| `delta=2, delta_dir=2, lam=0.5, mu=4` • | 10 | 140.4 | -0.3% | 0.089 | +136% | 0.441 | -53% | 0.75 |
| `delta=2, delta_dir=2, lam=1, mu=0.5` | 10 | 141.3 | +0.4% | 0.091 | +142% | 0.465 | -50% | 0.72 |
| `delta=2, delta_dir=2, lam=1, mu=1` | 10 | 141.1 | +0.2% | 0.092 | +146% | 0.466 | -50% | 0.73 |
| `delta=2, delta_dir=2, lam=1, mu=2` | 10 | 141.2 | +0.3% | 0.090 | +139% | 0.469 | -50% | 0.73 |
| `delta=2, delta_dir=2, lam=1, mu=4` | 10 | 141.4 | +0.4% | 0.091 | +142% | 0.454 | -52% | 0.84 |
| `delta=2, delta_dir=2, lam=2, mu=0.5` | 10 | 144.9 | +2.9% | 0.104 | +178% | 0.452 | -52% | 0.83 |
| `delta=2, delta_dir=2, lam=2, mu=1` | 10 | 145.1 | +3.1% | 0.101 | +169% | 0.452 | -52% | 0.78 |
| `delta=2, delta_dir=2, lam=2, mu=2` | 10 | 144.5 | +2.6% | 0.102 | +172% | 0.443 | -53% | 0.78 |
| `delta=2, delta_dir=2, lam=2, mu=4` | 10 | 145.8 | +3.6% | 0.105 | +180% | 0.426 | -55% | 0.83 |
| `delta=2, delta_dir=2, lam=4, mu=0.5` | 10 | 149.2 | +6.0% | 0.118 | +214% | 0.430 | -54% | 0.86 |
| `delta=2, delta_dir=2, lam=4, mu=1` | 10 | 149.2 | +5.9% | 0.117 | +211% | 0.409 | -56% | 0.90 |
| `delta=2, delta_dir=2, lam=4, mu=2` | 10 | 149.7 | +6.3% | 0.117 | +213% | 0.411 | -56% | 0.89 |
| `delta=2, delta_dir=2, lam=4, mu=4` | 10 | 151.1 | +7.3% | 0.121 | +222% | 0.404 | -57% | 0.93 |

## warehouse_small

TP (M0) reference: service time 93.2, wait fraction 0.047, head-on/task 0.606, 0.51 ms/step (10 runs).

### foresight

Near-best = within 0.5% of the best service time (2 of 12 settings, marked •); chosen in **bold**.

| params | runs | service time | vs TP | wait fraction | vs TP | head-on/task | vs TP | ms/step |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `lam=0.5, window=2` | 10 | 92.1 | -1.3% | 0.047 | +0% | 0.476 | -21% | 0.74 |
| `lam=0.5, window=5` | 10 | 91.9 | -1.4% | 0.053 | +13% | 0.414 | -32% | 0.75 |
| `lam=0.5, window=10` | 10 | 91.8 | -1.6% | 0.058 | +23% | 0.368 | -39% | 0.78 |
| `lam=1, window=2` | 10 | 91.9 | -1.4% | 0.046 | -2% | 0.466 | -23% | 0.82 |
| `lam=1, window=5` | 10 | 91.6 | -1.8% | 0.052 | +11% | 0.419 | -31% | 0.84 |
| `lam=1, window=10` • | 10 | 91.0 | -2.5% | 0.054 | +15% | 0.367 | -39% | 0.89 |
| `lam=2, window=2` | 10 | 92.8 | -0.5% | 0.040 | -14% | 0.460 | -24% | 0.99 |
| `lam=2, window=5` | 10 | 92.1 | -1.2% | 0.043 | -7% | 0.406 | -33% | 1.09 |
| **`lam=2, window=10`** • | 10 | **90.7** | -2.7% | 0.046 | -2% | 0.349 | -42% | 1.07 |
| `lam=4, window=2` | 10 | 95.6 | +2.5% | 0.034 | -26% | 0.447 | -26% | 1.24 |
| `lam=4, window=5` | 10 | 95.0 | +1.9% | 0.038 | -19% | 0.398 | -34% | 1.49 |
| `lam=4, window=10` | 10 | 93.5 | +0.2% | 0.042 | -10% | 0.348 | -43% | 1.50 |

### foresight_st

Near-best = within 0.5% of the best service time (3 of 12 settings, marked •); chosen in **bold**.

| params | runs | service time | vs TP | wait fraction | vs TP | head-on/task | vs TP | ms/step |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `delta=2, lam=0.5` | 10 | 93.1 | -0.2% | 0.065 | +40% | 0.328 | -46% | 0.81 |
| `delta=5, lam=0.5` | 10 | 92.2 | -1.1% | 0.067 | +43% | 0.342 | -44% | 0.88 |
| `delta=10, lam=0.5` • | 10 | 91.6 | -1.7% | 0.067 | +43% | 0.335 | -45% | 0.92 |
| `delta=2, lam=1` | 10 | 93.3 | +0.0% | 0.070 | +50% | 0.321 | -47% | 0.88 |
| `delta=5, lam=1` | 10 | 92.6 | -0.7% | 0.067 | +44% | 0.341 | -44% | 0.92 |
| `delta=10, lam=1` • | 10 | 91.9 | -1.5% | 0.066 | +42% | 0.337 | -44% | 1.00 |
| `delta=2, lam=2` | 10 | 94.4 | +1.2% | 0.072 | +55% | 0.318 | -48% | 0.91 |
| `delta=5, lam=2` | 10 | 92.7 | -0.6% | 0.062 | +33% | 0.320 | -47% | 0.98 |
| **`delta=10, lam=2`** • | 10 | **91.9** | -1.4% | 0.065 | +39% | 0.323 | -47% | 1.07 |
| `delta=2, lam=4` | 10 | 97.4 | +4.4% | 0.079 | +69% | 0.289 | -52% | 0.98 |
| `delta=5, lam=4` | 10 | 95.1 | +1.9% | 0.069 | +48% | 0.310 | -49% | 1.19 |
| `delta=10, lam=4` | 10 | 93.2 | -0.0% | 0.059 | +27% | 0.310 | -49% | 1.24 |

### foresight_std

Near-best = within 0.5% of the best service time (8 of 16 settings, marked •); chosen in **bold**. Stage 2: delta fixed to M4's chosen delta = 10.

| params | runs | service time | vs TP | wait fraction | vs TP | head-on/task | vs TP | ms/step |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `delta=10, delta_dir=2, lam=0.5, mu=0.5` | 10 | 92.4 | -0.9% | 0.067 | +45% | 0.322 | -47% | 1.08 |
| `delta=10, delta_dir=2, lam=0.5, mu=1` • | 10 | 92.0 | -1.3% | 0.064 | +38% | 0.319 | -47% | 1.09 |
| `delta=10, delta_dir=2, lam=0.5, mu=2` • | 10 | 91.9 | -1.4% | 0.065 | +40% | 0.308 | -49% | 1.06 |
| `delta=10, delta_dir=2, lam=0.5, mu=4` | 10 | 92.2 | -1.1% | 0.065 | +39% | 0.308 | -49% | 1.07 |
| `delta=10, delta_dir=2, lam=1, mu=0.5` • | 10 | 91.9 | -1.4% | 0.064 | +37% | 0.316 | -48% | 1.15 |
| `delta=10, delta_dir=2, lam=1, mu=1` | 10 | 92.2 | -1.1% | 0.067 | +43% | 0.317 | -48% | 1.11 |
| `delta=10, delta_dir=2, lam=1, mu=2` • | 10 | 91.8 | -1.5% | 0.064 | +36% | 0.320 | -47% | 1.16 |
| `delta=10, delta_dir=2, lam=1, mu=4` | 10 | 92.2 | -1.1% | 0.064 | +37% | 0.313 | -48% | 1.20 |
| `delta=10, delta_dir=2, lam=2, mu=0.5` • | 10 | 91.6 | -1.8% | 0.061 | +30% | 0.324 | -46% | 1.26 |
| `delta=10, delta_dir=2, lam=2, mu=1` • | 10 | 91.8 | -1.6% | 0.060 | +29% | 0.307 | -49% | 1.19 |
| `delta=10, delta_dir=2, lam=2, mu=2` • | 10 | 91.9 | -1.4% | 0.061 | +32% | 0.309 | -49% | 1.27 |
| **`delta=10, delta_dir=2, lam=2, mu=4`** • | 10 | **91.7** | -1.7% | 0.059 | +26% | 0.301 | -50% | 1.25 |
| `delta=10, delta_dir=2, lam=4, mu=0.5` | 10 | 93.1 | -0.2% | 0.059 | +26% | 0.303 | -50% | 1.46 |
| `delta=10, delta_dir=2, lam=4, mu=1` | 10 | 92.9 | -0.4% | 0.060 | +28% | 0.296 | -51% | 1.42 |
| `delta=10, delta_dir=2, lam=4, mu=2` | 10 | 92.3 | -1.1% | 0.058 | +25% | 0.288 | -53% | 1.46 |
| `delta=10, delta_dir=2, lam=4, mu=4` | 10 | 93.3 | +0.1% | 0.058 | +24% | 0.283 | -53% | 1.45 |

