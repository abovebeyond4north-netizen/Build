from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT_ROOT / ".conceptlab_ci"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from conceptlab import run_campaign, verify_campaign
from p1 import run_p1, verify_p1


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    if not (WORKSPACE / "campaign_result.json").is_file():
        run_campaign(WORKSPACE)
    p0 = verify_campaign(WORKSPACE)
    require(p0.all_p0_gates_passed, "P1 requires a passing P0 campaign")

    result = run_p1(WORKSPACE)
    verified = verify_p1(WORKSPACE)
    require(result.all_p1_gates_passed, "ConceptLab P1 gates did not all pass")
    require(not result.clg1_unlocked, "P1 must not unlock CLG-1")
    require(
        verified.evidence_ledger_tip == result.evidence_ledger_tip,
        "P1 evidence ledger tip changed during verification",
    )

    print("ConceptLab P1 causal validation complete")
    print(f"P0 manifest commitment: {result.p0_manifest_commitment}")
    print(f"P1 evidence ledger tip: {result.evidence_ledger_tip}")
    for item in result.principle_results:
        print(
            f"{item.opaque_principle_id}: "
            f"counterfactual={item.counterfactual_accuracy:.3f} "
            f"capsule={item.capsule_score:.3f} "
            f"ablated={item.ablated_score:.3f} "
            f"ablation_fraction={item.ablation_fraction:.3f}"
        )
    print("CLG-1 unlocked: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
