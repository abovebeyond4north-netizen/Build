from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
CI_WORKSPACE = PROJECT_ROOT / ".dgm_workspace_ci"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def validation_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else f"{SRC_ROOT}{os.pathsep}{existing}"
    return env


def run_step(name: str, command: list[str]) -> None:
    print(f"\n==> {name}")
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=validation_env())
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def seed_validation_baseline() -> None:
    """Seed a known-good baseline only for artifact/health validation.

    This is deliberately outside the evolver seed list. It lets validation check
    reporting, health, provenance, checkpoints, and restore plumbing without
    weakening the research search space used by normal runs.
    """

    from dgm_zero.archive import Archive

    Archive(CI_WORKSPACE).append(
        generation=-1,
        parent_id=None,
        expression="a * a + 3 * b - gcd(a, b)",
        score={
            "correctness": 1.0,
            "efficiency": 1.0,
            "novelty": 1.0,
            "safety": 1.0,
            "simplicity": 0.8,
            "generalization": 1.0,
            "weighted_total": 0.98,
        },
        accepted=True,
        reason="validation baseline",
    )


def load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"missing expected artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_artifacts() -> None:
    print("\n==> inspect artifacts")
    expected = [
        "archive.jsonl",
        "evolution_report.json",
        "health_report.json",
        "provenance.json",
        "operator_bandit.json",
        "mined_cases.json",
        "map_elites.json",
        "champion.py",
        "checkpoints/latest.json",
    ]
    for name in expected:
        path = CI_WORKSPACE / name
        if not path.exists():
            raise SystemExit(f"missing expected artifact: {path}")

    health = load_json(CI_WORKSPACE / "health_report.json")
    if not health.get("passed"):
        raise SystemExit(f"health check failed: {health}")

    report = load_json(CI_WORKSPACE / "evolution_report.json")
    checkpoint = report.get("checkpoint", {})
    if not checkpoint.get("healthy"):
        raise SystemExit(f"checkpoint was not healthy: {checkpoint}")
    copied_files = set(checkpoint.get("copied_files", []))
    for name in ["evolution_report.json", "health_report.json", "provenance.json", "champion.py"]:
        if name not in copied_files:
            raise SystemExit(f"checkpoint did not copy {name}: {checkpoint}")

    provenance = load_json(CI_WORKSPACE / "provenance.json")
    artifact_paths = {item["path"] for item in provenance.get("artifacts", [])}
    for name in ["evolution_report.json", "health_report.json", "champion.py"]:
        if name not in artifact_paths:
            raise SystemExit(f"provenance missing artifact fingerprint for {name}: {artifact_paths}")


def main() -> int:
    if CI_WORKSPACE.exists():
        shutil.rmtree(CI_WORKSPACE)
    run_step("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    seed_validation_baseline()
    run_step(
        "smoke evolution",
        [
            sys.executable,
            "-m",
            "dgm_zero.cli",
            "run",
            "--generations",
            "2",
            "--population",
            "4",
            "--workspace",
            str(CI_WORKSPACE),
        ],
    )
    inspect_artifacts()
    print("\nValidation complete")
    print(f"workspace: {CI_WORKSPACE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
