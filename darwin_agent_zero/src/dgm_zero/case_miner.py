from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .archive import ArchiveRecord
from .benchmark import BenchmarkCase, eval_expr, target_function


@dataclass(frozen=True)
class MinedCase:
    a: int
    b: int
    disagreement: int
    expected: int


class CaseMiner:
    """Mine extra validation cases from archive disagreement.

    Static tests are useful, but open-ended systems need pressure that adapts to
    what they have already tried. This miner evaluates archived expressions over
    a bounded grid and finds inputs where candidates disagree most. Those cases
    become extra validation pressure in later oracle checks.
    """

    def __init__(self, value_min: int, value_max: int, limit: int = 24) -> None:
        self.value_min = value_min
        self.value_max = value_max
        self.limit = limit

    def mine(self, records: list[ArchiveRecord]) -> list[BenchmarkCase]:
        expressions = unique_expressions(records)
        if len(expressions) < 2:
            return []
        candidates: list[MinedCase] = []
        step = max(1, (self.value_max - self.value_min) // 12)
        values = list(range(self.value_min, self.value_max + 1, step))
        for a in values:
            for b in values:
                outputs: set[int | str] = set()
                for expression in expressions[:32]:
                    try:
                        outputs.add(eval_expr(expression, a, b))
                    except Exception as exc:
                        outputs.add(type(exc).__name__)
                if len(outputs) > 1:
                    candidates.append(MinedCase(a=a, b=b, disagreement=len(outputs), expected=target_function(a, b)))
        ranked = sorted(candidates, key=lambda item: (item.disagreement, abs(item.a) + abs(item.b)), reverse=True)
        return [BenchmarkCase(f"mined_{idx}", item.a, item.b, item.expected) for idx, item in enumerate(ranked[: self.limit])]

    def write(self, path: Path, cases: list[BenchmarkCase]) -> None:
        payload = [asdict(case) for case in cases]
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def unique_expressions(records: list[ArchiveRecord]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    ranked = sorted(records, key=lambda record: record.score.get("weighted_total", 0.0), reverse=True)
    for record in ranked:
        if record.expression not in seen:
            seen.add(record.expression)
            output.append(record.expression)
    return output
