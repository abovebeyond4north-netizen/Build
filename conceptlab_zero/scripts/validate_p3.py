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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    if not (WORKSPACE / "campaign_result.json").is_file():
        run_campaign(WORKSPACE)
    require(
        verify_campaign(WORKSPACE).all_p0_gates_passed,
        "P3 requires passing P0",
    )
    if not (WORKSPACE / "p1_campaign_result.json").is_file():
        run_p1(WORKSPACE)
    require(
        verify_p1(WORKSPACE).all_p1_gates_passed,
        "P3 requires passing P1",
    )
    if not (WORKSPACE / "p2_campaign_result.json").is_file():
        run_p2(WORKSPACE)
    require(
        verify_p2(WORKSPACE).all_p2_gates_passed,
        "P3 requires passing P2",
    )

    result = run_p3(WORKSPACE)
    verified = verify_p3(WORKSPACE)
    require(result.all_p3_gates_passed, "ConceptLab P3 gates did not all pass")
    require(not result.clg1_unlocked, "P3 must not unlock CLG-1")
    require(
        verified.evidence_ledger_tip == result.evidence_ledger_tip,
        "P3 evidence ledger tip changed during verification",
    )

    print("ConceptLab P3 withheld-predicate synthesis validation complete")
    print(f"P2 evidence ledger tip: {result.p2_evidence_ledger_tip}")
    print(f"P3 evidence ledger tip: {result.evidence_ledger_tip}")
    for item in result.synthesis_results:
        print(
            f"{item.opaque_target_id}: "
            f"program={item.synthesized_signature} "
            f"train={item.train_accuracy:.3f} "
            f"D5={item.d5_accuracy:.3f} "
            f"P0={item.p0_control_accuracy:.3f} "
            f"gain={item.p0_control_gain:.3f} "
            f"compression={item.compression_ratio:.2f}x "
            f"restart={item.restart_accuracy:.3f}"
        )
    print("CLG-1 unlocked: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
