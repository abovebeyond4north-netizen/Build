"""Harmless defensive simulator for incident-response training.

This module models a safe tabletop response timeline. It does not touch the
network, system settings, credentials, external files, processes, or services.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable
import json


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ResponseStep:
    phase: str
    objective: str
    severity: Severity
    safe_action: str
    evidence_to_collect: tuple[str, ...]


def build_defensive_timeline() -> list[ResponseStep]:
    """Return a safe incident-response timeline."""
    return [
        ResponseStep(
            phase="intake",
            objective="Preserve a suspicious archive without running it",
            severity=Severity.HIGH,
            safe_action="Store the sample in an isolated evidence location and record hashes.",
            evidence_to_collect=("filename", "sha256", "source", "timestamp"),
        ),
        ResponseStep(
            phase="static_review",
            objective="Review metadata and text safely",
            severity=Severity.CRITICAL,
            safe_action="Review names, documentation, imports, and metadata without execution.",
            evidence_to_collect=("imports", "function names", "risk notes", "install notes"),
        ),
        ResponseStep(
            phase="containment",
            objective="Prevent unsafe material from entering public code paths",
            severity=Severity.CRITICAL,
            safe_action="Publish only reviewed educational material and keep private evidence offline.",
            evidence_to_collect=("repository policy", "allowlist", "review record"),
        ),
        ResponseStep(
            phase="training_conversion",
            objective="Create a harmless learning exercise",
            severity=Severity.MEDIUM,
            safe_action="Represent response phases as static records for tabletop practice.",
            evidence_to_collect=("timeline", "handling notes", "test results"),
        ),
        ResponseStep(
            phase="closure",
            objective="Document lessons and safe publication choices",
            severity=Severity.LOW,
            safe_action="Publish notes, manifest, and simulator while excluding private evidence.",
            evidence_to_collect=("manifest", "review notes", "safe repo path"),
        ),
    ]


def summarize_timeline(steps: Iterable[ResponseStep]) -> list[dict[str, object]]:
    """Convert response steps to plain dictionaries for reports."""
    return [asdict(step) for step in steps]


def main() -> None:
    print(json.dumps(summarize_timeline(build_defensive_timeline()), indent=2))


if __name__ == "__main__":
    main()
