"""ADI Genesis-15 uncertainty-gated partially observed world-model experiment."""

from .contract import (
    ArchitectureSnapshot,
    ArchitectureViolation,
    assert_genesis15_architecture,
    snapshot_from_payloads,
)

__all__ = [
    "ArchitectureSnapshot",
    "ArchitectureViolation",
    "assert_genesis15_architecture",
    "snapshot_from_payloads",
]
