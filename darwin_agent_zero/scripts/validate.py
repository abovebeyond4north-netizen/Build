from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
CI_WORKSPACE = PROJECT_ROOT / ".dgm_workspace_ci"
VALIDATION_SUMMARY = CI_WORKSPACE / "validation_summary.json"

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


def inspect_artifacts() -> dict[str, object]:
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

    return {
        "expected_artifacts": expected,
        "health_passed": bool(health.get("passed")),
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "checkpoint_copied_files": sorted(copied_files),
        "provenance_artifacts": sorted(artifact_paths),
        "champion_expression": report.get("champion_expression"),
        "accepted_records": report.get("accepted_records"),
        "total_records": report.get("total_records"),
    }


def validate_restore_path() -> dict[str, object]:
    print("\n==> validate restore path")
    from dgm_zero.checkpoint import CheckpointManager

    original_report = (CI_WORKSPACE / "evolution_report.json").read_text(encoding="utf-8")
    original_provenance = (CI_WORKSPACE / "provenance.json").read_text(encoding="utf-8")
    original_champion = (CI_WORKSPACE / "champion.py").read_text(encoding="utf-8")

    (CI_WORKSPACE / "evolution_report.json").write_text('{"corrupt": true}\n', encoding="utf-8")
    (CI_WORKSPACE / "provenance.json").write_text('{"corrupt": true}\n', encoding="utf-8")
    (CI_WORKSPACE / "champion.py").write_text("# corrupt\n", encoding="utf-8")

    restored = CheckpointManager(CI_WORKSPACE).restore_latest()
    if not restored.restored:
        raise SystemExit(f"restore failed: {restored}")
    for name in ["evolution_report.json", "provenance.json", "champion.py"]:
        if name not in restored.restored_files:
            raise SystemExit(f"restore did not include {name}: {restored.restored_files}")

    restored_report = (CI_WORKSPACE / "evolution_report.json").read_text(encoding="utf-8")
    restored_provenance = (CI_WORKSPACE / "provenance.json").read_text(encoding="utf-8")
    restored_champion = (CI_WORKSPACE / "champion.py").read_text(encoding="utf-8")
    if restored_report != original_report:
        raise SystemExit("restored evolution_report.json did not match final report")
    if restored_provenance != original_provenance:
        raise SystemExit("restored provenance.json did not match final provenance")
    if restored_champion != original_champion:
        raise SystemExit("restored champion.py did not match final champion")

    return {
        "restored": restored.restored,
        "checkpoint_id": restored.checkpoint_id,
        "restored_files": restored.restored_files,
        "reason": restored.reason,
    }


def write_validation_summary(artifact_summary: dict[str, object], restore_summary: dict[str, object]) -> None:
    summary = {
        "passed": True,
        "created_at": time.time(),
        "workspace": str(CI_WORKSPACE),
        "steps": ["unit tests", "smoke evolution", "inspect artifacts", "restore corruption check"],
        "artifacts": artifact_summary,
        "restore": restore_summary,
    }
    VALIDATION_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


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
    artifact_summary = inspect_artifacts()
    restore_summary = validate_restore_path()
    write_validation_summary(artifact_summary, restore_summary)
    print("\nValidation complete")
    print(f"workspace: {CI_WORKSPACE}")
    print(f"summary: {VALIDATION_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
