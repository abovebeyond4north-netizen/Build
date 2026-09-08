# Production Release Checklist

A release is ready only when every automated CI gate passes and the deployment environment satisfies the runtime requirements below.

## Automated gates

- Python compilation passes.
- Unit tests pass.
- Backup/restore round-trip passes.
- `pip-audit` reports no known vulnerable pinned dependencies.
- Docker image builds successfully.
- Production Compose configuration validates.

## Runtime requirements

- `ADMIN_TOKEN` is a strong secret and is not committed to Git.
- `WEBHOOK_SECRET` is a strong secret and matches the payment adapter.
- `PUBLIC_BASE_URL` is the final HTTPS origin.
- Persistent data and backup volumes are provisioned.
- TLS terminates before traffic reaches the FastAPI service.
- Only the reverse proxy/network layer can reach the bound application port unless direct exposure is intentional.
- The payment adapter sends server-verified completed-sale and refund events using the documented HMAC signature contract.
- The reserve configuration has been reviewed before any payout-ready recommendation is acted on.

## Post-deploy checks

```bash
docker compose -f docker-compose.production.yml ps
curl -fsS http://127.0.0.1:8000/health
docker compose -f docker-compose.production.yml run --rm backup python scripts/backup_db.py --once
```

Verify that the storefront, a product page, a guide page, sitemap, RSS feed, and authenticated treasury endpoint respond as expected.

## Rollback

If the application image is faulty but the database is healthy, redeploy the previous immutable image/tag without restoring the database.

If database integrity is faulty, stop both services and use `scripts/restore_db.py` against the newest verified snapshot before restarting.

External money movement remains outside the autonomous service and must not be used as a deployment health check.
