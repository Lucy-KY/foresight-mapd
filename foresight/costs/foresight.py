"""M3-M5: Foresight congestion costs built from committed reservations.

Owner: member 3.

    M3  ForesightCost                     1 + lam * rho(v)
    M4  SpatioTemporalCost                1 + lam * rho(v, t)
    M5  SpatioTemporalDirectionalCost     1 + lam * rho(v, t) + mu * c_opp(u -> v, t)

With lam = mu = 0 all three must produce exactly the same paths as M0 (TP).
Waits cost 1 in every method.
"""

from __future__ import annotations

from foresight.congestion.reservations import ReservationTable
from foresight.costs.base import BaseCostModel
from foresight.interfaces import Cell, Path, Timestep


class _ReservationBacked(BaseCostModel):
    def __init__(self) -> None:
        self.reservations = ReservationTable()

    def on_path_committed(self, path: Path) -> None:
        self.reservations.add_path(path)

    def on_path_released(self, path: Path) -> None:
        self.reservations.remove_path(path)


class ForesightCost(_ReservationBacked):
    """M3. ``rho(v)`` = reservations of v in [t_now, t_now + W) divided by W,
    regardless of when the planned agent actually arrives."""

    name = "foresight"

    def __init__(self, lam: float, window: int) -> None:
        super().__init__()
        self.lam = lam
        self.window = window
        self.t_now = 0

    def on_timestep(self, t: Timestep, positions: dict[int, Cell]) -> None:
        self.t_now = t

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        raise NotImplementedError


class SpatioTemporalCost(_ReservationBacked):
    """M4 (contribution 1). ``rho(v, t)`` counts reservations of v in
    [t - delta, t + delta] around the time the planned agent arrives,
    divided by 2 * delta + 1.

    ``delta`` must be >= 1: TP already forbids vertex conflicts, so with
    delta = 0 the only reservation at (v, t) is a hard obstacle and the
    term would never matter.
    """

    name = "foresight_st"

    def __init__(self, lam: float, delta: int) -> None:
        if delta < 1:
            raise ValueError("delta must be >= 1")
        super().__init__()
        self.lam = lam
        self.delta = delta

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        raise NotImplementedError


class SpatioTemporalDirectionalCost(SpatioTemporalCost):
    """M5 (contributions 1 + 2). Adds ``mu * c_opp(u -> v, t)``: the number
    of committed moves in the opposite direction v -> u within
    [t - delta_dir, t + delta_dir]. Agents in a corridor end up flowing the
    same way, i.e. one-way lanes emerge from traffic instead of being
    designed offline as in M1.
    """

    name = "foresight_std"

    def __init__(self, lam: float, delta: int, mu: float, delta_dir: int) -> None:
        super().__init__(lam, delta)
        self.mu = mu
        self.delta_dir = delta_dir

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        raise NotImplementedError
