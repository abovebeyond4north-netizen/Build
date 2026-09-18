from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(os.getenv("BOUNTYFORGE_REPO_VERIFY_DIR", "/repo-verify"))
SECRET = os.getenv("BOUNTYFORGE_REPO_VERIFY_SECRET", "")
MAX_ARCHIVE_BYTES = max(1024 * 1024, int(os.getenv("BOUNTYFORGE_REPO_ARCHIVE_MAX_BYTES", str(20 * 1024 * 1024))))
MAX_TREE_BYTES = max(1024 * 1024, int(os.getenv("BOUNTYFORGE_REPO_VERIFY_MAX_TREE_BYTES", str(50 * 1024 * 1024))))
MAX_FILES = max(10, int(os.getenv("BOUNTYFORGE_REPO_VERIFY_MAX_FILES", "5000")))
FETCH_TIMEOUT = max(5, int(os.getenv("BOUNTYFORGE_REPO_FETCH_TIMEOUT_SECONDS", "30")))

REPO_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def canonical_body(payload: dict[str, Any]) -> bytes:
    unsigned = {k: v for k, v in payload.items() if k != "signature"}
    return json.dumps(unsigned, separators=(",", ":"), sort_keys=True).encode()


def sign(payload: dict[str, Any]) -> dict[str, Any]:
    if not SECRET:
        raise ValueError("repository verifier secret is not configured")
    signed = dict(payload)
    signed["signature"] = hmac.new(SECRET.encode(), canonical_body(signed), hashlib.sha256).hexdigest()
    return signed


def verify_signature(payload: dict[str, Any]) -> None:
    if not SECRET:
        raise ValueError("repository verifier secret is not configured")
    supplied = str(payload.get("signature") or "")
    expected = hmac.new(SECRET.encode(), canonical_body(payload), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ValueError("invalid repository stage signature")


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", value):
        raise ValueError("invalid staging job id")
    return value


def fetch_archive(repo_url: str, commit_sha: str) -> tuple[bytes, str, str]:
    match = REPO_RE.fullmatch(repo_url)
    if not match:
        raise ValueError("only public github.com HTTPS repositories are supported")
    if not SHA_RE.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a full 40-hex commit")
    owner, repo = match.group(1), match.group(2)
    url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{commit_sha.lower()}"
    req = urllib.request.Request(url, headers={"User-Agent": "BountyForge-RepoStager/1.0"})
    chunks = []
    total = 0
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as response:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise ValueError("repository archive exceeds compressed-size limit")
            chunks.append(chunk)
    return b"".join(chunks), owner, repo


def safe_extract(archive: bytes, destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=False)
    file_count = 0
    total_size = 0
    files: list[dict[str, Any]] = []

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        members = tf.getmembers()
        if not members:
            raise ValueError("repository archive was empty")
        top = members[0].name.split("/", 1)[0]
        prefix = top + "/"

        for member in members:
            name = member.name
            if name == top or not name.startswith(prefix):
                continue
            rel = name[len(prefix):]
            if not rel:
                continue
            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise ValueError("archive contains path traversal")
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ValueError("archive contains unsupported special files")
            target = (destination / rel_path).resolve()
            root = destination.resolve()
            if target == root or root not in target.parents:
                raise ValueError("archive extraction escaped staging root")

            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue

            file_count += 1
            total_size += int(member.size)
            if file_count > MAX_FILES:
                raise ValueError("repository exceeds file-count limit")
            if total_size > MAX_TREE_BYTES:
                raise ValueError("repository exceeds expanded-size limit")

            source = tf.extractfile(member)
            if source is None:
                raise ValueError("unable to read archived file")
            data = source.read()
            if len(data) != member.size:
                raise ValueError("archived file size mismatch")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o644)
            files.append(
                {
                    "path": rel_path.as_posix(),
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

    return {
        "files": sorted(files, key=lambda item: item["path"]),
        "file_count": file_count,
        "tree_bytes": total_size,
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def stage(package: dict[str, Any]) -> dict[str, Any]:
    verify_signature(package)
    if package.get("version") != 1:
        raise ValueError("unsupported stage package version")
    job_id = safe_job_id(str(package.get("job_id") or ""))
    repo_url = str(package.get("repo_url") or "")
    commit_sha = str(package.get("commit_sha") or "").lower()
    checks = package.get("checks") or []
    if not isinstance(checks, list) or not checks or len(checks) > 3:
        raise ValueError("one to three verifier checks are required")

    archive, owner, repo = fetch_archive(repo_url, commit_sha)
    staged_root = ROOT / "staged" / job_id
    if staged_root.exists():
        shutil.rmtree(staged_root)
    tree = safe_extract(archive, staged_root)

    manifest = {
        "version": 1,
        "repo_url": f"https://github.com/{owner}/{repo}",
        "commit_sha": commit_sha,
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        **tree,
    }
    manifest_path = staged_root / ".bountyforge-manifest.json"
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    verifier_package = sign(
        {
            "version": 1,
            "job_id": job_id,
            "source": package.get("source"),
            "task_id": package.get("task_id"),
            "contract_id": package.get("contract_id"),
            "expected_task_updated_at": package.get("expected_task_updated_at"),
            "title": package.get("title"),
            "staged_path": job_id,
            "tree_manifest_sha256": manifest_hash,
            "checks": checks,
        }
    )
    atomic_json(ROOT / "inbox" / f"{job_id}.json", verifier_package)
    return {
        "job_id": job_id,
        "repo_url": manifest["repo_url"],
        "commit_sha": commit_sha,
        "tree_manifest_sha256": manifest_hash,
        "file_count": tree["file_count"],
        "tree_bytes": tree["tree_bytes"],
        "queued_for_verification": True,
    }


def run_once() -> list[dict[str, Any]]:
    for folder in ("fetch-inbox", "fetch-outbox", "fetch-processed", "fetch-failed", "inbox", "staged"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted((ROOT / "fetch-inbox").glob("*.json")):
        try:
            package = json.loads(path.read_text())
            result = {"ok": True, **stage(package)}
            path.replace(ROOT / "fetch-processed" / path.name)
        except Exception as exc:
            result = {"ok": False, "job_id": path.stem, "error": str(exc)[:1000]}
            path.replace(ROOT / "fetch-failed" / path.name)
        atomic_json(ROOT / "fetch-outbox" / path.name, sign(result))
        results.append(result)
    return results


def worker() -> None:
    poll = max(1, int(os.getenv("BOUNTYFORGE_REPO_STAGE_POLL_SECONDS", "5")))
    while True:
        for result in run_once():
            print(json.dumps(result, sort_keys=True), flush=True)
        time.sleep(poll)


if __name__ == "__main__":
    worker()
