import unittest

from dgm_zero.archive import ArchiveRecord
from dgm_zero.case_miner import CaseMiner


def record(record_id: str, expression: str, score: float) -> ArchiveRecord:
    return ArchiveRecord(
        id=record_id,
        generation=0,
        parent_id=None,
        expression=expression,
        score={"weighted_total": score},
        accepted=True,
        reason="test",
        created_at=1.0,
    )


class CaseMinerFailureTests(unittest.TestCase):
    def test_consensus_wrong_predictions_are_mined(self):
        records = [
            record("a", "0", 0.9),
            record("b", "0 + 0", 0.8),
        ]
        mined = CaseMiner(-3, 3, limit=12).mine(records)
        self.assertTrue(mined)
        self.assertTrue(any(case.expected != 0 for case in mined))

    def test_consensus_correct_predictions_do_not_create_false_pressure(self):
        records = [
            record("a", "a * a + 3 * b - gcd(a, b)", 1.0),
            record("b", "(a * a) + (3 * b) - gcd(a, b)", 0.99),
        ]
        mined = CaseMiner(-3, 3, limit=12).mine(records)
        self.assertEqual(mined, [])

    def test_higher_failure_regions_are_prioritized(self):
        records = [
            record("a", "0", 0.95),
            record("b", "a * a", 0.90),
            record("c", "a * a + 3 * b", 0.85),
        ]
        mined = CaseMiner(-4, 4, limit=4).mine(records)
        self.assertEqual(len(mined), 4)
        self.assertTrue(all(case.name.startswith("mined_") for case in mined))


if __name__ == "__main__":
    unittest.main()
