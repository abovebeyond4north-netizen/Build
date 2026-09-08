from __future__ import annotations

import html
import json
import os
import secrets
import sqlite3
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import engine

app = engine.app

PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox").lower()
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")
PAYPAL_API_BASE = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"
PAYPAL_SDK_BASE = "https://www.paypal.com" if PAYPAL_MODE == "live" else "https://www.sandbox.paypal.com"

_token_value = ""
_token_expires_at = 0.0


class CheckoutRequest(BaseModel):
    product_id: str


def _cents(value: str) -> int:
    return int((Decimal(value) * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _init_paypal_tables() -> None:
    with engine.db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS paypal_orders(
            order_id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            visitor_hash TEXT NOT NULL,
            capture_id TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            captured_at TEXT
        );
        CREATE TABLE IF NOT EXISTS paypal_events(
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            received_at TEXT NOT NULL
        );
        """)


_init_paypal_tables()


async def _access_token() -> str:
    global _token_value, _token_expires_at
    if _token_value and time.time() < _token_expires_at - 60:
        return _token_value
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(503, "PayPal checkout is not configured")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{PAYPAL_API_BASE}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
        )
    if response.status_code >= 400:
        engine.audit("paypal.oauth_failed", {"status": response.status_code})
        raise HTTPException(502, "PayPal authentication failed")
    payload = response.json()
    _token_value = payload["access_token"]
    _token_expires_at = time.time() + int(payload.get("expires_in", 300))
    return _token_value


async def paypal_request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    request_id: str | None = None,
) -> dict:
    token = await _access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if request_id:
        headers["PayPal-Request-Id"] = request_id[:108]
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.request(
            method,
            f"{PAYPAL_API_BASE}{path}",
            headers=headers,
            json=body,
        )
    if response.status_code >= 400:
        detail = ""
        try:
            detail = response.json().get("name", "")
        except Exception:
            pass
        engine.audit("paypal.api_error", {"method": method, "path": path, "status": response.status_code, "name": detail})
        raise HTTPException(502, f"PayPal API request failed ({response.status_code})")
    return response.json() if response.content else {}


def _capture_from_order(order: dict) -> dict:
    units = order.get("purchase_units") or []
    if len(units) != 1:
        raise HTTPException(409, "Unexpected PayPal purchase-unit count")
    captures = units[0].get("payments", {}).get("captures", [])
    completed = [capture for capture in captures if capture.get("status") == "COMPLETED"]
    if not completed:
        raise HTTPException(409, "PayPal order is not completed")
    return completed[-1]


def _validate_capture(product_id: str, order: dict, capture: dict) -> tuple[int, int]:
    product = engine.PRODUCTS[product_id]
    units = order.get("purchase_units") or []
    if len(units) != 1:
        raise HTTPException(409, "Unexpected PayPal purchase-unit count")
    unit = units[0]
    server_product_id = unit.get("custom_id") or unit.get("reference_id")
    if server_product_id != product_id:
        raise HTTPException(409, "PayPal product binding mismatch")
    amount = capture.get("amount", {})
    gross = _cents(str(amount.get("value", "-1")))
    if amount.get("currency_code") != engine.CURRENCY or gross != product["price_cents"]:
        raise HTTPException(409, "PayPal captured amount does not match the catalog")
    breakdown = capture.get("seller_receivable_breakdown", {})
    net_amount = breakdown.get("net_amount", {})
    if net_amount.get("currency_code") == engine.CURRENCY and net_amount.get("value") is not None:
        net = _cents(str(net_amount["value"]))
    else:
        fee = breakdown.get("paypal_fee", {})
        fee_cents = _cents(str(fee.get("value", "0"))) if fee.get("currency_code") == engine.CURRENCY else 0
        net = max(0, gross - fee_cents)
    if net < 0 or net > gross:
        raise HTTPException(409, "Invalid PayPal settlement amount")
    return gross, net


def fulfill_paypal_capture(order_id: str, order: dict, capture: dict) -> str:
    with engine.db() as con:
        local = con.execute("SELECT * FROM paypal_orders WHERE order_id=?", (order_id,)).fetchone()
    if not local:
        raise HTTPException(404, "Unknown PayPal order")
    product_id = local["product_id"]
    _, net = _validate_capture(product_id, order, capture)
    capture_id = str(capture.get("id", ""))
    if not capture_id:
        raise HTTPException(409, "Missing PayPal capture id")

    token = secrets.token_urlsafe(32)
    token_hash = engine.hashlib.sha256(token.encode()).hexdigest()
    expires = (engine.datetime.now(engine.timezone.utc) + engine.timedelta(hours=engine.DOWNLOAD_TTL_HOURS)).isoformat()
    now = engine.utcnow()

    with engine.db() as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "INSERT OR IGNORE INTO sales(id,product_id,net_cents,currency,created_at) VALUES(?,?,?,?,?)",
            (capture_id, product_id, net, engine.CURRENCY, now),
        )
        con.execute("DELETE FROM deliveries WHERE sale_id=?", (capture_id,))
        con.execute(
            "INSERT INTO deliveries(token_hash,sale_id,product_id,expires_at,downloads) VALUES(?,?,?,?,0)",
            (token_hash, capture_id, product_id, expires),
        )
        session = con.execute(
            "SELECT source,medium,campaign FROM visitor_sessions WHERE visitor_hash=?",
            (local["visitor_hash"],),
        ).fetchone()
        if session:
            con.execute(
                "INSERT OR REPLACE INTO sale_attribution(sale_id,source,medium,campaign,created_at) VALUES(?,?,?,?,?)",
                (capture_id, session["source"], session["medium"], session["campaign"], now),
            )
        con.execute(
            "UPDATE paypal_orders SET capture_id=?,status='COMPLETED',captured_at=? WHERE order_id=?",
            (capture_id, now, order_id),
        )
        con.execute("COMMIT")
    engine.audit("paypal.capture_completed", {"order_id": order_id, "capture_id": capture_id, "product_id": product_id, "net_cents": net})
    return token


def _checkout_script(product_id: str) -> str:
    if not PAYPAL_CLIENT_ID:
        return "<p class='badge'>Checkout is in setup mode. Configure PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.</p>"
    sdk_url = f"{PAYPAL_SDK_BASE}/web-sdk/v6/core"
    escaped_id = json.dumps(PAYPAL_CLIENT_ID)
    escaped_product = json.dumps(product_id)
    currency = json.dumps(engine.CURRENCY)
    return f"""
    <section id='checkout'><h2>Secure checkout</h2><div id='paypal-button-container'></div><p id='checkout-message' role='status'></p></section>
    <script>
    async function onPayPalLoaded() {{
      const message = document.getElementById('checkout-message');
      try {{
        const sdk = await window.paypal.createInstance({{
          clientId: {escaped_id}, components: ['paypal-payments'], pageType: 'checkout'
        }});
        const methods = await sdk.findEligibleMethods({{currencyCode: {currency}}});
        if (!methods.isEligible('paypal')) {{ message.textContent = 'PayPal is not available for this browser or region.'; return; }}
        const button = document.createElement('paypal-button');
        button.setAttribute('type', 'pay');
        document.getElementById('paypal-button-container').append(button);
        const session = sdk.createPayPalOneTimePaymentSession({{
          onApprove: async (data) => {{
            message.textContent = 'Confirming payment and preparing your download…';
            const response = await fetch('/api/paypal/orders/' + encodeURIComponent(data.orderId) + '/capture', {{method:'POST'}});
            const result = await response.json();
            if (!response.ok || !result.download_url) throw new Error(result.detail || 'Capture failed');
            window.location.assign(result.download_url);
          }},
          onCancel: () => {{ message.textContent = 'Checkout canceled. No download was issued.'; }},
          onError: () => {{ message.textContent = 'Checkout could not be completed. Please try again.'; }}
        }});
        button.addEventListener('click', async () => {{
          message.textContent = '';
          const orderPromise = fetch('/api/paypal/orders', {{
            method:'POST', headers:{{'Content-Type':'application/json'}},
            body:JSON.stringify({{product_id:{escaped_product}}})
          }}).then(async r => {{ const data = await r.json(); if(!r.ok) throw new Error(data.detail || 'Order creation failed'); return data.order_id; }});
          await session.start({{presentationMode:'auto'}}, orderPromise);
        }});
      }} catch (error) {{
        console.error(error); message.textContent = 'Checkout is temporarily unavailable.';
      }}
    }}
    </script>
    <script async src='{html.escape(sdk_url, quote=True)}' onload='onPayPalLoaded()'></script>
    """


# Replace the catalog product-page route with a checkout-enabled version.
app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/products/{product_id}"]


@app.get("/products/{product_id}", response_class=HTMLResponse)
def paypal_product_page(product_id: str, request: Request):
    product = engine.PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    response = HTMLResponse("")
    vh = engine.record_session(request, response)
    engine.record_product_view(product_id, vh)
    checkout = _checkout_script(product_id)
    body = (
        f"<main><span class='badge'>Instant digital download</span>"
        f"<h1>{html.escape(product['name'])}</h1><p>{html.escape(product['description'])}</p>"
        f"<p class='price'>{engine.cents(product['price_cents'])}</p>{checkout}"
        f"<h2>Designed for</h2><ul>{''.join(f'<li>{html.escape(k)}</li>' for k in product['keywords'])}</ul>"
        f"<p><a href='/guides'>Read the free guides</a></p></main>"
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product["name"],
        "description": product["description"],
        "offers": {
            "@type": "Offer",
            "priceCurrency": engine.CURRENCY,
            "price": f"{product['price_cents']/100:.2f}",
            "availability": "https://schema.org/InStock",
            "url": f"{engine.PUBLIC_BASE_URL}/products/{product_id}",
        },
    }
    response.body = engine.page_shell(
        product["name"], product["description"], f"{engine.PUBLIC_BASE_URL}/products/{product_id}", body, schema
    ).encode()
    response.headers["content-length"] = str(len(response.body))
    return response


@app.post("/api/paypal/orders")
async def create_paypal_order(request: Request, checkout: CheckoutRequest):
    product = engine.PRODUCTS.get(checkout.product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    raw_visitor = request.cookies.get("bdt_visitor") or secrets.token_urlsafe(24)
    vh = engine.visitor_hash(raw_visitor)
    value = f"{Decimal(product['price_cents']) / Decimal(100):.2f}"
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": checkout.product_id,
            "custom_id": checkout.product_id,
            "description": product["description"][:127],
            "amount": {
                "currency_code": engine.CURRENCY,
                "value": value,
                "breakdown": {"item_total": {"currency_code": engine.CURRENCY, "value": value}},
            },
            "items": [{
                "name": product["name"][:127],
                "description": product["description"][:127],
                "unit_amount": {"currency_code": engine.CURRENCY, "value": value},
                "quantity": "1",
                "category": "DIGITAL_GOODS",
            }],
        }],
        "payment_source": {"paypal": {"experience_context": {"shipping_preference": "NO_SHIPPING", "user_action": "PAY_NOW"}}},
    }
    data = await paypal_request("POST", "/v2/checkout/orders", body=body, request_id=f"create-{checkout.product_id}-{uuid.uuid4()}")
    order_id = str(data.get("id", ""))
    if not order_id:
        raise HTTPException(502, "PayPal did not return an order id")
    with engine.db() as con:
        con.execute(
            "INSERT INTO paypal_orders(order_id,product_id,visitor_hash,status,created_at) VALUES(?,?,?,?,?)",
            (order_id, checkout.product_id, vh, "CREATED", engine.utcnow()),
        )
    engine.audit("paypal.order_created", {"order_id": order_id, "product_id": checkout.product_id})
    return {"order_id": order_id}


@app.post("/api/paypal/orders/{order_id}/capture")
async def capture_paypal_order(order_id: str):
    with engine.db() as con:
        local = con.execute("SELECT * FROM paypal_orders WHERE order_id=?", (order_id,)).fetchone()
    if not local:
        raise HTTPException(404, "Unknown PayPal order")

    try:
        order = await paypal_request(
            "POST", f"/v2/checkout/orders/{order_id}/capture", body={}, request_id=f"capture-{order_id}"
        )
    except HTTPException:
        # A client retry can arrive after PayPal already captured the order. Retrieve the
        # authoritative order state and fulfill only if a completed capture exists.
        order = await paypal_request("GET", f"/v2/checkout/orders/{order_id}")
    capture = _capture_from_order(order)
    token = fulfill_paypal_capture(order_id, order, capture)
    return {"status": "COMPLETED", "download_url": f"/download/{token}"}


async def _verify_paypal_webhook(request: Request, event: dict) -> bool:
    if not PAYPAL_WEBHOOK_ID:
        return False
    headers = {key.lower(): value for key, value in request.headers.items()}
    verification = {
        "transmission_id": headers.get("paypal-transmission-id", ""),
        "transmission_time": headers.get("paypal-transmission-time", ""),
        "cert_url": headers.get("paypal-cert-url", ""),
        "auth_algo": headers.get("paypal-auth-algo", ""),
        "transmission_sig": headers.get("paypal-transmission-sig", ""),
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": event,
    }
    data = await paypal_request("POST", "/v1/notifications/verify-webhook-signature", body=verification)
    return data.get("verification_status") == "SUCCESS"


@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    try:
        event = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not await _verify_paypal_webhook(request, event):
        raise HTTPException(401, "Invalid PayPal webhook signature")
    event_id = str(event.get("id", ""))
    event_type = str(event.get("event_type", ""))
    if not event_id:
        raise HTTPException(400, "Missing PayPal event id")
    try:
        with engine.db() as con:
            con.execute(
                "INSERT INTO paypal_events(event_id,event_type,received_at) VALUES(?,?,?)",
                (event_id, event_type, engine.utcnow()),
            )
    except sqlite3.IntegrityError:
        return {"status": "duplicate"}

    if event_type == "PAYMENT.CAPTURE.REFUNDED":
        resource = event.get("resource", {})
        refund_id = str(resource.get("id", ""))
        amount = resource.get("amount", {})
        amount_cents = _cents(str(amount.get("value", "-1")))
        if amount.get("currency_code") != engine.CURRENCY or amount_cents <= 0:
            raise HTTPException(409, "Unexpected PayPal refund currency or amount")
        related = resource.get("supplementary_data", {}).get("related_ids", {})
        capture_id = str(related.get("capture_id", "")) or None
        product_id = None
        if capture_id:
            with engine.db() as con:
                sale = con.execute("SELECT product_id FROM sales WHERE id=?", (capture_id,)).fetchone()
                product_id = sale["product_id"] if sale else None
                con.execute(
                    "INSERT OR IGNORE INTO refunds(id,amount_cents,currency,created_at,sale_id,product_id) VALUES(?,?,?,?,?,?)",
                    (refund_id, amount_cents, engine.CURRENCY, engine.utcnow(), capture_id, product_id),
                )
        engine.audit("paypal.refund_recorded", {"refund_id": refund_id, "capture_id": capture_id, "amount_cents": amount_cents})
    return {"status": "ok"}


# Version marker for health checks and operational inspection.
for route in app.routes:
    if getattr(route, "path", None) == "/health":
        original_health_endpoint = route.endpoint
        break
else:
    original_health_endpoint = None

if original_health_endpoint:
    app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/health"]

    @app.get("/health")
    def checkout_health():
        result = original_health_endpoint()
        result["version"] = "3.0.0"
        result["paypal_checkout"] = bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)
        result["paypal_mode"] = PAYPAL_MODE
        return result
