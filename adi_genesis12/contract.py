from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


FROZEN_COMPONENTS = (
    "base_model",
    "specialist_model",
    "broad_model",
    "evaluator",
    "promotion",
    "memory",
    "distributions",
)
MUTABLE_COMPONENTS = ("planner",)
REQUIRED_COMPONENTS = FROZEN_COMPONENTS + MUTABLE_COMPONENTS


class ArchitectureViolation(RuntimeError):
    """Raised when a Genesis-12 candidate changes a frozen Genesis-9 component."""


@dataclass(frozen=True)
class ArchitectureSnapshot:
    """Content fingerprints for the parts of the Genesis experiment architecture."""

    components: Mapping[str, str]
    label: str = "genesis-9-compatible"

    def __post_init__(self) -> None:
        missing = [name for name in REQUIRED_COMPONENTS if name not in self.components]
        extra = [name for name in self.components if name not in REQUIRED_COMPONENTS]
        if missing or extra:
            raise ValueError(f"invalid architecture snapshot: missing={missing}, extra={extra}")
        invalid = [
            name
            for name, digest in self.components.items()
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)
        ]
        if invalid:
            raise ValueError(f"component fingerprints must be lowercase SHA-256 hex: {invalid}")

    @property
    def digest(self) -> str:
        canonical = json.dumps(dict(sorted(self.components.items())), separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def snapshot_from_payloads(payloads: Mapping[str, bytes], *, label: str) -> ArchitectureSnapshot:
    missing = [name for name in REQUIRED_COMPONENTS if name not in payloads]
    extra = [name for name in payloads if name not in REQUIRED_COMPONENTS]
    if missing or extra:
        raise ValueError(f"invalid component payload set: missing={missing}, extra={extra}")
    return ArchitectureSnapshot(
        components={name: fingerprint_bytes(payloads[name]) for name in REQUIRED_COMPONENTS},
        label=label,
    )


def assert_genesis12_architecture(before: ArchitectureSnapshot, after: ArchitectureSnapshot) -> None:
    """Require Genesis-12 to differ from Genesis-9 only in intervention planning."""

    changed_frozen = [
        name
        for name in FROZEN_COMPONENTS
        if before.components[name] != after.components[name]
    ]
    if changed_frozen:
        raise ArchitectureViolation(
            "Genesis-12 changed frozen components: " + ", ".join(changed_frozen)
        )

    if before.components["planner"] == after.components["planner"]:
        raise ArchitectureViolation("Genesis-12 planner fingerprint did not change")
