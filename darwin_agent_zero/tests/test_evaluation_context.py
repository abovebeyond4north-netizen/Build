import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive
from dgm_zero.benchmark import BenchmarkCase, BenchmarkConfig
from dgm_zero.oracle import EmpiricalGodelOracle


class EvaluationContextTests(unittest.TestCase):
    @staticmethod
    def small_config(value_max: int = 10) -> BenchmarkConfig:
        return BenchmarkConfig(
            value_min=-value_max,
            value_max=value_max,
            train_count=4,
            validation_count=4,
            adversarial_scale=1,
        )

    def test_context_is_stable_for_same_frozen_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            first = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(),
            )
            second = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(),
            )
            self.assertEqual(first.evaluation_context, second.evaluation_context)
            self.assertEqual(len(first.evaluation_context), 64)

    def test_context_changes_with_benchmark_or_mined_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            base = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(10),
            )
            harder = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(20),
            )
            mined = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(10),
                mined_cases=(BenchmarkCase("mined", 2, 3, 12),),
            )
            self.assertNotEqual(base.evaluation_context, harder.evaluation_context)
            self.assertNotEqual(base.evaluation_context, mined.evaluation_context)

    def test_new_archive_records_capture_oracle_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            oracle = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(),
            )
            decision = oracle.judge("a + b")
            record = archive.append(
                generation=0,
                parent_id=None,
                expression=decision.expression,
                score=decision.score.as_dict(),
                accepted=decision.accepted,
                reason=decision.reason,
            )
            self.assertEqual(record.evaluation_context, oracle.evaluation_context)
            self.assertEqual(record.evaluation_context, decision.evaluation_context)
            self.assertEqual(
                archive.records()[0].evaluation_context,
                oracle.evaluation_context,
            )

    def test_context_handoff_does_not_label_unrelated_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            oracle = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(),
            )
            oracle.judge("a + b")
            unrelated = archive.append(
                generation=0,
                parent_id=None,
                expression="a * a + b",
                score={"weighted_total": 0.5},
                accepted=True,
                reason="direct append",
            )
            self.assertIsNone(unrelated.evaluation_context)

    def test_oracle_novelty_reference_stays_frozen_after_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.5},
                accepted=True,
                reason="seed",
            )
            oracle = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(),
            )
            before = archive.novelty(
                "a * a + 3 * b",
                reference_records=oracle.reference_records,
            )
            frozen_context = oracle.evaluation_context

            archive.append(
                generation=1,
                parent_id=None,
                expression="a * a + b",
                score={"weighted_total": 0.6},
                accepted=True,
                reason="later",
            )

            after = archive.novelty(
                "a * a + 3 * b",
                reference_records=oracle.reference_records,
            )
            self.assertEqual(before, after)
            self.assertEqual(frozen_context, oracle.context_digest())

            refreshed = EmpiricalGodelOracle(
                archive,
                benchmark_config=self.small_config(),
            )
            self.assertNotEqual(frozen_context, refreshed.evaluation_context)

    def test_invalid_explicit_context_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                archive.append(
                    generation=0,
                    parent_id=None,
                    expression="a + b",
                    score={"weighted_total": 0.5},
                    accepted=True,
                    reason="bad context",
                    evaluation_context="not-a-digest",
                )


if __name__ == "__main__":
    unittest.main()
