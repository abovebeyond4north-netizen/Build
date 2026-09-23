from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT_ROOT / ".conceptlab_ci"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from conceptlab import run_campaign, verify_campaign
from p1 import run_p1, verify_p1
from p2 import run_p2, verify_p2
from p3 import run_p3, verify_p3
from p4 import run_p4, verify_p4
from p5 import run_p5, verify_p5


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    if not (WORKSPACE / "campaign_result.json").is_file():
        run_campaign(WORKSPACE)
    require(verify_campaign(WORKSPACE).all_p0_gates_passed, "P5 requires P0")
    if not (WORKSPACE / "p1_campaign_result.json").is_file():
        run_p1(WORKSPACE)
    require(verify_p1(WORKSPACE).all_p1_gates_passed, "P5 requires P1")
    if not (WORKSPACE / "p2_campaign_result.json").is_file():
        run_p2(WORKSPACE)
    require(verify_p2(WORKSPACE).all_p2_gates_passed, "P5 requires P2")
    if not (WORKSPACE / "p3_campaign_result.json").is_file():
        run_p3(WORKSPACE)
    require(verify_p3(WORKSPACE).all_p3_gates_passed, "P5 requires P3")
    if not (WORKSPACE / "p4_campaign_result.json").is_file():
        run_p4(WORKSPACE)
    require(verify_p4(WORKSPACE).all_p4_gates_passed, "P5 requires P4")

    result = run_p5(WORKSPACE)
    verified = verify_p5(WORKSPACE)
    require(result.all_p5_gates_passed, "ConceptLab P5 gates did not all pass")
    require(not result.clg1_unlocked, "P5 must not unlock CLG-1")
    require(
        verified.evidence_ledger_tip == result.evidence_ledger_tip,
        "P5 evidence ledger tip changed during verification",
    )

    print("ConceptLab P5 raw-token discovery validation complete")
    print(f"manifest={result.manifest_commitment}")
    print(f"controllers_unchanged={result.controllers_unchanged}")
    print(f"P5 evidence ledger tip: {result.evidence_ledger_tip}")
    for item in result.family_results:
        print(
            f"{item.family_id}: "
            f"feature={item.learned_feature} "
            f"support={item.support_accuracy:.3f} "
            f"D7={item.d7_accuracy:.3f} "
            f"legacy={item.legacy_numeric_accuracy:.3f} "
            f"runner={item.runner_up_accuracy:.3f} "
            f"control={item.strongest_control_accuracy:.3f} "
            f"gain={item.control_gain:.3f} "
            f"restart={item.restart_accuracy:.3f}"
        )
    print("CLG-1 unlocked: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
