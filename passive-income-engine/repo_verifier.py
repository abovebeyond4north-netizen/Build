from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import resource
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(os.getenv("BOUNTYFORGE_REPO_VERIFY_DIR", "/repo-verify"))
SECRET = os.getenv("BOUNTYFORGE_REPO_VERIFY_SECRET", "")
TIMEOUT_SECONDS = max(5, int(os.getenv("BOUNTYFORGE_REPO_VERIFY_TIMEOUT_SECONDS", "120")))
MAX_OUTPUT_BYTES = max(4096, int(os.getenv("BOUNTYFORGE_REPO_VERIFY_MAX_OUTPUT_BYTES", "131072")))
MAX_FILES = max(10, int(os.getenv("BOUNTYFORGE_REPO_VERIFY_MAX_FILES", "5000")))
MAX_TREE_BYTES = max(1024 * 1024, int(os.getenv("BOUNTYFORGE_REPO_VERIFY_MAX_TREE_BYTES", str(50 * 1024 * 1024))))

ALLOWED_COMMANDS: dict[str, list[str]] = {
    "python_unittest": ["python", "-m", "unittest", "discover", "-v"],
    "python_compileall": ["python", "-m", "compileall", "-q", "."],
    "pytest": ["python", "-m", "pytest", "-q"],
}


def canonical_body(payload: dict[str, Any]) -> bytes:
    unsigned = {k: v for k, v in payload.items() if k != "signature"}
    return json.dumps(unsigned, separators=(",", ":"), sort_keys=True).encode()


def verify_signature(payload: dict[str, Any]) -> None:
    if not SECRET:
        raise ValueError("repository verifier secret is not configured")
    supplied = str(payload.get("signature") or "")
    expected = hmac.new(SECRET.encode(), canonical_body(payload), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ValueError("invalid repository verification signature")


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", value):
        raise ValueError("invalid verifier job id")
    return value


def inspect_tree(root: Path) -> dict[str, int]:
    files = 0
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinks are not allowed in staged repository trees")
        if path.is_file():
            files += 1
            total += path.stat().st_size
            if files > MAX_FILES:
                raise ValueError("repository exceeds file-count limit")
            if total > MAX_TREE_BYTES:
                raise ValueError("repository exceeds byte-size limit")
    return {"files": files, "bytes": total}


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SECONDS, TIMEOUT_SECONDS + 1))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    max_file = 16 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (max_file, max_file))


def run_check(worktree: Path, check: str) -> dict[str, Any]:
    argv = ALLOWED_COMMANDS.get(check)
    if argv is None:
        raise ValueError(f"unsupported repository check: {check}")
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=worktree,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=TIMEOUT_SECONDS,
        check=False,
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": "/tmp",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        },
        preexec_fn=_limits,
    )
    output = proc.stdout[:MAX_OUTPUT_BYTES]
    return {
        "check": check,
        "argv": argv,
        "returncode": proc.returncode,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "output": output.decode("utf-8", "replace"),
        "output_truncated": len(proc.stdout) > MAX_OUTPUT_BYTES,
        "passed": proc.returncode == 0,
    }


def verify_job(package: dict[str, Any]) -> dict[str, Any]:
    verify_signature(package)
    if package.get("version") != 1:
        raise ValueError("unsupported verifier package version")
    job_id = safe_job_id(str(package.get("job_id") or ""))
    staged_rel = str(package.get("staged_path") or "")
    if not staged_rel or staged_rel.startswith("/") or ".." in Path(staged_rel).parts:
        raise ValueError("staged_path must be a safe relative path")

    staged_root = (ROOT / "staged").resolve()
    worktree = (staged_root / staged_rel).resolve()
    if worktree == staged_root or staged_root not in worktree.parents or not worktree.is_dir():
        raise ValueError("staged repository tree is unavailable")

    expected_tree_hash = str(package.get("tree_manifest_sha256") or "")
    manifest = worktree / ".bountyforge-manifest.json"
    if not manifest.is_file():
        raise ValueError("staged tree manifest is missing")
    manifest_bytes = manifest.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_tree_hash:
        raise ValueError("staged tree manifest hash mismatch")

    tree_stats = inspect_tree(worktree)
    checks = package.get("checks") or []
    if not isinstance(checks, list) or not checks or len(checks) > 3:
        raise ValueError("one to three verification checks are required")
    if not all(isinstance(check, str) and check in ALLOWED_COMMANDS for check in checks):
        raise ValueError("verification check is not allowlisted")

    results = [run_check(worktree, check) for check in checks]
    passed = all(result["passed"] for result in results)
    return {
        "version": 1,
        "job_id": job_id,
        "source": package.get("source"),
        "task_id": package.get("task_id"),
        "contract_id": package.get("contract_id"),
        "execution_mode": package.get("execution_mode"),
        "expected_task_updated_at": package.get("expected_task_updated_at"),
        "title": package.get("title"),
        "passed": passed,
        "tree": tree_stats,
        "checks": results,
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def sign_result(result: dict[str, Any]) -> dict[str, Any]:
    signed = dict(result)
    signed["signature"] = hmac.new(SECRET.encode(), canonical_body(signed), hashlib.sha256).hexdigest()
    return signed


def run_once() -> list[dict[str, Any]]:
    for folder in ("inbox", "outbox", "processed", "failed", "staged"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted((ROOT / "inbox").glob("*.json")):
        try:
            package = json.loads(path.read_text())
            result = sign_result(verify_job(package))
            path.replace(ROOT / "processed" / path.name)
        except Exception as exc:
            result = sign_result(
                {
                    "version": 1,
                    "job_id": path.stem,
                    "passed": False,
                    "error": str(exc)[:1000],
                }
            )
            path.replace(ROOT / "failed" / path.name)
        atomic_json(ROOT / "outbox" / path.name, result)
        results.append(result)
    return results


def worker() -> None:
    poll = max(1, int(os.getenv("BOUNTYFORGE_REPO_VERIFY_POLL_SECONDS", "5")))
    while True:
        for result in run_once():
            print(json.dumps(result, sort_keys=True), flush=True)
        time.sleep(poll)


if __name__ == "__main__":
    worker()
