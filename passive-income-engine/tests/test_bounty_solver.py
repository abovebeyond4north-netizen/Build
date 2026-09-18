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

    def test_jsonl_to_json_and_back(self):
        to_json = bounty_solver.solve_package(
            self.package({"kind": "jsonl_to_json", "input_text": '{"a":1}\n{"a":2}\n'})
        )
        self.assertEqual(json.loads(to_json.output.decode()), [{"a": 1}, {"a": 2}])

        to_jsonl = bounty_solver.solve_package(
            self.package({"kind": "json_to_jsonl", "input_text": '[{"a":1},{"a":2}]'})
        )
        self.assertEqual(
            [json.loads(line) for line in to_jsonl.output.decode().splitlines()],
            [{"a": 1}, {"a": 2}],
        )
        self.assertTrue(to_jsonl.verification["round_trip_equal"])

    def test_csv_deduplicate(self):
        result = bounty_solver.solve_package(
            self.package(
                {
                    "kind": "csv_deduplicate",
                    "input_text": "id,name\n1,A\n1,A\n2,B\n",
                    "keys": ["id"],
                }
            )
        )
        self.assertEqual(result.verification["removed_rows"], 1)
        self.assertIn("2,B", result.output.decode())

    def test_csv_to_markdown(self):
        result = bounty_solver.solve_package(
            self.package({"kind": "csv_to_markdown", "input_text": "name,value\na,1\n"})
        )
        self.assertIn("| name | value |", result.output.decode())
        self.assertEqual(result.verification["rows"], 1)

    def test_sort_unique_lines(self):
        result = bounty_solver.solve_package(
            self.package(
                {
                    "kind": "lines_sort_unique",
                    "input_text": "Beta\nalpha\nBeta\n",
                    "case_sensitive": False,
                }
            )
        )
        self.assertEqual(result.output.decode().splitlines(), ["alpha", "Beta"])
        self.assertTrue(result.verification["unique"])

    def test_base64_round_trip(self):
        encoded = bounty_solver.solve_package(
            self.package({"kind": "base64_encode", "input_text": "hello world"})
        )
        decoded = bounty_solver.solve_package(
            self.package({"kind": "base64_decode", "input_text": encoded.output.decode().strip()})
        )
        self.assertEqual(decoded.output.decode(), "hello world")
        self.assertTrue(decoded.verification["round_trip_equal"])

    def test_explicit_text_replace(self):
        result = bounty_solver.solve_package(
            self.package(
                {
                    "kind": "text_replace",
                    "input_text": "red green red",
                    "old": "red",
                    "new": "blue",
                }
            )
        )
        self.assertEqual(result.output.decode(), "blue green blue")
        self.assertEqual(result.verification["replacements"], 2)

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
