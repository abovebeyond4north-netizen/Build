"""x402-paid FastAPI entry point; requires real operator configuration."""
import os
from functools import lru_cache
from fastapi import FastAPI, HTTPException
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer
from prime_agent import BaseRPC, EvidenceStore, Intelligence, NETWORK, valid_address
from delivery_journal import DeliveryJournalASGI
from pricing import PRICES


def required(name):
    value = os.environ.get(name, '').strip()
    if not value: raise RuntimeError(f'{name} is required for paid routes')
    return value

pay_to = valid_address(required('PRIME_PAY_TO'))
facilitator_url = required('PRIME_FACILITATOR_URL')
rpc_url = required('PRIME_BASE_RPC_URL')
db_path = required('PRIME_EVIDENCE_DB')
journal_path = required('PRIME_DELIVERY_JOURNAL')
server = x402ResourceServer(HTTPFacilitatorClient(FacilitatorConfig(url=facilitator_url)))
server.register(NETWORK, ExactEvmServerScheme())
# The x402 matcher uses :param syntax; FastAPI handlers below use {param}.
routes = {path: RouteConfig(
    accepts=[PaymentOption(scheme='exact', pay_to=pay_to, price=price, network=NETWORK)],
    mime_type='application/json', description='Prime-Agent Base chain intelligence')
    for path, price in PRICES.items()}
app = FastAPI(title='Prime-Agent x402 Intelligence', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
app.add_middleware(DeliveryJournalASGI, path=journal_path, pay_to=pay_to, prices=PRICES)

@lru_cache(maxsize=1)
def intelligence(): return Intelligence(BaseRPC(rpc_url), EvidenceStore(db_path))

def execute(method, *args):
    try: return method(*args)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc

@app.get('/chain/status')
def chain_status(): return execute(intelligence().chain_status)

@app.get('/token/metadata/{address}')
def metadata(address: str): return execute(intelligence().metadata, address)

@app.get('/token/context/{address}')
def context(address: str): return execute(intelligence().token_context, address)
