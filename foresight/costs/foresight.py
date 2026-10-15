"""M3-M5: Foresight congestion costs built from committed reservations.

Owner: member 3.

    M3  ForesightCost                     1 + lam * rho(v)
    M4  SpatioTemporalCost                1 + lam * rho(v, t)
    M5  SpatioTemporalDirectionalCost     1 + lam * rho(v, t) + mu * c_opp(u -> v, t)

With lam = mu = 0 all three must produce exactly the same paths as M0 (TP).
Waits cost 1 in every method.

Every cost here is at least 1 and at most 1 + lam (plus the M5 term): the
token never lets two committed paths share a cell at the same time, so a
window of n timesteps holds at most n reservations of a cell and rho stays
in [0, 1].
"""

from __future__ import annotations

from foresight.congestion.reservations import ReservationTable
from foresight.costs.base import BaseCostModel
from foresight.interfaces import Cell, Path, Timestep


class _ReservationBacked(BaseCostModel):
    """Keeps a ``ReservationTable`` in sync with the token and remembers the
    current timestep ``t_now`` (the time the planner is being called at).

    Subclasses cache congestion values and drop the cache in
    ``_invalidate``, which runs whenever the table or ``t_now`` changes.
    """

    def __init__(self, lam: float) -> None:
        if lam < 0:
            raise ValueError("lam must be >= 0")
        self.lam = lam
        self.reservations = ReservationTable()
        self.t_now: Timestep = 0

    def on_path_committed(self, path: Path) -> None:
        self.reservations.add_path(path)
        self._invalidate()

    def on_path_released(self, path: Path) -> None:
        self.reservations.remove_path(path)
        self._invalidate()

    def on_timestep(self, t: Timestep, positions: dict[int, Cell]) -> None:
        self.t_now = t
        self._invalidate()

    def _invalidate(self) -> None:
        pass


class ForesightCost(_ReservationBacked):
    """M3. ``rho(v)`` = reservations of v in [t_now, t_now + W) divided by W,
    regardless of when the planned agent actually arrives."""

    name = "foresight"

    def __init__(self, lam: float, window: int) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        super().__init__(lam)
        self.window = window
        self._rho: dict[Cell, float] = {}

    def rho(self, v: Cell) -> float:
        """Share of the next ``window`` timesteps in which v is reserved.

        It does not depend on the arrival time, so one value per cell is
        cached until the table or ``t_now`` changes.
        """
        r = self._rho.get(v)
        if r is None:
            n = self.reservations.vertex_window(v, self.t_now, self.t_now + self.window - 1)
            r = self._rho[v] = n / self.window
        return r

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        if u == v or self.lam == 0:
            return 1.0
        return 1.0 + self.lam * self.rho(v)

    def _invalidate(self) -> None:
        self._rho.clear()


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
        super().__init__(lam)
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
