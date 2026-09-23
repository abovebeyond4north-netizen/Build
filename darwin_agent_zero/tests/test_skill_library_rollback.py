import tempfile
import unittest
from pathlib import Path

from dgm_zero.capability_model import (
    AcquisitionReport,
    AcquisitionTask,
    CapabilityCase,
    CapabilitySpec,
    SkillCandidate,
)
from dgm_zero.skill_library import SkillLibrary


def spec():
    return CapabilitySpec(
        "identity",
        "return input",
        "solve",
        (
            CapabilityCase("t", "train", (1,), 1),
            CapabilityCase("v", "validation", (2,), 2),
            CapabilityCase("h", "holdout", (3,), 3),
        ),
    )


def report(tmp: Path, digest: str, score: float = 1.0):
    return AcquisitionReport(
        capability="identity",
        description="return input",
        holdout_digest=digest,
        status="promoted",
        promoted=True,
        baseline_digest="0" * 64,
        baseline_score=0.0,
        finalist_digest="f" * 64,
        final_score=score,
        train_score=score,
        validation_score=score,
        holdout_score=score,
        candidates_generated=1,
        candidates_trained=1,
        candidates_validated=1,
        holdout_evaluations=1,
        tasks=(AcquisitionTask("test", "test", 1.0),),
        installed_path=None,
        report_path=str(tmp / "report.json"),
        created_at=1.0,
    )


class SkillLibraryRollbackTests(unittest.TestCase):
    def test_promotion_records_parent_and_rollback_restores_exact_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            library = SkillLibrary(workspace)
            first = SkillCandidate("def solve(x0):\n    return x0\n", "first")
            second = SkillCandidate("def solve(x0):\n    return x0 + 1\n", "second")

            library.promote(spec(), first, report(workspace, "1" * 64))
            library.promote(
                spec(),
                second,
                report(workspace, "2" * 64),
                evidence_record_hash="a" * 64,
            )

            _, current_manifest = library.current("identity")
            self.assertEqual(current_manifest["digest"], second.digest)
            self.assertEqual(current_manifest["parent_digest"], first.digest)
            self.assertEqual(current_manifest["evidence_record_hash"], "a" * 64)

            restored = library.rollback_current("identity")
            source, manifest = library.current("identity")
            self.assertEqual(source, first.source)
            self.assertEqual(manifest["digest"], first.digest)
            self.assertEqual(restored["rolled_back_from"], second.digest)
            self.assertEqual(restored["rollback_reason"], "verified_parent_dependency")

    def test_rollback_fails_if_predecessor_artifact_was_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            library = SkillLibrary(workspace)
            first = SkillCandidate("def solve(x0):\n    return x0\n", "first")
            second = SkillCandidate("def solve(x0):\n    return x0 + 1\n", "second")
            library.promote(spec(), first, report(workspace, "1" * 64))
            library.promote(spec(), second, report(workspace, "2" * 64))

            predecessor = (
                workspace
                / "capabilities"
                / "identity"
                / "versions"
                / f"{first.digest}.py"
            )
            predecessor.write_text(
                "def solve(x0):\n    return 'tampered'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                library.rollback_current("identity")

    def test_first_version_has_no_guessed_rollback_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            library = SkillLibrary(workspace)
            first = SkillCandidate("def solve(x0):\n    return x0\n", "first")
            library.promote(spec(), first, report(workspace, "1" * 64))
            with self.assertRaisesRegex(ValueError, "no verified predecessor"):
                library.rollback_current("identity")


if __name__ == "__main__":
    unittest.main()
