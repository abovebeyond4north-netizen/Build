from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CurriculumLevel:
    level: int
    value_min: int
    value_max: int
    train_count: int
    validation_count: int
    adversarial_scale: int

    def __post_init__(self) -> None:
        integer_fields = (
            "level",
            "value_min",
            "value_max",
            "train_count",
            "validation_count",
            "adversarial_scale",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"curriculum {name} must be an integer")
        if not 0 <= self.level <= 6:
            raise ValueError("curriculum level must be between 0 and 6")
        if self.value_min > self.value_max:
            raise ValueError("curriculum value_min must not exceed value_max")
        if self.train_count <= 0 or self.validation_count <= 0:
            raise ValueError("curriculum case counts must be positive")
        if self.adversarial_scale <= 0:
            raise ValueError("curriculum adversarial_scale must be positive")


@dataclass(frozen=True)
class CurriculumState:
    current: CurriculumLevel
    best_score_seen: float = 0.0
    stable_successes: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.current, CurriculumLevel):
            raise ValueError("current curriculum must be a CurriculumLevel")
        if (
            isinstance(self.best_score_seen, bool)
            or not isinstance(self.best_score_seen, (int, float))
            or not math.isfinite(float(self.best_score_seen))
            or not 0.0 <= float(self.best_score_seen) <= 1.0
        ):
            raise ValueError("best_score_seen must be finite and between 0 and 1")
        if (
            isinstance(self.stable_successes, bool)
            or not isinstance(self.stable_successes, int)
            or self.stable_successes < 0
        ):
            raise ValueError("stable_successes must be a non-negative integer")


class CurriculumManager:
    """Adaptive benchmark pressure for continued growth.

    When the champion repeatedly scores high, the curriculum expands the input
    range, case count, and adversarial scale. Persistent state is validated and
    written atomically so corrupted curriculum data cannot silently distort future
    recursive-improvement evidence.
    """

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "curriculum.json"
        workspace.mkdir(parents=True, exist_ok=True)

    def load(self) -> CurriculumState:
        if not self.path.exists():
            return CurriculumState(current=self.level_for(0))
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
                raise ValueError("curriculum state must contain a current level object")
            level = CurriculumLevel(**data["current"])
            return CurriculumState(
                current=level,
                best_score_seen=data.get("best_score_seen", 0.0),
                stable_successes=data.get("stable_successes", 0),
            )
        except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"invalid curriculum state: {exc}") from exc

    def save(self, state: CurriculumState) -> None:
        if not isinstance(state, CurriculumState):
            raise ValueError("state must be a CurriculumState")
        payload = json.dumps(asdict(state), indent=2, sort_keys=True)
        temp_path = self.path.with_name(f".{self.path.name}.{time.time_ns()}.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(self.path)

    def update_after_run(
        self,
        champion_score: float | None,
        *,
        progression_bias: float = 1.0,
    ) -> CurriculumState:
        state = self.load()
        if champion_score is None:
            self.save(state)
            return state
        if (
            isinstance(champion_score, bool)
            or not isinstance(champion_score, (int, float))
            or not math.isfinite(float(champion_score))
            or not 0.0 <= float(champion_score) <= 1.0
        ):
            raise ValueError("champion_score must be finite and between 0 and 1")
        if not math.isfinite(progression_bias) or progression_bias <= 0:
            raise ValueError("progression_bias must be finite and positive")

        bounded_bias = max(0.5, min(1.5, progression_bias))
        success_threshold = max(
            0.90,
            min(0.98, 0.94 + 0.03 * (1.0 - bounded_bias)),
        )
        stable = (
            state.stable_successes + 1
            if float(champion_score) >= success_threshold
            else 0
        )
        next_level = state.current
        if stable >= 2:
            next_level = self.level_for(state.current.level + 1)
            stable = 0
        updated = CurriculumState(
            current=next_level,
            best_score_seen=max(state.best_score_seen, float(champion_score)),
            stable_successes=stable,
        )
        self.save(updated)
        return updated

    @staticmethod
    def level_for(level: int) -> CurriculumLevel:
        if isinstance(level, bool) or not isinstance(level, int):
            raise ValueError("level must be an integer")
        level = max(0, min(level, 6))
        value_max = 30 + level * 25
        return CurriculumLevel(
            level=level,
            value_min=-value_max,
            value_max=value_max,
            train_count=64 + level * 24,
            validation_count=64 + level * 24,
            adversarial_scale=1 + level,
        )
