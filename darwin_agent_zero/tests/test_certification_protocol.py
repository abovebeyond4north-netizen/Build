import unittest

from dgm_zero.capability_model import CapabilityCase, CapabilitySpec
from dgm_zero.skill_library import holdout_digest


def make_spec(*, train_value=1, validation_value=2, holdout_value=3):
    return CapabilitySpec(
        "identity",
        "return the input",
        "solve",
        (
            CapabilityCase("train", "train", (train_value,), train_value),
            CapabilityCase("validation", "validation", (validation_value,), validation_value),
            CapabilityCase("holdout", "holdout", (holdout_value,), holdout_value),
        ),
    )


class CertificationProtocolTests(unittest.TestCase):
    def test_training_or_validation_changes_do_not_unlock_holdout(self):
        original = make_spec()
        changed_search_data = make_spec(train_value=10, validation_value=20)
        self.assertEqual(holdout_digest(original), holdout_digest(changed_search_data))

    def test_holdout_changes_produce_new_certification_identity(self):
        original = make_spec()
        changed_holdout = make_spec(holdout_value=30)
        self.assertNotEqual(holdout_digest(original), holdout_digest(changed_holdout))

    def test_digest_is_deterministic(self):
        spec = make_spec()
        self.assertEqual(holdout_digest(spec), holdout_digest(spec))
        self.assertEqual(len(holdout_digest(spec)), 64)


if __name__ == "__main__":
    unittest.main()
