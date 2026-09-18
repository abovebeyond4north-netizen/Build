from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bounty_solver import HANDLERS, MAX_OUTPUT_BYTES
from bountyforge import (
    BountyForge,
    Config,
    autonomous_fulfillment_route,
    build_bid_approach,
    decide,
    normalize_opentask,
    public_task_match_score,
    safe_solver_payload,
)


SAFE_ARTIFACT_KINDS = {"csv_to_json_cli_package"}


def _preflight_config(config: Config | None = None) -> Config:
    source = config or Config.from_env()
    database_path = source.database_path
    if config is None and not os.getenv("DATABASE_PATH"):
        database_path = "/tmp/bountyforge-preflight.db"
    return replace(
        source,
        database_path=database_path,
        auto_bid=False,
        auto_submit_entries=False,
        auto_deliver=False,
        reconcile_payments=False,
    )


CLOSED_TASK_STATUSES = {
    "accepted",
    "awarded",
    "cancelled",
    "canceled",
    "closed",
    "completed",
    "draft",
    "expired",
    "filled",
    "paused",
}


def _parse_iso_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _available_action_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, dict):
        for key, enabled in value.items():
            if bool(enabled):
                names.append(str(key))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("action") or item.get("id")
                if name:
                    names.append(str(name))
    return sorted(set(names))


def task_state_evidence(task: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    status = str(task.get("status") or "").strip().lower()
    actions_raw = task.get("availableActions")
    actions = _available_action_names(actions_raw)

    deadline_key = None
    deadline = None
    for key in ("deadlineAt", "expiresAt", "closedAt", "paymentDueAt"):
        parsed = _parse_iso_datetime(task.get(key))
        if parsed is not None:
            deadline_key = key
            deadline = parsed
            break

    updated = _parse_iso_datetime(task.get("updatedAt") or task.get("createdAt"))
    age_days = None if updated is None else max(0, int((current - updated).total_seconds() // 86400))

    explicit_bid_disabled = False
    if isinstance(actions_raw, dict):
        for key in ("canBid", "bid", "createBid", "sendOffer", "submitOffer"):
            if key in actions_raw and actions_raw.get(key) is False:
                explicit_bid_disabled = True
                break

    blocker = None
    if status in CLOSED_TASK_STATUSES:
        blocker = "task_not_open"
    elif deadline is not None and deadline_key in {"deadlineAt", "expiresAt"} and deadline <= current:
        blocker = "task_deadline_passed"
    elif explicit_bid_disabled:
        blocker = "task_not_biddable"

    return {
        "status": status or None,
        "available_actions": actions,
        "deadline_field": deadline_key,
        "deadline_at": None if deadline is None else deadline.isoformat(),
        "updated_age_days": age_days,
        "explicit_bid_disabled": explicit_bid_disabled,
        "state_blocker": blocker,
    }


def _artifact_evidence(
    *,
    title: str,
    description: str,
    route: dict[str, str] | None,
    artifact_dir: Path | None,
) -> dict[str, Any] | None:
    if route is None or route.get("route") != "solver":
        return None

    payload = safe_solver_payload(title, description)
    if payload is None:
        return None
    kind = str(payload.get("kind") or "")
    handler = HANDLERS.get(kind)
    if handler is None:
        return {
            "verified": False,
            "kind": kind,
            "error": "solver handler unavailable",
        }

    result = handler(payload)
    output = result.output or b""
    if not result.ok:
        return {
            "verified": False,
            "kind": kind,
            "error": result.error or "solver handler did not succeed",
        }
    if len(output) > MAX_OUTPUT_BYTES:
        return {
            "verified": False,
            "kind": kind,
            "error": "preflight artifact exceeds solver output limit",
        }

    evidence: dict[str, Any] = {
        "verified": True,
        "kind": kind,
        "filename": result.filename,
        "content_type": result.content_type,
        "size_bytes": len(output),
        "sha256": hashlib.sha256(output).hexdigest(),
        "verification": result.verification,
        "artifact_written": False,
    }

    if artifact_dir is not None:
        if kind not in SAFE_ARTIFACT_KINDS:
            evidence["artifact_write_blocked"] = "task-input-derived artifacts are not exported by automatic preflight"
        elif output and result.filename:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            target = artifact_dir / result.filename
            target.write_bytes(output)
            evidence["artifact_written"] = True
            evidence["artifact_path"] = str(target)

    return evidence


def preflight_task(
    task_id: str,
    *,
    config: Config | None = None,
    client: Any | None = None,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    cfg = _preflight_config(config)
    forge = BountyForge(cfg)
    if client is not None:
        forge.opentask = client

    detail = forge.opentask.public_task_detail(task_id)
    task = dict((detail or {}).get("task") or detail or {})
    if not task:
        return {
            "task_id": task_id,
            "bid_ready": False,
            "blocked_by": "task_unavailable",
        }

    score = public_task_match_score(task)
    rec = {"task": task, "score": score, "source": "public-preflight"}
    bounty = normalize_opentask(rec, {"task": task})
    if bounty is None:
        return {
            "task_id": task_id,
            "bid_ready": False,
            "blocked_by": "task_terms_unusable",
            "match_score": score,
        }

    decision = decide(bounty, forge.store, cfg)
    state = task_state_evidence(task)
    route = autonomous_fulfillment_route(bounty.title, bounty.description)
    approach = (
        build_bid_approach(bounty, decision)
        if decision.eligible and not state["state_blocker"]
        else None
    )
    artifact = (
        _artifact_evidence(
            title=bounty.title,
            description=bounty.description,
            route=route,
            artifact_dir=artifact_dir,
        )
        if not state["state_blocker"]
        else None
    )

    artifact_verified = (
        route is not None
        and (
            route.get("route") != "solver"
            or (artifact is not None and bool(artifact.get("verified")))
        )
    )
    bid_ready = bool(
        decision.eligible
        and not state["state_blocker"]
        and bounty.execution_mode == "pitch"
        and route is not None
        and approach
        and artifact_verified
    )

    if state["state_blocker"]:
        blocked_by = str(state["state_blocker"])
    elif not decision.eligible:
        blocked_by = decision.reason
    elif bounty.execution_mode != "pitch":
        blocked_by = "execution_mode_not_pitch"
    elif route is None:
        blocked_by = "no_autonomous_fulfillment_route"
    elif not artifact_verified:
        blocked_by = "artifact_preflight_failed"
    elif not cfg.opentask_token:
        blocked_by = "marketplace_auth"
    else:
        # Preflight is intentionally read-only even when credentials are present.
        blocked_by = "explicit_bid_action"

    return {
        "task_id": bounty.external_id,
        "task_url": bounty.task_url,
        "title": bounty.title,
        "updated_at": bounty.updated_at,
        "task_state": state,
        "execution_mode": bounty.execution_mode,
        "reward_cents": bounty.reward_cents,
        "currency": bounty.currency,
        "match_score": bounty.match_score,
        "description_excerpt": bounty.description[:800],
        "decision": asdict(decision),
        "fulfillment": route,
        "artifact": artifact,
        "bid_approach": approach,
        "marketplace_auth_present": bool(cfg.opentask_token),
        "bid_ready": bid_ready,
        "blocked_by": blocked_by,
        "write_actions_performed": False,
    }


def cli() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only BountyForge task preflight using fresh public marketplace data."
    )
    parser.add_argument("task_id", help="OpenTask task ID")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help="optionally write only preflight-safe static artifacts such as the CSV-to-JSON package",
    )
    args = parser.parse_args()

    result = preflight_task(args.task_id, artifact_dir=args.artifact_dir)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("bid_ready") else 3


if __name__ == "__main__":
    raise SystemExit(cli())
