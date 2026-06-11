from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from .archive import Archive, ArchiveRecord
from .benchmark import BenchmarkConfig
from .case_miner import CaseMiner
from .curriculum import CurriculumManager, CurriculumState
from .decision_matrix import DecisionMatrix
from .map_elites import MAPElitesGrid
from .memory import KnowledgeBank
from .meta_learning import MetaLearner, MetaLearningPolicy
from .metacognition import CognitiveState, MetacognitiveMonitor
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
    elite_parent_limit: int = 16
    curriculum_enabled: bool = True
    mined_case_limit: int = 24


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
    map_elites_cells: int
    map_elites_path: str
    curriculum: dict[str, object]
    mined_cases: int
    mined_cases_path: str
    cognitive_state: dict[str, object]
    meta_policy: dict[str, float]
    registered_tools: list[str]
    recalled_tasks: list[str]


class DarwinAgentZero:
    """Bounded Darwinian Godel loop with metacognitive control."""

    def __init__(self, workspace: Path, config: EvolutionConfig | None = None, registry: ToolRegistry | None = None) -> None:
        self.workspace = workspace
        self.archive = Archive(workspace)
        self.memory = KnowledgeBank(workspace)
        self.config = config or EvolutionConfig()
        self.rng = random.Random(self.config.seed)
        self.matrix = DecisionMatrix(accept_threshold=self.config.accept_threshold)
        self.curriculum = CurriculumManager(workspace)
        self.curriculum_state = self.curriculum.load()
        self.metacognition = MetacognitiveMonitor()
        self.meta_learner = MetaLearner()
        self.cognitive_state = self.assess_self()
        self.meta_policy = self.meta_learner.policy_from_state(self.cognitive_state)
        self.mined_cases = self.mine_cases()
        self.oracle = self.make_oracle(self.curriculum_state)
        self.instructor = SelfInstructor(self.memory)
        self.registry = registry or default_registry()
        self.map_elites = MAPElitesGrid().build(self.archive.records())

    def assess_self(self) -> CognitiveState:
        return self.metacognition.assess(
            self.archive.records(),
            elite_cell_count=len(getattr(self, "map_elites", MAPElitesGrid()).cells),
            mined_case_count=len(getattr(self, "mined_cases", ())),
        )

    def mine_cases(self):
        level = self.curriculum_state.current
        miner = CaseMiner(level.value_min, level.value_max, self.config.mined_case_limit)
        cases = miner.mine(self.archive.records())
        miner.write(self.workspace / "mined_cases.json", cases)
        return tuple(cases)

    def make_oracle(self, state: CurriculumState) -> EmpiricalGodelOracle:
        level = state.current
        benchmark_config = BenchmarkConfig(
            value_min=level.value_min,
            value_max=level.value_max,
            train_count=level.train_count,
            validation_count=level.validation_count,
            adversarial_scale=level.adversarial_scale,
        )
        return EmpiricalGodelOracle(self.archive, self.matrix, benchmark_config, self.mined_cases)

    def run(self) -> EvolutionReport:
        parent: ArchiveRecord | None = self.archive.champion()
        for generation in range(self.config.generations):
            self.map_elites = MAPElitesGrid().build(self.archive.records())
            self.mined_cases = self.mine_cases()
            self.cognitive_state = self.assess_self()
            self.meta_policy = self.meta_learner.policy_from_state(self.cognitive_state)
            self.metacognition.write(self.workspace / "cognitive_state.json", self.cognitive_state)
            self.oracle = self.make_oracle(self.curriculum_state)
            tasks = self.instructor.create_tasks(parent)
            level = self.curriculum_state.current
            self.memory.deposit(
                "metacognition",
                f"focus={self.cognitive_state.focus}; critique={self.cognitive_state.critique}",
                self.cognitive_state.confidence,
            )
            self.memory.deposit(
                "generation",
                f"generation={generation}; tasks={len(tasks)}; elite_cells={len(self.map_elites.cells)}; curriculum_level={level.level}; mined_cases={len(self.mined_cases)}; focus={self.cognitive_state.focus}",
                0.5,
            )
            candidates = self.self_instruct(parent, generation)
            for expr in candidates[: self.config.population]:
                record = self.evaluate_and_archive(expr, parent, generation)
                self.map_elites.add(record)
            parent = self.select_parent()

        champion = self.archive.champion()
        if champion:
            self.write_champion(champion)
            self.memory.deposit("champion", champion.expression, champion.score.get("weighted_total", 0.0))
        self.memory.prune()
        champion_total = champion.score.get("weighted_total", 0.0) if champion else None
        if self.config.curriculum_enabled:
            self.curriculum_state = self.curriculum.update_after_run(champion_total)
            self.mined_cases = self.mine_cases()
            self.oracle = self.make_oracle(self.curriculum_state)
        else:
            self.curriculum.save(self.curriculum_state)
        self.map_elites = MAPElitesGrid().build(self.archive.records())
        self.cognitive_state = self.assess_self()
        self.meta_policy = self.meta_learner.policy_from_state(self.cognitive_state)
        self.metacognition.write(self.workspace / "cognitive_state.json", self.cognitive_state)
        map_path = self.workspace / "map_elites.json"
        self.map_elites.write(map_path)
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
            map_elites_cells=len(self.map_elites.cells),
            map_elites_path=str(map_path),
            curriculum=asdict(self.curriculum_state),
            mined_cases=len(self.mined_cases),
            mined_cases_path=str(self.workspace / "mined_cases.json"),
            cognitive_state=asdict(self.cognitive_state),
            meta_policy=asdict(self.meta_policy),
            registered_tools=self.registry.names(),
            recalled_tasks=[entry.content for entry in self.memory.recall("task", limit=5)],
        )
        (self.workspace / "evolution_report.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        return report

    def select_parent(self) -> ArchiveRecord | None:
        accepted = self.archive.accepted()
        if not accepted:
            return None
        elite_ids = {cell.record_id for cell in self.map_elites.cells.values()}
        elite_records = [record for record in accepted if record.id in elite_ids]
        pool = elite_records or accepted
        pool = sorted(pool, key=lambda record: record.score.get("weighted_total", 0.0), reverse=True)[: self.config.elite_parent_limit]
        if self.cognitive_state.focus in {"increase diversity", "escape stagnation"} and elite_records:
            return self.rng.choice(elite_records)
        return self.rng.choice(pool)

    def self_instruct(self, parent: ArchiveRecord | None, generation: int) -> list[str]:
        if parent is None:
            base_pool = SEED_EXPRESSIONS[:]
        else:
            base_pool = [parent.expression] + SEED_EXPRESSIONS

        for expression in self.map_elites.elite_expressions(limit=self.config.elite_parent_limit):
            if expression not in base_pool:
                base_pool.append(expression)

        for memory in self.memory.recall("champion", limit=3):
            if memory.content not in base_pool:
                base_pool.append(memory.content)

        candidates: list[str] = []
        expansion = max(1, int((self.config.population // 2) * self.meta_policy.exploration_bias))
        for base in base_pool:
            candidates.append(base)
            for _ in range(expansion):
                candidates.append(self.mutate(base, generation))
        self.rng.shuffle(candidates)
        return dedupe(candidates)

    def mutate(self, expression: str, generation: int) -> str:
        if generation % 4 == 0 and self.meta_policy.novelty_bias >= 1.0:
            return self.rng.choice(SEED_EXPRESSIONS)
        mode = self.rng.choice(self.meta_learner.weighted_modes(self.meta_policy))
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
