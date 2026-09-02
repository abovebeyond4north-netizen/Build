#!/usr/bin/env python3
"""
self_audit_improve.py

A self-auditing code-quality tool.

Capabilities:
- Analyze Python source code.
- Detect syntax, complexity, reliability, style, documentation, and maintainability issues.
- Score code quality.
- Generate an improvement roadmap.
- Suggest safer implementation paths.
- Produce a verification checklist.

Usage:
    python self_audit_improve.py
    python self_audit_improve.py path/to/file.py
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditIssue:
    line: int
    severity: int
    category: str
    problem: str
    recommendation: str


@dataclass(frozen=True)
class ImprovementPatch:
    title: str
    reason: str
    suggested_change: str


@dataclass(frozen=True)
class AuditResult:
    target: str
    quality_score: int
    issue_count: int
    risk_summary: str
    issues: list[AuditIssue]
    implementation_path: list[str]
    proposed_patches: list[ImprovementPatch]
    verification_plan: list[str]


class PythonCodeAnalyzer:
    """
    Analyzes Python source code and returns quality issues.
    """

    def __init__(self, source_code: str, strictness: str = "medium") -> None:
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.strictness = strictness
        self.tree: ast.AST | None = None

    def analyze(self) -> list[AuditIssue]:
        syntax_issues = self._parse_safely()

        if syntax_issues:
            return syntax_issues

        issues: list[AuditIssue] = []

        issues.extend(self._check_long_lines())
        issues.extend(self._check_todo_comments())
        issues.extend(self._check_missing_docstrings())
        issues.extend(self._check_complexity())
        issues.extend(self._check_exception_handling())
        issues.extend(self._check_print_usage())
        issues.extend(self._check_magic_numbers())

        return sorted(issues, key=lambda issue: (-issue.severity, issue.line))

    def _parse_safely(self) -> list[AuditIssue]:
        try:
            self.tree = ast.parse(self.source_code)
            return []
        except SyntaxError as error:
            return [
                AuditIssue(
                    line=error.lineno or 0,
                    severity=10,
                    category="syntax",
                    problem=f"Syntax error: {error.msg}",
                    recommendation="Fix syntax before deeper analysis.",
                )
            ]

    def _max_line_length(self) -> int:
        limits = {
            "low": 120,
            "medium": 100,
            "high": 88,
        }

        return limits.get(self.strictness, 100)

    def _check_long_lines(self) -> list[AuditIssue]:
        issues: list[AuditIssue] = []
        max_length = self._max_line_length()

        for line_number, line in enumerate(self.lines, start=1):
            if len(line) > max_length:
                issues.append(
                    AuditIssue(
                        line=line_number,
                        severity=3,
                        category="style",
                        problem=f"Line exceeds {max_length} characters.",
                        recommendation="Wrap the line or extract part of the expression.",
                    )
                )

        return issues

    def _check_todo_comments(self) -> list[AuditIssue]:
        issues: list[AuditIssue] = []
        marker_pattern = re.compile(r"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)

        for line_number, line in enumerate(self.lines, start=1):
            if marker_pattern.search(line):
                issues.append(
                    AuditIssue(
                        line=line_number,
                        severity=4,
                        category="maintainability",
                        problem="Unresolved TODO/FIXME/HACK marker found.",
                        recommendation="Resolve it or convert it into a tracked task.",
                    )
                )

        return issues

    def _check_missing_docstrings(self) -> list[AuditIssue]:
        issues: list[AuditIssue] = []

        if self.tree is None:
            return issues

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.startswith("_"):
                    continue

                if ast.get_docstring(node) is None:
                    issues.append(
                        AuditIssue(
                            line=node.lineno,
                            severity=2,
                            category="documentation",
                            problem=f"'{node.name}' has no docstring.",
                            recommendation=(
                                "Add a short docstring explaining purpose, inputs, and output."
                            ),
                        )
                    )

        return issues

    def _check_complexity(self) -> list[AuditIssue]:
        issues: list[AuditIssue] = []

        if self.tree is None:
            return issues

        limits = {
            "low": 12,
            "medium": 8,
            "high": 5,
        }

        max_complexity = limits.get(self.strictness, 8)

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._estimate_complexity(node)

                if complexity > max_complexity:
                    issues.append(
                        AuditIssue(
                            line=node.lineno,
                            severity=7,
                            category="complexity",
                            problem=(
                                f"Function '{node.name}' has high estimated complexity "
                                f"({complexity})."
                            ),
                            recommendation=(
                                "Split it into smaller functions with one responsibility each."
                            ),
                        )
                    )

        return issues

    @staticmethod
    def _estimate_complexity(node: ast.AST) -> int:
        complexity_nodes = (
            ast.If,
            ast.For,
            ast.While,
            ast.Try,
            ast.ExceptHandler,
            ast.BoolOp,
            ast.IfExp,
            ast.Match,
        )

        return sum(isinstance(child, complexity_nodes) for child in ast.walk(node))

    def _check_exception_handling(self) -> list[AuditIssue]:
        issues: list[AuditIssue] = []

        if self.tree is None:
            return issues

        for node in ast.walk(self.tree):
            if not isinstance(node, ast.ExceptHandler):
                continue

            if node.type is None:
                issues.append(
                    AuditIssue(
                        line=node.lineno,
                        severity=9,
                        category="reliability",
                        problem="Bare except block found.",
                        recommendation="Catch a specific exception type.",
                    )
                )

            elif isinstance(node.type, ast.Name):
                if node.type.id in {"Exception", "BaseException"}:
                    issues.append(
                        AuditIssue(
                            line=node.lineno,
                            severity=6,
                            category="reliability",
                            problem=f"Overly broad exception handler: {node.type.id}.",
                            recommendation="Catch the narrowest expected exception.",
                        )
                    )

        return issues

    def _check_print_usage(self) -> list[AuditIssue]:
        issues: list[AuditIssue] = []

        if self.tree is None:
            return issues

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    issues.append(
                        AuditIssue(
                            line=node.lineno,
                            severity=2,
                            category="observability",
                            problem="Direct print() call found.",
                            recommendation=(
                                "Use logging for production code, or keep print only for CLI output."
                            ),
                        )
                    )

        return issues

    def _check_magic_numbers(self) -> list[AuditIssue]:
        issues: list[AuditIssue] = []

        if self.tree is None:
            return issues

        allowed_numbers = {-1, 0, 1, 2, 3, 10, 80, 88, 100, 120}

        for node in ast.walk(self.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, int):
                if node.value not in allowed_numbers:
                    issues.append(
                        AuditIssue(
                            line=getattr(node, "lineno", 0),
                            severity=3,
                            category="maintainability",
                            problem=f"Possible magic number found: {node.value}.",
                            recommendation=(
                                "Move this value into a named constant if it has domain meaning."
                            ),
                        )
                    )

        return issues


class SelfAuditImproveTool:
    """
    Tool wrapper that analyzes code and creates an implementation path.
    """

    def run(
        self,
        source_code: str,
        target: str = "<memory>",
        language: str = "python",
        goal: str = "improve reliability, maintainability, and correctness",
        strictness: str = "medium",
        allow_patch_generation: bool = True,
    ) -> AuditResult:
        if language.lower() != "python":
            return AuditResult(
                target=target,
                quality_score=0,
                issue_count=0,
                risk_summary="Only Python is supported in this implementation.",
                issues=[],
                implementation_path=[
                    "Add a language parser.",
                    "Define language-specific rules.",
                    "Add tests for the new language analyzer.",
                ],
                proposed_patches=[],
                verification_plan=[],
            )

        analyzer = PythonCodeAnalyzer(source_code, strictness=strictness)
        issues = analyzer.analyze()

        quality_score = self._calculate_quality_score(issues)
        risk_summary = self._summarize_risk(issues)
        implementation_path = self._create_implementation_path(issues, goal)
        proposed_patches = (
            self._generate_patches(issues) if allow_patch_generation else []
        )
        verification_plan = self._create_verification_plan(issues)

        return AuditResult(
            target=target,
            quality_score=quality_score,
            issue_count=len(issues),
            risk_summary=risk_summary,
            issues=issues,
            implementation_path=implementation_path,
            proposed_patches=proposed_patches,
            verification_plan=verification_plan,
        )

    @staticmethod
    def _calculate_quality_score(issues: list[AuditIssue]) -> int:
        if not issues:
            return 100

        penalty = sum(issue.severity for issue in issues)
        return max(0, 100 - penalty)

    @staticmethod
    def _summarize_risk(issues: list[AuditIssue]) -> str:
        if not issues:
            return "No significant quality risks detected."

        critical_count = sum(issue.severity >= 8 for issue in issues)
        high_count = sum(5 <= issue.severity < 8 for issue in issues)
        medium_count = sum(3 <= issue.severity < 5 for issue in issues)
        low_count = sum(issue.severity < 3 for issue in issues)

        if critical_count:
            return (
                f"Critical risks found: {critical_count}. "
                "Fix syntax and reliability issues before improving style."
            )

        if high_count:
            return (
                f"High-priority risks found: {high_count}. "
                "Main focus should be complexity and reliability."
            )

        return (
            f"No critical risks. Medium issues: {medium_count}. "
            f"Low issues: {low_count}."
        )

    def _create_implementation_path(
        self,
        issues: list[AuditIssue],
        goal: str,
    ) -> list[str]:
        path = [f"Goal: {goal}"]

        if not issues:
            path.extend(
                [
                    "Keep the current structure.",
                    "Add or strengthen tests.",
                    "Run linter, formatter, type checker, and security scanner.",
                    "Monitor future regressions.",
                ]
            )
            return path

        issue_groups = {
            "Phase 1 — Critical reliability and syntax fixes": [
                issue for issue in issues if issue.severity >= 8
            ],
            "Phase 2 — High-priority complexity and reliability fixes": [
                issue for issue in issues if 5 <= issue.severity < 8
            ],
            "Phase 3 — Maintainability and style improvements": [
                issue for issue in issues if 3 <= issue.severity < 5
            ],
            "Phase 4 — Documentation and observability polish": [
                issue for issue in issues if issue.severity < 3
            ],
        }

        for phase, grouped_issues in issue_groups.items():
            if not grouped_issues:
                continue

            path.append(phase)

            for issue in grouped_issues[:8]:
                path.append(
                    f"Line {issue.line}: {issue.problem} "
                    f"Recommended fix: {issue.recommendation}"
                )

            remaining = len(grouped_issues) - 8

            if remaining > 0:
                path.append(f"Address {remaining} additional issue(s) in this phase.")

        path.extend(
            [
                "Phase 5 — Add automated quality gates.",
                "Run formatter: black or ruff format.",
                "Run linter: ruff check.",
                "Run type checker: mypy or pyright.",
                "Run tests: pytest.",
                "Run coverage: coverage run -m pytest && coverage report.",
                "Run security scan: bandit -r .",
                "Repeat audit until quality score is acceptable.",
            ]
        )

        return path

    @staticmethod
    def _generate_patches(issues: list[AuditIssue]) -> list[ImprovementPatch]:
        categories = {issue.category for issue in issues}
        patches: list[ImprovementPatch] = []

        if "reliability" in categories:
            patches.append(
                ImprovementPatch(
                    title="Narrow exception handling",
                    reason="Broad exception handling can hide real failures.",
                    suggested_change=(
                        "Replace bare except or except Exception with specific exceptions, "
                        "then log useful context."
                    ),
                )
            )

        if "complexity" in categories:
            patches.append(
                ImprovementPatch(
                    title="Extract smaller functions",
                    reason="Complex functions are harder to test and maintain.",
                    suggested_change=(
                        "Split validation, transformation, calculation, and output into "
                        "separate functions."
                    ),
                )
            )

        if "observability" in categories:
            patches.append(
                ImprovementPatch(
                    title="Use logging where appropriate",
                    reason="Logging gives better control than print() in production.",
                    suggested_change=(
                        "Use logging.getLogger(__name__) and logger.info/warning/error "
                        "for operational messages."
                    ),
                )
            )

        if "documentation" in categories:
            patches.append(
                ImprovementPatch(
                    title="Add public API docstrings",
                    reason="Docstrings improve maintainability and onboarding.",
                    suggested_change=(
                        "Add concise docstrings to public classes and functions."
                    ),
                )
            )

        if "maintainability" in categories:
            patches.append(
                ImprovementPatch(
                    title="Remove unresolved markers and magic numbers",
                    reason="TODO/FIXME/HACK markers and unexplained numbers create future risk.",
                    suggested_change=(
                        "Convert markers into tracked tasks and move domain constants "
                        "into named variables."
                    ),
                )
            )

        return patches

    @staticmethod
    def _create_verification_plan(issues: list[AuditIssue]) -> list[str]:
        plan = [
            "Confirm the file parses successfully.",
            "Run unit tests.",
            "Run linting.",
            "Run formatting check.",
            "Run type checking.",
            "Run security scanning.",
            "Compare quality score before and after fixes.",
        ]

        categories = {issue.category for issue in issues}

        if "complexity" in categories:
            plan.append("Add tests for each newly extracted helper function.")

        if "reliability" in categories:
            plan.append("Add tests for failure paths and exception handling.")

        if "maintainability" in categories:
            plan.append("Review constants and comments for clear business meaning.")

        return plan


def result_to_dict(result: AuditResult) -> dict[str, Any]:
    return {
        "target": result.target,
        "quality_score": result.quality_score,
        "issue_count": result.issue_count,
        "risk_summary": result.risk_summary,
        "issues": [asdict(issue) for issue in result.issues],
        "implementation_path": result.implementation_path,
        "proposed_patches": [asdict(patch) for patch in result.proposed_patches],
        "verification_plan": result.verification_plan,
    }


def print_human_report(result: AuditResult) -> None:
    print("=" * 80)
    print("SELF AUDIT IMPROVE REPORT")
    print("=" * 80)
    print(f"Target: {result.target}")
    print(f"Quality score: {result.quality_score}/100")
    print(f"Issues found: {result.issue_count}")
    print(f"Risk summary: {result.risk_summary}")
    print()

    if result.issues:
        print("Issues")
        print("-" * 80)

        for issue in result.issues:
            print(
                f"Line {issue.line} | Severity {issue.severity}/10 | "
                f"{issue.category.upper()}"
            )
            print(f"Problem: {issue.problem}")
            print(f"Fix: {issue.recommendation}")
            print()

    print("Implementation Path")
    print("-" * 80)

    for index, step in enumerate(result.implementation_path, start=1):
        print(f"{index}. {step}")

    print()
    print("Proposed Patches")
    print("-" * 80)

    if result.proposed_patches:
        for patch in result.proposed_patches:
            print(f"- {patch.title}")
            print(f"  Reason: {patch.reason}")
            print(f"  Change: {patch.suggested_change}")
    else:
        print("No patches needed.")

    print()
    print("Verification Plan")
    print("-" * 80)

    for index, item in enumerate(result.verification_plan, start=1):
        print(f"{index}. {item}")


def read_target_file(argv: list[str]) -> tuple[str, str]:
    if len(argv) > 1:
        target_path = Path(argv[1])

        if not target_path.exists():
            raise FileNotFoundError(f"File does not exist: {target_path}")

        return str(target_path), target_path.read_text(encoding="utf-8")

    current_path = Path(__file__)
    return str(current_path), current_path.read_text(encoding="utf-8")


def main() -> None:
    try:
        target, source_code = read_target_file(sys.argv)

        tool = SelfAuditImproveTool()
        result = tool.run(
            source_code=source_code,
            target=target,
            language="python",
            goal="improve reliability, maintainability, correctness, and testability",
            strictness="medium",
            allow_patch_generation=True,
        )

        print_human_report(result)

        json_path = Path("self_audit_report.json")
        json_path.write_text(
            json.dumps(result_to_dict(result), indent=2),
            encoding="utf-8",
        )

        print()
        print(f"JSON report written to: {json_path}")

    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    except OSError as error:
        print(f"File system error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
