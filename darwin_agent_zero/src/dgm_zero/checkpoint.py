from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
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
    "provenance.json",
    "champion.py",
)
SNAPSHOT_FILE_SET = frozenset(SNAPSHOT_FILES)


@dataclass(frozen=True)
class CheckpointManifest:
    checkpoint_id: str
    path: str
    created_at: float
    healthy: bool
    copied_files: list[str]
    reason: str
    file_hashes: dict[str, str] = field(default_factory=dict)


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
        checkpoint_id = str(time.time_ns())
        target = self.root / checkpoint_id
        copied: list[str] = []
        file_hashes: dict[str, str] = {}
        if healthy:
            target.mkdir(parents=True, exist_ok=True)
            copied = self._copy_snapshot_files(target)
            file_hashes = self._hash_snapshot_files(target, copied)
        manifest = CheckpointManifest(
            checkpoint_id=checkpoint_id,
            path=str(target),
            created_at=time.time(),
            healthy=healthy,
            copied_files=copied,
            reason=reason,
            file_hashes=file_hashes,
        )
        self._write_manifest(manifest)
        return manifest

    def refresh(self, manifest: CheckpointManifest) -> CheckpointManifest:
        """Refresh a healthy checkpoint after final artifacts are written."""
        if not manifest.healthy:
            self._write_manifest(manifest)
            return manifest
        target = Path(manifest.path)
        target.mkdir(parents=True, exist_ok=True)
        copied = self._copy_snapshot_files(target)
        file_hashes = self._hash_snapshot_files(target, copied)
        refreshed = CheckpointManifest(
            checkpoint_id=manifest.checkpoint_id,
            path=manifest.path,
            created_at=manifest.created_at,
            healthy=True,
            copied_files=copied,
            reason=manifest.reason,
            file_hashes=file_hashes,
        )
        self._write_manifest(refreshed)
        return refreshed

    def restore_latest(self) -> RestoreReport:
        """Restore the newest healthy checkpoint, ignoring later failed runs."""
        manifest = self.latest_healthy_manifest()
        if manifest is None:
            latest = self.latest_manifest()
            if latest is None:
                return RestoreReport(False, None, [], "no_checkpoint_found")
            return RestoreReport(
                False,
                latest.checkpoint_id,
                [],
                "no_healthy_checkpoint_found",
            )

        checkpoint_path = Path(manifest.path)
        if not checkpoint_path.exists() or not checkpoint_path.is_dir():
            return RestoreReport(
                False,
                manifest.checkpoint_id,
                [],
                "checkpoint_path_missing",
            )

        restorable = [
            name
            for name in manifest.copied_files
            if name in SNAPSHOT_FILE_SET
            and (checkpoint_path / name).exists()
            and (checkpoint_path / name).is_file()
        ]
        if manifest.file_hashes:
            for name in restorable:
                expected = manifest.file_hashes.get(name)
                if expected is None or sha256_file(checkpoint_path / name) != expected:
                    report = RestoreReport(
                        False,
                        manifest.checkpoint_id,
                        [],
                        "checkpoint_integrity_failed",
                    )
                    self._write_json_atomic(
                        self.root / "last_restore.json",
                        asdict(report),
                    )
                    return report
            if any(
                name in SNAPSHOT_FILE_SET and name not in restorable
                for name in manifest.copied_files
            ):
                report = RestoreReport(
                    False,
                    manifest.checkpoint_id,
                    [],
                    "checkpoint_integrity_failed",
                )
                self._write_json_atomic(
                    self.root / "last_restore.json",
                    asdict(report),
                )
                return report

        restored: list[str] = []
        for name in restorable:
            shutil.copy2(checkpoint_path / name, self.workspace / name)
            restored.append(name)

        if not restored:
            report = RestoreReport(
                False,
                manifest.checkpoint_id,
                [],
                "checkpoint_has_no_restorable_files",
            )
        else:
            report = RestoreReport(
                True,
                manifest.checkpoint_id,
                restored,
                "restored_latest_healthy_checkpoint",
            )
        self._write_json_atomic(self.root / "last_restore.json", asdict(report))
        return report

    def latest_manifest(self) -> CheckpointManifest | None:
        """Return the newest checkpoint attempt, healthy or unhealthy."""
        latest = self._load_manifest_file(self.root / "latest.json")
        if latest is not None:
            return latest
        manifests = sorted(self.root.glob("*/manifest.json"), reverse=True)
        for path in manifests:
            manifest = self._load_manifest_file(path)
            if manifest is not None:
                return manifest
        return None

    def latest_healthy_manifest(self) -> CheckpointManifest | None:
        """Return the newest valid healthy checkpoint available for rollback."""
        pointer = self._load_manifest_file(self.root / "latest_healthy.json")
        if pointer is not None and pointer.healthy:
            return pointer

        manifests = sorted(self.root.glob("*/manifest.json"), reverse=True)
        for path in manifests:
            manifest = self._load_manifest_file(path)
            if manifest is not None and manifest.healthy:
                return manifest
        return None

    def _copy_snapshot_files(self, target: Path) -> list[str]:
        copied: list[str] = []
        for name in SNAPSHOT_FILES:
            src = self.workspace / name
            if src.exists() and src.is_file():
                shutil.copy2(src, target / name)
                copied.append(name)
        return copied

    @staticmethod
    def _hash_snapshot_files(target: Path, names: list[str]) -> dict[str, str]:
        return {name: sha256_file(target / name) for name in names}

    def _read_health(self, path: Path) -> tuple[bool, str]:
        if not path.exists():
            return False, "health_report_missing"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False, "health_report_invalid_json"
        if not isinstance(data, dict):
            return False, "health_report_invalid_shape"
        healthy = bool(data.get("passed", False))
        summary = data.get("summary")
        if not isinstance(summary, str) or not summary:
            summary = "healthy" if healthy else "needs_attention"
        return healthy, summary

    @staticmethod
    def _load_manifest_file(path: Path) -> CheckpointManifest | None:
        if not path.exists() or not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            manifest = CheckpointManifest(**data)
        except (OSError, json.JSONDecodeError, TypeError):
            return None
        if not isinstance(manifest.copied_files, list):
            return None
        if not all(isinstance(name, str) for name in manifest.copied_files):
            return None
        if not isinstance(manifest.file_hashes, dict):
            return None
        if not all(
            isinstance(name, str) and isinstance(digest, str)
            for name, digest in manifest.file_hashes.items()
        ):
            return None
        return manifest

    @staticmethod
    def _write_json_atomic(path: Path, data: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _write_manifest(self, manifest: CheckpointManifest) -> None:
        target = Path(manifest.path)
        target.mkdir(parents=True, exist_ok=True)
        data = asdict(manifest)
        self._write_json_atomic(target / "manifest.json", data)
        self._write_json_atomic(self.root / "latest.json", data)
        if manifest.healthy:
            self._write_json_atomic(self.root / "latest_healthy.json", data)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
