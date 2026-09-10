"""Evaluation and fitness scoring."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EvalCase:
    prompt: str
    expected_keywords: tuple[str, ...]
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        weight = float(self.weight)
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("weight must be finite and non-negative")

        unique: list[str] = []
        seen: set[str] = set()
        for keyword in self.expected_keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError("expected keywords must be non-empty strings")
            normalized = keyword.strip()
            key = normalized.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(normalized)
        object.__setattr__(self, "expected_keywords", tuple(unique))
        object.__setattr__(self, "weight", weight)


@dataclass(frozen=True)
class EvalResult:
    prompt: str
    score: float
    missing_keywords: tuple[str, ...]


class Evaluator:
    """Keyword-based evaluator for local deterministic tests."""

    def __init__(self, cases: list[EvalCase]) -> None:
        self.cases = list(cases)

    def score_answer(self, answer: str, case: EvalCase) -> EvalResult:
        if not isinstance(answer, str):
            raise TypeError("answer must be a string")
        answer_l = answer.casefold()
        missing = tuple(
            keyword
            for keyword in case.expected_keywords
            if keyword.casefold() not in answer_l
        )
        if not case.expected_keywords:
            score = 1.0
        else:
            score = 1.0 - len(missing) / len(case.expected_keywords)
        return EvalResult(case.prompt, max(0.0, min(1.0, score)), missing)

    def fitness(self, agent) -> float:
        weighted_total = 0.0
        total_weight = 0.0
        for case in self.cases:
            if case.weight == 0.0:
                continue
            response = agent.answer(case.prompt)
            result = self.score_answer(response.answer, case)
            weighted_total += result.score * case.weight
            total_weight += case.weight
        return weighted_total / total_weight if total_weight else 0.0
