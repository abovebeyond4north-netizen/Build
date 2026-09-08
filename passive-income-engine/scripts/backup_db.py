from __future__ import annotations

import argparse
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


def backup_once(source: Path, target_dir: Path, retention: int) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = target_dir / f"passive_income_{stamp}.db"

    source_uri = f"file:{source}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=30) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            check = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise RuntimeError(f"backup integrity check failed: {check}")

    backups = sorted(target_dir.glob("passive_income_*.db"), reverse=True)
    for old in backups[max(1, retention):]:
        old.unlink(missing_ok=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Create verified SQLite snapshots for the passive-income engine.")
    parser.add_argument("--source", default=os.getenv("DATABASE_PATH", "/data/passive_income.db"))
    parser.add_argument("--target-dir", default=os.getenv("BACKUP_DIR", "/backups"))
    parser.add_argument("--interval", type=int, default=int(os.getenv("BACKUP_INTERVAL_SECONDS", "21600")))
    parser.add_argument("--retention", type=int, default=int(os.getenv("BACKUP_RETENTION_COUNT", "28")))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target_dir)
    if args.retention < 1:
        raise SystemExit("retention must be at least 1")

    while True:
        if source.exists():
            created = backup_once(source, target, args.retention)
            print(f"backup_created={created}", flush=True)
        else:
            print(f"backup_skipped=source_missing:{source}", flush=True)
        if args.once:
            return
        time.sleep(max(300, args.interval))


if __name__ == "__main__":
    main()
