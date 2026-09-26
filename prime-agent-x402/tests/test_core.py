import tempfile
import urllib.error
import unittest
import json
from unittest.mock import patch
from prime_agent import Intelligence, EvidenceStore, BaseRPC, decode_abi_string, NETWORK, MAX_RPC_BYTES
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
    def test_receipt_dedup(self):
        receipts=[{'status':'settled','network':NETWORK,'transaction':'0x1','amount_usd':'0.02','payer':TOKEN}]*2
        out=reconcile(receipts,[{'amount_usd':'0.001'}])
        self.assertEqual(out['reported_contribution_usd'],'0.019')
        self.assertEqual(out['reported_settled_receipts'],1)
        self.assertEqual(len(out['duplicate_transactions']),1)
