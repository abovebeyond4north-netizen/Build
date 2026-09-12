import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive


class ArchiveParentageTests(unittest.TestCase):
    def test_rejects_orphaned_parent_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            with self.assertRaisesRegex(ValueError, "parent_id does not reference"):
                archive.append(
                    generation=1,
                    parent_id="missing-parent",
                    expression="a + b",
                    score={"weighted_total": 0.5},
                    accepted=True,
                    reason="invalid lineage",
                )

    def test_accepts_existing_parent_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            parent = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.5},
                accepted=True,
                reason="parent",
            )
            child = archive.append(
                generation=1,
                parent_id=parent.id,
                expression="a * a + b",
                score={"weighted_total": 0.6},
                accepted=True,
                reason="child",
            )
            self.assertEqual(child.parent_id, parent.id)


if __name__ == "__main__":
    unittest.main()
