import unittest

from dgm_zero.archive import ArchiveRecord
from dgm_zero.case_miner import CaseMiner, MinedCase, select_mining_expressions


def record(
    identifier: str,
    expression: str,
    total: float,
    generation: int,
    bucket: str,
) -> ArchiveRecord:
    return ArchiveRecord(
        id=identifier,
        generation=generation,
        parent_id=None,
        expression=expression,
        score={"weighted_total": total},
        accepted=True,
        reason="test",
        created_at=float(generation + 1),
        bucket=bucket,
    )


class CaseMinerSelectionTests(unittest.TestCase):
    def test_failure_rate_is_normalized(self):
        case = MinedCase(
            a=1,
            b=2,
            disagreement=2,
            failures=2,
            evaluated=4,
            expected=3,
        )
        self.assertEqual(case.failure_rate, 0.5)

    def test_selection_includes_recent_low_scoring_stepping_stones(self):
        records = [
            record(
                f"old-{index}",
                f"a + b + {index}",
                0.99 - index * 0.01,
                index,
                "old-bucket",
            )
            for index in range(6)
        ]
        records.extend(
            [
                record("recent-a", "a - b", 0.20, 6, "recent-a"),
                record("recent-b", "a * b", 0.10, 7, "recent-b"),
            ]
        )

        selected = select_mining_expressions(records, limit=4)

        self.assertEqual(len(selected), 4)
        self.assertIn("a * b", selected)
        self.assertEqual(len(selected), len(set(selected)))

    def test_selection_preserves_behavior_niches(self):
        records = [
            record("a1", "a + b", 0.95, 0, "add"),
            record("a2", "a + b + 1", 0.90, 1, "add"),
            record("m1", "a * b", 0.70, 2, "multiply"),
            record("s1", "a - b", 0.60, 3, "subtract"),
        ]

        selected = select_mining_expressions(records, limit=3)

        selected_buckets = {
            next(item.bucket for item in records if item.expression == expression)
            for expression in selected
        }
        self.assertGreaterEqual(len(selected_buckets), 2)

    def test_selection_limit_is_hard_bound(self):
        records = [
            record(str(index), f"a + {index}", 0.5, index, str(index))
            for index in range(20)
        ]
        self.assertEqual(len(select_mining_expressions(records, limit=5)), 5)
        self.assertEqual(select_mining_expressions(records, limit=0), [])

    def test_miner_rejects_invalid_bounds_and_limit(self):
        with self.assertRaisesRegex(ValueError, "must not exceed"):
            CaseMiner(5, -5)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            CaseMiner(-5, 5, limit=-1)
        with self.assertRaisesRegex(ValueError, "integer"):
            CaseMiner(False, 5)

    def test_zero_limit_skips_case_generation(self):
        miner = CaseMiner(-5, 5, limit=0)
        records = [
            record("one", "a + b", 0.5, 0, "one"),
            record("two", "a - b", 0.4, 1, "two"),
        ]
        self.assertEqual(miner.mine(records), [])


if __name__ == "__main__":
    unittest.main()
