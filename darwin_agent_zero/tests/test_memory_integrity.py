import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.memory import KnowledgeBank


class MemoryIntegrityTests(unittest.TestCase):
    def test_new_entries_form_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            first = bank.deposit("task", "first", 0.4)
            second = bank.deposit("task", "second", 0.8)

            self.assertIsNotNone(first.entry_hash)
            self.assertEqual(first.previous_hash, None)
            self.assertEqual(second.previous_hash, first.entry_hash)
            self.assertEqual(bank.entries()[1].entry_hash, second.entry_hash)

    def test_content_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            bank.deposit("task", "trusted", 0.8)
            row = json.loads(bank.path.read_text(encoding="utf-8"))
            row["content"] = "tampered"
            bank.path.write_text(json.dumps(row) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "entry hash mismatch"):
                bank.entries()

    def test_reordering_chained_memory_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            bank.deposit("task", "first", 0.4)
            bank.deposit("task", "second", 0.8)
            lines = bank.path.read_text(encoding="utf-8").splitlines()
            bank.path.write_text("\n".join(reversed(lines)) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "predecessor mismatch"):
                bank.entries()

    def test_legacy_out_of_range_usefulness_is_rejected_not_clamped(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            bank.path.write_text(
                json.dumps(
                    {
                        "kind": "task",
                        "content": "poisoned ranking",
                        "usefulness": 100.0,
                        "created_at": 1.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                bank.entries()

    def test_prune_upgrades_legacy_entries_to_fresh_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            rows = [
                {
                    "kind": "task",
                    "content": "low",
                    "usefulness": 0.2,
                    "created_at": 1.0,
                },
                {
                    "kind": "task",
                    "content": "high",
                    "usefulness": 0.9,
                    "created_at": 2.0,
                },
            ]
            bank.path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            bank.prune(2)
            entries = bank.entries()

            self.assertEqual([entry.content for entry in entries], ["high", "low"])
            self.assertTrue(all(entry.entry_hash for entry in entries))
            self.assertIsNone(entries[0].previous_hash)
            self.assertEqual(entries[1].previous_hash, entries[0].entry_hash)

    def test_boolean_usefulness_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bank = KnowledgeBank(Path(tmp))
            with self.assertRaisesRegex(ValueError, "boolean"):
                bank.deposit("task", "bad", True)


if __name__ == "__main__":
    unittest.main()
