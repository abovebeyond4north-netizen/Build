from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from conceptlab import Principle, RuleInducer, run_campaign
from p1 import run_p1
from p2 import (
    D4_ACCURACY_GATE,
    D4_CONTROL_GAIN_GATE,
    RESTART_GATE,
    RETENTION_GATE,
    REVISION_ACCURACY_GATE,
    ConceptStore,
    build_ambiguous_revision_support,
    build_revision_batch,
    revise_capsule,
    run_p2,
    verify_p2,
)


class ConceptLabP2Tests(unittest.TestCase):
    def test_contradiction_revision_changes_only_target_concept(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p2-revise-") as directory:
            store = ConceptStore(Path(directory) / "store")

            stable_support = build_ambiguous_revision_support()
            stable_capsule, _ = RuleInducer().fit(stable_support)
            store.save_capsule("stable", stable_capsule, reason="control")
            _, stable_digest_before = store.load_capsule("stable")

            initial, score = RuleInducer().fit(build_ambiguous_revision_support())
            self.assertEqual(score, 1.0)
            self.assertEqual(initial.signature, "distance_ge:4")
            store.save_capsule("target", initial, reason="ambiguous")

            revision = revise_capsule(
                store=store,
                concept_id="target",
                evidence=build_revision_batch(),
            )
            revised, _ = store.load_capsule("target")
            _, stable_digest_after = store.load_capsule("stable")

            self.assertTrue(revision.accepted)
            self.assertGreater(revision.contradiction_count, 0)
            self.assertEqual(revised.signature, "distance_ge:6")
            self.assertEqual(stable_digest_before, stable_digest_after)

    def test_p2_composition_revision_and_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="conceptlab-p2-") as directory:
            workspace = Path(directory)
            p0 = run_campaign(workspace)
            self.assertTrue(p0.all_p0_gates_passed)
            p1 = run_p1(workspace)
            self.assertTrue(p1.all_p1_gates_passed)

            p2 = run_p2(workspace)
            self.assertTrue(p2.all_p2_gates_passed)
            self.assertFalse(p2.clg1_unlocked)
            self.assertEqual(
                p2.claim,
                "p2_composition_revision_persistence_passed",
            )
            self.assertEqual(p2.composition_operator, "xor")
            self.assertGreaterEqual(p2.d4_accuracy, D4_ACCURACY_GATE)
            self.assertGreaterEqual(
                p2.d4_control_gain,
                D4_CONTROL_GAIN_GATE,
            )
            self.assertEqual(p2.composition_leakage_collisions, 0)

            self.assertEqual(
                p2.revision.before_signature,
                "distance_ge:4",
            )
            self.assertEqual(
                p2.revision.after_signature,
                "distance_ge:6",
            )
            self.assertTrue(p2.revision.accepted)
            self.assertGreaterEqual(
                p2.revised_holdout_accuracy,
                REVISION_ACCURACY_GATE,
            )
            self.assertGreaterEqual(
                p2.unaffected_before_accuracy,
                RETENTION_GATE,
            )
            self.assertGreaterEqual(
                p2.unaffected_after_accuracy,
                RETENTION_GATE,
            )
            self.assertTrue(p2.unaffected_digest_unchanged)

            self.assertGreaterEqual(
                p2.restart_primitive_a_accuracy,
                RESTART_GATE,
            )
            self.assertGreaterEqual(
                p2.restart_revised_accuracy,
                RESTART_GATE,
            )
            self.assertGreaterEqual(
                p2.restart_composite_accuracy,
                RESTART_GATE,
            )
            self.assertEqual(p2.persisted_episode_artifacts, 0)

            verified = verify_p2(workspace)
            self.assertEqual(
                verified.evidence_ledger_tip,
                p2.evidence_ledger_tip,
            )
            self.assertEqual(
                verified.p1_evidence_ledger_tip,
                p1.evidence_ledger_tip,
            )


if __name__ == "__main__":
    unittest.main()
