"""Pictures of a run: an animated GIF of the agents and visit heatmaps.

Owner: member 1. Uses matplotlib's object API (no pyplot), so it works
without a display.
"""

from __future__ import annotations

from pathlib import Path as FsPath

import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure

from foresight.sim.grid import HOME, OBSTACLE, TASK_ENDPOINT, GridMap
from foresight.sim.metrics import cell_entries
from foresight.sim.simulator import SimulationLog

# free, obstacle, task endpoint, start cell
_MAP_COLORS = ListedColormap(["#ffffff", "#3a3a3a", "#cfe3f5", "#f7e2c8"])
_CODES = {OBSTACLE: 1, TASK_ENDPOINT: 2, HOME: 3}


def map_codes(grid: GridMap) -> np.ndarray:
    return np.array([[_CODES.get(ch, 0) for ch in row] for row in grid.rows])


def draw_map(ax, grid: GridMap) -> None:
    ax.imshow(map_codes(grid), cmap=_MAP_COLORS, vmin=0, vmax=3, interpolation="nearest")
    ax.set_xticks(np.arange(-0.5, grid.width, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, grid.height, 1), minor=True)
    ax.grid(which="minor", color="#e4e4e4", linewidth=0.4)
    ax.tick_params(which="both", length=0, labelbottom=False, labelleft=False)


def carrying(log: SimulationLog) -> dict[int, list[tuple[int, int]]]:
    """agent_id -> [(pickup_time, delivery_time), ...]."""
    spans: dict[int, list[tuple[int, int]]] = {}
    for r in log.records:
        spans.setdefault(r.agent_id, []).append((r.pickup_time, r.delivery_time))
    return spans


def animate(
    log: SimulationLog,
    out: str | FsPath,
    t_from: int = 0,
    t_to: int | None = None,
    every: int = 1,
    fps: int = 8,
    title: str = "",
) -> FsPath:
    """Write an animated GIF of timesteps ``t_from..t_to`` (every ``every``-th).

    Agents are dots in a fixed colour each; a dot is filled while the agent
    carries a package and hollow otherwise. Long runs make large files, so
    ``t_to`` defaults to at most 300 steps after ``t_from``.
    """
    grid = log.instance.grid
    t_to = min(log.n_timesteps, t_from + 300) if t_to is None else min(t_to, log.n_timesteps)
    frames = list(range(t_from, t_to + 1, every))
    spans = carrying(log)
    done_times = sorted(r.delivery_time for r in log.records)
    colors = [f"C{i % 10}" for i in range(len(log.paths))]

    fig = Figure(figsize=(max(4, grid.width * 0.22), max(3, grid.height * 0.22 + 0.6)), dpi=100)
    ax = fig.add_subplot()
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.92)
    draw_map(ax, grid)
    dots = ax.scatter([], [], s=36, linewidths=1.4)
    label = ax.set_title("", fontsize=9)

    def frame(t: int):
        xs, ys, faces = [], [], []
        for p in log.paths:
            r, c = p.at(t)
            xs.append(c)
            ys.append(r)
            loaded = any(a <= t < b for a, b in spans.get(p.agent_id, []))
            faces.append(colors[p.agent_id] if loaded else "none")
        dots.set_offsets(np.column_stack([xs, ys]))
        dots.set_edgecolors(colors)
        dots.set_facecolors(faces)
        completed = sum(1 for d in done_times if d <= t)
        label.set_text(f"{title}  t={t}  done {completed}/{len(log.instance.tasks)}".strip())
        return dots, label

    out = FsPath(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    FuncAnimation(fig, frame, frames=frames, blit=False).save(out, writer=PillowWriter(fps=fps))
    return out


def plot_visits(ax, grid: GridMap, log: SimulationLog, vmax: float | None = None, title: str = ""):
    """Heatmap of how often agents entered each cell; obstacles stay dark."""
    entries = cell_entries(log.paths)
    heat = np.full((grid.height, grid.width), np.nan)
    for r in range(grid.height):
        for c in range(grid.width):
            if grid.passable((r, c)):
                heat[r, c] = entries.get((r, c), 0)
    ax.set_facecolor("#3a3a3a")
    image = ax.imshow(heat, cmap="magma_r", vmin=0, vmax=vmax, interpolation="nearest")
    ax.tick_params(which="both", length=0, labelbottom=False, labelleft=False)
    ax.set_title(title, fontsize=9)
    return image


def save_visit_heatmaps(logs: dict[str, SimulationLog], out: str | FsPath) -> FsPath:
    """Side-by-side visit heatmaps on one shared colour scale, e.g.
    ``{"M0 TP": log0, "M1 Highway": log1, "M5": log5}``."""
    if not logs:
        raise ValueError("no runs to plot")
    vmax = max(max(cell_entries(log.paths).values(), default=1) for log in logs.values())
    grid = next(iter(logs.values())).instance.grid
    fig = Figure(figsize=(3.4 * len(logs) + 0.8, 0.13 * grid.height + 1.2), dpi=150)
    axes = fig.subplots(1, len(logs), squeeze=False)[0]
    for ax, (name, log) in zip(axes, logs.items()):
        image = plot_visits(ax, log.instance.grid, log, vmax=vmax, title=name)
    fig.colorbar(image, ax=list(axes), shrink=0.8, label="entries per cell")
    out = FsPath(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    return out
