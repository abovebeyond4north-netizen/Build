"""Corroborate claimed Base USDC receipts onchain; does not prove x402 attribution."""
from __future__ import annotations
import argparse
import json
import re
import urllib.request
from decimal import Decimal

BASE_USDC = '0x833589fcD6edb6e08f4c7c32d4f71b54bda02913'.lower()
TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')
TX_HASH = re.compile(r'^0x[0-9a-fA-F]{64}$')
MAX_BYTES = 1_000_000


def address(value):
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise ValueError('invalid EVM address')
    return value.lower()


def quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x(?:0|[1-9a-fA-F][0-9a-fA-F]*)', value):
        raise ValueError('invalid JSON-RPC quantity')
    return int(value, 16)


class AuditRPC:
    def __init__(self, url):
        if not url.startswith(('https://', 'http://127.0.0.1:', 'http://localhost:')):
            raise ValueError('audit RPC must use HTTPS or loopback HTTP')
        self.url = url

    def call(self, method, params):
        if method not in {'eth_chainId', 'eth_blockNumber', 'eth_getTransactionReceipt', 'eth_getBlockByNumber'}:
            raise ValueError('disallowed audit method')
        request = urllib.request.Request(self.url,
            json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(),
            {'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError('audit RPC HTTP failure')
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise RuntimeError('audit RPC response too large')
        try: body = json.loads(raw)
        except ValueError as exc: raise RuntimeError('audit RPC invalid JSON') from exc
        if not isinstance(body, dict) or body.get('jsonrpc') != '2.0' or body.get('id') != 1 or 'error' in body or 'result' not in body:
            raise RuntimeError('audit RPC error')
        return body['result']


def _matching_log(log, payer, pay_to, atomic, receipt):
    if not isinstance(log, dict) or log.get('removed') is True:
        return False
    if str(log.get('address', '')).lower() != BASE_USDC:
        return False
    topics = log.get('topics')
    if not isinstance(topics, list) or len(topics) != 3 or str(topics[0]).lower() != TRANSFER_TOPIC:
        return False
    for topic in topics[1:]:
        if not isinstance(topic, str) or not re.fullmatch(r'0x[0-9a-fA-F]{64}', topic):
            return False
    if int(topics[1], 16) != int(payer, 16) or int(topics[2], 16) != int(pay_to, 16):
        return False
    data = log.get('data')
    if not isinstance(data, str) or not re.fullmatch(r'0x[0-9a-fA-F]{64}', data) or int(data, 16) != atomic:
        return False
    if log.get('blockHash') and str(log['blockHash']).lower() != str(receipt['blockHash']).lower():
        return False
    if log.get('transactionHash') and str(log['transactionHash']).lower() != str(receipt['transactionHash']).lower():
        return False
    return True


def corroborate(claims, rpc, pay_to, min_depth=12):
    pay_to = address(pay_to)
    if min_depth < 1:
        raise ValueError('min_depth must be positive')
    if rpc.call('eth_chainId', []) != '0x2105':
        raise RuntimeError('audit RPC is not Base mainnet')
    head = quantity(rpc.call('eth_blockNumber', []))
    matched, rejected, seen = [], [], set()
    for index, claim in enumerate(claims):
        try:
            tx = claim['transaction']
            if not isinstance(tx, str) or not TX_HASH.fullmatch(tx):
                raise ValueError('invalid transaction hash')
            if claim.get('network') != 'eip155:8453' or address(claim['asset']) != BASE_USDC:
                raise ValueError('unsupported network or asset')
            if claim.get('status') != 'settled':
                raise ValueError('claim is not settled')
            payer = address(claim['payer'])
            atomic = int(claim['amount_atomic'])
            if atomic <= 0 or str(atomic) != str(claim['amount_atomic']):
                raise ValueError('invalid atomic amount')
            receipt = rpc.call('eth_getTransactionReceipt', [tx])
            if not isinstance(receipt, dict) or str(receipt.get('transactionHash','')).lower() != tx.lower() or receipt.get('status') != '0x1':
                raise ValueError('missing or failed transaction')
            block_num = quantity(receipt.get('blockNumber'))
            block_hash = receipt.get('blockHash')
            if not isinstance(block_hash, str) or not TX_HASH.fullmatch(block_hash) or head - block_num + 1 < min_depth:
                raise ValueError('receipt has insufficient depth')
            block = rpc.call('eth_getBlockByNumber', [hex(block_num), False])
            if not isinstance(block, dict) or str(block.get('hash','')).lower() != block_hash.lower():
                raise ValueError('receipt block is not canonical at audit time')
            logs = receipt.get('logs')
            if not isinstance(logs, list):
                raise ValueError('receipt logs missing')
            candidates = [log for log in logs if _matching_log(log, payer, pay_to, atomic, receipt)]
            if len(candidates) != 1:
                raise ValueError('expected exactly one matching USDC transfer')
            log_index = quantity(candidates[0].get('logIndex'))
            key = (tx.lower(), log_index)
            if key in seen:
                raise ValueError('duplicate transfer claim')
            seen.add(key)
            matched.append({'transaction':tx.lower(), 'log_index':log_index,
                            'payer':payer, 'pay_to':pay_to, 'amount_atomic':atomic,
                            'block_number':block_num, 'block_hash':block_hash.lower()})
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({'claim_index':index, 'reason':str(exc)})
    nominal = sum((Decimal(row['amount_atomic']) / Decimal(1_000_000) for row in matched), Decimal('0'))
    return {'chain_matched_transfers':len(matched), 'matched_usdc_nominal':str(nominal),
            'matched':matched, 'rejected':rejected, 'min_block_depth':min_depth,
            'limitation':'A matching inbound USDC Transfer does not prove x402 request attribution, unique buyers, USD market value, or profitability.'}


def read_jsonl(path):
    with open(path, encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--claims',required=True)
    parser.add_argument('--audit-rpc-url',required=True)
    parser.add_argument('--pay-to',required=True)
    parser.add_argument('--min-depth',type=int,default=12)
    args=parser.parse_args()
    print(json.dumps(corroborate(read_jsonl(args.claims),AuditRPC(args.audit_rpc_url),args.pay_to,args.min_depth),indent=2))
