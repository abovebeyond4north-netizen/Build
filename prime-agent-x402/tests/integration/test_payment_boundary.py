"""Payment boundary through the real x402 middleware and a local facilitator."""
import base64
import hashlib
import json
import os
import threading
import tempfile
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
        if self.path != '/supported':
            self.send_error(404)
            return
        body = json.dumps({
            'kinds': [{'x402Version': 2, 'scheme': 'exact', 'network': 'eip155:8453', 'extra': {}}],
            'extensions': [], 'signers': {}
        }).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        if self.path == '/verify':
            type(self).verify_calls += 1
            type(self).events.append('verify')
            valid = type(self).verify_valid
            body = json.dumps({'isValid': valid, 'invalidReason': None if valid else 'invalid_signature',
                               'payer': '0x' + '2' * 40 if valid else None}).encode()
        elif self.path == '/settle':
            type(self).settle_calls += 1
            type(self).events.append('settle')
            body = json.dumps({'success': type(self).settle_success,
                               'transaction': '0x' + '4' * 64 if type(self).settle_success else '',
                               'network': 'eip155:8453', 'payer': '0x' + '2' * 40,
                               'errorReason': None if type(self).settle_success else 'mock_settlement_failure'}).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class PaymentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log_dir = tempfile.TemporaryDirectory()
        cls.log_path = os.path.join(cls.log_dir.name, 'paid-responses.jsonl')
        cls.facilitator = ThreadingHTTPServer(('127.0.0.1', 0), SupportedHandler)
        cls.thread = threading.Thread(target=cls.facilitator.serve_forever, daemon=True)
        cls.thread.start()
        os.environ['PRIME_PAY_TO'] = '0x0000000000000000000000000000000000000001'
        os.environ['PRIME_FACILITATOR_URL'] = f'http://127.0.0.1:{cls.facilitator.server_port}'
        os.environ['PRIME_BASE_RPC_URL'] = 'http://127.0.0.1:1'
        os.environ['PRIME_EVIDENCE_DB'] = ':memory:'
        os.environ['PRIME_DELIVERY_JOURNAL'] = cls.log_path
        import server
        cls.app = server.app
        cls.server_module = server

    def tearDown(self):
        SupportedHandler.verify_valid = False
        SupportedHandler.settle_success = False
        SupportedHandler.events.clear()
        if os.path.exists(self.log_path):
            os.unlink(self.log_path)

    @classmethod
    def tearDownClass(cls):
        cls.facilitator.shutdown()
        cls.facilitator.server_close()
        cls.thread.join(timeout=2)
        cls.log_dir.cleanup()

    def test_unsigned_request_is_402_without_rpc(self):
        with TestClient(self.app) as client:
            response = client.get('/chain/status')
            self.assertEqual(response.status_code, 402)
            header = response.headers['PAYMENT-REQUIRED']
            challenge = json.loads(base64.b64decode(header))
            self.assertEqual(challenge['x402Version'], 2)
            self.assertEqual(challenge['accepts'][0]['network'], 'eip155:8453')
            self.assertEqual(challenge['accepts'][0]['scheme'], 'exact')
            self.assertEqual(challenge['accepts'][0]['amount'], '1000')

    def test_unoffered_verdict_is_not_paid(self):
        with TestClient(self.app) as client:
            response = client.get('/token/verdict/0x'+'a'*40)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn('PAYMENT-REQUIRED', response.headers)

    def test_all_offered_routes_require_payment(self):
        address = '0x' + 'a' * 40
        for path, amount in [('/chain/status', '1000'),
                             (f'/token/metadata/{address}', '3000'),
                             (f'/token/context/{address}', '9000')]:
            with self.subTest(path=path), TestClient(self.app) as client:
                response = client.get(path)
                self.assertEqual(response.status_code, 402)
                challenge = json.loads(base64.b64decode(response.headers['PAYMENT-REQUIRED']))
                self.assertEqual(challenge['accepts'][0]['amount'], amount)

    def test_invalid_payment_never_settles(self):
        with TestClient(self.app) as client:
            signature = self.payment_header(client)
            before = SupportedHandler.settle_calls
            before_verify = SupportedHandler.verify_calls
            response = client.get('/chain/status', headers={'PAYMENT-SIGNATURE': signature})
            self.assertEqual(response.status_code, 402)
            self.assertGreater(SupportedHandler.verify_calls, before_verify)
            self.assertEqual(SupportedHandler.settle_calls, before)

    @staticmethod
    def payment_header(client):
        challenge_response = client.get('/chain/status')
        challenge = json.loads(base64.b64decode(challenge_response.headers['PAYMENT-REQUIRED']))
        accepted = challenge['accepts'][0]
        payment = {
            'x402Version': 2, 'accepted': accepted, 'resource': challenge['resource'],
            'payload': {
                'signature': '0x' + '0' * 130,
                'authorization': {'from': '0x' + '2' * 40, 'to': accepted['payTo'],
                                  'value': accepted['amount'], 'validAfter': '0',
                                  'validBefore': '9999999999', 'nonce': '0x' + '3' * 64},
            },
        }
        return base64.b64encode(json.dumps(payment).encode()).decode()

    def test_mock_settlement_precedes_content(self):
        SupportedHandler.verify_valid = True
        SupportedHandler.settle_success = True
        data = {'network': 'eip155:8453', 'block_number': 42, 'marker': 'paid-content'}
        fake = MagicMock()
        fake.chain_status.side_effect = lambda: (SupportedHandler.events.append('handler'), data)[1]
        with patch.object(self.server_module, 'intelligence', return_value=fake), TestClient(self.app) as client:
            signature = self.payment_header(client)
            response = client.get('/chain/status', headers={'PAYMENT-SIGNATURE': signature})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), data)
        self.assertIn('PAYMENT-RESPONSE', response.headers)
        self.assertEqual(SupportedHandler.events, ['verify', 'handler', 'settle'])
        with open(self.log_path, encoding='utf-8') as stream:
            journal = [json.loads(line) for line in stream]
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]['transaction'], '0x' + '4' * 64)
        self.assertEqual(journal[0]['route'], 'GET /chain/status')
        self.assertEqual(journal[0]['status'], 200)
        self.assertEqual(journal[0]['body_sha256'], hashlib.sha256(response.content).hexdigest())
        self.assertNotIn('signature', json.dumps(journal))

    def test_mock_settlement_failure_withholds_content(self):
        SupportedHandler.verify_valid = True
        SupportedHandler.settle_success = False
        fake = MagicMock()
        fake.chain_status.side_effect = lambda: {'marker': 'private-paid-content'}
        with patch.object(self.server_module, 'intelligence', return_value=fake), TestClient(self.app) as client:
            signature = self.payment_header(client)
            response = client.get('/chain/status', headers={'PAYMENT-SIGNATURE': signature})
        self.assertEqual(response.status_code, 402)
        self.assertNotIn('private-paid-content', response.text)
        self.assertEqual(SupportedHandler.events, ['verify', 'settle'])
        fake.chain_status.assert_called_once()
        self.assertFalse(os.path.exists(self.log_path))
