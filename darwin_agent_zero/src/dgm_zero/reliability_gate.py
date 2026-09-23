from __future__ import annotations

import hashlib
import json
import math
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .capability_model import CapabilityCase, SuiteScore


RELIABILITY_LEDGER_VERSION = 1
DEFAULT_REPLAY_SEEDS = (104729, 130363, 155921, 196613, 262147)


@dataclass(frozen=True)
class ReliabilityTrial:
    seed: int
    case_order_digest: str
    baseline_score: float
    finalist_score: float
    delta: float


@dataclass(frozen=True)
class ReliabilityDecision:
    ledger_version: int
    capability: str
    baseline_digest: str
    finalist_digest: str
    validation_digest: str
    replay_seeds: tuple[int, ...]
    minimum_gain: float
    trials: tuple[ReliabilityTrial, ...]
    baseline_stable: bool
    finalist_stable: bool
    worst_delta: float
    mean_delta: float
    passed: bool
    reason: str
    created_at: float
    previous_hash: str | None = None
    record_hash: str | None = None


class ReliabilityLedger:
    """Tamper-evident evidence ledger for protected promotion decisions."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "reliability_gate.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[ReliabilityDecision]:
        if not self.path.exists():
            return []
        output: list[ReliabilityDecision] = []
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
                if data.get("ledger_version") != RELIABILITY_LEDGER_VERSION:
                    raise ValueError("unsupported ledger version")
                raw_trials = data.get("trials")
                if not isinstance(raw_trials, list) or not raw_trials:
                    raise ValueError("trials must be a non-empty list")
                trials = tuple(ReliabilityTrial(**item) for item in raw_trials)
                raw_seeds = data.get("replay_seeds")
                if not isinstance(raw_seeds, list):
                    raise ValueError("replay_seeds must be a list")
                data["replay_seeds"] = tuple(raw_seeds)
                data["trials"] = trials
                record = ReliabilityDecision(**data)
                validate_decision(record)
                if record.previous_hash != previous_hash:
                    raise ValueError("hash-chain predecessor mismatch")
                if reliability_record_hash(record) != record.record_hash:
                    raise ValueError("record hash mismatch")
                previous_hash = record.record_hash
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid reliability ledger on line {line_number}: {exc}"
                ) from exc
            output.append(record)
        return output

    def find(
        self,
        *,
        capability: str,
        baseline_digest: str,
        finalist_digest: str,
        validation_digest: str,
        replay_seeds: tuple[int, ...],
        minimum_gain: float,
    ) -> ReliabilityDecision | None:
        for record in reversed(self.records()):
            if (
                record.capability == capability
                and record.baseline_digest == baseline_digest
                and record.finalist_digest == finalist_digest
                and record.validation_digest == validation_digest
                and record.replay_seeds == replay_seeds
                and abs(record.minimum_gain - minimum_gain) <= 1e-12
            ):
                return record
        return None

    def append(self, decision: ReliabilityDecision) -> ReliabilityDecision:
        existing = self.records()
        previous_hash = existing[-1].record_hash if existing else None
        unsigned = ReliabilityDecision(
            **{
                **asdict(decision),
                "trials": decision.trials,
                "previous_hash": previous_hash,
                "record_hash": None,
            }
        )
        sealed = ReliabilityDecision(
            **{
                **asdict(unsigned),
                "trials": unsigned.trials,
                "record_hash": reliability_record_hash(unsigned),
            }
        )
        validate_decision(sealed)
        rows = existing + [sealed]
        atomic_write_text(
            self.path,
            "".join(json.dumps(asdict(row), sort_keys=True) + "\n" for row in rows),
        )
        return sealed


class IndependentReliabilityGate:
    """Protected promotion gate using paired replay and whole-change ablation.

    The baseline is the intervention control: replacing the finalist with the
    installed baseline ablates the proposed capability change. Both versions are
    evaluated on the same validation cases under several deterministic order
    permutations. This measures the causal contribution of the whole proposed
    change and catches order-sensitive behavior without exposing holdout data.
    """

    def __init__(
        self,
        workspace: Path,
        *,
        replay_seeds: tuple[int, ...] = DEFAULT_REPLAY_SEEDS,
    ) -> None:
        self.replay_seeds = validate_replay_seeds(replay_seeds)
        self.ledger = ReliabilityLedger(workspace)

    def evaluate(
        self,
        *,
        capability: str,
        baseline_source: str,
        finalist_source: str,
        entrypoint: str,
        validation_cases: tuple[CapabilityCase, ...],
        sandbox: Any,
        minimum_gain: float,
    ) -> ReliabilityDecision:
        if not isinstance(capability, str) or not capability.strip():
            raise ValueError("capability must be a non-empty string")
        if not isinstance(baseline_source, str) or not baseline_source.strip():
            raise ValueError("baseline_source must be non-empty")
        if not isinstance(finalist_source, str) or not finalist_source.strip():
            raise ValueError("finalist_source must be non-empty")
        if not validation_cases:
            raise ValueError("validation_cases must be non-empty")
        if (
            isinstance(minimum_gain, bool)
            or not isinstance(minimum_gain, (int, float))
            or not math.isfinite(float(minimum_gain))
            or not 0.0 <= float(minimum_gain) <= 1.0
        ):
            raise ValueError("minimum_gain must be finite and between 0 and 1")

        baseline_digest = source_digest(baseline_source)
        finalist_digest = source_digest(finalist_source)
        validation_digest = suite_digest(validation_cases)
        required_gain = float(minimum_gain)

        cached = self.ledger.find(
            capability=capability,
            baseline_digest=baseline_digest,
            finalist_digest=finalist_digest,
            validation_digest=validation_digest,
            replay_seeds=self.replay_seeds,
            minimum_gain=required_gain,
        )
        if cached is not None:
            return cached

        trials: list[ReliabilityTrial] = []
        for seed in self.replay_seeds:
            ordered = list(validation_cases)
            random.Random(seed).shuffle(ordered)
            ordered_cases = tuple(ordered)
            baseline_score = require_suite_score(
                sandbox.evaluate(baseline_source, entrypoint, ordered_cases),
                "baseline",
            ).correctness
            finalist_score = require_suite_score(
                sandbox.evaluate(finalist_source, entrypoint, ordered_cases),
                "finalist",
            ).correctness
            trials.append(
                ReliabilityTrial(
                    seed=seed,
                    case_order_digest=case_order_digest(ordered_cases),
                    baseline_score=baseline_score,
                    finalist_score=finalist_score,
                    delta=finalist_score - baseline_score,
                )
            )

        baseline_scores = tuple(trial.baseline_score for trial in trials)
        finalist_scores = tuple(trial.finalist_score for trial in trials)
        baseline_stable = score_stable(baseline_scores)
        finalist_stable = score_stable(finalist_scores)
        deltas = tuple(trial.delta for trial in trials)
        worst_delta = min(deltas)
        mean_delta = sum(deltas) / len(deltas)

        if baseline_digest == finalist_digest:
            passed = False
            reason = "identical_to_baseline"
        elif not baseline_stable or not finalist_stable:
            passed = False
            reason = "order_instability"
        elif worst_delta + 1e-12 < required_gain:
            passed = False
            reason = "insufficient_ablation_delta"
        else:
            passed = True
            reason = "passed"

        decision = ReliabilityDecision(
            ledger_version=RELIABILITY_LEDGER_VERSION,
            capability=capability,
            baseline_digest=baseline_digest,
            finalist_digest=finalist_digest,
            validation_digest=validation_digest,
            replay_seeds=self.replay_seeds,
            minimum_gain=required_gain,
            trials=tuple(trials),
            baseline_stable=baseline_stable,
            finalist_stable=finalist_stable,
            worst_delta=worst_delta,
            mean_delta=mean_delta,
            passed=passed,
            reason=reason,
            created_at=time.time(),
        )
        return self.ledger.append(decision)


def suite_digest(cases: Iterable[CapabilityCase]) -> str:
    canonical = sorted(
        (
            {
                "name": case.name,
                "split": case.split,
                "args": list(case.args),
                "expected": case.expected,
            }
            for case in cases
        ),
        key=lambda item: item["name"],
    )
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def case_order_digest(cases: Iterable[CapabilityCase]) -> str:
    encoded = json.dumps(
        [case.name for case in cases],
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def score_stable(values: tuple[float, ...]) -> bool:
    if not values:
        return False
    return max(values) - min(values) <= 1e-12


def require_suite_score(value: object, label: str) -> SuiteScore:
    if not isinstance(value, SuiteScore):
        raise TypeError(f"{label} evaluator must return SuiteScore")
    return value


def validate_replay_seeds(seeds: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(seeds, tuple) or len(seeds) < 2:
        raise ValueError("replay_seeds must contain at least two seeds")
    clean: list[int] = []
    for seed in seeds:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("replay seeds must be non-negative integers")
        clean.append(seed)
    if len(set(clean)) != len(clean):
        raise ValueError("replay seeds must be unique")
    return tuple(clean)


def validate_decision(record: ReliabilityDecision) -> None:
    if record.ledger_version != RELIABILITY_LEDGER_VERSION:
        raise ValueError("unsupported ledger version")
    for name, digest in (
        ("baseline_digest", record.baseline_digest),
        ("finalist_digest", record.finalist_digest),
        ("validation_digest", record.validation_digest),
    ):
        require_sha256(digest, name)
    validate_replay_seeds(record.replay_seeds)
    if len(record.trials) != len(record.replay_seeds):
        raise ValueError("trial count must match replay seed count")
    if tuple(trial.seed for trial in record.trials) != record.replay_seeds:
        raise ValueError("trial seeds must match replay seeds")
    for trial in record.trials:
        require_sha256(trial.case_order_digest, "case_order_digest")
        for value in (
            trial.baseline_score,
            trial.finalist_score,
            trial.delta,
        ):
            if not math.isfinite(float(value)):
                raise ValueError("trial scores must be finite")
        if not 0.0 <= trial.baseline_score <= 1.0:
            raise ValueError("baseline score must be between 0 and 1")
        if not 0.0 <= trial.finalist_score <= 1.0:
            raise ValueError("finalist score must be between 0 and 1")
        if not -1.0 <= trial.delta <= 1.0:
            raise ValueError("trial delta must be between -1 and 1")
    if not math.isfinite(record.minimum_gain) or not 0.0 <= record.minimum_gain <= 1.0:
        raise ValueError("minimum_gain must be between 0 and 1")
    if not math.isfinite(record.worst_delta) or not -1.0 <= record.worst_delta <= 1.0:
        raise ValueError("worst_delta must be between -1 and 1")
    if not math.isfinite(record.mean_delta) or not -1.0 <= record.mean_delta <= 1.0:
        raise ValueError("mean_delta must be between -1 and 1")
    if not isinstance(record.reason, str) or not record.reason:
        raise ValueError("reason must be non-empty")
    if not math.isfinite(record.created_at) or record.created_at <= 0:
        raise ValueError("created_at must be finite and positive")
    if record.previous_hash is not None:
        require_sha256(record.previous_hash, "previous_hash")
    if record.record_hash is not None:
        require_sha256(record.record_hash, "record_hash")


def reliability_record_hash(record: ReliabilityDecision) -> str:
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


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
