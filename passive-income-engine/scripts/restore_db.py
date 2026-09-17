from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path


def verify_database(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=30) as con:
        result = con.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"database integrity check failed: {result}")


def restore(source: Path, destination: Path) -> None:
    verify_database(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.restore-",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        verify_database(temporary)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Atomically restore a verified passive-income SQLite snapshot.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--destination", type=Path, default=Path(os.getenv("DATABASE_PATH", "/data/passive_income.db")))
    args = parser.parse_args()
    restore(args.backup, args.destination)
    print(f"restored={args.backup} destination={args.destination}")


if __name__ == "__main__":
    main()
