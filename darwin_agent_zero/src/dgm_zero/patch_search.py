from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .patch_synthesis import BoundedPolicyPatchSynthesizer, SynthesizedPatch
from .self_patch import (
    COMPARISON_SEEDS,
    PatchComparisonResult,
    PatchGateResult,
    RepositoryPatchLab,
    compare_strategy_reports,
    load_json_object,
    normalize_relative_path,
)


MIN_DEVELOPMENT_GAIN = 0.001


@dataclass(frozen=True)
class PatchDevelopmentScreen:
    proposal_digest: str
    focus: str
    knob: str
    old_value: float
    new_value: float
    passed: bool
    reason: str
    aggregate_delta: float | None
    mean_champion_delta: float | None
    worst_seed_champion_delta: float | None
    gates: tuple[PatchGateResult, ...]
    comparison: PatchComparisonResult | None


@dataclass(frozen=True)
class PatchSearchReport:
    search_digest: str
    focus: str | None
    max_candidates: int
    generated_candidates: int
    screened_candidates: int
    development_passes: int
    finalist_digest: str | None
    certification_attempted: bool
    certification_passed: bool
    certification_status: str
    certification_report_path: str | None
    screens: tuple[PatchDevelopmentScreen, ...]
    created_at: float
    report_path: str


class BoundedPatchSearchEngine:
    """Search strategy patches using targeted development evidence, then certify one finalist."""

    def __init__(
        self,
        repo_root: Path,
        workspace: Path,
        *,
        lab: RepositoryPatchLab | None = None,
        synthesizer: BoundedPolicyPatchSynthesizer | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.lab = lab or RepositoryPatchLab(self.repo_root, self.workspace)
        self.synthesizer = synthesizer or BoundedPolicyPatchSynthesizer(self.repo_root)

    def run(
        self,
        *,
        max_candidates: int = 6,
        focus: str | None = None,
        timeout_seconds: float = 90.0,
    ) -> PatchSearchReport:
        if (
            isinstance(max_candidates, bool)
            or not isinstance(max_candidates, int)
            or max_candidates <= 0
        ):
            raise ValueError("max_candidates must be a positive integer")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or float(timeout_seconds) <= 0.0
        ):
            raise ValueError("timeout_seconds must be finite and positive")

        candidates = self.synthesizer.generate_validated(
            self.lab,
            max_candidates=max_candidates,
            focus=focus,
        )
        screens = tuple(
            self._screen_candidate(candidate, float(timeout_seconds))
            for candidate in candidates
        )
        passing = [screen for screen in screens if screen.passed]
        finalist_screen = select_finalist(passing)
        by_digest = {candidate.proposal.digest: candidate for candidate in candidates}

        certification_attempted = False
        certification_passed = False
        certification_status = "not_attempted"
        certification_report_path: str | None = None
        finalist_digest: str | None = None
        if finalist_screen is not None:
            finalist_digest = finalist_screen.proposal_digest
            finalist = by_digest[finalist_digest]
            certification_attempted = True
            certification = self.lab.evaluate(
                finalist.proposal,
                timeout_seconds=float(timeout_seconds),
            )
            certification_passed = certification.passed
            certification_status = certification.certification_status
            certification_report_path = certification.report_path

        search_digest = search_identity(
            candidates,
            focus=focus,
            max_candidates=max_candidates,
        )
        return self._write_report(
            PatchSearchReport(
                search_digest=search_digest,
                focus=focus,
                max_candidates=max_candidates,
                generated_candidates=len(candidates),
                screened_candidates=len(screens),
                development_passes=len(passing),
                finalist_digest=finalist_digest,
                certification_attempted=certification_attempted,
                certification_passed=certification_passed,
                certification_status=certification_status,
                certification_report_path=certification_report_path,
                screens=screens,
                created_at=time.time(),
                report_path="",
            )
        )

    def _screen_candidate(
        self,
        candidate: SynthesizedPatch,
        timeout_seconds: float,
    ) -> PatchDevelopmentScreen:
        validation = self.lab.validate(candidate.proposal)
        if not validation.passed:
            return PatchDevelopmentScreen(
                proposal_digest=candidate.proposal.digest,
                focus=candidate.focus,
                knob=candidate.knob,
                old_value=candidate.old_value,
                new_value=candidate.new_value,
                passed=False,
                reason="static_validation_failed",
                aggregate_delta=None,
                mean_champion_delta=None,
                worst_seed_champion_delta=None,
                gates=(),
                comparison=None,
            )

        gates: list[PatchGateResult] = []
        comparison: PatchComparisonResult | None = None
        with tempfile.TemporaryDirectory(prefix="dgm-patch-screen-") as tmp:
            temp_root = Path(tmp)
            baseline_root = temp_root / "baseline"
            candidate_root = temp_root / "candidate"
            self.lab._copy_project(self.repo_root, baseline_root)
            self.lab._copy_project(baseline_root, candidate_root)
            for item in candidate.proposal.files:
                relative_path = normalize_relative_path(item.relative_path)
                (candidate_root / relative_path).write_text(
                    item.replacement_source,
                    encoding="utf-8",
                )

            compile_gate = self.lab._run_gate(
                "development_compile",
                (sys.executable, "-m", "compileall", "-q", "src"),
                candidate_root,
                self.lab._validation_env(candidate_root),
                timeout_seconds,
            )
            gates.append(compile_gate)
            if compile_gate.passed:
                comparison, comparison_gates = self._compare_focus_strategy(
                    baseline_root,
                    candidate_root,
                    temp_root,
                    timeout_seconds,
                    focus=candidate.focus,
                )
                gates.extend(comparison_gates)

        gates_passed = bool(gates) and all(gate.passed for gate in gates)
        measured_gain = (
            comparison is not None
            and comparison.passed
            and comparison.aggregate_delta >= MIN_DEVELOPMENT_GAIN
        )
        passed = gates_passed and measured_gain
        if not gates_passed:
            reason = "development_gate_failed"
        elif comparison is None:
            reason = "development_comparison_missing"
        elif not comparison.passed:
            reason = "development_regression"
        elif comparison.aggregate_delta < MIN_DEVELOPMENT_GAIN:
            reason = "development_gain_below_threshold"
        else:
            reason = "development_gain_verified"

        return PatchDevelopmentScreen(
            proposal_digest=candidate.proposal.digest,
            focus=candidate.focus,
            knob=candidate.knob,
            old_value=candidate.old_value,
            new_value=candidate.new_value,
            passed=passed,
            reason=reason,
            aggregate_delta=(comparison.aggregate_delta if comparison else None),
            mean_champion_delta=(
                comparison.mean_champion_delta if comparison else None
            ),
            worst_seed_champion_delta=(
                comparison.worst_seed_champion_delta if comparison else None
            ),
            gates=tuple(gates),
            comparison=comparison,
        )

    def _compare_focus_strategy(
        self,
        baseline_root: Path,
        candidate_root: Path,
        temp_root: Path,
        timeout_seconds: float,
        *,
        focus: str,
    ) -> tuple[PatchComparisonResult | None, list[PatchGateResult]]:
        baseline_output = temp_root / "development-baseline.json"
        candidate_output = temp_root / "development-candidate.json"
        seeds_arg = ",".join(str(seed) for seed in COMPARISON_SEEDS)
        runs = (
            (
                "development_baseline",
                baseline_root,
                baseline_output,
                temp_root / "development-baseline-workspace",
            ),
            (
                "development_candidate",
                candidate_root,
                candidate_output,
                temp_root / "development-candidate-workspace",
            ),
        )
        gates: list[PatchGateResult] = []
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
                "--focus",
                focus,
            )
            result = self.lab._run_gate(
                name,
                command,
                root,
                self.lab._validation_env(root),
                timeout_seconds,
            )
            gates.append(result)
            if not result.passed:
                return None, gates

        baseline = load_json_object(
            baseline_output,
            "focus-conditioned baseline strategy benchmark",
        )
        candidate = load_json_object(
            candidate_output,
            "focus-conditioned candidate strategy benchmark",
        )
        if baseline.get("focus") != focus or candidate.get("focus") != focus:
            raise ValueError("focus-conditioned benchmark report focus mismatch")
        return (
            compare_strategy_reports(
                baseline,
                candidate,
                expected_seeds=COMPARISON_SEEDS,
            ),
            gates,
        )

    def _write_report(self, report: PatchSearchReport) -> PatchSearchReport:
        report_dir = self.workspace / "patch_search_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"{report.search_digest}.json"
        completed = PatchSearchReport(
            **{
                **asdict(report),
                "screens": report.screens,
                "report_path": str(path),
            }
        )
        payload = asdict(completed)
        temp = path.with_name(f".{path.name}.tmp")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        temp.replace(path)
        latest = report_dir / "latest.json"
        latest_temp = latest.with_name(f".{latest.name}.tmp")
        latest_temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        latest_temp.replace(latest)
        return completed


def select_finalist(
    screens: list[PatchDevelopmentScreen],
) -> PatchDevelopmentScreen | None:
    eligible = [
        screen
        for screen in screens
        if screen.passed
        and screen.aggregate_delta is not None
        and screen.mean_champion_delta is not None
        and screen.worst_seed_champion_delta is not None
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda screen: (
            -float(screen.aggregate_delta),
            -float(screen.mean_champion_delta),
            -float(screen.worst_seed_champion_delta),
            screen.proposal_digest,
        ),
    )[0]


def search_identity(
    candidates: list[SynthesizedPatch],
    *,
    focus: str | None,
    max_candidates: int,
) -> str:
    payload = {
        "protocol_version": 2,
        "focus": focus,
        "focus_conditioned_development": True,
        "max_candidates": max_candidates,
        "minimum_development_gain": MIN_DEVELOPMENT_GAIN,
        "candidate_digests": [candidate.proposal.digest for candidate in candidates],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
