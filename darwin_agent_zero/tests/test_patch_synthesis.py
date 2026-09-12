import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.patch_synthesis import (
    BoundedPolicyPatchSynthesizer,
    META_POLICY_PATH,
    POLICY_MAX,
    POLICY_MIN,
    write_synthesized_patches,
)
from dgm_zero.self_patch import PatchProposal, RepositoryPatchLab


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
        if state.focus == "repair correctness":
            return MetaLearningPolicy(novelty_bias=0.75, simplification_bias=1.30, exploration_bias=0.85, curriculum_bias=0.60)
        if state.focus == "escape stagnation":
            return MetaLearningPolicy(novelty_bias=1.60, simplification_bias=0.85, exploration_bias=1.50, curriculum_bias=0.75)
        if state.focus == "increase diversity":
            return MetaLearningPolicy(novelty_bias=1.80, simplification_bias=0.90, exploration_bias=1.30, curriculum_bias=0.80)
        if state.focus == "mine failures":
            return MetaLearningPolicy(novelty_bias=1.20, simplification_bias=1.00, exploration_bias=1.10, curriculum_bias=0.90)
        if state.focus == "raise curriculum":
            return MetaLearningPolicy(novelty_bias=1.00, simplification_bias=1.10, exploration_bias=0.95, curriculum_bias=1.40)
        return MetaLearningPolicy()
'''


class PatchSynthesisTests(unittest.TestCase):
    @staticmethod
    def make_repo(root: Path) -> Path:
        repo = root / "repo"
        target = repo / META_POLICY_PATH
        target.parent.mkdir(parents=True)
        (repo / "pyproject.toml").write_text(
            "[project]\nname='fixture'\nversion='0.0.0'\n",
            encoding="utf-8",
        )
        (target.parent / "__init__.py").write_text("", encoding="utf-8")
        (target.parent / "metacognition.py").write_text(
            "class CognitiveState:\n    focus = ''\n",
            encoding="utf-8",
        )
        target.write_text(META_SOURCE, encoding="utf-8")
        return repo

    def test_generation_is_deterministic_bounded_and_does_not_edit_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            target = repo / META_POLICY_PATH
            original = target.read_text(encoding="utf-8")
            synth = BoundedPolicyPatchSynthesizer(repo)
            first = synth.generate(max_candidates=8)
            second = synth.generate(max_candidates=8)

            self.assertEqual(len(first), 8)
            self.assertEqual(
                [item.proposal.digest for item in first],
                [item.proposal.digest for item in second],
            )
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            for candidate in first:
                self.assertGreaterEqual(candidate.new_value, POLICY_MIN)
                self.assertLessEqual(candidate.new_value, POLICY_MAX)
                self.assertNotEqual(candidate.old_value, candidate.new_value)
                self.assertEqual(len(candidate.proposal.files), 1)
                self.assertEqual(candidate.proposal.files[0].relative_path, META_POLICY_PATH)

    def test_focus_filter_only_changes_requested_policy_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            candidates = BoundedPolicyPatchSynthesizer(repo).generate(
                max_candidates=8,
                focus="escape stagnation",
            )
            self.assertEqual(len(candidates), 8)
            self.assertTrue(all(item.focus == "escape stagnation" for item in candidates))
            replacement = candidates[0].proposal.files[0].replacement_source
            self.assertIn('state.focus == \'escape stagnation\'', replacement)

    def test_generated_candidates_pass_static_patch_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            lab = RepositoryPatchLab(repo, root / "workspace")
            candidates = BoundedPolicyPatchSynthesizer(repo).generate_validated(
                lab,
                max_candidates=6,
            )
            self.assertEqual(len(candidates), 6)
            self.assertTrue(all(lab.validate(item.proposal).passed for item in candidates))

    def test_written_files_are_directly_loadable_patch_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self.make_repo(root)
            candidates = BoundedPolicyPatchSynthesizer(repo).generate(max_candidates=2)
            paths = write_synthesized_patches(root / "proposals", candidates)
            self.assertEqual(len(paths), 2)
            for path, candidate in zip(paths, candidates):
                loaded = PatchProposal.load(path)
                self.assertEqual(loaded.digest, candidate.proposal.digest)
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["synthesis"]["focus"], candidate.focus)

    def test_invalid_focus_and_candidate_budget_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(Path(tmp))
            synth = BoundedPolicyPatchSynthesizer(repo)
            with self.assertRaisesRegex(ValueError, "max_candidates"):
                synth.generate(max_candidates=0)
            with self.assertRaisesRegex(ValueError, "unsupported metacognitive focus"):
                synth.generate(focus="invent a new evaluator")


if __name__ == "__main__":
    unittest.main()
