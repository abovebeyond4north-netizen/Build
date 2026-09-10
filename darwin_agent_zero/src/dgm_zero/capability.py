from __future__ import annotations

import ast
import time
from dataclasses import asdict
from pathlib import Path

from .capability_model import (
    AcquisitionReport,
    AcquisitionTask,
    CandidateGenerator,
    CapabilitySpec,
    SkillCandidate,
    SuiteScore,
    TrainingView,
    render_function,
)
from .capability_sandbox import SkillSandbox
from .capability_synthesis import TemplateSynthesizer
from .memory import KnowledgeBank
from .skill_library import SkillLibrary, holdout_digest, write_report


class CapabilityPlanner:
    """Create explicit acquisition tasks from public baseline failures."""

    def plan(
        self,
        view: TrainingView,
        baseline_train: SuiteScore,
    ) -> tuple[AcquisitionTask, ...]:
        failed = baseline_train.total - baseline_train.passed
        return (
            AcquisitionTask(
                "repair public failures",
                (
                    f"Synthesize candidates that repair {failed} of "
                    f"{baseline_train.total} training failures."
                ),
                1.0,
            ),
            AcquisitionTask(
                "generalize beyond training",
                (
                    "Select among training-successful candidates using the "
                    "separate validation split."
                ),
                0.9,
            ),
            AcquisitionTask(
                "certify before promotion",
                (
                    "Evaluate only the selected finalist on holdout cases and "
                    "promote only on measurable gain."
                ),
                0.95,
            ),
        )


class CapabilityAcquirer:
    """General bounded acquisition loop.

    The search/generator receives only training cases. Validation is used to
    choose among training-successful candidates. Holdout is evaluated exactly
    once, on the finalist, and cannot feed another search step in the same run.
    A skill is promoted only when it clears all split thresholds and improves on
    the currently installed version by the requested minimum gain.
    """

    def __init__(
        self,
        workspace: Path,
        *,
        generator: CandidateGenerator | None = None,
        sandbox: SkillSandbox | None = None,
    ) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.generator = generator or TemplateSynthesizer()
        self.sandbox = sandbox or SkillSandbox()
        self.library = SkillLibrary(workspace)
        self.memory = KnowledgeBank(workspace)
        self.planner = CapabilityPlanner()

    def acquire(
        self,
        spec: CapabilitySpec,
        *,
        max_candidates: int = 96,
        validation_budget: int = 12,
    ) -> AcquisitionReport:
        if max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        if validation_budget <= 0:
            raise ValueError("validation_budget must be positive")

        train_cases = spec.cases_for("train")
        validation_cases = spec.cases_for("validation")
        holdout_cases = spec.cases_for("holdout")

        certification_digest = holdout_digest(spec)
        current = self.library.current(spec.name)
        prior_source = current[0] if current else None
        current_manifest = current[1] if current else None

        if self.library.certification_consumed(
            spec.name,
            certification_digest,
        ):
            already_certified = bool(
                current_manifest
                and current_manifest.get("holdout_digest")
                == certification_digest
            )
            baseline_score = (
                float(current_manifest.get("final_score", 0.0))
                if current_manifest
                else 0.0
            )
            baseline_source = prior_source or render_function(
                spec.entrypoint,
                spec.arity,
                "None",
            )
            baseline = SkillCandidate(
                baseline_source,
                "installed-baseline" if prior_source else "null-baseline",
            )
            training_view = TrainingView(
                name=spec.name,
                description=spec.description,
                entrypoint=spec.entrypoint,
                arity=spec.arity,
                cases=train_cases,
            )
            baseline_train = self.sandbox.evaluate(
                baseline_source,
                spec.entrypoint,
                train_cases,
            )
            tasks = self.planner.plan(training_view, baseline_train)
            return self._finish(
                spec,
                holdout_digest_value=certification_digest,
                status=(
                    "already_certified"
                    if already_certified
                    else "holdout_suite_consumed"
                ),
                promoted=False,
                baseline=baseline,
                baseline_score=baseline_score,
                finalist=None,
                final_score=baseline_score if already_certified else None,
                train_score=baseline_train.correctness,
                validation_score=None,
                holdout_score=None,
                generated=0,
                trained=0,
                validated=0,
                holdout_evaluations=0,
                tasks=tasks,
            )

        baseline_source = prior_source or render_function(
            spec.entrypoint,
            spec.arity,
            "None",
        )
        baseline = SkillCandidate(
            baseline_source,
            "installed-baseline" if prior_source else "null-baseline",
        )
        baseline_train = self.sandbox.evaluate(
            baseline_source,
            spec.entrypoint,
            train_cases,
        )
        baseline_validation = self.sandbox.evaluate(
            baseline_source,
            spec.entrypoint,
            validation_cases,
        )
        baseline_holdout = self.sandbox.evaluate(
            baseline_source,
            spec.entrypoint,
            holdout_cases,
        )
        baseline_score = min(
            baseline_train.correctness,
            baseline_validation.correctness,
            baseline_holdout.correctness,
        )

        training_view = TrainingView(
            name=spec.name,
            description=spec.description,
            entrypoint=spec.entrypoint,
            arity=spec.arity,
            cases=train_cases,
        )
        tasks = self.planner.plan(training_view, baseline_train)
        for task in tasks:
            self.memory.deposit(
                "capability_task",
                f"{spec.name}: {task.title}: {task.instruction}",
                task.priority,
            )

        generated = self.generator.generate(
            training_view,
            prior_source=prior_source,
            max_candidates=max_candidates,
        )
        evaluated_train: list[
            tuple[SkillCandidate, SuiteScore, int]
        ] = []
        for candidate in generated:
            score = self.sandbox.evaluate(
                candidate.source,
                spec.entrypoint,
                train_cases,
            )
            evaluated_train.append(
                (candidate, score, source_complexity(candidate.source))
            )

        train_survivors = [
            item
            for item in evaluated_train
            if item[1].correctness >= spec.thresholds.train
        ]
        train_survivors.sort(
            key=lambda item: (
                -item[1].correctness,
                item[2],
                item[0].digest,
            )
        )

        validation_evidence: list[
            tuple[SkillCandidate, SuiteScore, SuiteScore, int]
        ] = []
        for candidate, train_score, complexity in train_survivors[
            :validation_budget
        ]:
            validation_score = self.sandbox.evaluate(
                candidate.source,
                spec.entrypoint,
                validation_cases,
            )
            validation_evidence.append(
                (
                    candidate,
                    train_score,
                    validation_score,
                    complexity,
                )
            )

        validation_survivors = [
            item
            for item in validation_evidence
            if item[2].correctness >= spec.thresholds.validation
        ]
        validation_survivors.sort(
            key=lambda item: (
                -min(item[1].correctness, item[2].correctness),
                item[3],
                item[0].digest,
            )
        )

        if not train_survivors:
            return self._finish(
                spec,
                holdout_digest_value=certification_digest,
                status="no_train_candidate",
                promoted=False,
                baseline=baseline,
                baseline_score=baseline_score,
                finalist=None,
                final_score=None,
                train_score=None,
                validation_score=None,
                holdout_score=None,
                generated=len(generated),
                trained=len(evaluated_train),
                validated=0,
                holdout_evaluations=0,
                tasks=tasks,
            )

        if not validation_survivors:
            return self._finish(
                spec,
                holdout_digest_value=certification_digest,
                status="no_validation_candidate",
                promoted=False,
                baseline=baseline,
                baseline_score=baseline_score,
                finalist=None,
                final_score=None,
                train_score=train_survivors[0][1].correctness,
                validation_score=max(
                    (
                        item[2].correctness
                        for item in validation_evidence
                    ),
                    default=0.0,
                ),
                holdout_score=None,
                generated=len(generated),
                trained=len(evaluated_train),
                validated=len(validation_evidence),
                holdout_evaluations=0,
                tasks=tasks,
            )

        finalist, train_score, validation_score, _ = (
            validation_survivors[0]
        )
        holdout_score = self.sandbox.evaluate(
            finalist.source,
            spec.entrypoint,
            holdout_cases,
        )
        final_score = min(
            train_score.correctness,
            validation_score.correctness,
            holdout_score.correctness,
        )

        holdout_passed = (
            holdout_score.correctness >= spec.thresholds.holdout
        )
        self.library.record_certification(
            capability=spec.name,
            holdout_digest=certification_digest,
            finalist_digest=finalist.digest,
            holdout_score=holdout_score.correctness,
            passed=holdout_passed,
        )

        if not holdout_passed:
            status = "holdout_failed"
            promoted = False
        elif (
            final_score + 1e-12
            < baseline_score + spec.thresholds.min_gain
        ):
            status = "no_measurable_gain"
            promoted = False
        else:
            status = "promoted"
            promoted = True

        return self._finish(
            spec,
            holdout_digest_value=certification_digest,
            status=status,
            promoted=promoted,
            baseline=baseline,
            baseline_score=baseline_score,
            finalist=finalist,
            final_score=final_score,
            train_score=train_score.correctness,
            validation_score=validation_score.correctness,
            holdout_score=holdout_score.correctness,
            generated=len(generated),
            trained=len(evaluated_train),
            validated=len(validation_evidence),
            holdout_evaluations=1,
            tasks=tasks,
        )

    def _finish(
        self,
        spec: CapabilitySpec,
        *,
        holdout_digest_value: str,
        status: str,
        promoted: bool,
        baseline: SkillCandidate,
        baseline_score: float,
        finalist: SkillCandidate | None,
        final_score: float | None,
        train_score: float | None,
        validation_score: float | None,
        holdout_score: float | None,
        generated: int,
        trained: int,
        validated: int,
        holdout_evaluations: int,
        tasks: tuple[AcquisitionTask, ...],
    ) -> AcquisitionReport:
        report_dir = self.workspace / "capability_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        created_at = time.time()
        report_path = (
            report_dir / f"{spec.name}-{time.time_ns()}.json"
        )
        report = AcquisitionReport(
            capability=spec.name,
            description=spec.description,
            holdout_digest=holdout_digest_value,
            status=status,
            promoted=promoted,
            baseline_digest=baseline.digest,
            baseline_score=baseline_score,
            finalist_digest=finalist.digest if finalist else None,
            final_score=final_score,
            train_score=train_score,
            validation_score=validation_score,
            holdout_score=holdout_score,
            candidates_generated=generated,
            candidates_trained=trained,
            candidates_validated=validated,
            holdout_evaluations=holdout_evaluations,
            tasks=tasks,
            installed_path=None,
            report_path=str(report_path),
            created_at=created_at,
        )

        if promoted and finalist is not None:
            installed = self.library.promote(
                spec,
                finalist,
                report,
            )
            report = AcquisitionReport(
                **{
                    **asdict(report),
                    "tasks": tasks,
                    "installed_path": str(installed),
                }
            )
            self.memory.deposit(
                "skill",
                (
                    f"{spec.name}: {finalist.digest[:12]} "
                    f"score={final_score:.3f}"
                ),
                final_score or 0.0,
            )

        write_report(self.workspace, report)
        return report


def source_complexity(source: str) -> int:
    try:
        return sum(1 for _ in ast.walk(ast.parse(source)))
    except SyntaxError:
        return 10**9
