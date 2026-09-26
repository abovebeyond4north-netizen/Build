# Prime-Agent x402 Intelligence: first slice

Three configured paid Base routes (`/chain/status`, `/token/metadata/{address}`, and `/token/context/{address}`) share a SQLite evidence cache. The context response explicitly marks holder, liquidity, and activity coverage as absent. An offline `/token/verdict` function returns `insufficient_evidence`; it is **not offered as a paid route** until those sources exist. No simulated payment is counted as revenue.

## Local core test

Run `python3 -m unittest discover -s tests -v` in this directory. No third-party libraries are needed for the core or evaluator. After installing `requirements.txt` and `httpx2`, run `python3 -m unittest discover -s tests/integration -v` to verify the unpaid x402 challenge using a local fake facilitator. The test sends no blockchain transaction.

## Paid server

Install `requirements.txt` in a Python 3.11+ environment. Set `PRIME_PAY_TO` to the operator's real Base address, `PRIME_FACILITATOR_URL` to a facilitator confirmed to support x402 v2 exact Base, `PRIME_BASE_RPC_URL` to a Base mainnet RPC endpoint, and `PRIME_EVIDENCE_DB` to a writable SQLite file path. Start with `uvicorn server:app --host 127.0.0.1 --port 8000`. Startup fails when required configuration is absent. There is no free access switch.

The x402 middleware is responsible for payment challenge, verification and settlement. The intelligence core checks Base chain ID, pins reads to an EIP-1898 block hash with `requireCanonical`, and checks the block by number again before returning composed token facts. Providers without EIP-1898 support fail closed. RPC responses over 512,000 bytes are rejected. A later reorganization remains possible: each response identifies its observed block rather than claiming finality. An unsigned challenge and the absence of the unfinished verdict route have passed in CI on Python 3.11 and 3.12. This implementation has **not** executed a paid request. Before exposure to customers, verify paid retries and settlement on the configured facilitator, strengthen provider failure handling and limits, and reconcile transactions independently.

## Receipt evaluation

Run `python3 evaluate.py --receipts receipts.jsonl --costs costs.jsonl`. Receipt records need `status`, `transaction`, `network`, `amount_usd`, `payer`; cost records need `amount_usd`. Exports must come from an independent, confirmed source. The evaluator deduplicates settlements and does not count merely verified authorizations. It does not itself query a chain.

References: [x402 FastAPI integration](https://github.com/x402-foundation/x402/blob/main/docs/extensions/bazaar.mdx), [x402 v2 specification](https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md), [SDK changes](https://github.com/x402-foundation/x402/blob/main/python/x402/CHANGELOG.md).

Block-hash addressing: [EIP-1898](https://eips.ethereum.org/EIPS/eip-1898).
