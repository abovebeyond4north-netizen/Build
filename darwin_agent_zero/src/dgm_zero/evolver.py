from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from .archive import Archive, ArchiveRecord
from .decision_matrix import DecisionMatrix
from .memory import KnowledgeBank
from .oracle import EmpiricalGodelOracle
from .self_instruction import SelfInstructor
from .tools import ToolRegistry, default_registry


SEED_EXPRESSIONS = [
    "a + b",
    "a * a + b",
    "a * a + 3 * b",
    "a * a + 3 * b - gcd(a, b)",
    "abs(a) + abs(b)",
    "a * a - gcd(a, b)",
    "a * a + b + b + b",
]

MUTATION_SNIPPETS = [
    " + 1",
    " - 1",
    " + b",
    " - b",
    " + 3 * b",
    " + b + b + b",
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
    elite_buckets: dict[str, str]
    registered_tools: list[str]
    recalled_tasks: list[str]


class DarwinAgentZero:
    """Bounded Darwinian Gödel loop for local tool evolution.

    The prototype evolves arithmetic tool expressions rather than arbitrary code.
    This keeps the loop safe while preserving the essential architecture: propose,
    evaluate, score, archive, remember, and select from prior stepping stones.
    """

    def __init__(self, workspace: Path, config: EvolutionConfig | None = None, registry: ToolRegistry | None = None) -> None:
        self.workspace = workspace
        self.archive = Archive(workspace)
        self.memory = KnowledgeBank(workspace)
        self.config = config or EvolutionConfig()
        self.rng = random.Random(self.config.seed)
        self.matrix = DecisionMatrix(accept_threshold=self.config.accept_threshold)
        self.oracle = EmpiricalGodelOracle(self.archive, self.matrix)
        self.instructor = SelfInstructor(self.memory)
        self.registry = registry or default_registry()

    def run(self) -> EvolutionReport:
        parent: ArchiveRecord | None = self.archive.champion()
        for generation in range(self.config.generations):
            tasks = self.instructor.create_tasks(parent)
            self.memory.deposit("generation", f"generation={generation}; tasks={len(tasks)}", 0.5)
            candidates = self.self_instruct(parent, generation)
            for expr in candidates[: self.config.population]:
                self.evaluate_and_archive(expr, parent, generation)
            parent = self.archive.champion()

        champion = self.archive.champion()
        if champion:
            self.write_champion(champion)
            self.memory.deposit("champion", champion.expression, champion.score.get("weighted_total", 0.0))
        self.memory.prune()
        elites = self.archive.elites_by_bucket()
        report = EvolutionReport(
            generations=self.config.generations,
            population=self.config.population,
            total_records=len(self.archive.records()),
            accepted_records=len(self.archive.accepted()),
            champion_id=champion.id if champion else None,
            champion_expression=champion.expression if champion else None,
            champion_score=champion.score if champion else None,
            elite_buckets={bucket: record.id for bucket, record in sorted(elites.items())},
            registered_tools=self.registry.names(),
            recalled_tasks=[entry.content for entry in self.memory.recall("task", limit=5)],
        )
        (self.workspace / "evolution_report.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        return report

    def self_instruct(self, parent: ArchiveRecord | None, generation: int) -> list[str]:
        """Generate improvement candidates from champion, elites, seeds, and memory."""

        if parent is None:
            base_pool = SEED_EXPRESSIONS[:]
        else:
            base_pool = [parent.expression] + SEED_EXPRESSIONS

        for elite in self.archive.elites_by_bucket().values():
            if elite.expression not in base_pool:
                base_pool.append(elite.expression)

        for memory in self.memory.recall("champion", limit=3):
            if memory.content not in base_pool:
                base_pool.append(memory.content)

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
        mode = self.rng.choice(["wrap", "append", "replace", "simplify"])
        if mode == "wrap":
            return f"({expression}){self.rng.choice(MUTATION_SNIPPETS)}"
        if mode == "append":
            return f"{expression}{self.rng.choice(MUTATION_SNIPPETS)}"
        if mode == "simplify":
            return expression.replace("b + b + b", "3 * b").replace("(a * a)", "a * a")
        return self.rng.choice(SEED_EXPRESSIONS)

    def evaluate_and_archive(self, expression: str, parent: ArchiveRecord | None, generation: int) -> ArchiveRecord:
        parent_score = parent.score.get("weighted_total") if parent else None
        decision = self.oracle.judge(expression, parent_total=parent_score)
        usefulness = decision.score.weighted_total
        self.memory.deposit("candidate", f"{expression} -> {decision.reason}", usefulness)
        return self.archive.append(
            generation=generation,
            parent_id=parent.id if parent else None,
            expression=expression,
            score=decision.score.as_dict(),
            accepted=decision.accepted,
            reason=decision.reason,
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
