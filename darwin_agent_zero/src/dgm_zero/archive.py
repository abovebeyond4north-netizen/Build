from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

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
        digest = hashlib.sha256(f"{generation}:{expression}".encode("utf-8")).hexdigest()
        return digest[:16]

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
        signature = expression_signature(expression)
        record = ArchiveRecord(
            id=self.make_id(expression, generation),
            generation=generation,
            parent_id=parent_id,
            expression=expression,
            score=score,
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
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            output.append(ArchiveRecord(**data))
        return output

    def accepted(self) -> list[ArchiveRecord]:
        return [record for record in self.records() if record.accepted]

    def champion(self) -> ArchiveRecord | None:
        accepted = self.accepted()
        if not accepted:
            return None
        return max(accepted, key=lambda record: record.score.get("weighted_total", 0.0))

    def elites_by_bucket(self) -> dict[str, ArchiveRecord]:
        """Return the best accepted record in each behaviour bucket."""

        elites: dict[str, ArchiveRecord] = {}
        for record in self.accepted():
            bucket = record.bucket or "unknown"
            current = elites.get(bucket)
            if current is None or record.score.get("weighted_total", 0.0) > current.score.get("weighted_total", 0.0):
                elites[bucket] = record
        return elites

    def novelty(self, expression: str) -> float:
        """Reward expressions that differ in source and behaviour."""

        records = self.records()
        if not records:
            return 1.0
        tokens = set(expression.replace("(", " ").replace(")", " ").split())
        signature = expression_signature(expression)
        distances: list[float] = []
        for record in records[-50:]:
            other = set(record.expression.replace("(", " ").replace(")", " ").split())
            union = tokens | other
            token_distance = 0.0 if not union else 1.0 - len(tokens & other) / len(union)
            behaviour_distance = 0.0 if record.signature == signature.digest else 1.0
            distances.append((token_distance + behaviour_distance) / 2.0)
        return max(0.0, min(1.0, sum(distances) / len(distances)))
