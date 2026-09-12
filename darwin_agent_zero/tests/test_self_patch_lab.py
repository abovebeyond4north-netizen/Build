import json
import sys
import tempfile
import unittest
from pathlib import Path

from dgm_zero.self_patch import (
    PatchFile,
    PatchProposal,
    RepositoryPatchLab,
    normalize_relative_path,
    sha256_file,
)


class SelfPatchLabTests(unittest.TestCase):
    @staticmethod
    def make_repo(root: Path) -> Path:
        repo = root / "repo"
        package = repo / "src" / "dgm_zero"
        package.mkdir(parents=True)
        (repo / "pyproject.toml").write_text(
            "[project]\nname='fixture'\nversion='0.0.0'\n",
            encoding="utf-8",
        )
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "mutation.py").write_text("VALUE = 1\n", encoding="utf-8")
        (package / "search_schedule.py").write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )
        (package / "meta_learning.py").write_text("VALUE = 1\n", encoding="utf-8")
        (package / "self_instruction.py").write_text("VALUE = 1\n", encoding="utf-8")
        return repo

    def test_valid_patch_is_evaluated_only_in_ephemeral_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            workspace = root / "workspace"
            original = repo / "src" / "dgm_zero" / "mutation.py"
            proposal = PatchProposal.for_replacements(
                repo,
                rationale="raise fixture value",
                replacements={"src/dgm_zero/mutation.py": "VALUE = 2\n"},
            )
            lab = RepositoryPatchLab(repo, workspace)
            report = lab.evaluate(
                proposal,
                gate_commands=(
                    (
                        "import replacement",
                        (
                            sys.executable,
                            "-c",
                            (
                                "import dgm_zero.mutation as m; "
                                "assert m.VALUE == 2"
                            ),
                        ),
                    ),
                ),
            )
            self.assertTrue(report.passed)
            self.assertEqual(original.read_text(encoding="utf-8"), "VALUE = 1\n")
            self.assertTrue(Path(report.report_path).is_file())
            payload = json.loads(Path(report.report_path).read_text(encoding="utf-8"))
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["proposal_digest"], proposal.digest)
            self.assertFalse(hasattr(lab, "apply"))

    def test_disallowed_core_or_test_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            forbidden = repo / "src" / "dgm_zero" / "oracle.py"
            forbidden.write_text("VALUE = 1\n", encoding="utf-8")
            proposal = PatchProposal(
                rationale="attempt evaluator change",
                files=(
                    PatchFile(
                        "src/dgm_zero/oracle.py",
                        sha256_file(forbidden),
                        "VALUE = 2\n",
                    ),
                ),
            )
            report = RepositoryPatchLab(repo, root / "workspace").validate(proposal)
            self.assertFalse(report.passed)
            self.assertTrue(any("not editable" in reason for reason in report.reasons))

    def test_stale_base_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            proposal = PatchProposal(
                rationale="stale proposal",
                files=(
                    PatchFile(
                        "src/dgm_zero/mutation.py",
                        "0" * 64,
                        "VALUE = 2\n",
                    ),
                ),
            )
            report = RepositoryPatchLab(repo, root / "workspace").validate(proposal)
            self.assertFalse(report.passed)
            self.assertTrue(any("base hash mismatch" in reason for reason in report.reasons))

    def test_path_traversal_and_backslashes_are_rejected(self):
        for value in ("../mutation.py", "src\\dgm_zero\\mutation.py", "/tmp/x.py"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "patch path|unsafe"):
                    normalize_relative_path(value)

    def test_forbidden_import_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            proposal = PatchProposal.for_replacements(
                repo,
                rationale="unsafe network/process access",
                replacements={
                    "src/dgm_zero/mutation.py": "import os\nVALUE = 2\n"
                },
            )
            report = RepositoryPatchLab(repo, root / "workspace").evaluate(
                proposal,
                gate_commands=(("never", (sys.executable, "-c", "raise SystemExit(0)")),),
            )
            self.assertFalse(report.passed)
            self.assertEqual(report.gates, ())
            self.assertTrue(any("forbidden import: os" in reason for reason in report.validation.reasons))

    def test_failed_gate_stops_later_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            proposal = PatchProposal.for_replacements(
                repo,
                rationale="valid source but failing verification",
                replacements={"src/dgm_zero/mutation.py": "VALUE = 2\n"},
            )
            report = RepositoryPatchLab(repo, root / "workspace").evaluate(
                proposal,
                gate_commands=(
                    ("fail", (sys.executable, "-c", "raise SystemExit(7)")),
                    ("must not run", (sys.executable, "-c", "raise SystemExit(0)")),
                ),
            )
            self.assertFalse(report.passed)
            self.assertEqual(len(report.gates), 1)
            self.assertEqual(report.gates[0].returncode, 7)

    def test_duplicate_paths_and_payload_limits_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            target = repo / "src" / "dgm_zero" / "mutation.py"
            digest = sha256_file(target)
            item = PatchFile(
                "src/dgm_zero/mutation.py",
                digest,
                "VALUE = 2\n",
            )
            proposal = PatchProposal(
                rationale="duplicate",
                files=(item, item),
            )
            lab = RepositoryPatchLab(
                repo,
                root / "workspace",
                max_total_bytes=8,
            )
            report = lab.validate(proposal)
            self.assertFalse(report.passed)
            self.assertTrue(any("duplicate" in reason for reason in report.reasons))
            self.assertTrue(any("payload exceeds" in reason for reason in report.reasons))

    def test_proposal_digest_is_content_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            first = PatchProposal.for_replacements(
                repo,
                rationale="same",
                replacements={"src/dgm_zero/mutation.py": "VALUE = 2\n"},
            )
            second = PatchProposal.for_replacements(
                repo,
                rationale="same",
                replacements={"src/dgm_zero/mutation.py": "VALUE = 2\n"},
            )
            self.assertEqual(first.digest, second.digest)


if __name__ == "__main__":
    unittest.main()
