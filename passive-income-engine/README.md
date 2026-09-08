# Passive Income Engine

A self-hosted unattended storefront, digital fulfillment service, and treasury monitor.

## Current automation

- Serves a small digital-product catalog.
- Accepts signed payment-provider webhooks.
- Verifies product ID, price, and currency before fulfillment.
- Issues expiring download links after completed-sale events.
- Records sales, refunds, and expenses in SQLite.
- Calculates tax, refund, operating, and permanent cash reserves.
- Computes `payout_ready_cents` once profits exceed configured reserve thresholds.
- Uses idempotent event IDs to avoid duplicate fulfillment/accounting.
- Provides an authenticated treasury endpoint.
- Runs in Docker with persistent `/data` storage.

The treasury monitor intentionally stops at a payout-ready recommendation. It does not execute external transfers automatically.

## Default treasury policy

- Currency: CAD
- Profit floor: CA$500
- Minimum payout-ready amount: CA$50
- Maximum payout-ready recommendation: CA$1,000
- Tax reserve: 25%
- Refund reserve: 5% of the most recent 60 days of net sales
- Operating reserve: CA$100

All values are configurable in `.env`.

## Start

```bash
cd passive-income-engine
cp .env.example .env
# Replace ADMIN_TOKEN and WEBHOOK_SECRET with long random secrets.
docker build -t passive-income-engine .
docker run --restart unless-stopped --env-file .env -p 8000:8000 -v passive-income-data:/data passive-income-engine
```

Open `http://localhost:8000`.

## Payment-provider webhook contract

Configure the checkout provider or adapter to POST JSON to `/webhooks/payment` and place an HMAC-SHA256 signature of the raw request body in `X-Signature` using `WEBHOOK_SECRET`.

Completed sale:

```json
{
  "id": "evt_20260908_0001",
  "type": "sale.completed",
  "sale_id": "sale_0001",
  "product_id": "compound-growth-calculator",
  "gross_cents": 900,
  "net_cents": 855,
  "currency": "CAD"
}
```

Refund:

```json
{
  "id": "evt_20260908_0002",
  "type": "sale.refunded",
  "refund_id": "refund_0001",
  "amount_cents": 900,
  "currency": "CAD"
}
```

## Admin API

Send `Authorization: Bearer <ADMIN_TOKEN>`.

- `GET /admin/treasury` returns sales, reserves, and `payout_ready_cents`.
- `POST /admin/expenses` records costs not captured by the payment provider.
- `GET /health` is an unauthenticated health check.

Expense request:

```json
{
  "category": "hosting",
  "amount_cents": 2500,
  "note": "September hosting"
}
```

## Production boundary

Keep the payment provider as the source of truth for completed sales and refunds. Do not fulfill from browser-provided prices or unsigned callbacks. Use HTTPS, protect the admin token and webhook secret, keep the database volume backed up, and reconcile `payout_ready_cents` against actual settled funds before making a transfer.
