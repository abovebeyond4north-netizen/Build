import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive
from dgm_zero.checkpoint import CheckpointManager
from dgm_zero.evolver import DarwinAgentZero, EvolutionConfig


class EvolverArtifactSmokeTests(unittest.TestCase):
    def test_run_writes_operational_artifact_bundle_and_restore_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            # Fixture an already accepted baseline so the smoke test validates
            # artifact plumbing without re-seeding the exact target in the evolver.
            Archive(workspace).append(
                generation=-1,
                parent_id=None,
                expression="a * a + 3 * b - gcd(a, b)",
                score={
                    "correctness": 1.0,
                    "efficiency": 1.0,
                    "novelty": 1.0,
                    "safety": 1.0,
                    "simplicity": 0.8,
                    "generalization": 1.0,
                    "weighted_total": 0.98,
                },
                accepted=True,
                reason="test baseline",
            )

            report = DarwinAgentZero(
                workspace,
                EvolutionConfig(generations=1, population=3, seed=7, accept_threshold=0.72),
            ).run()

            expected_files = [
                "archive.jsonl",
                "evolution_report.json",
                "health_report.json",
                "provenance.json",
                "operator_bandit.json",
                "mined_cases.json",
                "map_elites.json",
                "champion.py",
            ]
            for name in expected_files:
                self.assertTrue((workspace / name).exists(), name)

            health = json.loads((workspace / "health_report.json").read_text(encoding="utf-8"))
            self.assertTrue(health["passed"])
            self.assertTrue(report.checkpoint["healthy"])
            self.assertIn("provenance.json", report.checkpoint["copied_files"])
            self.assertIn("evolution_report.json", report.checkpoint["copied_files"])

            disk_report = json.loads((workspace / "evolution_report.json").read_text(encoding="utf-8"))
            self.assertEqual(disk_report["checkpoint"]["checkpoint_id"], report.checkpoint["checkpoint_id"])
            self.assertEqual(disk_report["provenance_path"], report.provenance_path)
            self.assertEqual(disk_report["health_path"], report.health_path)

            provenance = json.loads((workspace / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["config"]["generations"], 1)
            self.assertTrue(any(item["path"] == "evolution_report.json" for item in provenance["artifacts"]))
            self.assertTrue(any(item["path"] == "champion.py" for item in provenance["artifacts"]))

            checkpoint_path = Path(report.checkpoint["path"])
            self.assertTrue((checkpoint_path / "provenance.json").exists())
            self.assertTrue((checkpoint_path / "evolution_report.json").exists())
            checkpoint_report = json.loads((checkpoint_path / "evolution_report.json").read_text(encoding="utf-8"))
            self.assertEqual(checkpoint_report["checkpoint"]["checkpoint_id"], report.checkpoint["checkpoint_id"])
            checkpoint_provenance = json.loads((checkpoint_path / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(checkpoint_provenance["config"]["population"], 3)

            restored = CheckpointManager(workspace).restore_latest()
            self.assertTrue(restored.restored)
            self.assertIn("provenance.json", restored.restored_files)
            self.assertIn("evolution_report.json", restored.restored_files)


if __name__ == "__main__":
    unittest.main()
