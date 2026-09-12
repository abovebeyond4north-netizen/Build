import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.patch_search_memory import PatchSearchMemory
from dgm_zero.patch_synthesis import BoundedPolicyPatchSynthesizer


META_SOURCE = '''from __future__ import annotations
from dataclasses import dataclass
from .metacognition import CognitiveState

@dataclass(frozen=True)
class MetaLearningPolicy:
    novelty_bias: float = 1.0
    simplification_bias: float = 1.0
    exploration_bias: float = 1.0
    curriculum_bias: float = 1.0

class MetaLearner:
    def policy_from_state(self, state: CognitiveState) -> MetaLearningPolicy:
        if state.focus == "escape stagnation":
            return MetaLearningPolicy(novelty_bias=1.60, simplification_bias=0.85, exploration_bias=1.50, curriculum_bias=0.75)
        return MetaLearningPolicy()
'''


class PatchSearchMemoryTests(unittest.TestCase):
    def test_duplicate_search_proposal_does_not_double_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = PatchSearchMemory(Path(tmp))
            kwargs = dict(
                search_digest="a" * 64,
                proposal_digest="b" * 64,
                focus="escape stagnation",
                knob="exploration_bias",
                direction=1,
                step=0.15,
                aggregate_delta=0.02,
                passed=True,
                reason="development_gain_verified",
            )
            first = memory.record(**kwargs)
            second = memory.record(**kwargs)
            self.assertEqual(first.record_hash, second.record_hash)
            self.assertEqual(len(memory.records()), 1)

    def test_conflicting_duplicate_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = PatchSearchMemory(Path(tmp))
            base = dict(
                search_digest="a" * 64,
                proposal_digest="b" * 64,
                focus="escape stagnation",
                knob="exploration_bias",
                direction=1,
                step=0.15,
                passed=True,
                reason="development_gain_verified",
            )
            memory.record(**base, aggregate_delta=0.02)
            with self.assertRaisesRegex(ValueError, "conflicting"):
                memory.record(**base, aggregate_delta=0.03)

    def test_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = PatchSearchMemory(Path(tmp))
            memory.record(
                search_digest="a" * 64,
                proposal_digest="b" * 64,
                focus="escape stagnation",
                knob="novelty_bias",
                direction=-1,
                step=0.15,
                aggregate_delta=-0.01,
                passed=False,
                reason="development_regression",
            )
            data = json.loads(memory.path.read_text(encoding="utf-8").strip())
            data["aggregate_delta"] = 0.5
            memory.path.write_text(json.dumps(data) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "record hash mismatch"):
                memory.records()

    def test_unseen_adjustments_explore_before_seen_and_positive_beats_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = PatchSearchMemory(Path(tmp))
            unseen = memory.priority("escape stagnation", "curriculum_bias", 1)
            memory.record(
                search_digest="a" * 64,
                proposal_digest="b" * 64,
                focus="escape stagnation",
                knob="exploration_bias",
                direction=1,
                step=0.15,
                aggregate_delta=0.03,
                passed=True,
                reason="development_gain_verified",
            )
            positive = memory.priority("escape stagnation", "exploration_bias", 1)
            self.assertGreater(unseen, positive)

            memory.record(
                search_digest="c" * 64,
                proposal_digest="d" * 64,
                focus="escape stagnation",
                knob="exploration_bias",
                direction=-1,
                step=0.15,
                aggregate_delta=-0.04,
                passed=False,
                reason="development_regression",
            )
            negative = memory.priority("escape stagnation", "exploration_bias", -1)
            positive = memory.priority("escape stagnation", "exploration_bias", 1)
            self.assertGreater(positive, negative)

    def test_synthesizer_uses_priority_to_allocate_limited_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            target = repo / "src" / "dgm_zero" / "meta_learning.py"
            target.parent.mkdir(parents=True)
            (repo / "pyproject.toml").write_text(
                "[project]\nname='fixture'\nversion='0.0.0'\n",
                encoding="utf-8",
            )
            target.write_text(META_SOURCE, encoding="utf-8")
            synth = BoundedPolicyPatchSynthesizer(repo)

            def priority(focus, knob, direction):
                return 100.0 if knob == "curriculum_bias" and direction == 1 else 0.0

            candidates = synth.generate(
                max_candidates=1,
                focus="escape stagnation",
                priority_fn=priority,
            )
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].knob, "curriculum_bias")
            self.assertEqual(candidates[0].direction, 1)


if __name__ == "__main__":
    unittest.main()
