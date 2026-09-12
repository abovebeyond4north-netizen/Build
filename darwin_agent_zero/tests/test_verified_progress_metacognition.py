import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive, ArchiveRecord
from dgm_zero.benchmark import BenchmarkConfig
from dgm_zero.metacognition import MetacognitiveMonitor, stagnation_score
from dgm_zero.oracle import EmpiricalGodelOracle


OLD_CONTEXT = "a" * 64
NEW_CONTEXT = "b" * 64


def record(
    identifier: str,
    total: float,
    *,
    context: str,
    delta: float | None,
    accepted: bool = True,
) -> ArchiveRecord:
    return ArchiveRecord(
        id=identifier,
        generation=0,
        parent_id=None,
        expression=f"a + {identifier!r}" if identifier.isdigit() else "a + b",
        score={"weighted_total": total},
        accepted=accepted,
        reason="test",
        created_at=1.0,
        evaluation_context=context,
        verified_delta=delta,
    )


class VerifiedProgressMetacognitionTests(unittest.TestCase):
    def test_confidence_uses_latest_context_not_old_easy_score(self):
        records = [
            record("old", 0.99, context=OLD_CONTEXT, delta=0.10),
            record("new", 0.60, context=NEW_CONTEXT, delta=0.0),
        ]
        state = MetacognitiveMonitor().assess(
            records,
            elite_cell_count=12,
            mined_case_count=3,
        )
        self.assertAlmostEqual(state.confidence, 0.60)
        self.assertAlmostEqual(state.uncertainty, 0.40)
        self.assertEqual(state.focus, "escape stagnation")

    def test_old_context_gain_does_not_hide_current_stall(self):
        records = [
            record("old", 0.90, context=OLD_CONTEXT, delta=0.20),
            record("new1", 0.70, context=NEW_CONTEXT, delta=0.0),
            record("new2", 0.70, context=NEW_CONTEXT, delta=-0.02),
        ]
        state = MetacognitiveMonitor().assess(
            records,
            elite_cell_count=12,
            mined_case_count=3,
        )
        self.assertEqual(state.stagnation, 1.0)
        self.assertEqual(state.focus, "escape stagnation")

    def test_meaningful_verified_gain_clears_stagnation(self):
        records = [
            record("new1", 0.70, context=NEW_CONTEXT, delta=0.01),
            record("new2", 0.78, context=NEW_CONTEXT, delta=0.06),
        ]
        state = MetacognitiveMonitor().assess(
            records,
            elite_cell_count=12,
            mined_case_count=3,
        )
        self.assertEqual(state.stagnation, 0.0)
        self.assertEqual(state.focus, "raise curriculum")

    def test_stagnation_score_uses_verified_delta_when_available(self):
        high = stagnation_score(
            [],
            recent_best=0.9,
            accepted_rate=1.0,
            verified_deltas=[0.0, -0.1],
        )
        low = stagnation_score(
            [],
            recent_best=0.9,
            accepted_rate=0.0,
            verified_deltas=[0.05],
        )
        self.assertEqual(high, 1.0)
        self.assertEqual(low, 0.0)

    def test_oracle_persists_same_context_verified_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            parent = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.5},
                accepted=True,
                reason="seed",
            )
            oracle = EmpiricalGodelOracle(
                archive,
                benchmark_config=BenchmarkConfig(
                    value_min=-10,
                    value_max=10,
                    train_count=4,
                    validation_count=4,
                    adversarial_scale=1,
                ),
            )
            parent_total = oracle.judge(parent.expression).score.weighted_total
            decision = oracle.judge(
                "a * a + 3 * b - gcd(a, b)",
                parent_total=parent_total,
            )
            child = archive.append(
                generation=1,
                parent_id=parent.id,
                expression=decision.expression,
                score=decision.score.as_dict(),
                accepted=decision.accepted,
                reason=decision.reason,
            )

            self.assertEqual(child.evaluation_context, oracle.evaluation_context)
            self.assertAlmostEqual(
                child.verified_delta,
                decision.score.weighted_total - parent_total,
            )
            self.assertAlmostEqual(child.verified_delta, decision.verified_delta)

    def test_verified_delta_without_context_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            with self.assertRaisesRegex(ValueError, "requires evaluation_context"):
                archive.append(
                    generation=0,
                    parent_id=None,
                    expression="a + b",
                    score={"weighted_total": 0.5},
                    accepted=True,
                    reason="invalid",
                    verified_delta=0.1,
                )


if __name__ == "__main__":
    unittest.main()
