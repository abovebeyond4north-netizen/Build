from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


FROZEN_COMPONENTS = (
    "protected_evaluator",
    "hidden_world_generator",
    "causal_control_genesis9",
    "planner",
    "memory",
    "promotion_rules",
    "train_eval_split",
)
MUTABLE_COMPONENTS = ("representation_encoder",)
REQUIRED_COMPONENTS = FROZEN_COMPONENTS + MUTABLE_COMPONENTS


class ArchitectureViolation(RuntimeError):
    pass


@dataclass(frozen=True)
class ArchitectureSnapshot:
    components: Mapping[str, str]
    label: str

    def __post_init__(self) -> None:
        missing = [name for name in REQUIRED_COMPONENTS if name not in self.components]
        extra = [name for name in self.components if name not in REQUIRED_COMPONENTS]
        if missing or extra:
            raise ValueError(f"invalid snapshot: missing={missing}, extra={extra}")

    @property
    def digest(self) -> str:
        canonical = json.dumps(dict(sorted(self.components.items())), separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def snapshot_from_payloads(payloads: Mapping[str, bytes], *, label: str) -> ArchitectureSnapshot:
    missing = [name for name in REQUIRED_COMPONENTS if name not in payloads]
    extra = [name for name in payloads if name not in REQUIRED_COMPONENTS]
    if missing or extra:
        raise ValueError(f"invalid payload set: missing={missing}, extra={extra}")
    return ArchitectureSnapshot(
        components={name: _sha(payloads[name]) for name in REQUIRED_COMPONENTS},
        label=label,
    )


def assert_genesis13_architecture(before: ArchitectureSnapshot, after: ArchitectureSnapshot) -> None:
    changed = [
        name
        for name in FROZEN_COMPONENTS
        if before.components[name] != after.components[name]
    ]
    if changed:
        raise ArchitectureViolation(
            "Genesis-13 changed frozen components: " + ", ".join(changed)
        )
    if before.components["representation_encoder"] == after.components["representation_encoder"]:
        raise ArchitectureViolation("representation encoder did not change")


@dataclass
class RepresentationRegistry:
    active_version: str
    active_validation_error: float

    def propose(
        self,
        *,
        version: str,
        validation_error: float,
        minimum_relative_improvement: float = 0.05,
    ) -> bool:
        if validation_error < 0:
            raise ValueError("validation_error must be non-negative")
        threshold = self.active_validation_error * (1.0 - minimum_relative_improvement)
        if validation_error <= threshold:
            self.active_version = version
            self.active_validation_error = validation_error
            return True
        return False
