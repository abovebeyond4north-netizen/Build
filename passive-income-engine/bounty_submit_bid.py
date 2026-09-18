from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from bounty_bid_packet import prepare_bid_packet
from bountyforge import (
    Bounty,
    Config,
    OpenTaskClient,
    authenticated_bid_readiness,
    build_bid_request_body,
    utcnow,
)


CONFIRM_PHRASE = "SUBMIT_BID"


def _safe_bid_summary(value: Any) -> dict[str, Any]:
    bid = dict(value or {})
    return {
        "id": str(bid.get("id") or "") or None,
        "status": str(bid.get("status") or "") or None,
        "task_id": str(bid.get("taskId") or bid.get("task_id") or "") or None,
        "created_at": bid.get("createdAt") or bid.get("created_at"),
        "updated_at": bid.get("updatedAt") or bid.get("updated_at"),
    }


def _safe_auth_summary(auth: dict[str, Any]) -> dict[str, Any]:
    return {
        "ready_for_bid": bool(auth.get("ready_for_bid")),
        "blocked_by": auth.get("blocked_by"),
        "profile_identity_present": bool((auth.get("profile") or {}).get("id")),
        "profile_read_verified": bool(auth.get("profile_read_verified")),
        "onboarding_read_verified": bool(auth.get("onboarding_read_verified")),
        "tasks_read_verified": bool(auth.get("tasks_read_verified")),
        "bids_read_verified": bool(auth.get("bids_read_verified")),
        "checkpoint": auth.get("checkpoint"),
        "required_scopes": auth.get("required_scopes") or [],
        "missing_declared_scopes": auth.get("missing_declared_scopes") or [],
        "write_scope_verification": auth.get("write_scope_verification"),
        "warnings": auth.get("warnings") or [],
    }


def _result_base(task_id: str, expected_intent_sha256: str) -> dict[str, Any]:
    return {
        "kind": "bountyforge.manualBidResult",
        "schema_version": 1,
        "generated_at": utcnow(),
        "task_id": task_id,
        "expected_intent_sha256": expected_intent_sha256,
        "write_attempted": False,
        "write_confirmed": False,
        "write_outcome_unknown": False,
        "reconciled_after_error": False,
        "blocked_by": None,
    }


def submit_manual_bid(
    task_id: str,
    *,
    expected_intent_sha256: str,
    confirm_phrase: str,
    config: Config | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    report = _result_base(task_id, expected_intent_sha256)

    if confirm_phrase != CONFIRM_PHRASE:
        report["blocked_by"] = "confirmation_required"
        return report
    if not expected_intent_sha256 or len(expected_intent_sha256) != 64:
        report["blocked_by"] = "intent_hash_invalid"
        return report

    cfg = config or Config.from_env()
    api = client or OpenTaskClient(cfg)

    auth = authenticated_bid_readiness(cfg, api)
    report["auth_readiness"] = _safe_auth_summary(auth)
    if not auth.get("ready_for_bid"):
        report["blocked_by"] = auth.get("blocked_by") or "auth_not_ready"
        return report

    try:
        existing = api.list_own_bids(task_id=task_id, limit=5)
    except Exception as exc:
        report["blocked_by"] = "existing_bid_check_failed"
        report["error"] = str(exc)[:500]
        return report
    if existing:
        report["blocked_by"] = "existing_bid"
        report["existing_bids"] = [_safe_bid_summary(item) for item in existing[:5]]
        return report

    try:
        packet = prepare_bid_packet(task_id, config=cfg, client=api)
    except Exception as exc:
        report["blocked_by"] = "fresh_packet_failed"
        report["error"] = str(exc)[:500]
        return report

    report["fresh_intent_sha256"] = packet.get("intent_sha256")
    report["packet_ready"] = bool(packet.get("packet_ready"))
    if not packet.get("packet_ready"):
        report["blocked_by"] = packet.get("blocked_by") or "packet_not_ready"
        return report
    if packet.get("intent_sha256") != expected_intent_sha256:
        report["blocked_by"] = "intent_hash_mismatch"
        return report
    if packet.get("current_preflight_blocker") != "explicit_bid_action":
        report["blocked_by"] = "preflight_write_boundary_unexpected"
        return report

    intent = dict(packet.get("intent") or {})
    task = dict(intent.get("task") or {})
    request = dict(intent.get("request") or {})
    body = dict(request.get("body") or {})
    economics = dict(intent.get("economics") or {})
    guards = dict(intent.get("guards") or {})

    if request.get("method") != "POST":
        report["blocked_by"] = "request_method_invalid"
        return report
    if guards.get("write_action_enabled") is not False:
        report["blocked_by"] = "dry_run_guard_invalid"
        return report
    if not guards.get("requires_exact_task_updated_at"):
        report["blocked_by"] = "freshness_guard_missing"
        return report
    if not guards.get("requires_auth_readiness"):
        report["blocked_by"] = "auth_guard_missing"
        return report

    bounty = Bounty(
        source="opentask",
        external_id=str(task.get("id") or ""),
        title=str(task.get("title") or ""),
        description="",
        reward_cents=int(economics.get("reward_cents") or 0),
        currency=str(economics.get("currency") or ""),
        task_url=str(task.get("url") or ""),
        execution_mode=str(task.get("execution_mode") or ""),
        match_score=0,
        updated_at=str(task.get("updated_at") or ""),
        raw={},
    )
    recomputed = build_bid_request_body(
        bounty,
        eta_days=int(body.get("etaDays") or 1),
        approach=str(body.get("approach") or ""),
    )
    if recomputed != body:
        report["blocked_by"] = "request_body_drift"
        return report

    report["write_attempted"] = True
    try:
        response = api.create_bid(
            bounty,
            eta_days=int(body["etaDays"]),
            approach=str(body["approach"]),
        )
    except Exception as exc:
        report["write_error"] = str(exc)[:500]
        try:
            recovered = api.list_own_bids(task_id=task_id, limit=5)
        except Exception as read_exc:
            report["blocked_by"] = "bid_write_outcome_unknown"
            report["write_outcome_unknown"] = True
            report["reconciliation_error"] = str(read_exc)[:500]
            return report

        if recovered:
            report["write_confirmed"] = True
            report["reconciled_after_error"] = True
            report["bid"] = _safe_bid_summary(recovered[0])
            return report

        report["blocked_by"] = "bid_write_outcome_unknown"
        report["write_outcome_unknown"] = True
        return report

    bid = dict((response or {}).get("bid") or {})
    if not bid.get("id"):
        report["blocked_by"] = "bid_response_missing_id"
        report["write_outcome_unknown"] = True
        return report

    report["write_confirmed"] = True
    report["bid"] = _safe_bid_summary(bid)
    return report


def cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly submit one fresh, hash-pinned OpenTask bid. "
            "This is a marketplace write and requires an exact confirmation phrase."
        )
    )
    parser.add_argument("task_id", help="OpenTask task ID")
    parser.add_argument(
        "--intent-sha256",
        required=True,
        help="exact intent SHA-256 from the latest BountyForge public bid packet",
    )
    parser.add_argument(
        "--confirm",
        required=True,
        help=f"must equal {CONFIRM_PHRASE}",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="optional sanitized result output path",
    )
    args = parser.parse_args()

    result = submit_manual_bid(
        args.task_id,
        expected_intent_sha256=args.intent_sha256,
        confirm_phrase=args.confirm,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True, default=str) + "\n"
    print(rendered, end="")
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered)

    if result.get("write_confirmed"):
        return 0
    if result.get("write_outcome_unknown"):
        return 4
    return 3


if __name__ == "__main__":
    raise SystemExit(cli())
