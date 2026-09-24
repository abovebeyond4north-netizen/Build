from __future__ import annotations

import json

from adi_genesis13.experiment import write_json
from .experiment import run_block


PILOT_SEEDS = (61, 193, 487, 809, 1231, 1777)


if __name__ == "__main__":
    report = {
        "experiment": "ADI Genesis-16 development pilot",
        "seeds": list(PILOT_SEEDS),
        "result": run_block(PILOT_SEEDS),
    }
    write_json("genesis16_pilot.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
