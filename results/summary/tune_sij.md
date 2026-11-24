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

# Results

Produced by `python experiments/select_sij.py results/tune_sij_warehouse_small.csv results/tune_sij_narrow_corridor.csv`.
All 260 runs completed with 0 failures and 0 conflicts. TP's reference numbers match
`baseline_tuning.md` and `tune_foresight.md` exactly (140.8 and 93.2).

## narrow_corridor

TP (nearest pickup): service 140.8, p95 287.6, max 412.3, wait 0.037, head-on/task 0.937 (10 runs, 0 conflicts in all runs).

| beta | gamma | service | vs TP | p95 | max | wait | head-on/task | ms/step |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.01 | 137.6 | -2.3% | 289.6 | 424.6 | 0.037 | 0.929 | 0.74 |
| 5 | 0.05 | 139.7 | -0.8% | 279.4 | 403.6 | 0.037 | 0.931 | 0.65 |
| 5 | 0.1 | 142.1 | +0.9% | 278.1 | 383.9 | 0.036 | 0.919 | 0.68 |
| **10** | **0.01** | **135.5 •** | **-3.8%** | **289.0** | **432.6** | **0.035** | **0.942** | **0.73** |
| 10 | 0.05 | 138.7 | -1.5% | 278.6 | 388.2 | 0.035 | 0.911 | 0.69 |
| 10 | 0.1 | 141.6 | +0.6% | 274.5 | 366.0 | 0.037 | 0.945 | 0.74 |
| 20 | 0.01 | 135.5 • | -3.8% | 290.7 | 439.6 | 0.034 | 0.900 | 0.72 |
| 20 | 0.05 | 137.7 | -2.2% | 281.0 | 395.9 | 0.037 | 0.905 | 0.74 |
| 20 | 0.1 | 141.5 | +0.5% | 278.0 | 387.1 | 0.036 | 0.919 | 0.72 |
| 40 | 0.01 | 135.2 • | -4.0% | 291.8 | 453.6 | 0.035 | 0.919 | 0.92 |
| 40 | 0.05 | 136.2 | -3.3% | 282.1 | 408.8 | 0.035 | 0.918 | 2.04 |
| 40 | 0.1 | 140.0 | -0.6% | 279.2 | 384.3 | 0.035 | 0.923 | 1.04 |

Chosen: beta = 10, gamma = 0.01.

## warehouse_small

TP (nearest pickup): service 93.2, p95 185.3, max 250.7, wait 0.047, head-on/task 0.606 (10 runs, 0 conflicts in all runs).

| beta | gamma | service | vs TP | p95 | max | wait | head-on/task | ms/step |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.01 | 89.3 | -4.3% | 184.3 | 257.4 | 0.045 | 0.596 | 1.05 |
| 5 | 0.05 | 91.7 | -1.6% | 178.8 | 228.6 | 0.046 | 0.609 | 1.10 |
| 5 | 0.1 | 93.9 | +0.7% | 177.6 | 242.1 | 0.046 | 0.616 | 1.00 |
| 10 | 0.01 | 87.8 | -5.9% | 187.7 | 257.4 | 0.043 | 0.601 | 1.13 |
| 10 | 0.05 | 90.3 | -3.2% | 179.2 | 236.6 | 0.045 | 0.612 | 1.33 |
| 10 | 0.1 | 92.4 | -0.9% | 176.1 | 243.5 | 0.046 | 0.596 | 1.19 |
| **20** | **0.01** | **87.3 •** | **-6.4%** | **188.5** | **271.1** | **0.042** | **0.606** | **1.17** |
| 20 | 0.05 | 89.0 | -4.6% | 182.3 | 266.4 | 0.044 | 0.586 | 1.34 |
| 20 | 0.1 | 91.7 | -1.6% | 178.9 | 250.2 | 0.047 | 0.590 | 1.40 |
| 40 | 0.01 | 87.3 • | -6.4% | 193.7 | 277.4 | 0.045 | 0.590 | 1.37 |
| 40 | 0.05 | 87.8 | -5.9% | 186.6 | 253.2 | 0.041 | 0.584 | 1.39 |
| 40 | 0.1 | 90.2 | -3.3% | 182.3 | 250.8 | 0.042 | 0.590 | 1.41 |

Chosen: beta = 20, gamma = 0.01.

## Observations (tuning seeds; not results)

- **Service time**: S_ij is faster than TP in 9 of 12 settings on narrow_corridor and 11 of
  12 on warehouse_small; the chosen settings by 3.8% and 6.4%. That is a larger change
  than any path cost gave on the same seeds (narrow -0.4% to -0.7%, warehouse -1.4% to
  -2.7%, `tune_foresight.md`).
- **The tail goes the other way**: the near-best sets contain only gamma = 0.01, and those
  settings raise the maximum service time (narrow 432.6 vs 412.3, warehouse 271.1 vs 250.7).
  Larger gamma lowers the maximum below TP's (e.g. narrow beta = 10, gamma = 0.1: 366.0)
  but gives back most of the mean gain. The rule fixes gamma = 0.01; the trade-off is
  reported, not tuned away.
- **Head-on encounters and waiting** barely change (within a few percent of TP): choosing
  tasks with less congested routes does not by itself reduce encounters.
- **Planning time** rises from TP's ~0.3 ms/step (narrow) to ~0.7 ms/step; Cong costs a
  route per scored task.
