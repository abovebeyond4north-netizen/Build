# Prime-Agent x402 Intelligence: first slice

Three configured paid Base routes (`/chain/status`, `/token/metadata/{address}`, and `/token/context/{address}`) share a SQLite evidence cache. The context response explicitly marks holder, liquidity, and activity coverage as absent. An offline `/token/verdict` function returns `insufficient_evidence`; it is **not offered as a paid route** until those sources exist. No simulated payment is counted as revenue.

## Local core test

Run `python3 -m unittest discover -s tests -v` in this directory. No third-party libraries are needed for the core or offline audits. After installing `requirements.txt` and `httpx2`, run `python3 -m unittest discover -s tests/integration -v` to verify all three route challenges, an invalid retry, and mock acceptance and settlement paths using a local fake facilitator. The invalid retry reaches `/verify` and never calls `/settle`. On mock success, the handler runs between `/verify` and `/settle`; on mock settlement failure, paid content is withheld. The fake deliberately does not validate signatures or move funds.

## Paid server

Install `requirements.txt` in a Python 3.11+ environment. Set `PRIME_PAY_TO` to the operator's real Base address, `PRIME_FACILITATOR_URL` to a facilitator confirmed to support x402 v2 exact Base, `PRIME_BASE_RPC_URL` to a Base mainnet RPC endpoint, `PRIME_EVIDENCE_DB` to a writable SQLite file path, and `PRIME_DELIVERY_JOURNAL` to a writable JSONL file in a private directory. Start with `uvicorn server:app --host 127.0.0.1 --port 8000`. Startup fails when required configuration is absent. There is no free access switch.

The x402 middleware is responsible for payment challenge, verification and settlement. The intelligence core checks Base chain ID, pins reads to an EIP-1898 block hash with `requireCanonical`, and checks the block by number again before returning composed token facts. Providers without EIP-1898 support fail closed. RPC responses over 512,000 bytes are rejected. A later reorganization remains possible: each response identifies its observed block rather than claiming finality. All three unsigned challenges, a rejected retry, mock settlement success and failure, and the absence of the unfinished verdict route have passed in CI on Python 3.11 and 3.12. The middleware price patterns use x402's `:address` syntax while FastAPI handlers use `{address}`. This implementation has **not** executed a paid request. Before exposure to customers, verify paid retries and settlement on the configured facilitator, strengthen provider failure handling and limits, and reconcile transactions independently.

The outer delivery journal records a transaction reference, configured route price and payee, facilitator-reported payer, and SHA-256 of the response bytes after ASGI send completion when a 200 response carries a successful settlement header. It never stores the payment signature. An unsigned challenge or failed settlement produces no paid journal record. A server-side send event does not establish that the buyer received content; the header, journal, and reported payer are not independent settlement evidence. If a journal write fails, the already sent response remains available and an error is logged, leaving an explicit audit gap. Protect and back up the journal; this is an operational event log, not a tamper-proof ledger.

## Receipt evaluation

Run `python3 evaluate.py --receipts receipts.jsonl --costs costs.jsonl`. Receipt records need `status`, `transaction`, `network`, `amount_usd`, `payer`; cost records need `amount_usd`. Outputs are explicitly named `reported_*`: this calculation deduplicates seller claims but does not independently verify settlement or costs. It does not count merely verified authorizations.

Run `python3 verify_transfers.py --claims claims.jsonl --audit-rpc-url https://YOUR_BASE_RPC --pay-to 0xYOUR_PAYEE` to corroborate inbound transfers against a separately configured Base RPC. Each JSONL claim needs `status: "settled"`, `network: "eip155:8453"`, `asset` set to Circle's Base USDC contract `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, `transaction` as a transaction hash, `payer` as an EVM address, and `amount_atomic` as a positive decimal integer string (for example `"20000"` for 0.02 USDC). The checker rejects failed, noncanonical at audit time, or fewer than 12 blocks deep transactions; it requires an exact ERC-20 Transfer to the independently configured payee and rejects duplicate log claims. `matched_usdc_nominal` represents transferred USDC units, **not** verified x402 revenue: an inbound transfer alone cannot link a payment to a delivered request or establish independent buyer identity. Block depth is not a guarantee of finality. No real claims or live RPC receipts have been audited here.

Run `python3 audit_sales.py --journal "$PRIME_DELIVERY_JOURNAL" --audit-rpc-url "$PRIME_AUDIT_RPC_URL" --pay-to "$PRIME_PAY_TO"` to correlate journaled responses with onchain transfers. Configure `PRIME_AUDIT_RPC_URL` separately from the serving RPC and direct it to Base mainnet. The offered route prices have one source in `pricing.py`: the joiner derives exact USDC atomic amounts from the price table and checks receipt success, block depth and hash, ERC-20 sender/payee/amount, duplicate request and transaction references, and the response digest format. Its result is named `chain_correlated_response_events`, **not sales or settled revenue**. Journal content, facilitator-reported payer, and route attribution remain seller-side evidence; this tool does not attest to client receipt, verify a payment signature, or establish profit. Running it with a live provider and real journal is still outstanding.


## Bazaar discoverability

Every paid x402 v2 route declares the official Bazaar discovery extension. The 402 challenge includes a stable service name, shared search tags, route-specific descriptions, callable input metadata, and output examples/schemas. Dynamic token routes declare the `:address` path parameter so facilitators can consolidate concrete token URLs under a single route template.

This makes the service **discovery-ready**, not automatically indexed. Catalog inclusion is facilitator-controlled and must be observed after a real paid request echoes the Bazaar extension through settlement. For a live deployment, verify all of the following before claiming discoverability:

1. An unsigned public request returns a v2 `PAYMENT-REQUIRED` header whose decoded payload contains `extensions.bazaar`, an absolute public `resource.url`, `serviceName: "Prime-Agent x402 Intelligence"`, and the expected tags.
2. A real buyer echoes the Bazaar extension in its `PAYMENT-SIGNATURE` payload and settlement succeeds through the configured facilitator.
3. If the facilitator returns `EXTENSION-RESPONSES`, decode it and confirm `bazaar.status` is `success` or `processing`; treat `rejected` as a failed discovery registration.
4. Query the facilitator's discovery API, preferably `GET /discovery/resources?payTo=<payee>`, and confirm the public route appears. Allow for asynchronous indexing. Payment settlement by itself does not prove catalog inclusion.

The integration suite asserts that dynamic-route 402 responses contain Bazaar metadata and that mock paid retries echo the extension back to the facilitator boundary.

References: [x402 FastAPI integration](https://github.com/x402-foundation/x402/blob/main/docs/extensions/bazaar.mdx), [x402 v2 specification](https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md), [SDK changes](https://github.com/x402-foundation/x402/blob/main/python/x402/CHANGELOG.md).

Block-hash addressing: [EIP-1898](https://eips.ethereum.org/EIPS/eip-1898).
