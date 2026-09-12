import tempfile
import unittest
from pathlib import Path

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.capability_model import (
    CapabilityCase,
    CapabilityEvidencePolicy,
    CapabilitySpec,
    SkillCandidate,
    SuiteScore,
)
from dgm_zero.objective import ObjectiveCompiler


class ManyCandidateGenerator:
    def generate(self, view, *, prior_source, max_candidates):
        count = min(max_candidates, 10)
        return [
            SkillCandidate(
                f'"""candidate {index}"""\ndef {view.entrypoint}(x0):\n    return x0\n',
                f"candidate-{index}",
            )
            for index in range(count)
        ]


class PassingSandbox:
    def __init__(self):
        self.calls = []

    def evaluate(self, source, entrypoint, cases):
        cases = tuple(cases)
        self.calls.append((source, entrypoint, cases))
        return SuiteScore(len(cases), len(cases), 0.0, ())


class CapabilityEvidencePolicyTests(unittest.TestCase):
    def test_policy_rejects_nonpositive_and_boolean_limits(self):
        for kwargs in (
            {"min_train_cases": 0},
            {"min_validation_cases": False},
            {"min_holdout_cases": -1},
            {"max_validation_trials_per_case": 0},
            {"max_validation_trials_per_case": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    CapabilityEvidencePolicy(**kwargs)

    def test_spec_enforces_declared_minimum_evidence(self):
        evidence = CapabilityEvidencePolicy(
            min_train_cases=1,
            min_validation_cases=2,
            min_holdout_cases=1,
        )
        with self.assertRaisesRegex(ValueError, "at least 2 validation"):
            CapabilitySpec(
                "weak_validation",
                "insufficient validation evidence",
                "solve",
                (
                    CapabilityCase("train", "train", (1,), 1),
                    CapabilityCase("validation", "validation", (2,), 2),
                    CapabilityCase("holdout", "holdout", (3,), 3),
                ),
                evidence=evidence,
            )

    def test_json_evidence_policy_round_trips_into_spec(self):
        spec = CapabilitySpec.from_dict(
            {
                "name": "identity",
                "description": "return the input",
                "entrypoint": "solve",
                "evidence": {
                    "min_train_cases": 1,
                    "min_validation_cases": 1,
                    "min_holdout_cases": 1,
                    "max_validation_trials_per_case": 3,
                },
                "cases": [
                    {"name": "t", "split": "train", "args": [1], "expected": 1},
                    {"name": "v", "split": "validation", "args": [2], "expected": 2},
                    {"name": "h", "split": "holdout", "args": [3], "expected": 3},
                ],
            }
        )
        self.assertEqual(spec.evidence.max_validation_trials_per_case, 3)
        self.assertEqual(spec.validation_trial_limit(), 3)

    def test_built_in_objectives_require_stronger_evidence(self):
        compiler = ObjectiveCompiler()
        for objective in (
            "normalize text",
            "sequence span",
            "clamp values",
            "improve python debugging ability",
        ):
            with self.subTest(objective=objective):
                spec = compiler.compile(objective)
                self.assertGreaterEqual(len(spec.cases_for("train")), 2)
                self.assertGreaterEqual(len(spec.cases_for("validation")), 3)
                self.assertGreaterEqual(len(spec.cases_for("holdout")), 3)
                self.assertEqual(spec.evidence.min_validation_cases, 3)
                self.assertEqual(spec.evidence.min_holdout_cases, 3)
                self.assertEqual(spec.validation_trial_limit(), 12)

    def test_validation_trials_are_capped_relative_to_evidence(self):
        evidence = CapabilityEvidencePolicy(
            min_train_cases=1,
            min_validation_cases=2,
            min_holdout_cases=1,
            max_validation_trials_per_case=2,
        )
        spec = CapabilitySpec(
            "bounded_identity",
            "identity with bounded validation reuse",
            "solve",
            (
                CapabilityCase("t1", "train", (1,), 1),
                CapabilityCase("v1", "validation", (2,), 2),
                CapabilityCase("v2", "validation", (3,), 3),
                CapabilityCase("h1", "holdout", (4,), 4),
            ),
            evidence=evidence,
        )
        sandbox = PassingSandbox()
        with tempfile.TemporaryDirectory() as tmp:
            report = CapabilityAcquirer(
                Path(tmp),
                generator=ManyCandidateGenerator(),
                sandbox=sandbox,
            ).acquire(
                spec,
                max_candidates=10,
                validation_budget=50,
            )

        self.assertEqual(spec.validation_trial_limit(), 4)
        self.assertEqual(report.candidates_generated, 10)
        self.assertEqual(report.candidates_trained, 10)
        self.assertEqual(report.candidates_validated, 4)

    def test_custom_specs_keep_unbounded_legacy_default(self):
        spec = CapabilitySpec(
            "legacy_custom",
            "legacy-compatible custom capability",
            "solve",
            (
                CapabilityCase("t", "train", (1,), 1),
                CapabilityCase("v", "validation", (2,), 2),
                CapabilityCase("h", "holdout", (3,), 3),
            ),
        )
        self.assertIsNone(spec.validation_trial_limit())


if __name__ == "__main__":
    unittest.main()
