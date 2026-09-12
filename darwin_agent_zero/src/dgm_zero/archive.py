from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .signature import expression_signature


@dataclass(frozen=True)
class ArchiveRecord:
    id: str
    generation: int
    parent_id: str | None
    expression: str
    score: dict[str, float]
    accepted: bool
    reason: str
    created_at: float
    signature: str | None = None
    bucket: str | None = None
    evaluation_context: str | None = None
    verified_delta: float | None = None
    previous_hash: str | None = None
    record_hash: str | None = None


class Archive:
    """Append-only evolutionary memory for generated agents/tools.

    New records are hash chained so modifications or reordering are detected on
    read. Oracle-backed records can carry both the evaluation-context digest and
    the parent-to-child score delta measured within that same frozen context.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.path = self.workspace / "archive.jsonl"
        self._pending_evaluation_context: (
            tuple[str, str, float | None] | None
        ) = None

    def make_id(
        self,
        expression: str,
        generation: int,
        nonce: int | str | None = None,
    ) -> str:
        identity = f"{generation}:{expression}"
        if nonce is not None:
            identity = f"{identity}:{nonce}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return digest[:16]

    @staticmethod
    def _validate_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value

    @staticmethod
    def _validate_score(score: Mapping[str, float]) -> dict[str, float]:
        if not isinstance(score, Mapping):
            raise ValueError("score must be a mapping")
        output: dict[str, float] = {}
        for name, raw_value in score.items():
            if not isinstance(name, str) or not name:
                raise ValueError("score keys must be non-empty strings")
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"score {name} must be numeric") from exc
            if not math.isfinite(value):
                raise ValueError(f"score {name} must be finite")
            output[name] = value

        if "weighted_total" in output and not 0.0 <= output["weighted_total"] <= 1.0:
            raise ValueError("score weighted_total must be between 0 and 1")
        return output

    @staticmethod
    def _validate_delta(value: float | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("verified_delta must be numeric, not boolean")
        delta = float(value)
        if not math.isfinite(delta) or not -1.0 <= delta <= 1.0:
            raise ValueError("verified_delta must be finite and between -1 and 1")
        return delta

    def stage_evaluation_context(
        self,
        expression: str,
        digest: str,
        verified_delta: float | None = None,
    ) -> None:
        """Stage one context/delta pair for the next matching append."""
        expression = self._validate_text(expression, "expression")
        if not is_sha256(digest):
            raise ValueError("evaluation_context must be a SHA-256 digest")
        delta = self._validate_delta(verified_delta)
        self._pending_evaluation_context = (expression, digest, delta)

    @classmethod
    def _validate_loaded_record(cls, record: ArchiveRecord) -> ArchiveRecord:
        cls._validate_text(record.id, "id")
        if isinstance(record.generation, bool) or not isinstance(record.generation, int):
            raise ValueError("generation must be an integer")
        if record.parent_id is not None:
            cls._validate_text(record.parent_id, "parent_id")
        cls._validate_text(record.expression, "expression")
        cls._validate_text(record.reason, "reason")
        if not isinstance(record.accepted, bool):
            raise ValueError("accepted must be a boolean")
        if not math.isfinite(float(record.created_at)):
            raise ValueError("created_at must be finite")
        if record.evaluation_context is not None and not is_sha256(
            record.evaluation_context
        ):
            raise ValueError("evaluation_context must be a SHA-256 digest")
        verified_delta = cls._validate_delta(record.verified_delta)
        if verified_delta is not None and record.evaluation_context is None:
            raise ValueError("verified_delta requires evaluation_context")
        score = cls._validate_score(record.score)
        return ArchiveRecord(
            id=record.id,
            generation=record.generation,
            parent_id=record.parent_id,
            expression=record.expression,
            score=score,
            accepted=record.accepted,
            reason=record.reason,
            created_at=float(record.created_at),
            signature=record.signature,
            bucket=record.bucket,
            evaluation_context=record.evaluation_context,
            verified_delta=verified_delta,
            previous_hash=record.previous_hash,
            record_hash=record.record_hash,
        )

    def append(
        self,
        *,
        generation: int,
        parent_id: str | None,
        expression: str,
        score: dict[str, float],
        accepted: bool,
        reason: str,
        evaluation_context: str | None = None,
        verified_delta: float | None = None,
    ) -> ArchiveRecord:
        if isinstance(generation, bool) or not isinstance(generation, int):
            raise ValueError("generation must be an integer")
        expression = self._validate_text(expression, "expression")
        reason = self._validate_text(reason, "reason")
        if parent_id is not None:
            parent_id = self._validate_text(parent_id, "parent_id")
        if not isinstance(accepted, bool):
            raise ValueError("accepted must be a boolean")
        clean_score = self._validate_score(score)

        pending = self._pending_evaluation_context
        self._pending_evaluation_context = None
        if pending is not None:
            pending_expression, pending_digest, pending_delta = pending
            if pending_expression == expression:
                if evaluation_context is None:
                    evaluation_context = pending_digest
                if verified_delta is None:
                    verified_delta = pending_delta
        if evaluation_context is not None and not is_sha256(evaluation_context):
            raise ValueError("evaluation_context must be a SHA-256 digest")
        verified_delta = self._validate_delta(verified_delta)
        if verified_delta is not None and evaluation_context is None:
            raise ValueError("verified_delta requires evaluation_context")

        existing = self.records()
        previous_hash = next(
            (
                record.record_hash
                for record in reversed(existing)
                if record.record_hash is not None
            ),
            None,
        )
        existing_ids = {record.id for record in existing}
        if parent_id is not None and parent_id not in existing_ids:
            raise ValueError(f"parent_id does not reference an existing archive record: {parent_id}")

        nonce = time.time_ns()
        record_id = self.make_id(expression, generation, nonce)
        while record_id in existing_ids:
            nonce += 1
            record_id = self.make_id(expression, generation, nonce)

        signature = expression_signature(expression)
        unsigned = ArchiveRecord(
            id=record_id,
            generation=generation,
            parent_id=parent_id,
            expression=expression,
            score=clean_score,
            accepted=accepted,
            reason=reason,
            created_at=nonce / 1_000_000_000,
            signature=signature.digest,
            bucket=signature.bucket,
            evaluation_context=evaluation_context,
            verified_delta=verified_delta,
            previous_hash=previous_hash,
            record_hash=None,
        )
        record = ArchiveRecord(
            **{
                **asdict(unsigned),
                "record_hash": archive_record_hash(unsigned),
            }
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
        return record

    def records(self) -> list[ArchiveRecord]:
        if not self.path.exists():
            return []
        output: list[ArchiveRecord] = []
        chained_started = False
        previous_hash: str | None = None
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                record = self._validate_loaded_record(ArchiveRecord(**data))
                if record.record_hash is None:
                    if chained_started:
                        raise ValueError("unchained record follows chained records")
                else:
                    chained_started = True
                    if not is_sha256(record.record_hash):
                        raise ValueError("malformed record hash")
                    if record.previous_hash != previous_hash:
                        raise ValueError("hash-chain predecessor mismatch")
                    if archive_record_hash(record) != record.record_hash:
                        raise ValueError("record hash mismatch")
                    previous_hash = record.record_hash
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid archive record on line {line_number}: {exc}"
                ) from exc
            output.append(record)
        return output

    def accepted(self) -> list[ArchiveRecord]:
        return [record for record in self.records() if record.accepted]

    def champion(self) -> ArchiveRecord | None:
        accepted = self.accepted()
        if not accepted:
            return None
        return max(
            accepted,
            key=lambda record: record.score.get("weighted_total", 0.0),
        )

    def elites_by_bucket(self) -> dict[str, ArchiveRecord]:
        """Return the best accepted record in each behaviour bucket."""
        elites: dict[str, ArchiveRecord] = {}
        for record in self.accepted():
            bucket = record.bucket or "unknown"
            current = elites.get(bucket)
            if (
                current is None
                or record.score.get("weighted_total", 0.0)
                > current.score.get("weighted_total", 0.0)
            ):
                elites[bucket] = record
        return elites

    def novelty(
        self,
        expression: str,
        reference_records: Iterable[ArchiveRecord] | None = None,
    ) -> float:
        """Reward source/behaviour novelty against a chosen archive snapshot."""
        expression = self._validate_text(expression, "expression")
        records = (
            self.records()
            if reference_records is None
            else list(reference_records)
        )
        if not records:
            return 1.0
        tokens = set(expression.replace("(", " ").replace(")", " ").split())
        signature = expression_signature(expression)
        distances: list[float] = []
        for record in records[-50:]:
            other = set(
                record.expression.replace("(", " ").replace(")", " ").split()
            )
            union = tokens | other
            token_distance = (
                0.0 if not union else 1.0 - len(tokens & other) / len(union)
            )
            behaviour_distance = (
                0.0 if record.signature == signature.digest else 1.0
            )
            distances.append((token_distance + behaviour_distance) / 2.0)
        return max(0.0, min(1.0, sum(distances) / len(distances)))


def archive_record_hash(record: ArchiveRecord) -> str:
    payload = asdict(record)
    payload.pop("record_hash", None)
    # Preserve verification of older hash-chained archives. Optional evidence
    # fields that did not exist in a legacy record are excluded when absent.
    if payload.get("evaluation_context") is None:
        payload.pop("evaluation_context", None)
    if payload.get("verified_delta") is None:
        payload.pop("verified_delta", None)
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
