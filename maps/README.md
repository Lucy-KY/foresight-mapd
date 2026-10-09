# Maps

| File | Size | Task endpoints | Start cells | Purpose |
|---|---|---|---|---|
| `toy_corridor.map` | 5 x 9 | 3 | 4 | Tiny map for unit tests |
| `warehouse_small.map` | 21 x 35 | 200 | 152 | Small simulated warehouse of Ma et al. (2017), Figure 4 |
| `narrow_corridor.map` | 21 x 35 | 110 | 152 | Our stress-test map with single-lane aisles |

## Format

One character per cell; lines starting with `#` are comments.

| Char | Meaning |
|---|---|
| `.` | free cell |
| `@` | obstacle |
| `e` | task endpoint (pickup / delivery) |
| `r` | candidate agent start cell |

## Notes

**`warehouse_small.map`** was reconstructed cell by cell from Figure 4 of
Ma et al. (2017) and checked against the figure image. The figure shows 10
shelf strips (2 x 5) with task endpoints in the rows directly above and
below each strip, and agents starting in the four side columns. Multi-Goal
MAPD (Xu et al., 2022), which reuses this map, describes the same layout.

The paper says the start locations of the agents are the only non-task
endpoints, but it does not say where agents start when there are fewer than
50 of them. We sample start cells among the `r` cells with the run's seed
(`foresight/sim/instance.py`); unused `r` cells are ordinary free cells.

**`narrow_corridor.map`** keeps the same footprint and side columns but:

- removes the middle cross-aisle, so each horizontal aisle is a 21-cell
  single-lane corridor that can only be entered at its two ends;
- turns the endpoint rows into pockets cut into the shelf faces (every other
  column), so agents can no longer use them as extra lanes.

In `warehouse_small.map` each aisle is effectively three cells wide, because
agents may walk along the endpoint rows. The narrow map removes that slack,
which is where head-on encounters should matter most.

Both maps are well-formed for up to 152 agents; `tests/test_maps.py` checks
this.
