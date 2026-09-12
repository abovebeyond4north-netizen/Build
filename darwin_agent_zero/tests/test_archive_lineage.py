import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive


class ArchiveLineageTests(unittest.TestCase):
    def test_repeated_evaluations_receive_unique_persisted_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            kwargs = {
                "generation": 0,
                "parent_id": None,
                "expression": "a + b",
                "score": {"weighted_total": 0.5},
                "accepted": True,
                "reason": "repeatable evaluation",
            }
            first = archive.append(**kwargs)
            second = archive.append(**kwargs)
            self.assertNotEqual(first.id, second.id)
            self.assertEqual(len({record.id for record in archive.records()}), 2)

    def test_direct_make_id_remains_deterministic_without_nonce(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            self.assertEqual(
                archive.make_id("a + b", 0),
                archive.make_id("a + b", 0),
            )
            self.assertNotEqual(
                archive.make_id("a + b", 0, 1),
                archive.make_id("a + b", 0, 2),
            )


if __name__ == "__main__":
    unittest.main()
