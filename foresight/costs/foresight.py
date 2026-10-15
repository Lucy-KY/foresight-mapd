"""M3-M5: Foresight congestion costs built from committed reservations.

Owner: member 3.

    M3  ForesightCost                     1 + lam * rho(v)
    M4  SpatioTemporalCost                1 + lam * rho(v, t)
    M5  SpatioTemporalDirectionalCost     1 + lam * rho(v, t) + mu * c_opp(u -> v, t)

With lam = mu = 0 all three must produce exactly the same paths as M0 (TP).
Waits cost 1 in every method.

Every cost here is at least 1 and at most 1 + lam + mu: the token never lets
two committed paths share a cell at the same time, so a window of n
timesteps holds at most n reservations of a cell (or moves along an edge),
and rho and c_opp stay in [0, 1].
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

    ``cost(u, v, t)`` moves u at t -> v at t + 1, so the arrival time used
    is t + 1.

    ``delta`` must be >= 1: TP already forbids vertex conflicts, so with
    delta = 0 the only reservation at (v, t) is a hard obstacle and the
    term would never matter.

    Reservations before ``t_now`` are left out of the window: they record
    where agents already were, which is history (M2's information), not a
    forecast. The divisor stays 2 * delta + 1.
    """

    name = "foresight_st"

    def __init__(self, lam: float, delta: int) -> None:
        if delta < 1:
            raise ValueError("delta must be >= 1")
        super().__init__(lam)
        self.delta = delta
        self._rho: dict[tuple[Cell, Timestep], float] = {}

    def rho(self, v: Cell, t: Timestep) -> float:
        """Share of [t - delta, t + delta] in which v is reserved, for an
        agent that is at v at time t. Cached per (v, t)."""
        key = (v, t)
        r = self._rho.get(key)
        if r is None:
            t_from = max(t - self.delta, self.t_now)
            n = self.reservations.vertex_window(v, t_from, t + self.delta)
            r = self._rho[key] = n / (2 * self.delta + 1)
        return r

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        if u == v or self.lam == 0:
            return 1.0
        return 1.0 + self.lam * self.rho(v, t + 1)

    def _invalidate(self) -> None:
        self._rho.clear()


class SpatioTemporalDirectionalCost(SpatioTemporalCost):
    """M5 (contributions 1 + 2). Adds ``mu * c_opp(u -> v, t)``: the
    committed moves in the opposite direction v -> u within
    [t - delta_dir, t + delta_dir], divided by 2 * delta_dir + 1. Moving
    with committed traffic costs nothing extra, moving against it does, so
    agents in a corridor end up flowing the same way: one-way lanes emerge
    from traffic instead of being designed offline as in M1.

    ``t`` is the departure time of the move u -> v, the same convention as
    the edge counts ``E[(v, u)][t]``, so no shift is needed (unlike M4,
    which looks at the arrival time t + 1). The window looks both ways:
    a reverse move after t means the two agents are about to meet head-on,
    one before t means they just did.

    ``delta_dir`` must be >= 1: a reverse move at exactly t is a swap
    conflict, which TP already forbids. Normalizing by the window length
    keeps c_opp in [0, 1] (at most one agent moves v -> u per timestep, or
    two would meet at u), on the same scale as rho, so ``mu`` means the same
    for every ``delta_dir``. As in M4, moves before ``t_now`` are history
    and are left out; the divisor stays 2 * delta_dir + 1.

    With mu = 0 the cost equals M4's exactly.
    """

    name = "foresight_std"

    def __init__(self, lam: float, delta: int, mu: float, delta_dir: int) -> None:
        if mu < 0:
            raise ValueError("mu must be >= 0")
        if delta_dir < 1:
            raise ValueError("delta_dir must be >= 1")
        super().__init__(lam, delta)
        self.mu = mu
        self.delta_dir = delta_dir
        self._opp: dict[tuple[Cell, Cell, Timestep], float] = {}

    def c_opp(self, u: Cell, v: Cell, t: Timestep) -> float:
        """Share of [t - delta_dir, t + delta_dir] in which a committed path
        moves v -> u, for a move u -> v departing at t. Cached per (u, v, t)."""
        key = (u, v, t)
        c = self._opp.get(key)
        if c is None:
            t_from = max(t - self.delta_dir, self.t_now)
            n = self.reservations.edge_window(v, u, t_from, t + self.delta_dir)
            c = self._opp[key] = n / (2 * self.delta_dir + 1)
        return c

    def cost(self, u: Cell, v: Cell, t: Timestep) -> float:
        if u == v:
            return 1.0
        w = 1.0
        if self.lam != 0:
            w += self.lam * self.rho(v, t + 1)
        if self.mu != 0:
            w += self.mu * self.c_opp(u, v, t)
        return w

    def _invalidate(self) -> None:
        super()._invalidate()
        self._opp.clear()
