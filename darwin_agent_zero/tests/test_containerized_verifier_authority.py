import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dgm_zero.protected_evaluator import ProtectedEvaluator


BASELINE = "def solve(x0):\n    return None\n"
NORMALIZER = (
    "def solve(x0):\n"
    "    return ' '.join(x0.lower().split())\n"
)


def docker_enabled() -> bool:
    return (
        os.environ.get("DGM_VERIFIER_AUTHORITY_MODE") == "container"
        and shutil.which(os.environ.get("DGM_DOCKER_BIN", "docker")) is not None
        and bool(os.environ.get("DGM_VERIFIER_AUTHORITY_IMAGE"))
    )


@unittest.skipUnless(
    docker_enabled(),
    "containerized verifier authority is not enabled",
)
class ContainerizedVerifierAuthorityTests(unittest.TestCase):
    def make_evaluator(self, root: Path) -> ProtectedEvaluator:
        evaluator = ProtectedEvaluator(root / "workspace")
        self.addCleanup(
            subprocess.run,
            [
                evaluator.docker_bin,
                "volume",
                "rm",
                "-f",
                evaluator.authority_volume,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return evaluator

    def test_hardening_flags_are_part_of_every_authority_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = self.make_evaluator(Path(tmp))
            command = evaluator._container_run_command("describe")
            joined = "\n".join(command)

            for required in (
                "--network\nnone",
                "--read-only",
                "--cap-drop\nALL",
                "--security-opt\nno-new-privileges:true",
                "--pids-limit\n64",
                "--memory\n256m",
                "--memory-swap\n256m",
                "--cpus\n1.0",
                "--tmpfs\n/tmp:rw,noexec,nosuid,nodev,size=64m",
                "target=/state",
            ):
                self.assertIn(required, joined)

            self.assertNotIn("/var/run/docker.sock", joined)
            self.assertNotIn("type=bind", joined)
            self.assertNotIn("--privileged", command)

    def test_real_container_evaluation_proves_isolation_and_keeps_key_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.make_evaluator(root)
            decision = evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )

            self.assertTrue(decision.passed)
            trust = json.loads(
                (
                    root
                    / "workspace"
                    / "verifier_authority_trust.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(trust["runtime_mode"], "container")
            self.assertTrue(
                str(trust["runtime_image_id"]).startswith("sha256:")
            )
            self.assertNotIn(
                str(trust["runtime_user"]).strip(),
                {"", "0", "root", "0:0"},
            )

            private_keys = list(
                (root / "workspace").rglob("authority-private.pem")
            )
            self.assertEqual(private_keys, [])

            inspected = subprocess.run(
                [
                    evaluator.docker_bin,
                    "volume",
                    "inspect",
                    evaluator.authority_volume,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                inspected.returncode,
                0,
                inspected.stderr,
            )

    def test_trusted_image_digest_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = self.make_evaluator(root)
            evaluator.evaluate(
                capability="normalize_text",
                entrypoint="solve",
                baseline_source=BASELINE,
                finalist_source=NORMALIZER,
                required_score=1.0,
                minimum_gain=0.05,
            )
            trust_path = (
                root
                / "workspace"
                / "verifier_authority_trust.json"
            )
            trust = json.loads(
                trust_path.read_text(encoding="utf-8")
            )
            trust["runtime_image_id"] = "sha256:" + ("0" * 64)
            trust_path.write_text(
                json.dumps(trust, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "container image changed",
            ):
                evaluator.evaluate(
                    capability="normalize_text",
                    entrypoint="solve",
                    baseline_source=BASELINE,
                    finalist_source=NORMALIZER,
                    required_score=1.0,
                    minimum_gain=0.05,
                )

    def test_missing_hardened_image_never_falls_back_to_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evaluator = ProtectedEvaluator(
                root / "workspace",
                authority_image=(
                    "dgm-verifier-authority:"
                    "definitely-not-present"
                ),
                authority_mode="container",
            )
            self.addCleanup(
                subprocess.run,
                [
                    evaluator.docker_bin,
                    "volume",
                    "rm",
                    "-f",
                    evaluator.authority_volume,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            with self.assertRaisesRegex(
                ValueError,
                "image is unavailable",
            ):
                evaluator.evaluate(
                    capability="normalize_text",
                    entrypoint="solve",
                    baseline_source=BASELINE,
                    finalist_source=NORMALIZER,
                    required_score=1.0,
                    minimum_gain=0.05,
                )
            self.assertFalse(
                (root / "authority-state").exists()
            )


class ContainerCommandUnitTests(unittest.TestCase):
    def test_container_command_has_no_host_bind_or_docker_socket(self):
        docker = shutil.which(sys.executable)
        self.assertIsNotNone(docker)
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = ProtectedEvaluator(
                Path(tmp) / "workspace",
                authority_mode="container",
                authority_image="test-authority:unit",
                docker_bin=sys.executable,
            )
            command = evaluator._container_run_command("describe")
            self.assertNotIn("--privileged", command)
            rendered = " ".join(command)
            self.assertNotIn("/var/run/docker.sock", rendered)
            self.assertNotIn("type=bind", rendered)
            self.assertIn("--read-only", command)
            self.assertIn("none", command)


if __name__ == "__main__":
    unittest.main()
