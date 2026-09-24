from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROTECTED_EVALUATOR_LEDGER_VERSION = 2
PROTECTED_EVALUATOR_PROTOCOL_VERSION = 2
PROTECTED_CAPABILITIES = frozenset(
    {
        "normalize_text",
        "sequence_span",
        "clamp_value",
        "python_error_diagnosis",
    }
)


@dataclass(frozen=True)
class ProtectedEvaluationDecision:
    ledger_version: int
    protocol_version: int
    capability: str
    baseline_digest: str
    finalist_digest: str
    evaluator_digest: str
    suite_digest: str
    seed: int | None
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
    authority_version: str | None = None
    manifest_digest: str | None = None
    public_key_sha256: str | None = None
    authority_signature: str | None = None
    evaluation_id: str | None = None
    metamorphic_pair_count: int = 0
    baseline_metamorphic_score: float | None = None
    finalist_metamorphic_score: float | None = None
    replay_verified: bool = False
    replay_signature: str | None = None


class ProtectedEvaluationLedger:
    """Hash-chained public audit log for protected authority decisions."""

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
                record_hash = raw.get("record_hash")
                if not is_sha256(record_hash):
                    raise ValueError("record hash is malformed")
                if raw.get("previous_hash") != previous_hash:
                    raise ValueError("hash-chain predecessor mismatch")
                if protected_record_hash_dict(raw) != record_hash:
                    raise ValueError("record hash mismatch")
                data = dict(raw)
                version = data.get("ledger_version")
                if version == 1:
                    data.setdefault("authority_version", None)
                    data.setdefault("manifest_digest", None)
                    data.setdefault("public_key_sha256", None)
                    data.setdefault("authority_signature", None)
                    data.setdefault("evaluation_id", None)
                    data.setdefault("metamorphic_pair_count", 0)
                    data.setdefault("baseline_metamorphic_score", None)
                    data.setdefault("finalist_metamorphic_score", None)
                    data.setdefault("replay_verified", False)
                    data.setdefault("replay_signature", None)
                record = ProtectedEvaluationDecision(**data)
                validate_decision(record)
                previous_hash = record.record_hash
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid protected evaluator record on line "
                    f"{line_number}: {exc}"
                ) from exc
            output.append(record)
        return output

    def by_evaluation_id(
        self,
        evaluation_id: str,
    ) -> ProtectedEvaluationDecision | None:
        for record in reversed(self.records()):
            if record.evaluation_id == evaluation_id:
                return record
        return None

    def append(
        self,
        decision: ProtectedEvaluationDecision,
    ) -> ProtectedEvaluationDecision:
        existing = self.records()
        previous_hash = (
            existing[-1].record_hash
            if existing
            else None
        )
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
        rows = [*existing, sealed]
        atomic_write_text(
            self.path,
            "".join(
                json.dumps(
                    serialized_record(row),
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
                for row in rows
            ),
        )
        return sealed


class ProtectedEvaluator:
    """Client for the separately versioned verifier authority.

    Hidden test generation, the signing key, private seeds, and the independent
    candidate sandbox live outside the learner package. The learner receives only
    a signed receipt. The public-key fingerprint is pinned on first use unless an
    explicit fingerprint is supplied, and identity changes fail closed.
    """

    def __init__(
        self,
        workspace: Path,
        *,
        timeout_seconds: float = 30.0,
        authority_path: Path | None = None,
        authority_state: Path | None = None,
        trusted_public_key_sha256: str | None = None,
        authority_mode: str | None = None,
        authority_image: str | None = None,
        authority_volume: str | None = None,
        docker_bin: str | None = None,
    ) -> None:
        if (
            not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds must be finite and positive"
            )
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = float(timeout_seconds)
        self.ledger = ProtectedEvaluationLedger(workspace)
        self.authority_path = (
            Path(authority_path).resolve()
            if authority_path is not None
            else default_authority_path()
        )
        self.authority_state = (
            Path(authority_state).expanduser().resolve()
            if authority_state is not None
            else default_authority_state()
        )
        self.authority_mode = (
            authority_mode
            or os.environ.get("DGM_VERIFIER_AUTHORITY_MODE")
            or "container"
        ).strip().lower()
        if self.authority_mode not in {"container", "process"}:
            raise ValueError(
                "authority_mode must be 'container' or 'process'"
            )
        self.authority_image = (
            authority_image
            or os.environ.get("DGM_VERIFIER_AUTHORITY_IMAGE")
            or "dgm-verifier-authority:local"
        )
        if not isinstance(self.authority_image, str) or not self.authority_image.strip():
            raise ValueError("authority_image must be non-empty")
        self.authority_volume = (
            authority_volume
            or os.environ.get("DGM_VERIFIER_AUTHORITY_VOLUME")
            or default_authority_volume(self.workspace)
        )
        if not isinstance(self.authority_volume, str) or not self.authority_volume.strip():
            raise ValueError("authority_volume must be non-empty")
        configured_docker = (
            docker_bin
            or os.environ.get("DGM_DOCKER_BIN")
            or "docker"
        )
        self.docker_bin = (
            shutil.which(configured_docker)
            if self.authority_mode == "container"
            else None
        )
        if self.authority_mode == "container" and self.docker_bin is None:
            raise ValueError(
                "Docker is required for protected evaluation; "
                "process fallback is disabled unless explicitly selected"
            )
        self.runtime_metadata: dict[str, Any] | None = None
        configured_pin = (
            trusted_public_key_sha256
            or os.environ.get(
                "DGM_VERIFIER_PUBLIC_KEY_SHA256"
            )
        )
        if configured_pin is not None:
            require_sha256(
                configured_pin,
                "trusted_public_key_sha256",
            )
        self.configured_pin = configured_pin
        self.trust_path = (
            workspace / "verifier_authority_trust.json"
        )

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
        required = require_score(
            required_score,
            "required_score",
        )
        gain = require_score(
            minimum_gain,
            "minimum_gain",
        )
        if (
            not isinstance(entrypoint, str)
            or not entrypoint.isidentifier()
            or entrypoint.startswith("_")
        ):
            raise ValueError(
                "entrypoint must be a public Python identifier"
            )
        if (
            not isinstance(baseline_source, str)
            or not baseline_source.strip()
        ):
            raise ValueError(
                "baseline_source must be non-empty"
            )
        if (
            not isinstance(finalist_source, str)
            or not finalist_source.strip()
        ):
            raise ValueError(
                "finalist_source must be non-empty"
            )

        identity_response = self._run_authority(
            "describe",
            None,
        )
        identity = require_object(
            identity_response.get("identity"),
            "authority identity",
        )
        public_key_pem = require_text(
            identity_response.get("public_key_pem"),
            "authority public key",
        )
        identity_signature = require_text(
            identity_response.get(
                "identity_signature"
            ),
            "authority identity signature",
        )
        self._verify_and_pin_identity(
            identity,
            identity_signature,
            public_key_pem,
        )

        request = {
            "protocol_version": (
                PROTECTED_EVALUATOR_PROTOCOL_VERSION
            ),
            "capability": capability,
            "entrypoint": entrypoint,
            "baseline_source": baseline_source,
            "finalist_source": finalist_source,
            "required_score": required,
            "minimum_gain": gain,
        }
        evaluation_response = self._run_authority(
            "evaluate",
            request,
        )
        receipt = require_object(
            evaluation_response.get("receipt"),
            "authority receipt",
        )
        signature = require_text(
            evaluation_response.get("signature"),
            "authority receipt signature",
        )
        response_public_key = require_text(
            evaluation_response.get(
                "public_key_pem"
            ),
            "authority response public key",
        )
        if (
            sha256_text(response_public_key)
            != sha256_text(public_key_pem)
        ):
            raise ValueError(
                "authority public key changed during evaluation"
            )
        verify_signature(
            public_key_pem,
            receipt,
            signature,
        )
        self._validate_receipt(
            receipt=receipt,
            identity=identity,
            capability=capability,
            baseline_source=baseline_source,
            finalist_source=finalist_source,
            required_score=required,
            minimum_gain=gain,
        )

        evaluation_id = require_text(
            receipt.get("evaluation_id"),
            "evaluation_id",
        )
        existing = self.ledger.by_evaluation_id(
            evaluation_id
        )
        if existing is not None:
            if (
                existing.authority_signature
                != signature
            ):
                raise ValueError(
                    "authority reused evaluation_id "
                    "with a different signature"
                )
            return existing

        replay_response = self._run_authority(
            "replay",
            {
                "protocol_version": (
                    PROTECTED_EVALUATOR_PROTOCOL_VERSION
                ),
                "evaluation_id": evaluation_id,
                "baseline_source": baseline_source,
                "finalist_source": finalist_source,
            },
        )
        replay = require_object(
            replay_response.get("replay"),
            "authority replay",
        )
        replay_signature = require_text(
            replay_response.get(
                "replay_signature"
            ),
            "authority replay signature",
        )
        replay_public_key = require_text(
            replay_response.get(
                "public_key_pem"
            ),
            "authority replay public key",
        )
        if (
            sha256_text(replay_public_key)
            != sha256_text(public_key_pem)
        ):
            raise ValueError(
                "authority public key changed during replay"
            )
        verify_signature(
            public_key_pem,
            replay,
            replay_signature,
        )
        self._validate_replay(
            replay,
            receipt,
            identity,
            signature,
        )

        decision = ProtectedEvaluationDecision(
            ledger_version=(
                PROTECTED_EVALUATOR_LEDGER_VERSION
            ),
            protocol_version=(
                PROTECTED_EVALUATOR_PROTOCOL_VERSION
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
            evaluator_digest=require_sha256(
                receipt.get("authority_digest"),
                "authority_digest",
            ),
            suite_digest=require_sha256(
                receipt.get("suite_digest"),
                "suite_digest",
            ),
            seed=None,
            case_count=require_positive_int(
                receipt.get("hidden_case_count"),
                "hidden_case_count",
            ),
            containment_passed=require_bool(
                receipt.get("containment_passed"),
                "containment_passed",
            ),
            baseline_score=require_score(
                receipt.get("baseline_score"),
                "baseline_score",
            ),
            finalist_score=require_score(
                receipt.get("finalist_score"),
                "finalist_score",
            ),
            delta=require_delta(
                receipt.get("delta"),
                "delta",
            ),
            required_score=required,
            minimum_gain=gain,
            passed=require_bool(
                receipt.get("passed"),
                "passed",
            ),
            reason=require_text(
                receipt.get("reason"),
                "reason",
            ),
            created_at=require_positive_float(
                receipt.get("created_at"),
                "created_at",
            ),
            authority_version=require_text(
                receipt.get("authority_version"),
                "authority_version",
            ),
            manifest_digest=require_sha256(
                receipt.get("manifest_digest"),
                "manifest_digest",
            ),
            public_key_sha256=require_sha256(
                receipt.get(
                    "public_key_sha256"
                ),
                "public_key_sha256",
            ),
            authority_signature=signature,
            evaluation_id=evaluation_id,
            metamorphic_pair_count=(
                require_positive_int(
                    receipt.get(
                        "metamorphic_pair_count"
                    ),
                    "metamorphic_pair_count",
                )
            ),
            baseline_metamorphic_score=(
                require_score(
                    receipt.get(
                        "baseline_metamorphic_score"
                    ),
                    "baseline_metamorphic_score",
                )
            ),
            finalist_metamorphic_score=(
                require_score(
                    receipt.get(
                        "finalist_metamorphic_score"
                    ),
                    "finalist_metamorphic_score",
                )
            ),
            replay_verified=True,
            replay_signature=replay_signature,
        )
        return self.ledger.append(decision)

    def _verify_and_pin_identity(
        self,
        identity: dict[str, Any],
        signature: str,
        public_key_pem: str,
    ) -> None:
        verify_signature(
            public_key_pem,
            identity,
            signature,
        )
        fingerprint = sha256_text(
            public_key_pem
        )
        if (
            require_sha256(
                identity.get("public_key_sha256"),
                "identity public_key_sha256",
            )
            != fingerprint
        ):
            raise ValueError(
                "authority identity public-key digest mismatch"
            )
        if (
            identity.get("protocol_version")
            != PROTECTED_EVALUATOR_PROTOCOL_VERSION
        ):
            raise ValueError(
                "authority protocol version mismatch"
            )
        authority_version = require_text(
            identity.get("authority_version"),
            "authority_version",
        )
        authority_digest = require_sha256(
            identity.get("authority_digest"),
            "authority_digest",
        )
        manifest_digest = require_sha256(
            identity.get("manifest_digest"),
            "manifest_digest",
        )
        supported = identity.get(
            "supported_capabilities"
        )
        if (
            not isinstance(supported, list)
            or set(supported)
            != set(PROTECTED_CAPABILITIES)
        ):
            raise ValueError(
                "authority capability manifest mismatch"
            )

        if (
            self.configured_pin is not None
            and fingerprint
            != self.configured_pin
        ):
            raise ValueError(
                "authority public key does not match "
                "configured trust pin"
            )

        if self.trust_path.exists():
            try:
                trust = json.loads(
                    self.trust_path.read_text(
                        encoding="utf-8"
                    )
                )
            except (
                OSError,
                json.JSONDecodeError,
            ) as exc:
                raise ValueError(
                    "invalid verifier authority trust file"
                ) from exc
            if not isinstance(trust, dict):
                raise ValueError(
                    "invalid verifier authority trust file"
                )
            if (
                trust.get("public_key_sha256")
                != fingerprint
            ):
                raise ValueError(
                    "verifier authority identity changed"
                )
            if trust.get("runtime_mode") not in (None, self.authority_mode):
                raise ValueError(
                    "verifier authority runtime mode changed"
                )
            if (
                self.runtime_metadata is not None
                and trust.get("runtime_image_id") not in (
                    None,
                    self.runtime_metadata.get("image_id"),
                )
            ):
                raise ValueError(
                    "verifier authority container image changed"
                )
            first_seen = trust.get(
                "first_seen"
            )
            if (
                isinstance(first_seen, bool)
                or not isinstance(
                    first_seen,
                    (int, float),
                )
                or not math.isfinite(
                    float(first_seen)
                )
                or float(first_seen) <= 0
            ):
                raise ValueError(
                    "invalid verifier authority trust timestamp"
                )
        else:
            first_seen = time.time()

        trust_record = {
            "schema_version": 1,
            "public_key_sha256": fingerprint,
            "first_seen": float(first_seen),
            "last_seen": time.time(),
            "authority_version": authority_version,
            "authority_digest": authority_digest,
            "manifest_digest": manifest_digest,
            "trust_mode": (
                "explicit_pin"
                if self.configured_pin
                is not None
                else "trust_on_first_use"
            ),
            "runtime_mode": self.authority_mode,
            "runtime_image": (
                self.authority_image
                if self.authority_mode == "container"
                else None
            ),
            "runtime_image_id": (
                self.runtime_metadata.get("image_id")
                if self.runtime_metadata is not None
                else None
            ),
            "runtime_user": (
                self.runtime_metadata.get("user")
                if self.runtime_metadata is not None
                else None
            ),
            "runtime_rootless": (
                self.runtime_metadata.get("rootless")
                if self.runtime_metadata is not None
                else None
            ),
        }
        atomic_write_text(
            self.trust_path,
            json.dumps(
                trust_record,
                indent=2,
                sort_keys=True,
            ),
        )

    def _validate_receipt(
        self,
        *,
        receipt: dict[str, Any],
        identity: dict[str, Any],
        capability: str,
        baseline_source: str,
        finalist_source: str,
        required_score: float,
        minimum_gain: float,
    ) -> None:
        if (
            receipt.get("protocol_version")
            != PROTECTED_EVALUATOR_PROTOCOL_VERSION
        ):
            raise ValueError(
                "protected authority receipt protocol mismatch"
            )
        for field in (
            "authority_version",
            "authority_digest",
            "manifest_digest",
            "public_key_sha256",
        ):
            if receipt.get(field) != identity.get(field):
                raise ValueError(
                    f"authority receipt {field} "
                    "does not match signed identity"
                )
        if receipt.get("capability") != capability:
            raise ValueError(
                "authority receipt capability mismatch"
            )
        if (
            receipt.get("baseline_digest")
            != source_digest(baseline_source)
        ):
            raise ValueError(
                "authority receipt baseline digest mismatch"
            )
        if (
            receipt.get("finalist_digest")
            != source_digest(finalist_source)
        ):
            raise ValueError(
                "authority receipt finalist digest mismatch"
            )
        if (
            abs(
                require_score(
                    receipt.get("required_score"),
                    "receipt required_score",
                )
                - required_score
            )
            > 1e-12
        ):
            raise ValueError(
                "authority receipt required-score mismatch"
            )
        if (
            abs(
                require_score(
                    receipt.get("minimum_gain"),
                    "receipt minimum_gain",
                )
                - minimum_gain
            )
            > 1e-12
        ):
            raise ValueError(
                "authority receipt minimum-gain mismatch"
            )
        require_sha256(
            receipt.get("suite_digest"),
            "suite_digest",
        )
        require_positive_int(
            receipt.get("hidden_case_count"),
            "hidden_case_count",
        )
        require_positive_int(
            receipt.get(
                "metamorphic_pair_count"
            ),
            "metamorphic_pair_count",
        )
        require_bool(
            receipt.get("containment_passed"),
            "containment_passed",
        )
        require_score(
            receipt.get("baseline_score"),
            "baseline_score",
        )
        require_score(
            receipt.get("finalist_score"),
            "finalist_score",
        )
        require_score(
            receipt.get(
                "baseline_metamorphic_score"
            ),
            "baseline_metamorphic_score",
        )
        require_score(
            receipt.get(
                "finalist_metamorphic_score"
            ),
            "finalist_metamorphic_score",
        )
        require_delta(
            receipt.get("delta"),
            "delta",
        )
        require_bool(
            receipt.get("passed"),
            "passed",
        )
        require_text(
            receipt.get("reason"),
            "reason",
        )
        require_positive_float(
            receipt.get("created_at"),
            "created_at",
        )

    @staticmethod
    def _validate_replay(
        replay: dict[str, Any],
        receipt: dict[str, Any],
        identity: dict[str, Any],
        original_signature: str,
    ) -> None:
        if (
            replay.get("protocol_version")
            != PROTECTED_EVALUATOR_PROTOCOL_VERSION
        ):
            raise ValueError(
                "authority replay protocol mismatch"
            )
        for field in (
            "authority_version",
            "authority_digest",
            "manifest_digest",
            "public_key_sha256",
        ):
            if replay.get(field) != identity.get(field):
                raise ValueError(
                    f"authority replay {field} mismatch"
                )
        if (
            replay.get("evaluation_id")
            != receipt.get("evaluation_id")
        ):
            raise ValueError(
                "authority replay evaluation_id mismatch"
            )
        if (
            replay.get("replay_of_signature")
            != original_signature
        ):
            raise ValueError(
                "authority replay does not reference "
                "the original signed receipt"
            )
        if (
            replay.get("matches_original")
            is not True
        ):
            raise ValueError(
                "authority replay did not reproduce "
                "the original evidence"
            )
        comparisons = (
            (
                "suite_digest",
                replay.get("suite_digest"),
                receipt.get("suite_digest"),
            ),
            (
                "baseline_score",
                replay.get("baseline_score"),
                receipt.get("baseline_score"),
            ),
            (
                "finalist_score",
                replay.get("finalist_score"),
                receipt.get("finalist_score"),
            ),
            (
                "baseline_metamorphic_score",
                replay.get(
                    "baseline_metamorphic_score"
                ),
                receipt.get(
                    "baseline_metamorphic_score"
                ),
            ),
            (
                "finalist_metamorphic_score",
                replay.get(
                    "finalist_metamorphic_score"
                ),
                receipt.get(
                    "finalist_metamorphic_score"
                ),
            ),
        )
        for name, actual, expected in comparisons:
            if actual != expected:
                raise ValueError(
                    f"authority replay {name} mismatch"
                )

    def _run_authority(
        self,
        command: str,
        request: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if self.authority_mode == "container":
            return self._run_container_authority(command, request)
        return self._run_process_authority(command, request)

    def _run_process_authority(
        self,
        command: str,
        request: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.runtime_metadata = {
            "mode": "process",
            "image_id": None,
            "user": None,
            "rootless": None,
        }
        if (
            not self.authority_path.exists()
            or not self.authority_path.is_file()
        ):
            raise ValueError(
                "verifier authority executable is missing: "
                f"{self.authority_path}"
            )
        manifest = self.authority_path.with_name(
            "manifest.json"
        )
        if (
            not manifest.exists()
            or not manifest.is_file()
        ):
            raise ValueError(
                "verifier authority manifest is missing"
            )
        self.authority_state.mkdir(
            parents=True,
            exist_ok=True,
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get(
                "HOME",
                str(Path.home()),
            ),
            "DGM_VERIFIER_AUTHORITY_STATE": (
                str(self.authority_state)
            ),
            "DGM_OPENSSL_BIN": os.environ.get(
                "DGM_OPENSSL_BIN",
                "openssl",
            ),
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": os.environ.get(
                "LANG",
                "C.UTF-8",
            ),
        }
        payload = (
            ""
            if request is None
            else json.dumps(
                request,
                sort_keys=True,
                allow_nan=False,
            )
        )
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    str(self.authority_path),
                    command,
                ],
                input=payload,
                capture_output=True,
                text=True,
                env=env,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "verifier authority process timed out"
            ) from exc
        return parse_authority_response(
            completed,
            "verifier authority process",
        )



    def _run_container_authority(
        self,
        command: str,
        request: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata = self._container_runtime_metadata()
        self.runtime_metadata = metadata
        payload = (
            ""
            if request is None
            else json.dumps(
                request,
                sort_keys=True,
                allow_nan=False,
            )
        )
        docker = require_text(self.docker_bin, "docker executable")
        run_command = [
            docker,
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            "64",
            "--memory",
            "256m",
            "--memory-swap",
            "256m",
            "--cpus",
            "1.0",
            "--shm-size",
            "16m",
            "--ulimit",
            "nofile=64:64",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--mount",
            (
                "type=volume,source="
                f"{self.authority_volume},target=/state"
            ),
            "--env",
            "DGM_VERIFIER_AUTHORITY_STATE=/state",
            "--env",
            "DGM_OPENSSL_BIN=/usr/bin/openssl",
            "--env",
            "PYTHONHASHSEED=0",
            "--env",
            "PYTHONNOUSERSITE=1",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            self.authority_image,
            command,
        ]
        try:
            completed = subprocess.run(
                run_command,
                input=payload,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "containerized verifier authority timed out"
            ) from exc
        return parse_authority_response(
            completed,
            "containerized verifier authority",
        )

    def _container_runtime_metadata(self) -> dict[str, Any]:
        docker = require_text(self.docker_bin, "docker executable")
        try:
            completed = subprocess.run(
                [
                    docker,
                    "image",
                    "inspect",
                    self.authority_image,
                ],
                capture_output=True,
                text=True,
                timeout=min(self.timeout_seconds, 10.0),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "Docker image inspection timed out"
            ) from exc
        if completed.returncode != 0:
            raise ValueError(
                "hardened verifier authority image is unavailable; "
                "build verifier_authority/Dockerfile before protected evaluation"
            )
        try:
            images = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Docker returned invalid image metadata"
            ) from exc
        if not isinstance(images, list) or len(images) != 1:
            raise ValueError("Docker image inspection returned an invalid result")
        image = images[0]
        if not isinstance(image, dict):
            raise ValueError("Docker image metadata must be an object")
        image_id = image.get("Id")
        if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
            raise ValueError("verifier authority image has no content digest")
        config = image.get("Config")
        if not isinstance(config, dict):
            raise ValueError("verifier authority image config is missing")
        user = config.get("User")
        if not isinstance(user, str) or user.strip() in {"", "0", "root", "0:0"}:
            raise ValueError(
                "verifier authority image must run as a non-root user"
            )
        labels = config.get("Labels")
        if not isinstance(labels, dict):
            raise ValueError("verifier authority image labels are missing")
        if labels.get("ai.recursive.verifier.authority") != "true":
            raise ValueError("image is not labeled as a verifier authority")
        if labels.get("ai.recursive.verifier.runtime") != "isolated-container-v1":
            raise ValueError("verifier authority image runtime label mismatch")

        info = subprocess.run(
            [
                docker,
                "info",
                "--format",
                "{{json .SecurityOptions}}",
            ],
            capture_output=True,
            text=True,
            timeout=min(self.timeout_seconds, 10.0),
            check=False,
        )
        if info.returncode != 0:
            raise ValueError("unable to inspect Docker security options")
        try:
            security_options = json.loads(info.stdout.strip())
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Docker returned invalid security options"
            ) from exc
        if not isinstance(security_options, list):
            raise ValueError("Docker security options must be a list")
        normalized = tuple(str(item) for item in security_options)
        if not any("seccomp" in item for item in normalized):
            raise ValueError(
                "Docker seccomp protection is required for verifier isolation"
            )
        rootless = any("rootless" in item for item in normalized)
        if os.environ.get("DGM_VERIFIER_REQUIRE_ROOTLESS") == "1" and not rootless:
            raise ValueError(
                "rootless Docker is required by DGM_VERIFIER_REQUIRE_ROOTLESS"
            )
        return {
            "mode": "container",
            "image": self.authority_image,
            "image_id": image_id,
            "user": user,
            "rootless": rootless,
            "security_options": list(normalized),
            "volume": self.authority_volume,
        }


def parse_authority_response(
    completed: subprocess.CompletedProcess[str],
    label: str,
) -> dict[str, Any]:
    detail = (
        completed.stdout
        or completed.stderr
        or ""
    ).strip()
    try:
        response = json.loads(detail)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label} returned invalid JSON"
        ) from exc
    if not isinstance(response, dict):
        raise ValueError(
            f"{label} response must be an object"
        )
    if completed.returncode != 0 or response.get("error"):
        raise ValueError(
            f"{label} failed: "
            f"{response.get('error') or detail[:1000]}"
        )
    return response


def default_authority_volume(workspace: Path) -> str:
    digest = hashlib.sha256(
        str(workspace.resolve()).encode("utf-8")
    ).hexdigest()[:24]
    return f"dgm-verifier-authority-{digest}"


def default_authority_path() -> Path:
    configured = os.environ.get(
        "DGM_VERIFIER_AUTHORITY_PATH"
    )
    if configured:
        return Path(
            configured
        ).expanduser().resolve()
    return (
        Path(__file__).resolve().parents[3]
        / "verifier_authority"
        / "authority.py"
    )


def default_authority_state() -> Path:
    configured = os.environ.get(
        "DGM_VERIFIER_AUTHORITY_STATE"
    )
    if configured:
        return Path(
            configured
        ).expanduser().resolve()
    return (
        Path.home()
        / ".dgm-verifier-authority"
    ).resolve()


def source_digest(source: str) -> str:
    return hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def canonical_json(
    value: dict[str, Any],
) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def openssl_bin() -> str:
    configured = os.environ.get(
        "DGM_OPENSSL_BIN",
        "openssl",
    )
    resolved = shutil.which(configured)
    if resolved is None:
        raise ValueError(
            "OpenSSL is required to verify "
            "verifier-authority signatures"
        )
    return resolved


def verify_signature(
    public_key_pem: str,
    payload: dict[str, Any],
    signature_b64: str,
) -> None:
    try:
        signature = base64.b64decode(
            signature_b64,
            validate=True,
        )
    except (
        ValueError,
        base64.binascii.Error,
    ) as exc:
        raise ValueError(
            "authority signature is not valid base64"
        ) from exc

    with tempfile.TemporaryDirectory(
        prefix="dgm-authority-verify-"
    ) as tmp:
        root = Path(tmp)
        public_key = root / "public.pem"
        signature_path = root / "signature.bin"
        public_key.write_text(
            public_key_pem,
            encoding="utf-8",
        )
        signature_path.write_bytes(signature)
        completed = subprocess.run(
            [
                openssl_bin(),
                "dgst",
                "-sha256",
                "-verify",
                str(public_key),
                "-signature",
                str(signature_path),
            ],
            input=canonical_json(payload),
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError(
                "verifier authority signature "
                "verification failed"
            )


def validate_decision(
    record: ProtectedEvaluationDecision,
) -> None:
    if record.ledger_version not in (1, 2):
        raise ValueError(
            "unsupported protected evaluator "
            "ledger version"
        )
    if record.protocol_version not in (1, 2):
        raise ValueError(
            "unsupported protected evaluator "
            "protocol version"
        )
    for name, digest in (
        (
            "baseline_digest",
            record.baseline_digest,
        ),
        (
            "finalist_digest",
            record.finalist_digest,
        ),
        (
            "evaluator_digest",
            record.evaluator_digest,
        ),
        (
            "suite_digest",
            record.suite_digest,
        ),
    ):
        require_sha256(digest, name)
    if record.seed is not None and (
        isinstance(record.seed, bool)
        or not isinstance(record.seed, int)
        or record.seed < 0
    ):
        raise ValueError(
            "seed must be null or a "
            "non-negative integer"
        )
    require_positive_int(
        record.case_count,
        "case_count",
    )
    require_bool(
        record.containment_passed,
        "containment_passed",
    )
    require_score(
        record.baseline_score,
        "baseline_score",
    )
    require_score(
        record.finalist_score,
        "finalist_score",
    )
    require_delta(
        record.delta,
        "delta",
    )
    require_score(
        record.required_score,
        "required_score",
    )
    require_score(
        record.minimum_gain,
        "minimum_gain",
    )
    require_bool(
        record.passed,
        "passed",
    )
    require_text(
        record.reason,
        "reason",
    )
    require_positive_float(
        record.created_at,
        "created_at",
    )

    if record.ledger_version == 2:
        require_text(
            record.authority_version,
            "authority_version",
        )
        require_sha256(
            record.manifest_digest,
            "manifest_digest",
        )
        require_sha256(
            record.public_key_sha256,
            "public_key_sha256",
        )
        require_text(
            record.authority_signature,
            "authority_signature",
        )
        require_text(
            record.evaluation_id,
            "evaluation_id",
        )
        require_positive_int(
            record.metamorphic_pair_count,
            "metamorphic_pair_count",
        )
        require_score(
            record.baseline_metamorphic_score,
            "baseline_metamorphic_score",
        )
        require_score(
            record.finalist_metamorphic_score,
            "finalist_metamorphic_score",
        )
        if record.replay_verified is not True:
            raise ValueError(
                "version-2 protected evidence "
                "must have a verified replay"
            )
        require_text(
            record.replay_signature,
            "replay_signature",
        )

    if record.previous_hash is not None:
        require_sha256(
            record.previous_hash,
            "previous_hash",
        )
    if record.record_hash is not None:
        require_sha256(
            record.record_hash,
            "record_hash",
        )


def serialized_record(
    record: ProtectedEvaluationDecision,
) -> dict[str, Any]:
    data = asdict(record)
    if record.ledger_version == 1:
        for field in (
            "authority_version",
            "manifest_digest",
            "public_key_sha256",
            "authority_signature",
            "evaluation_id",
            "metamorphic_pair_count",
            "baseline_metamorphic_score",
            "finalist_metamorphic_score",
            "replay_verified",
            "replay_signature",
        ):
            data.pop(field, None)
    return data


def protected_record_hash(
    record: ProtectedEvaluationDecision,
) -> str:
    return protected_record_hash_dict(
        serialized_record(record)
    )


def protected_record_hash_dict(
    row: dict[str, Any],
) -> str:
    payload = {
        key: value
        for key, value in row.items()
        if key != "record_hash"
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require_object(
    value: object,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{name} must be an object"
        )
    return value


def require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value
    ):
        raise ValueError(
            f"{name} must be non-empty text"
        )
    return value


def require_bool(
    value: object,
    name: str,
) -> bool:
    if not isinstance(value, bool):
        raise ValueError(
            f"{name} must be boolean"
        )
    return value


def require_positive_int(
    value: object,
    name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValueError(
            f"{name} must be a positive integer"
        )
    return value


def require_positive_float(
    value: object,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
    ):
        raise ValueError(
            f"{name} must be numeric"
        )
    number = float(value)
    if (
        not math.isfinite(number)
        or number <= 0
    ):
        raise ValueError(
            f"{name} must be finite and positive"
        )
    return number


def require_score(
    value: object,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
    ):
        raise ValueError(
            f"{name} must be numeric"
        )
    score = float(value)
    if (
        not math.isfinite(score)
        or not 0.0 <= score <= 1.0
    ):
        raise ValueError(
            f"{name} must be finite "
            "and between 0 and 1"
        )
    return score


def require_delta(
    value: object,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
    ):
        raise ValueError(
            f"{name} must be numeric"
        )
    delta = float(value)
    if (
        not math.isfinite(delta)
        or not -1.0 <= delta <= 1.0
    ):
        raise ValueError(
            f"{name} must be finite "
            "and between -1 and 1"
        )
    return delta


def require_sha256(
    value: object,
    name: str,
) -> str:
    if not is_sha256(value):
        raise ValueError(
            f"{name} must be a lowercase "
            "SHA-256 digest"
        )
    return str(value)


def is_sha256(value: object) -> bool:
    if (
        not isinstance(value, str)
        or len(value) != 64
    ):
        return False
    return all(
        character
        in "0123456789abcdef"
        for character in value
    )


def atomic_write_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    temp = path.with_name(
        f".{path.name}.{time.time_ns()}.tmp"
    )
    temp.write_text(
        content,
        encoding="utf-8",
    )
    temp.replace(path)
