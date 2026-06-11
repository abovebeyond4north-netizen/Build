from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path


SNAPSHOT_FILES = (
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
class CheckpointManifest:
    checkpoint_id: str
    path: str
    created_at: float
    healthy: bool
    copied_files: list[str]
    reason: str


@dataclass(frozen=True)
class RestoreReport:
    restored: bool
    checkpoint_id: str | None
    restored_files: list[str]
    reason: str


class CheckpointManager:
    """Save and restore last-known-good run artifacts."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.root = workspace / "checkpoints"
        self.root.mkdir(parents=True, exist_ok=True)

    def save_if_healthy(self, health_path: Path | None = None) -> CheckpointManifest:
        health_file = health_path or self.workspace / "health_report.json"
        healthy, reason = self._read_health(health_file)
        checkpoint_id = str(int(time.time() * 1000))
        target = self.root / checkpoint_id
        copied: list[str] = []
        if healthy:
            target.mkdir(parents=True, exist_ok=True)
            for name in SNAPSHOT_FILES:
                src = self.workspace / name
                if src.exists() and src.is_file():
                    shutil.copy2(src, target / name)
                    copied.append(name)
        manifest = CheckpointManifest(
            checkpoint_id=checkpoint_id,
            path=str(target),
            created_at=time.time(),
            healthy=healthy,
            copied_files=copied,
            reason=reason,
        )
        self._write_manifest(manifest)
        return manifest

    def restore_latest(self) -> RestoreReport:
        manifest = self.latest_manifest()
        if manifest is None:
            return RestoreReport(False, None, [], "no_checkpoint_found")
        if not manifest.healthy:
            return RestoreReport(False, manifest.checkpoint_id, [], "latest_checkpoint_not_healthy")
        checkpoint_path = Path(manifest.path)
        if not checkpoint_path.exists():
            return RestoreReport(False, manifest.checkpoint_id, [], "checkpoint_path_missing")
        restored: list[str] = []
        for name in manifest.copied_files:
            src = checkpoint_path / name
            if src.exists() and src.is_file():
                shutil.copy2(src, self.workspace / name)
                restored.append(name)
        report = RestoreReport(True, manifest.checkpoint_id, restored, "restored_latest_healthy_checkpoint")
        (self.root / "last_restore.json").write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def latest_manifest(self) -> CheckpointManifest | None:
        latest = self.root / "latest.json"
        if latest.exists():
            data = json.loads(latest.read_text(encoding="utf-8"))
            return CheckpointManifest(**data)
        manifests = sorted(self.root.glob("*/manifest.json"), reverse=True)
        if not manifests:
            return None
        data = json.loads(manifests[0].read_text(encoding="utf-8"))
        return CheckpointManifest(**data)

    def _read_health(self, path: Path) -> tuple[bool, str]:
        if not path.exists():
            return False, "health_report_missing"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False, "health_report_invalid_json"
        healthy = bool(data.get("passed", False))
        return healthy, data.get("summary", "healthy" if healthy else "needs_attention")

    def _write_manifest(self, manifest: CheckpointManifest) -> None:
        target = Path(manifest.path)
        target.mkdir(parents=True, exist_ok=True)
        (target / "manifest.json").write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")
        (self.root / "latest.json").write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")
