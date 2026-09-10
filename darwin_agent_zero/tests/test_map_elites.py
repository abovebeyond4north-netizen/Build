import math
import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive, ArchiveRecord
from dgm_zero.map_elites import MAPElitesGrid, fitness, length_axis, score_axis


class MAPElitesTests(unittest.TestCase):
    def test_axes_bucket_values(self):
        self.assertEqual(length_axis("a + b"), "xs")
        self.assertEqual(score_axis(0.99, "C"), "C100")
        self.assertEqual(score_axis(0.10, "N"), "N0")
        self.assertEqual(score_axis(math.nan, "N"), "N0")

    def test_grid_keeps_accepted_elite(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            record = archive.append(
                generation=0,
                parent_id=None,
                expression="a * a + 3 * b - gcd(a, b)",
                score={
                    "correctness": 1.0,
                    "efficiency": 1.0,
                    "novelty": 1.0,
                    "safety": 1.0,
                    "simplicity": 0.9,
                    "generalization": 1.0,
                    "weighted_total": 0.99,
                },
                accepted=True,
                reason="test",
            )
            grid = MAPElitesGrid().build(archive.records())
            self.assertEqual(len(grid.cells), 1)
            self.assertEqual(grid.elite_expressions(), [record.expression])

    def test_grid_ignores_rejected_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={
                    "weighted_total": 0.1,
                    "correctness": 0.0,
                    "novelty": 1.0,
                    "simplicity": 1.0,
                },
                accepted=False,
                reason="bad",
            )
            grid = MAPElitesGrid().build(archive.records())
            self.assertEqual(len(grid.cells), 0)

    def test_non_finite_candidate_fitness_cannot_enter_grid(self):
        record = ArchiveRecord(
            id="nan",
            generation=0,
            parent_id=None,
            expression="a + b",
            score={
                "weighted_total": math.nan,
                "correctness": math.nan,
                "novelty": 0.5,
                "simplicity": 0.5,
            },
            accepted=True,
            reason="corrupt",
            created_at=0.0,
            signature="sig",
            bucket="short:mixed",
        )
        grid = MAPElitesGrid()
        self.assertFalse(grid.add(record))
        self.assertEqual(grid.cells, {})

    def test_grid_copies_score_mapping_from_archive_record(self):
        score = {
            "weighted_total": 0.8,
            "correctness": 0.8,
            "novelty": 0.5,
            "simplicity": 0.5,
        }
        record = ArchiveRecord(
            id="record",
            generation=0,
            parent_id=None,
            expression="a + b",
            score=score,
            accepted=True,
            reason="test",
            created_at=0.0,
            signature="sig",
            bucket="short:mixed",
        )
        grid = MAPElitesGrid()
        self.assertTrue(grid.add(record))
        cell = next(iter(grid.cells.values()))
        score["weighted_total"] = 0.0
        self.assertEqual(cell.score["weighted_total"], 0.8)
        self.assertEqual(fitness(cell), 0.8)

    def test_negative_elite_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            MAPElitesGrid().elite_expressions(-1)

    def test_write_is_atomic_and_creates_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "map_elites.json"
            MAPElitesGrid().write(path)
            self.assertTrue(path.exists())
            self.assertFalse(path.with_name(".map_elites.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
