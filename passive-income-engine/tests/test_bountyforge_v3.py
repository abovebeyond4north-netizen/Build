import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

from bountyforge import (
    BountyForge,
    Config,
    _queue_signature,
    safe_repo_verification_spec,
)


class BountyForgeV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.config = Config(
            database_path=str(root / "engine.db"),
            auto_solve=True,
            auto_repo_verify=True,
            auto_deliver=False,
            reconcile_payments=False,
            queue_dir=str(root / "bounty-queue"),
            queue_secret="queue-secret",
            repo_verify_dir=str(root / "repo-verify"),
            repo_verify_secret="repo-secret",
            opentask_token="",
        )
        self.forge = BountyForge(self.config)

    def test_repo_spec_requires_public_repo_full_sha_and_named_check(self):
        sha = "a" * 40
        spec = safe_repo_verification_spec(
            "Verify Python tests",
            f"Run python unittest for https://github.com/example/project at commit {sha}.",
        )
        self.assertIsNotNone(spec)
        self.assertEqual(spec["repo_url"], "https://github.com/example/project")
        self.assertEqual(spec["commit_sha"], sha)
        self.assertEqual(spec["checks"], ["python_unittest"])

        self.assertIsNone(
            safe_repo_verification_spec(
                "Verify branch",
                "Run tests for https://github.com/example/project on main.",
            )
        )
        self.assertIsNone(
            safe_repo_verification_spec(
                "Look at repo",
                f"https://github.com/example/project {sha}",
            )
        )
        self.assertIsNone(
            safe_repo_verification_spec(
                "Verify tests",
                f"Run unittest for https://gitlab.com/example/project at {sha}",
            )
        )

    def test_queue_repo_verification_writes_signed_fetch_request(self):
        sha = "b" * 40
        queued = self.forge.queue_repo_verification(
            task_id="task-1",
            title="Verify repository tests",
            description=(
                f"Run python unittest and compileall for "
                f"https://github.com/example/project at commit {sha}."
            ),
            execution_mode="pitch",
            expected_task_updated_at="2026-09-18T00:00:00Z",
            contract_id="contract-1",
        )
        self.assertTrue(queued)

        files = list((Path(self.config.repo_verify_dir) / "fetch-inbox").glob("*.json"))
        self.assertEqual(len(files), 1)
        package = json.loads(files[0].read_text())
        self.assertEqual(package["task_id"], "task-1")
        self.assertEqual(package["contract_id"], "contract-1")
        self.assertEqual(package["repo_url"], "https://github.com/example/project")
        self.assertEqual(package["commit_sha"], sha)
        self.assertEqual(package["checks"], ["python_unittest", "python_compileall"])
        self.assertEqual(
            package["signature"],
            _queue_signature(self.config.repo_verify_secret, package),
        )

        second = self.forge.queue_repo_verification(
            task_id="task-1",
            title="Verify repository tests",
            description=(
                f"Run python unittest and compileall for "
                f"https://github.com/example/project at commit {sha}."
            ),
            execution_mode="pitch",
            expected_task_updated_at="2026-09-18T00:00:00Z",
            contract_id="contract-1",
        )
        self.assertFalse(second)

    def test_signed_repo_result_becomes_hash_verified_delivery_manifest(self):
        repo_root = Path(self.config.repo_verify_dir)
        (repo_root / "outbox").mkdir(parents=True)
        result = {
            "version": 1,
            "job_id": "opentask-repo-job",
            "source": "opentask",
            "task_id": "task-2",
            "contract_id": "contract-2",
            "execution_mode": "pitch",
            "expected_task_updated_at": "2026-09-18T00:00:00Z",
            "title": "Verify tests",
            "passed": True,
            "tree": {"files": 3, "bytes": 120},
            "checks": [
                {
                    "check": "python_unittest",
                    "argv": ["python", "-m", "unittest", "discover", "-v"],
                    "returncode": 0,
                    "duration_ms": 25,
                    "output_sha256": "c" * 64,
                    "output": "OK\n",
                    "output_truncated": False,
                    "passed": True,
                }
            ],
        }
        result["signature"] = _queue_signature(self.config.repo_verify_secret, result)
        (repo_root / "outbox" / "opentask-repo-job.json").write_text(json.dumps(result))

        counts = self.forge.collect_repo_verification_results()
        self.assertEqual(counts["verified"], 1)
        self.assertEqual(counts["translated"], 1)

        queue_root = Path(self.config.queue_dir)
        manifest_path = queue_root / "outbox" / "opentask-repo-job.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertTrue(manifest["ok"])
        self.assertEqual(manifest["handler"], "repository_verification")
        self.assertEqual(manifest["contract_id"], "contract-2")
        self.assertEqual(
            manifest["signature"],
            _queue_signature(self.config.queue_secret, manifest),
        )

        artifact = queue_root / manifest["artifact"]["relative_path"]
        data = artifact.read_bytes()
        self.assertEqual(len(data), manifest["artifact"]["size_bytes"])
        self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["artifact"]["sha256"])
        report = json.loads(data)
        self.assertTrue(report["passed"])
        self.assertEqual(report["checks"][0]["output"], "OK\n")

    def test_tampered_repo_result_is_quarantined(self):
        repo_root = Path(self.config.repo_verify_dir)
        (repo_root / "outbox").mkdir(parents=True)
        result = {
            "version": 1,
            "job_id": "tampered",
            "source": "opentask",
            "task_id": "task-3",
            "contract_id": "contract-3",
            "passed": True,
            "tree": {},
            "checks": [],
        }
        result["signature"] = _queue_signature(self.config.repo_verify_secret, result)
        result["passed"] = False
        (repo_root / "outbox" / "tampered.json").write_text(json.dumps(result))

        counts = self.forge.collect_repo_verification_results()
        self.assertEqual(counts["quarantined"], 1)
        self.assertTrue((repo_root / "quarantine" / "tampered.json").exists())


if __name__ == "__main__":
    unittest.main()
