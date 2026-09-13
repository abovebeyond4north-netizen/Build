from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PatchDevelopmentObservation:
    search_digest: str
    proposal_digest: str
    focus: str
    knob: str
    direction: int
    step: float
    aggregate_delta: float
    passed: bool
    reason: str
    created_at: float
    previous_hash: str | None = None
    record_hash: str | None = None


class PatchSearchMemory:
    """Tamper-evident memory for public/development patch-search evidence only."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "patch_search_development.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[PatchDevelopmentObservation]:
        if not self.path.exists():
            return []
        output: list[PatchDevelopmentObservation] = []
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
                    raise ValueError("observation must be an object")
                record = PatchDevelopmentObservation(**data)
                validate_observation(record)
                if record.previous_hash != previous_hash:
                    raise ValueError("hash-chain predecessor mismatch")
                if observation_hash(record) != record.record_hash:
                    raise ValueError("record hash mismatch")
                previous_hash = record.record_hash
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid patch-search observation on line {line_number}: {exc}"
                ) from exc
            output.append(record)
        return output

    def record(
        self,
        *,
        search_digest: str,
        proposal_digest: str,
        focus: str,
        knob: str,
        direction: int,
        step: float,
        aggregate_delta: float,
        passed: bool,
        reason: str,
    ) -> PatchDevelopmentObservation:
        candidate = PatchDevelopmentObservation(
            search_digest=search_digest,
            proposal_digest=proposal_digest,
            focus=focus,
            knob=knob,
            direction=direction,
            step=step,
            aggregate_delta=aggregate_delta,
            passed=passed,
            reason=reason,
            created_at=time.time(),
        )
        validate_observation(candidate, require_hashes=False)
        existing = self.records()
        matches = [
            record
            for record in existing
            if record.search_digest == search_digest
            and record.proposal_digest == proposal_digest
        ]
        if matches:
            previous = matches[0]
            if observation_semantics(previous) != observation_semantics(candidate):
                raise ValueError("conflicting development observation for search/proposal")
            return previous

        previous_hash = existing[-1].record_hash if existing else None
        unsigned = PatchDevelopmentObservation(
            **{
                **asdict(candidate),
                "previous_hash": previous_hash,
                "record_hash": None,
            }
        )
        record = PatchDevelopmentObservation(
            **{
                **asdict(unsigned),
                "record_hash": observation_hash(unsigned),
            }
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
        return record

    def priority(self, focus: str, knob: str, direction: int) -> float:
        """UCB-like public-evidence priority; unseen adjustments are explored first."""
        if direction not in {-1, 1}:
            raise ValueError("direction must be -1 or 1")
        all_records = self.records()
        records = [
            record
            for record in all_records
            if record.focus == focus
            and record.knob == knob
            and record.direction == direction
        ]
        if not records:
            return 10.0
        total_focus = sum(1 for record in all_records if record.focus == focus)
        mean = sum(record.aggregate_delta for record in records) / len(records)
        exploration = 0.05 * math.sqrt(
            math.log(max(2, total_focus + 1)) / len(records)
        )
        pass_bonus = 0.01 * (
            sum(1 for record in records if record.passed) / len(records)
        )
        return mean + exploration + pass_bonus


def validate_observation(
    record: PatchDevelopmentObservation,
    *,
    require_hashes: bool = True,
) -> None:
    require_sha256(record.search_digest, "search_digest")
    require_sha256(record.proposal_digest, "proposal_digest")
    if not isinstance(record.focus, str) or not record.focus.strip():
        raise ValueError("focus must be non-empty")
    if not isinstance(record.knob, str) or not record.knob.strip():
        raise ValueError("knob must be non-empty")
    if record.direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    if (
        isinstance(record.step, bool)
        or not isinstance(record.step, (int, float))
        or not math.isfinite(float(record.step))
        or not 0.0 < float(record.step) <= 1.0
    ):
        raise ValueError("step must be finite and in (0, 1]")
    if (
        isinstance(record.aggregate_delta, bool)
        or not isinstance(record.aggregate_delta, (int, float))
        or not math.isfinite(float(record.aggregate_delta))
        or not -1.0 <= float(record.aggregate_delta) <= 1.0
    ):
        raise ValueError("aggregate_delta must be finite and between -1 and 1")
    if not isinstance(record.passed, bool):
        raise ValueError("passed must be boolean")
    if not isinstance(record.reason, str) or not record.reason.strip():
        raise ValueError("reason must be non-empty")
    if not math.isfinite(float(record.created_at)) or float(record.created_at) <= 0:
        raise ValueError("created_at must be finite and positive")
    if require_hashes:
        if record.previous_hash is not None:
            require_sha256(record.previous_hash, "previous_hash")
        require_sha256(record.record_hash, "record_hash")


def observation_hash(record: PatchDevelopmentObservation) -> str:
    payload = asdict(record)
    payload.pop("record_hash", None)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def observation_semantics(record: PatchDevelopmentObservation) -> tuple[object, ...]:
    return (
        record.search_digest,
        record.proposal_digest,
        record.focus,
        record.knob,
        record.direction,
        float(record.step),
        float(record.aggregate_delta),
        record.passed,
        record.reason,
    )


def require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    if any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value
