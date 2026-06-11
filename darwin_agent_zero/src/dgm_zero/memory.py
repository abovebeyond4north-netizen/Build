from __future__ import annotations

import json
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

    def deposit(self, kind: str, content: str, usefulness: float = 0.5) -> MemoryEntry:
        entry = MemoryEntry(kind=kind, content=content, usefulness=max(0.0, min(1.0, usefulness)), created_at=time.time())
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return entry

    def entries(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        output: list[MemoryEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                output.append(MemoryEntry(**json.loads(line)))
        return output

    def recall(self, kind: str | None = None, limit: int = 8) -> list[MemoryEntry]:
        entries = self.entries()
        if kind is not None:
            entries = [entry for entry in entries if entry.kind == kind]
        return sorted(entries, key=lambda entry: entry.usefulness, reverse=True)[:limit]

    def prune(self, max_entries: int = 200) -> None:
        entries = sorted(self.entries(), key=lambda entry: entry.usefulness, reverse=True)[:max_entries]
        with self.path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
