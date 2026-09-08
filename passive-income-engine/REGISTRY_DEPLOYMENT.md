# Registry Deployment

Validated releases are published as OCI/Docker images to:

```text
ghcr.io/abovebeyond4north-netizen/passive-income-engine
```

The release workflow smoke-tests the image before publishing. Every published main revision receives:

- `sha-<12-character-git-sha>` — immutable revision tag for controlled deployments and rollback.
- `latest` — current validated `main` image.

The image contains application code only. PayPal credentials, admin tokens, webhook IDs, the SQLite database, and backup data are runtime inputs and are not built into the image.

## Initial deployment

On a persistent Docker host, copy these repository files into one directory:

- `.env.example` as `.env`, then configure its runtime values locally.
- `docker-compose.registry.yml`.

Set the live host's `.env` with the final HTTPS `PUBLIC_BASE_URL`, strong local secrets, and the PayPal environment appropriate to the deployment. Do not commit that `.env` file.

Pull and start the current validated release:

```bash
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
docker compose -f docker-compose.registry.yml ps
```

The application binds to `127.0.0.1:8000` by default so a TLS reverse proxy can own the public interface.

## Pin to an immutable release

For reproducible production, set `IMAGE_TAG` to the published revision tag before running Compose, for example:

```bash
export IMAGE_TAG=sha-e9fa16bb0ff0
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

Use the SHA tag emitted by the release workflow for the revision you actually intend to run. `latest` is convenient but moves when a new validated `main` image is published.

## Unattended update procedure

Before changing revisions, force a verified database snapshot:

```bash
docker compose -f docker-compose.registry.yml run --rm backup python scripts/backup_db.py --once
```

Then pull and recreate the services:

```bash
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
docker compose -f docker-compose.registry.yml ps
```

Persistent `engine_data` and `engine_backups` volumes survive image replacement.

## Rollback

Set `IMAGE_TAG` to the previously known-good SHA tag and recreate the services:

```bash
export IMAGE_TAG=sha-PREVIOUS_VALIDATED_SHA
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

If only the application image is faulty, do not restore the database. Restore a SQLite snapshot only when database integrity or data state itself requires recovery, following `OPERATIONS.md`.

## Registry authentication

GitHub Actions publishes the repository-associated package with its short-lived `GITHUB_TOKEN`; no separate publishing secret is committed. GitHub Container Registry package visibility and pull permissions can be configured independently of repository visibility. If the production host cannot pull anonymously, authenticate that host to `ghcr.io` with a GitHub credential that has only the package-read access it requires.

## Financial boundary

This release path deploys customer-initiated PayPal Checkout, fulfillment, accounting, optimization, backups, and `payout_ready_cents` calculation. It does not add or invoke PayPal Payouts and does not autonomously transfer business funds.
