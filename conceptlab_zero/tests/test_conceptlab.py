from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from conceptlab import (
    HIDDEN_PRINCIPLES,
    default_manifest,
    extract_numeric_pair,
    manifest_commitment,
    run_campaign,
    verify_campaign,
)


class ConceptLabP0Tests(unittest.TestCase):
    def test_surface_extractors_preserve_only_numeric_structure(self) -> None:
        observations = (
            [4, -2],
            {"opaque": 4, "other": -2},
            {"outer": [{"payload": 4}, {"payload": -2}], "tag": "x"},
            "alpha=4;omega=-2",
            {"meta": {"kind": "opaque"}, "payload": {"a": {"value": 4}, "b": {"value": -2}}},
            "<4|-2>",
        )
        for observation in observations:
            self.assertEqual(extract_numeric_pair(observation), (4, -2))

    def test_manifest_commitment_binds_hidden_principles(self) -> None:
        manifest = default_manifest()
        first = manifest_commitment(manifest)
        self.assertEqual(first, manifest_commitment(manifest))

        data = {
            **manifest.__dict__,
            "hidden_principles": tuple(
                list(manifest.hidden_principles[:-1])
                + [("hp_changed", "equal:0")]
            ),
        }
        changed = type(manifest)(**data)
        self.assertNotEqual(first, manifest_commitment(changed))

    def test_p0_campaign_recovers_rules_and_beats_controls(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p0-") as directory:
            workspace = Path(directory)
            result = run_campaign(workspace)

            self.assertTrue(result.all_p0_gates_passed)
            self.assertFalse(result.clg1_unlocked)
            self.assertEqual(result.claim, "p0_measurement_harness_passed")
            self.assertEqual(
                len(result.principle_results),
                len(HIDDEN_PRINCIPLES),
            )
            for principle in result.principle_results:
                self.assertTrue(principle.passed, principle.failure_reasons)
                self.assertTrue(principle.exact_recovery)
                self.assertEqual(principle.train_accuracy, 1.0)
                self.assertGreaterEqual(principle.d0_accuracy, 0.90)
                self.assertGreaterEqual(principle.d1_accuracy, 0.85)
                self.assertGreaterEqual(principle.d2_accuracy, 0.85)
                self.assertGreaterEqual(principle.d3_accuracy, 0.85)
                self.assertGreaterEqual(principle.d3_control_gain, 0.10)
                self.assertLessEqual(principle.false_transfer_rate, 0.10)
                self.assertGreaterEqual(principle.compression_ratio, 4.0)
                self.assertEqual(principle.leakage_collisions, 0)
                self.assertEqual(principle.isolation.capsule_only, principle.d3_accuracy)
                self.assertGreater(
                    principle.isolation.capsule_only,
                    max(
                        principle.isolation.irrelevant_capsule,
                        principle.isolation.matched_sham,
                    ),
                )

            verified = verify_campaign(workspace)
            self.assertEqual(
                verified.evidence_ledger_tip,
                result.evidence_ledger_tip,
            )
            self.assertEqual(
                verified.manifest_commitment,
                result.manifest_commitment,
            )

    def test_manifest_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p0-tamper-") as directory:
            workspace = Path(directory)
            run_campaign(workspace)
            manifest_path = workspace / "sealed_manifest.revealed.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["eval_cases"] += 1
            manifest_path.write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "commitment mismatch"):
                verify_campaign(workspace)


if __name__ == "__main__":
    unittest.main()
