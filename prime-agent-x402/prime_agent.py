"""Prime-Agent deterministic, provenance-bearing Base chain intelligence core."""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import time
import urllib.request
import threading
from dataclasses import dataclass
from typing import Any

NETWORK = 'eip155:8453'
ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')
HASH = re.compile(r'^0x[0-9a-fA-F]{64}$')
SELECTORS = {'decimals': '0x313ce567', 'symbol': '0x95d89b41', 'name': '0x06fdde03'}
MAX_RPC_BYTES = 512_000


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def valid_address(address: str) -> str:
    if not ADDRESS.fullmatch(address):
        raise ValueError('invalid EVM address')
    return address.lower()


def decode_abi_string(raw: str) -> str:
    data = bytes.fromhex(raw.removeprefix('0x'))
    if len(data) == 32:  # Older contracts sometimes return bytes32.
        return data.rstrip(b'\x00').decode('utf-8', errors='replace')
    if len(data) < 64:
        raise ValueError('invalid ABI string')
    offset = int.from_bytes(data[:32], 'big')
    if offset + 32 > len(data):
        raise ValueError('invalid ABI offset')
    length = int.from_bytes(data[offset:offset + 32], 'big')
    if length > 4096 or offset + 32 + length > len(data):
        raise ValueError('invalid ABI length')
    return data[offset + 32:offset + 32 + length].decode('utf-8', errors='replace')


class BaseRPC:
    def __init__(self, url: str):
        if not url.startswith(('https://', 'http://127.0.0.1:', 'http://localhost:')):
            raise ValueError('RPC URL must use HTTPS or local loopback HTTP')
        self.url = url
        self.calls = 0

    def call(self, method: str, params: list) -> Any:
        if method not in {'eth_chainId', 'eth_getBlockByNumber', 'eth_getCode', 'eth_call'}:
            raise ValueError('RPC method disallowed')
        body = canonical({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
        req = urllib.request.Request(self.url, body, {'Content-Type': 'application/json'}, method='POST')
        self.calls += 1
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                raise RuntimeError('RPC HTTP failure')
            raw = resp.read(MAX_RPC_BYTES + 1)
        if len(raw) > MAX_RPC_BYTES:
            raise RuntimeError('RPC response exceeds byte limit')
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError('RPC returned invalid JSON') from exc
        if not isinstance(result, dict) or result.get('id') != 1 or result.get('jsonrpc') != '2.0' or 'error' in result or 'result' not in result:
            raise RuntimeError('RPC returned an error')
        return result['result']

    def snapshot(self) -> dict:
        if self.call('eth_chainId', []) != '0x2105':
            raise RuntimeError('RPC is not Base mainnet')
        block = self.call('eth_getBlockByNumber', ['latest', False])
        if not isinstance(block, dict) or not HASH.fullmatch(block.get('hash', '')):
            raise RuntimeError('invalid latest block')
        return {'network': NETWORK, 'block_number': int(block['number'], 16),
                'block_hash': block['hash'].lower(), 'observed_at': int(time.time())}

    def require_canonical(self, snapshot: dict) -> None:
        block = self.call('eth_getBlockByNumber', [hex(snapshot['block_number']), False])
        if not isinstance(block, dict) or block.get('hash', '').lower() != snapshot['block_hash']:
            raise RuntimeError('snapshot was reorganized; discard response')

    def code(self, address: str, snapshot: dict) -> str:
        value = self.call('eth_getCode', [valid_address(address),
                                          {'blockHash': snapshot['block_hash'], 'requireCanonical': True}])
        if not isinstance(value, str) or not re.fullmatch(r'0x(?:[0-9a-fA-F]{2})*', value):
            raise RuntimeError('invalid contract code response')
        return value

    def token_call(self, address: str, selector: str, snapshot: dict) -> str:
        value = self.call('eth_call', [{'to': valid_address(address), 'data': selector},
                                       {'blockHash': snapshot['block_hash'], 'requireCanonical': True}])
        if not isinstance(value, str) or len(value) > 8194 or not re.fullmatch(r'0x(?:[0-9a-fA-F]{2})*', value):
            raise RuntimeError('invalid or oversized contract call response')
        return value


@dataclass(frozen=True)
class Observation:
    entity: str
    predicate: str
    value: Any
    source: str
    snapshot: dict
    expires_at: int
    version: str = '1.0'

    def body(self) -> dict:
        return self.__dict__.copy()

    def record(self) -> dict:
        return {'evidence_id': digest(self.body()), **self.body()}


class EvidenceStore:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, entity TEXT NOT NULL, predicate TEXT NOT NULL, block_hash TEXT NOT NULL, expires_at INTEGER NOT NULL, body TEXT NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS evidence_lookup ON evidence(entity,predicate,block_hash,expires_at)')
        self.db.commit()
        self.lock = threading.RLock()

    def get(self, entity: str, predicate: str, snapshot: dict) -> dict | None:
        with self.lock:
            row = self.db.execute('SELECT body FROM evidence WHERE entity=? AND predicate=? AND block_hash=? AND expires_at>? ORDER BY expires_at DESC LIMIT 1',
                                  (entity, predicate, snapshot['block_hash'], int(time.time()))).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, observation: Observation) -> dict:
        record = observation.record()
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO evidence VALUES (?,?,?,?,?,?)',
                            (record['evidence_id'], observation.entity, observation.predicate,
                             observation.snapshot['block_hash'], observation.expires_at, canonical(record)))
        return record


class Intelligence:
    def __init__(self, rpc: BaseRPC, store: EvidenceStore):
        self.rpc, self.store = rpc, store

    def _read(self, entity: str, predicate: str, snapshot: dict, fn, ttl=300) -> dict:
        cached = self.store.get(entity, predicate, snapshot)
        if cached:
            return cached
        value = fn()
        return self.store.put(Observation(entity, predicate, value, 'base-json-rpc', snapshot,
                                          int(time.time()) + ttl))

    def chain_status(self) -> dict:
        snap = self.rpc.snapshot()
        return {'network': NETWORK, 'block_number': snap['block_number'],
                'block_hash': snap['block_hash'], 'observed_at': snap['observed_at']}

    def metadata(self, address: str, snapshot: dict | None = None) -> dict:
        address = valid_address(address)
        snap = snapshot or self.rpc.snapshot()
        entity = f'{NETWORK}:token:{address}'
        code = self._read(entity, 'code_present', snap,
                          lambda: self.rpc.code(address, snap) not in ('0x', '0x0'), ttl=600)
        if not code['value']:
            self.rpc.require_canonical(snap)
            return {'network': NETWORK, 'token': address, 'snapshot': snap, 'is_contract': False,
                    'fields': {}, 'evidence_ids': [code['evidence_id']], 'missing': ['contract_code']}
        fields, evidence_ids, missing = {}, [code['evidence_id']], []
        for field, selector in SELECTORS.items():
            try:
                def fetch(selector=selector, field=field):
                    raw = self.rpc.token_call(address, selector, snap)
                    if field == 'decimals':
                        if len(bytes.fromhex(raw.removeprefix('0x'))) != 32:
                            raise ValueError('invalid decimals ABI')
                        value = int(raw, 16)
                        if value > 255:
                            raise ValueError('decimals out of range')
                        return value
                    return decode_abi_string(raw)
                record = self._read(entity, field, snap, fetch, ttl=600)
                fields[field] = record['value']
                evidence_ids.append(record['evidence_id'])
            except (ValueError, RuntimeError):
                missing.append(field)
        self.rpc.require_canonical(snap)
        return {'network': NETWORK, 'token': address, 'snapshot': snap, 'is_contract': True,
                'fields': fields, 'evidence_ids': evidence_ids, 'missing': missing}

    def token_context(self, address: str) -> dict:
        result = self.metadata(address)
        result['coverage'] = {'contract': result['is_contract'], 'metadata': not result['missing'],
                              'holders': False, 'liquidity': False, 'activity': False}
        return result

    def token_verdict(self, address: str) -> dict:
        context = self.token_context(address)
        required = ('contract', 'metadata', 'holders', 'liquidity', 'activity')
        missing = [name for name in required if not context['coverage'][name]]
        return {'verdict': 'insufficient_evidence', 'ruleset': 'v1.0', 'missing_dimensions': missing,
                'reason': 'A token risk assessment requires holder, liquidity, and activity evidence.',
                'context': context}
