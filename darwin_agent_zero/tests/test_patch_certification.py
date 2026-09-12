import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dgm_zero.patch_certification import PatchCertificationLedger
from dgm_zero.self_patch import (
    PatchComparisonResult,
    PatchGateResult,
    PatchProposal,
    RepositoryPatchLab,
)


class PatchCertificationLedgerTests(unittest.TestCase):
    def test_reservation_is_one_shot_and_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            ledger = PatchCertificationLedger(workspace)
            digest = "a" * 64
            record = ledger.reserve(digest, (1_000_001, 1_000_003, 1_000_007))
            self.assertTrue(record.record_hash)
            self.assertTrue(ledger.is_consumed(digest))
            loaded = PatchCertificationLedger(workspace)
            self.assertTrue(loaded.is_consumed(digest))
            with self.assertRaisesRegex(ValueError, "already consumed"):
                loaded.reserve(digest, (1_000_011, 1_000_013, 1_000_017))

    def test_tampered_reservation_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            ledger = PatchCertificationLedger(workspace)
            ledger.reserve("b" * 64, (1_100_001, 1_100_003, 1_100_007))
            data = json.loads(ledger.path.read_text(encoding="utf-8").strip())
            data["replay_seeds"][0] = 9_999_999
            ledger.path.write_text(json.dumps(data) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "record hash mismatch"):
                ledger.records()

    def test_duplicate_or_invalid_seeds_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = PatchCertificationLedger(Path(tmp))
            with self.assertRaisesRegex(ValueError, "unique"):
                ledger.reserve("c" * 64, (1, 1))
            with self.assertRaisesRegex(ValueError, "integers"):
                ledger.reserve("c" * 64, (True, 2))


class RepositoryPatchOneShotTests(unittest.TestCase):
    @staticmethod
    def make_repo(root: Path) -> Path:
        repo = root / "repo"
        package = repo / "src" / "dgm_zero"
        package.mkdir(parents=True)
        (repo / "pyproject.toml").write_text(
            "[project]\nname='fixture'\nversion='0.0.0'\n",
            encoding="utf-8",
        )
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "mutation.py").write_text("VALUE = 1\n", encoding="utf-8")
        (package / "search_schedule.py").write_text("VALUE = 1\n", encoding="utf-8")
        (package / "meta_learning.py").write_text("VALUE = 1\n", encoding="utf-8")
        (package / "self_instruction.py").write_text("VALUE = 1\n", encoding="utf-8")
        return repo

    @staticmethod
    def passed_gate(name="compile"):
        return PatchGateResult(
            name=name,
            command=("python",),
            passed=True,
            returncode=0,
            elapsed_seconds=0.01,
            stdout_tail="",
            stderr_tail="",
        )

    @staticmethod
    def comparison(seeds):
        return PatchComparisonResult(
            passed=True,
            reasons=(),
            seeds=tuple(seeds),
            baseline_aggregate_score=0.7,
            candidate_aggregate_score=0.71,
            aggregate_delta=0.01,
            baseline_mean_champion_score=0.8,
            candidate_mean_champion_score=0.81,
            mean_champion_delta=0.01,
            worst_seed_champion_delta=0.0,
        )

    def test_second_default_evaluation_cannot_consume_fresh_replay_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            proposal = PatchProposal.for_replacements(
                repo,
                rationale="one-shot test",
                replacements={"src/dgm_zero/mutation.py": "VALUE = 2\n"},
            )
            lab = RepositoryPatchLab(repo, root / "workspace")
            compare_calls = []

            def fake_compare(
                baseline_root,
                staged_root,
                temp_root,
                timeout_seconds,
                *,
                seeds,
                prefix,
            ):
                compare_calls.append((prefix, tuple(seeds)))
                return self.comparison(seeds), []

            with patch.object(
                RepositoryPatchLab,
                "default_gate_commands",
                return_value=(("compile", ("python",)),),
            ), patch.object(
                RepositoryPatchLab,
                "_run_gate",
                return_value=self.passed_gate(),
            ), patch.object(
                lab,
                "_compare_strategy",
                side_effect=fake_compare,
            ):
                first = lab.evaluate(proposal)
                self.assertTrue(first.passed)
                self.assertEqual(first.certification_status, "certified_passed")
                self.assertIsNotNone(first.replay)
                first_call_count = len(compare_calls)
                self.assertEqual(first_call_count, 2)

                second = lab.evaluate(proposal)
                self.assertFalse(second.passed)
                self.assertEqual(
                    second.certification_status,
                    "fresh_replay_already_consumed",
                )
                self.assertIsNone(second.replay)
                self.assertEqual(len(compare_calls), first_call_count + 1)

            reservations = lab.certifications.records()
            self.assertEqual(len(reservations), 1)
            self.assertEqual(reservations[0].proposal_digest, proposal.digest)


if __name__ == "__main__":
    unittest.main()
