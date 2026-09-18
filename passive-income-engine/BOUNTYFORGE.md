# BountyForge v2

BountyForge is the active-work revenue subsystem for the Passive Income Engine. It scouts micro-bounties, rejects unsafe or uneconomic work, ranks viable jobs by expected return, performs a narrow set of deterministic tasks in an offline solver, delivers verified artifacts for bound Pitch contracts, and reconciles exact payment receipts into the shared treasury.

## Trust zones

BountyForge deliberately separates marketplace authority from work execution.

### Coordinator

`bountyforge.py` runs with:

- the scoped OpenTask token;
- the shared accounting database;
- outbound network access;
- the signed queue volume.

It may discover tasks, score them, place bounded bids when explicitly enabled, inspect seller contracts, submit verified native deliveries when enabled, and reconcile exact router-verified receipts.

It does **not** execute buyer-supplied commands or arbitrary code.

### Offline solver

`bounty_solver.py` runs with:

- no network;
- no `/data` treasury volume;
- no OpenTask or PayPal credentials;
- a dedicated queue volume;
- a queue authentication secret only;
- all Linux capabilities dropped;
- `no-new-privileges`;
- a PID cap;
- a memory limit;
- a CPU limit;
- a read-only container filesystem.

The coordinator signs each work package with HMAC-SHA256. The solver rejects unsigned or altered packages. Solver result manifests are also signed and include artifact SHA-256 evidence; the coordinator verifies both signature and artifact hash before any delivery action.

## Safe solver v2

The first deterministic handlers are intentionally narrow:

- `json_format`
- `csv_to_json`
- `json_to_csv`
- `sha256`

The task router activates a handler only when the task wording clearly identifies one of those operations and includes an inline fenced input block.

The solver does not:

- run shell commands;
- execute Python, JavaScript, binaries, macros, or task-supplied code;
- clone repositories;
- browse the web;
- read production credentials;
- access the treasury database.

Unsupported tasks remain unsolved rather than being guessed.

## OpenTask integration

Current integrations use OpenTask's scoped REST agent API.

Discovery and marketplace state:

- `GET /api/agent/me/task-recommendations`
- `GET /api/agent/tasks/{taskId}`
- `POST /api/agent/tasks/{taskId}/bids`
- `GET /api/agent/contracts?role=seller`

Native Pitch delivery:

- `POST /api/agent/contracts/{contractId}/deliveries`
- `POST /api/agent/contracts/{contractId}/deliveries/{packageId}/upload-intents`
- direct authorized HTTPS PUT using the short-lived upload authorization;
- upload completion and processing-status polling;
- `POST /api/agent/contracts/{contractId}/deliveries/{packageId}/submit`

The upload URL and caller headers are treated as short-lived credentials and are never logged.

Payment reconciliation:

- `GET /api/agent/contracts/{contractId}/receipts`
- `GET /api/agent/contracts/{contractId}/invoices`

BountyForge credits an earning only when an invoice settlement unit is `paid`, carries a receipt ID, and that exact receipt is present in the receipt collection. The seller amount on that unit becomes the recorded proceeds. Platform-fee estimates used during opportunity scoring are not deducted again from a verified seller amount.

## Bounty and Benchmark entries

OpenTask Bounty/Benchmark entry artifacts currently require an artifact URL in the entry schema. The native task-entry upload flow and the public artifact URL field are separate surfaces.

Therefore v2 may safely solve supported Bounty/Benchmark work and stage the verified artifact as `solved_entry_ready`, but it does not invent a public URL or auto-submit that entry.

This is an intentional correctness boundary.

## Runtime controls

The example environment contains:

```dotenv
BOUNTYFORGE_ENABLED=true
BOUNTYFORGE_AUTO_BID=false
BOUNTYFORGE_AUTO_SOLVE=true
BOUNTYFORGE_AUTO_DELIVER=false
BOUNTYFORGE_AUTO_SUBMIT_ENTRIES=false
BOUNTYFORGE_RECONCILE_PAYMENTS=true

BOUNTYFORGE_SCOUT_INTERVAL_SECONDS=900
BOUNTYFORGE_MIN_REWARD_CENTS=500
BOUNTYFORGE_MAX_REWARD_CENTS=10000
BOUNTYFORGE_MIN_SUCCESS_PROBABILITY=0.70
BOUNTYFORGE_MIN_EXPECTED_PROFIT_CENTS=300
BOUNTYFORGE_MIN_HOURLY_CENTS=1500
BOUNTYFORGE_COMPUTE_BUDGET_CENTS=100
BOUNTYFORGE_MAX_ACTIVE_JOBS=3
BOUNTYFORGE_MAX_NEW_BIDS_PER_DAY=10
BOUNTYFORGE_ALLOWED_CURRENCIES=USD,USDC,USDT

BOUNTYFORGE_QUEUE_DIR=/bounty-queue
BOUNTYFORGE_QUEUE_SECRET=replace-with-an-independent-long-random-secret

OPENTASK_BASE_URL=https://opentask.ai/api
OPENTASK_TOKEN=
```

Generate `BOUNTYFORGE_QUEUE_SECRET` independently from the admin, webhook, PayPal, and OpenTask secrets.

A production OpenTask token should contain only the scopes required for the features actually enabled.

## Autonomy sequence

With discovery only:

```text
discover -> normalize -> safety filter -> profitability score -> ledger candidate
```

With bounded bidding enabled:

```text
eligible Pitch task -> bid -> accepted contract
```

With solving enabled:

```text
bound contract
  -> classify deterministic task
  -> signed work package
  -> offline/no-network solver
  -> signed result manifest
  -> SHA-256 verification
  -> delivery-ready artifact
```

With native delivery enabled:

```text
verified artifact
  -> OpenTask delivery draft
  -> native private upload
  -> OpenTask processing
  -> immutable delivery submit
  -> buyer review
```

With payment reconciliation enabled:

```text
exact receipt + paid invoice unit
  -> idempotent bounty_earnings row
  -> same-currency treasury integration
```

Foreign-currency earnings remain separate until an explicit conversion process exists.

## Commands

Run one complete coordinator cycle:

```bash
python bountyforge.py scout
```

Inspect local state:

```bash
python bountyforge.py status
```

Reconcile contracts and exact receipts without running discovery:

```bash
python bountyforge.py reconcile
```

Collect signed solver results without running discovery:

```bash
python bountyforge.py collect
```

Run continuously:

```bash
python bountyforge.py worker
```

Manual settlement remains available for independently verified external bounty sources:

```bash
python bountyforge.py settle \
  --source SOURCE \
  --external-id TASK_ID \
  --settlement-ref RECEIPT_ID \
  --gross-cents 2000 \
  --fees-cents 0 \
  --currency USDC
```

## Profitability model

The opportunity model remains conservative:

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

The 0.955 multiplier is an opportunity-screening assumption, not settlement accounting. Verified settlement rows use actual seller proceeds from payment records.

## Deployment

Both production Compose stacks run four logical services:

1. `engine` — storefront, checkout, treasury API.
2. `bountyforge` — marketplace coordinator and reconciler.
3. `bounty-solver` — offline deterministic solver with no network or treasury mount.
4. `backup` — verified SQLite backup worker.

The coordinator and solver share only `bounty_queue`. The solver never mounts `engine_data`.

## Next capability boundary

The next safe expansion is not arbitrary code execution. It is a larger library of objectively verifiable handlers, such as schema-constrained text/data transforms and generated documentation whose output can be validated without giving task content a shell.

Repository/code-change bounties would require a separate disposable build sandbox with cloned-source allowlisting, outbound-network policy, test execution limits, secret scrubbing, and a clean artifact-only return channel. That should remain distinct from the revenue host and from this deterministic solver.
