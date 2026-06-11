from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from .archive import Archive, ArchiveRecord
from .benchmark import evaluate_expression
from .decision_matrix import DecisionMatrix
from .safety import scan_source


SEED_EXPRESSIONS = [
    "a + b",
    "a * a + b",
    "a * a + 3 * b",
    "a * a + 3 * b - gcd(a, b)",
    "abs(a) + abs(b)",
]

MUTATION_SNIPPETS = [
    " + 1",
    " - 1",
    " + b",
    " - b",
    " + 3 * b",
    " - gcd(a, b)",
    " + gcd(a, b)",
    " + a * a",
    " - a",
    " + abs(b)",
]


@dataclass(frozen=True)
class EvolutionConfig:
    generations: int = 12
    population: int = 6
    seed: int = 11
    accept_threshold: float = 0.72


@dataclass(frozen=True)
class EvolutionReport:
    generations: int
    population: int
    total_records: int
    accepted_records: int
    champion_id: str | None
    champion_expression: str | None
    champion_score: dict[str, float] | None


class DarwinAgentZero:
    """Bounded Darwinian Gödel loop for local tool evolution.

    The prototype evolves arithmetic tool expressions rather than arbitrary code.
    This keeps the loop safe while preserving the essential architecture: propose,
    evaluate, score, archive, and select from prior stepping stones.
    """

    def __init__(self, workspace: Path, config: EvolutionConfig | None = None) -> None:
        self.workspace = workspace
        self.archive = Archive(workspace)
        self.config = config or EvolutionConfig()
        self.rng = random.Random(self.config.seed)
        self.matrix = DecisionMatrix(accept_threshold=self.config.accept_threshold)

    def run(self) -> EvolutionReport:
        parent: ArchiveRecord | None = self.archive.champion()
        for generation in range(self.config.generations):
            candidates = self.self_instruct(parent, generation)
            for expr in candidates[: self.config.population]:
                self.evaluate_and_archive(expr, parent, generation)
            parent = self.archive.champion()

        champion = self.archive.champion()
        if champion:
            self.write_champion(champion)
        report = EvolutionReport(
            generations=self.config.generations,
            population=self.config.population,
            total_records=len(self.archive.records()),
            accepted_records=len(self.archive.accepted()),
            champion_id=champion.id if champion else None,
            champion_expression=champion.expression if champion else None,
            champion_score=champion.score if champion else None,
        )
        (self.workspace / "evolution_report.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        return report

    def self_instruct(self, parent: ArchiveRecord | None, generation: int) -> list[str]:
        """Generate improvement tasks from the current champion and archive gaps."""

        if parent is None:
            base_pool = SEED_EXPRESSIONS[:]
        else:
            base_pool = [parent.expression] + SEED_EXPRESSIONS
        candidates: list[str] = []
        for base in base_pool:
            candidates.append(base)
            for _ in range(max(1, self.config.population // 2)):
                candidates.append(self.mutate(base, generation))
        self.rng.shuffle(candidates)
        return dedupe(candidates)

    def mutate(self, expression: str, generation: int) -> str:
        if generation % 4 == 0:
            return self.rng.choice(SEED_EXPRESSIONS)
        mode = self.rng.choice(["wrap", "append", "replace"])
        if mode == "wrap":
            return f"({expression}){self.rng.choice(MUTATION_SNIPPETS)}"
        if mode == "append":
            return f"{expression}{self.rng.choice(MUTATION_SNIPPETS)}"
        return self.rng.choice(SEED_EXPRESSIONS)

    def evaluate_and_archive(self, expression: str, parent: ArchiveRecord | None, generation: int) -> ArchiveRecord:
        source = f"def solve(a, b):\n    return {expression}\n"
        safety = scan_source(source)
        benchmark = evaluate_expression(expression)
        line_count = max(1, source.count("\n"))
        simplicity = max(0.0, min(1.0, 1.0 - (len(expression) / 240.0) - (line_count / 100.0)))
        generalization = 1.0 if benchmark.correctness >= 0.95 else benchmark.correctness * 0.85
        score = self.matrix.score(
            {
                "correctness": benchmark.correctness,
                "efficiency": benchmark.efficiency,
                "novelty": self.archive.novelty(expression),
                "safety": safety.score,
                "simplicity": simplicity,
                "generalization": generalization,
            }
        )
        parent_score = parent.score.get("weighted_total") if parent else None
        accepted = safety.passed and self.matrix.accepts(score, parent_score=parent_score)
        reason = "accepted by empirical Gödel gate" if accepted else "; ".join(safety.reasons or benchmark.errors[:2] or ["below threshold"])
        return self.archive.append(
            generation=generation,
            parent_id=parent.id if parent else None,
            expression=expression,
            score=score.as_dict(),
            accepted=accepted,
            reason=reason,
        )

    def write_champion(self, champion: ArchiveRecord) -> None:
        code = "\n".join(
            [
                '"""Best evolved tool from Darwin Agent Zero."""',
                "",
                "from math import gcd",
                "",
                "",
                "def solve(a: int, b: int) -> int:",
                f"    return {champion.expression}",
                "",
            ]
        )
        (self.workspace / "champion.py").write_text(code, encoding="utf-8")


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output
