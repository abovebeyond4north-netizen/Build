"""Independent offline evaluator of confirmed settlement exports and actual costs."""
import argparse
import json
from decimal import Decimal, InvalidOperation

def reconcile(receipts, costs):
    revenue = Decimal('0')
    expenses = Decimal('0')
    paid = set()
    payers = set()
    duplicates = []
    unsettled = 0
    for receipt in receipts:
        if receipt.get('status') != 'settled' or not receipt.get('transaction'):
            unsettled += 1
            continue
        key = (receipt.get('network'), receipt['transaction'])
        if key in paid:
            duplicates.append(receipt['transaction'])
            continue
        try: amount = Decimal(str(receipt['amount_usd']))
        except (KeyError, InvalidOperation) as exc: raise ValueError('invalid settled amount') from exc
        if amount <= 0 or not receipt.get('payer'): raise ValueError('missing positive amount or payer')
        paid.add(key)
        revenue += amount
        payers.add((receipt.get('network'), receipt['payer'].lower()))
    for cost in costs:
        try: value = Decimal(str(cost['amount_usd']))
        except (KeyError, InvalidOperation) as exc: raise ValueError('invalid cost') from exc
        if value < 0: raise ValueError('negative cost')
        expenses += value
    return {'settled_revenue_usd':str(revenue), 'attributed_cost_usd':str(expenses),
            'contribution_usd':str(revenue-expenses), 'distinct_payer_wallets':len(payers),
            'settled_receipts':len(paid), 'unsettled_records':unsettled,
            'duplicate_transactions':duplicates,
            'caveat':'Exports require independent chain confirmation; wallet count is not independent buyers.'}

def read_jsonl(path):
    with open(path, encoding='utf-8') as f: return [json.loads(line) for line in f if line.strip()]

if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--receipts', required=True)
    cli.add_argument('--costs', required=True)
    args = cli.parse_args()
    print(json.dumps(reconcile(read_jsonl(args.receipts), read_jsonl(args.costs)), indent=2))
