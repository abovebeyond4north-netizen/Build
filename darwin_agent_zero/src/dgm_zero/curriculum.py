from __future__ import annotations

import json
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


@dataclass(frozen=True)
class CurriculumState:
    current: CurriculumLevel
    best_score_seen: float = 0.0
    stable_successes: int = 0


class CurriculumManager:
    """Adaptive benchmark pressure for continued growth.

    When the champion repeatedly scores high, the curriculum expands the input
    range, case count, and adversarial scale. This prevents the system from
    treating one solved toy benchmark as permanent success.
    """

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "curriculum.json"
        workspace.mkdir(parents=True, exist_ok=True)

    def load(self) -> CurriculumState:
        if not self.path.exists():
            return CurriculumState(current=self.level_for(0))
        data = json.loads(self.path.read_text(encoding="utf-8"))
        level = CurriculumLevel(**data["current"])
        return CurriculumState(current=level, best_score_seen=data.get("best_score_seen", 0.0), stable_successes=data.get("stable_successes", 0))

    def save(self, state: CurriculumState) -> None:
        self.path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")

    def update_after_run(self, champion_score: float | None) -> CurriculumState:
        state = self.load()
        if champion_score is None:
            self.save(state)
            return state

        stable = state.stable_successes + 1 if champion_score >= 0.94 else 0
        next_level = state.current
        if stable >= 2:
            next_level = self.level_for(state.current.level + 1)
            stable = 0
        updated = CurriculumState(
            current=next_level,
            best_score_seen=max(state.best_score_seen, champion_score),
            stable_successes=stable,
        )
        self.save(updated)
        return updated

    @staticmethod
    def level_for(level: int) -> CurriculumLevel:
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
