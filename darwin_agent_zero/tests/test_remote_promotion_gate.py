import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.capability_model import SkillCandidate
from dgm_zero.capability_sandbox import SkillSandbox
from dgm_zero.objective import ObjectiveCompiler


NORMALIZER = (
    "def solve(x0):\n"
    "    return ' '.join(x0.lower().split())\n"
)
REMOTE_HASH = "e" * 64


class NormalizerGenerator:
    def generate(self, view, *, prior_source, max_candidates):
        return [SkillCandidate(NORMALIZER, "normalizer")]


class CountingSandbox(SkillSandbox):
    def __init__(self):
        super().__init__(timeout_seconds=1.0)
        self.holdout_calls = 0

    def evaluate(self, source, entrypoint, cases):
        cases = tuple(cases)
        if cases and cases[0].split == "holdout":
            self.holdout_calls += 1
        return super().evaluate(source, entrypoint, cases)


class PassingProtectedEvaluator:
    def evaluate(self, **kwargs):
        return SimpleNamespace(passed=True, record_hash="d" * 64)


class FakeRemoteVerifier:
    def __init__(self, *, passed=True, error=None):
        self.passed = passed
        self.error = error
        self.calls = 0

    def evaluate(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            passed=self.passed,
            record_hash=REMOTE_HASH,
        )


class RemotePromotionGateTests(unittest.TestCase):
    def make_acquirer(self, workspace, remote):
        sandbox = CountingSandbox()
        acquirer = CapabilityAcquirer(
            workspace,
            generator=NormalizerGenerator(),
            sandbox=sandbox,
            remote_verifier=remote,
            remote_verifier_mode="required",
        )
        acquirer.protected_evaluator = PassingProtectedEvaluator()
        return acquirer, sandbox

    def test_remote_failure_keeps_sealed_holdout_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            remote = FakeRemoteVerifier(passed=False)
            acquirer, sandbox = self.make_acquirer(workspace, remote)

            report = acquirer.acquire(
                ObjectiveCompiler().compile("normalize text")
            )

            self.assertFalse(report.promoted)
            self.assertEqual(report.status, "remote_evaluator_failed")
            self.assertEqual(report.holdout_evaluations, 0)
            self.assertEqual(sandbox.holdout_calls, 0)
            self.assertEqual(remote.calls, 1)
            self.assertIsNone(
                acquirer.library.current("normalize_text")
            )

    def test_remote_unavailability_fails_closed_before_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            remote = FakeRemoteVerifier(
                error=ValueError("attestation unavailable")
            )
            acquirer, sandbox = self.make_acquirer(workspace, remote)

            report = acquirer.acquire(
                ObjectiveCompiler().compile("normalize text")
            )

            self.assertFalse(report.promoted)
            self.assertEqual(
                report.status,
                "remote_evaluator_unavailable",
            )
            self.assertEqual(report.holdout_evaluations, 0)
            self.assertEqual(sandbox.holdout_calls, 0)

    def test_remote_pass_becomes_promotion_evidence_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            remote = FakeRemoteVerifier(passed=True)
            acquirer, sandbox = self.make_acquirer(workspace, remote)

            report = acquirer.acquire(
                ObjectiveCompiler().compile("normalize text")
            )

            self.assertTrue(report.promoted)
            self.assertEqual(report.status, "promoted")
            self.assertEqual(report.holdout_evaluations, 1)
            self.assertGreater(sandbox.holdout_calls, 0)
            current = acquirer.library.current("normalize_text")
            self.assertIsNotNone(current)
            _, manifest = current
            self.assertEqual(
                manifest["evidence_record_hash"],
                REMOTE_HASH,
            )


if __name__ == "__main__":
    unittest.main()
