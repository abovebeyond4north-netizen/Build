import unittest

from dgm_zero.capability_model import CapabilityCase
from dgm_zero.capability_sandbox import SkillSandbox


class CapabilitySandboxStateTests(unittest.TestCase):
    def test_rejects_mutable_default_state(self):
        sandbox = SkillSandbox()
        source = (
            "def solve(x0, seen=[]):\n"
            "    seen.append(x0)\n"
            "    return len(seen)\n"
        )
        passed, reasons = sandbox.validate_source(source, "solve")
        self.assertFalse(passed)
        self.assertTrue(any("default arguments" in reason for reason in reasons))

    def test_evaluation_fails_closed_for_default_arguments(self):
        sandbox = SkillSandbox()
        result = sandbox.evaluate(
            "def solve(x0=1):\n    return x0\n",
            "solve",
            (CapabilityCase("case", "train", (1,), 1),),
        )
        self.assertEqual(result.correctness, 0.0)
        self.assertTrue(any("default arguments" in reason for reason in result.errors))

    def test_rejects_function_object_state_writes(self):
        sandbox = SkillSandbox()
        source = (
            "def solve(x0):\n"
            "    try:\n"
            "        solve.counter += 1\n"
            "    except AttributeError:\n"
            "        solve.counter = 1\n"
            "    return solve.counter\n"
        )
        passed, reasons = sandbox.validate_source(source, "solve")
        self.assertFalse(passed)
        self.assertTrue(any("write or delete attributes" in reason for reason in reasons))

    def test_attribute_reads_remain_available(self):
        sandbox = SkillSandbox()
        passed, reasons = sandbox.validate_source(
            "def solve(x0):\n    return x0.strip().lower()\n",
            "solve",
        )
        self.assertTrue(passed)
        self.assertEqual(reasons, ())

    def test_plain_fixed_positional_function_remains_valid(self):
        sandbox = SkillSandbox()
        passed, reasons = sandbox.validate_source(
            "def solve(x0):\n    return x0\n",
            "solve",
        )
        self.assertTrue(passed)
        self.assertEqual(reasons, ())


if __name__ == "__main__":
    unittest.main()
