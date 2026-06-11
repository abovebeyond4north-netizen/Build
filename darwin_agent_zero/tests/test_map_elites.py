import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive
from dgm_zero.map_elites import MAPElitesGrid, length_axis, score_axis


class MAPElitesTests(unittest.TestCase):
    def test_axes_bucket_values(self):
        self.assertEqual(length_axis("a + b"), "xs")
        self.assertEqual(score_axis(0.99, "C"), "C100")
        self.assertEqual(score_axis(0.10, "N"), "N0")

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
                score={"weighted_total": 0.1, "correctness": 0.0, "novelty": 1.0, "simplicity": 1.0},
                accepted=False,
                reason="bad",
            )
            grid = MAPElitesGrid().build(archive.records())
            self.assertEqual(len(grid.cells), 0)


if __name__ == "__main__":
    unittest.main()
