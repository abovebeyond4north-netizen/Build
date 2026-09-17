import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.restore_db import restore


class RestoreDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "backup.db"
        self.destination = self.root / "data" / "passive_income.db"
        with sqlite3.connect(self.source) as con:
            con.execute("CREATE TABLE values_table(value INTEGER)")
            con.execute("INSERT INTO values_table VALUES(42)")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_restore_publishes_verified_database(self):
        restore(self.source, self.destination)

        with sqlite3.connect(self.destination) as con:
            value = con.execute("SELECT value FROM values_table").fetchone()[0]
        self.assertEqual(value, 42)
        self.assertEqual(list(self.destination.parent.glob(".*.restore-*.tmp")), [])

    def test_failed_publish_preserves_destination_and_cleans_temporary_file(self):
        self.destination.parent.mkdir(parents=True)
        with sqlite3.connect(self.destination) as con:
            con.execute("CREATE TABLE original(value INTEGER)")
            con.execute("INSERT INTO original VALUES(7)")

        with mock.patch("scripts.restore_db.os.replace", side_effect=OSError("simulated publish failure")):
            with self.assertRaisesRegex(OSError, "simulated publish failure"):
                restore(self.source, self.destination)

        with sqlite3.connect(self.destination) as con:
            value = con.execute("SELECT value FROM original").fetchone()[0]
        self.assertEqual(value, 7)
        self.assertEqual(list(self.destination.parent.glob(".*.restore-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
