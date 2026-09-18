from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


QUEUE_DIR = Path(os.getenv("BOUNTYFORGE_QUEUE_DIR", "/bounty-queue"))
POLL_SECONDS = max(1, int(os.getenv("BOUNTYFORGE_SOLVER_POLL_SECONDS", "5")))
MAX_INPUT_BYTES = max(1024, int(os.getenv("BOUNTYFORGE_SOLVER_MAX_INPUT_BYTES", "262144")))
MAX_OUTPUT_BYTES = max(1024, int(os.getenv("BOUNTYFORGE_SOLVER_MAX_OUTPUT_BYTES", "524288")))
QUEUE_SECRET = os.getenv("BOUNTYFORGE_QUEUE_SECRET", "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", value):
        raise ValueError("invalid job id")
    return value


@dataclass(frozen=True)
class SolveResult:
    ok: bool
    handler: str
    filename: str | None
    content_type: str | None
    output: bytes | None
    verification: dict[str, Any]
    error: str | None = None


def _json_input(payload: dict[str, Any]) -> Any:
    raw = payload.get("input_text")
    if not isinstance(raw, str):
        raise ValueError("input_text must be text")
    if len(raw.encode()) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds configured limit")
    return json.loads(raw)


def solve_json_format(payload: dict[str, Any]) -> SolveResult:
    value = _json_input(payload)
    compact = bool(payload.get("compact", False))
    text = (
        json.dumps(value, separators=(",", ":"), sort_keys=True)
        if compact
        else json.dumps(value, indent=2, sort_keys=True)
    ) + "\n"
    output = text.encode()
    reparsed = json.loads(text)
    return SolveResult(
        True,
        "json_format",
        "result.json",
        "application/json",
        output,
        {
            "json_parse": True,
            "round_trip_equal": reparsed == value,
            "sha256": sha256_bytes(output),
        },
    )


def solve_csv_to_json(payload: dict[str, Any]) -> SolveResult:
    raw = payload.get("input_text")
    if not isinstance(raw, str):
        raise ValueError("input_text must be text")
    if len(raw.encode()) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds configured limit")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ValueError("CSV header is required")
    rows = list(reader)
    text = json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
    output = text.encode()
    check = json.loads(text)
    return SolveResult(
        True,
        "csv_to_json",
        "result.json",
        "application/json",
        output,
        {
            "row_count": len(rows),
            "columns": reader.fieldnames,
            "json_parse": isinstance(check, list),
            "sha256": sha256_bytes(output),
        },
    )


def solve_json_to_csv(payload: dict[str, Any]) -> SolveResult:
    value = _json_input(payload)
    if not isinstance(value, list) or not value:
        raise ValueError("JSON input must be a non-empty array of objects")
    if not all(isinstance(row, dict) for row in value):
        raise ValueError("every JSON array item must be an object")

    requested = payload.get("columns")
    if requested is not None:
        if not isinstance(requested, list) or not all(isinstance(x, str) and x for x in requested):
            raise ValueError("columns must be a list of non-empty strings")
        columns = requested
    else:
        columns = []
        seen: set[str] = set()
        for row in value:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    columns.append(str(key))

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value:
        normalized = {}
        for col in columns:
            cell = row.get(col, "")
            if isinstance(cell, (dict, list)):
                cell = json.dumps(cell, separators=(",", ":"), sort_keys=True)
            normalized[col] = cell
        writer.writerow(normalized)
    output = buf.getvalue().encode()
    parsed_rows = list(csv.DictReader(io.StringIO(output.decode())))
    return SolveResult(
        True,
        "json_to_csv",
        "result.csv",
        "text/csv",
        output,
        {
            "row_count": len(parsed_rows),
            "columns": columns,
            "csv_parse": len(parsed_rows) == len(value),
            "sha256": sha256_bytes(output),
        },
    )


def solve_sha256(payload: dict[str, Any]) -> SolveResult:
    raw = payload.get("input_text")
    if not isinstance(raw, str):
        raise ValueError("input_text must be text")
    data = raw.encode()
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds configured limit")
    digest = sha256_bytes(data)
    output = (digest + "\n").encode()
    return SolveResult(
        True,
        "sha256",
        "sha256.txt",
        "text/plain",
        output,
        {"sha256_of_input": digest, "format_valid": bool(re.fullmatch(r"[0-9a-f]{64}", digest))},
    )


HANDLERS = {
    "json_format": solve_json_format,
    "csv_to_json": solve_csv_to_json,
    "json_to_csv": solve_json_to_csv,
    "sha256": solve_sha256,
}


def verify_package_signature(package: dict[str, Any]) -> None:
    if not QUEUE_SECRET:
        raise ValueError("solver queue secret is not configured")
    supplied = str(package.get("signature") or "")
    unsigned = {key: value for key, value in package.items() if key != "signature"}
    body = json.dumps(unsigned, separators=(",", ":"), sort_keys=True).encode()
    expected = hmac.new(QUEUE_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ValueError("invalid work-package signature")


def solve_package(package: dict[str, Any]) -> SolveResult:
    verify_package_signature(package)
    if package.get("version") != 1:
        raise ValueError("unsupported work-package version")
    payload = package.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload is required")
    kind = str(payload.get("kind") or "")
    handler = HANDLERS.get(kind)
    if handler is None:
        raise ValueError(f"unsupported safe solver kind: {kind}")
    result = handler(payload)
    if result.output is not None and len(result.output) > MAX_OUTPUT_BYTES:
        raise ValueError("output exceeds configured limit")
    return result


def process_file(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("work package exceeds configured limit")
    package = json.loads(path.read_text())
    job_id = safe_job_id(str(package.get("job_id") or path.stem))
    result = solve_package(package)

    artifact_path = None
    if result.ok and result.output is not None and result.filename:
        artifact_path = QUEUE_DIR / "artifacts" / job_id / result.filename
        atomic_write(artifact_path, result.output)

    manifest = {
        "version": 1,
        "job_id": job_id,
        "task_id": package.get("task_id"),
        "source": package.get("source"),
        "ok": result.ok,
        "handler": result.handler,
        "artifact": None
        if artifact_path is None
        else {
            "relative_path": str(artifact_path.relative_to(QUEUE_DIR)),
            "filename": result.filename,
            "content_type": result.content_type,
            "size_bytes": artifact_path.stat().st_size,
            "sha256": sha256_bytes(artifact_path.read_bytes()),
        },
        "verification": result.verification,
        "error": result.error,
    }
    unsigned = dict(manifest)
    body = json.dumps(unsigned, separators=(",", ":"), sort_keys=True).encode()
    manifest["signature"] = hmac.new(QUEUE_SECRET.encode(), body, hashlib.sha256).hexdigest()
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    atomic_write(QUEUE_DIR / "outbox" / f"{job_id}.json", encoded)
    path.replace(QUEUE_DIR / "processed" / path.name)
    return manifest


def run_once() -> list[dict[str, Any]]:
    for folder in ("inbox", "outbox", "processed", "failed", "artifacts"):
        (QUEUE_DIR / folder).mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for path in sorted((QUEUE_DIR / "inbox").glob("*.json")):
        try:
            results.append(process_file(path))
        except Exception as exc:
            failure = {
                "version": 1,
                "job_id": path.stem,
                "ok": False,
                "error": str(exc)[:1000],
            }
            if QUEUE_SECRET:
                body = json.dumps(failure, separators=(",", ":"), sort_keys=True).encode()
                failure["signature"] = hmac.new(QUEUE_SECRET.encode(), body, hashlib.sha256).hexdigest()
            atomic_write(
                QUEUE_DIR / "outbox" / f"{path.stem}.json",
                (json.dumps(failure, indent=2, sort_keys=True) + "\n").encode(),
            )
            path.replace(QUEUE_DIR / "failed" / path.name)
            results.append(failure)
    return results


def worker() -> None:
    while True:
        for result in run_once():
            print(json.dumps(result, sort_keys=True), flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    worker()
