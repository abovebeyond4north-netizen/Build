"""Payment boundary through the real x402 middleware and a local facilitator."""
import asyncio
import base64
import hashlib
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class SupportedHandler(BaseHTTPRequestHandler):
    verify_calls = 0
    settle_calls = 0
    verify_valid = False
    settle_success = False
    events = []

    def do_GET(self):
        if self.path != "/supported":
            self.send_error(404)
            return
        body = json.dumps(
            {
                "kinds": [
                    {
                        "x402Version": 2,
                        "scheme": "exact",
                        "network": "eip155:8453",
                        "extra": {},
                    }
                ],
                "extensions": [],
                "signers": {},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/verify":
            type(self).verify_calls += 1
            type(self).events.append("verify")
            valid = type(self).verify_valid
            body = json.dumps(
                {
                    "isValid": valid,
                    "invalidReason": None if valid else "invalid_signature",
                    "payer": "0x" + "2" * 40 if valid else None,
                }
            ).encode()
        elif self.path == "/settle":
            type(self).settle_calls += 1
            type(self).events.append("settle")
            body = json.dumps(
                {
                    "success": type(self).settle_success,
                    "transaction": "0x" + "4" * 64 if type(self).settle_success else "",
                    "network": "eip155:8453",
                    "payer": "0x" + "2" * 40,
                    "errorReason": (
                        None if type(self).settle_success else "mock_settlement_failure"
                    ),
                }
            ).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class PaymentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log_dir = tempfile.TemporaryDirectory()
        cls.log_path = os.path.join(cls.log_dir.name, "paid-responses.jsonl")
        cls.facilitator = ThreadingHTTPServer(("127.0.0.1", 0), SupportedHandler)
        cls.thread = threading.Thread(
            target=cls.facilitator.serve_forever,
            daemon=True,
        )
        cls.thread.start()

        os.environ["PRIME_PAY_TO"] = "0x0000000000000000000000000000000000000001"
        os.environ["PRIME_FACILITATOR_URL"] = (
            f"http://127.0.0.1:{cls.facilitator.server_port}"
        )
        os.environ["PRIME_BASE_RPC_URL"] = "http://127.0.0.1:1"
        os.environ["PRIME_EVIDENCE_DB"] = ":memory:"
        os.environ["PRIME_DELIVERY_JOURNAL"] = cls.log_path
        os.environ["PRIME_PUBLIC_URL"] = "http://testserver"

        import server

        cls.app = server.app
        cls.server_module = server
        cls.client = TestClient(cls.app)
        cls.client.__enter__()

    def tearDown(self):
        SupportedHandler.verify_valid = False
        SupportedHandler.settle_success = False
        SupportedHandler.events.clear()
        if os.path.exists(self.log_path):
            os.unlink(self.log_path)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.facilitator.shutdown()
        cls.facilitator.server_close()
        cls.thread.join(timeout=2)
        cls.log_dir.cleanup()

    def test_unsigned_request_is_402_without_rpc(self):
        response = self.client.get("/chain/status")
        self.assertEqual(response.status_code, 402)
        header = response.headers["PAYMENT-REQUIRED"]
        challenge = json.loads(base64.b64decode(header))
        self.assertEqual(challenge["x402Version"], 2)
        self.assertEqual(challenge["accepts"][0]["network"], "eip155:8453")
        self.assertEqual(challenge["accepts"][0]["scheme"], "exact")
        self.assertEqual(challenge["accepts"][0]["amount"], "1000")

    def test_bazaar_discovery_metadata_is_in_dynamic_402(self):
        address = "0x" + "a" * 40
        response = self.client.get(f"/token/metadata/{address}")
        self.assertEqual(response.status_code, 402)
        challenge = json.loads(
            base64.b64decode(response.headers["PAYMENT-REQUIRED"])
        )
        resource = challenge["resource"]
        self.assertEqual(resource["serviceName"], "Prime-Agent x402 Intelligence")
        self.assertEqual(
            resource["tags"],
            ["base", "erc20", "token-metadata", "contract", "provenance"],
        )
        self.assertTrue(
            resource["url"].startswith("http://testserver/token/metadata/")
        )
        bazaar = challenge["extensions"]["bazaar"]
        self.assertEqual(bazaar["routeTemplate"], "/token/metadata/:address")
        self.assertEqual(bazaar["info"]["input"]["type"], "http")
        self.assertEqual(bazaar["info"]["input"]["method"], "GET")
        self.assertEqual(
            bazaar["info"]["input"]["pathParams"]["address"],
            address,
        )
        self.assertEqual(bazaar["info"]["output"]["type"], "json")
        self.assertEqual(
            bazaar["info"]["output"]["example"]["network"],
            "eip155:8453",
        )

    def test_free_discovery_surfaces_do_not_require_payment(self):
        catalog = self.client.get("/catalog")
        self.assertEqual(catalog.status_code, 200)
        self.assertNotIn("PAYMENT-REQUIRED", catalog.headers)
        payload = catalog.json()
        self.assertEqual(payload["service"], "Prime-Agent x402 Intelligence")
        self.assertEqual(len(payload["products"]), 3)
        self.assertTrue(all(product["paid"] for product in payload["products"]))

        llms = self.client.get("/llms.txt")
        self.assertEqual(llms.status_code, 200)
        self.assertIn("/token/context/{address}", llms.text)

        server_json = self.client.get("/server.json")
        self.assertEqual(server_json.status_code, 200)
        manifest = server_json.json()
        self.assertEqual(
            manifest["name"],
            "io.github.abovebeyond4north-netizen/prime-agent-x402-intelligence",
        )
        self.assertEqual(
            manifest["remotes"][0]["type"],
            "streamable-http",
        )
        self.assertTrue(manifest["remotes"][0]["url"].endswith("/mcp/"))

        openapi = self.client.get("/openapi.json")
        self.assertEqual(openapi.status_code, 200)
        self.assertIn("/chain/status", openapi.json()["paths"])

        manifest = self.client.get("/.well-known/x402")
        self.assertEqual(manifest.status_code, 200)
        x402_manifest = manifest.json()
        self.assertEqual(x402_manifest["spec"], "agent402-service-manifest/1")
        self.assertEqual(x402_manifest["version"], 1)
        self.assertEqual(len(x402_manifest["resources"]), 3)
        self.assertEqual(
            x402_manifest["payment"]["x402"]["network"],
            "eip155:8453",
        )
        self.assertFalse(
            x402_manifest["capabilities"]["tokenContext"]["holders"]
        )

    def test_openapi_declares_x402_prices_and_agent_guidance(self):
        doc = self.client.get("/openapi.json").json()
        self.assertIn("x-guidance", doc["info"])
        cases = [
            ("/chain/status", "0.001"),
            ("/token/metadata/{address}", "0.003"),
            ("/token/context/{address}", "0.009"),
        ]
        for path, price in cases:
            with self.subTest(path=path):
                operation = doc["paths"][path]["get"]
                payment = operation["x-payment-info"]
                self.assertEqual(
                    payment["price"],
                    {"mode": "fixed", "currency": "USD", "amount": price},
                )
                self.assertEqual(payment["protocols"], [{"x402": {}}])
                self.assertIn("402", operation["responses"])
                self.assertIn("200", operation["responses"])
                schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
                self.assertEqual(schema["type"], "object")

        self.assertEqual(doc["paths"]["/"]["get"]["security"], [])
        self.assertEqual(doc["paths"]["/catalog"]["get"]["security"], [])
        self.assertIn(
            "Liquidity",
            doc["paths"]["/token/context/{address}"]["get"]["tags"],
        )
        self.assertIn(
            "Token Metadata",
            doc["paths"]["/token/metadata/{address}"]["get"]["tags"],
        )

    def test_mcp_discovery_tools_are_free_quotes_not_paid_content(self):
        tools = asyncio.run(self.server_module.mcp_server.list_tools())
        names = {tool.name for tool in tools}
        self.assertIn("list_products", names)
        self.assertIn("quote_token_product", names)

        quote = self.server_module.quote_token_product(
            "token_metadata",
            "0x" + "a" * 40,
        )
        self.assertEqual(quote["price_usd"], "0.003")
        self.assertFalse(quote["spends_funds"])
        self.assertIn("/token/metadata/0x", quote["url"])

    def test_unoffered_verdict_is_not_paid(self):
        response = self.client.get("/token/verdict/" + "0x" + "a" * 40)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("PAYMENT-REQUIRED", response.headers)

    def test_all_offered_routes_require_payment(self):
        address = "0x" + "a" * 40
        cases = [
            ("/chain/status", "1000"),
            (f"/token/metadata/{address}", "3000"),
            (f"/token/context/{address}", "9000"),
        ]
        for path, amount in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 402)
                challenge = json.loads(
                    base64.b64decode(response.headers["PAYMENT-REQUIRED"])
                )
                self.assertEqual(challenge["accepts"][0]["amount"], amount)
                self.assertIn("bazaar", challenge["extensions"])

    def test_invalid_payment_never_settles(self):
        signature = self.payment_header(self.client)
        before = SupportedHandler.settle_calls
        before_verify = SupportedHandler.verify_calls
        response = self.client.get(
            "/chain/status",
            headers={"PAYMENT-SIGNATURE": signature},
        )
        self.assertEqual(response.status_code, 402)
        self.assertGreater(SupportedHandler.verify_calls, before_verify)
        self.assertEqual(SupportedHandler.settle_calls, before)

    @staticmethod
    def payment_header(client):
        challenge_response = client.get("/chain/status")
        challenge = json.loads(
            base64.b64decode(challenge_response.headers["PAYMENT-REQUIRED"])
        )
        accepted = challenge["accepts"][0]
        payment = {
            "x402Version": 2,
            "accepted": accepted,
            "resource": challenge["resource"],
            "extensions": challenge.get("extensions", {}),
            "payload": {
                "signature": "0x" + "0" * 130,
                "authorization": {
                    "from": "0x" + "2" * 40,
                    "to": accepted["payTo"],
                    "value": accepted["amount"],
                    "validAfter": "0",
                    "validBefore": "9999999999",
                    "nonce": "0x" + "3" * 64,
                },
            },
        }
        return base64.b64encode(json.dumps(payment).encode()).decode()

    def test_mock_settlement_precedes_content(self):
        SupportedHandler.verify_valid = True
        SupportedHandler.settle_success = True
        data = {
            "network": "eip155:8453",
            "block_number": 42,
            "marker": "paid-content",
        }
        fake = MagicMock()
        fake.chain_status.side_effect = lambda: (
            SupportedHandler.events.append("handler"),
            data,
        )[1]

        with patch.object(
            self.server_module,
            "intelligence",
            return_value=fake,
        ):
            signature = self.payment_header(self.client)
            with self.assertLogs("delivery_journal", level="INFO") as logs:
                response = self.client.get(
                    "/chain/status",
                    headers={"PAYMENT-SIGNATURE": signature},
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("x402 settlement_delivered", "\n".join(logs.output))
        self.assertIn("0x" + "4" * 64, "\n".join(logs.output))
        self.assertEqual(response.json(), data)
        self.assertIn("PAYMENT-RESPONSE", response.headers)
        self.assertEqual(
            SupportedHandler.events,
            ["verify", "handler", "settle"],
        )

        with open(self.log_path, encoding="utf-8") as stream:
            journal = [json.loads(line) for line in stream]

        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]["transaction"], "0x" + "4" * 64)
        self.assertEqual(journal[0]["route"], "GET /chain/status")
        self.assertEqual(journal[0]["status"], 200)
        self.assertEqual(
            journal[0]["body_sha256"],
            hashlib.sha256(response.content).hexdigest(),
        )
        self.assertNotIn("signature", json.dumps(journal))

    def test_mock_settlement_failure_withholds_content(self):
        SupportedHandler.verify_valid = True
        SupportedHandler.settle_success = False
        fake = MagicMock()
        fake.chain_status.side_effect = lambda: {
            "marker": "private-paid-content"
        }

        with patch.object(
            self.server_module,
            "intelligence",
            return_value=fake,
        ):
            signature = self.payment_header(self.client)
            response = self.client.get(
                "/chain/status",
                headers={"PAYMENT-SIGNATURE": signature},
            )

        self.assertEqual(response.status_code, 402)
        self.assertNotIn("private-paid-content", response.text)
        self.assertEqual(SupportedHandler.events, ["verify", "settle"])
        fake.chain_status.assert_called_once()
        self.assertFalse(os.path.exists(self.log_path))


if __name__ == "__main__":
    unittest.main()
