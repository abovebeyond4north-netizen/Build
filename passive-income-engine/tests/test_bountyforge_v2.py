import hashlib
import hmac
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from bountyforge import (
    BountyForge,
    Config,
    _queue_signature,
    _settled_units,
    safe_solver_payload,
)


class FakeOpenTask:
    def __init__(self):
        self.submitted = []
        self.task = {
            "id": "task-1",
            "title": "Convert CSV to JSON",
            "description": "Convert this CSV to JSON.\n\n```csv\nname,value\na,1\nb,2\n```",
            "executionMode": "pitch",
            "updatedAt": "2026-09-18T00:00:00Z",
        }

    def contracts(self, role="seller"):
        return [
            {
                "id": "contract-1",
                "status": "in_progress",
                "settlementStatus": "unpaid",
                "paymentVerificationStatus": "unpaid",
                "source": "bid",
                "task": {"id": "task-1", "title": self.task["title"]},
            }
        ]

    def task_detail(self, task_id):
        return {"task": dict(self.task)}

    def contract_receipts(self, contract_id):
        return [{"id": "rcpt_payment_1"}]

    def contract_invoices(self, contract_id):
        return [
            {
                "settlement": {
                    "units": [
                        {
                            "status": "paid",
                            "receiptId": "rcpt_payment_1",
                            "amount": {
                                "sellerAmount": "5.00",
                                "feeAmount": "0.23",
                                "currency": "USDC",
                            },
                        }
                    ]
                }
            }
        ]

    def create_delivery_draft(self, contract_id, **kwargs):
        return {"delivery": {"id": "delivery-1", "version": 1}}

    def create_delivery_upload_intent(self, contract_id, package_id, **kwargs):
        return {
            "uploadIntent": {
                "id": "upload-1",
                "fileId": "file-1",
                "fileStatus": "pending_upload",
                "upload": {
                    "url": "https://upload.test/object",
                    "callerHeaders": {"x-test": "secret"},
                },
            },
            "pollAfterMs": 0,
        }

    def upload_authorized(self, authorization, data):
        self.uploaded = data

    def complete_delivery_upload(self, contract_id, package_id, upload_intent_id):
        return {"file": {"id": "file-1", "status": "ready"}, "pollAfterMs": None}

    def delivery_upload_status(self, contract_id, package_id, upload_intent_id):
        return {"file": {"id": "file-1", "status": "ready"}, "pollAfterMs": None}

    def submit_delivery(self, contract_id, package_id, **kwargs):
        self.submitted.append((contract_id, package_id, kwargs))
        return {"delivery": {"id": package_id, "status": "submitted"}}


class BountyForgeV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.config = Config(
            database_path=str(root / "engine.db"),
            auto_solve=True,
            auto_deliver=False,
            reconcile_payments=True,
            queue_dir=str(root / "queue"),
            queue_secret="queue-test-secret",
            opentask_token="fake-token",
        )
        self.forge = BountyForge(self.config)
        self.fake = FakeOpenTask()
        self.forge.opentask = self.fake

    def test_safe_solver_payload_requires_clear_supported_work(self):
        payload = safe_solver_payload(
            "Convert CSV to JSON",
            "Please convert.\n\n```csv\nname,value\na,1\n```",
        )
        self.assertEqual(payload["kind"], "csv_to_json")
        self.assertIsNone(
            safe_solver_payload("Build a website", "Create a custom React app from scratch.")
        )

    def test_settled_units_require_matching_exact_receipt(self):
        invoice = self.fake.contract_invoices("contract-1")[0]
        self.assertEqual(list(_settled_units(invoice, set())), [])
        units = list(_settled_units(invoice, {"rcpt_payment_1"}))
        self.assertEqual(units[0]["seller_amount"], "5.00")
        self.assertEqual(units[0]["currency"], "USDC")

    def test_reconcile_queues_safe_contract_and_records_receipt_once(self):
        first = self.forge.reconcile_contracts()
        second = self.forge.reconcile_contracts()
        self.assertEqual(first["contracts"], 1)
        self.assertEqual(first["queued"], 1)
        self.assertEqual(first["settlements"], 1)
        self.assertEqual(second["queued"], 0)
        self.assertEqual(second["settlements"], 0)

        inbox = list((Path(self.config.queue_dir) / "inbox").glob("*.json"))
        self.assertEqual(len(inbox), 1)
        package = json.loads(inbox[0].read_text())
        supplied = package["signature"]
        self.assertEqual(supplied, _queue_signature(self.config.queue_secret, package))

        summary = self.forge.store.summary()
        self.assertEqual(summary["earnings"][0]["gross_cents"], 500)
        self.assertEqual(summary["earnings"][0]["fees_cents"], 0)
        self.assertEqual(summary["earnings"][0]["net_cents"], 500)

    def test_hash_verified_manifest_can_be_natively_delivered(self):
        root = Path(self.config.queue_dir)
        artifact = root / "artifacts" / "job-1" / "result.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"ok":true}\n')
        data = artifact.read_bytes()
        manifest = {
            "version": 1,
            "job_id": "job-1",
            "task_id": "task-1",
            "contract_id": "contract-1",
            "source": "opentask",
            "ok": True,
            "handler": "json_format",
            "artifact": {
                "relative_path": str(artifact.relative_to(root)),
                "filename": "result.json",
                "content_type": "application/json",
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            "verification": {"round_trip_equal": True},
            "error": None,
        }
        manifest["signature"] = _queue_signature(self.config.queue_secret, manifest)
        ready = root / "outbox"
        ready.mkdir(parents=True, exist_ok=True)
        (ready / "job-1.json").write_text(json.dumps(manifest))

        self.forge.config = Config(
            database_path=self.config.database_path,
            auto_solve=True,
            auto_deliver=True,
            reconcile_payments=False,
            queue_dir=self.config.queue_dir,
            queue_secret=self.config.queue_secret,
            opentask_token="fake-token",
        )
        result = self.forge.collect_solver_results()
        self.assertEqual(result["delivered"], 1)
        self.assertEqual(len(self.fake.submitted), 1)
        self.assertEqual(self.fake.uploaded, data)


if __name__ == "__main__":
    unittest.main()
