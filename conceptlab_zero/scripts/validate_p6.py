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
from p6 import run_p6, verify_p6


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    if not (WORKSPACE / "campaign_result.json").is_file():
        run_campaign(WORKSPACE)
    require(verify_campaign(WORKSPACE).all_p0_gates_passed, "P6 requires P0")
    if not (WORKSPACE / "p1_campaign_result.json").is_file():
        run_p1(WORKSPACE)
    require(verify_p1(WORKSPACE).all_p1_gates_passed, "P6 requires P1")
    if not (WORKSPACE / "p2_campaign_result.json").is_file():
        run_p2(WORKSPACE)
    require(verify_p2(WORKSPACE).all_p2_gates_passed, "P6 requires P2")
    if not (WORKSPACE / "p3_campaign_result.json").is_file():
        run_p3(WORKSPACE)
    require(verify_p3(WORKSPACE).all_p3_gates_passed, "P6 requires P3")
    if not (WORKSPACE / "p4_campaign_result.json").is_file():
        run_p4(WORKSPACE)
    require(verify_p4(WORKSPACE).all_p4_gates_passed, "P6 requires P4")
    if not (WORKSPACE / "p5_campaign_result.json").is_file():
        run_p5(WORKSPACE)
    require(verify_p5(WORKSPACE).all_p5_gates_passed, "P6 requires P5")

    result = run_p6(WORKSPACE)
    verified = verify_p6(WORKSPACE)
    require(result.all_p6_gates_passed, "ConceptLab P6 gates did not all pass")
    require(not result.clg1_unlocked, "P6 must not unlock CLG-1")
    require(
        verified.evidence_ledger_tip == result.evidence_ledger_tip,
        "P6 evidence ledger tip changed during verification",
    )

    print("ConceptLab P6 active-curriculum validation complete")
    print(f"controller_unchanged={result.controller_unchanged}")
    print(f"P6 evidence ledger tip: {result.evidence_ledger_tip}")
    for item in result.curriculum_results:
        print(
            f"{item.family_id}: "
            f"active={item.active_queries} "
            f"passive_mean={item.passive_mean_queries:.3f} "
            f"passive_median={item.passive_median_queries:.3f} "
            f"ratio={item.efficiency_ratio:.3f} "
            f"D8={item.d8_accuracy:.3f} "
            f"candidates={item.initial_candidates}"
        )
    print("CLG-1 unlocked: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
