# BountyForge v1

BountyForge is the active-work revenue subsystem for the Passive Income Engine. It discovers agent-compatible micro-bounties, normalizes them, rejects unsafe or uneconomic work, ranks eligible jobs by expected profit per hour, optionally places bounded bids, and records verified settlements into the shared treasury ledger.

## What v1 automates

- Authenticated OpenTask seller-side task discovery using `GET /api/agent/me/task-recommendations`.
- Task-detail enrichment before scoring.
- Reward/currency normalization.
- Hard rejection of disallowed task classes such as CAPTCHA solving, fake reviews, spam, credential abuse, phishing, malware, or identity-bypass work.
- Reward caps and allowlisted settlement currencies.
- Bayesian success estimates using task-match quality plus the local attempt history.
- Expected-profit and expected-hourly calculations.
- Active-job and daily-bid limits.
- Optional OpenTask pitch-mode bid creation.
- Queueing of Bounty/Benchmark completed-entry tasks until a sandboxed solver/verifier is attached.
- Idempotent settlement accounting.
- Shared treasury integration for settlements already denominated in the engine's configured currency.

## Current platform integration

OpenTask's current agent API supports scoped task recommendations, task reads, bids, contracts, entries, deliveries, and payment receipts. BountyForge v1 deliberately starts with discovery and pitch-mode bidding because those can be bounded cleanly before a general solver is attached.

The OpenTask base URL is:

```text
https://opentask.ai/api
```

Authentication uses a scoped bearer token. Do not commit that token.

## Activation

BountyForge runs as a separate least-privilege service in both production Compose stacks. The service shares only the engine's persistent `/data` volume.

The default configuration is observation-first:

```dotenv
BOUNTYFORGE_ENABLED=true
BOUNTYFORGE_AUTO_BID=false
BOUNTYFORGE_MIN_REWARD_CENTS=500
BOUNTYFORGE_MAX_REWARD_CENTS=10000
BOUNTYFORGE_MIN_SUCCESS_PROBABILITY=0.70
BOUNTYFORGE_MIN_EXPECTED_PROFIT_CENTS=300
BOUNTYFORGE_MIN_HOURLY_CENTS=1500
BOUNTYFORGE_MAX_ACTIVE_JOBS=3
BOUNTYFORGE_MAX_NEW_BIDS_PER_DAY=10
BOUNTYFORGE_ALLOWED_CURRENCIES=USD,USDC,USDT
OPENTASK_TOKEN=
```

Once a scoped OpenTask credential exists, set it only in the production secret environment. A read-capable token is enough for discovery. Enable `BOUNTYFORGE_AUTO_BID=true` only when the credential also has the required bid-write scope and the seller profile is ready.

## Profitability model

For each task, BountyForge estimates:

```text
success_probability =
    65% * marketplace match score
  + 35% * Bayesian historical success

expected_profit =
    reward
  * success_probability
  * 0.955
  - configured compute budget

expected_hourly =
    expected_profit / estimated_minutes * 60
```

The 0.955 factor is a conservative model of OpenTask's currently advertised 4.5% platform fee. Actual settlement accounting always records actual gross and fee amounts rather than relying on this estimate.

A job must satisfy every configured threshold before it becomes eligible.

## Execution boundary

BountyForge v1 does **not** run arbitrary bounty-supplied commands and does not clone untrusted code into the production container. That would break the existing least-privilege security model.

Pitch-mode jobs may be bid on when auto-bid is explicitly enabled. Bounty/Benchmark jobs are queued for the next layer: a disposable network-bounded sandbox that can receive a normalized work specification, create a candidate artifact, run task-specific verification, and submit only verified output.

This separation prevents a marketplace description from becoming an implicit shell command on the revenue server.

## Commands

Run one discovery/scoring cycle:

```bash
python bountyforge.py scout
```

Inspect the local bounty ledger:

```bash
python bountyforge.py status
```

Run continuously:

```bash
python bountyforge.py worker
```

Record a verified settlement:

```bash
python bountyforge.py settle \
  --source opentask \
  --external-id TASK_ID \
  --settlement-ref RECEIPT_ID \
  --gross-cents 2000 \
  --fees-cents 90 \
  --currency USDC
```

Settlement references are unique per source, making retries idempotent.

## Next layer

The next implementation stage is the **BountyForge Sandbox Solver**:

1. Materialize only an allowlisted task/repository into a disposable workspace.
2. Disable access to the production database and payment credentials.
3. Apply CPU, memory, disk, time, and network limits.
4. Generate a candidate deliverable through a configured coding/LLM agent.
5. Run declared tests plus static/security checks.
6. Produce a signed evidence manifest.
7. Submit only after objective verification passes.
8. Poll contract/payment receipts and record verified earnings automatically.

The production engine remains the scout, policy, accounting, and orchestration layer; untrusted work execution belongs in the disposable sandbox.
