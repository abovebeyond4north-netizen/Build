import tempfile
import urllib.error
import unittest
import json
from unittest.mock import patch
from prime_agent import Intelligence, EvidenceStore, BaseRPC, DexScreenerClient, decode_abi_string, NETWORK, MAX_RPC_BYTES
from evaluate import reconcile

TOKEN = '0x' + 'a'*40
class FakeRPC:
    def __init__(self): self.calls=0; self.block_hash='0x'+'1'*64
    def snapshot(self): return {'network':NETWORK,'block_number':123,'block_hash':self.block_hash,'observed_at':1}
    def require_canonical(self, snapshot):
        if snapshot['block_hash'] != self.block_hash: raise RuntimeError('reorg')
    def code(self, address, snapshot): self.calls+=1; return '0x1234'
    def token_call(self, address, selector, snapshot):
        self.calls+=1
        if selector == '0x313ce567': return '0x'+(18).to_bytes(32,'big').hex()
        data = ('TEST' if selector == '0x95d89b41' else 'Test Token').encode()
        return '0x'+(32).to_bytes(32,'big').hex()+len(data).to_bytes(32,'big').hex()+data.hex().ljust(64,'0')

class CoreTests(unittest.TestCase):
    def test_reuse_and_reorg(self):
        with tempfile.TemporaryDirectory() as path:
            rpc=FakeRPC(); system=Intelligence(rpc,EvidenceStore(path+'/db.sqlite'))
            first=system.token_context(TOKEN)
            self.assertEqual(first['fields']['symbol'],'TEST')
            self.assertEqual(rpc.calls,4)
            again=system.token_verdict(TOKEN)
            self.assertEqual(rpc.calls,4)
            self.assertEqual(again['verdict'],'insufficient_evidence')
            self.assertEqual(first['evidence_ids'],again['context']['evidence_ids'])
            rpc.block_hash='0x'+'2'*64
            system.token_context(TOKEN)
            self.assertEqual(rpc.calls,8)
    def test_bad_string(self):
        with self.assertRaises(ValueError): decode_abi_string('0x1234')
    def test_reorg_during_request_fails_closed(self):
        with tempfile.TemporaryDirectory() as path:
            rpc=FakeRPC(); system=Intelligence(rpc,EvidenceStore(path+'/db.sqlite'))
            old=rpc.token_call
            def reorder(address, selector, snapshot):
                rpc.block_hash='0x'+'2'*64
                return old(address, selector, snapshot)
            rpc.token_call=reorder
            with self.assertRaisesRegex(RuntimeError,'reorg'):
                system.token_context(TOKEN)
    def test_hash_pinning_and_rpc_bound(self):
        class Response:
            status=200
            def __init__(self, body): self.body=body
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n): return self.body[:n]
        rpc=BaseRPC('http://127.0.0.1:8545')
        payload=json.dumps({'jsonrpc':'2.0','id':1,'result':'0x1234'}).encode()
        with patch('urllib.request.urlopen', return_value=Response(payload)) as urlopen:
            rpc.code(TOKEN, {'block_hash':'0x'+'1'*64})
            request=urlopen.call_args.args[0]
            sent=json.loads(request.data)
            self.assertEqual(sent['params'][1],{'blockHash':'0x'+'1'*64,'requireCanonical':True})
            self.assertEqual(request.get_header('User-agent'),'Prime-Agent-x402/1.0')
        with patch('urllib.request.urlopen', return_value=Response(b' '*(MAX_RPC_BYTES+1))):
            with self.assertRaisesRegex(RuntimeError,'byte limit'): rpc.call('eth_chainId',[])
        denied=urllib.error.HTTPError(rpc.url,403,'Forbidden',None,None)
        with patch('urllib.request.urlopen', side_effect=denied):
            with self.assertRaisesRegex(RuntimeError,'RPC request failed'): rpc.call('eth_chainId',[])

    def test_dex_context_adds_liquidity_activity_and_provenance(self):
        class FakeDex:
            calls = 0
            def token_pairs(self, address):
                self.calls += 1
                self.last_address = address
                return [
                    {
                        'chainId': 'base',
                        'dexId': 'dex-a',
                        'pairAddress': '0x'+'b'*40,
                        'url': 'https://dexscreener.com/base/example-a',
                        'baseToken': {'address': TOKEN},
                        'quoteToken': {'address': '0x'+'c'*40},
                        'priceUsd': '1.25',
                        'liquidity': {'usd': 1000.25},
                        'volume': {'h24': 500.50},
                        'txns': {'h24': {'buys': 7, 'sells': 5}},
                    },
                    {
                        'chainId': 'base',
                        'dexId': 'dex-b',
                        'pairAddress': '0x'+'d'*40,
                        'url': 'https://dexscreener.com/base/example-b',
                        'baseToken': {'address': '0x'+'e'*40},
                        'quoteToken': {'address': TOKEN.upper()},
                        'liquidity': {'usd': 250.75},
                        'volume': {'h24': 99.50},
                        'txns': {'h24': {'buys': 2, 'sells': 3}},
                    },
                ]

        with tempfile.TemporaryDirectory() as path:
            rpc=FakeRPC(); dex=FakeDex()
            system=Intelligence(rpc,EvidenceStore(path+'/db.sqlite'),dex)
            first=system.token_context(TOKEN)
            self.assertTrue(first['coverage']['liquidity'])
            self.assertTrue(first['coverage']['activity'])
            self.assertFalse(first['coverage']['holders'])
            self.assertEqual(first['dex_market']['pair_count'],2)
            self.assertEqual(first['dex_market']['aggregate_liquidity_usd'],1251.0)
            self.assertEqual(first['dex_market']['aggregate_volume_h24_usd'],600.0)
            self.assertEqual(first['dex_market']['buys_h24'],9)
            self.assertEqual(first['dex_market']['sells_h24'],8)
            self.assertEqual(first['dex_market']['top_pair']['dex'],'dex-a')
            self.assertEqual(dex.calls,1)
            self.assertEqual(len(first['evidence_ids']),5)

            again=system.token_context(TOKEN)
            self.assertEqual(dex.calls,1)
            self.assertEqual(first['dex_market'],again['dex_market'])

    def test_dex_failure_is_partial_not_false_coverage(self):
        class FailingDex:
            def token_pairs(self, address):
                raise RuntimeError('upstream unavailable')

        with tempfile.TemporaryDirectory() as path:
            system=Intelligence(FakeRPC(),EvidenceStore(path+'/db.sqlite'),FailingDex())
            result=system.token_context(TOKEN)
            self.assertFalse(result['coverage']['liquidity'])
            self.assertFalse(result['coverage']['activity'])
            self.assertFalse(result['coverage']['holders'])
            self.assertFalse(result['dex_market']['available'])

    def test_dex_client_is_bounded_and_validates_shape(self):
        class Response:
            status=200
            def __init__(self, body): self.body=body
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n): return self.body[:n]

        client=DexScreenerClient('http://127.0.0.1:9999')
        payload=json.dumps([{'chainId':'base'}]).encode()
        with patch('urllib.request.urlopen', return_value=Response(payload)) as urlopen:
            pairs=client.token_pairs(TOKEN)
            self.assertEqual(pairs,[{'chainId':'base'}])
            request=urlopen.call_args.args[0]
            self.assertIn('/token-pairs/v1/base/', request.full_url)
            self.assertEqual(request.get_header('User-agent'),'Prime-Agent-x402/1.0')

    def test_receipt_dedup(self):
        receipts=[{'status':'settled','network':NETWORK,'transaction':'0x1','amount_usd':'0.02','payer':TOKEN}]*2
        out=reconcile(receipts,[{'amount_usd':'0.001'}])
        self.assertEqual(out['reported_contribution_usd'],'0.019')
        self.assertEqual(out['reported_settled_receipts'],1)
        self.assertEqual(len(out['duplicate_transactions']),1)
