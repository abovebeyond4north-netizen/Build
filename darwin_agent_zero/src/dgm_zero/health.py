from __future__ import annotations

import json
import math
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

    This does not decide scientific truth. It verifies internal consistency and
    confirms that the run produced meaningful, numerically valid search-state
    artifacts before checkpoint promotion is allowed.
    """

    @staticmethod
    def _is_nonnegative_int(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    @staticmethod
    def _is_unit_number(value: object) -> bool:
        return (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(float(value))
            and 0.0 <= float(value) <= 1.0
        )

    @classmethod
    def _valid_cognitive_state(cls, state: object) -> bool:
        if not isinstance(state, dict) or not state:
            return False
        required_numeric = (
            "confidence",
            "uncertainty",
            "stagnation",
            "diversity",
            "safety_pressure",
        )
        if any(not cls._is_unit_number(state.get(name)) for name in required_numeric):
            return False
        return all(
            isinstance(state.get(name), str) and bool(state[name].strip())
            for name in ("focus", "critique")
        )

    @staticmethod
    def _valid_bandit_state(state: object) -> bool:
        if not isinstance(state, dict) or not state:
            return False
        for name, arm in state.items():
            if not isinstance(name, str) or not name or not isinstance(arm, dict):
                return False
            pulls = arm.get("pulls")
            reward_sum = arm.get("reward_sum")
            mean_reward = arm.get("mean_reward")
            if (
                isinstance(pulls, bool)
                or not isinstance(pulls, (int, float))
                or not math.isfinite(float(pulls))
                or float(pulls) < 0.0
                or not float(pulls).is_integer()
            ):
                return False
            if (
                isinstance(reward_sum, bool)
                or not isinstance(reward_sum, (int, float))
                or not math.isfinite(float(reward_sum))
                or float(reward_sum) < 0.0
                or float(reward_sum) > float(pulls)
            ):
                return False
            if (
                isinstance(mean_reward, bool)
                or not isinstance(mean_reward, (int, float))
                or not math.isfinite(float(mean_reward))
                or not 0.0 <= float(mean_reward) <= 1.0
            ):
                return False
            expected_mean = (
                float(reward_sum) / float(pulls)
                if float(pulls) > 0.0
                else 0.0
            )
            if not math.isclose(
                float(mean_reward),
                expected_mean,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                return False
        return True

    @classmethod
    def _valid_champion_score(cls, score: object) -> bool:
        if not isinstance(score, dict) or not score:
            return False
        weighted_total = score.get("weighted_total")
        if not cls._is_unit_number(weighted_total):
            return False
        for name, value in score.items():
            if name == "weighted_total":
                continue
            if not isinstance(name, str) or not name or not cls._is_unit_number(value):
                return False
        return True

    def audit(self, report: Any) -> HealthReport:
        total_records = getattr(report, "total_records", 0)
        accepted_records = getattr(report, "accepted_records", 0)
        champion_expression = getattr(report, "champion_expression", None)
        champion_score = getattr(report, "champion_score", None)
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
        champion_score_valid = self._valid_champion_score(champion_score)
        map_elites_valid = (
            self._is_nonnegative_int(map_elites_cells)
            and map_elites_cells > 0
        )
        cognitive_valid = self._valid_cognitive_state(cognitive_state)
        bandit_valid = self._valid_bandit_state(operator_bandit)

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
                "champion_score_valid",
                champion_score_valid,
                (
                    f"weighted_total={champion_score.get('weighted_total')!r}"
                    if isinstance(champion_score, dict)
                    else f"score_type={type(champion_score).__name__}"
                ),
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
                "cognitive_state_valid",
                cognitive_valid,
                (
                    f"focus={cognitive_state.get('focus')!r}"
                    if isinstance(cognitive_state, dict)
                    else f"state_type={type(cognitive_state).__name__}"
                ),
            ),
            HealthCheck(
                "operator_bandit_valid",
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
