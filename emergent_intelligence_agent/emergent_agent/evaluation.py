"""Evaluation and fitness scoring."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class EvalCase:
    prompt: str
    expected_keywords: tuple[str, ...]
    weight: float = 1.0


@dataclass(frozen=True)
class EvalResult:
    prompt: str
    score: float
    missing_keywords: tuple[str, ...]


class Evaluator:
    """Keyword-based evaluator for local deterministic tests."""

    def __init__(self, cases: list[EvalCase]) -> None:
        self.cases = cases

    def score_answer(self, answer: str, case: EvalCase) -> EvalResult:
        answer_l = answer.lower()
        missing = tuple(k for k in case.expected_keywords if k.lower() not in answer_l)
        if not case.expected_keywords:
            score = 1.0
        else:
            score = 1.0 - len(missing) / len(case.expected_keywords)
        return EvalResult(case.prompt, max(0.0, score) * case.weight, missing)

    def fitness(self, agent) -> float:
        results = []
        for case in self.cases:
            response = agent.answer(case.prompt)
            results.append(self.score_answer(response.answer, case).score)
        return mean(results) if results else 0.0
