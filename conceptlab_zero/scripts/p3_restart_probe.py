from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from p3 import run_p3_restart_probe


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: p3_restart_probe.py <program-store>")
    result = run_p3_restart_probe(Path(sys.argv[1]).resolve())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
