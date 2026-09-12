import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from dgm_zero.patch_search import (
    BoundedPatchSearchEngine,
    PatchDevelopmentScreen,
    search_identity,
    select_finalist,
)
from dgm_zero.patch_synthesis import SynthesizedPatch
from dgm_zero.self_patch import PatchFile, PatchProposal


def proposal(character: str) -> PatchProposal:
    return PatchProposal(
        rationale=f"candidate {character}",
        files=(
            PatchFile(
                relative_path="src/dgm_zero/meta_learning.py",
                base_sha256=character * 64,
                replacement_source=f"VALUE = {ord(character)}\n",
            ),
        ),
    )


def candidate(character: str, new_value: float) -> SynthesizedPatch:
    return SynthesizedPatch(
        focus="escape stagnation",
        knob="exploration_bias",
        old_value=1.5,
        new_value=new_value,
        proposal=proposal(character),
    )


def screen(
    item: SynthesizedPatch,
    *,
    aggregate: float,
    mean: float,
    worst: float,
    passed: bool = True,
) -> PatchDevelopmentScreen:
    return PatchDevelopmentScreen(
        proposal_digest=item.proposal.digest,
        focus=item.focus,
        knob=item.knob,
        old_value=item.old_value,
        new_value=item.new_value,
        passed=passed,
        reason="development_gain_verified" if passed else "development_regression",
        aggregate_delta=aggregate,
        mean_champion_delta=mean,
        worst_seed_champion_delta=worst,
        gates=(),
        comparison=None,
    )


class PatchSearchTests(unittest.TestCase):
    def test_select_finalist_prioritizes_aggregate_then_secondary_evidence(self):
        a = candidate("a", 1.35)
        b = candidate("b", 1.65)
        c = candidate("c", 1.80)
        selected = select_finalist(
            [
                screen(a, aggregate=0.01, mean=0.02, worst=0.0),
                screen(b, aggregate=0.02, mean=0.00, worst=0.0),
                screen(c, aggregate=0.02, mean=0.01, worst=-0.001),
            ]
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.proposal_digest, c.proposal.digest)

    def test_search_certifies_exactly_one_selected_finalist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            items = [candidate("a", 1.35), candidate("b", 1.65), candidate("c", 1.80)]
            fake_synth = Mock()
            fake_synth.generate_validated.return_value = items
            fake_lab = Mock()
            fake_lab.evaluate.return_value = SimpleNamespace(
                passed=False,
                certification_status="certified_failed",
                report_path=str(root / "cert.json"),
            )
            engine = BoundedPatchSearchEngine(
                repo,
                root / "workspace",
                lab=fake_lab,
                synthesizer=fake_synth,
            )
            screens = {
                items[0].proposal.digest: screen(items[0], aggregate=0.003, mean=0.0, worst=0.0),
                items[1].proposal.digest: screen(items[1], aggregate=0.012, mean=0.005, worst=0.0),
                items[2].proposal.digest: screen(items[2], aggregate=0.007, mean=0.02, worst=0.0),
            }
            engine._screen_candidate = Mock(
                side_effect=lambda item, timeout: screens[item.proposal.digest]
            )

            report = engine.run(max_candidates=3, focus="escape stagnation")

            self.assertTrue(report.certification_attempted)
            self.assertFalse(report.certification_passed)
            self.assertEqual(report.finalist_digest, items[1].proposal.digest)
            fake_lab.evaluate.assert_called_once()
            certified = fake_lab.evaluate.call_args.args[0]
            self.assertEqual(certified.digest, items[1].proposal.digest)

    def test_failed_certification_does_not_try_runner_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            items = [candidate("a", 1.35), candidate("b", 1.65)]
            fake_synth = Mock()
            fake_synth.generate_validated.return_value = items
            fake_lab = Mock()
            fake_lab.evaluate.return_value = SimpleNamespace(
                passed=False,
                certification_status="certified_failed",
                report_path="failed.json",
            )
            engine = BoundedPatchSearchEngine(
                repo,
                root / "workspace",
                lab=fake_lab,
                synthesizer=fake_synth,
            )
            engine._screen_candidate = Mock(
                side_effect=[
                    screen(items[0], aggregate=0.02, mean=0.01, worst=0.0),
                    screen(items[1], aggregate=0.01, mean=0.02, worst=0.0),
                ]
            )
            report = engine.run(max_candidates=2)
            self.assertFalse(report.certification_passed)
            fake_lab.evaluate.assert_called_once()

    def test_no_development_pass_means_no_fresh_certification_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            item = candidate("a", 1.35)
            fake_synth = Mock()
            fake_synth.generate_validated.return_value = [item]
            fake_lab = Mock()
            engine = BoundedPatchSearchEngine(
                repo,
                root / "workspace",
                lab=fake_lab,
                synthesizer=fake_synth,
            )
            engine._screen_candidate = Mock(
                return_value=screen(
                    item,
                    aggregate=-0.01,
                    mean=-0.01,
                    worst=-0.02,
                    passed=False,
                )
            )
            report = engine.run(max_candidates=1)
            self.assertFalse(report.certification_attempted)
            self.assertEqual(report.certification_status, "not_attempted")
            fake_lab.evaluate.assert_not_called()

    def test_search_identity_is_deterministic_and_commits_to_candidate_set(self):
        a = candidate("a", 1.35)
        b = candidate("b", 1.65)
        first = search_identity([a, b], focus="escape stagnation", max_candidates=2)
        second = search_identity([a, b], focus="escape stagnation", max_candidates=2)
        changed = search_identity([b, a], focus="escape stagnation", max_candidates=2)
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)


if __name__ == "__main__":
    unittest.main()
