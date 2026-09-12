import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.curriculum import CurriculumManager, CurriculumState
from dgm_zero.evolver import DarwinAgentZero, EvolutionConfig
from dgm_zero.sota_methods import UCBOperatorBandit


class ContextAwareBanditTests(unittest.TestCase):
    def test_first_context_assignment_preserves_legacy_evidence(self):
        bandit = UCBOperatorBandit(["wrap"])
        for _ in range(4):
            bandit.update("wrap", 0.75)
        changed = bandit.adapt_context("level-0", retention=0.5)
        self.assertFalse(changed)
        self.assertEqual(bandit.arms["wrap"].pulls, 4)
        self.assertAlmostEqual(bandit.arms["wrap"].reward_sum, 3.0)
        self.assertEqual(bandit.context, "level-0")

    def test_same_context_does_not_decay_learning(self):
        bandit = UCBOperatorBandit(["wrap"])
        bandit.adapt_context("level-0")
        for _ in range(4):
            bandit.update("wrap", 1.0)
        changed = bandit.adapt_context("level-0", retention=0.25)
        self.assertFalse(changed)
        self.assertEqual(bandit.arms["wrap"].pulls, 4)
        self.assertEqual(bandit.arms["wrap"].reward_sum, 4.0)

    def test_new_context_discounts_stale_evidence(self):
        bandit = UCBOperatorBandit(["wrap", "replace"])
        bandit.adapt_context("level-0")
        for _ in range(8):
            bandit.update("wrap", 1.0)
        for _ in range(4):
            bandit.update("replace", 0.5)

        changed = bandit.adapt_context("level-1", retention=0.5)
        self.assertTrue(changed)
        self.assertEqual(bandit.context, "level-1")
        self.assertEqual(bandit.arms["wrap"].pulls, 4)
        self.assertAlmostEqual(bandit.arms["wrap"].reward_sum, 4.0)
        self.assertEqual(bandit.arms["replace"].pulls, 2)
        self.assertAlmostEqual(bandit.arms["replace"].reward_sum, 1.0)

    def test_small_stale_history_becomes_unseen_again(self):
        bandit = UCBOperatorBandit(["wrap"])
        bandit.adapt_context("old")
        bandit.update("wrap", 1.0)
        bandit.adapt_context("new", retention=0.5)
        self.assertEqual(bandit.arms["wrap"].pulls, 0)
        self.assertEqual(bandit.arms["wrap"].reward_sum, 0.0)
        self.assertEqual(bandit.choose(), "wrap")

    def test_context_round_trip_and_legacy_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "operator_bandit.json"
            bandit = UCBOperatorBandit(["wrap"])
            bandit.adapt_context("level-2")
            bandit.update("wrap", 0.8)
            bandit.save(path)

            loaded = UCBOperatorBandit.load(path, ["wrap"])
            self.assertEqual(loaded.context, "level-2")
            self.assertEqual(loaded.arms["wrap"].pulls, 1)

            path.write_text(
                json.dumps(
                    {
                        "exploration": 1.4,
                        "arms": {
                            "wrap": {
                                "name": "wrap",
                                "pulls": 3,
                                "reward_sum": 1.5,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            legacy = UCBOperatorBandit.load(path, ["wrap"])
            self.assertIsNone(legacy.context)
            legacy.adapt_context("current", retention=0.1)
            self.assertEqual(legacy.arms["wrap"].pulls, 3)

    def test_invalid_context_and_retention_fail_closed(self):
        bandit = UCBOperatorBandit(["wrap"])
        with self.assertRaisesRegex(ValueError, "context"):
            bandit.adapt_context("   ")
        for retention in (-0.1, 1.1, True):
            with self.subTest(retention=retention):
                with self.assertRaisesRegex(ValueError, "retention"):
                    bandit.adapt_context("x", retention=retention)  # type: ignore[arg-type]

    def test_evolver_context_changes_with_curriculum_and_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            base = DarwinAgentZero(
                workspace,
                EvolutionConfig(
                    generations=1,
                    population=1,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            level_zero = base.operator_context_key()

            base.curriculum_state = CurriculumState(
                current=CurriculumManager.level_for(1)
            )
            level_one = base.operator_context_key()
            self.assertNotEqual(level_zero, level_one)

            stricter = DarwinAgentZero(
                Path(tmp) / "strict",
                EvolutionConfig(
                    generations=1,
                    population=1,
                    accept_threshold=0.8,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            self.assertNotEqual(level_zero, stricter.operator_context_key())


if __name__ == "__main__":
    unittest.main()
