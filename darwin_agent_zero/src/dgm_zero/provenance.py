from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ARTIFACT_FILES = (
    "archive.jsonl",
    "knowledge.jsonl",
    "evolution_report.json",
    "map_elites.json",
    "curriculum.json",
    "cognitive_state.json",
    "operator_bandit.json",
    "mined_cases.json",
    "health_report.json",
    "champion.py",
)


@dataclass(frozen=True)
class FileFingerprint:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class ProvenanceManifest:
    created_at: float
    python: str
    platform: str
    config: dict[str, Any]
    source_files: list[FileFingerprint]
    artifacts: list[FileFingerprint]


class ProvenanceRecorder:
    """Write a reproducibility manifest for each run.

    Source discovery is dynamic so newly-added ``dgm_zero`` modules cannot silently
    fall outside the provenance boundary merely because a constant list was not
    updated at the same time.
    """

    def __init__(self, project_root: Path, workspace: Path) -> None:
        self.project_root = project_root
        self.workspace = workspace

    def _source_files(self) -> list[FileFingerprint]:
        source_root = self.project_root / "src" / "dgm_zero"
        if not source_root.exists():
            return []

        fingerprints: list[FileFingerprint] = []
        for path in sorted(source_root.glob("*.py")):
            if not path.is_file():
                continue
            label = path.relative_to(self.project_root).as_posix()
            item = fingerprint(path, label)
            if item is not None:
                fingerprints.append(item)
        return fingerprints

    def _artifact_files(self) -> list[FileFingerprint]:
        fingerprints: list[FileFingerprint] = []
        for name in ARTIFACT_FILES:
            item = fingerprint(self.workspace / name, name)
            if item is not None:
                fingerprints.append(item)
        return fingerprints

    def build(self, config: Any) -> ProvenanceManifest:
        config_data = (
            asdict(config)
            if hasattr(config, "__dataclass_fields__")
            else dict(config)
        )
        return ProvenanceManifest(
            created_at=time.time(),
            python=sys.version.split()[0],
            platform=platform.platform(),
            config=config_data,
            source_files=self._source_files(),
            artifacts=self._artifact_files(),
        )

    def write(self, path: Path, manifest: ProvenanceManifest) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(path)


def fingerprint(path: Path, label: str | None = None) -> FileFingerprint | None:
    if not path.exists() or not path.is_file():
        return None
    data = path.read_bytes()
    return FileFingerprint(
        path=label or str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
    )
