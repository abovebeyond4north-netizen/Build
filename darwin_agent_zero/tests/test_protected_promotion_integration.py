import tempfile
import unittest
from pathlib import Path

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.capability_model import SkillCandidate
from dgm_zero.capability_sandbox import SkillSandbox
from dgm_zero.objective import ObjectiveCompiler


OVERFIT_NORMALIZER = r'''def solve(x0):
    if x0 == "  Hello   WORLD  ":
        return "hello world"
    if x0 == "A  B":
        return "a b"
    if x0 == "  Mixed CASE":
        return "mixed case"
    if x0 == "ONE\n\nTwo":
        return "one two"
    if x0 == "A\t B\tC":
        return "a b c"
    return x0
'''


class OverfitGenerator:
    def generate(self, view, *, prior_source, max_candidates):
        return [SkillCandidate(OVERFIT_NORMALIZER, "visible-suite-overfit")]


class CountingSandbox(SkillSandbox):
    def __init__(self):
        super().__init__(timeout_seconds=1.0)
        self.visible_holdout_calls = 0

    def evaluate(self, source, entrypoint, cases):
        cases = tuple(cases)
        if cases and cases[0].split == "holdout":
            self.visible_holdout_calls += 1
        return super().evaluate(source, entrypoint, cases)


class ProtectedPromotionIntegrationTests(unittest.TestCase):
    def test_visible_suite_overfit_is_rejected_before_sealed_holdout(self):
        spec = ObjectiveCompiler().compile("normalize text")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            sandbox = CountingSandbox()
            report = CapabilityAcquirer(
                workspace,
                generator=OverfitGenerator(),
                sandbox=sandbox,
            ).acquire(spec)

            self.assertFalse(report.promoted)
            self.assertEqual(report.status, "protected_evaluator_failed")
            self.assertEqual(report.holdout_evaluations, 0)
            self.assertEqual(sandbox.visible_holdout_calls, 0)
            self.assertTrue((workspace / "protected_evaluator.jsonl").is_file())
            self.assertFalse(
                (
                    workspace
                    / "capabilities"
                    / "normalize_text"
                    / "current.json"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
