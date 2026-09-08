# Passive Income Engine Operations

This runbook covers the unattended production posture for the passive-income engine.

## Production start

```bash
cd passive-income-engine
cp .env.example .env
```

Set strong values for `ADMIN_TOKEN` and `WEBHOOK_SECRET`, set `PUBLIC_BASE_URL` to the final HTTPS origin, and review the treasury reserve settings before accepting real payments.

Start the hardened stack:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

The application binds to `127.0.0.1:8000` by default. Put a TLS-terminating reverse proxy in front of it. Set `BIND_ADDRESS=0.0.0.0` only when the surrounding network/firewall configuration intentionally exposes port 8000.

## Unattended behavior

- `engine` restarts automatically unless explicitly stopped.
- Docker checks `/health` every 30 seconds.
- The process runs as an unprivileged user with Linux capabilities dropped and `no-new-privileges` enabled.
- The container root filesystem is read-only; only the persistent data volume is writable.
- `backup` creates a verified SQLite snapshot every six hours by default.
- Backups are stored in a separate Docker volume and retained for the most recent 28 snapshots by default.
- Each backup is validated with SQLite `PRAGMA integrity_check` before it is retained.

## Status

```bash
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=100 engine
docker compose -f docker-compose.production.yml logs --tail=100 backup
```

Application health:

```bash
curl -fsS http://127.0.0.1:8000/health
```

## Backups

Force an immediate snapshot:

```bash
docker compose -f docker-compose.production.yml run --rm backup python scripts/backup_db.py --once
```

List snapshots:

```bash
docker compose -f docker-compose.production.yml run --rm backup sh -lc 'ls -lh /backups'
```

## Restore

Restoring replaces the active database. Stop the application first so no writer is active.

```bash
docker compose -f docker-compose.production.yml stop engine backup
```

Inspect available snapshots, then run the integrity-checked atomic restore utility against the selected file:

```bash
docker compose -f docker-compose.production.yml run --rm \
  -v passive-income-engine_engine_backups:/backups:ro \
  engine python scripts/restore_db.py /backups/passive_income_YYYYMMDDTHHMMSSZ.db
```

Restart and verify health:

```bash
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml ps
```

## Upgrade procedure

```bash
git pull --ff-only
docker compose -f docker-compose.production.yml run --rm backup python scripts/backup_db.py --once
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
```

Use immutable release tags in long-lived production environments rather than deploying arbitrary branch heads.

## CI gates

The GitHub Actions workflow requires:

1. Python bytecode compilation.
2. Unit tests.
3. Backup/restore round-trip verification.
4. Dependency vulnerability audit with `pip-audit`.
5. Production Docker image build.
6. Production Compose configuration validation.

## Financial boundary

The service automatically calculates `payout_ready_cents` only after configured reserves. It does not autonomously execute an external money transfer. Compare the recommendation with actual settled funds before transferring money.

## Incident priorities

1. If signed webhook validation fails unexpectedly, stop fulfillment intake before changing the secret.
2. If database integrity is questionable, stop the engine and restore the newest verified snapshot.
3. If product pricing or currency validation fails, keep fulfillment disabled until the server-side catalog and payment adapter agree.
4. If reserve calculations appear incorrect, stop financial distributions while preserving storefront and accounting data.
5. Rotate `ADMIN_TOKEN` and `WEBHOOK_SECRET` immediately if either secret may have been exposed.
