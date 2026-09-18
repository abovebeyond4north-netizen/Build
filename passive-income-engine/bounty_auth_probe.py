from __future__ import annotations

import argparse
import json
from pathlib import Path

from bountyforge import BountyForge, Config, authenticated_bid_readiness


def probe(config: Config | None = None) -> dict:
    cfg = config or Config.from_env()
    forge = BountyForge(cfg)
    result = authenticated_bid_readiness(cfg, forge.opentask)
    result["write_actions_performed"] = False
    result["token_value_returned"] = False
    return result


def cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only OpenTask credential readiness probe. "
            "It never prints or persists OPENTASK_TOKEN."
        )
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="optional path for the non-secret readiness report",
    )
    args = parser.parse_args()

    result = probe()
    rendered = json.dumps(result, indent=2, sort_keys=True, default=str) + "\n"
    print(rendered, end="")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered)

    return 0 if result.get("ready_for_bid") else 3


if __name__ == "__main__":
    raise SystemExit(cli())
