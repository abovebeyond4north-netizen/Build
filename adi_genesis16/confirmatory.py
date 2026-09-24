from __future__ import annotations

import argparse
import json
import math

from adi_genesis13.experiment import write_json
from .experiment import run_block


PRIMARY_SEEDS = tuple(range(30000, 30020))
REPLICATION_SEEDS = tuple(range(34000, 34020))

GATES = {
    "multistep_improvement_vs_linear": 0.12,
    "planning_improvement_vs_linear": 0.75,
    "planning_candidate_regret_max": 0.002,
    "coverage_90_min": 0.84,
    "coverage_90_max": 0.96,
    "interval_width_90_max": 0.18,
    "nll_gain_vs_no_epistemic": 0.08,
    "abrupt_detection_rate": 0.90,
    "gradual_detection_rate": 0.80,
    "false_positive_rate_max": 0.10,
    "abrupt_detection_delay_max": 8.0,
    "gradual_detection_delay_max": 18.0,
    "prediction_planning_compute_ratio_max": 4.0,
}


def gates(summary: dict[str, float]) -> dict[str, bool]:
    finite = all(math.isfinite(float(value)) for value in summary.values())
    return {
        "finite": finite,
        "multistep_vs_linear": (
            summary["multistep_improvement_vs_linear"]
            >= GATES["multistep_improvement_vs_linear"]
        ),
        "planning_vs_linear": (
            summary["planning_improvement_vs_linear"]
            >= GATES["planning_improvement_vs_linear"]
        ),
        "planning_regret": (
            summary["planning_candidate_regret"]
            <= GATES["planning_candidate_regret_max"]
        ),
        "coverage_90": (
            GATES["coverage_90_min"]
            <= summary["coverage_90"]
            <= GATES["coverage_90_max"]
        ),
        "interval_width_90": (
            summary["interval_width_90"]
            <= GATES["interval_width_90_max"]
        ),
        "epistemic_nll_gain": (
            summary["nll_gain_vs_no_epistemic"]
            >= GATES["nll_gain_vs_no_epistemic"]
        ),
        "abrupt_detection": (
            summary["abrupt_detection_rate"]
            >= GATES["abrupt_detection_rate"]
        ),
        "gradual_detection": (
            summary["gradual_detection_rate"]
            >= GATES["gradual_detection_rate"]
        ),
        "false_positive": (
            summary["false_positive_rate"]
            <= GATES["false_positive_rate_max"]
        ),
        "abrupt_delay": (
            summary["abrupt_detection_delay"]
            <= GATES["abrupt_detection_delay_max"]
        ),
        "gradual_delay": (
            summary["gradual_detection_delay"]
            <= GATES["gradual_detection_delay_max"]
        ),
        "compute_ratio": (
            summary["compute_ratio"]
            <= GATES["prediction_planning_compute_ratio_max"]
        ),
    }


def run_confirmatory() -> dict:
    primary = run_block(PRIMARY_SEEDS)
    replication = run_block(REPLICATION_SEEDS)
    primary_gates = gates(primary["summary"])
    replication_gates = gates(replication["summary"])
    passed = all(primary_gates.values()) and all(replication_gates.values())
    return {
        "experiment": "ADI Genesis-16",
        "claim": "nonlinear stochastic dynamics plus epistemic uncertainty",
        "primary_seed_range": [PRIMARY_SEEDS[0], PRIMARY_SEEDS[-1]],
        "replication_seed_range": [
            REPLICATION_SEEDS[0],
            REPLICATION_SEEDS[-1],
        ],
        "gates": GATES,
        "primary": primary,
        "replication": replication,
        "primary_gates": primary_gates,
        "replication_gates": replication_gates,
        "status": "PASS" if passed else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="genesis16_confirmatory.json",
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
                "primary_gates": report["primary_gates"],
                "replication_gates": report["replication_gates"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
