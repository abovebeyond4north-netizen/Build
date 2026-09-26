"""Join server response events to independently queried Base USDC transfers."""
from __future__ import annotations

import argparse
import json
import re

from pricing import PRICES, atomic_price
from verify_transfers import AuditRPC, BASE_USDC, TX_HASH, address, corroborate, read_jsonl

SHA256 = re.compile(r'^[0-9a-f]{64}$')
REQUEST_ID = re.compile(r'^[0-9a-f]{32}$')


def audit(events: list[dict], rpc, pay_to: str, min_depth: int = 12) -> dict:
    pay_to = address(pay_to)
    claims, accepted_events, rejected = [], [], []
    seen_requests, seen_transactions = set(), set()
    for index, event in enumerate(events):
        try:
            if not isinstance(event, dict):
                raise ValueError('invalid journal entry')
            request_id = event['request_id']
            tx = event['transaction']
            payer = address(event['payer_reported_by_facilitator'])
            route = event['route']
            if (event.get('event') != 'asgi_response_sent' or event.get('status') != 200
                    or event.get('network') != 'eip155:8453'):
                raise ValueError('not a successful Base response event')
            if (not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id)
                    or not isinstance(tx, str) or not TX_HASH.fullmatch(tx)
                    or not isinstance(event.get('body_sha256'), str)
                    or not SHA256.fullmatch(event['body_sha256'])):
                raise ValueError('invalid event identifiers or response digest')
            if route not in PRICES or event.get('price') != PRICES[route]:
                raise ValueError('unoffered route or price mismatch')
            if address(event['pay_to']) != pay_to:
                raise ValueError('wrong configured payee')
            if request_id in seen_requests or tx.lower() in seen_transactions:
                raise ValueError('duplicate request or transaction event')
            seen_requests.add(request_id)
            seen_transactions.add(tx.lower())
            accepted_events.append((index, event))
            claims.append({'status': 'settled', 'network': 'eip155:8453', 'asset': BASE_USDC,
                           'transaction': tx, 'payer': payer,
                           'amount_atomic': str(atomic_price(route))})
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({'event_index': index, 'reason': str(exc)})

    transfers = corroborate(claims, rpc, pay_to, min_depth)
    rejected += [{'event_index': accepted_events[row['claim_index']][0], 'reason': row['reason']}
                 for row in transfers['rejected']]
    matched_by_tx = {row['transaction']: row for row in transfers['matched']}
    correlated = []
    for index, event in accepted_events:
        row = matched_by_tx.get(event['transaction'].lower())
        if row is not None:
            correlated.append({'event_index': index, 'request_id': event['request_id'],
                               'route': event['route'], 'body_sha256': event['body_sha256'],
                               'transaction': row['transaction'], 'log_index': row['log_index'],
                               'payer': row['payer'], 'amount_atomic': row['amount_atomic'],
                               'block_number': row['block_number']})
    return {'chain_correlated_response_events': len(correlated),
            'correlated_usdc_nominal': transfers['matched_usdc_nominal'],
            'distinct_payer_wallets': len({row['payer'] for row in correlated}),
            'correlated': correlated, 'rejected': rejected, 'min_block_depth': min_depth,
            'limitation': ('The response journal and facilitator-reported payer are seller-side records. '
                           'A matched inbound transfer does not independently prove x402 request attribution, '
                           'client receipt, independent buyers, revenue, or profitability.')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--journal', required=True)
    parser.add_argument('--audit-rpc-url', required=True)
    parser.add_argument('--pay-to', required=True)
    parser.add_argument('--min-depth', type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(audit(read_jsonl(args.journal), AuditRPC(args.audit_rpc_url),
                           args.pay_to, args.min_depth), indent=2))
