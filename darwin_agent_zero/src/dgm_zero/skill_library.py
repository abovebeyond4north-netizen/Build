from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .capability_model import (
    AcquisitionReport,
    CapabilitySpec,
    SkillCandidate,
)


CERTIFICATION_LEDGER_VERSION = 1


class SkillLibrary:
    """Content-addressed, append-versioned store for verified capability skills."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.root = workspace / "capabilities"
        self.root.mkdir(parents=True, exist_ok=True)
        self.certification_path = (
            workspace / "capability_certifications.jsonl"
        )

    def current(
        self,
        capability: str,
    ) -> tuple[str, dict[str, Any]] | None:
        root = self._capability_root(capability)
        current = root / "current.json"
        if not current.exists():
            return None
        try:
            data = json.loads(current.read_text(encoding="utf-8"))
            relative_path = data["relative_path"]
            expected_digest = data["digest"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError(
                f"invalid current skill manifest for {capability}"
            ) from exc

        path = (root / relative_path).resolve()
        resolved_root = root.resolve()
        if path != resolved_root and resolved_root not in path.parents:
            raise ValueError(
                f"current skill path escapes capability root for {capability}"
            )
        if not path.is_file():
            raise ValueError(
                f"current skill artifact is missing for {capability}"
            )
        source = path.read_text(encoding="utf-8")
        actual_digest = SkillCandidate(source, "installed").digest
        if actual_digest != expected_digest:
            raise ValueError(
                f"current skill digest mismatch for {capability}"
            )
        return source, data

    def current_source(self, capability: str) -> str | None:
        current = self.current(capability)
        return current[0] if current else None

    def certification_consumed(
        self,
        capability: str,
        holdout_digest: str,
    ) -> bool:
        return any(
            row.get("capability") == capability
            and row.get("holdout_digest") == holdout_digest
            for row in self._certifications()
        )

    def record_certification(
        self,
        *,
        capability: str,
        holdout_digest: str,
        finalist_digest: str,
        holdout_score: float,
        passed: bool,
    ) -> None:
        rows = self._certifications()
        if any(
            row.get("capability") == capability
            and row.get("holdout_digest") == holdout_digest
            for row in rows
        ):
            raise ValueError(
                "holdout suite has already been consumed for this capability"
            )

        previous_hash = next(
            (
                row["record_hash"]
                for row in reversed(rows)
                if isinstance(row.get("record_hash"), str)
            ),
            None,
        )
        row: dict[str, Any] = {
            "ledger_version": CERTIFICATION_LEDGER_VERSION,
            "previous_hash": previous_hash,
            "capability": capability,
            "holdout_digest": holdout_digest,
            "finalist_digest": finalist_digest,
            "holdout_score": holdout_score,
            "passed": bool(passed),
            "evaluated_at": time.time(),
        }
        row["record_hash"] = certification_record_hash(row)
        rows.append(row)
        atomic_write_text(
            self.certification_path,
            "".join(
                json.dumps(item, sort_keys=True) + "\n"
                for item in rows
            ),
        )

    def promote(
        self,
        spec: CapabilitySpec,
        candidate: SkillCandidate,
        report: AcquisitionReport,
    ) -> Path:
        root = self._capability_root(spec.name)
        versions = root / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        version_path = versions / f"{candidate.digest}.py"
        if not version_path.exists():
            atomic_write_text(version_path, candidate.source)

        manifest = {
            "capability": spec.name,
            "description": spec.description,
            "entrypoint": spec.entrypoint,
            "digest": candidate.digest,
            "relative_path": str(version_path.relative_to(root)),
            "final_score": report.final_score,
            "holdout_digest": report.holdout_digest,
            "promoted_at": report.created_at,
        }
        atomic_write_text(
            root / "current.json",
            json.dumps(manifest, indent=2, sort_keys=True),
        )

        history_path = root / "history.jsonl"
        history = (
            history_path.read_text(encoding="utf-8").splitlines()
            if history_path.exists()
            else []
        )
        history.append(json.dumps(manifest, sort_keys=True))
        atomic_write_text(history_path, "\n".join(history) + "\n")
        return version_path

    def _certifications(self) -> list[dict[str, Any]]:
        if not self.certification_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        chained_started = False
        previous_hash: str | None = None
        for line_number, line in enumerate(
            self.certification_path.read_text(
                encoding="utf-8"
            ).splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "invalid capability certification ledger at "
                    f"line {line_number}: {exc.msg}"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(
                    "invalid capability certification ledger at "
                    f"line {line_number}: expected object"
                )

            record_hash = row.get("record_hash")
            if record_hash is None:
                if chained_started:
                    raise ValueError(
                        "invalid capability certification ledger at "
                        f"line {line_number}: unchained record follows chained records"
                    )
                rows.append(row)
                continue

            chained_started = True
            if row.get("ledger_version") != CERTIFICATION_LEDGER_VERSION:
                raise ValueError(
                    "invalid capability certification ledger at "
                    f"line {line_number}: unsupported ledger version"
                )
            if not is_sha256(record_hash):
                raise ValueError(
                    "invalid capability certification ledger at "
                    f"line {line_number}: malformed record hash"
                )
            if row.get("previous_hash") != previous_hash:
                raise ValueError(
                    "invalid capability certification ledger at "
                    f"line {line_number}: hash-chain predecessor mismatch"
                )
            if certification_record_hash(row) != record_hash:
                raise ValueError(
                    "invalid capability certification ledger at "
                    f"line {line_number}: record hash mismatch"
                )
            score = row.get("holdout_score")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
                or not 0.0 <= float(score) <= 1.0
            ):
                raise ValueError(
                    "invalid capability certification ledger at "
                    f"line {line_number}: invalid holdout score"
                )
            previous_hash = record_hash
            rows.append(row)
        return rows

    def _capability_root(self, capability: str) -> Path:
        return self.root / capability


def certification_record_hash(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key != "record_hash"}
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def holdout_digest(spec: CapabilitySpec) -> str:
    payload = [
        {
            "name": case.name,
            "args": list(case.args),
            "expected": case.expected,
        }
        for case in spec.cases_for("holdout")
    ]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_report(
    workspace: Path,
    report: AcquisitionReport,
) -> None:
    report_path = Path(report.report_path)
    serialized = json.dumps(asdict(report), indent=2, sort_keys=True)
    atomic_write_text(report_path, serialized)
    atomic_write_text(
        workspace / "capability_acquisition_report.json",
        serialized,
    )


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
