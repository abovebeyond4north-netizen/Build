from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HealthCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class HealthReport:
    passed: bool
    checks: list[HealthCheck]
    summary: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunHealthAuditor:
    """Post-run diagnostic audit for evolution health.

    This does not decide scientific truth. It verifies basic internal consistency
    and confirms that the run produced meaningful search-state artifacts.
    """

    @staticmethod
    def _is_nonnegative_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def audit(self, report: Any) -> HealthReport:
        total_records = getattr(report, "total_records", 0)
        accepted_records = getattr(report, "accepted_records", 0)
        champion_expression = getattr(report, "champion_expression", None)
        map_elites_cells = getattr(report, "map_elites_cells", 0)
        cognitive_state = getattr(report, "cognitive_state", {})
        operator_bandit = getattr(report, "operator_bandit", {})

        total_valid = self._is_nonnegative_int(total_records) and total_records > 0
        accepted_valid = (
            self._is_nonnegative_int(accepted_records)
            and accepted_records > 0
            and self._is_nonnegative_int(total_records)
            and accepted_records <= total_records
        )
        champion_valid = (
            isinstance(champion_expression, str)
            and bool(champion_expression.strip())
        )
        map_elites_valid = (
            self._is_nonnegative_int(map_elites_cells)
            and map_elites_cells > 0
        )
        cognitive_valid = isinstance(cognitive_state, dict) and bool(cognitive_state)
        bandit_valid = isinstance(operator_bandit, dict) and bool(operator_bandit)

        checks = [
            HealthCheck(
                "archive_records",
                total_valid,
                f"records={total_records!r}",
            ),
            HealthCheck(
                "champion_exists",
                champion_valid,
                f"champion={champion_expression!r}",
            ),
            HealthCheck(
                "accepted_candidates",
                accepted_valid,
                f"accepted={accepted_records!r}; total={total_records!r}",
            ),
            HealthCheck(
                "map_elites_cells",
                map_elites_valid,
                f"cells={map_elites_cells!r}",
            ),
            HealthCheck(
                "cognitive_state_present",
                cognitive_valid,
                (
                    f"focus={cognitive_state.get('focus')!r}"
                    if isinstance(cognitive_state, dict)
                    else f"state_type={type(cognitive_state).__name__}"
                ),
            ),
            HealthCheck(
                "operator_bandit_present",
                bandit_valid,
                (
                    f"operators={sorted(operator_bandit.keys())}"
                    if isinstance(operator_bandit, dict)
                    else f"bandit_type={type(operator_bandit).__name__}"
                ),
            ),
        ]
        passed = all(check.passed for check in checks)
        return HealthReport(
            passed=passed,
            checks=checks,
            summary="healthy" if passed else "needs_attention",
        )

    def write(self, path: Path, report: HealthReport) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.write_text(
            json.dumps(report.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(path)
