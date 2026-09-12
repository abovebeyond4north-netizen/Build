import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive


SCORE = {
    "correctness": 1.0,
    "efficiency": 1.0,
    "novelty": 0.5,
    "safety": 1.0,
    "simplicity": 0.9,
    "generalization": 1.0,
    "weighted_total": 0.95,
}


class ArchiveIntegrityTests(unittest.TestCase):
    def test_new_records_form_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            first = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score=SCORE,
                accepted=True,
                reason="first",
            )
            second = archive.append(
                generation=1,
                parent_id=first.id,
                expression="a * a + b",
                score=SCORE,
                accepted=True,
                reason="second",
            )
            self.assertIsNone(first.previous_hash)
            self.assertEqual(second.previous_hash, first.record_hash)
            self.assertEqual(len(second.record_hash or ""), 64)
            self.assertEqual(len(archive.records()), 2)

    def test_modified_chained_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score=SCORE,
                accepted=True,
                reason="verified",
            )
            row = json.loads(archive.path.read_text(encoding="utf-8"))
            row["accepted"] = False
            archive.path.write_text(
                json.dumps(row, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "record hash mismatch"):
                archive.records()

    def test_legacy_records_can_precede_new_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            legacy = {
                "id": "legacy-record",
                "generation": -1,
                "parent_id": None,
                "expression": "a + b",
                "score": SCORE,
                "accepted": True,
                "reason": "legacy",
                "created_at": 1.0,
                "signature": None,
                "bucket": None,
            }
            archive.path.write_text(
                json.dumps(legacy, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            new = archive.append(
                generation=0,
                parent_id="legacy-record",
                expression="a * a + b",
                score=SCORE,
                accepted=True,
                reason="new",
            )
            self.assertIsNone(new.previous_hash)
            self.assertEqual(len(archive.records()), 2)


if __name__ == "__main__":
    unittest.main()
