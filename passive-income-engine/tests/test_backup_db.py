import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_db.py"
spec = importlib.util.spec_from_file_location("backup_db", SCRIPT)
backup_db = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(backup_db)


class BackupDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.db"
        self.backups = self.root / "backups"
        with sqlite3.connect(self.source) as con:
            con.execute("CREATE TABLE values_table(value TEXT NOT NULL)")
            con.execute("INSERT INTO values_table(value) VALUES('verified')")

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_is_integrity_checked_and_contains_source_data(self):
        destination = backup_db.backup_once(self.source, self.backups, retention=2)

        self.assertTrue(destination.exists())
        with sqlite3.connect(destination) as con:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("SELECT value FROM values_table").fetchone()[0], "verified")
        self.assertEqual(list(self.backups.glob(".*.tmp")), [])

    def test_failed_publish_cleans_temporary_snapshot(self):
        with patch.object(backup_db.os, "replace", side_effect=OSError("publish failed")):
            with self.assertRaisesRegex(OSError, "publish failed"):
                backup_db.backup_once(self.source, self.backups, retention=2)

        self.assertEqual(list(self.backups.glob(".*.tmp")), [])
        self.assertEqual(list(self.backups.glob("passive_income_*.db")), [])


if __name__ == "__main__":
    unittest.main()
