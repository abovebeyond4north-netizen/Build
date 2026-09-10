import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.checkpoint import CheckpointManager


class CheckpointTests(unittest.TestCase):
    @staticmethod
    def write_health(workspace: Path, passed: bool, summary: str) -> None:
        (workspace / "health_report.json").write_text(
            json.dumps({"passed": passed, "summary": summary}),
            encoding="utf-8",
        )

    def test_save_and_restore_latest_healthy_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.write_health(workspace, True, "healthy")
            (workspace / "archive.jsonl").write_text("good\n", encoding="utf-8")
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()
            self.assertTrue(manifest.healthy)
            self.assertIn("archive.jsonl", manifest.copied_files)

            (workspace / "archive.jsonl").write_text("corrupt\n", encoding="utf-8")
            restored = manager.restore_latest()
            self.assertTrue(restored.restored)
            self.assertEqual(
                (workspace / "archive.jsonl").read_text(encoding="utf-8"),
                "good\n",
            )

    def test_unhealthy_newer_checkpoint_does_not_hide_last_known_good(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manager = CheckpointManager(workspace)

            self.write_health(workspace, True, "healthy")
            (workspace / "archive.jsonl").write_text("known-good\n", encoding="utf-8")
            healthy = manager.save_if_healthy()
            self.assertTrue(healthy.healthy)

            self.write_health(workspace, False, "regression")
            (workspace / "archive.jsonl").write_text("bad-run\n", encoding="utf-8")
            unhealthy = manager.save_if_healthy()
            self.assertFalse(unhealthy.healthy)
            self.assertEqual(manager.latest_manifest().checkpoint_id, unhealthy.checkpoint_id)

            restored = manager.restore_latest()
            self.assertTrue(restored.restored)
            self.assertEqual(restored.checkpoint_id, healthy.checkpoint_id)
            self.assertEqual(
                (workspace / "archive.jsonl").read_text(encoding="utf-8"),
                "known-good\n",
            )

    def test_corrupt_healthy_pointer_falls_back_to_checkpoint_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.write_health(workspace, True, "healthy")
            (workspace / "archive.jsonl").write_text("good\n", encoding="utf-8")
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()

            (manager.root / "latest_healthy.json").write_text("{broken", encoding="utf-8")
            found = manager.latest_healthy_manifest()
            self.assertIsNotNone(found)
            self.assertEqual(found.checkpoint_id, manifest.checkpoint_id)

    def test_restore_ignores_manifest_paths_outside_snapshot_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            self.write_health(workspace, True, "healthy")
            (workspace / "archive.jsonl").write_text("good\n", encoding="utf-8")
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()

            outside_source = manager.root / "outside.txt"
            outside_source.write_text("should-not-escape\n", encoding="utf-8")
            outside_destination = workspace.parent / "outside.txt"
            outside_destination.write_text("untouched\n", encoding="utf-8")

            pointer_path = manager.root / "latest_healthy.json"
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            pointer["copied_files"] = ["../outside.txt", "archive.jsonl"]
            pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

            restored = manager.restore_latest()
            self.assertTrue(restored.restored)
            self.assertEqual(restored.checkpoint_id, manifest.checkpoint_id)
            self.assertEqual(outside_destination.read_text(encoding="utf-8"), "untouched\n")
            self.assertNotIn("../outside.txt", restored.restored_files)

    def test_refresh_updates_checkpoint_with_final_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.write_health(workspace, True, "healthy")
            (workspace / "evolution_report.json").write_text(
                json.dumps({"phase": "preliminary"}),
                encoding="utf-8",
            )
            (workspace / "provenance.json").write_text(
                json.dumps({"phase": "preliminary"}),
                encoding="utf-8",
            )
            manager = CheckpointManager(workspace)
            manifest = manager.save_if_healthy()

            (workspace / "evolution_report.json").write_text(
                json.dumps({"phase": "final"}),
                encoding="utf-8",
            )
            (workspace / "provenance.json").write_text(
                json.dumps({"phase": "final"}),
                encoding="utf-8",
            )
            refreshed = manager.refresh(manifest)

            checkpoint_path = Path(refreshed.path)
            self.assertIn("evolution_report.json", refreshed.copied_files)
            self.assertIn("provenance.json", refreshed.copied_files)
            self.assertEqual(
                json.loads(
                    (checkpoint_path / "evolution_report.json").read_text(
                        encoding="utf-8"
                    )
                )["phase"],
                "final",
            )
            self.assertEqual(
                json.loads(
                    (checkpoint_path / "provenance.json").read_text(encoding="utf-8")
                )["phase"],
                "final",
            )

    def test_restore_without_checkpoint_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            restored = CheckpointManager(Path(tmp)).restore_latest()
            self.assertFalse(restored.restored)
            self.assertEqual(restored.reason, "no_checkpoint_found")


if __name__ == "__main__":
    unittest.main()
