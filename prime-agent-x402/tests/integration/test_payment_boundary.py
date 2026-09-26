"""Unpaid HTTP challenge through the real x402 middleware and a local facilitator."""
import base64
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient


class SupportedHandler(BaseHTTPRequestHandler):
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

    def log_message(self, *_args):
        pass


class PaymentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facilitator = ThreadingHTTPServer(('127.0.0.1', 0), SupportedHandler)
        cls.thread = threading.Thread(target=cls.facilitator.serve_forever, daemon=True)
        cls.thread.start()
        os.environ['PRIME_PAY_TO'] = '0x0000000000000000000000000000000000000001'
        os.environ['PRIME_FACILITATOR_URL'] = f'http://127.0.0.1:{cls.facilitator.server_port}'
        os.environ['PRIME_BASE_RPC_URL'] = 'http://127.0.0.1:1'
        os.environ['PRIME_EVIDENCE_DB'] = ':memory:'
        import server
        cls.app = server.app

    @classmethod
    def tearDownClass(cls):
        cls.facilitator.shutdown()
        cls.facilitator.server_close()
        cls.thread.join(timeout=2)

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
