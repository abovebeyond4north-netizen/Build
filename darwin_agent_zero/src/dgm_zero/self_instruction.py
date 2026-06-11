from __future__ import annotations

from dataclasses import dataclass

from .archive import ArchiveRecord
from .memory import KnowledgeBank


@dataclass(frozen=True)
class ImprovementTask:
    title: str
    instruction: str
    priority: float


class SelfInstructor:
    """Generates local improvement pressure from failures and memory."""

    def __init__(self, memory: KnowledgeBank) -> None:
        self.memory = memory

    def create_tasks(self, champion: ArchiveRecord | None) -> list[ImprovementTask]:
        tasks: list[ImprovementTask] = []
        if champion is None:
            tasks.append(
                ImprovementTask(
                    "bootstrap baseline",
                    "Search simple candidate expressions and establish the first accepted tool.",
                    1.0,
                )
            )
            return tasks

        total = champion.score.get("weighted_total", 0.0)
        correctness = champion.score.get("correctness", 0.0)
        novelty = champion.score.get("novelty", 0.0)
        simplicity = champion.score.get("simplicity", 0.0)

        if correctness < 1.0:
            tasks.append(ImprovementTask("improve correctness", "Prefer mutations that repair failed benchmark cases.", 0.95))
        if novelty < 0.35:
            tasks.append(ImprovementTask("increase novelty", "Explore structurally different candidate expressions.", 0.60))
        if simplicity < 0.60:
            tasks.append(ImprovementTask("compress tool", "Prefer shorter expressions with equal benchmark performance.", 0.50))
        if total >= 0.90:
            tasks.append(ImprovementTask("raise curriculum", "Generate harder hidden validation tasks next run.", 0.80))

        if not tasks:
            tasks.append(ImprovementTask("maintain exploration", "Mutate the champion and preserve diverse stepping stones.", 0.40))

        for task in tasks:
            self.memory.deposit("task", f"{task.title}: {task.instruction}", task.priority)
        return tasks
