from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


FROZEN_COMPONENTS = (
    "protected_evaluator",
    "hidden_world_generator",
    "representation_genesis13",
    "world_model_genesis14",
    "causal_control_genesis9",
    "memory",
    "promotion_rules",
    "train_eval_split",
    "evaluation_controls",
)
MUTABLE_COMPONENTS = (
    "belief_filter",
    "uncertainty_detector",
    "gated_residual_adapter",
)
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
            raise ValueError(
                f"invalid snapshot: missing={missing}, extra={extra}"
            )

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            dict(sorted(self.components.items())),
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def snapshot_from_payloads(
    payloads: Mapping[str, bytes],
    *,
    label: str,
) -> ArchitectureSnapshot:
    missing = [name for name in REQUIRED_COMPONENTS if name not in payloads]
    extra = [name for name in payloads if name not in REQUIRED_COMPONENTS]
    if missing or extra:
        raise ValueError(
            f"invalid payload set: missing={missing}, extra={extra}"
        )
    return ArchitectureSnapshot(
        components={name: _sha(payloads[name]) for name in REQUIRED_COMPONENTS},
        label=label,
    )


def assert_genesis15_architecture(
    before: ArchitectureSnapshot,
    after: ArchitectureSnapshot,
) -> None:
    changed_frozen = [
        name
        for name in FROZEN_COMPONENTS
        if before.components[name] != after.components[name]
    ]
    if changed_frozen:
        raise ArchitectureViolation(
            "Genesis-15 changed frozen components: "
            + ", ".join(changed_frozen)
        )

    changed_mutable = [
        name
        for name in MUTABLE_COMPONENTS
        if before.components[name] != after.components[name]
    ]
    if not changed_mutable:
        raise ArchitectureViolation(
            "Genesis-15 changed none of its permitted experimental components"
        )
