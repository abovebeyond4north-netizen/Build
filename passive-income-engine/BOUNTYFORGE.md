# BountyForge v4.6

BountyForge is the active-work revenue subsystem for the Passive Income Engine. It scouts public micro-bounties even before marketplace authentication, applies safety and profitability gates, completes a growing set of deterministic jobs offline, verifies explicit public-GitHub repository jobs at immutable commits, delivers verified artifacts for bound Pitch contracts, and reconciles exact payment receipts into the shared treasury.

## Trust zones

BountyForge deliberately separates marketplace authority, deterministic work execution, repository fetching, repository verification, and accounting.

### Coordinator

`bountyforge.py` has:

- the scoped OpenTask token;
- the accounting database;
- outbound network access;
- the deterministic solver queue;
- the repository-verification queue.

It may discover tasks, score them, place bounded bids when enabled, inspect seller contracts, submit verified native deliveries when enabled, and reconcile exact payment receipts.

It does **not** execute buyer-provided shell commands or arbitrary code.

### Deterministic solver

`bounty_solver.py` runs with:

- no network;
- no treasury database;
- no OpenTask or PayPal credentials;
- a dedicated HMAC-authenticated queue;
- a read-only container root;
- dropped Linux capabilities;
- `no-new-privileges`;
- CPU, memory, PID, input, and output limits.

Every work package and result manifest is authenticated with HMAC-SHA256. Artifact bytes are independently SHA-256 checked by the coordinator before delivery.

### Repository stager

`repo_stager.py` is the only repository worker with network access. It has no treasury, PayPal, or OpenTask credential.

It accepts only:

- `https://github.com/<owner>/<repo>`;
- a full 40-hex immutable commit SHA;
- a signed request from the coordinator.

It fetches the public codeload archive, rejects symlinks, hardlinks, devices, FIFOs, absolute paths, and traversal paths, enforces compressed/expanded size and file-count ceilings, and writes a file-level SHA-256 manifest.

### Repository verifier

`repo_verifier.py` receives the staged tree but has:

- no network;
- no treasury volume;
- no OpenTask/PayPal credential;
- a read-only root filesystem;
- dropped capabilities;
- `no-new-privileges`;
- resource limits.

It accepts only signed verification jobs and a tiny command allowlist:

- `python -m unittest discover -v`
- `python -m compileall -q .`

No free-form command string is accepted.

## Deterministic microtask library

v3 supports:

- `json_format`
- `csv_to_json`
- `json_to_csv`
- `jsonl_to_json`
- `json_to_jsonl`
- `csv_deduplicate`
- `csv_to_markdown`
- `csv_to_json_cli_package` — deterministic ZIP containing a stdlib Python CLI/API, unit tests, and README for explicit buyer requests to build a CSV→JSON script
- `lines_sort_unique`
- `base64_encode`
- `base64_decode`
- `text_replace`
- `sha256`

The router only selects these handlers when task wording is explicit and the required input appears in an inline fenced block. Unsupported tasks remain unsolved.

The deterministic solver never executes Python, JavaScript, binaries, macros, shell commands, or task-supplied programs.

## Deterministic CSV→JSON script fulfillment

v4.3 can recognize a narrow buyer request to build/create/write/implement a Python CSV→JSON script or converter. That route produces a fixed reproducible ZIP rather than free-form generated code.

The package contains:

- `csv_to_json.py` — standard-library CLI + importable API;
- `test_csv_to_json.py` — unit tests covering quoting, Unicode, delimiter detection, compact output, file output, and invalid delimiters;
- `README.md` — run, import, and verification instructions.

Runtime solver verification parses both generated Python sources, verifies the exact ZIP structure and file bytes, and hashes every component. Repository CI additionally unpacks the generated ZIP, runs its unit tests, and invokes the CLI on sample input.

No buyer-provided program is executed by this handler.

Seller-package wording such as “tested, delivered in 24h” and “ready template/ready-made” is demoted during public discovery so an agent advertising its own prebuilt package is not mistaken for a buyer request.

## Repository verification microtasks

BountyForge can also recognize explicit jobs of the form:

```text
Verify/run tests for:
https://github.com/OWNER/REPO
commit: <40-hex SHA>
check: python unittest and/or compileall
```

The coordinator signs a staging request, the stager fetches that exact public commit, the no-network verifier runs only the named allowlisted checks, and the signed result is converted into a normal BountyForge delivery artifact.

A successful report includes:

- repository tree size;
- file count;
- check name;
- exact argv used;
- return code;
- duration;
- capped output;
- output SHA-256;
- pass/fail state.

This creates a real autonomous microjob class for repository verification without pretending to be a general coding model.

## Current boundary on code-change bounties

v3 does **not** generate arbitrary source-code patches.

Repository verification is intentionally separate from patch generation. A future code-change system would need a dedicated candidate-generator boundary and must return candidate diffs into this verifier rather than receiving shell or marketplace authority.

Until that exists, BountyForge can earn from deterministic transforms and repository verification jobs, but it will not claim that it can safely solve arbitrary software bugs.

## Credential-free public scouting

OpenTask's documented public REST discovery surface is used before authentication:

```text
GET /api/tasks?skill=<signal>&sort=new
GET /api/tasks/<taskId>
```

BountyForge queries a bounded configurable set of capability signals, deduplicates task IDs across searches, fetches task details, preserves acceptance criteria, and assigns a local capability-fit score. It does not claim that this local score is OpenTask's personalized recommendation score.

Public reads therefore continue with no `OPENTASK_TOKEN`. Authenticated recommendations are merged in when a scoped token exists and take precedence when their match score is stronger.

Default public signals:

```dotenv
BOUNTYFORGE_PUBLIC_SCOUT=true
BOUNTYFORGE_PUBLIC_SKILLS=csv,json,data,python,documentation
BOUNTYFORGE_PUBLIC_TASKS_PER_SIGNAL=20
```

The token remains mandatory for marketplace writes such as bids, contract reads, delivery submission, and payment reconciliation.

## Zero-credential scheduled scouting

The repository includes `.github/workflows/bountyforge-public-scout.yml`.
It runs every six hours and on relevant `main` pushes with no marketplace
credentials and no repository write permission.

The workflow explicitly disables bidding, solving, delivery, repository
verification, and payment reconciliation. It performs public discovery and
profitability ranking only, then preserves:

- `public-scout.json` — machine-readable result and candidate metrics.
- `public-scout-summary.md` — a compact top-candidate report shown in the
  GitHub Actions run summary.

Artifacts are retained for 14 days. This gives BountyForge a continuously
refreshed opportunity feed before an OpenTask seller identity is connected.

Public-feed quality filtering also demotes high-confidence seller
advertisements (for example, "pitch me your task" service listings) so they
are not mistaken for buyer bounties.

## Bid-readiness gate

Opportunity profitability and marketplace fit are not sufficient for an automated bid.

For every Pitch candidate, BountyForge resolves a concrete fulfillment route before the bid loop can act:

- `solver/<kind>` for deterministic handlers such as `csv_to_json_cli_package`;
- `repo_verifier/repository_verification` for an explicit immutable public-repository verification task;
- no route for unsupported work.

The scheduled public scout exposes `bid_ready`, `fulfillment_route`, and `fulfillment_kind` for each accepted candidate.

Even when `BOUNTYFORGE_AUTO_BID=true`, the coordinator skips a profitable candidate when no concrete route exists. Supported routes also generate task-specific bid text that promises only verified capabilities and verification evidence. Generic “we can do this” bid language is not used.

## Read-only task preflight

`bounty_preflight.py` performs a fresh public-task read and prepares the exact evidence needed before a marketplace commitment.

For a task ID it:

- reloads current public task terms and `updatedAt`;
- reruns local fit, safety, profitability, and execution-mode checks;
- resolves the concrete fulfillment route;
- generates the route-specific truthful bid approach;
- runs the trusted deterministic handler in-memory when applicable;
- records artifact filename, size, SHA-256, and verification evidence;
- reports whether marketplace authentication is present;
- always reports `write_actions_performed: false`.

When a task is technically bid-ready but no OpenTask credential is configured, the blocker is `marketplace_auth`. When a credential is present, preflight still remains read-only and reports `explicit_bid_action`.

Run manually:

    python bounty_preflight.py <TASK_ID>

For the static `csv_to_json_cli_package` route only, a human/operator can optionally write the preflight artifact:

    python bounty_preflight.py <TASK_ID> --artifact-dir ./preflight-artifacts

Automatic preflight does not export task-input-derived transform artifacts.

The scheduled public scout fresh-preflights at most the top three `bid_ready` candidates and preserves `public-preflight.json` plus a compact summary. No marketplace write credential is supplied to that workflow.

## Fresh task-state gate

Preflight also validates current marketplace state before declaring a Pitch task bid-ready.

It blocks when the fresh public task response explicitly indicates:

- a closed/cancelled/completed/expired/filled/paused/draft state;
- a passed `deadlineAt` or `expiresAt`;
- an explicit bid control such as `canBid: false`.

Missing unauthenticated action metadata is not treated as a rejection by itself. The report records the status, enabled public action names, deadline evidence, and `updated_age_days`.

Age is an audit signal, not an automatic rejection. An older task may remain genuinely open; current public task state controls the decision.

## OpenTask integration

Discovery and marketplace state:

- `GET /api/agent/me/task-recommendations`
- `GET /api/agent/tasks/{taskId}`
- `POST /api/agent/tasks/{taskId}/bids`
- `GET /api/agent/contracts?role=seller`

Native Pitch delivery:

- create delivery draft;
- create native upload intent;
- upload using the short-lived authorized HTTPS request;
- complete/poll file processing;
- submit immutable delivery package.

The temporary upload URL and headers are never persisted in logs.

Payment reconciliation:

- contract receipts;
- contract invoices;
- exact paid settlement units.

An earning is recorded only when a paid invoice unit references a receipt that exists in the contract receipt collection. The recorded amount is the seller proceeds from the verified unit, so the opportunity-model fee estimate is not deducted again.

## Bounty and Benchmark entries

OpenTask Bounty/Benchmark entry artifacts currently require a public artifact URL in the entry schema.

BountyForge may solve or verify those jobs and stage them as ready, but it does not invent a public artifact URL. Automatic native private delivery is used only where the contract delivery surface supports it.

## Runtime controls

```dotenv
BOUNTYFORGE_ENABLED=true
BOUNTYFORGE_PUBLIC_SCOUT=true
BOUNTYFORGE_PUBLIC_SKILLS=csv,json,data,python,documentation
BOUNTYFORGE_PUBLIC_TASKS_PER_SIGNAL=20

BOUNTYFORGE_AUTO_BID=false
BOUNTYFORGE_AUTO_SOLVE=true
BOUNTYFORGE_AUTO_REPO_VERIFY=true
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

BOUNTYFORGE_REPO_VERIFY_DIR=/repo-verify
BOUNTYFORGE_REPO_VERIFY_SECRET=replace-with-an-independent-long-random-secret
BOUNTYFORGE_REPO_ARCHIVE_MAX_BYTES=20971520
BOUNTYFORGE_REPO_VERIFY_MAX_TREE_BYTES=52428800
BOUNTYFORGE_REPO_VERIFY_MAX_FILES=5000
BOUNTYFORGE_REPO_VERIFY_TIMEOUT_SECONDS=120
BOUNTYFORGE_REPO_VERIFY_MAX_OUTPUT_BYTES=131072

OPENTASK_BASE_URL=https://opentask.ai/api
OPENTASK_TOKEN=
```

Generate the queue secrets independently from each other and independently from admin, webhook, PayPal, and marketplace credentials.

## Autonomy flow

Deterministic job:

```text
discover
 -> safety/profit scoring
 -> accepted contract
 -> signed deterministic package
 -> offline solver
 -> signed + SHA-256 verified artifact
 -> native delivery
 -> exact payment receipt
 -> treasury
```

Repository verification job:

```text
discover explicit repo-verification task
 -> require github.com + full commit SHA + allowlisted checks
 -> signed fetch request
 -> public immutable archive staging
 -> path/symlink/size validation
 -> file-hash manifest
 -> no-network verifier
 -> signed verification report
 -> normal BountyForge delivery artifact
 -> exact payment receipt
 -> treasury
```

## Commands

One full cycle:

```bash
python bountyforge.py scout
```

State:

```bash
python bountyforge.py status
```

Contract/payment reconciliation:

```bash
python bountyforge.py reconcile
```

Collect deterministic solver output:

```bash
python bountyforge.py collect
```

Collect repository verification output:

```bash
python bountyforge.py collect-repos
```

Continuous worker:

```bash
python bountyforge.py worker
```

Manual recording for independently verified external bounty receipts remains available through `settle`.

## Profitability model

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

The 0.955 multiplier is an opportunity-screening estimate only. Verified settlement accounting uses actual seller proceeds.

## Deployment services

The production Compose stacks now separate six roles:

1. `engine` — storefront, checkout, treasury API.
2. `bountyforge` — marketplace coordinator/reconciler.
3. `bounty-solver` — no-network deterministic transform worker.
4. `repo-stager` — public immutable GitHub archive fetcher with no business secrets.
5. `repo-verifier` — no-network allowlisted repository test worker.
6. `backup` — verified SQLite backup worker.

The repository workers never mount `engine_data`. The deterministic solver never mounts `engine_data`. The coordinator is the only BountyForge component that combines marketplace authority with accounting state.
