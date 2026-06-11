from __future__ import annotations

from dataclasses import dataclass

from .archive import Archive
from .benchmark import BenchmarkCase, BenchmarkConfig, BenchmarkResult, SplitBenchmarkResult, evaluate_expression, evaluate_expression_split
from .decision_matrix import CandidateScore, DecisionMatrix
from .safety import SafetyReport, scan_source


@dataclass(frozen=True)
class OracleDecision:
    expression: str
    accepted: bool
    reason: str
    benchmark: SplitBenchmarkResult
    safety: SafetyReport
    score: CandidateScore
    mined: BenchmarkResult | None = None


class EmpiricalGodelOracle:
    """Empirical proof gate for candidate tool changes."""

    def __init__(
        self,
        archive: Archive,
        matrix: DecisionMatrix | None = None,
        benchmark_config: BenchmarkConfig | None = None,
        mined_cases: tuple[BenchmarkCase, ...] = (),
    ) -> None:
        self.archive = archive
        self.matrix = matrix or DecisionMatrix()
        self.benchmark_config = benchmark_config or BenchmarkConfig()
        self.mined_cases = mined_cases

    def judge(self, expression: str, parent_total: float | None = None) -> OracleDecision:
        source = f"def solve(a, b):\n    return {expression}\n"
        safety = scan_source(source)
        benchmark = evaluate_expression_split(expression, self.benchmark_config)
        mined = evaluate_expression(expression, list(self.mined_cases)) if self.mined_cases else None
        mined_correctness = mined.correctness if mined else 1.0
        simplicity = max(0.0, min(1.0, 1.0 - (len(expression) / 240.0)))
        validation_bonus = 1.0 if benchmark.validation.correctness >= 0.95 else benchmark.validation.correctness * 0.85
        adversarial_bonus = 1.0 if benchmark.adversarial.correctness >= 0.95 else benchmark.adversarial.correctness * 0.75
        mined_bonus = 1.0 if mined_correctness >= 0.95 else mined_correctness * 0.70
        generalization = min(benchmark.train.correctness, validation_bonus, adversarial_bonus, mined_bonus)
        correctness = min(benchmark.correctness, mined_correctness)
        score = self.matrix.score(
            {
                "correctness": correctness,
                "efficiency": benchmark.efficiency,
                "novelty": self.archive.novelty(expression),
                "safety": safety.score,
                "simplicity": simplicity,
                "generalization": generalization,
            }
        )
        accepted = safety.passed and self.matrix.accepts(score, parent_score=parent_total)
        if accepted:
            reason = "accepted by empirical proof gate"
        elif not safety.passed:
            reason = "; ".join(safety.reasons)
        elif mined and mined.errors:
            reason = "; ".join(mined.errors[:2])
        elif benchmark.errors:
            reason = "; ".join(benchmark.errors[:2])
        else:
            reason = "decision score below gate threshold"
        return OracleDecision(expression, accepted, reason, benchmark, safety, score, mined)
