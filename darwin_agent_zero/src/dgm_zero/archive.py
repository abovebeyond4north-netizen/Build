from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

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


class Archive:
    """Append-only evolutionary memory for generated agents/tools."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.path = self.workspace / "archive.jsonl"

    def make_id(self, expression: str, generation: int) -> str:
        digest = hashlib.sha256(
            f"{generation}:{expression}".encode("utf-8")
        ).hexdigest()
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

        signature = expression_signature(expression)
        record = ArchiveRecord(
            id=self.make_id(expression, generation),
            generation=generation,
            parent_id=parent_id,
            expression=expression,
            score=clean_score,
            accepted=accepted,
            reason=reason,
            created_at=time.time(),
            signature=signature.digest,
            bucket=signature.bucket,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
        return record

    def records(self) -> list[ArchiveRecord]:
        if not self.path.exists():
            return []
        output: list[ArchiveRecord] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                record = self._validate_loaded_record(ArchiveRecord(**data))
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

    def novelty(self, expression: str) -> float:
        """Reward expressions that differ in source and behaviour."""
        expression = self._validate_text(expression, "expression")
        records = self.records()
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
