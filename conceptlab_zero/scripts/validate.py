from __future__ import annotations

import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT_ROOT / ".conceptlab_ci"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from conceptlab import run_campaign, verify_campaign


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    result = run_campaign(WORKSPACE)
    verified = verify_campaign(WORKSPACE)

    require(result.all_p0_gates_passed, "ConceptLab P0 gates did not all pass")
    require(not result.clg1_unlocked, "P0 must not unlock CLG-1")
    require(
        verified.evidence_ledger_tip == result.evidence_ledger_tip,
        "verified evidence ledger tip changed",
    )
    require(
        all(item.exact_recovery for item in result.principle_results),
        "not every hidden principle was exactly recovered",
    )

    print("ConceptLab P0 validation complete")
    print(f"manifest commitment: {result.manifest_commitment}")
    print(f"evidence ledger tip: {result.evidence_ledger_tip}")
    for item in result.principle_results:
        print(
            f"{item.opaque_principle_id}: {item.recovered_signature} "
            f"D3={item.d3_accuracy:.3f} "
            f"control_gain={item.d3_control_gain:.3f} "
            f"compression={item.compression_ratio:.2f}x"
        )
    print("CLG-1 unlocked: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
