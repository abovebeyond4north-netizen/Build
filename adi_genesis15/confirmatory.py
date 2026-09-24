from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .experiment import run_adaptation_sweep, run_block

PRIMARY = range(20000, 20020)
REPLICATION = range(24000, 24020)
BUDGETS = (4, 8, 12, 24)

def gates(s: dict[str, float]) -> dict[str, bool]:
    finite = all(math.isfinite(float(v)) for v in s.values())
    return {
        "finite": finite,
        "multistep_vs_raw": s["multistep_improvement_vs_raw"] >= 0.50,
        "planning_vs_raw": s["planning_regret_improvement_vs_raw"] >= 0.50,
        "coverage_90": 0.82 <= s["coverage_90"] <= 0.96,
        "interval_width": s["interval_width_90"] <= 0.50,
        "shift_detection": s["shift_detection_rate"] >= 0.80,
        "false_positive": s["false_positive_rate"] <= 0.10,
        "detection_delay": s["mean_detection_delay"] <= 10.0,
        "adapt_vs_unadapted": s["adaptation_improvement_vs_unadapted"] >= 0.10,
        "adapt_vs_raw": s["adaptation_improvement_vs_raw"] >= 0.10,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="genesis15_confirmatory.json")
    args = parser.parse_args()
    primary = run_block(PRIMARY)
    replication = run_block(REPLICATION)
    pg = gates(primary["summary"])
    rg = gates(replication["summary"])
    result = {
        "experiment": "ADI Genesis-15",
        "claim": "uncertainty-gated partially observed world-model component",
        "primary": primary,
        "replication": replication,
        "primary_gates": pg,
        "replication_gates": rg,
        "adaptation_sweep_replication": run_adaptation_sweep(REPLICATION, BUDGETS),
        "status": "PASS" if all(pg.values()) and all(rg.values()) else "FAIL",
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
