from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PatchCertificationReservation:
    proposal_digest: str
    replay_seeds: tuple[int, ...]
    created_at: float
    previous_hash: str | None = None
    record_hash: str | None = None


class PatchCertificationLedger:
    """Tamper-evident one-shot reservations for fresh patch replay evidence.

    A proposal is reserved before fresh replay starts. Any reservation consumes
    that proposal's fresh certification opportunity, even if execution later
    crashes or times out. This prevents repeated replay attempts from turning the
    fresh evidence into adaptive tuning data.
    """

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "patch_replay_certifications.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[PatchCertificationReservation]:
        if not self.path.exists():
            return []
        output: list[PatchCertificationReservation] = []
        previous_hash: str | None = None
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise ValueError("record must be an object")
                raw_seeds = data.get("replay_seeds")
                if isinstance(raw_seeds, list):
                    data["replay_seeds"] = tuple(raw_seeds)
                record = PatchCertificationReservation(**data)
                self._validate_record(record)
                if record.previous_hash != previous_hash:
                    raise ValueError("hash-chain predecessor mismatch")
                if certification_record_hash(record) != record.record_hash:
                    raise ValueError("record hash mismatch")
                previous_hash = record.record_hash
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid patch certification record on line {line_number}: {exc}"
                ) from exc
            output.append(record)
        return output

    def is_consumed(self, proposal_digest: str) -> bool:
        require_sha256(proposal_digest, "proposal_digest")
        return any(
            record.proposal_digest == proposal_digest for record in self.records()
        )

    def reserve(
        self,
        proposal_digest: str,
        replay_seeds: tuple[int, ...],
    ) -> PatchCertificationReservation:
        require_sha256(proposal_digest, "proposal_digest")
        seeds = validate_replay_seeds(replay_seeds)
        existing = self.records()
        if any(record.proposal_digest == proposal_digest for record in existing):
            raise ValueError(
                "fresh replay certification already consumed for proposal: "
                f"{proposal_digest}"
            )
        previous_hash = existing[-1].record_hash if existing else None
        unsigned = PatchCertificationReservation(
            proposal_digest=proposal_digest,
            replay_seeds=seeds,
            created_at=time.time(),
            previous_hash=previous_hash,
            record_hash=None,
        )
        record = PatchCertificationReservation(
            **{
                **asdict(unsigned),
                "record_hash": certification_record_hash(unsigned),
            }
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
        return record

    @staticmethod
    def _validate_record(record: PatchCertificationReservation) -> None:
        require_sha256(record.proposal_digest, "proposal_digest")
        validate_replay_seeds(record.replay_seeds)
        if not math.isfinite(float(record.created_at)) or float(record.created_at) <= 0:
            raise ValueError("created_at must be finite and positive")
        if record.previous_hash is not None:
            require_sha256(record.previous_hash, "previous_hash")
        require_sha256(record.record_hash, "record_hash")


def validate_replay_seeds(seeds: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(seeds, tuple) or not seeds:
        raise ValueError("replay_seeds must be a non-empty tuple")
    clean: list[int] = []
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("replay seeds must be integers")
        if seed < 0:
            raise ValueError("replay seeds must be non-negative")
        clean.append(seed)
    if len(set(clean)) != len(clean):
        raise ValueError("replay seeds must be unique")
    return tuple(clean)


def certification_record_hash(record: PatchCertificationReservation) -> str:
    payload = asdict(record)
    payload.pop("record_hash", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value
