from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REMOTE_LEDGER_VERSION = 1
REMOTE_PROTOCOL_VERSION = 2
REMOTE_RESULT_MARKER = "<!-- dgm-remote-verifier-result:v2 -->"
REMOTE_REJECT_MARKER = "<!-- dgm-remote-verifier-rejected:v2 -->"
REMOTE_CAPABILITIES = frozenset(
    {
        "normalize_text",
        "sequence_span",
        "clamp_value",
        "python_error_diagnosis",
    }
)
DEFAULT_REPOSITORY = "abovebeyond4north-netizen/Build"
DEFAULT_WORKFLOW_PATH = ".github/workflows/remote_verifier_authority.yml"


@dataclass(frozen=True)
class RemoteEvaluationDecision:
    ledger_version: int
    repository: str
    workflow_path: str
    evaluation_key: str
    issue_number: int
    reused_remote_issue: bool
    receipt_sha256: str
    attestation_verified: bool
    remote_protocol_version: int
    authority_version: str
    authority_digest: str
    manifest_digest: str
    request_digest: str
    receipt_nonce: str
    capability: str
    baseline_digest: str
    finalist_digest: str
    suite_digest: str
    hidden_case_count: int
    metamorphic_pair_count: int
    containment_passed: bool
    deterministic_replay: bool
    baseline_score: float
    finalist_score: float
    baseline_metamorphic_score: float
    finalist_metamorphic_score: float
    delta: float
    required_score: float
    minimum_gain: float
    passed: bool
    reason: str
    source_ref: str
    workflow_sha: str
    created_at: float
    previous_hash: str | None = None
    record_hash: str | None = None


class RemoteEvaluationLedger:
    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "remote_evaluator.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[RemoteEvaluationDecision]:
        if not self.path.exists():
            return []
        output: list[RemoteEvaluationDecision] = []
        previous_hash: str | None = None
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise ValueError("remote record must be an object")
                record = RemoteEvaluationDecision(**raw)
                validate_remote_decision(record)
                if record.previous_hash != previous_hash:
                    raise ValueError("remote ledger predecessor mismatch")
                if remote_record_hash(record) != record.record_hash:
                    raise ValueError("remote ledger record hash mismatch")
                previous_hash = record.record_hash
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid remote evaluator ledger line {line_number}: {exc}"
                ) from exc
            output.append(record)
        return output

    def find(self, evaluation_key: str) -> RemoteEvaluationDecision | None:
        for record in reversed(self.records()):
            if record.evaluation_key == evaluation_key:
                return record
        return None

    def append(
        self,
        decision: RemoteEvaluationDecision,
    ) -> RemoteEvaluationDecision:
        existing = self.records()
        previous_hash = existing[-1].record_hash if existing else None
        unsigned = RemoteEvaluationDecision(
            **{
                **asdict(decision),
                "previous_hash": previous_hash,
                "record_hash": None,
            }
        )
        sealed = RemoteEvaluationDecision(
            **{
                **asdict(unsigned),
                "record_hash": remote_record_hash(unsigned),
            }
        )
        validate_remote_decision(sealed)
        atomic_write_text(
            self.path,
            "".join(
                json.dumps(asdict(item), sort_keys=True) + "\n"
                for item in [*existing, sealed]
            ),
        )
        return sealed


class GitHubRemoteVerifier:
    """Client for the GitHub-hosted attested verifier authority."""

    def __init__(
        self,
        workspace: Path,
        *,
        repository: str | None = None,
        workflow_path: str = DEFAULT_WORKFLOW_PATH,
        timeout_seconds: float = 600.0,
        poll_seconds: float = 3.0,
        gh_bin: str | None = None,
        token: str | None = None,
    ) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.repository = (
            repository
            or os.environ.get("DGM_REMOTE_VERIFIER_REPOSITORY")
            or os.environ.get("GITHUB_REPOSITORY")
            or DEFAULT_REPOSITORY
        )
        validate_repository(self.repository)
        if not isinstance(workflow_path, str) or not workflow_path.strip():
            raise ValueError("workflow_path must be non-empty")
        self.workflow_path = workflow_path.strip()
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or float(timeout_seconds) <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        if (
            isinstance(poll_seconds, bool)
            or not isinstance(poll_seconds, (int, float))
            or not math.isfinite(float(poll_seconds))
            or float(poll_seconds) <= 0
        ):
            raise ValueError("poll_seconds must be finite and positive")
        self.timeout_seconds = float(timeout_seconds)
        self.poll_seconds = float(poll_seconds)
        configured_gh = gh_bin or os.environ.get("DGM_GH_BIN") or "gh"
        self.gh_bin = shutil.which(configured_gh)
        if self.gh_bin is None:
            raise ValueError(
                "GitHub CLI is required for remote verification"
            )
        self.token = (
            token
            or os.environ.get("DGM_REMOTE_VERIFIER_TOKEN")
            or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
        )
        self.signer_digest = os.environ.get(
            "DGM_REMOTE_VERIFIER_SIGNER_DIGEST"
        )
        if self.signer_digest is not None:
            require_sha1_or_sha256_hex(
                self.signer_digest,
                "DGM_REMOTE_VERIFIER_SIGNER_DIGEST",
            )
        self.ledger = RemoteEvaluationLedger(workspace)

    def required_for(self, capability: str) -> bool:
        return capability in REMOTE_CAPABILITIES

    def evaluate(
        self,
        *,
        capability: str,
        entrypoint: str,
        baseline_source: str,
        finalist_source: str,
        required_score: float,
        minimum_gain: float,
    ) -> RemoteEvaluationDecision | None:
        if not self.required_for(capability):
            return None

        required = require_score(required_score, "required_score")
        gain = require_score(minimum_gain, "minimum_gain")
        request = {
            "protocol_version": 2,
            "request_nonce": secrets.token_hex(32),
            "capability": capability,
            "entrypoint": entrypoint,
            "baseline_source": baseline_source,
            "finalist_source": finalist_source,
            "required_score": required,
            "minimum_gain": gain,
        }
        key = evaluation_key(request)
        cached = self.ledger.find(key)
        if cached is not None:
            return cached

        issue_number = self._create_issue(request, key)
        receipt_bytes, reused_remote_issue = self._wait_for_receipt(
            issue_number=issue_number,
            request_nonce=request["request_nonce"],
            evaluation_key_value=key,
        )
        receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
        self._verify_attestation(receipt_bytes)
        receipt = parse_json_object(receipt_bytes, "remote receipt")
        self._validate_receipt(
            receipt=receipt,
            request=request,
            evaluation_key_value=key,
            allow_prior_nonce=reused_remote_issue,
        )

        context = require_object(receipt.get("context"), "receipt context")
        decision = RemoteEvaluationDecision(
            ledger_version=REMOTE_LEDGER_VERSION,
            repository=self.repository,
            workflow_path=self.workflow_path,
            evaluation_key=key,
            issue_number=require_positive_int(
                receipt.get("issue_number"),
                "issue_number",
            ),
            reused_remote_issue=reused_remote_issue,
            receipt_sha256=receipt_sha256,
            attestation_verified=True,
            remote_protocol_version=require_positive_int(
                receipt.get("remote_protocol_version"),
                "remote_protocol_version",
            ),
            authority_version=require_text(
                receipt.get("authority_version"),
                "authority_version",
            ),
            authority_digest=require_sha256(
                receipt.get("authority_digest"),
                "authority_digest",
            ),
            manifest_digest=require_sha256(
                receipt.get("manifest_digest"),
                "manifest_digest",
            ),
            request_digest=require_sha256(
                receipt.get("request_digest"),
                "request_digest",
            ),
            receipt_nonce=require_sha256(
                receipt.get("request_nonce"),
                "request_nonce",
            ),
            capability=capability,
            baseline_digest=require_sha256(
                receipt.get("baseline_digest"),
                "baseline_digest",
            ),
            finalist_digest=require_sha256(
                receipt.get("finalist_digest"),
                "finalist_digest",
            ),
            suite_digest=require_sha256(
                receipt.get("suite_digest"),
                "suite_digest",
            ),
            hidden_case_count=require_positive_int(
                receipt.get("hidden_case_count"),
                "hidden_case_count",
            ),
            metamorphic_pair_count=require_positive_int(
                receipt.get("metamorphic_pair_count"),
                "metamorphic_pair_count",
            ),
            containment_passed=require_bool(
                receipt.get("containment_passed"),
                "containment_passed",
            ),
            deterministic_replay=require_bool(
                receipt.get("deterministic_replay"),
                "deterministic_replay",
            ),
            baseline_score=require_score(
                receipt.get("baseline_score"),
                "baseline_score",
            ),
            finalist_score=require_score(
                receipt.get("finalist_score"),
                "finalist_score",
            ),
            baseline_metamorphic_score=require_score(
                receipt.get("baseline_metamorphic_score"),
                "baseline_metamorphic_score",
            ),
            finalist_metamorphic_score=require_score(
                receipt.get("finalist_metamorphic_score"),
                "finalist_metamorphic_score",
            ),
            delta=require_delta(receipt.get("delta"), "delta"),
            required_score=required,
            minimum_gain=gain,
            passed=require_bool(receipt.get("passed"), "passed"),
            reason=require_text(receipt.get("reason"), "reason"),
            source_ref=require_text(
                context.get("source_ref"),
                "source_ref",
            ),
            workflow_sha=require_git_sha(
                context.get("workflow_sha"),
                "workflow_sha",
            ),
            created_at=require_positive_float(
                receipt.get("created_at"),
                "created_at",
            ),
        )
        return self.ledger.append(decision)

    def _create_issue(
        self,
        request: dict[str, Any],
        key: str,
    ) -> int:
        payload = {
            "title": f"[DGM-VERIFY] {key}",
            "body": json.dumps(
                request,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        }
        with tempfile.TemporaryDirectory(
            prefix="dgm-remote-request-"
        ) as tmp:
            path = Path(tmp) / "issue.json"
            path.write_text(
                json.dumps(payload, sort_keys=True),
                encoding="utf-8",
            )
            completed = self._run_gh(
                [
                    "api",
                    "--method",
                    "POST",
                    f"repos/{self.repository}/issues",
                    "--input",
                    str(path),
                ]
            )
        response = parse_json_object(
            completed.stdout.encode("utf-8"),
            "GitHub issue response",
        )
        return require_positive_int(response.get("number"), "issue number")

    def _wait_for_receipt(
        self,
        *,
        issue_number: int,
        request_nonce: str,
        evaluation_key_value: str,
    ) -> tuple[bytes, bool]:
        deadline = time.monotonic() + self.timeout_seconds
        current_issue = issue_number

        while True:
            comments = self._fetch_comments(current_issue)
            for comment in comments:
                body = comment.get("body")
                user = comment.get("user")
                login = (
                    user.get("login")
                    if isinstance(user, dict)
                    else None
                )
                if login != "github-actions[bot]" or not isinstance(body, str):
                    continue
                if REMOTE_RESULT_MARKER in body:
                    receipt = parse_result_comment(body)
                    if (
                        receipt["evaluation_key"]
                        != evaluation_key_value
                    ):
                        continue
                    if (
                        current_issue == issue_number
                        and receipt["request_nonce"] != request_nonce
                    ):
                        raise ValueError(
                            "remote receipt nonce does not match request"
                        )
                    return receipt["receipt_bytes"], (
                        current_issue != issue_number
                    )
                if (
                    current_issue == issue_number
                    and REMOTE_REJECT_MARKER in body
                ):
                    earlier = parse_earlier_issue(body)
                    if earlier is None:
                        raise ValueError(
                            "remote verifier rejected request without "
                            "an earlier evidence reference"
                        )
                    current_issue = earlier
                    break
            else:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "timed out waiting for remote verifier receipt"
                    )
                time.sleep(self.poll_seconds)
                continue
            # A duplicate rejection redirected us to the original evidence.
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "timed out resolving prior remote verifier receipt"
                )

    def _fetch_comments(self, issue_number: int) -> list[dict[str, Any]]:
        completed = self._run_gh(
            [
                "api",
                f"repos/{self.repository}/issues/{issue_number}/comments"
                "?per_page=100",
            ]
        )
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "GitHub comments response is invalid JSON"
            ) from exc
        if not isinstance(data, list):
            raise ValueError("GitHub comments response must be a list")
        return [item for item in data if isinstance(item, dict)]

    def _verify_attestation(self, receipt_bytes: bytes) -> None:
        with tempfile.TemporaryDirectory(
            prefix="dgm-remote-attestation-"
        ) as tmp:
            receipt_path = Path(tmp) / "receipt.json"
            receipt_path.write_bytes(receipt_bytes)
            command = [
                "attestation",
                "verify",
                str(receipt_path),
                "-R",
                self.repository,
                "--signer-workflow",
                f"{self.repository}/{self.workflow_path}",
                "--source-ref",
                "refs/heads/main",
                "--deny-self-hosted-runners",
                "--format",
                "json",
            ]
            if self.signer_digest is not None:
                command.extend(
                    ["--signer-digest", self.signer_digest]
                )
            completed = self._run_gh(command)
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "GitHub attestation verification returned invalid JSON"
            ) from exc
        if not isinstance(data, list) or not data:
            raise ValueError(
                "GitHub attestation verification returned no verified claims"
            )

    def _validate_receipt(
        self,
        *,
        receipt: dict[str, Any],
        request: dict[str, Any],
        evaluation_key_value: str,
        allow_prior_nonce: bool,
    ) -> None:
        if receipt.get("remote_protocol_version") != REMOTE_PROTOCOL_VERSION:
            raise ValueError("remote receipt protocol version mismatch")
        if receipt.get("evaluation_key") != evaluation_key_value:
            raise ValueError("remote receipt evaluation key mismatch")
        if receipt.get("capability") != request["capability"]:
            raise ValueError("remote receipt capability mismatch")
        if receipt.get("baseline_digest") != source_digest(
            request["baseline_source"]
        ):
            raise ValueError("remote receipt baseline digest mismatch")
        if receipt.get("finalist_digest") != source_digest(
            request["finalist_source"]
        ):
            raise ValueError("remote receipt finalist digest mismatch")
        if abs(
            require_score(
                receipt.get("required_score"),
                "receipt required_score",
            )
            - float(request["required_score"])
        ) > 1e-12:
            raise ValueError("remote receipt required-score mismatch")
        if abs(
            require_score(
                receipt.get("minimum_gain"),
                "receipt minimum_gain",
            )
            - float(request["minimum_gain"])
        ) > 1e-12:
            raise ValueError("remote receipt minimum-gain mismatch")

        if not allow_prior_nonce:
            if receipt.get("request_nonce") != request["request_nonce"]:
                raise ValueError("remote receipt nonce mismatch")
            if receipt.get("request_digest") != hashlib.sha256(
                canonical_json(request)
            ).hexdigest():
                raise ValueError("remote receipt request digest mismatch")

        if receipt.get("containment_passed") is not True:
            # A failed containment receipt can still be authentic, but it must
            # never be interpreted as a passing promotion result.
            if receipt.get("passed") is True:
                raise ValueError(
                    "remote receipt passed despite containment failure"
                )
        if receipt.get("deterministic_replay") is not True:
            if receipt.get("passed") is True:
                raise ValueError(
                    "remote receipt passed despite replay failure"
                )

        context = require_object(receipt.get("context"), "receipt context")
        if context.get("repository") != self.repository:
            raise ValueError("remote receipt repository mismatch")
        if context.get("source_ref") != "refs/heads/main":
            raise ValueError("remote receipt source ref mismatch")
        expected_workflow_suffix = (
            f"{self.repository}/{self.workflow_path}@refs/heads/main"
        )
        if context.get("workflow_ref") != expected_workflow_suffix:
            raise ValueError("remote receipt workflow ref mismatch")

    def _run_gh(
        self,
        args: list[str],
    ) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        if self.token is not None:
            env["GH_TOKEN"] = self.token
        try:
            completed = subprocess.run(
                [self.gh_bin, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("GitHub CLI command timed out") from exc
        if completed.returncode != 0:
            detail = (
                completed.stderr
                or completed.stdout
                or "GitHub CLI command failed"
            ).strip()[-1000:]
            raise ValueError(f"GitHub CLI failed: {detail}")
        return completed


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def evaluation_key(request: dict[str, Any]) -> str:
    material = dict(request)
    material.pop("request_nonce", None)
    payload = {
        "remote_protocol_version": REMOTE_PROTOCOL_VERSION,
        "request": material,
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def parse_result_comment(body: str) -> dict[str, Any]:
    digest_match = re.search(
        r"Receipt SHA-256:\s*([0-9a-f]{64})",
        body,
    )
    key_match = re.search(
        r"Evaluation key:\s*([0-9a-f]{64})",
        body,
    )
    nonce_match = re.search(
        r"Request nonce:\s*([0-9a-f]{64})",
        body,
    )
    payload_match = re.search(
        r"<details><summary>Attested receipt payload \(base64\)</summary>"
        r"\s+([A-Za-z0-9+/=]+)\s+</details>",
        body,
        flags=re.DOTALL,
    )
    if not all(
        (
            digest_match,
            key_match,
            nonce_match,
            payload_match,
        )
    ):
        raise ValueError("remote verifier result comment is malformed")
    try:
        receipt_bytes = base64.b64decode(
            payload_match.group(1),
            validate=True,
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError(
            "remote verifier receipt payload is not valid base64"
        ) from exc
    digest = hashlib.sha256(receipt_bytes).hexdigest()
    if digest != digest_match.group(1):
        raise ValueError("remote verifier receipt digest mismatch")
    return {
        "receipt_sha256": digest,
        "evaluation_key": key_match.group(1),
        "request_nonce": nonce_match.group(1),
        "receipt_bytes": receipt_bytes,
    }


def parse_earlier_issue(body: str) -> int | None:
    match = re.search(r"earlier issue\s+(\d+)", body)
    if match is None:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def parse_json_object(data: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def validate_repository(value: str) -> None:
    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        value,
    ):
        raise ValueError("repository must be in owner/name form")


def validate_remote_decision(record: RemoteEvaluationDecision) -> None:
    if record.ledger_version != REMOTE_LEDGER_VERSION:
        raise ValueError("unsupported remote ledger version")
    validate_repository(record.repository)
    require_text(record.workflow_path, "workflow_path")
    for name, value in (
        ("evaluation_key", record.evaluation_key),
        ("receipt_sha256", record.receipt_sha256),
        ("authority_digest", record.authority_digest),
        ("manifest_digest", record.manifest_digest),
        ("request_digest", record.request_digest),
        ("receipt_nonce", record.receipt_nonce),
        ("baseline_digest", record.baseline_digest),
        ("finalist_digest", record.finalist_digest),
        ("suite_digest", record.suite_digest),
    ):
        require_sha256(value, name)
    require_positive_int(record.issue_number, "issue_number")
    require_bool(record.reused_remote_issue, "reused_remote_issue")
    if record.attestation_verified is not True:
        raise ValueError("remote decision must have verified attestation")
    require_positive_int(
        record.remote_protocol_version,
        "remote_protocol_version",
    )
    require_text(record.authority_version, "authority_version")
    require_text(record.capability, "capability")
    require_positive_int(record.hidden_case_count, "hidden_case_count")
    require_positive_int(
        record.metamorphic_pair_count,
        "metamorphic_pair_count",
    )
    require_bool(record.containment_passed, "containment_passed")
    require_bool(record.deterministic_replay, "deterministic_replay")
    require_score(record.baseline_score, "baseline_score")
    require_score(record.finalist_score, "finalist_score")
    require_score(
        record.baseline_metamorphic_score,
        "baseline_metamorphic_score",
    )
    require_score(
        record.finalist_metamorphic_score,
        "finalist_metamorphic_score",
    )
    require_delta(record.delta, "delta")
    require_score(record.required_score, "required_score")
    require_score(record.minimum_gain, "minimum_gain")
    require_bool(record.passed, "passed")
    require_text(record.reason, "reason")
    if record.source_ref != "refs/heads/main":
        raise ValueError("remote decision source_ref must be refs/heads/main")
    require_git_sha(record.workflow_sha, "workflow_sha")
    require_positive_float(record.created_at, "created_at")
    if record.previous_hash is not None:
        require_sha256(record.previous_hash, "previous_hash")
    if record.record_hash is not None:
        require_sha256(record.record_hash, "record_hash")


def remote_record_hash(record: RemoteEvaluationDecision) -> str:
    payload = asdict(record)
    payload.pop("record_hash", None)
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def require_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be boolean")
    return value


def require_positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def require_positive_float(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def require_score(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return number


def require_delta(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not -1.0 <= number <= 1.0:
        raise ValueError(f"{name} must be finite and between -1 and 1")
    return number


def require_sha256(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def require_git_sha(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) not in (40, 64)
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"{name} must be a Git object digest")
    return value


def require_sha1_or_sha256_hex(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) not in (40, 64)
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"{name} must be a 40- or 64-character hex digest")
    return value


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
