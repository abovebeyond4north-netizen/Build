from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
from pathlib import Path
from typing import Any

from bounty_preflight import preflight_task
from bountyforge import (
    Bounty,
    Config,
    build_bid_request_body,
    utcnow,
)


SCHEMA_VERSION = 1


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")


def _bounty_from_preflight(preflight: dict[str, Any]) -> Bounty:
    return Bounty(
        source="opentask",
        external_id=str(preflight.get("task_id") or ""),
        title=str(preflight.get("title") or ""),
        description=str(preflight.get("description_excerpt") or ""),
        reward_cents=int(preflight.get("reward_cents") or 0),
        currency=str(preflight.get("currency") or ""),
        task_url=str(preflight.get("task_url") or ""),
        execution_mode=str(preflight.get("execution_mode") or ""),
        match_score=int(preflight.get("match_score") or 0),
        updated_at=str(preflight.get("updated_at") or ""),
        raw={},
    )


def build_bid_packet_from_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    if not preflight.get("bid_ready"):
        return {
            "kind": "bountyforge.bidPacket",
            "schema_version": SCHEMA_VERSION,
            "generated_at": utcnow(),
            "packet_ready": False,
            "task_id": preflight.get("task_id"),
            "blocked_by": preflight.get("blocked_by") or "preflight_not_ready",
            "write_actions_performed": False,
        }

    approach = str(preflight.get("bid_approach") or "")
    if not approach:
        return {
            "kind": "bountyforge.bidPacket",
            "schema_version": SCHEMA_VERSION,
            "generated_at": utcnow(),
            "packet_ready": False,
            "task_id": preflight.get("task_id"),
            "blocked_by": "bid_approach_missing",
            "write_actions_performed": False,
        }

    bounty = _bounty_from_preflight(preflight)
    if not bounty.external_id or not bounty.updated_at:
        return {
            "kind": "bountyforge.bidPacket",
            "schema_version": SCHEMA_VERSION,
            "generated_at": utcnow(),
            "packet_ready": False,
            "task_id": bounty.external_id or None,
            "blocked_by": "task_identity_incomplete",
            "write_actions_performed": False,
        }

    request_body = build_bid_request_body(
        bounty,
        eta_days=1,
        approach=approach,
    )
    artifact = dict(preflight.get("artifact") or {})
    decision = dict(preflight.get("decision") or {})
    fulfillment = dict(preflight.get("fulfillment") or {})
    task_state = dict(preflight.get("task_state") or {})

    intent = {
        "task": {
            "id": bounty.external_id,
            "url": bounty.task_url,
            "title": bounty.title,
            "updated_at": bounty.updated_at,
            "execution_mode": bounty.execution_mode,
            "state": {
                "status": task_state.get("status"),
                "deadline_at": task_state.get("deadline_at"),
                "explicit_bid_disabled": bool(task_state.get("explicit_bid_disabled")),
            },
        },
        "request": {
            "method": "POST",
            "path": (
                "/api/agent/tasks/"
                + urllib.parse.quote(bounty.external_id, safe="")
                + "/bids"
            ),
            "body": request_body,
        },
        "fulfillment": {
            "route": fulfillment.get("route"),
            "kind": fulfillment.get("kind"),
            "artifact_filename": artifact.get("filename"),
            "artifact_sha256": artifact.get("sha256"),
            "artifact_size_bytes": artifact.get("size_bytes"),
        },
        "economics": {
            "reward_cents": bounty.reward_cents,
            "currency": bounty.currency,
            "expected_profit_cents": decision.get("expected_profit_cents"),
            "expected_hourly_cents": decision.get("expected_hourly_cents"),
            "estimated_minutes": decision.get("estimated_minutes"),
            "success_probability": decision.get("success_probability"),
        },
        "guards": {
            "requires_exact_task_updated_at": True,
            "requires_auth_readiness": True,
            "requires_explicit_write_executor": True,
            "write_action_enabled": False,
        },
    }
    intent_sha256 = hashlib.sha256(_canonical_bytes(intent)).hexdigest()

    return {
        "kind": "bountyforge.bidPacket",
        "schema_version": SCHEMA_VERSION,
        "generated_at": utcnow(),
        "packet_ready": True,
        "intent_sha256": intent_sha256,
        "intent": intent,
        "current_preflight_blocker": preflight.get("blocked_by"),
        "marketplace_auth_present": bool(preflight.get("marketplace_auth_present")),
        "write_actions_performed": False,
    }


def prepare_bid_packet(
    task_id: str,
    *,
    config: Config | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    preflight = preflight_task(
        task_id,
        config=config,
        client=client,
        artifact_dir=None,
    )
    return build_bid_packet_from_preflight(preflight)


def cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a hashable OpenTask bid packet from fresh read-only preflight data. "
            "This command never submits the bid."
        )
    )
    parser.add_argument("task_id", help="OpenTask task ID")
    parser.add_argument("--json-out", type=Path, help="optional packet output path")
    args = parser.parse_args()

    packet = prepare_bid_packet(args.task_id)
    rendered = json.dumps(packet, indent=2, sort_keys=True, default=str) + "\n"
    print(rendered, end="")
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered)

    return 0 if packet.get("packet_ready") else 3


if __name__ == "__main__":
    raise SystemExit(cli())
