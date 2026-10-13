import unittest

from audit_sales import audit
from test_transfer_verification import PAY_TO, PAYER, TX, FakeRPC, fixture


def event(route='GET /chain/status', price='$0.001'):
    return {'event': 'asgi_response_sent', 'request_id': '1' * 32,
            'transaction': TX, 'payer_reported_by_facilitator': PAYER,
            'route': route, 'price': price, 'status': 200, 'network': 'eip155:8453',
            'pay_to': PAY_TO, 'body_sha256': 'f' * 64}


class SalesAuditTests(unittest.TestCase):
    def test_correlates_only_exact_route_price_and_onchain_transfer(self):
        _, receipt = fixture()
        receipt['logs'][0]['data'] = '0x' + format(1000, '064x')
        out = audit([event()], FakeRPC(receipt), PAY_TO)
        self.assertEqual(out['chain_correlated_response_events'], 1)
        self.assertEqual(out['correlated_usdc_nominal'], '0.001')
        self.assertEqual(out['distinct_payer_wallets'], 1)
        self.assertEqual(out['correlated'][0]['body_sha256'], 'f' * 64)
        self.assertNotIn('revenue', out)

    def test_duplicate_or_wrong_price_or_payee_rejected(self):
        _, receipt = fixture()
        receipt['logs'][0]['data'] = '0x' + format(1000, '064x')
        wrong_price = {**event(), 'request_id': '2' * 32, 'price': '$0.009'}
        wrong_payee = {**event(), 'request_id': '3' * 32, 'pay_to': PAYER}
        out = audit([event(), event(), wrong_price, wrong_payee], FakeRPC(receipt), PAY_TO)
        self.assertEqual(out['chain_correlated_response_events'], 1)
        self.assertEqual(len(out['rejected']), 3)

    def test_wrong_amount_or_payer_cannot_correlate(self):
        _, receipt = fixture()
        out = audit([event()], FakeRPC(receipt), PAY_TO)
        self.assertEqual(out['chain_correlated_response_events'], 0)
        self.assertEqual(out['correlated_usdc_nominal'], '0')
        self.assertEqual(len(out['rejected']), 1)
        receipt['logs'][0]['data'] = '0x' + format(1000, '064x')
        out = audit([{**event(), 'payer_reported_by_facilitator': PAY_TO}], FakeRPC(receipt), PAY_TO)
        self.assertEqual(out['chain_correlated_response_events'], 0)


if __name__ == '__main__':
    unittest.main()
