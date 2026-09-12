import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path

from dgm_zero.cli import main
from dgm_zero.self_patch import sha256_file


class SelfPatchCliTests(unittest.TestCase):
    @staticmethod
    def make_repo(root: Path) -> Path:
        repo = root / "repo"
        package = repo / "src" / "dgm_zero"
        package.mkdir(parents=True)
        (repo / "pyproject.toml").write_text(
            "[project]\nname='fixture'\nversion='0.0.0'\n",
            encoding="utf-8",
        )
        (package / "oracle.py").write_text("VALUE = 1\n", encoding="utf-8")
        return repo

    def test_cli_rejects_immutable_evaluator_patch_without_running_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            oracle = repo / "src" / "dgm_zero" / "oracle.py"
            proposal_path = root / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "rationale": "attempt core evaluator edit",
                        "files": [
                            {
                                "relative_path": "src/dgm_zero/oracle.py",
                                "base_sha256": sha256_file(oracle),
                                "replacement_source": "VALUE = 2\n",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(
                    [
                        "evaluate-patch",
                        str(proposal_path),
                        "--repo-root",
                        str(repo),
                        "--workspace",
                        str(root / "workspace"),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("passed: False", stdout.getvalue())
            self.assertIn("not editable", stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
