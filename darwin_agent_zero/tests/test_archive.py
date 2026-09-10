import math
import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive


class ArchiveTests(unittest.TestCase):
    def test_append_copies_score_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            score = {"weighted_total": 0.8, "correctness": 1.0}
            record = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score=score,
                accepted=True,
                reason="test",
            )
            score["weighted_total"] = 0.0
            self.assertEqual(record.score["weighted_total"], 0.8)
            self.assertEqual(archive.records()[0].score["weighted_total"], 0.8)

    def test_non_finite_scores_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            for bad in (math.nan, math.inf, -math.inf):
                with self.subTest(bad=bad):
                    with self.assertRaisesRegex(ValueError, "finite"):
                        archive.append(
                            generation=0,
                            parent_id=None,
                            expression="a + b",
                            score={"weighted_total": bad},
                            accepted=False,
                            reason="invalid score",
                        )

    def test_weighted_total_must_be_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                archive.append(
                    generation=0,
                    parent_id=None,
                    expression="a + b",
                    score={"weighted_total": 1.1},
                    accepted=False,
                    reason="invalid score",
                )

    def test_invalid_text_and_boolean_generation_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            with self.assertRaisesRegex(ValueError, "expression"):
                archive.append(
                    generation=0,
                    parent_id=None,
                    expression="   ",
                    score={"weighted_total": 0.1},
                    accepted=False,
                    reason="invalid expression",
                )
            with self.assertRaisesRegex(ValueError, "generation"):
                archive.append(
                    generation=True,
                    parent_id=None,
                    expression="a + b",
                    score={"weighted_total": 0.1},
                    accepted=False,
                    reason="invalid generation",
                )

    def test_corrupt_jsonl_reports_exact_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.1},
                accepted=False,
                reason="valid",
            )
            with archive.path.open("a", encoding="utf-8") as handle:
                handle.write("{broken json\n")

            with self.assertRaisesRegex(ValueError, "line 2"):
                archive.records()

    def test_loaded_nan_score_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            archive.path.write_text(
                '{"id":"x","generation":0,"parent_id":null,'
                '"expression":"a+b","score":{"weighted_total":NaN},'
                '"accepted":true,"reason":"bad","created_at":1.0}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "finite"):
                archive.records()

    def test_champion_selects_highest_valid_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.4},
                accepted=True,
                reason="first",
            )
            best = archive.append(
                generation=1,
                parent_id=None,
                expression="a * b",
                score={"weighted_total": 0.9},
                accepted=True,
                reason="best",
            )
            self.assertEqual(archive.champion().id, best.id)


if __name__ == "__main__":
    unittest.main()
