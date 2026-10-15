"""Token Passing with Task Swaps (Ma et al., 2017). Optional.

Owner: member 2.
"""

from __future__ import annotations

from foresight.interfaces import AgentState, AgentStatus, Decision, Path, Task, Timestep
from foresight.planner.tp import TokenPassing


class TokenPassingWithSwaps(TokenPassing):
    """TP plus task swaps: an agent may take a task from another agent still
    on its way to the pickup if it can get there sooner.

    Follows Algorithm 2 (GetTask) of Ma et al. (2017). The task set holds
    every task not yet picked up, assigned or not. Taking a task from agent
    a' releases a''s path, plans Path1 for the taker and keeps the swap only
    if the taker reaches the pickup strictly earlier and a' then succeeds in
    its own GetTask; otherwise the token, task set and assignments are
    restored and the next task is tried. Two details differ from a literal
    reading of the pseudo-code:

    - Line 12 drops tasks whose pickup or delivery is the end of *another*
      agent's path. The holder's own path always ends at the delivery, so we
      ignore the holder's path there; otherwise no task could ever be taken.
    - An agent that lost its task is mid-path. Like line 35 it moves to a
      free endpoint and may fail, but it may also rest where it is (lines
      39-40) if that cell is an endpoint no committed path visits later.
    """

    def step(self, t: Timestep, agents: list[AgentState], open_tasks: list[Task]) -> list[Decision]:
        """Like TP, but a task taken from another agent also needs a
        ``Decision`` for that agent (the simulator checks this)."""
        self._t = t
        self._loc = {a.agent_id: a.location for a in agents}
        self._tasks = {task.task_id: task for task in open_tasks}
        self._holder: dict[int, int] = {}  # task_id -> agent on its way to the pickup
        self._pickup_time: dict[int, Timestep] = {}  # agent -> when it reaches its pickup
        for a in agents:
            if a.status is AgentStatus.TO_PICKUP:
                self._tasks[a.task.task_id] = a.task
                self._holder[a.task.task_id] = a.agent_id
                self._pickup_time[a.agent_id] = a.pickup_time
        self._decisions: dict[int, Decision] = {}
        for agent in sorted(agents, key=lambda a: a.agent_id):
            if agent.at_path_end(t):
                self._get_task(agent.agent_id, depth=0)
        return list(self._decisions.values())

    def _get_task(self, i: int, depth: int) -> bool:
        t, loc = self._t, self._loc[i]
        owners = self.token.end_owners()
        candidates = []
        for task in self._tasks.values():
            holder = self._holder.get(task.task_id)
            if holder == i:
                continue
            if all(owners.get(c) in (None, i, holder) for c in (task.pickup, task.delivery)):
                candidates.append(task)
        candidates.sort(key=lambda task: (self.dist(loc, task.pickup), task.task_id))

        for task in candidates:
            holder = self._holder.get(task.task_id)
            if holder is None:
                d = self._plan_task(t, i, loc, task)
                if d is not None:
                    self._assign(i, task, d)
                    return True
                continue
            theirs = self._pickup_time[holder]
            if t + self.dist(loc, task.pickup) >= theirs:
                continue  # cannot get there strictly earlier
            saved = self._save()
            del self._pickup_time[holder]
            del self._holder[task.task_id]
            self.token.release(holder)
            d = self._plan_task(t, i, loc, task)
            if d is not None and d.pickup_time < theirs:
                self._assign(i, task, d)
                if depth < len(self._loc) and self._get_task(holder, depth + 1):
                    return True
            self._restore(saved)

        tasks = list(self._tasks.values())
        if depth == 0:  # at the end of its path, hence at an endpoint
            if any(task.delivery == loc for task in tasks):
                d = self._plan_to_free_endpoint(t, i, loc, tasks, self.token.path_ends(exclude=i))
                if d is not None:
                    self._decide(d)
            return True

        # Lost its task while on the way to the pickup.
        if (
            loc in self.endpoints
            and loc not in self.token.path_ends(exclude=i)
            and all(task.delivery != loc for task in tasks)
            and self.token.can_stay(i, loc, t)
        ):
            path = Path(i, t, (loc,))
            self.token.commit(path)
            self._decide(Decision(i, path))
            return True
        d = self._plan_to_free_endpoint(t, i, loc, tasks, self.token.path_ends(exclude=i))
        if d is None:
            return False
        self._decide(d)
        return True

    def _assign(self, i: int, task: Task, d: Decision) -> None:
        self._holder[task.task_id] = i
        self._pickup_time[i] = d.pickup_time
        self._decide(d)

    def _decide(self, d: Decision) -> None:
        self._decisions.pop(d.agent_id, None)
        self._decisions[d.agent_id] = d

    def _save(self):
        return (
            dict(self.token.paths),
            dict(self._holder),
            dict(self._pickup_time),
            dict(self._decisions),
        )

    def _restore(self, saved) -> None:
        paths, holder, pickup_time, decisions = saved
        agents = set(paths) | set(self.token.paths)
        changed = [a for a in sorted(agents) if self.token.paths.get(a) is not paths.get(a)]
        for a in changed:  # release all first so restored paths never meet new ones
            self.token.release(a)
        for a in changed:
            if a in paths:
                self.token.commit(paths[a])
        self._holder, self._pickup_time, self._decisions = holder, pickup_time, decisions
