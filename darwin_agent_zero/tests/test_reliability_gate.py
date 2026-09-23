import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.capability_model import CapabilityCase, SuiteScore
from dgm_zero.reliability_gate import IndependentReliabilityGate, ReliabilityLedger


BASELINE = "def solve(x0):\n    return 0\n"
FINALIST = "def solve(x0):\n    return x0\n"


class FixedSandbox:
    def evaluate(self, source, entrypoint, cases):
        if source == BASELINE:
            passed = 0
        else:
            passed = len(cases)
        return SuiteScore(
            passed=passed,
            total=len(cases),
            elapsed_seconds=0.0,
            errors=(),
        )


class OrderSensitiveSandbox:
    def evaluate(self, source, entrypoint, cases):
        if source == BASELINE:
            passed = 0
        else:
            passed = len(cases) if cases[0].name in {"b", "c"} else len(cases) - 1
        return SuiteScore(
            passed=passed,
            total=len(cases),
            elapsed_seconds=0.0,
            errors=(),
        )


def validation_cases():
    return (
        CapabilityCase("a", "validation", (1,), 1),
        CapabilityCase("b", "validation", (2,), 2),
        CapabilityCase("c", "validation", (3,), 3),
        CapabilityCase("d", "validation", (4,), 4),
    )


class ReliabilityGateTests(unittest.TestCase):
    def test_paired_replays_require_stable_gain_and_write_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = IndependentReliabilityGate(
                Path(tmp),
                replay_seeds=(1, 2, 3, 4),
            )
            decision = gate.evaluate(
                capability="identity",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                entrypoint="solve",
                validation_cases=validation_cases(),
                sandbox=FixedSandbox(),
                minimum_gain=0.5,
            )

            self.assertTrue(decision.passed)
            self.assertEqual(decision.reason, "passed")
            self.assertEqual(decision.worst_delta, 1.0)
            self.assertEqual(len(decision.trials), 4)
            self.assertTrue(decision.record_hash)

            loaded = ReliabilityLedger(Path(tmp)).records()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].record_hash, decision.record_hash)

    def test_same_evidence_is_reused_without_retesting(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = IndependentReliabilityGate(
                Path(tmp),
                replay_seeds=(1, 2),
            )
            sandbox = FixedSandbox()
            first = gate.evaluate(
                capability="identity",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                entrypoint="solve",
                validation_cases=validation_cases(),
                sandbox=sandbox,
                minimum_gain=0.5,
            )
            second = gate.evaluate(
                capability="identity",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                entrypoint="solve",
                validation_cases=tuple(reversed(validation_cases())),
                sandbox=sandbox,
                minimum_gain=0.5,
            )
            self.assertEqual(first.record_hash, second.record_hash)
            self.assertEqual(len(gate.ledger.records()), 1)

    def test_order_sensitive_candidate_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = IndependentReliabilityGate(
                Path(tmp),
                replay_seeds=(1, 2, 3, 4),
            )
            decision = gate.evaluate(
                capability="identity",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                entrypoint="solve",
                validation_cases=validation_cases(),
                sandbox=OrderSensitiveSandbox(),
                minimum_gain=0.5,
            )
            self.assertFalse(decision.passed)
            self.assertEqual(decision.reason, "order_instability")

    def test_identical_candidate_is_an_explicit_failed_ablation(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = IndependentReliabilityGate(Path(tmp), replay_seeds=(1, 2))
            decision = gate.evaluate(
                capability="identity",
                baseline_source=BASELINE,
                finalist_source=BASELINE,
                entrypoint="solve",
                validation_cases=validation_cases(),
                sandbox=FixedSandbox(),
                minimum_gain=0.0,
            )
            self.assertFalse(decision.passed)
            self.assertEqual(decision.reason, "identical_to_baseline")

    def test_tampered_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            gate = IndependentReliabilityGate(workspace, replay_seeds=(1, 2))
            gate.evaluate(
                capability="identity",
                baseline_source=BASELINE,
                finalist_source=FINALIST,
                entrypoint="solve",
                validation_cases=validation_cases(),
                sandbox=FixedSandbox(),
                minimum_gain=0.5,
            )
            path = workspace / "reliability_gate.jsonl"
            data = json.loads(path.read_text(encoding="utf-8").strip())
            data["worst_delta"] = 0.0
            path.write_text(json.dumps(data) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "record hash mismatch"):
                ReliabilityLedger(workspace).records()


if __name__ == "__main__":
    unittest.main()
