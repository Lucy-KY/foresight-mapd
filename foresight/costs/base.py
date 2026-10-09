"""Base class for step-cost models."""

from __future__ import annotations

from foresight.interfaces import Cell, Path, Timestep


class BaseCostModel:
    """No-op hooks; subclasses override ``cost`` and whichever hooks they need."""

    name = "base"

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        return 1.0

    def on_path_committed(self, path: Path) -> None:
        pass

    def on_path_released(self, path: Path) -> None:
        pass

    def on_timestep(self, t: Timestep, positions: dict[int, Cell]) -> None:
        pass
