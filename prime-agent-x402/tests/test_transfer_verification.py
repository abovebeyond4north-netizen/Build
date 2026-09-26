import copy
import unittest

from verify_transfers import BASE_USDC, TRANSFER_TOPIC, corroborate


PAYER = '0x' + 'a' * 40
PAY_TO = '0x' + 'b' * 40
TX = '0x' + 'c' * 64
BLOCK = '0x' + 'd' * 64


def fixture():
    claim = {'status': 'settled', 'network': 'eip155:8453', 'asset': BASE_USDC,
             'transaction': TX, 'payer': PAYER, 'amount_atomic': '20000'}
    log = {'address': BASE_USDC, 'topics': [TRANSFER_TOPIC,
           '0x' + PAYER[2:].rjust(64, '0'), '0x' + PAY_TO[2:].rjust(64, '0')],
           'data': '0x' + format(20000, '064x'), 'logIndex': '0x0',
           'blockHash': BLOCK, 'transactionHash': TX}
    receipt = {'transactionHash': TX, 'status': '0x1', 'blockNumber': '0x64',
               'blockHash': BLOCK, 'logs': [log]}
    return claim, receipt


class FakeRPC:
    def __init__(self, receipt, head=111, canonical=BLOCK):
        self.receipt, self.head, self.canonical = receipt, head, canonical

    def call(self, method, params):
        if method == 'eth_chainId': return '0x2105'
        if method == 'eth_blockNumber': return hex(self.head)
        if method == 'eth_getTransactionReceipt': return self.receipt
        if method == 'eth_getBlockByNumber': return {'hash': self.canonical}
        raise AssertionError(method)


class TransferVerificationTests(unittest.TestCase):
    def test_matching_transfer_and_duplicate_claim(self):
        claim, receipt = fixture()
        out = corroborate([claim, claim], FakeRPC(receipt), PAY_TO)
        self.assertEqual(out['chain_matched_transfers'], 1)
        self.assertEqual(out['matched_usdc_nominal'], '0.02')
        self.assertEqual(out['rejected'][0]['reason'], 'duplicate transfer claim')

    def test_wrong_asset_sender_payee_or_amount_rejected(self):
        claim, receipt = fixture()
        for change in ('asset', 'sender', 'payee', 'amount'):
            with self.subTest(change=change):
                altered_claim, altered_receipt = copy.deepcopy(claim), copy.deepcopy(receipt)
                if change == 'asset': altered_receipt['logs'][0]['address'] = PAYER
                if change == 'sender': altered_receipt['logs'][0]['topics'][1] = '0x' + '0' * 64
                if change == 'payee': altered_receipt['logs'][0]['topics'][2] = '0x' + '0' * 64
                if change == 'amount': altered_claim['amount_atomic'] = '30000'
                out = corroborate([altered_claim], FakeRPC(altered_receipt), PAY_TO)
                self.assertEqual(out['chain_matched_transfers'], 0)
                self.assertEqual(len(out['rejected']), 1)

    def test_failed_reorged_or_shallow_transaction_rejected(self):
        claim, receipt = fixture()
        for rpc in (FakeRPC({**receipt, 'status': '0x0'}),
                    FakeRPC(receipt, canonical='0x' + 'e' * 64),
                    FakeRPC(receipt, head=110)):
            with self.subTest(rpc=rpc):
                out = corroborate([claim], rpc, PAY_TO)
                self.assertEqual(out['chain_matched_transfers'], 0)
                self.assertEqual(len(out['rejected']), 1)

    def test_wrong_chain_fails_closed(self):
        claim, receipt = fixture()
        class WrongChain(FakeRPC):
            def call(self, method, params):
                if method == 'eth_chainId': return '0x1'
                return super().call(method, params)
        with self.assertRaisesRegex(RuntimeError, 'not Base'):
            corroborate([claim], WrongChain(receipt), PAY_TO)


if __name__ == '__main__':
    unittest.main()
