from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
WORKSPACE = PROJECT_ROOT / ".dgm_capability_ci"
SUMMARY = WORKSPACE / "capability_validation_summary.json"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.capability_model import CapabilitySpec


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def run_example(name: str) -> dict[str, object]:
    spec_path = PROJECT_ROOT / "examples" / "capabilities" / name
    spec = CapabilitySpec.load(spec_path)
    report = CapabilityAcquirer(WORKSPACE).acquire(
        spec,
        validation_budget=24,
    )
    require(report.promoted, f"{spec.name} was not promoted: {report}")
    require(report.final_score == 1.0, f"{spec.name} final score was not 1.0")
    require(report.train_score == 1.0, f"{spec.name} train score was not 1.0")
    require(
        report.validation_score == 1.0,
        f"{spec.name} validation score was not 1.0",
    )
    require(
        report.holdout_score == 1.0,
        f"{spec.name} holdout score was not 1.0",
    )
    require(
        report.holdout_evaluations == 1,
        f"{spec.name} did not use exactly one holdout evaluation",
    )
    require(
        report.installed_path is not None
        and Path(report.installed_path).is_file(),
        f"{spec.name} did not install a versioned skill",
    )
    return {
        "capability": spec.name,
        "status": report.status,
        "baseline_score": report.baseline_score,
        "final_score": report.final_score,
        "holdout_evaluations": report.holdout_evaluations,
        "installed_path": report.installed_path,
        "holdout_digest": report.holdout_digest,
    }


def verify_holdout_reuse_blocked() -> dict[str, object]:
    spec = CapabilitySpec.load(
        PROJECT_ROOT
        / "examples"
        / "capabilities"
        / "normalize_text.json"
    )
    second = CapabilityAcquirer(WORKSPACE).acquire(spec)
    require(
        second.status == "already_certified",
        f"expected already_certified, got {second.status}",
    )
    require(
        second.holdout_evaluations == 0,
        "certified holdout suite was evaluated more than once",
    )
    require(
        second.holdout_score is None,
        "reused holdout score should not be re-exposed",
    )
    return {
        "status": second.status,
        "holdout_evaluations": second.holdout_evaluations,
    }


def main() -> int:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)

    examples = [
        run_example("normalize_text.json"),
        run_example("sequence_span.json"),
    ]
    reuse = verify_holdout_reuse_blocked()
    summary = {
        "passed": True,
        "examples": examples,
        "holdout_reuse": reuse,
    }
    SUMMARY.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print("Capability acquisition validation complete")
    print(f"summary: {SUMMARY}")
    for result in examples:
        print(
            f"{result['capability']}: "
            f"{result['baseline_score']} -> {result['final_score']}"
        )
    print("holdout reuse: blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
