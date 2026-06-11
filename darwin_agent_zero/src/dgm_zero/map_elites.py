from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .archive import ArchiveRecord


@dataclass(frozen=True)
class EliteCell:
    """Best known artifact inside one MAP-Elites descriptor cell."""

    key: str
    axes: dict[str, str]
    record_id: str
    expression: str
    score: dict[str, float]
    generation: int


class MAPElitesGrid:
    """Small MAP-Elites grid for open-ended stepping-stone preservation.

    MAP-Elites keeps a best candidate for each behaviour descriptor instead of
    collapsing the whole population into one champion. That gives evolution more
    stepping stones and helps it escape local optima.
    """

    def __init__(self) -> None:
        self.cells: dict[str, EliteCell] = {}

    def add(self, record: ArchiveRecord) -> bool:
        if not record.accepted:
            return False
        key, axes = descriptor(record)
        candidate = EliteCell(
            key=key,
            axes=axes,
            record_id=record.id,
            expression=record.expression,
            score=record.score,
            generation=record.generation,
        )
        current = self.cells.get(key)
        if current is None or fitness(candidate) > fitness(current):
            self.cells[key] = candidate
            return True
        return False

    def build(self, records: list[ArchiveRecord]) -> "MAPElitesGrid":
        for record in records:
            self.add(record)
        return self

    def elite_expressions(self, limit: int = 32) -> list[str]:
        ranked = sorted(self.cells.values(), key=fitness, reverse=True)
        return [cell.expression for cell in ranked[:limit]]

    def summary(self) -> dict[str, object]:
        cells = sorted(self.cells.values(), key=lambda cell: cell.key)
        return {
            "cell_count": len(cells),
            "cells": [asdict(cell) for cell in cells],
        }

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.summary(), indent=2, sort_keys=True), encoding="utf-8")


def descriptor(record: ArchiveRecord) -> tuple[str, dict[str, str]]:
    axes = {
        "length": length_axis(record.expression),
        "correctness": score_axis(record.score.get("correctness", 0.0), "C"),
        "novelty": score_axis(record.score.get("novelty", 0.0), "N"),
        "simplicity": score_axis(record.score.get("simplicity", 0.0), "S"),
        "behavior": record.bucket or "unknown",
    }
    key = "|".join(f"{name}={value}" for name, value in axes.items())
    return key, axes


def length_axis(expression: str) -> str:
    size = len(expression)
    if size <= 24:
        return "xs"
    if size <= 48:
        return "s"
    if size <= 96:
        return "m"
    return "l"


def score_axis(value: float, prefix: str) -> str:
    if value >= 0.95:
        return f"{prefix}100"
    if value >= 0.75:
        return f"{prefix}75"
    if value >= 0.50:
        return f"{prefix}50"
    if value >= 0.25:
        return f"{prefix}25"
    return f"{prefix}0"


def fitness(cell: EliteCell) -> float:
    return float(cell.score.get("weighted_total", 0.0))
