"""x402-paid FastAPI entry point; requires real operator configuration."""
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from x402.extensions.bazaar import OutputConfig, declare_discovery_extension
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

from delivery_journal import DeliveryJournalASGI
from pricing import PRICES
from prime_agent import BaseRPC, EvidenceStore, Intelligence, NETWORK, valid_address


SERVICE_NAME = 'Prime-Agent x402 Intelligence'
SERVICE_TAGS = ['base', 'chain-data', 'token-metadata', 'agent-intelligence', 'x402']
TOKEN_ADDRESS_SCHEMA = {
    'properties': {
        'address': {
            'type': 'string',
            'description': 'EVM token contract address on Base mainnet.',
            'pattern': '^0x[0-9a-fA-F]{40}$',
        },
    },
    'required': ['address'],
}
SNAPSHOT_SCHEMA = {
    'type': 'object',
    'properties': {
        'network': {'type': 'string'},
        'block_number': {'type': 'integer'},
        'block_hash': {'type': 'string'},
        'observed_at': {'type': 'integer'},
    },
    'required': ['network', 'block_number', 'block_hash', 'observed_at'],
}
CHAIN_STATUS_OUTPUT = OutputConfig(
    example={
        'network': NETWORK,
        'block_number': 12345678,
        'block_hash': '0x' + '1' * 64,
        'observed_at': 1760000000,
    },
    schema=SNAPSHOT_SCHEMA,
)
TOKEN_METADATA_OUTPUT = OutputConfig(
    example={
        'network': NETWORK,
        'token': '0x' + 'a' * 40,
        'snapshot': {
            'network': NETWORK,
            'block_number': 12345678,
            'block_hash': '0x' + '1' * 64,
            'observed_at': 1760000000,
        },
        'is_contract': True,
        'fields': {'decimals': 18, 'symbol': 'TOKEN', 'name': 'Example Token'},
        'evidence_ids': ['example-evidence-id'],
        'missing': [],
    },
    schema={
        'type': 'object',
        'properties': {
            'network': {'type': 'string'},
            'token': {'type': 'string'},
            'snapshot': SNAPSHOT_SCHEMA,
            'is_contract': {'type': 'boolean'},
            'fields': {'type': 'object'},
            'evidence_ids': {'type': 'array', 'items': {'type': 'string'}},
            'missing': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['network', 'token', 'snapshot', 'is_contract', 'fields', 'evidence_ids', 'missing'],
    },
)
TOKEN_CONTEXT_OUTPUT = OutputConfig(
    example={
        **TOKEN_METADATA_OUTPUT.example,
        'coverage': {
            'contract': True,
            'metadata': True,
            'holders': False,
            'liquidity': False,
            'activity': False,
        },
    },
    schema={
        'type': 'object',
        'properties': {
            **TOKEN_METADATA_OUTPUT.schema['properties'],
            'coverage': {
                'type': 'object',
                'properties': {
                    'contract': {'type': 'boolean'},
                    'metadata': {'type': 'boolean'},
                    'holders': {'type': 'boolean'},
                    'liquidity': {'type': 'boolean'},
                    'activity': {'type': 'boolean'},
                },
                'required': ['contract', 'metadata', 'holders', 'liquidity', 'activity'],
            },
        },
        'required': TOKEN_METADATA_OUTPUT.schema['required'] + ['coverage'],
    },
)
ROUTE_DETAILS = {
    'GET /chain/status': {
        'description': 'Canonical-at-read-time Base mainnet block status with block hash provenance.',
        'extensions': declare_discovery_extension(output=CHAIN_STATUS_OUTPUT),
    },
    'GET /token/metadata/:address': {
        'description': 'Base token contract metadata pinned to one canonical-at-read-time block hash.',
        'extensions': declare_discovery_extension(
            path_params_schema=TOKEN_ADDRESS_SCHEMA,
            output=TOKEN_METADATA_OUTPUT,
        ),
    },
    'GET /token/context/:address': {
        'description': 'Composed Base token context with evidence IDs and explicit coverage gaps.',
        'extensions': declare_discovery_extension(
            path_params_schema=TOKEN_ADDRESS_SCHEMA,
            output=TOKEN_CONTEXT_OUTPUT,
        ),
    },
}


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(f'{name} is required for paid routes')
    return value


pay_to = valid_address(required('PRIME_PAY_TO'))
facilitator_url = required('PRIME_FACILITATOR_URL')
rpc_url = required('PRIME_BASE_RPC_URL')
db_path = required('PRIME_EVIDENCE_DB')
journal_path = required('PRIME_DELIVERY_JOURNAL')
server = x402ResourceServer(HTTPFacilitatorClient(FacilitatorConfig(url=facilitator_url)))
server.register(NETWORK, ExactEvmServerScheme())
# The x402 matcher uses :param syntax; FastAPI handlers below use {param}.
routes = {
    path: RouteConfig(
        accepts=[PaymentOption(scheme='exact', pay_to=pay_to, price=price, network=NETWORK)],
        mime_type='application/json',
        description=ROUTE_DETAILS[path]['description'],
        service_name=SERVICE_NAME,
        tags=SERVICE_TAGS,
        extensions=ROUTE_DETAILS[path]['extensions'],
    )
    for path, price in PRICES.items()
}
app = FastAPI(title='Prime-Agent x402 Intelligence', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
app.add_middleware(DeliveryJournalASGI, path=journal_path, pay_to=pay_to, prices=PRICES)


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


@app.get('/chain/status')
def chain_status():
    return execute(intelligence().chain_status)


@app.get('/token/metadata/{address}')
def metadata(address: str):
    return execute(intelligence().metadata, address)


@app.get('/token/context/{address}')
def context(address: str):
    return execute(intelligence().token_context, address)
