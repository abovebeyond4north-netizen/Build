from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path


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
        record = ArchiveRecord(
            id=self.make_id(expression, generation),
            generation=generation,
            parent_id=parent_id,
            expression=expression,
            score=score,
            accepted=accepted,
            reason=reason,
            created_at=time.time(),
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

    def novelty(self, expression: str) -> float:
        """Reward expressions that differ from the archive.

        Cheap string-level novelty is enough for the seed prototype. Future builds
        can replace this with AST edit distance, behaviour embeddings, or MAP-Elites.
        """

        records = self.records()
        if not records:
            return 1.0
        tokens = set(expression.replace("(", " ").replace(")", " ").split())
        distances: list[float] = []
        for record in records[-50:]:
            other = set(record.expression.replace("(", " ").replace(")", " ").split())
            union = tokens | other
            if not union:
                distances.append(0.0)
            else:
                distances.append(1.0 - len(tokens & other) / len(union))
        return max(0.0, min(1.0, sum(distances) / len(distances)))
