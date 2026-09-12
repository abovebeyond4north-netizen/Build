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
    failures: int
    evaluated: int
    expected: int

    @property
    def failure_rate(self) -> float:
        return self.failures / self.evaluated if self.evaluated else 0.0


class CaseMiner:
    """Mine extra validation cases from archive failures and disagreement.

    Mining sources deliberately mix behavioural niches, recent stepping stones,
    and historical leaders rather than trusting historical scores alone. This
    keeps adaptive evaluation pressure relevant as the curriculum changes without
    introducing a circular dependency on the current oracle.
    """

    def __init__(self, value_min: int, value_max: int, limit: int = 24) -> None:
        for name, value in (("value_min", value_min), ("value_max", value_max)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if value_min > value_max:
            raise ValueError("value_min must not exceed value_max")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        self.value_min = value_min
        self.value_max = value_max
        self.limit = limit

    def mine(self, records: list[ArchiveRecord]) -> list[BenchmarkCase]:
        expressions = select_mining_expressions(records, limit=32)
        if len(expressions) < 2 or self.limit == 0:
            return []
        candidates: list[MinedCase] = []
        step = max(1, (self.value_max - self.value_min) // 12)
        values = list(range(self.value_min, self.value_max + 1, step))
        for a in values:
            for b in values:
                expected = target_function(a, b)
                outputs: set[int | str] = set()
                failures = 0
                for expression in expressions:
                    try:
                        value = eval_expr(expression, a, b)
                        outputs.add(value)
                        if value != expected:
                            failures += 1
                    except Exception as exc:
                        outputs.add(type(exc).__name__)
                        failures += 1
                if failures > 0:
                    candidates.append(
                        MinedCase(
                            a=a,
                            b=b,
                            disagreement=len(outputs),
                            failures=failures,
                            evaluated=len(expressions),
                            expected=expected,
                        )
                    )
        ranked = sorted(
            candidates,
            key=lambda item: (
                item.failure_rate,
                item.disagreement,
                abs(item.a) + abs(item.b),
            ),
            reverse=True,
        )
        return [
            BenchmarkCase(f"mined_{idx}", item.a, item.b, item.expected)
            for idx, item in enumerate(ranked[: self.limit])
        ]

    def write(self, path: Path, cases: list[BenchmarkCase]) -> None:
        payload = [asdict(case) for case in cases]
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def select_mining_expressions(
    records: list[ArchiveRecord],
    limit: int = 32,
) -> list[str]:
    """Select bounded, diverse archive expressions without stale-score monopoly."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    if limit == 0 or not records:
        return []

    historical = sorted(
        records,
        key=lambda record: record.score.get("weighted_total", 0.0),
        reverse=True,
    )
    recent = list(reversed(records))

    bucket_best: dict[str, ArchiveRecord] = {}
    for record in historical:
        bucket = record.bucket or "unknown"
        bucket_best.setdefault(bucket, record)
    niches = list(bucket_best.values())

    sources = (niches, recent, historical)
    positions = [0, 0, 0]
    seen: set[str] = set()
    output: list[str] = []
    while len(output) < limit:
        progressed = False
        for source_index, source in enumerate(sources):
            while positions[source_index] < len(source):
                record = source[positions[source_index]]
                positions[source_index] += 1
                if record.expression in seen:
                    continue
                seen.add(record.expression)
                output.append(record.expression)
                progressed = True
                break
            if len(output) >= limit:
                break
        if not progressed:
            break
    return output


def unique_expressions(records: list[ArchiveRecord]) -> list[str]:
    """Backward-compatible unbounded expression selection."""
    return select_mining_expressions(records, limit=len(records))
