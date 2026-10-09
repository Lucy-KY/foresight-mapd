# Maps

| File | Purpose |
|---|---|
| `toy_corridor.map` | Tiny map for unit tests |
| `warehouse.map` | TODO: the warehouse map of Ma et al. (2017); match its size and endpoint layout to the paper |
| `narrow_corridor.map` | TODO: our stress-test map with single-width corridors and few detours |

Format (one character per cell, `#` lines are comments):

| Char | Meaning |
|---|---|
| `.` | free cell |
| `@` | obstacle |
| `e` | task endpoint (pickup / delivery) |
| `r` | non-task endpoint (agent home / parking) |
