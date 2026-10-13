# M1 / M2 parameter tuning

Tuning seeds 100-104; 30 agents at 1 and 5 tasks/step, 500 tasks. Mean service time over both configurations; **bold** = chosen.

## narrow_corridor

TP (M0) reference: 140.8

| method | params | service time | vs TP | wait fraction | ms/step |
|---|---|---:|---:|---:|---:|
| heatmap | `{"eta": 0.95, "lam": 0.5}` | **140.2** | -0.4% | 0.085 | 1.07 |
| heatmap | `{"eta": 0.95, "lam": 1}` | 140.8 | -0.0% | 0.085 | 1.87 |
| heatmap | `{"eta": 0.95, "lam": 2}` | 144.1 | +2.4% | 0.088 | 4.08 |
| heatmap | `{"eta": 0.95, "lam": 4}` | 147.6 | +4.8% | 0.088 | 9.31 |
| heatmap | `{"eta": 0.99, "lam": 0.5}` | 141.0 | +0.2% | 0.090 | 1.42 |
| heatmap | `{"eta": 0.99, "lam": 1}` | 141.2 | +0.3% | 0.087 | 3.02 |
| heatmap | `{"eta": 0.99, "lam": 2}` | 144.0 | +2.2% | 0.086 | 7.15 |
| heatmap | `{"eta": 0.99, "lam": 4}` | 148.6 | +5.6% | 0.092 | 16.41 |
| highway | `{"w_h": 1.2}` | **144.4** | +2.5% | 0.074 | 0.79 |
| highway | `{"w_h": 1.5}` | 144.9 | +2.9% | 0.070 | 0.91 |
| highway | `{"w_h": 2}` | 152.4 | +8.2% | 0.064 | 1.36 |
| highway | `{"w_h": 3}` | 164.5 | +16.8% | 0.052 | 2.03 |

## warehouse_small

TP (M0) reference: 93.2

| method | params | service time | vs TP | wait fraction | ms/step |
|---|---|---:|---:|---:|---:|
| heatmap | `{"eta": 0.95, "lam": 0.5}` | 91.6 | -1.7% | 0.058 | 1.52 |
| heatmap | `{"eta": 0.95, "lam": 1}` | 91.0 | -2.4% | 0.048 | 2.14 |
| heatmap | `{"eta": 0.95, "lam": 2}` | 93.0 | -0.3% | 0.040 | 4.12 |
| heatmap | `{"eta": 0.95, "lam": 4}` | 97.7 | +4.7% | 0.042 | 7.83 |
| heatmap | `{"eta": 0.99, "lam": 0.5}` | 91.5 | -1.8% | 0.058 | 1.52 |
| heatmap | `{"eta": 0.99, "lam": 1}` | **90.8** | -2.6% | 0.050 | 2.57 |
| heatmap | `{"eta": 0.99, "lam": 2}` | 92.3 | -1.0% | 0.040 | 5.47 |
| heatmap | `{"eta": 0.99, "lam": 4}` | 97.1 | +4.2% | 0.041 | 12.43 |
| highway | `{"w_h": 1.2}` | 94.1 | +1.0% | 0.052 | 1.02 |
| highway | `{"w_h": 1.5}` | **93.1** | -0.2% | 0.049 | 1.09 |
| highway | `{"w_h": 2}` | 94.3 | +1.1% | 0.047 | 1.25 |
| highway | `{"w_h": 3}` | 96.8 | +3.9% | 0.044 | 1.42 |
