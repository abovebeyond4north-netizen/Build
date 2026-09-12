from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from .patch_policy import patch_import_reasons
from .safety import scan_source


DEFAULT_EDITABLE_PATHS = frozenset(
    {
        "src/dgm_zero/mutation.py",
        "src/dgm_zero/search_schedule.py",
        "src/dgm_zero/meta_learning.py",
        "src/dgm_zero/self_instruction.py",
    }
)
MAX_PATCH_FILES = 4
MAX_FILE_BYTES = 32_768
MAX_TOTAL_BYTES = 65_536
OUTPUT_TAIL_CHARS = 4_000
COMPARISON_SEEDS = (11, 23, 47)
AGGREGATE_REGRESSION_TOLERANCE = 1e-12
MEAN_CHAMPION_REGRESSION_TOLERANCE = 0.005
PER_SEED_CHAMPION_REGRESSION_TOLERANCE = 0.02


@dataclass(frozen=True)
class PatchFile:
    relative_path: str
    base_sha256: str
    replacement_source: str

    def __post_init__(self) -> None:
        if not isinstance(self.relative_path, str) or not self.relative_path.strip():
            raise ValueError("patch relative_path must be a non-empty string")
        if not is_sha256(self.base_sha256):
            raise ValueError("patch base_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(self.replacement_source, str) or not self.replacement_source.strip():
            raise ValueError("patch replacement_source must be non-empty text")


@dataclass(frozen=True)
class PatchProposal:
    rationale: str
    files: tuple[PatchFile, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("patch rationale must be non-empty")
        if not isinstance(self.files, tuple) or not self.files:
            raise ValueError("patch proposal must contain files")
        if any(not isinstance(item, PatchFile) for item in self.files):
            raise TypeError("patch proposal files must contain PatchFile values")

    @property
    def digest(self) -> str:
        payload = {
            "rationale": self.rationale,
            "files": [asdict(item) for item in self.files],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PatchProposal":
        if not isinstance(data, dict):
            raise TypeError("patch proposal must be an object")
        rationale = data.get("rationale")
        raw_files = data.get("files")
        if not isinstance(rationale, str):
            raise ValueError("patch rationale must be text")
        if not isinstance(raw_files, list):
            raise ValueError("patch files must be a list")
        files: list[PatchFile] = []
        for index, raw in enumerate(raw_files):
            if not isinstance(raw, dict):
                raise ValueError(f"patch file {index} must be an object")
            try:
                relative_path = raw["relative_path"]
                base_sha256 = raw["base_sha256"]
                replacement_source = raw["replacement_source"]
            except KeyError as exc:
                raise ValueError(
                    f"patch file {index} missing field: {exc.args[0]}"
                ) from exc
            files.append(
                PatchFile(
                    relative_path=relative_path,  # type: ignore[arg-type]
                    base_sha256=base_sha256,  # type: ignore[arg-type]
                    replacement_source=replacement_source,  # type: ignore[arg-type]
                )
            )
        return cls(rationale=rationale, files=tuple(files))

    @classmethod
    def load(cls, path: Path) -> "PatchProposal":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to load patch proposal: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def for_replacements(
        cls,
        repo_root: Path,
        *,
        rationale: str,
        replacements: dict[str, str],
    ) -> "PatchProposal":
        """Create a content-addressed proposal from explicit replacements."""
        files: list[PatchFile] = []
        for relative_path, replacement in sorted(replacements.items()):
            normalized = normalize_relative_path(relative_path)
            current_path = repo_root / normalized
            if not current_path.is_file():
                raise ValueError(f"patch base file is missing: {normalized}")
            files.append(
                PatchFile(
                    relative_path=normalized,
                    base_sha256=sha256_file(current_path),
                    replacement_source=replacement,
                )
            )
        return cls(rationale=rationale, files=tuple(files))


@dataclass(frozen=True)
class PatchValidationReport:
    passed: bool
    reasons: tuple[str, ...]
    proposal_digest: str
    checked_files: tuple[str, ...]


@dataclass(frozen=True)
class PatchGateResult:
    name: str
    command: tuple[str, ...]
    passed: bool
    returncode: int | None
    elapsed_seconds: float
    stdout_tail: str
    stderr_tail: str


@dataclass(frozen=True)
class PatchComparisonResult:
    passed: bool
    reasons: tuple[str, ...]
    seeds: tuple[int, ...]
    baseline_aggregate_score: float
    candidate_aggregate_score: float
    aggregate_delta: float
    baseline_mean_champion_score: float
    candidate_mean_champion_score: float
    mean_champion_delta: float
    worst_seed_champion_delta: float


@dataclass(frozen=True)
class PatchEvaluationReport:
    proposal_digest: str
    passed: bool
    validation: PatchValidationReport
    gates: tuple[PatchGateResult, ...]
    comparison: PatchComparisonResult | None
    created_at: float
    report_path: str


class RepositoryPatchLab:
    """Evaluate bounded self-modification proposals without changing live source.

    The lab is deliberately proposal-only. It has no method that writes a passed
    proposal back into ``repo_root`` and no GitHub merge capability. A proposal is
    applied only inside an ephemeral copy, then compile/test and comparative
    strategy gates produce evidence for human review.
    """

    def __init__(
        self,
        repo_root: Path,
        workspace: Path,
        *,
        editable_paths: Iterable[str] = DEFAULT_EDITABLE_PATHS,
        max_patch_files: int = MAX_PATCH_FILES,
        max_file_bytes: int = MAX_FILE_BYTES,
        max_total_bytes: int = MAX_TOTAL_BYTES,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.workspace = workspace.resolve()
        self.editable_paths = frozenset(
            normalize_relative_path(path) for path in editable_paths
        )
        self.max_patch_files = require_positive_int(
            max_patch_files,
            "max_patch_files",
        )
        self.max_file_bytes = require_positive_int(
            max_file_bytes,
            "max_file_bytes",
        )
        self.max_total_bytes = require_positive_int(
            max_total_bytes,
            "max_total_bytes",
        )
        if not (self.repo_root / "pyproject.toml").is_file():
            raise ValueError("repo_root must contain pyproject.toml")
        self.workspace.mkdir(parents=True, exist_ok=True)

    def validate(self, proposal: PatchProposal) -> PatchValidationReport:
        reasons: list[str] = []
        checked: list[str] = []
        if len(proposal.files) > self.max_patch_files:
            reasons.append(
                f"proposal changes {len(proposal.files)} files; maximum is "
                f"{self.max_patch_files}"
            )

        seen_paths: set[str] = set()
        total_bytes = 0
        for item in proposal.files:
            try:
                relative_path = normalize_relative_path(item.relative_path)
            except ValueError as exc:
                reasons.append(str(exc))
                continue
            checked.append(relative_path)
            if relative_path in seen_paths:
                reasons.append(f"duplicate patch path: {relative_path}")
                continue
            seen_paths.add(relative_path)
            if relative_path not in self.editable_paths:
                reasons.append(f"path is not editable by self-patch policy: {relative_path}")
                continue

            target = self.repo_root / relative_path
            if not target.is_file() or target.is_symlink():
                reasons.append(f"editable path is not a regular file: {relative_path}")
                continue
            actual_hash = sha256_file(target)
            if actual_hash != item.base_sha256:
                reasons.append(
                    f"base hash mismatch for {relative_path}: expected "
                    f"{item.base_sha256}, found {actual_hash}"
                )

            source_bytes = len(item.replacement_source.encode("utf-8"))
            total_bytes += source_bytes
            if source_bytes > self.max_file_bytes:
                reasons.append(
                    f"replacement exceeds {self.max_file_bytes} bytes: "
                    f"{relative_path}"
                )

            try:
                ast.parse(item.replacement_source)
            except SyntaxError as exc:
                reasons.append(f"syntax error in {relative_path}: {exc}")
                continue
            reasons.extend(
                patch_import_reasons(relative_path, item.replacement_source)
            )
            safety = scan_source(item.replacement_source)
            if not safety.passed:
                reasons.extend(
                    f"{relative_path}: {reason}" for reason in safety.reasons
                )

        if total_bytes > self.max_total_bytes:
            reasons.append(
                f"proposal replacement payload exceeds {self.max_total_bytes} bytes"
            )
        unique_reasons = tuple(dict.fromkeys(reasons))
        return PatchValidationReport(
            passed=not unique_reasons,
            reasons=unique_reasons,
            proposal_digest=proposal.digest,
            checked_files=tuple(checked),
        )

    def evaluate(
        self,
        proposal: PatchProposal,
        *,
        timeout_seconds: float = 90.0,
        gate_commands: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
    ) -> PatchEvaluationReport:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or float(timeout_seconds) <= 0.0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        validation = self.validate(proposal)
        gates: list[PatchGateResult] = []
        comparison: PatchComparisonResult | None = None
        default_gates = gate_commands is None
        if validation.passed:
            with tempfile.TemporaryDirectory(prefix="dgm-self-patch-") as tmp:
                temp_root = Path(tmp)
                baseline_root = temp_root / "baseline"
                staged_root = temp_root / "candidate"
                self._copy_project(self.repo_root, baseline_root)
                self._copy_project(baseline_root, staged_root)
                for item in proposal.files:
                    relative_path = normalize_relative_path(item.relative_path)
                    target = staged_root / relative_path
                    target.write_text(item.replacement_source, encoding="utf-8")

                commands = (
                    self.default_gate_commands()
                    if gate_commands is None
                    else gate_commands
                )
                env = self._validation_env(staged_root)
                for name, command in commands:
                    result = self._run_gate(
                        name,
                        command,
                        staged_root,
                        env,
                        float(timeout_seconds),
                    )
                    gates.append(result)
                    if not result.passed:
                        break

                if default_gates and gates and all(gate.passed for gate in gates):
                    comparison, comparison_gates = self._compare_strategy(
                        baseline_root,
                        staged_root,
                        temp_root,
                        float(timeout_seconds),
                    )
                    gates.extend(comparison_gates)

        gates_passed = bool(gates) and all(gate.passed for gate in gates)
        comparison_passed = comparison is None or comparison.passed
        if default_gates:
            comparison_passed = comparison is not None and comparison.passed
        passed = validation.passed and gates_passed and comparison_passed
        return self._write_report(
            PatchEvaluationReport(
                proposal_digest=proposal.digest,
                passed=passed,
                validation=validation,
                gates=tuple(gates),
                comparison=comparison,
                created_at=time.time(),
                report_path="",
            )
        )

    @staticmethod
    def default_gate_commands() -> tuple[tuple[str, tuple[str, ...]], ...]:
        python = sys.executable
        return (
            (
                "compile",
                (python, "-m", "compileall", "-q", "src", "tests", "scripts"),
            ),
            ("darwin_validation", (python, "scripts/validate.py")),
            (
                "capability_validation",
                (python, "scripts/validate_capability_acquisition.py"),
            ),
        )

    @staticmethod
    def _copy_project(source: Path, destination: Path) -> None:
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "__pycache__",
                "*.pyc",
                ".dgm_workspace*",
                ".pytest_cache",
                "build",
                "dist",
                "patch_reports",
            ),
        )

    def _compare_strategy(
        self,
        baseline_root: Path,
        staged_root: Path,
        temp_root: Path,
        timeout_seconds: float,
    ) -> tuple[PatchComparisonResult | None, list[PatchGateResult]]:
        baseline_output = temp_root / "baseline-strategy.json"
        candidate_output = temp_root / "candidate-strategy.json"
        seeds_arg = ",".join(str(seed) for seed in COMPARISON_SEEDS)
        runs = (
            (
                "strategy_baseline",
                baseline_root,
                baseline_output,
                temp_root / "baseline-strategy-workspace",
            ),
            (
                "strategy_candidate",
                staged_root,
                candidate_output,
                temp_root / "candidate-strategy-workspace",
            ),
        )
        gate_results: list[PatchGateResult] = []
        for name, root, output, workspace in runs:
            command = (
                sys.executable,
                "-m",
                "dgm_zero.strategy_benchmark",
                "--workspace-root",
                str(workspace),
                "--output",
                str(output),
                "--seeds",
                seeds_arg,
            )
            result = self._run_gate(
                name,
                command,
                root,
                self._validation_env(root),
                timeout_seconds,
            )
            gate_results.append(result)
            if not result.passed:
                return None, gate_results

        baseline = load_json_object(baseline_output, "baseline strategy benchmark")
        candidate = load_json_object(candidate_output, "candidate strategy benchmark")
        return compare_strategy_reports(baseline, candidate), gate_results

    @staticmethod
    def _validation_env(staged_root: Path) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(staged_root / "src"),
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }

    @staticmethod
    def _run_gate(
        name: str,
        command: tuple[str, ...],
        staged_root: Path,
        env: dict[str, str],
        timeout_seconds: float,
    ) -> PatchGateResult:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("gate name must be non-empty")
        if not command or any(not isinstance(part, str) or not part for part in command):
            raise ValueError("gate command must contain non-empty strings")
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                list(command),
                cwd=staged_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            elapsed = time.perf_counter() - started
            return PatchGateResult(
                name=name,
                command=command,
                passed=completed.returncode == 0,
                returncode=completed.returncode,
                elapsed_seconds=elapsed,
                stdout_tail=tail(completed.stdout),
                stderr_tail=tail(completed.stderr),
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started
            stdout = decode_timeout_output(exc.stdout)
            stderr = decode_timeout_output(exc.stderr)
            return PatchGateResult(
                name=name,
                command=command,
                passed=False,
                returncode=None,
                elapsed_seconds=elapsed,
                stdout_tail=tail(stdout),
                stderr_tail=tail(stderr or "gate timed out"),
            )

    def _write_report(self, report: PatchEvaluationReport) -> PatchEvaluationReport:
        report_dir = self.workspace / "patch_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{report.proposal_digest}.json"
        completed = PatchEvaluationReport(
            **{
                **asdict(report),
                "validation": report.validation,
                "gates": report.gates,
                "comparison": report.comparison,
                "report_path": str(report_path),
            }
        )
        payload = asdict(completed)
        temp = report_path.with_name(f".{report_path.name}.{time.time_ns()}.tmp")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        temp.replace(report_path)
        latest = report_dir / "latest.json"
        latest_tmp = latest.with_name(f".{latest.name}.{time.time_ns()}.tmp")
        latest_tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        latest_tmp.replace(latest)
        return completed


def compare_strategy_reports(
    baseline: dict[str, object],
    candidate: dict[str, object],
) -> PatchComparisonResult:
    baseline_seeds = parse_report_seeds(baseline)
    candidate_seeds = parse_report_seeds(candidate)
    if baseline_seeds != candidate_seeds:
        raise ValueError("strategy benchmark seeds do not match")
    if baseline_seeds != COMPARISON_SEEDS:
        raise ValueError("strategy benchmark did not use the sealed comparison seeds")

    baseline_aggregate = report_score(baseline, "aggregate_score")
    candidate_aggregate = report_score(candidate, "aggregate_score")
    baseline_mean = report_score(baseline, "mean_champion_score")
    candidate_mean = report_score(candidate, "mean_champion_score")
    baseline_runs = champion_scores_by_seed(baseline)
    candidate_runs = champion_scores_by_seed(candidate)
    if set(baseline_runs) != set(candidate_runs):
        raise ValueError("strategy benchmark run seeds do not match")

    per_seed_deltas = {
        seed: candidate_runs[seed] - baseline_runs[seed]
        for seed in baseline_seeds
    }
    aggregate_delta = candidate_aggregate - baseline_aggregate
    mean_delta = candidate_mean - baseline_mean
    worst_seed_delta = min(per_seed_deltas.values())
    reasons: list[str] = []
    if aggregate_delta < -AGGREGATE_REGRESSION_TOLERANCE:
        reasons.append(
            f"aggregate strategy score regressed by {aggregate_delta:.6f}"
        )
    if mean_delta < -MEAN_CHAMPION_REGRESSION_TOLERANCE:
        reasons.append(
            f"mean champion score regressed by {mean_delta:.6f}"
        )
    if worst_seed_delta < -PER_SEED_CHAMPION_REGRESSION_TOLERANCE:
        worst_seed = min(per_seed_deltas, key=per_seed_deltas.get)
        reasons.append(
            f"seed {worst_seed} champion score regressed by "
            f"{per_seed_deltas[worst_seed]:.6f}"
        )

    return PatchComparisonResult(
        passed=not reasons,
        reasons=tuple(reasons),
        seeds=baseline_seeds,
        baseline_aggregate_score=baseline_aggregate,
        candidate_aggregate_score=candidate_aggregate,
        aggregate_delta=aggregate_delta,
        baseline_mean_champion_score=baseline_mean,
        candidate_mean_champion_score=candidate_mean,
        mean_champion_delta=mean_delta,
        worst_seed_champion_delta=worst_seed_delta,
    )


def parse_report_seeds(report: dict[str, object]) -> tuple[int, ...]:
    raw = report.get("seeds")
    if not isinstance(raw, list) or not raw:
        raise ValueError("strategy benchmark report has invalid seeds")
    seeds: list[int] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("strategy benchmark seeds must be integers")
        seeds.append(value)
    if len(set(seeds)) != len(seeds):
        raise ValueError("strategy benchmark seeds must be unique")
    return tuple(seeds)


def report_score(report: dict[str, object], field: str) -> float:
    raw = report.get(field)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"strategy benchmark {field} must be numeric")
    value = float(raw)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(
            f"strategy benchmark {field} must be finite and between 0 and 1"
        )
    return value


def champion_scores_by_seed(report: dict[str, object]) -> dict[int, float]:
    raw_runs = report.get("runs")
    if not isinstance(raw_runs, list) or not raw_runs:
        raise ValueError("strategy benchmark report has invalid runs")
    output: dict[int, float] = {}
    for raw in raw_runs:
        if not isinstance(raw, dict):
            raise ValueError("strategy benchmark run must be an object")
        seed = raw.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("strategy benchmark run seed must be an integer")
        if seed in output:
            raise ValueError("strategy benchmark contains duplicate run seeds")
        output[seed] = report_score(raw, "champion_score")
    return output


def load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid {label}: expected object")
    return value


def normalize_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("patch path must be a non-empty string")
    if "\\" in value:
        raise ValueError("patch path must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe patch path: {value}")
    normalized = path.as_posix()
    if not normalized.endswith(".py"):
        raise ValueError(f"patch path must target Python source: {normalized}")
    return normalized


def require_positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tail(value: str) -> str:
    return value[-OUTPUT_TAIL_CHARS:]


def decode_timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
