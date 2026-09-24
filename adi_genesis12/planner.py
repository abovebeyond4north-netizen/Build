from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import time
import tracemalloc


class PlanningBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class DeterministicHypothesisUniverse:
    """Finite deterministic experiment model.

    predictions[h][a] is the binary outcome predicted by hypothesis h for action a.
    The prior is over hypotheses and is normalized during construction.
    """

    hypothesis_ids: tuple[str, ...]
    action_ids: tuple[str, ...]
    predictions: tuple[tuple[int, ...], ...]
    prior: tuple[float, ...]

    def __post_init__(self) -> None:
        n = len(self.hypothesis_ids)
        m = len(self.action_ids)
        if n < 2:
            raise ValueError("at least two hypotheses are required")
        if m < 1:
            raise ValueError("at least one action is required")
        if len(self.predictions) != n or any(len(row) != m for row in self.predictions):
            raise ValueError("predictions must be an n_hypotheses x n_actions matrix")
        if any(outcome not in (0, 1) for row in self.predictions for outcome in row):
            raise ValueError("only deterministic binary outcomes 0/1 are supported")
        if len(self.prior) != n or any(weight < 0 for weight in self.prior):
            raise ValueError("prior must contain one non-negative weight per hypothesis")
        total = sum(self.prior)
        if total <= 0:
            raise ValueError("prior mass must be positive")
        if len(set(self.hypothesis_ids)) != n or len(set(self.action_ids)) != m:
            raise ValueError("hypothesis and action identifiers must be unique")
        normalized = tuple(weight / total for weight in self.prior)
        object.__setattr__(self, "prior", normalized)

    @property
    def full_mask(self) -> int:
        return (1 << len(self.hypothesis_ids)) - 1


@dataclass(frozen=True)
class PlannerStats:
    states_expanded: int
    cache_hits: int
    hypothesis_ops: int
    branch_evaluations: int
    cpu_ns: int
    peak_traced_bytes: int
    used_fallback: bool


@dataclass(frozen=True)
class PlanningDecision:
    action_index: int
    action_id: str
    expected_remaining_probes: float | None
    stats: PlannerStats


class DecisionAlignedPlanner:
    """Bayes-optimal expected-stopping-time planner for small deterministic worlds.

    V(S) = 0, |S| <= 1
    V(S) = min_a [1 + sum_o P(o|a,S) V(S_{a,o})]

    Exact dynamic programming is memoized by surviving-hypothesis bitmask. If the
    configured planning budget is exhausted, selection falls back to the frozen
    one-step entropy-greedy policy rather than changing any model/evaluator state.
    """

    def __init__(
        self,
        universe: DeterministicHypothesisUniverse,
        *,
        max_states: int = 100_000,
        max_hypothesis_ops: int = 10_000_000,
    ) -> None:
        if max_states < 1 or max_hypothesis_ops < 1:
            raise ValueError("planning budgets must be positive")
        self.universe = universe
        self.max_states = max_states
        self.max_hypothesis_ops = max_hypothesis_ops

    def _active_ids(self, mask: int) -> list[int]:
        return [i for i in range(len(self.universe.hypothesis_ids)) if mask & (1 << i)]

    def _split(self, mask: int, action: int, counters: dict[str, int]) -> tuple[int, int, float, float]:
        ids = self._active_ids(mask)
        total = sum(self.universe.prior[i] for i in ids)
        if total <= 0:
            raise ValueError("posterior state has zero prior mass")
        mask0 = 0
        mask1 = 0
        mass0 = 0.0
        mass1 = 0.0
        for i in ids:
            counters["hypothesis_ops"] += 1
            if counters["hypothesis_ops"] > self.max_hypothesis_ops:
                raise PlanningBudgetExceeded("hypothesis-operation budget exceeded")
            outcome = self.universe.predictions[i][action]
            if outcome == 0:
                mask0 |= 1 << i
                mass0 += self.universe.prior[i]
            else:
                mask1 |= 1 << i
                mass1 += self.universe.prior[i]
        return mask0, mask1, mass0 / total, mass1 / total

    def entropy_greedy_action(self, mask: int | None = None) -> int:
        mask = self.universe.full_mask if mask is None else mask
        counters = {"hypothesis_ops": 0}
        best: tuple[float, int] | None = None
        for action in range(len(self.universe.action_ids)):
            try:
                mask0, mask1, p0, p1 = self._split(mask, action, counters)
            except PlanningBudgetExceeded:
                ids = self._active_ids(mask)
                total = sum(self.universe.prior[i] for i in ids)
                masses = [0.0, 0.0]
                child_masks = [0, 0]
                for i in ids:
                    o = self.universe.predictions[i][action]
                    masses[o] += self.universe.prior[i]
                    child_masks[o] |= 1 << i
                mask0, mask1 = child_masks
                p0, p1 = masses[0] / total, masses[1] / total
            if not mask0 or not mask1:
                continue
            entropy = 0.0
            for p in (p0, p1):
                if p > 0:
                    entropy -= p * math.log2(p)
            candidate = (-entropy, action)
            if best is None or candidate < best:
                best = candidate
        if best is None:
            raise ValueError("no action can distinguish the remaining hypotheses")
        return best[1]

    def select_action(self, mask: int | None = None) -> PlanningDecision:
        mask = self.universe.full_mask if mask is None else mask
        if mask <= 0 or mask & ~self.universe.full_mask:
            raise ValueError("invalid posterior mask")
        if mask.bit_count() <= 1:
            raise ValueError("no intervention is needed for an identified hypothesis")

        counters = {
            "states_expanded": 0,
            "cache_hits": 0,
            "hypothesis_ops": 0,
            "branch_evaluations": 0,
        }
        memo: dict[int, tuple[float, int]] = {}

        def value(state: int) -> tuple[float, int]:
            if state.bit_count() <= 1:
                return 0.0, -1
            if state in memo:
                counters["cache_hits"] += 1
                return memo[state]
            counters["states_expanded"] += 1
            if counters["states_expanded"] > self.max_states:
                raise PlanningBudgetExceeded("posterior-state budget exceeded")

            best: tuple[float, int] | None = None
            for action in range(len(self.universe.action_ids)):
                mask0, mask1, p0, p1 = self._split(state, action, counters)
                if not mask0 or not mask1:
                    continue
                counters["branch_evaluations"] += 1
                v0, _ = value(mask0)
                v1, _ = value(mask1)
                expected = 1.0 + p0 * v0 + p1 * v1
                candidate = (expected, action)
                if best is None or candidate < best:
                    best = candidate
            if best is None:
                raise ValueError("remaining hypotheses are observationally indistinguishable")
            memo[state] = best
            return best

        tracing_before = tracemalloc.is_tracing()
        if not tracing_before:
            tracemalloc.start()
        start_current, _ = tracemalloc.get_traced_memory()
        start_cpu = time.process_time_ns()
        used_fallback = False
        expected: float | None
        try:
            expected, action = value(mask)
        except PlanningBudgetExceeded:
            used_fallback = True
            expected = None
            action = self.entropy_greedy_action(mask)
        cpu_ns = time.process_time_ns() - start_cpu
        _, peak = tracemalloc.get_traced_memory()
        peak_delta = max(0, peak - start_current)
        if not tracing_before:
            tracemalloc.stop()

        return PlanningDecision(
            action_index=action,
            action_id=self.universe.action_ids[action],
            expected_remaining_probes=expected,
            stats=PlannerStats(
                states_expanded=counters["states_expanded"],
                cache_hits=counters["cache_hits"],
                hypothesis_ops=counters["hypothesis_ops"],
                branch_evaluations=counters["branch_evaluations"],
                cpu_ns=cpu_ns,
                peak_traced_bytes=peak_delta,
                used_fallback=used_fallback,
            ),
        )


def policy_expected_cost(
    universe: DeterministicHypothesisUniverse,
    chooser,
    mask: int | None = None,
) -> float:
    """Expected probes to a singleton under a deterministic action chooser."""

    start = universe.full_mask if mask is None else mask

    @lru_cache(maxsize=None)
    def cost(state: int) -> float:
        if state.bit_count() <= 1:
            return 0.0
        action = chooser(state)
        ids = [i for i in range(len(universe.hypothesis_ids)) if state & (1 << i)]
        total = sum(universe.prior[i] for i in ids)
        child = [0, 0]
        mass = [0.0, 0.0]
        for i in ids:
            outcome = universe.predictions[i][action]
            child[outcome] |= 1 << i
            mass[outcome] += universe.prior[i]
        if not child[0] or not child[1]:
            raise ValueError("chooser selected a non-discriminating action")
        return 1.0 + (mass[0] / total) * cost(child[0]) + (mass[1] / total) * cost(child[1])

    return cost(start)
