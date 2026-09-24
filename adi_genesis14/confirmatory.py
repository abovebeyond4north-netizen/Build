from __future__ import annotations

import argparse
import json

from adi_genesis13.experiment import write_json

from .experiment import run_block


PRIMARY_SEEDS = tuple(range(12000, 12020))
REPLICATION_SEEDS = tuple(range(16000, 16020))

GATES = {
    "multistep_improvement_vs_raw": 0.80,
    "planning_regret_improvement_vs_raw": 0.80,
    "planning_candidate_regret_max": 0.05,
    "exploitation_gap_improvement_vs_raw": 0.75,
    "shift_improvement_vs_unadapted": 0.15,
    "shift_improvement_vs_raw_fewshot": 0.30,
}


def gate_block(summary: dict[str, float]) -> dict[str, bool]:
    return {
        "multistep_improvement_vs_raw": (
            summary["multistep_improvement_vs_raw"]
            >= GATES["multistep_improvement_vs_raw"]
        ),
        "planning_regret_improvement_vs_raw": (
            summary["planning_regret_improvement_vs_raw"]
            >= GATES["planning_regret_improvement_vs_raw"]
        ),
        "planning_candidate_regret_max": (
            summary["planning_candidate_regret"]
            <= GATES["planning_candidate_regret_max"]
        ),
        "exploitation_gap_improvement_vs_raw": (
            summary["exploitation_gap_improvement_vs_raw"]
            >= GATES["exploitation_gap_improvement_vs_raw"]
        ),
        "shift_improvement_vs_unadapted": (
            summary["shift_improvement_vs_unadapted"]
            >= GATES["shift_improvement_vs_unadapted"]
        ),
        "shift_improvement_vs_raw_fewshot": (
            summary["shift_improvement_vs_raw_fewshot"]
            >= GATES["shift_improvement_vs_raw_fewshot"]
        ),
    }


def run_confirmatory() -> dict:
    primary = run_block(
        PRIMARY_SEEDS,
        shift_adaptation_steps=8,
    )
    replication = run_block(
        REPLICATION_SEEDS,
        shift_adaptation_steps=8,
    )

    primary_gates = gate_block(primary["summary"])
    replication_gates = gate_block(replication["summary"])

    sweep = {
        str(steps): run_block(
            REPLICATION_SEEDS,
            shift_adaptation_steps=steps,
        )["summary"]
        for steps in (4, 8, 12, 24)
    }

    passed = all(primary_gates.values()) and all(replication_gates.values())

    return {
        "experiment": "ADI Genesis-14",
        "status": "PASS" if passed else "FAIL",
        "primary_seed_range": [PRIMARY_SEEDS[0], PRIMARY_SEEDS[-1]],
        "replication_seed_range": [
            REPLICATION_SEEDS[0],
            REPLICATION_SEEDS[-1],
        ],
        "gates": GATES,
        "primary": primary,
        "replication": replication,
        "primary_gate_results": primary_gates,
        "replication_gate_results": replication_gates,
        "secondary_shift_budget_sweep": sweep,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="genesis14_confirmatory.json",
        help="Path for the complete result ledger JSON.",
    )
    args = parser.parse_args()

    report = run_confirmatory()
    write_json(args.output, report)

    print(
        json.dumps(
            {
                "status": report["status"],
                "primary": report["primary"]["summary"],
                "replication": report["replication"]["summary"],
                "primary_gate_results": report["primary_gate_results"],
                "replication_gate_results": report[
                    "replication_gate_results"
                ],
                "secondary_shift_budget_sweep": report[
                    "secondary_shift_budget_sweep"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
