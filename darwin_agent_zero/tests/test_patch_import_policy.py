import unittest

from dgm_zero.patch_policy import patch_import_reasons


class PatchImportPolicyTests(unittest.TestCase):
    def test_mutation_allows_existing_safe_dependencies(self):
        source = (
            "from __future__ import annotations\n"
            "import ast\n"
            "import random\n"
        )
        self.assertEqual(
            patch_import_reasons("src/dgm_zero/mutation.py", source),
            (),
        )

    def test_dynamic_loader_import_is_rejected(self):
        reasons = patch_import_reasons(
            "src/dgm_zero/mutation.py",
            "import importlib\n",
        )
        self.assertTrue(any("importlib" in reason for reason in reasons))

    def test_relative_privilege_proxy_is_rejected(self):
        reasons = patch_import_reasons(
            "src/dgm_zero/meta_learning.py",
            "from .self_patch import RepositoryPatchLab\n",
        )
        self.assertTrue(any("self_patch" in reason for reason in reasons))

    def test_expected_relative_import_is_allowed(self):
        reasons = patch_import_reasons(
            "src/dgm_zero/meta_learning.py",
            "from .metacognition import CognitiveState\n",
        )
        self.assertEqual(reasons, ())

    def test_star_import_is_rejected(self):
        reasons = patch_import_reasons(
            "src/dgm_zero/self_instruction.py",
            "from .memory import *\n",
        )
        self.assertTrue(any("star import" in reason for reason in reasons))

    def test_unknown_editable_path_has_no_implicit_policy(self):
        reasons = patch_import_reasons(
            "src/dgm_zero/unknown.py",
            "VALUE = 1\n",
        )
        self.assertTrue(any("no import policy" in reason for reason in reasons))


if __name__ == "__main__":
    unittest.main()
