import json
import tempfile
import unittest
from pathlib import Path

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.capability_model import CapabilityCase, CapabilitySpec
from dgm_zero.capability_sandbox import SkillSandbox


def normalize_spec() -> CapabilitySpec:
    return CapabilitySpec(
        "normalize_text",
        "normalize case and internal whitespace",
        "solve",
        (
            CapabilityCase(
                "train_spaces",
                "train",
                ("  Hello   WORLD  ",),
                "hello world",
            ),
            CapabilityCase(
                "train_case",
                "train",
                ("A  B",),
                "a b",
            ),
            CapabilityCase(
                "validation_mixed",
                "validation",
                ("  Mixed CASE",),
                "mixed case",
            ),
            CapabilityCase(
                "holdout_tabs",
                "holdout",
                ("\tNEW   Value\n",),
                "new value",
            ),
        ),
    )


class CapabilityModelTests(unittest.TestCase):
    def test_requires_all_three_splits(self):
        with self.assertRaises(ValueError):
            CapabilitySpec(
                "incomplete",
                "missing holdout",
                "solve",
                (
                    CapabilityCase("t", "train", (1,), 1),
                    CapabilityCase("v", "validation", (2,), 2),
                ),
            )

    def test_load_json_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capability.json"
            path.write_text(
                json.dumps(
                    {
                        "name": "identity",
                        "description": "return the input",
                        "entrypoint": "solve",
                        "cases": [
                            {
                                "name": "t",
                                "split": "train",
                                "args": [1],
                                "expected": 1,
                            },
                            {
                                "name": "v",
                                "split": "validation",
                                "args": [2],
                                "expected": 2,
                            },
                            {
                                "name": "h",
                                "split": "holdout",
                                "args": [3],
                                "expected": 3,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            spec = CapabilitySpec.load(path)
            self.assertEqual(spec.name, "identity")
            self.assertEqual(spec.arity, 1)


class SkillSandboxTests(unittest.TestCase):
    def test_blocks_imports_and_dunder_traversal(self):
        sandbox = SkillSandbox(timeout_seconds=0.5)
        passed, reasons = sandbox.validate_source(
            "import os\n\ndef solve(x0):\n    return x0.__class__\n",
            "solve",
        )
        self.assertFalse(passed)
        self.assertTrue(
            any("Import" in reason or "import" in reason for reason in reasons)
        )
        self.assertTrue(any("__class__" in reason for reason in reasons))

    def test_times_out_infinite_candidate(self):
        sandbox = SkillSandbox(timeout_seconds=0.15)
        result = sandbox.evaluate(
            "def solve(x0):\n    while True:\n        pass\n",
            "solve",
            (CapabilityCase("loop", "train", (1,), 1),),
        )
        self.assertEqual(result.correctness, 0.0)
        self.assertTrue(
            any("timed out" in error for error in result.errors)
        )


class CapabilityAcquisitionTests(unittest.TestCase):
    def test_acquires_and_versions_text_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            report = CapabilityAcquirer(workspace).acquire(normalize_spec())
            self.assertTrue(report.promoted)
            self.assertEqual(report.status, "promoted")
            self.assertEqual(report.train_score, 1.0)
            self.assertEqual(report.validation_score, 1.0)
            self.assertEqual(report.holdout_score, 1.0)
            self.assertEqual(report.holdout_evaluations, 1)
            self.assertIsNotNone(report.installed_path)
            installed = Path(report.installed_path)
            self.assertTrue(installed.is_file())
            self.assertIn(".lower()", installed.read_text(encoding="utf-8"))
            current = (
                workspace
                / "capabilities"
                / "normalize_text"
                / "current.json"
            )
            self.assertTrue(current.is_file())

    def test_reusing_certification_suite_does_not_reexpose_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            acquirer = CapabilityAcquirer(Path(tmp))
            first = acquirer.acquire(normalize_spec())
            second = acquirer.acquire(normalize_spec())
            self.assertTrue(first.promoted)
            self.assertEqual(second.status, "already_certified")
            self.assertFalse(second.promoted)
            self.assertEqual(second.holdout_evaluations, 0)
            self.assertIsNone(second.holdout_score)

    def test_failed_holdout_is_consumed_once(self):
        spec = CapabilitySpec(
            "affine_shift",
            "fit public x+1 examples while holdout differs",
            "solve",
            (
                CapabilityCase("t1", "train", (1,), 2),
                CapabilityCase("t2", "train", (2,), 3),
                CapabilityCase("v1", "validation", (5,), 6),
                CapabilityCase("h1", "holdout", (10,), 12),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            acquirer = CapabilityAcquirer(Path(tmp))
            first = acquirer.acquire(spec)
            second = acquirer.acquire(spec)
            self.assertEqual(first.status, "holdout_failed")
            self.assertEqual(first.holdout_evaluations, 1)
            self.assertFalse(first.promoted)
            self.assertEqual(second.status, "holdout_suite_consumed")
            self.assertEqual(second.holdout_evaluations, 0)

    def test_acquires_different_sequence_capability(self):
        spec = CapabilitySpec(
            "sequence_span",
            "compute maximum minus minimum",
            "solve",
            (
                CapabilityCase("t1", "train", ([1, 5, 3],), 4),
                CapabilityCase("t2", "train", ([-2, 4],), 6),
                CapabilityCase("v1", "validation", ([10, 10],), 0),
                CapabilityCase("h1", "holdout", ([-5, 0, 7],), 12),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = CapabilityAcquirer(Path(tmp)).acquire(spec)
            self.assertTrue(report.promoted)
            self.assertEqual(report.final_score, 1.0)

    def test_affine_synthesis_acquires_numeric_relation(self):
        spec = CapabilitySpec(
            "linear_relation",
            "learn a small affine relationship",
            "solve",
            (
                CapabilityCase("t1", "train", (1, 2), 5),
                CapabilityCase("t2", "train", (2, 1), 4),
                CapabilityCase("t3", "train", (3, 4), 11),
                CapabilityCase("v1", "validation", (-2, 5), 8),
                CapabilityCase("h1", "holdout", (7, -3), 1),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = CapabilityAcquirer(Path(tmp)).acquire(
                spec,
                validation_budget=24,
            )
            self.assertTrue(report.promoted)
            self.assertEqual(report.final_score, 1.0)


if __name__ == "__main__":
    unittest.main()
