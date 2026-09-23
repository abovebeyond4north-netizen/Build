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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    if not (WORKSPACE / "campaign_result.json").is_file():
        run_campaign(WORKSPACE)
    p0 = verify_campaign(WORKSPACE)
    require(p0.all_p0_gates_passed, "P2 requires passing P0")

    if not (WORKSPACE / "p1_campaign_result.json").is_file():
        run_p1(WORKSPACE)
    p1 = verify_p1(WORKSPACE)
    require(p1.all_p1_gates_passed, "P2 requires passing P1")

    result = run_p2(WORKSPACE)
    verified = verify_p2(WORKSPACE)
    require(result.all_p2_gates_passed, "ConceptLab P2 gates did not all pass")
    require(not result.clg1_unlocked, "P2 must not unlock CLG-1")
    require(
        verified.evidence_ledger_tip == result.evidence_ledger_tip,
        "P2 evidence ledger tip changed during verification",
    )

    print("ConceptLab P2 composition/revision/persistence validation complete")
    print(f"P1 evidence ledger tip: {result.p1_evidence_ledger_tip}")
    print(f"P2 evidence ledger tip: {result.evidence_ledger_tip}")
    print(
        "D4 composition: "
        f"operator={result.composition_operator} "
        f"accuracy={result.d4_accuracy:.3f} "
        f"control={result.d4_strongest_control:.3f} "
        f"gain={result.d4_control_gain:.3f}"
    )
    print(
        "Revision: "
        f"{result.revision.before_signature} -> "
        f"{result.revision.after_signature} "
        f"contradictions={result.revision.contradiction_count} "
        f"holdout={result.revised_holdout_accuracy:.3f}"
    )
    print(
        "Retention: "
        f"before={result.unaffected_before_accuracy:.3f} "
        f"after={result.unaffected_after_accuracy:.3f} "
        f"digest_unchanged={result.unaffected_digest_unchanged}"
    )
    print(
        "Restart: "
        f"primitive={result.restart_primitive_a_accuracy:.3f} "
        f"revised={result.restart_revised_accuracy:.3f} "
        f"composite={result.restart_composite_accuracy:.3f} "
        f"episode_artifacts={result.persisted_episode_artifacts}"
    )
    print("CLG-1 unlocked: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
