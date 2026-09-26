"""x402-paid FastAPI entry point; requires real operator configuration."""
import os
import base64
import json
import logging
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
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
PUBLIC_BASE_URL = os.environ.get(
    "PRIME_PUBLIC_URL",
    "https://prime-agent-x402-intelligence.onrender.com",
).rstrip("/")
MCP_SERVER_NAME = "io.github.abovebeyond4north-netizen/prime-agent-x402-intelligence"

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
        "tags": ["base", "block-status", "canonical-data", "provenance", "rpc"],
        "extensions": declare_discovery_extension(
            output=OutputConfig(
                example=CHAIN_STATUS_EXAMPLE,
                schema=CHAIN_STATUS_SCHEMA,
            ),
        ),
    },
    "GET /token/metadata/:address": {
        "description": "Base ERC-20 contract metadata pinned to one canonical-at-read-time block hash.",
        "tags": ["base", "erc20", "token-metadata", "contract", "provenance"],
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
        "tags": ["base", "token-context", "evidence", "coverage", "agent-intelligence"],
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
        tags=ROUTE_DETAILS[path]["tags"],
        extensions=ROUTE_DETAILS[path]["extensions"],
    )
    for path, price in PRICES.items()
}


def product_catalog(base_url: str) -> dict:
    base_url = base_url.rstrip("/")
    products = []
    for route, price in PRICES.items():
        method, template = route.split(" ", 1)
        http_template = template.replace(":address", "{address}")
        products.append({
            "id": route.lower().replace(" ", ":").replace("/", ".").replace(":", "-"),
            "method": method,
            "route_template": template,
            "purchase_url_template": base_url + http_template,
            "price_usd": price.removeprefix("$"),
            "currency": "USDC",
            "network": NETWORK,
            "scheme": "exact",
            "description": ROUTE_DETAILS[route]["description"],
            "tags": ROUTE_DETAILS[route]["tags"],
            "paid": True,
        })
    return {
        "service": SERVICE_NAME,
        "version": "0.2.0",
        "base_url": base_url,
        "network": NETWORK,
        "payment_protocol": "x402-v2",
        "products": products,
        "mcp": {
            "transport": "streamable-http",
            "url": base_url + "/mcp/",
            "purpose": "Free product discovery and quoting; paid intelligence remains on x402 HTTP routes.",
        },
    }


mcp_server = MCPServer(
    name=MCP_SERVER_NAME,
    title=SERVICE_NAME,
    description="Discover and quote x402-paid Base intelligence products.",
    instructions=(
        "Use these tools to discover Prime-Agent products and prices. "
        "The MCP tools do not bypass payment; purchase the returned x402 HTTP URL."
    ),
    website_url=PUBLIC_BASE_URL,
    version="0.2.0",
)


@mcp_server.tool()
def list_products() -> dict:
    """List Prime-Agent x402 products, prices, capabilities, and purchase URL templates."""
    return product_catalog(PUBLIC_BASE_URL)


@mcp_server.tool()
def quote_token_product(product: str, address: str | None = None) -> dict:
    """Quote one product and return the exact x402 purchase URL without spending funds."""
    aliases = {
        "chain_status": "GET /chain/status",
        "token_metadata": "GET /token/metadata/:address",
        "token_context": "GET /token/context/:address",
    }
    route = aliases.get(product)
    if route is None:
        raise ValueError("product must be chain_status, token_metadata, or token_context")
    if ":address" in route:
        if address is None:
            raise ValueError("address is required for token products")
        address = valid_address(address)
    _, template = route.split(" ", 1)
    url = PUBLIC_BASE_URL + template.replace(":address", address or "")
    return {
        "product": product,
        "url": url,
        "price_usd": PRICES[route].removeprefix("$"),
        "currency": "USDC",
        "network": NETWORK,
        "scheme": "exact",
        "description": ROUTE_DETAILS[route]["description"],
        "tags": ROUTE_DETAILS[route]["tags"],
        "spends_funds": False,
        "next_step": "Issue an x402-capable GET to the quoted URL and authorize only under the buyer's own budget policy.",
    }


mcp_http_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "prime-agent-x402-intelligence.onrender.com",
            "prime-agent-x402-intelligence.onrender.com:*",
            "testserver",
            "testserver:*",
            "localhost:*",
            "127.0.0.1:*",
        ],
        allowed_origins=[
            "https://prime-agent-x402-intelligence.onrender.com",
            "http://testserver",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
    ),
)


@asynccontextmanager
async def app_lifespan(_app):
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title=SERVICE_NAME,
    version="0.2.0",
    description="x402-paid Base intelligence with free machine-readable discovery.",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=app_lifespan,
)
app.mount("/mcp", mcp_http_app)

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


@app.get("/catalog")
def catalog(request: Request):
    """Free product catalog; contains no paid chain intelligence."""
    return product_catalog(str(request.base_url).rstrip("/"))


@app.get("/capabilities.json")
def capabilities(request: Request):
    return product_catalog(str(request.base_url).rstrip("/"))


@app.get("/.well-known/ai-catalog.json")
def ai_catalog(request: Request):
    return product_catalog(str(request.base_url).rstrip("/"))


@app.get("/server.json")
def mcp_server_json():
    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": MCP_SERVER_NAME,
        "title": SERVICE_NAME,
        "description": "Discover and quote x402-paid Base intelligence products.",
        "version": "0.2.0",
        "websiteUrl": PUBLIC_BASE_URL,
        "repository": {
            "url": "https://github.com/abovebeyond4north-netizen/Build",
            "source": "github",
            "subfolder": "prime-agent-x402",
        },
        "remotes": [
            {
                "type": "streamable-http",
                "url": PUBLIC_BASE_URL + "/mcp/",
            }
        ],
    }


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    return f"""# {SERVICE_NAME}

Machine-payable Base intelligence using x402 v2 exact USDC payments.

Free discovery:
- Catalog: {PUBLIC_BASE_URL}/catalog
- OpenAPI: {PUBLIC_BASE_URL}/openapi.json
- MCP: {PUBLIC_BASE_URL}/mcp/
- MCP Registry metadata: {PUBLIC_BASE_URL}/server.json
- AI catalog: {PUBLIC_BASE_URL}/.well-known/ai-catalog.json

Paid products:
- GET /chain/status — $0.001 USDC — canonical Base block status with provenance
- GET /token/metadata/{{address}} — $0.003 USDC — Base ERC-20 metadata pinned to one block hash
- GET /token/context/{{address}} — $0.009 USDC — composed evidence-bearing token context

The MCP tools are discovery/quotation tools only and do not bypass x402 payment.
Never send a private key to this service.
"""


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


@app.get("/health/rpc")
def rpc_health():
    try:
        rpc = intelligence().rpc
        snapshot = rpc.snapshot()
        decimals = rpc.token_call(
            "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
            "0x313ce567",
            snapshot,
        )
        if decimals.lower() != "0x" + (6).to_bytes(32, "big").hex():
            raise RuntimeError("unexpected Base USDC decimals response")
        return {"ok": True, "network": NETWORK, "eip1898": True}
    except RuntimeError as exc:
        raise HTTPException(503, "Base RPC health check failed") from exc


@app.get("/chain/status")
def chain_status():
    return execute(intelligence().chain_status)


@app.get("/token/metadata/{address}")
def metadata(address: str):
    return execute(intelligence().metadata, address)


@app.get("/token/context/{address}")
def context(address: str):
    return execute(intelligence().token_context, address)
