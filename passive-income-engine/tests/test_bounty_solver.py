import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

import bounty_solver


def sign(secret, package):
    body = json.dumps(package, separators=(",", ":"), sort_keys=True).encode()
    signed = dict(package)
    signed["signature"] = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return signed


class BountySolverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_queue = bounty_solver.QUEUE_DIR
        self.old_secret = bounty_solver.QUEUE_SECRET
        bounty_solver.QUEUE_DIR = Path(self.tmp.name)
        bounty_solver.QUEUE_SECRET = "unit-test-queue-secret"

    def tearDown(self):
        bounty_solver.QUEUE_DIR = self.old_queue
        bounty_solver.QUEUE_SECRET = self.old_secret

    def package(self, payload):
        base = {
            "version": 1,
            "job_id": "opentask-test-job",
            "source": "opentask",
            "task_id": "task-1",
            "contract_id": "contract-1",
            "execution_mode": "pitch",
            "expected_task_updated_at": "2026-09-18T00:00:00Z",
            "title": "test",
            "payload": payload,
        }
        return sign(bounty_solver.QUEUE_SECRET, base)

    def test_json_format_round_trips(self):
        result = bounty_solver.solve_package(
            self.package({"kind": "json_format", "input_text": '{"b":2,"a":1}'})
        )
        self.assertTrue(result.ok)
        self.assertEqual(json.loads(result.output.decode()), {"a": 1, "b": 2})
        self.assertTrue(result.verification["round_trip_equal"])

    def test_csv_to_json(self):
        result = bounty_solver.solve_package(
            self.package({"kind": "csv_to_json", "input_text": "name,value\na,1\nb,2\n"})
        )
        self.assertTrue(result.ok)
        self.assertEqual(json.loads(result.output.decode())[1]["name"], "b")
        self.assertEqual(result.verification["row_count"], 2)

    def test_json_to_csv(self):
        result = bounty_solver.solve_package(
            self.package(
                {
                    "kind": "json_to_csv",
                    "input_text": '[{"name":"a","value":1},{"name":"b","value":2}]',
                }
            )
        )
        self.assertTrue(result.ok)
        text = result.output.decode()
        self.assertIn("name,value", text)
        self.assertIn("b,2", text)

    def test_unsigned_package_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "signature"):
            bounty_solver.solve_package(
                {
                    "version": 1,
                    "job_id": "x",
                    "payload": {"kind": "sha256", "input_text": "hello"},
                }
            )

    def test_unknown_handler_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported safe solver"):
            bounty_solver.solve_package(
                self.package({"kind": "python", "input_text": "print('no')"})
            )

    def test_queue_run_writes_signed_hash_verified_manifest(self):
        inbox = bounty_solver.QUEUE_DIR / "inbox"
        inbox.mkdir(parents=True)
        package = self.package({"kind": "sha256", "input_text": "hello"})
        (inbox / "opentask-test-job.json").write_text(json.dumps(package))

        results = bounty_solver.run_once()
        self.assertEqual(len(results), 1)
        manifest_path = bounty_solver.QUEUE_DIR / "outbox" / "opentask-test-job.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertTrue(manifest["ok"])
        self.assertEqual(manifest["contract_id"], "contract-1")
        signature = manifest.pop("signature")
        expected = hmac.new(
            bounty_solver.QUEUE_SECRET.encode(),
            json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(signature, expected)
        artifact = bounty_solver.QUEUE_DIR / manifest["artifact"]["relative_path"]
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), manifest["artifact"]["sha256"])


if __name__ == "__main__":
    unittest.main()
