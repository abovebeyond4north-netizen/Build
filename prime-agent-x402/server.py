"""x402-paid FastAPI entry point; requires real operator configuration."""
import os
import base64
import json
import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from x402.extensions.bazaar import OutputConfig, declare_discovery_extension
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import PaywallConfig, RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

from delivery_journal import DeliveryJournalASGI
from pricing import PRICES
from prime_agent import BaseRPC, EvidenceStore, Intelligence, NETWORK, valid_address


SERVICE_NAME = "Prime-Agent x402 Intelligence"
SERVICE_TAGS = ["base", "chain-data", "token-metadata", "agent-intelligence", "x402"]

TOKEN_ADDRESS_SCHEMA = {
    "properties": {
        "address": {
            "type": "string",
            "description": "EVM token contract address on Base mainnet.",
            "pattern": "^0x[0-9a-fA-F]{40}$",
        },
    },
    "required": ["address"],
}

SNAPSHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "network": {"type": "string"},
        "block_number": {"type": "integer"},
        "block_hash": {"type": "string"},
        "observed_at": {"type": "integer"},
    },
    "required": ["network", "block_number", "block_hash", "observed_at"],
}

CHAIN_STATUS_EXAMPLE = {
    "network": NETWORK,
    "block_number": 12345678,
    "block_hash": "0x" + "1" * 64,
    "observed_at": 1760000000,
}
CHAIN_STATUS_SCHEMA = SNAPSHOT_SCHEMA

TOKEN_METADATA_EXAMPLE = {
    "network": NETWORK,
    "token": "0x" + "a" * 40,
    "snapshot": CHAIN_STATUS_EXAMPLE,
    "is_contract": True,
    "fields": {"decimals": 18, "symbol": "TOKEN", "name": "Example Token"},
    "evidence_ids": ["example-evidence-id"],
    "missing": [],
}
TOKEN_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "network": {"type": "string"},
        "token": {"type": "string"},
        "snapshot": SNAPSHOT_SCHEMA,
        "is_contract": {"type": "boolean"},
        "fields": {"type": "object"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "network",
        "token",
        "snapshot",
        "is_contract",
        "fields",
        "evidence_ids",
        "missing",
    ],
}

COVERAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "contract": {"type": "boolean"},
        "metadata": {"type": "boolean"},
        "holders": {"type": "boolean"},
        "liquidity": {"type": "boolean"},
        "activity": {"type": "boolean"},
    },
    "required": ["contract", "metadata", "holders", "liquidity", "activity"],
}
TOKEN_CONTEXT_EXAMPLE = {
    **TOKEN_METADATA_EXAMPLE,
    "coverage": {
        "contract": True,
        "metadata": True,
        "holders": False,
        "liquidity": False,
        "activity": False,
    },
}
TOKEN_CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        **TOKEN_METADATA_SCHEMA["properties"],
        "coverage": COVERAGE_SCHEMA,
    },
    "required": [*TOKEN_METADATA_SCHEMA["required"], "coverage"],
}

ROUTE_DETAILS = {
    "GET /chain/status": {
        "description": "Canonical-at-read-time Base mainnet block status with block hash provenance.",
        "extensions": declare_discovery_extension(
            output=OutputConfig(
                example=CHAIN_STATUS_EXAMPLE,
                schema=CHAIN_STATUS_SCHEMA,
            ),
        ),
    },
    "GET /token/metadata/:address": {
        "description": "Base token contract metadata pinned to one canonical-at-read-time block hash.",
        "extensions": declare_discovery_extension(
            path_params_schema=TOKEN_ADDRESS_SCHEMA,
            output=OutputConfig(
                example=TOKEN_METADATA_EXAMPLE,
                schema=TOKEN_METADATA_SCHEMA,
            ),
        ),
    },
    "GET /token/context/:address": {
        "description": "Composed Base token context with evidence IDs and explicit coverage gaps.",
        "extensions": declare_discovery_extension(
            path_params_schema=TOKEN_ADDRESS_SCHEMA,
            output=OutputConfig(
                example=TOKEN_CONTEXT_EXAMPLE,
                schema=TOKEN_CONTEXT_SCHEMA,
            ),
        ),
    },
}


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for paid routes")
    return value


pay_to = valid_address(required("PRIME_PAY_TO"))
facilitator_url = required("PRIME_FACILITATOR_URL")
rpc_url = required("PRIME_BASE_RPC_URL")
db_path = required("PRIME_EVIDENCE_DB")
journal_path = required("PRIME_DELIVERY_JOURNAL")

server = x402ResourceServer(
    HTTPFacilitatorClient(FacilitatorConfig(url=facilitator_url))
)
server.register(NETWORK, ExactEvmServerScheme())

# PaymentMiddlewareASGI in x402 >=2.24 auto-registers the Bazaar resource
# extension whenever a configured route declares extensions.bazaar. The x402
# matcher uses :param syntax; FastAPI handlers below use {param}.
routes = {
    path: RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=pay_to,
                price=price,
                network=NETWORK,
            )
        ],
        mime_type="application/json",
        description=ROUTE_DETAILS[path]["description"],
        service_name=SERVICE_NAME,
        tags=SERVICE_TAGS,
        extensions=ROUTE_DETAILS[path]["extensions"],
    )
    for path, price in PRICES.items()
}

app = FastAPI(
    title=SERVICE_NAME,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    PaymentMiddlewareASGI,
    routes=routes,
    server=server,
    paywall_config=PaywallConfig(
        app_name=SERVICE_NAME,
        testnet=False,
    ),
)
app.add_middleware(
    DeliveryJournalASGI,
    path=journal_path,
    pay_to=pay_to,
    prices=PRICES,
)


@app.get("/", response_class=HTMLResponse)
def landing():
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Prime-Agent x402 Intelligence</title>
  <style>
    body{font-family:system-ui,-apple-system,sans-serif;max-width:720px;margin:48px auto;padding:0 20px;line-height:1.5}
    a.buy{display:inline-block;padding:14px 18px;border:1px solid currentColor;border-radius:10px;text-decoration:none;font-weight:700}
    code{overflow-wrap:anywhere}
  </style>
</head>
<body>
  <h1>Prime-Agent x402 Intelligence</h1>
  <p>Machine-payable Base intelligence via x402. The cheapest live product is chain status at <strong>$0.001 USDC</strong>.</p>
  <p><a class="buy" href="/chain/status">Buy chain status — $0.001 USDC</a></p>
  <p>Opening a paid route in a compatible browser shows the official x402 EVM paywall. Connect a wallet, review the Base mainnet USDC terms, and approve the payment. Never paste a private key into this site.</p>
  <p>Agent endpoint: <code>GET /chain/status</code></p>
</body>
</html>"""


@app.middleware("http")
async def payment_diagnostics(request, call_next):
    """Log only safe x402 outcome metadata; never log payment signatures."""
    had_payment = bool(
        request.headers.get("payment-signature") or request.headers.get("x-payment")
    )
    response = await call_next(request)
    if had_payment:
        reason = None
        if response.status_code == 402:
            encoded = response.headers.get("payment-required")
            if encoded:
                try:
                    payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
                    reason = payload.get("error")
                except Exception:
                    reason = "unreadable_payment_required"
        logging.getLogger("prime_agent.payment").warning(
            "x402 paid_retry path=%s status=%s reason=%s",
            request.url.path,
            response.status_code,
            reason,
        )
    return response


@lru_cache(maxsize=1)
def intelligence():
    return Intelligence(BaseRPC(rpc_url), EvidenceStore(db_path))


def execute(method, *args):
    try:
        return method(*args)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/chain/status")
def chain_status():
    return execute(intelligence().chain_status)


@app.get("/token/metadata/{address}")
def metadata(address: str):
    return execute(intelligence().metadata, address)


@app.get("/token/context/{address}")
def context(address: str):
    return execute(intelligence().token_context, address)
