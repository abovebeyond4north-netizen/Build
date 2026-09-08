# Passive Income Engine

A self-hosted unattended digital storefront, fulfillment service, SEO surface, conversion-learning loop, and treasury monitor.

## Automation in v2

The service now runs the complete low-risk operating loop inside one container:

- Serves three real offline digital products.
- Publishes dedicated product pages with canonical URLs and Product structured data.
- Publishes three evergreen educational guides with Article structured data.
- Generates `/sitemap.xml`, `/robots.txt`, and `/feed.xml` automatically from the catalog.
- Records first-party product views without third-party analytics scripts.
- Deduplicates product views by visitor/product/day to reduce refresh noise.
- Preserves UTM source, medium, and campaign attribution when a checkout adapter returns `visitor_id` in the signed completed-sale event.
- Uses a Bayesian conversion prior plus an exploration bonus to rotate the storefront's featured product automatically.
- Produces `explore`, `maintain`, `promote`, `revise-offer`, or `review-refunds` recommendations from observed performance.
- Limits autonomous optimization to on-site featured placement; it does not autonomously change prices or send external marketing messages.
- Accepts signed payment-provider webhooks.
- Verifies product ID, server-owned price, currency, and net amount before fulfillment.
- Issues expiring download links after completed-sale events and limits repeated downloads.
- Records sales, product-linked refunds, expenses, attribution, and audit events in SQLite.
- Calculates tax, refund, operating, and permanent cash reserves.
- Computes `payout_ready_cents` only after configured reserve thresholds are satisfied.
- Uses idempotent event IDs to prevent duplicate webhook processing.
- Runs regression tests in GitHub Actions.
- Runs in Docker with persistent `/data` storage.

The treasury monitor intentionally stops at a payout-ready recommendation. It does not execute external transfers automatically.

## Autonomous optimization model

For each product, the engine tracks deduplicated views, completed sales, net revenue, product-linked refunds, Bayesian conversion rate, refund rate, expected net value per view, and an exploration score.

The Bayesian conversion estimate is:

```text
(sales + 1) / (views + 50)
```

This behaves like a small prior near 2% conversion, preventing one or two early events from dominating decisions. The feature selector adds an exploration term so products with little traffic continue receiving opportunities instead of being permanently starved.

Automatic action is deliberately narrow: **choose the featured product on the site's home page**. Price changes, product retirement, and external promotion remain recommendations rather than automatic commercial actions.

## Default treasury policy

- Currency: CAD
- Profit floor: CA$500
- Minimum payout-ready amount: CA$50
- Maximum payout-ready recommendation: CA$1,000
- Tax reserve: 25%
- Refund reserve: 5% of the most recent 60 days of net sales
- Operating reserve: CA$100
- Download-link lifetime: 168 hours
- Maximum downloads per fulfillment link: 8

All values are configurable in `.env`.

## Start

```bash
cd passive-income-engine
cp .env.example .env
# Replace ADMIN_TOKEN and WEBHOOK_SECRET with long random secrets.
docker build -t passive-income-engine .
docker run --restart unless-stopped --env-file .env -p 8000:8000 -v passive-income-data:/data passive-income-engine
```

Set `PUBLIC_BASE_URL` to the final HTTPS origin in production so canonical URLs, structured data, sitemap entries, and RSS links use the correct domain.

Open `http://localhost:8000` during local development.

## Public routes

- `GET /` — storefront; featured product is selected by the optimization engine.
- `GET /products/{product_id}` — indexable product page and first-party product-view measurement.
- `GET /guides` — evergreen content index.
- `GET /guides/{slug}` — indexable educational guide.
- `GET /sitemap.xml` — generated XML sitemap.
- `GET /robots.txt` — crawler policy and sitemap location.
- `GET /feed.xml` — RSS feed for the guide library.
- `GET /go/{product_id}?utm_source=...&utm_medium=...&utm_campaign=...` — attribution-preserving product redirect.
- `GET /download/{token}` — expiring, usage-limited digital fulfillment link.
- `GET /health` — service health and catalog counts.

## Payment-provider webhook contract

Configure the checkout provider or adapter to POST JSON to `/webhooks/payment` and place an HMAC-SHA256 signature of the raw request body in `X-Signature` using `WEBHOOK_SECRET`.

The browser does not supply the authoritative price. The webhook product ID is matched against the server-side catalog before fulfillment.

Completed sale:

```json
{
  "id": "evt_20260908_0001",
  "type": "sale.completed",
  "sale_id": "sale_0001",
  "product_id": "compound-growth-calculator",
  "gross_cents": 900,
  "net_cents": 855,
  "currency": "CAD",
  "visitor_id": "the-bdt_visitor-cookie-value-captured-by-the-checkout-adapter"
}
```

`visitor_id` is optional. When supplied, the engine hashes it and joins the sale back to the first-party UTM session without storing the raw visitor identifier in analytics tables.

Refund:

```json
{
  "id": "evt_20260908_0002",
  "type": "sale.refunded",
  "refund_id": "refund_0001",
  "sale_id": "sale_0001",
  "amount_cents": 900,
  "currency": "CAD"
}
```

Providing `sale_id` on refunds lets the optimizer calculate product-specific refund rates.

## Admin API

Send `Authorization: Bearer <ADMIN_TOKEN>`.

- `GET /admin/treasury` — sales, reserves, and `payout_ready_cents`.
- `GET /admin/optimizer?days=90` — product performance, rankings, and recommendation state.
- `GET /admin/attribution` — sales grouped by source, medium, and campaign.
- `GET /admin/audit?limit=100` — recent audited sale/refund/expense events.
- `POST /admin/expenses` — costs not captured by the payment provider.

Expense request:

```json
{
  "category": "hosting",
  "amount_cents": 2500,
  "note": "September hosting"
}
```

## Testing

```bash
pip install -r requirements.txt
python -m compileall -q engine.py tests
python -m unittest discover -s tests -v
```

The branch also contains `.github/workflows/passive-income-engine.yml`, which runs the same checks when this subsystem changes.

## Production boundary

Keep the payment provider as the source of truth for completed sales and refunds. Do not fulfill from browser-provided prices or unsigned callbacks. Use HTTPS, protect the admin token and webhook secret, keep `/data` backed up, and reconcile `payout_ready_cents` against actual settled funds before making a transfer.

The engine automates owned-site discovery surfaces and on-site placement optimization. It does not send spam, fabricate traffic or reviews, perform deceptive promotion, or autonomously move money.
