import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.checkpoint import CheckpointManager


class CheckpointIntegrityTests(unittest.TestCase):
    @staticmethod
    def write_health(workspace: Path) -> None:
        (workspace / "health_report.json").write_text(
            json.dumps({"passed": True, "summary": "healthy"}),
            encoding="utf-8",
        )

    def test_checkpoint_records_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.write_health(workspace)
            (workspace / "archive.jsonl").write_text("known-good\n", encoding="utf-8")
            manifest = CheckpointManager(workspace).save_if_healthy()
            self.assertIn("archive.jsonl", manifest.file_hashes)
            self.assertEqual(len(manifest.file_hashes["archive.jsonl"]), 64)

    def test_corrupt_checkpoint_fails_before_restoring_any_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.write_health(workspace)
            (workspace / "archive.jsonl").write_text("known-good\n", encoding="utf-8")
            (workspace / "knowledge.jsonl").write_text("memory-good\n", encoding="utf-8")
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()

            checkpoint = Path(manifest.path)
            (checkpoint / "archive.jsonl").write_text("tampered\n", encoding="utf-8")
            (workspace / "archive.jsonl").write_text("current-archive\n", encoding="utf-8")
            (workspace / "knowledge.jsonl").write_text("current-memory\n", encoding="utf-8")

            restored = manager.restore_latest()
            self.assertFalse(restored.restored)
            self.assertEqual(restored.reason, "checkpoint_integrity_failed")
            self.assertEqual(restored.restored_files, [])
            self.assertEqual(
                (workspace / "archive.jsonl").read_text(encoding="utf-8"),
                "current-archive\n",
            )
            self.assertEqual(
                (workspace / "knowledge.jsonl").read_text(encoding="utf-8"),
                "current-memory\n",
            )

    def test_legacy_manifest_without_hashes_remains_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.write_health(workspace)
            (workspace / "archive.jsonl").write_text("known-good\n", encoding="utf-8")
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()

            for path in (
                Path(manifest.path) / "manifest.json",
                manager.root / "latest.json",
                manager.root / "latest_healthy.json",
            ):
                data = json.loads(path.read_text(encoding="utf-8"))
                data.pop("file_hashes", None)
                path.write_text(json.dumps(data), encoding="utf-8")

            (workspace / "archive.jsonl").write_text("changed\n", encoding="utf-8")
            restored = manager.restore_latest()
            self.assertTrue(restored.restored)
            self.assertEqual(
                (workspace / "archive.jsonl").read_text(encoding="utf-8"),
                "known-good\n",
            )


if __name__ == "__main__":
    unittest.main()
