from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .archive import Archive, ArchiveRecord
from .benchmark import (
    BenchmarkCase,
    BenchmarkConfig,
    BenchmarkResult,
    SplitBenchmarkResult,
    evaluate_expression,
    evaluate_expression_split,
)
from .decision_matrix import CandidateScore, DecisionMatrix
from .safety import SafetyReport, scan_source


EVALUATION_PROTOCOL_VERSION = 2


@dataclass(frozen=True)
class OracleDecision:
    expression: str
    accepted: bool
    reason: str
    benchmark: SplitBenchmarkResult
    safety: SafetyReport
    score: CandidateScore
    evaluation_context: str
    verified_delta: float | None = None
    mined: BenchmarkResult | None = None


class EmpiricalGodelOracle:
    """Empirical proof gate with a frozen, fingerprinted evaluation context."""

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
        self.reference_records: tuple[ArchiveRecord, ...] = tuple(archive.records())
        self.evaluation_context = self.context_digest()

    def context_digest(self) -> str:
        """Fingerprint all bounded evidence that materially affects scoring."""
        novelty_reference = [
            {
                "id": record.id,
                "expression": record.expression,
                "signature": record.signature,
                "record_hash": record.record_hash,
            }
            for record in self.reference_records[-50:]
        ]
        payload = {
            "evaluation_protocol_version": EVALUATION_PROTOCOL_VERSION,
            "benchmark_config": asdict(self.benchmark_config),
            "mined_cases": [asdict(case) for case in self.mined_cases],
            "decision_matrix": {
                "accept_threshold": self.matrix.accept_threshold,
                "weights": self.matrix.weights.as_dict(),
                "min_safety": self.matrix.MIN_SAFETY,
                "min_correctness": self.matrix.MIN_CORRECTNESS,
            },
            "novelty_reference": novelty_reference,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def judge(self, expression: str, parent_total: float | None = None) -> OracleDecision:
        source = f"def solve(a, b):\n    return {expression}\n"
        safety = scan_source(source)
        benchmark = evaluate_expression_split(expression, self.benchmark_config)
        mined = (
            evaluate_expression(expression, list(self.mined_cases))
            if self.mined_cases
            else None
        )
        mined_correctness = mined.correctness if mined else 1.0
        simplicity = max(0.0, min(1.0, 1.0 - (len(expression) / 240.0)))
        validation_bonus = (
            1.0
            if benchmark.validation.correctness >= 0.95
            else benchmark.validation.correctness * 0.85
        )
        adversarial_bonus = (
            1.0
            if benchmark.adversarial.correctness >= 0.95
            else benchmark.adversarial.correctness * 0.75
        )
        mined_bonus = (
            1.0 if mined_correctness >= 0.95 else mined_correctness * 0.70
        )
        generalization = min(
            benchmark.train.correctness,
            validation_bonus,
            adversarial_bonus,
            mined_bonus,
        )
        correctness = min(benchmark.correctness, mined_correctness)
        score = self.matrix.score(
            {
                "correctness": correctness,
                "efficiency": benchmark.efficiency,
                "novelty": self.archive.novelty(
                    expression,
                    reference_records=self.reference_records,
                ),
                "safety": safety.score,
                "simplicity": simplicity,
                "generalization": generalization,
            }
        )
        accepted = safety.passed and self.matrix.accepts(
            score,
            parent_score=parent_total,
        )
        verified_delta = (
            None
            if parent_total is None
            else score.weighted_total - parent_total
        )
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

        self.archive.stage_evaluation_context(
            expression,
            self.evaluation_context,
            verified_delta,
        )
        return OracleDecision(
            expression=expression,
            accepted=accepted,
            reason=reason,
            benchmark=benchmark,
            safety=safety,
            score=score,
            evaluation_context=self.evaluation_context,
            verified_delta=verified_delta,
            mined=mined,
        )
