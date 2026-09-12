from __future__ import annotations

import hashlib
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
    previous_hash: str | None = None
    entry_hash: str | None = None


class KnowledgeBank:
    """Persistent lightweight memory for self-instruction and cultural transfer.

    New entries are hash chained. Legacy unchained entries remain readable until
    the first chained entry, and pruning deliberately upgrades retained entries
    into a fresh fully chained memory file.
    """

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
        if isinstance(value, bool):
            raise ValueError("usefulness must be numeric, not boolean")
        usefulness = float(value)
        if not math.isfinite(usefulness):
            raise ValueError("usefulness must be finite")
        return max(0.0, min(1.0, usefulness))

    @staticmethod
    def _validate_loaded_usefulness(value: float) -> float:
        if isinstance(value, bool):
            raise ValueError("usefulness must be numeric, not boolean")
        usefulness = float(value)
        if not math.isfinite(usefulness):
            raise ValueError("usefulness must be finite")
        if not 0.0 <= usefulness <= 1.0:
            raise ValueError("stored usefulness must be between 0 and 1")
        return usefulness

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
        existing = self.entries()
        previous_hash = next(
            (
                entry.entry_hash
                for entry in reversed(existing)
                if entry.entry_hash is not None
            ),
            None,
        )
        unsigned = MemoryEntry(
            kind=self._validated_text(kind, "kind"),
            content=self._validated_text(content, "content"),
            usefulness=self._validated_usefulness(usefulness),
            created_at=time.time(),
            previous_hash=previous_hash,
            entry_hash=None,
        )
        entry = MemoryEntry(
            **{
                **asdict(unsigned),
                "entry_hash": memory_entry_hash(unsigned),
            }
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return entry

    def entries(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []

        output: list[MemoryEntry] = []
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
                entry = MemoryEntry(**data)
                self._validated_text(entry.kind, "kind")
                self._validated_text(entry.content, "content")
                self._validate_loaded_usefulness(entry.usefulness)
                created_at = float(entry.created_at)
                if not math.isfinite(created_at) or created_at < 0.0:
                    raise ValueError("created_at must be finite and non-negative")

                if entry.entry_hash is None:
                    if entry.previous_hash is not None:
                        raise ValueError("unchained entry has previous_hash")
                    if chained_started:
                        raise ValueError("unchained entry follows chained entries")
                else:
                    chained_started = True
                    if not is_sha256(entry.entry_hash):
                        raise ValueError("malformed entry hash")
                    if entry.previous_hash != previous_hash:
                        raise ValueError("hash-chain predecessor mismatch")
                    if memory_entry_hash(entry) != entry.entry_hash:
                        raise ValueError("entry hash mismatch")
                    previous_hash = entry.entry_hash
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
        selected = sorted(
            self.entries(),
            key=lambda entry: entry.usefulness,
            reverse=True,
        )[:max_entries]
        entries = rechain_entries(selected)

        temp_path = self.path.with_name(f".{self.path.name}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        temp_path.replace(self.path)


def rechain_entries(entries: list[MemoryEntry]) -> list[MemoryEntry]:
    """Authorize a rewritten/pruned memory ordering with a fresh hash chain."""
    output: list[MemoryEntry] = []
    previous_hash: str | None = None
    for entry in entries:
        unsigned = MemoryEntry(
            kind=entry.kind,
            content=entry.content,
            usefulness=KnowledgeBank._validate_loaded_usefulness(entry.usefulness),
            created_at=float(entry.created_at),
            previous_hash=previous_hash,
            entry_hash=None,
        )
        chained = MemoryEntry(
            **{
                **asdict(unsigned),
                "entry_hash": memory_entry_hash(unsigned),
            }
        )
        output.append(chained)
        previous_hash = chained.entry_hash
    return output


def memory_entry_hash(entry: MemoryEntry) -> str:
    payload = asdict(entry)
    payload.pop("entry_hash", None)
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
