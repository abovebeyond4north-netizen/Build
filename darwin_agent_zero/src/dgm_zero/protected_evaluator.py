from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import protected_evaluator_worker


PROTECTED_EVALUATOR_LEDGER_VERSION = 1
PROTECTED_EVALUATOR_PROTOCOL_VERSION = protected_evaluator_worker.PROTOCOL_VERSION
PROTECTED_CAPABILITIES = protected_evaluator_worker.SUPPORTED_CAPABILITIES


@dataclass(frozen=True)
class ProtectedEvaluationDecision:
    ledger_version: int
    protocol_version: int
    capability: str
    baseline_digest: str
    finalist_digest: str
    evaluator_digest: str
    suite_digest: str
    seed: int
    case_count: int
    containment_passed: bool
    baseline_score: float
    finalist_score: float
    delta: float
    required_score: float
    minimum_gain: float
    passed: bool
    reason: str
    created_at: float
    previous_hash: str | None = None
    record_hash: str | None = None


class ProtectedEvaluationLedger:
    """Hash-chained audit log for one-shot protected evaluator decisions."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "protected_evaluator.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[ProtectedEvaluationDecision]:
        if not self.path.exists():
            return []
        output: list[ProtectedEvaluationDecision] = []
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
                    raise ValueError("record must be an object")
                record = ProtectedEvaluationDecision(**raw)
                validate_decision(record)
                if record.previous_hash != previous_hash:
                    raise ValueError("hash-chain predecessor mismatch")
                if protected_record_hash(record) != record.record_hash:
                    raise ValueError("record hash mismatch")
                previous_hash = record.record_hash
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid protected evaluator record on line {line_number}: {exc}"
                ) from exc
            output.append(record)
        return output

    def find(
        self,
        *,
        capability: str,
        baseline_digest: str,
        finalist_digest: str,
        evaluator_digest: str,
        protocol_version: int,
    ) -> ProtectedEvaluationDecision | None:
        for record in reversed(self.records()):
            if (
                record.capability == capability
                and record.baseline_digest == baseline_digest
                and record.finalist_digest == finalist_digest
                and record.evaluator_digest == evaluator_digest
                and record.protocol_version == protocol_version
            ):
                return record
        return None

    def append(
        self,
        decision: ProtectedEvaluationDecision,
    ) -> ProtectedEvaluationDecision:
        existing = self.records()
        previous_hash = existing[-1].record_hash if existing else None
        unsigned = ProtectedEvaluationDecision(
            **{
                **asdict(decision),
                "previous_hash": previous_hash,
                "record_hash": None,
            }
        )
        sealed = ProtectedEvaluationDecision(
            **{
                **asdict(unsigned),
                "record_hash": protected_record_hash(unsigned),
            }
        )
        validate_decision(sealed)
        atomic_write_text(
            self.path,
            "".join(
                json.dumps(asdict(item), sort_keys=True) + "\n"
                for item in [*existing, sealed]
            ),
        )
        return sealed


class ProtectedEvaluator:
    """Run fresh, hidden built-in capability tests in a separate process.

    Candidate generation receives no protected cases or seeds. A finalist is
    evaluated at most once for a fixed evaluator version; repeated calls reuse the
    sealed decision rather than drawing fresh tests that could become adaptive
    tuning feedback.
    """

    def __init__(
        self,
        workspace: Path,
        *,
        timeout_seconds: float = 20.0,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.workspace = workspace
        self.timeout_seconds = float(timeout_seconds)
        self.ledger = ProtectedEvaluationLedger(workspace)

    def required_for(self, capability: str) -> bool:
        return capability in PROTECTED_CAPABILITIES

    def evaluate(
        self,
        *,
        capability: str,
        entrypoint: str,
        baseline_source: str,
        finalist_source: str,
        required_score: float,
        minimum_gain: float,
    ) -> ProtectedEvaluationDecision | None:
        if not self.required_for(capability):
            return None
        for name, value in (
            ("required_score", required_score),
            ("minimum_gain", minimum_gain),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 1.0
            ):
                raise ValueError(f"{name} must be finite and between 0 and 1")
        if not isinstance(entrypoint, str) or not entrypoint.isidentifier():
            raise ValueError("entrypoint must be a Python identifier")
        if not isinstance(baseline_source, str) or not baseline_source.strip():
            raise ValueError("baseline_source must be non-empty")
        if not isinstance(finalist_source, str) or not finalist_source.strip():
            raise ValueError("finalist_source must be non-empty")

        evaluator_digest = worker_digest()
        baseline_digest = source_digest(baseline_source)
        finalist_digest = source_digest(finalist_source)
        cached = self.ledger.find(
            capability=capability,
            baseline_digest=baseline_digest,
            finalist_digest=finalist_digest,
            evaluator_digest=evaluator_digest,
            protocol_version=PROTECTED_EVALUATOR_PROTOCOL_VERSION,
        )
        if cached is not None:
            return cached

        seed = self._fresh_seed()
        request = {
            "protocol_version": PROTECTED_EVALUATOR_PROTOCOL_VERSION,
            "capability": capability,
            "entrypoint": entrypoint,
            "baseline_source": baseline_source,
            "finalist_source": finalist_source,
            "seed": seed,
        }
        response = self._run_worker(request)
        if response.get("protocol_version") != PROTECTED_EVALUATOR_PROTOCOL_VERSION:
            raise ValueError("protected evaluator protocol mismatch")
        if response.get("evaluator_digest") != evaluator_digest:
            raise ValueError("protected evaluator source digest mismatch")

        suite_digest = require_sha256(response.get("suite_digest"), "suite_digest")
        case_count = require_positive_int(response.get("case_count"), "case_count")
        containment_passed = response.get("containment_passed")
        if not isinstance(containment_passed, bool):
            raise ValueError("protected evaluator returned invalid containment status")
        baseline_score = require_score(response.get("baseline_score"), "baseline_score")
        finalist_score = require_score(response.get("finalist_score"), "finalist_score")
        delta = finalist_score - baseline_score
        threshold = float(required_score)
        gain = float(minimum_gain)

        if not containment_passed:
            passed = False
            reason = "containment_probe_failed"
        elif finalist_digest == baseline_digest:
            passed = False
            reason = "identical_to_baseline"
        elif finalist_score + 1e-12 < threshold:
            passed = False
            reason = "hidden_suite_below_required_score"
        elif delta + 1e-12 < gain:
            passed = False
            reason = "hidden_suite_insufficient_gain"
        else:
            passed = True
            reason = "passed"

        decision = ProtectedEvaluationDecision(
            ledger_version=PROTECTED_EVALUATOR_LEDGER_VERSION,
            protocol_version=PROTECTED_EVALUATOR_PROTOCOL_VERSION,
            capability=capability,
            baseline_digest=baseline_digest,
            finalist_digest=finalist_digest,
            evaluator_digest=evaluator_digest,
            suite_digest=suite_digest,
            seed=seed,
            case_count=case_count,
            containment_passed=containment_passed,
            baseline_score=baseline_score,
            finalist_score=finalist_score,
            delta=delta,
            required_score=threshold,
            minimum_gain=gain,
            passed=passed,
            reason=reason,
            created_at=time.time(),
        )
        return self.ledger.append(decision)

    def _fresh_seed(self) -> int:
        used = {record.seed for record in self.ledger.records()}
        for _ in range(128):
            seed = secrets.randbits(63)
            if seed not in used:
                return seed
        raise RuntimeError("unable to allocate a fresh protected evaluator seed")

    def _run_worker(self, request: dict[str, Any]) -> dict[str, Any]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "dgm_zero.protected_evaluator_worker",
                ],
                input=json.dumps(request, sort_keys=True, allow_nan=False),
                capture_output=True,
                text=True,
                env=env,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("protected evaluator process timed out") from exc
        if completed.returncode != 0:
            detail = (completed.stdout or completed.stderr).strip()[:1000]
            raise ValueError(f"protected evaluator process failed: {detail}")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("protected evaluator returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise ValueError("protected evaluator response must be an object")
        if response.get("error"):
            raise ValueError(f"protected evaluator error: {response['error']}")
        return response


def worker_digest() -> str:
    path = Path(protected_evaluator_worker.__file__).resolve()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def require_score(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return score


def require_positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def validate_decision(record: ProtectedEvaluationDecision) -> None:
    if record.ledger_version != PROTECTED_EVALUATOR_LEDGER_VERSION:
        raise ValueError("unsupported protected evaluator ledger version")
    if record.protocol_version != PROTECTED_EVALUATOR_PROTOCOL_VERSION:
        raise ValueError("unsupported protected evaluator protocol version")
    for name, digest in (
        ("baseline_digest", record.baseline_digest),
        ("finalist_digest", record.finalist_digest),
        ("evaluator_digest", record.evaluator_digest),
        ("suite_digest", record.suite_digest),
    ):
        require_sha256(digest, name)
    if isinstance(record.seed, bool) or not isinstance(record.seed, int) or record.seed < 0:
        raise ValueError("seed must be a non-negative integer")
    require_positive_int(record.case_count, "case_count")
    require_score(record.baseline_score, "baseline_score")
    require_score(record.finalist_score, "finalist_score")
    if not math.isfinite(record.delta) or not -1.0 <= record.delta <= 1.0:
        raise ValueError("delta must be finite and between -1 and 1")
    require_score(record.required_score, "required_score")
    require_score(record.minimum_gain, "minimum_gain")
    if not isinstance(record.containment_passed, bool):
        raise ValueError("containment_passed must be boolean")
    if not isinstance(record.passed, bool):
        raise ValueError("passed must be boolean")
    if not isinstance(record.reason, str) or not record.reason:
        raise ValueError("reason must be non-empty")
    if not math.isfinite(record.created_at) or record.created_at <= 0:
        raise ValueError("created_at must be finite and positive")
    if record.previous_hash is not None:
        require_sha256(record.previous_hash, "previous_hash")
    if record.record_hash is not None:
        require_sha256(record.record_hash, "record_hash")


def protected_record_hash(record: ProtectedEvaluationDecision) -> str:
    payload = asdict(record)
    payload.pop("record_hash", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
