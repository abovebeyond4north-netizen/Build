from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiment import run_block, write_json


PRIMARY_SEEDS = tuple(range(5000, 5020))
REPLICATION_SEEDS = tuple(range(9000, 9020))

GATES = {
    "improvement_vs_pooled": 0.70,
    "improvement_vs_fewshot": 0.50,
    "shuffled_to_candidate_ratio": 2.50,
    "structure_f1": 0.95,
    "max_dynamics_abs_error": 0.10,
    "compression_ratio": 2.50,
}


def _gate_block(summary: dict[str, float]) -> dict[str, bool]:
    return {
        "improvement_vs_pooled": summary["improvement_vs_pooled"]
        >= GATES["improvement_vs_pooled"],
        "improvement_vs_fewshot": summary["improvement_vs_fewshot"]
        >= GATES["improvement_vs_fewshot"],
        "shuffled_to_candidate_ratio": summary["shuffled_to_candidate_ratio"]
        >= GATES["shuffled_to_candidate_ratio"],
        "structure_f1": summary["structure_f1"] >= GATES["structure_f1"],
        "max_dynamics_abs_error": summary["max_dynamics_abs_error"]
        <= GATES["max_dynamics_abs_error"],
        "compression_ratio": summary["compression_ratio"] >= GATES["compression_ratio"],
    }


def run_confirmatory() -> dict:
    primary = run_block(PRIMARY_SEEDS, pairs_per_action=1)
    replication = run_block(REPLICATION_SEEDS, pairs_per_action=1)

    primary_gates = _gate_block(primary["summary"])
    replication_gates = _gate_block(replication["summary"])

    sweep = {
        str(pairs): run_block(REPLICATION_SEEDS, pairs_per_action=pairs)["summary"]
        for pairs in (1, 2, 4)
    }

    passed = all(primary_gates.values()) and all(replication_gates.values())

    return {
        "experiment": "ADI Genesis-13",
        "status": "PASS" if passed else "FAIL",
        "primary_seed_range": [PRIMARY_SEEDS[0], PRIMARY_SEEDS[-1]],
        "replication_seed_range": [REPLICATION_SEEDS[0], REPLICATION_SEEDS[-1]],
        "gates": GATES,
        "primary": primary,
        "replication": replication,
        "primary_gate_results": primary_gates,
        "replication_gate_results": replication_gates,
        "secondary_replication_budget_sweep": sweep,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="genesis13_confirmatory.json",
        help="Path for the complete result ledger JSON.",
    )
    args = parser.parse_args()

    report = run_confirmatory()
    write_json(args.output, report)

    print(json.dumps(
        {
            "status": report["status"],
            "primary": report["primary"]["summary"],
            "replication": report["replication"]["summary"],
            "primary_gate_results": report["primary_gate_results"],
            "replication_gate_results": report["replication_gate_results"],
            "secondary_replication_budget_sweep": report[
                "secondary_replication_budget_sweep"
            ],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
