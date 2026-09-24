from __future__ import annotations

import json

from adi_genesis13.experiment import write_json

from .experiment import (
    evaluate_adaptation_budget,
    evaluate_seed,
    summarize,
)


PILOT_SEEDS = (42, 314, 777, 991, 1337, 2025)


def run_pilot() -> dict:
    rows = [evaluate_seed(seed) for seed in PILOT_SEEDS]
    sweep = {}
    for budget in (4, 8, 12, 20):
        values = [
            evaluate_adaptation_budget(seed, adaptation_steps=budget)
            for seed in PILOT_SEEDS
        ]
        sweep[str(budget)] = {
            key: sum(row[key] for row in values) / len(values)
            for key in values[0]
        }
    return {
        "experiment": "ADI Genesis-15 pilot",
        "seeds": list(PILOT_SEEDS),
        "summary": summarize(rows),
        "adaptation_budget_sweep": sweep,
    }


if __name__ == "__main__":
    report = run_pilot()
    write_json("genesis15_pilot.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
