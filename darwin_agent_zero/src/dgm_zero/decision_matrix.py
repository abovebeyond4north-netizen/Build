from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class DecisionWeights:
    """Non-negative weights for the empirical promotion gate."""

    correctness: float = 0.42
    efficiency: float = 0.14
    novelty: float = 0.14
    safety: float = 0.16
    simplicity: float = 0.08
    generalization: float = 0.06

    def normalized(self) -> "DecisionWeights":
        raw = self.as_dict()
        for name, value in raw.items():
            if not math.isfinite(value):
                raise ValueError(f"decision weight {name} must be finite")
            if value < 0.0:
                raise ValueError(f"decision weight {name} must be non-negative")

        total = sum(raw.values())
        if total <= 0.0:
            raise ValueError("decision weights must sum to a positive value")
        values = {key: value / total for key, value in raw.items()}
        return DecisionWeights(**values)

    def as_dict(self) -> dict[str, float]:
        return {
            "correctness": self.correctness,
            "efficiency": self.efficiency,
            "novelty": self.novelty,
            "safety": self.safety,
            "simplicity": self.simplicity,
            "generalization": self.generalization,
        }


@dataclass(frozen=True)
class CandidateScore:
    correctness: float
    efficiency: float
    novelty: float
    safety: float
    simplicity: float
    generalization: float
    weighted_total: float = field(init=False)

    def __post_init__(self) -> None:
        for name, value in self.as_dict(include_total=False).items():
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be finite and between 0 and 1, got {value!r}"
                )
        object.__setattr__(self, "weighted_total", 0.0)

    def as_dict(self, include_total: bool = True) -> dict[str, float]:
        data = {
            "correctness": self.correctness,
            "efficiency": self.efficiency,
            "novelty": self.novelty,
            "safety": self.safety,
            "simplicity": self.simplicity,
            "generalization": self.generalization,
        }
        if include_total:
            data["weighted_total"] = self.weighted_total
        return data

    def with_total(self, total: float) -> "CandidateScore":
        if not math.isfinite(total) or not 0.0 <= total <= 1.0:
            raise ValueError(
                f"weighted_total must be finite and between 0 and 1, got {total!r}"
            )
        clone = CandidateScore(
            correctness=self.correctness,
            efficiency=self.efficiency,
            novelty=self.novelty,
            safety=self.safety,
            simplicity=self.simplicity,
            generalization=self.generalization,
        )
        object.__setattr__(clone, "weighted_total", total)
        return clone


class DecisionMatrix:
    """Rank candidate self-modifications using bounded empirical factors."""

    MIN_SAFETY = 0.80
    MIN_CORRECTNESS = 0.70

    def __init__(
        self,
        weights: DecisionWeights | None = None,
        accept_threshold: float = 0.72,
    ) -> None:
        if not math.isfinite(accept_threshold) or not 0.0 <= accept_threshold <= 1.0:
            raise ValueError("accept_threshold must be finite and between 0 and 1")
        self.weights = (weights or DecisionWeights()).normalized()
        self.accept_threshold = accept_threshold

    @staticmethod
    def _bounded_factor(name: str, raw_value: float) -> float:
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"factor {name} must be finite")
        return max(0.0, min(1.0, value))

    def score(self, factors: Mapping[str, float]) -> CandidateScore:
        weights = self.weights.as_dict()
        safe_factors = {
            key: self._bounded_factor(key, factors.get(key, 0.0))
            for key in weights
        }
        total = sum(safe_factors[key] * weights[key] for key in weights)
        return CandidateScore(**safe_factors).with_total(total)

    def accepts(
        self,
        score: CandidateScore,
        parent_score: float | None = None,
    ) -> bool:
        if parent_score is not None:
            if not math.isfinite(parent_score) or not 0.0 <= parent_score <= 1.0:
                raise ValueError("parent_score must be finite and between 0 and 1")

        beats_threshold = score.weighted_total >= self.accept_threshold
        beats_parent = parent_score is None or score.weighted_total >= parent_score
        return (
            beats_threshold
            and beats_parent
            and score.safety >= self.MIN_SAFETY
            and score.correctness >= self.MIN_CORRECTNESS
        )
