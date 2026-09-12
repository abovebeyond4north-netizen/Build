import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.skill_library import SkillLibrary


class CertificationLedgerTests(unittest.TestCase):
    def test_new_certifications_form_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = SkillLibrary(Path(tmp))
            library.record_certification(
                capability="alpha",
                holdout_digest="a" * 64,
                finalist_digest="1" * 64,
                holdout_score=1.0,
                passed=True,
            )
            library.record_certification(
                capability="beta",
                holdout_digest="b" * 64,
                finalist_digest="2" * 64,
                holdout_score=0.75,
                passed=False,
            )
            rows = [
                json.loads(line)
                for line in library.certification_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 2)
            self.assertIsNone(rows[0]["previous_hash"])
            self.assertEqual(rows[1]["previous_hash"], rows[0]["record_hash"])
            self.assertTrue(library.certification_consumed("beta", "b" * 64))

    def test_tampered_certification_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = SkillLibrary(Path(tmp))
            library.record_certification(
                capability="alpha",
                holdout_digest="a" * 64,
                finalist_digest="1" * 64,
                holdout_score=1.0,
                passed=True,
            )
            row = json.loads(library.certification_path.read_text(encoding="utf-8"))
            row["holdout_score"] = 0.0
            library.certification_path.write_text(
                json.dumps(row, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "record hash mismatch"):
                library.certification_consumed("alpha", "a" * 64)

    def test_legacy_records_remain_readable_before_chained_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = SkillLibrary(Path(tmp))
            legacy = {
                "capability": "legacy",
                "holdout_digest": "c" * 64,
                "finalist_digest": "3" * 64,
                "holdout_score": 1.0,
                "passed": True,
                "evaluated_at": 1.0,
            }
            library.certification_path.write_text(
                json.dumps(legacy, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(library.certification_consumed("legacy", "c" * 64))
            library.record_certification(
                capability="new",
                holdout_digest="d" * 64,
                finalist_digest="4" * 64,
                holdout_score=1.0,
                passed=True,
            )
            self.assertTrue(library.certification_consumed("new", "d" * 64))


if __name__ == "__main__":
    unittest.main()
