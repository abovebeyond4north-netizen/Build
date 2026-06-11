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

    This does not decide scientific truth. It checks whether a run produced the
    expected artifacts and whether the search process has basic signs of life.
    """

    def audit(self, report: Any) -> HealthReport:
        checks = [
            HealthCheck(
                "archive_records",
                getattr(report, "total_records", 0) > 0,
                f"records={getattr(report, 'total_records', 0)}",
            ),
            HealthCheck(
                "champion_exists",
                getattr(report, "champion_expression", None) is not None,
                f"champion={getattr(report, 'champion_expression', None)}",
            ),
            HealthCheck(
                "accepted_candidates",
                getattr(report, "accepted_records", 0) > 0,
                f"accepted={getattr(report, 'accepted_records', 0)}",
            ),
            HealthCheck(
                "map_elites_cells",
                getattr(report, "map_elites_cells", 0) >= 0,
                f"cells={getattr(report, 'map_elites_cells', 0)}",
            ),
            HealthCheck(
                "cognitive_state_present",
                bool(getattr(report, "cognitive_state", {})),
                f"focus={getattr(report, 'cognitive_state', {}).get('focus') if isinstance(getattr(report, 'cognitive_state', {}), dict) else None}",
            ),
            HealthCheck(
                "operator_bandit_present",
                bool(getattr(report, "operator_bandit", {})),
                f"operators={sorted(getattr(report, 'operator_bandit', {}).keys()) if isinstance(getattr(report, 'operator_bandit', {}), dict) else []}",
            ),
        ]
        passed = all(check.passed for check in checks)
        summary = "healthy" if passed else "needs_attention"
        return HealthReport(passed=passed, checks=checks, summary=summary)

    def write(self, path: Path, report: HealthReport) -> None:
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
