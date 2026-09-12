from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
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
    get exploration chances. The bandit can persist across runs so learning does
    not reset every time the CLI is invoked. A search-context key can also be
    attached so evidence from an older curriculum/evaluator regime is discounted
    rather than treated as equally current forever.
    """

    def __init__(self, arms: Iterable[str], exploration: float = 1.4) -> None:
        if not math.isfinite(exploration) or exploration <= 0:
            raise ValueError("exploration must be finite and positive")
        names = list(arms)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("bandit arm names must be non-empty strings")
        if len(set(names)) != len(names):
            raise ValueError("bandit arm names must be unique")
        self.exploration = float(exploration)
        self.context: str | None = None
        self.arms: dict[str, BanditArm] = {name: BanditArm(name) for name in names}

    def choose(self) -> str:
        if not self.arms:
            raise ValueError("bandit has no operators to choose from")
        for arm in self.arms.values():
            if arm.pulls == 0:
                return arm.name
        total = max(1, sum(arm.pulls for arm in self.arms.values()))
        return max(
            self.arms.values(),
            key=lambda arm: arm.mean_reward
            + self.exploration * math.sqrt(math.log(total + 1) / arm.pulls),
        ).name

    def update(self, name: str, reward: float) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("bandit arm name must be a non-empty string")
        if not math.isfinite(float(reward)):
            raise ValueError("bandit reward must be finite")
        if name not in self.arms:
            self.arms[name] = BanditArm(name)
        arm = self.arms[name]
        arm.pulls += 1
        arm.reward_sum += clamp01(reward)

    def adapt_context(self, context: str, retention: float = 0.5) -> bool:
        """Move operator evidence into a new search regime with bounded decay.

        The first context assignment upgrades legacy state without discarding it.
        Re-entering the same context is a no-op. When the context changes, pulls
        and rewards are discounted together, preserving approximate means while
        restoring exploration pressure. Tiny histories can decay fully back to an
        unseen arm, which is preferable to one stale observation becoming sticky.
        """
        if not isinstance(context, str) or not context.strip():
            raise ValueError("bandit context must be a non-empty string")
        if (
            isinstance(retention, bool)
            or not isinstance(retention, (int, float))
            or not math.isfinite(float(retention))
            or not 0.0 <= float(retention) <= 1.0
        ):
            raise ValueError("bandit context retention must be finite and between 0 and 1")
        normalized = context.strip()
        if self.context is None:
            self.context = normalized
            return False
        if self.context == normalized:
            return False

        keep = float(retention)
        for arm in self.arms.values():
            previous_pulls = arm.pulls
            previous_reward = arm.reward_sum
            retained_pulls = int(math.floor(previous_pulls * keep + 1e-12))
            if retained_pulls <= 0:
                arm.pulls = 0
                arm.reward_sum = 0.0
                continue
            retained_reward = previous_reward * keep
            arm.pulls = retained_pulls
            arm.reward_sum = max(0.0, min(float(retained_pulls), retained_reward))
        self.context = normalized
        return True

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {
            name: {
                "pulls": float(arm.pulls),
                "reward_sum": arm.reward_sum,
                "mean_reward": arm.mean_reward,
            }
            for name, arm in sorted(self.arms.items())
        }

    def save(self, path: Path) -> None:
        payload = {
            "exploration": self.exploration,
            "context": self.context,
            "arms": {name: asdict(arm) for name, arm in self.arms.items()},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(path)

    @classmethod
    def load(cls, path: Path, arms: Iterable[str], exploration: float = 1.4) -> "UCBOperatorBandit":
        configured_arms = list(arms)
        bandit = cls(configured_arms, exploration=exploration)
        if not path.exists():
            return bandit
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid operator bandit state: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("invalid operator bandit state: expected object")

        stored_exploration = data.get("exploration", exploration)
        try:
            stored_exploration = float(stored_exploration)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid operator bandit exploration") from exc
        if not math.isfinite(stored_exploration) or stored_exploration <= 0:
            raise ValueError("invalid operator bandit exploration")
        bandit.exploration = stored_exploration

        stored_context = data.get("context")
        if stored_context is not None:
            if not isinstance(stored_context, str) or not stored_context.strip():
                raise ValueError("invalid operator bandit context")
            bandit.context = stored_context.strip()

        stored_arms = data.get("arms", {})
        if not isinstance(stored_arms, dict):
            raise ValueError("invalid operator bandit arms")
        for name, arm_data in stored_arms.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(arm_data, dict):
                raise ValueError("invalid operator bandit arm")
            pulls_raw = arm_data.get("pulls", 0)
            if isinstance(pulls_raw, bool) or not isinstance(pulls_raw, int) or pulls_raw < 0:
                raise ValueError(f"invalid pull count for operator {name}")
            reward_raw = arm_data.get("reward_sum", 0.0)
            try:
                reward_sum = float(reward_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid reward sum for operator {name}") from exc
            if (
                not math.isfinite(reward_sum)
                or reward_sum < 0.0
                or reward_sum > pulls_raw + 1e-12
            ):
                raise ValueError(f"invalid reward sum for operator {name}")
            bandit.arms[name] = BanditArm(
                name=name,
                pulls=pulls_raw,
                reward_sum=reward_sum,
            )
        for name in configured_arms:
            bandit.arms.setdefault(name, BanditArm(name))
        return bandit


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


def improvement_reward(parent_score: float | None, child_score: float) -> float:
    """Reward mutation operators only for verified progress over their parent.

    The previous bandit update mixed absolute child quality with regret, which
    could still assign a positive reward to a regressing child. For recursive
    self-improvement, operator credit should reflect actual measured progress.
    Seed candidates have no parent, so their verified absolute score is used.
    """

    child = clamp01(child_score)
    if parent_score is None:
        return child
    parent = clamp01(parent_score)
    return clamp01(max(0.0, child - parent))


def disagreement(values: Iterable[object]) -> float:
    """Normalized ensemble disagreement over candidate outputs."""

    outputs = list(values)
    if len(outputs) <= 1:
        return 0.0
    unique = len(set(outputs))
    return clamp01((unique - 1) / (len(outputs) - 1))


def clamp01(value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("value must be finite")
    return max(0.0, min(1.0, numeric))
