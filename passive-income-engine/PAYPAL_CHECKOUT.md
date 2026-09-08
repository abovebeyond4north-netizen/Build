# PayPal Checkout Integration

The production application runs through `checkout_app.py`, which extends the passive-income engine with PayPal Web SDK v6 and the PayPal Orders v2 API.

This integration accepts customer-initiated one-time purchases. It does **not** implement PayPal Payouts or autonomous external transfers.

## Security model

- Product prices are defined only in the server-side `PRODUCTS` catalog.
- The browser sends a product ID, never an authoritative amount.
- The server creates the PayPal order with the catalog amount and currency.
- Every PayPal order is persisted and bound to its product and visitor attribution before capture.
- A completed capture must match the stored product, catalog amount, and currency before fulfillment.
- PayPal capture IDs are the sale IDs in the accounting ledger, providing idempotency.
- Capture retries retrieve PayPal's authoritative order state instead of charging a second time.
- Refund events are accepted only through a PayPal-signature-verified webhook.
- Client secrets and webhook IDs remain server-side environment variables.

## Sandbox setup

Create a PayPal REST application and use its sandbox credentials:

```text
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=<sandbox REST app client ID>
PAYPAL_CLIENT_SECRET=<sandbox REST app client secret>
PAYPAL_WEBHOOK_ID=<sandbox webhook ID>
```

Set the webhook listener URL to:

```text
https://YOUR-DOMAIN/webhooks/paypal
```

Subscribe at minimum to:

```text
PAYMENT.CAPTURE.REFUNDED
```

The checkout capture itself is synchronous through Orders v2. The refund webhook keeps the accounting ledger synchronized after a later PayPal refund.

Start the hardened stack:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

Open a product page and use a PayPal sandbox buyer account to complete an end-to-end purchase. Verify that:

1. PayPal shows the exact server catalog amount.
2. The capture completes.
3. The browser is redirected to an expiring download URL.
4. `/admin/treasury` records the sale net of PayPal fees when settlement details are present.
5. `/admin/attribution` includes the originating UTM campaign when one was present.
6. Repeating the capture request does not create another PayPal charge.
7. A sandbox refund arrives at `/webhooks/paypal` and reduces treasury profit.

## Live transition

Only after sandbox validation:

```text
PAYPAL_MODE=live
PAYPAL_CLIENT_ID=<live REST app client ID>
PAYPAL_CLIENT_SECRET=<live REST app client secret>
PAYPAL_WEBHOOK_ID=<live webhook ID>
PUBLIC_BASE_URL=https://YOUR-DOMAIN
```

Recreate the webhook under the live PayPal REST application. Sandbox webhook IDs are not interchangeable with live webhook IDs.

## Routes

- `POST /api/paypal/orders` — creates one PayPal order from a server-owned product ID.
- `POST /api/paypal/orders/{order_id}/capture` — captures and validates an approved order, then issues the download.
- `POST /webhooks/paypal` — verifies PayPal webhook signatures and reconciles refunds.
- `GET /products/{product_id}` — renders PayPal Web SDK v6 checkout when credentials are configured.
- `GET /health` — reports whether PayPal Checkout is configured and whether sandbox or live mode is active.

## Operational boundary

The merchant credentials authorize the store to accept purchases selected and approved by buyers. They are not used for Payouts. The separate treasury component continues to calculate `payout_ready_cents` without initiating transfers.
