from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class BanditArm:
    name: str
    pulls: int = 0
    reward_sum: float = 0.0

    @property
    def mean_reward(self) -> float:
        return self.reward_sum / self.pulls if self.pulls else 0.0


class UCBOperatorBandit:
    """Upper-confidence-bound selector for mutation operators.

    Operators that have produced reward are reused, but uncertain operators still
    get exploration chances. This gives the evolver a simple online meta-optimizer.
    """

    def __init__(self, arms: Iterable[str], exploration: float = 1.4) -> None:
        self.exploration = exploration
        self.arms: dict[str, BanditArm] = {name: BanditArm(name) for name in arms}

    def choose(self) -> str:
        for arm in self.arms.values():
            if arm.pulls == 0:
                return arm.name
        total = max(1, sum(arm.pulls for arm in self.arms.values()))
        return max(
            self.arms.values(),
            key=lambda arm: arm.mean_reward + self.exploration * math.sqrt(math.log(total + 1) / arm.pulls),
        ).name

    def update(self, name: str, reward: float) -> None:
        if name not in self.arms:
            self.arms[name] = BanditArm(name)
        arm = self.arms[name]
        arm.pulls += 1
        arm.reward_sum += clamp01(reward)

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {
            name: {
                "pulls": float(arm.pulls),
                "reward_sum": arm.reward_sum,
                "mean_reward": arm.mean_reward,
            }
            for name, arm in sorted(self.arms.items())
        }


class HasScore(Protocol):
    score: dict[str, float]


def pareto_front(records: Iterable[HasScore], keys: tuple[str, ...] = ("correctness", "novelty", "simplicity", "generalization")) -> list[HasScore]:
    """Return non-dominated records for multi-objective selection."""

    items = list(records)
    front: list[HasScore] = []
    for candidate in items:
        dominated = False
        for challenger in items:
            if challenger is candidate:
                continue
            if dominates(challenger.score, candidate.score, keys):
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    return front


def dominates(a: dict[str, float], b: dict[str, float], keys: tuple[str, ...]) -> bool:
    better_or_equal = all(a.get(key, 0.0) >= b.get(key, 0.0) for key in keys)
    strictly_better = any(a.get(key, 0.0) > b.get(key, 0.0) for key in keys)
    return better_or_equal and strictly_better


def uncertainty_score(score: dict[str, float]) -> float:
    """Estimate where more exploration is useful."""

    correctness_gap = 1.0 - score.get("correctness", 0.0)
    generalization_gap = 1.0 - score.get("generalization", 0.0)
    novelty_gap = 1.0 - score.get("novelty", 0.0)
    return clamp01(0.45 * correctness_gap + 0.40 * generalization_gap + 0.15 * novelty_gap)


def regret(parent_score: float | None, child_score: float) -> float:
    """Counterfactual regret: how much worse the child was than its parent."""

    if parent_score is None:
        return 0.0
    return max(0.0, parent_score - child_score)


def disagreement(values: Iterable[object]) -> float:
    """Normalized ensemble disagreement over candidate outputs."""

    outputs = list(values)
    if len(outputs) <= 1:
        return 0.0
    unique = len(set(outputs))
    return clamp01((unique - 1) / (len(outputs) - 1))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
