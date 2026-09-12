from __future__ import annotations

import hashlib
import json
import keyword
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


SPLITS = ("train", "validation", "holdout")


@dataclass(frozen=True)
class CapabilityCase:
    name: str
    split: str
    args: tuple[Any, ...]
    expected: Any

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("case name must be a non-empty string")
        if self.split not in SPLITS:
            raise ValueError(f"case split must be one of {SPLITS}")
        if not isinstance(self.args, tuple):
            raise TypeError("case args must be a tuple")
        ensure_json_value(self.args, "case args")
        ensure_json_value(self.expected, "case expected value")


@dataclass(frozen=True)
class CapabilityThresholds:
    train: float = 1.0
    validation: float = 1.0
    holdout: float = 1.0
    min_gain: float = 0.05

    def __post_init__(self) -> None:
        for name in ("train", "validation", "holdout"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} threshold must be finite and between 0 and 1")
        if not math.isfinite(self.min_gain) or not 0.0 <= self.min_gain <= 1.0:
            raise ValueError("min_gain must be finite and between 0 and 1")


@dataclass(frozen=True)
class CapabilityEvidencePolicy:
    """Minimum evidence and bounded adaptive validation reuse.

    Defaults preserve the historical custom-spec contract: one case per split and
    no additional validation-trial cap. Built-in objectives can opt into stronger
    evidence requirements without breaking explicit user-provided specifications.
    """

    min_train_cases: int = 1
    min_validation_cases: int = 1
    min_holdout_cases: int = 1
    max_validation_trials_per_case: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "min_train_cases",
            "min_validation_cases",
            "min_holdout_cases",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_validation_trials_per_case is not None:
            value = self.max_validation_trials_per_case
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(
                    "max_validation_trials_per_case must be a positive integer or null"
                )


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    description: str
    entrypoint: str
    cases: tuple[CapabilityCase, ...]
    thresholds: CapabilityThresholds = CapabilityThresholds()
    evidence: CapabilityEvidencePolicy = CapabilityEvidencePolicy()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", self.name
        ):
            raise ValueError("capability name must be 1-64 safe identifier characters")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("capability description must be non-empty")
        if (
            not isinstance(self.entrypoint, str)
            or not self.entrypoint.isidentifier()
            or keyword.iskeyword(self.entrypoint)
            or self.entrypoint.startswith("_")
        ):
            raise ValueError("entrypoint must be a public Python identifier")
        if not isinstance(self.cases, tuple) or not self.cases:
            raise ValueError("capability must define cases")
        if not isinstance(self.thresholds, CapabilityThresholds):
            raise TypeError("thresholds must be CapabilityThresholds")
        if not isinstance(self.evidence, CapabilityEvidencePolicy):
            raise TypeError("evidence must be CapabilityEvidencePolicy")

        names = [case.name for case in self.cases]
        if len(names) != len(set(names)):
            raise ValueError("case names must be unique")
        split_counts = {split: 0 for split in SPLITS}
        arities: set[int] = set()
        for case in self.cases:
            if not isinstance(case, CapabilityCase):
                raise TypeError("cases must contain CapabilityCase values")
            split_counts[case.split] += 1
            arities.add(len(case.args))
        if any(count == 0 for count in split_counts.values()):
            raise ValueError(
                "capability requires non-empty train, validation, and holdout splits"
            )
        required_counts = {
            "train": self.evidence.min_train_cases,
            "validation": self.evidence.min_validation_cases,
            "holdout": self.evidence.min_holdout_cases,
        }
        for split, minimum in required_counts.items():
            if split_counts[split] < minimum:
                raise ValueError(
                    f"capability requires at least {minimum} {split} cases "
                    f"under its evidence policy; found {split_counts[split]}"
                )
        if len(arities) != 1:
            raise ValueError("all capability cases must use the same positional arity")

    @property
    def arity(self) -> int:
        return len(self.cases[0].args)

    def cases_for(self, split: str) -> tuple[CapabilityCase, ...]:
        if split not in SPLITS:
            raise ValueError(f"unknown split: {split}")
        return tuple(case for case in self.cases if case.split == split)

    def validation_trial_limit(self) -> int | None:
        """Return the maximum adaptive validation probes allowed for this spec."""
        per_case = self.evidence.max_validation_trials_per_case
        if per_case is None:
            return None
        return len(self.cases_for("validation")) * per_case

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilitySpec":
        if not isinstance(data, dict):
            raise TypeError("capability specification must be an object")
        raw_cases = data.get("cases")
        if not isinstance(raw_cases, list):
            raise ValueError("cases must be a list")

        cases: list[CapabilityCase] = []
        for index, item in enumerate(raw_cases):
            if not isinstance(item, dict):
                raise ValueError(f"case {index} must be an object")
            try:
                cases.append(
                    CapabilityCase(
                        name=item["name"],
                        split=item["split"],
                        args=tuple(item.get("args", [])),
                        expected=item.get("expected"),
                    )
                )
            except KeyError as exc:
                raise ValueError(
                    f"case {index} is missing required field: {exc.args[0]}"
                ) from exc

        raw_thresholds = data.get("thresholds", {})
        if not isinstance(raw_thresholds, dict):
            raise ValueError("thresholds must be an object")
        thresholds = CapabilityThresholds(
            train=float(raw_thresholds.get("train", 1.0)),
            validation=float(raw_thresholds.get("validation", 1.0)),
            holdout=float(raw_thresholds.get("holdout", 1.0)),
            min_gain=float(raw_thresholds.get("min_gain", 0.05)),
        )

        raw_evidence = data.get("evidence", {})
        if not isinstance(raw_evidence, dict):
            raise ValueError("evidence must be an object")
        evidence = CapabilityEvidencePolicy(
            min_train_cases=raw_evidence.get("min_train_cases", 1),
            min_validation_cases=raw_evidence.get("min_validation_cases", 1),
            min_holdout_cases=raw_evidence.get("min_holdout_cases", 1),
            max_validation_trials_per_case=raw_evidence.get(
                "max_validation_trials_per_case"
            ),
        )

        try:
            name = data["name"]
            description = data["description"]
        except KeyError as exc:
            raise ValueError(
                f"capability is missing required field: {exc.args[0]}"
            ) from exc
        return cls(
            name=name,
            description=description,
            entrypoint=data.get("entrypoint", "solve"),
            cases=tuple(cases),
            thresholds=thresholds,
            evidence=evidence,
        )

    @classmethod
    def load(cls, path: Path) -> "CapabilitySpec":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid capability JSON: {exc}") from exc
        except OSError as exc:
            raise ValueError(
                f"unable to read capability specification: {exc}"
            ) from exc
        return cls.from_dict(data)


@dataclass(frozen=True)
class TrainingView:
    name: str
    description: str
    entrypoint: str
    arity: int
    cases: tuple[CapabilityCase, ...]


@dataclass(frozen=True)
class SkillCandidate:
    source: str
    strategy: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("candidate source must be non-empty")
        if not isinstance(self.strategy, str) or not self.strategy.strip():
            raise ValueError("candidate strategy must be non-empty")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.source.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SuiteScore:
    passed: int
    total: int
    elapsed_seconds: float
    errors: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.passed < 0 or self.total < 0 or self.passed > self.total:
            raise ValueError("suite counts are inconsistent")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be finite and non-negative")

    @property
    def correctness(self) -> float:
        return self.passed / self.total if self.total else 0.0


@dataclass(frozen=True)
class AcquisitionTask:
    title: str
    instruction: str
    priority: float


@dataclass(frozen=True)
class AcquisitionReport:
    capability: str
    description: str
    holdout_digest: str
    status: str
    promoted: bool
    baseline_digest: str
    baseline_score: float
    finalist_digest: str | None
    final_score: float | None
    train_score: float | None
    validation_score: float | None
    holdout_score: float | None
    candidates_generated: int
    candidates_trained: int
    candidates_validated: int
    holdout_evaluations: int
    tasks: tuple[AcquisitionTask, ...]
    installed_path: str | None
    report_path: str
    created_at: float


class CandidateGenerator(Protocol):
    def generate(
        self,
        view: TrainingView,
        *,
        prior_source: str | None,
        max_candidates: int,
    ) -> list[SkillCandidate]: ...


def render_function(entrypoint: str, arity: int, expression: str) -> str:
    args = ", ".join(f"x{i}" for i in range(arity))
    return f"def {entrypoint}({args}):\n    return {expression}\n"


def ensure_json_value(value: Any, label: str) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{label} must be JSON-serializable without NaN/Infinity"
        ) from exc
