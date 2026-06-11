from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
CI_WORKSPACE = PROJECT_ROOT / ".dgm_workspace_ci"


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


def main() -> int:
    if CI_WORKSPACE.exists():
        shutil.rmtree(CI_WORKSPACE)
    run_step("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"])
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
    print("\nValidation complete")
    print(f"workspace: {CI_WORKSPACE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
