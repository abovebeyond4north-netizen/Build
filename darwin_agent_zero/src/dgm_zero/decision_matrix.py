from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class DecisionWeights:
    """Weights for the empirical Gödel gate.

    The score is intentionally multi-factor. A tool is not accepted just because
    it passes tests; it must also remain simple, safe, reasonably efficient, and
    interesting enough to preserve evolutionary diversity.
    """

    correctness: float = 0.42
    efficiency: float = 0.14
    novelty: float = 0.14
    safety: float = 0.16
    simplicity: float = 0.08
    generalization: float = 0.06

    def normalized(self) -> "DecisionWeights":
        total = sum(self.as_dict().values())
        if total <= 0:
            raise ValueError("decision weights must sum to a positive value")
        values = {key: value / total for key, value in self.as_dict().items()}
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
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1, got {value!r}")
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
    """Ranks candidate self-modifications using bounded intelligence factors."""

    def __init__(self, weights: DecisionWeights | None = None, accept_threshold: float = 0.72) -> None:
        self.weights = (weights or DecisionWeights()).normalized()
        self.accept_threshold = accept_threshold

    def score(self, factors: Mapping[str, float]) -> CandidateScore:
        weights = self.weights.as_dict()
        safe_factors = {key: max(0.0, min(1.0, float(factors.get(key, 0.0)))) for key in weights}
        total = sum(safe_factors[key] * weights[key] for key in weights)
        return CandidateScore(**safe_factors).with_total(total)

    def accepts(self, score: CandidateScore, parent_score: float | None = None) -> bool:
        beats_threshold = score.weighted_total >= self.accept_threshold
        beats_parent = parent_score is None or score.weighted_total >= parent_score
        return beats_threshold and beats_parent and score.safety >= 0.80 and score.correctness >= 0.70
