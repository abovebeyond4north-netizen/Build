from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

import authority


REMOTE_PROTOCOL_VERSION = 2
TITLE_PREFIX = "[DGM-VERIFY] "
NONCE_HEX_LENGTH = 64


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_nonce(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != NONCE_HEX_LENGTH
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(
            "request_nonce must be a 64-character lowercase hex value"
        )
    return value


def require_issue_event(
    event: object,
) -> tuple[int, str, dict[str, Any]]:
    if not isinstance(event, dict):
        raise ValueError("GitHub event must be a JSON object")
    if event.get("action") != "opened":
        raise ValueError("remote verification only accepts newly opened issues")
    issue = event.get("issue")
    if not isinstance(issue, dict):
        raise ValueError("GitHub event has no issue object")
    number = issue.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise ValueError("issue number must be a positive integer")
    title = issue.get("title")
    if not isinstance(title, str) or not title.startswith(TITLE_PREFIX):
        raise ValueError("issue title must use the DGM verification prefix")
    body = issue.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("verification issue body must contain JSON")
    try:
        request = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "verification issue body must be exactly one JSON object"
        ) from exc
    if not isinstance(request, dict):
        raise ValueError("verification request must be a JSON object")
    return number, title, request


def request_context(event: dict[str, Any]) -> dict[str, Any]:
    issue = event["issue"]
    user = issue.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return {
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF", ""),
        "workflow_sha": os.environ.get("GITHUB_SHA", ""),
        "source_ref": os.environ.get("GITHUB_REF", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        "request_issue_author": login,
    }


def evaluation_key(request: dict[str, Any]) -> str:
    material = dict(request)
    material.pop("request_nonce", None)
    payload = {
        "remote_protocol_version": REMOTE_PROTOCOL_VERSION,
        "request": material,
    }
    return sha256_bytes(canonical_json(payload))


def expected_issue_title(request: dict[str, Any]) -> str:
    return TITLE_PREFIX + evaluation_key(request)


def build_preflight(event: dict[str, Any]) -> dict[str, Any]:
    issue_number, title, request = require_issue_event(event)
    nonce = require_nonce(request.get("request_nonce"))
    authority.validate_request(request)
    key = evaluation_key(request)
    expected = TITLE_PREFIX + key
    if title != expected:
        raise ValueError(
            "verification issue title does not match deterministic evaluation key"
        )
    return {
        "schema_version": 1,
        "remote_protocol_version": REMOTE_PROTOCOL_VERSION,
        "issue_number": issue_number,
        "evaluation_key": key,
        "expected_title": expected,
        "request_nonce": nonce,
        "request_digest": sha256_bytes(canonical_json(request)),
    }


def flatten_issue_pages(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("issue listing must be a JSON list")
    if value and all(isinstance(item, list) for item in value):
        items = [
            issue
            for page in value
            for issue in page
            if isinstance(issue, dict)
        ]
    else:
        items = [item for item in value if isinstance(item, dict)]
    return items


def verify_first_issue_claim(
    preflight: dict[str, Any],
    issue_pages: object,
) -> dict[str, Any]:
    expected_title = preflight.get("expected_title")
    current = preflight.get("issue_number")
    if not isinstance(expected_title, str) or not expected_title:
        raise ValueError("preflight expected_title is invalid")
    if isinstance(current, bool) or not isinstance(current, int) or current <= 0:
        raise ValueError("preflight issue_number is invalid")

    matches: list[int] = []
    for issue in flatten_issue_pages(issue_pages):
        if "pull_request" in issue:
            continue
        if issue.get("title") != expected_title:
            continue
        number = issue.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            continue
        matches.append(number)

    if not matches:
        raise ValueError("current verification issue is missing from issue history")
    first = min(matches)
    if first != current:
        raise ValueError(
            f"hidden evidence already claimed by earlier issue {first}"
        )
    return {
        "claimed": True,
        "first_issue_number": first,
        "matching_issue_numbers": sorted(matches),
        "evaluation_key": preflight.get("evaluation_key"),
    }


def evaluate_remote(
    *,
    issue_number: int,
    request: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    nonce = require_nonce(request.get("request_nonce"))
    key = evaluation_key(request)
    (
        capability,
        entrypoint,
        baseline_source,
        finalist_source,
        required_score,
        minimum_gain,
    ) = authority.validate_request(request)

    request_digest = sha256_bytes(canonical_json(request))
    seed = secrets.randbits(63)
    cases = authority.hidden_cases(capability, seed)
    pairs = authority.metamorphic_pairs(capability, seed)
    pair_cases = [item for pair in pairs for item in pair]

    containment_passed, containment_failures = (
        authority.containment_self_test()
    )

    baseline_outputs, baseline_errors = authority.evaluate_outputs(
        baseline_source,
        entrypoint,
        cases,
    )
    finalist_outputs, finalist_errors = authority.evaluate_outputs(
        finalist_source,
        entrypoint,
        cases,
    )
    baseline_meta_outputs, baseline_meta_errors = authority.evaluate_outputs(
        baseline_source,
        entrypoint,
        pair_cases,
    )
    finalist_meta_outputs, finalist_meta_errors = authority.evaluate_outputs(
        finalist_source,
        entrypoint,
        pair_cases,
    )

    baseline_score = authority.score_outputs(baseline_outputs, cases)
    finalist_score = authority.score_outputs(finalist_outputs, cases)
    baseline_meta = authority.metamorphic_score(
        baseline_meta_outputs,
        pairs,
    )
    finalist_meta = authority.metamorphic_score(
        finalist_meta_outputs,
        pairs,
    )
    delta = finalist_score - baseline_score

    baseline_outputs_2, _ = authority.evaluate_outputs(
        baseline_source,
        entrypoint,
        cases,
    )
    finalist_outputs_2, _ = authority.evaluate_outputs(
        finalist_source,
        entrypoint,
        cases,
    )
    baseline_meta_outputs_2, _ = authority.evaluate_outputs(
        baseline_source,
        entrypoint,
        pair_cases,
    )
    finalist_meta_outputs_2, _ = authority.evaluate_outputs(
        finalist_source,
        entrypoint,
        pair_cases,
    )
    deterministic_replay = (
        baseline_outputs_2 == baseline_outputs
        and finalist_outputs_2 == finalist_outputs
        and baseline_meta_outputs_2 == baseline_meta_outputs
        and finalist_meta_outputs_2 == finalist_meta_outputs
    )

    baseline_digest = authority.source_digest(baseline_source)
    finalist_digest = authority.source_digest(finalist_source)

    if not containment_passed:
        passed = False
        reason = "containment_probe_failed"
    elif not deterministic_replay:
        passed = False
        reason = "nondeterministic_replay"
    elif finalist_digest == baseline_digest:
        passed = False
        reason = "identical_to_baseline"
    elif finalist_score + 1e-12 < required_score:
        passed = False
        reason = "hidden_suite_below_required_score"
    elif finalist_meta + 1e-12 < required_score:
        passed = False
        reason = "metamorphic_suite_below_required_score"
    elif delta + 1e-12 < minimum_gain:
        passed = False
        reason = "hidden_suite_insufficient_gain"
    else:
        passed = True
        reason = "passed"

    receipt = {
        "schema_version": 1,
        "remote_protocol_version": REMOTE_PROTOCOL_VERSION,
        "authority_protocol_version": authority.PROTOCOL_VERSION,
        "authority_version": authority.AUTHORITY_VERSION,
        "authority_digest": authority.authority_digest(),
        "manifest_digest": authority.manifest_digest(),
        "evaluation_key": key,
        "request_digest": request_digest,
        "request_nonce": nonce,
        "issue_number": issue_number,
        "capability": capability,
        "baseline_digest": baseline_digest,
        "finalist_digest": finalist_digest,
        "suite_digest": authority.suite_digest(cases, pairs),
        "hidden_case_count": len(cases),
        "metamorphic_pair_count": len(pairs),
        "containment_passed": containment_passed,
        "deterministic_replay": deterministic_replay,
        "baseline_score": baseline_score,
        "finalist_score": finalist_score,
        "baseline_metamorphic_score": baseline_meta,
        "finalist_metamorphic_score": finalist_meta,
        "delta": delta,
        "required_score": required_score,
        "minimum_gain": minimum_gain,
        "passed": passed,
        "reason": reason,
        "error_counts": {
            "baseline": len(baseline_errors) + len(baseline_meta_errors),
            "finalist": len(finalist_errors) + len(finalist_meta_errors),
        },
        "context": context,
        "created_at": time.time(),
        "containment_failure_count": len(containment_failures),
    }

    serialized = canonical_json(receipt)
    if str(seed).encode("ascii") in serialized:
        raise RuntimeError("private verifier seed leaked into public receipt")
    return receipt


def write_outputs(
    receipt: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / "receipt.json"
    receipt_bytes = (
        json.dumps(
            receipt,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    receipt_path.write_bytes(receipt_bytes)
    receipt_digest = sha256_bytes(receipt_bytes)
    receipt_b64 = base64.b64encode(receipt_bytes).decode("ascii")

    status = "PASS" if receipt.get("passed") is True else "FAIL"
    comment_body = "\n".join(
        [
            "<!-- dgm-remote-verifier-result:v2 -->",
            f"Remote verifier result: **{status}**",
            f"Receipt SHA-256: {receipt_digest}",
            f"Evaluation key: {receipt['evaluation_key']}",
            f"Request nonce: {receipt['request_nonce']}",
            f"Workflow run: {receipt['context'].get('run_id', '')}",
            "",
            "<details><summary>Attested receipt payload (base64)</summary>",
            "",
            receipt_b64,
            "",
            "</details>",
            "",
            "The receipt file is attested by the GitHub-hosted verifier workflow.",
        ]
    )
    comment_path = output_dir / "comment.json"
    comment_path.write_text(
        json.dumps({"body": comment_body}, ensure_ascii=False),
        encoding="utf-8",
    )
    return receipt_path, comment_path


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def command_preflight(event_path: Path, output_path: Path) -> int:
    event = load_json(event_path)
    result = build_preflight(event)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(json.dumps(result, sort_keys=True))
    return 0


def command_claim(preflight_path: Path, issues_path: Path) -> int:
    result = verify_first_issue_claim(
        load_json(preflight_path),
        load_json(issues_path),
    )
    sys.stdout.write(json.dumps(result, sort_keys=True))
    return 0


def command_evaluate(event_path: Path, output_dir: Path) -> int:
    event = load_json(event_path)
    issue_number, title, request = require_issue_event(event)
    expected = expected_issue_title(request)
    if title != expected:
        raise ValueError(
            "verification issue title does not match deterministic evaluation key"
        )
    receipt = evaluate_remote(
        issue_number=issue_number,
        request=request,
        context=request_context(event),
    )
    receipt_path, comment_path = write_outputs(receipt, output_dir)
    sys.stdout.write(
        json.dumps(
            {
                "issue_number": issue_number,
                "receipt_path": str(receipt_path),
                "comment_path": str(comment_path),
                "passed": bool(receipt["passed"]),
                "receipt_sha256": sha256_bytes(receipt_path.read_bytes()),
                "evaluation_key": receipt["evaluation_key"],
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) == 3 and args[0] == "preflight":
            return command_preflight(Path(args[1]), Path(args[2]))
        if len(args) == 3 and args[0] == "claim":
            return command_claim(Path(args[1]), Path(args[2]))
        if len(args) == 3 and args[0] == "evaluate":
            return command_evaluate(Path(args[1]), Path(args[2]))
        raise SystemExit(
            "usage: remote_issue_request.py "
            "preflight EVENT_JSON OUTPUT_JSON | "
            "claim PREFLIGHT_JSON ISSUES_JSON | "
            "evaluate EVENT_JSON OUTPUT_DIR"
        )
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
