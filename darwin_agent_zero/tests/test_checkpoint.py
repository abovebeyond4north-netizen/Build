import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.checkpoint import CheckpointManager


class CheckpointTests(unittest.TestCase):
    def test_save_and_restore_latest_healthy_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "health_report.json").write_text(json.dumps({"passed": True, "summary": "healthy"}), encoding="utf-8")
            (workspace / "archive.jsonl").write_text("good\n", encoding="utf-8")
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()
            self.assertTrue(manifest.healthy)
            self.assertIn("archive.jsonl", manifest.copied_files)

            (workspace / "archive.jsonl").write_text("corrupt\n", encoding="utf-8")
            restored = manager.restore_latest()
            self.assertTrue(restored.restored)
            self.assertEqual((workspace / "archive.jsonl").read_text(encoding="utf-8"), "good\n")

    def test_refresh_updates_checkpoint_with_final_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "health_report.json").write_text(json.dumps({"passed": True, "summary": "healthy"}), encoding="utf-8")
            (workspace / "evolution_report.json").write_text(json.dumps({"phase": "preliminary"}), encoding="utf-8")
            (workspace / "provenance.json").write_text(json.dumps({"phase": "preliminary"}), encoding="utf-8")
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()

            (workspace / "evolution_report.json").write_text(json.dumps({"phase": "final"}), encoding="utf-8")
            (workspace / "provenance.json").write_text(json.dumps({"phase": "final"}), encoding="utf-8")
            refreshed = manager.refresh(manifest)

            checkpoint_path = Path(refreshed.path)
            self.assertIn("evolution_report.json", refreshed.copied_files)
            self.assertIn("provenance.json", refreshed.copied_files)
            self.assertEqual(json.loads((checkpoint_path / "evolution_report.json").read_text(encoding="utf-8"))["phase"], "final")
            self.assertEqual(json.loads((checkpoint_path / "provenance.json").read_text(encoding="utf-8"))["phase"], "final")

    def test_restore_without_checkpoint_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            restored = CheckpointManager(Path(tmp)).restore_latest()
            self.assertFalse(restored.restored)
            self.assertEqual(restored.reason, "no_checkpoint_found")


if __name__ == "__main__":
    unittest.main()
