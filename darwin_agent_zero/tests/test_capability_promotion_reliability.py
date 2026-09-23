import tempfile
import unittest
from pathlib import Path

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.capability_model import (
    CapabilityCase,
    CapabilitySpec,
    CapabilityThresholds,
    SkillCandidate,
    SuiteScore,
)


CANDIDATE_SOURCE = "def solve(x0):\n    return x0\n"


class SingleCandidateGenerator:
    def generate(self, view, *, prior_source, max_candidates):
        return [SkillCandidate(CANDIDATE_SOURCE, "identity")]


class OrderSensitiveIntegrationSandbox:
    def __init__(self):
        self.holdout_calls = 0

    def evaluate(self, source, entrypoint, cases):
        cases = tuple(cases)
        split = cases[0].split
        if split == "holdout":
            self.holdout_calls += 1

        is_candidate = source == CANDIDATE_SOURCE
        if not is_candidate:
            passed = 0
        elif split == "train":
            passed = len(cases)
        elif split == "validation":
            passed = len(cases) if cases[0].name == "v1" else len(cases) - 1
        else:
            passed = len(cases)

        return SuiteScore(
            passed=passed,
            total=len(cases),
            elapsed_seconds=0.0,
            errors=(),
        )


def reliability_spec():
    return CapabilitySpec(
        "reliability_identity",
        "identity candidate used to prove fail-closed promotion",
        "solve",
        (
            CapabilityCase("t1", "train", (1,), 1),
            CapabilityCase("v1", "validation", (2,), 2),
            CapabilityCase("v2", "validation", (3,), 3),
            CapabilityCase("v3", "validation", (4,), 4),
            CapabilityCase("v4", "validation", (5,), 5),
            CapabilityCase("h1", "holdout", (6,), 6),
        ),
        thresholds=CapabilityThresholds(
            train=1.0,
            validation=1.0,
            holdout=1.0,
            min_gain=0.5,
        ),
    )


class CapabilityPromotionReliabilityTests(unittest.TestCase):
    def test_reliability_failure_preserves_holdout_and_incumbent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            sandbox = OrderSensitiveIntegrationSandbox()
            report = CapabilityAcquirer(
                workspace,
                generator=SingleCandidateGenerator(),
                sandbox=sandbox,
            ).acquire(reliability_spec())

            self.assertFalse(report.promoted)
            self.assertEqual(report.status, "reliability_gate_failed")
            self.assertEqual(report.holdout_evaluations, 0)
            self.assertEqual(sandbox.holdout_calls, 0)
            self.assertFalse(
                (
                    workspace
                    / "capabilities"
                    / "reliability_identity"
                    / "current.json"
                ).exists()
            )
            self.assertTrue((workspace / "reliability_gate.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
