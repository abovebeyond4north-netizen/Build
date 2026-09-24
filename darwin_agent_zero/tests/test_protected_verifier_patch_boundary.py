import unittest

from dgm_zero.self_patch import DEFAULT_EDITABLE_PATHS


class ProtectedVerifierPatchBoundaryTests(unittest.TestCase):
    def test_self_patch_cannot_edit_verification_authority(self):
        protected = {
            "src/dgm_zero/protected_evaluator.py",
            "src/dgm_zero/protected_evaluator_worker.py",
            "src/dgm_zero/reliability_gate.py",
            "src/dgm_zero/remote_verifier.py",
            "src/dgm_zero/capability.py",
            "src/dgm_zero/skill_library.py",
            "src/dgm_zero/checkpoint.py",
            "src/dgm_zero/patch_policy.py",
            "src/dgm_zero/self_patch.py",
        }
        self.assertTrue(protected.isdisjoint(DEFAULT_EDITABLE_PATHS))
        self.assertNotIn(
            "verifier_authority/authority.py",
            DEFAULT_EDITABLE_PATHS,
        )
        self.assertTrue(
            all(path.startswith("src/dgm_zero/") for path in DEFAULT_EDITABLE_PATHS)
        )


if __name__ == "__main__":
    unittest.main()
