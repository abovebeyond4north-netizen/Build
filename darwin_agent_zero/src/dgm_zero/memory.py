from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryEntry:
    kind: str
    content: str
    usefulness: float
    created_at: float


class KnowledgeBank:
    """Persistent lightweight memory for self-instruction and cultural transfer."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "knowledge.jsonl"
        workspace.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_limit(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        return value

    @staticmethod
    def _validated_usefulness(value: float) -> float:
        usefulness = float(value)
        if not math.isfinite(usefulness):
            raise ValueError("usefulness must be finite")
        return max(0.0, min(1.0, usefulness))

    @staticmethod
    def _validated_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value

    def deposit(
        self,
        kind: str,
        content: str,
        usefulness: float = 0.5,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            kind=self._validated_text(kind, "kind"),
            content=self._validated_text(content, "content"),
            usefulness=self._validated_usefulness(usefulness),
            created_at=time.time(),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return entry

    def entries(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []

        output: list[MemoryEntry] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                entry = MemoryEntry(**data)
                self._validated_text(entry.kind, "kind")
                self._validated_text(entry.content, "content")
                self._validated_usefulness(entry.usefulness)
                if not math.isfinite(float(entry.created_at)):
                    raise ValueError("created_at must be finite")
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid knowledge entry on line {line_number}: {exc}"
                ) from exc
            output.append(entry)
        return output

    def recall(
        self,
        kind: str | None = None,
        limit: int = 8,
    ) -> list[MemoryEntry]:
        limit = self._validate_limit(limit, "limit")
        if kind is not None:
            self._validated_text(kind, "kind")

        entries = self.entries()
        if kind is not None:
            entries = [entry for entry in entries if entry.kind == kind]
        return sorted(
            entries,
            key=lambda entry: entry.usefulness,
            reverse=True,
        )[:limit]

    def prune(self, max_entries: int = 200) -> None:
        max_entries = self._validate_limit(max_entries, "max_entries")
        entries = sorted(
            self.entries(),
            key=lambda entry: entry.usefulness,
            reverse=True,
        )[:max_entries]

        temp_path = self.path.with_name(f".{self.path.name}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        temp_path.replace(self.path)
