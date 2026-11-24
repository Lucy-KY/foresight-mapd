"""Task selection: which open task an agent takes when it holds the token.

Owner: member 2.

TP (Ma et al., 2017) always takes the task whose pickup is nearest. That
rule is one ``TaskSelector`` here, ``NearestPickup``, and it is the default,
so TP behaves exactly as before. Congestion-aware assignment (the S_ij
score) is another selector plugged into the same place; nothing else in the
planner changes, which keeps the "routing vs assignment" ablation
controlled.

Writing a selector::

    class MySelector(BaseTaskSelector):
        name = "my_selector"

        def reset(self, ctx: SelectorSetup) -> None:
            super().reset(ctx)            # keeps ctx as self.setup
            ...                           # optional: ctx.token.add_listener(...)

        def rank(self, ctx: SelectionContext, candidates: list[Task]) -> list[Task]:
            return sorted(candidates, key=lambda task: (score(task), task.task_id))

and register the class in ``SELECTORS`` below. Always end the sort key with
``task.task_id`` so ties break deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from foresight.interfaces import Cell, CostModel, Task, Timestep

if TYPE_CHECKING:
    from foresight.planner.astar import DistanceTable
    from foresight.planner.token import Token
    from foresight.sim.instance import MapdInstance


@dataclass(frozen=True)
class SelectorSetup:
    """What a selector may keep for a whole run; given once in ``reset``.

    ``token`` is the live token: ``token.paths`` always holds the committed
    paths, and ``token.add_listener`` streams commits / releases (to keep a
    ``ReservationTable`` of one's own, for instance).
    """

    instance: MapdInstance
    token: Token
    dist: DistanceTable
    cost_model: CostModel


@dataclass(frozen=True)
class SelectionContext:
    """The agent asking for a task, at time ``t``.

    ``dist(a, b)`` is the individual-agent distance (``None`` if b cannot be
    reached). When ``rank`` is called the agent's own old path has *not* been
    released from the token yet, so congestion read from the token
    includes it; exclude ``agent_id`` if that matters.
    """

    t: Timestep
    agent_id: int
    location: Cell
    dist: DistanceTable


@runtime_checkable
class TaskSelector(Protocol):
    """Orders the candidate tasks for one agent, best first.

    ``candidates`` are already filtered by TP's rule (no pickup or delivery
    at the end of another agent's path) and are never empty. TP plans the
    first task in the returned order; TPTS walks down the list. Return the
    same tasks, only reordered (dropping some is allowed, e.g. to cap work,
    but return at least one).
    """

    name: str

    def reset(self, setup: SelectorSetup) -> None: ...

    def rank(self, ctx: SelectionContext, candidates: list[Task]) -> list[Task]: ...


class BaseTaskSelector:
    """Convenience base: stores the setup in ``self.setup``."""

    name = "base"

    def reset(self, setup: SelectorSetup) -> None:
        self.setup = setup

    def rank(self, ctx: SelectionContext, candidates: list[Task]) -> list[Task]:
        raise NotImplementedError

    def __repr__(self) -> str:
        params = ", ".join(f"{k}={v!r}" for k, v in vars(self).items() if k != "setup")
        return f"{type(self).__name__}({params})"


class NearestPickup(BaseTaskSelector):
    """TP's rule: nearest pickup first, ties by task id (Ma et al., 2017)."""

    name = "nearest"

    def rank(self, ctx: SelectionContext, candidates: list[Task]) -> list[Task]:
        return sorted(candidates, key=lambda task: (ctx.dist(ctx.location, task.pickup), task.task_id))


SELECTORS: dict[str, type] = {
    "nearest": NearestPickup,  # TP default
}

# Registered here, after the base classes it imports, to avoid an import cycle.
from foresight.planner.congestion_assignment import CongestionAwareAssignment  # noqa: E402

SELECTORS["sij"] = CongestionAwareAssignment  # S_ij (member 1)

DEFAULT_SELECTOR = "nearest"


def build_selector(name: str = DEFAULT_SELECTOR, params: dict[str, Any] | None = None) -> TaskSelector:
    """Selector registered as ``name``, constructed with ``params``."""
    if name not in SELECTORS:
        raise ValueError(f"unknown task selector {name!r}; known: {sorted(SELECTORS)}")
    return SELECTORS[name](**(params or {}))
