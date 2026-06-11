from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SOURCE_FILES = (
    "src/dgm_zero/evolver.py",
    "src/dgm_zero/oracle.py",
    "src/dgm_zero/benchmark.py",
    "src/dgm_zero/archive.py",
    "src/dgm_zero/decision_matrix.py",
    "src/dgm_zero/safety.py",
    "src/dgm_zero/case_miner.py",
    "src/dgm_zero/metacognition.py",
    "src/dgm_zero/meta_learning.py",
    "src/dgm_zero/sota_methods.py",
    "src/dgm_zero/health.py",
    "src/dgm_zero/checkpoint.py",
)

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
    """Writes a reproducibility manifest for each run."""

    def __init__(self, project_root: Path, workspace: Path) -> None:
        self.project_root = project_root
        self.workspace = workspace

    def build(self, config: Any) -> ProvenanceManifest:
        return ProvenanceManifest(
            created_at=time.time(),
            python=sys.version.split()[0],
            platform=platform.platform(),
            config=asdict(config) if hasattr(config, "__dataclass_fields__") else dict(config),
            source_files=[fp for fp in (fingerprint(self.project_root / name, name) for name in SOURCE_FILES) if fp is not None],
            artifacts=[fp for fp in (fingerprint(self.workspace / name, name) for name in ARTIFACT_FILES) if fp is not None],
        )

    def write(self, path: Path, manifest: ProvenanceManifest) -> None:
        path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")


def fingerprint(path: Path, label: str | None = None) -> FileFingerprint | None:
    if not path.exists() or not path.is_file():
        return None
    data = path.read_bytes()
    return FileFingerprint(path=label or str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
