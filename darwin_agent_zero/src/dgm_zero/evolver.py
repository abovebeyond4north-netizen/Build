from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from .archive import Archive, ArchiveRecord
from .benchmark import BenchmarkConfig
from .case_miner import CaseMiner
from .checkpoint import CheckpointManager
from .curriculum import CurriculumManager, CurriculumState
from .decision_matrix import DecisionMatrix
from .health import RunHealthAuditor
from .map_elites import MAPElitesGrid
from .memory import KnowledgeBank
from .meta_learning import MetaLearner, MetaLearningPolicy
from .metacognition import CognitiveState, MetacognitiveMonitor
from .mutation import structural_replace
from .oracle import EmpiricalGodelOracle
from .provenance import ProvenanceRecorder
from .self_instruction import SelfInstructor
from .sota_methods import UCBOperatorBandit, improvement_reward, pareto_front, uncertainty_score
from .tools import ToolRegistry, default_registry


SEED_EXPRESSIONS = [
    "a + b",
    "a * a + b",
    "a * a + 2 * b",
    "a * a + 3 * b",
    "a * a + 4 * b",
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
OPERATORS = ["wrap", "append", "replace", "simplify"]


@dataclass(frozen=True)
class Candidate:
    expression: str
    operator: str


@dataclass(frozen=True)
class CurrentArchiveCandidate:
    record: ArchiveRecord
    score: dict[str, float]
    accepted: bool


@dataclass(frozen=True)
class EvolutionConfig:
    generations: int = 12
    population: int = 6
    seed: int = 11
    accept_threshold: float = 0.72
    elite_parent_limit: int = 16
    curriculum_enabled: bool = True
    mined_case_limit: int = 24
    operator_context_retention: float = 0.5


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
    operator_bandit: dict[str, dict[str, float]]
    operator_bandit_path: str
    health_path: str
    checkpoint: dict[str, object]
    provenance_path: str
    registered_tools: list[str]
    recalled_tasks: list[str]


class DarwinAgentZero:
    """Bounded Darwinian Godel loop with metacognitive and SOTA-style search control."""

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
        self.health_auditor = RunHealthAuditor()
        self.checkpoints = CheckpointManager(workspace)
        self.provenance = ProvenanceRecorder(Path(__file__).resolve().parents[2], workspace)
        self.bandit_path = self.workspace / "operator_bandit.json"
        self.operator_bandit = UCBOperatorBandit.load(self.bandit_path, OPERATORS)
        self.operator_bandit.adapt_context(
            self.operator_context_key(),
            retention=self.config.operator_context_retention,
        )
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

    def operator_context_key(self) -> str:
        """Stable mutation-credit regime, excluding per-generation novelty state."""
        level = self.curriculum_state.current
        return json.dumps(
            {
                "curriculum": asdict(level),
                "accept_threshold": self.config.accept_threshold,
                "mined_case_limit": self.config.mined_case_limit,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def run(self) -> EvolutionReport:
        parent: ArchiveRecord | None = self.select_parent()
        evaluated_expressions: set[str] = set()
        completed_generations = 0
        for generation in range(self.config.generations):
            self.map_elites = MAPElitesGrid().build(self.archive.records())
            self.mined_cases = self.mine_cases()
            self.cognitive_state = self.assess_self()
            self.meta_policy = self.meta_learner.policy_from_state(self.cognitive_state)
            self.metacognition.write(self.workspace / "cognitive_state.json", self.cognitive_state)
            self.oracle = self.make_oracle(self.curriculum_state)
            parent_total = self.current_parent_total(parent)
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
            evaluated_count = 0
            for candidate in candidates:
                if candidate.expression in evaluated_expressions:
                    continue
                evaluated_expressions.add(candidate.expression)
                record = self.evaluate_and_archive(
                    candidate,
                    parent,
                    generation,
                    parent_total=parent_total,
                )
                self.map_elites.add(record)
                evaluated_count += 1
                if evaluated_count >= self.config.population:
                    break
            completed_generations = generation + 1
            self.operator_bandit.save(self.bandit_path)
            if evaluated_count == 0:
                self.memory.deposit(
                    "search",
                    (
                        f"generation={generation}; stop=search_space_exhausted; "
                        f"unique_evaluated={len(evaluated_expressions)}"
                    ),
                    0.9,
                )
                break
            parent = self.select_parent()

        current_champion = self.current_champion()
        champion = current_champion.record if current_champion else None
        champion_score = current_champion.score if current_champion else None
        if champion:
            self.write_champion(champion)
            self.memory.deposit(
                "champion",
                champion.expression,
                champion_score.get("weighted_total", 0.0) if champion_score else 0.0,
            )
        self.memory.prune()
        champion_total = champion_score.get("weighted_total", 0.0) if champion_score else None
        if self.config.curriculum_enabled:
            self.curriculum_state = self.curriculum.update_after_run(
                champion_total,
                progression_bias=self.meta_policy.curriculum_bias,
            )
            self.mined_cases = self.mine_cases()
            self.oracle = self.make_oracle(self.curriculum_state)
        else:
            self.curriculum.save(self.curriculum_state)
        self.operator_bandit.save(self.bandit_path)
        self.map_elites = MAPElitesGrid().build(self.archive.records())
        self.cognitive_state = self.assess_self()
        self.meta_policy = self.meta_learner.policy_from_state(self.cognitive_state)
        self.metacognition.write(self.workspace / "cognitive_state.json", self.cognitive_state)
        map_path = self.workspace / "map_elites.json"
        self.map_elites.write(map_path)
        health_path = self.workspace / "health_report.json"
        provenance_path = self.workspace / "provenance.json"
        elites = self.archive.elites_by_bucket()
        preliminary = EvolutionReport(
            generations=completed_generations,
            population=self.config.population,
            total_records=len(self.archive.records()),
            accepted_records=len(self.archive.accepted()),
            champion_id=champion.id if champion else None,
            champion_expression=champion.expression if champion else None,
            champion_score=champion_score,
            elite_buckets={bucket: record.id for bucket, record in sorted(elites.items())},
            map_elites_cells=len(self.map_elites.cells),
            map_elites_path=str(map_path),
            curriculum=asdict(self.curriculum_state),
            mined_cases=len(self.mined_cases),
            mined_cases_path=str(self.workspace / "mined_cases.json"),
            cognitive_state=asdict(self.cognitive_state),
            meta_policy=asdict(self.meta_policy),
            operator_bandit=self.operator_bandit.snapshot(),
            operator_bandit_path=str(self.bandit_path),
            health_path=str(health_path),
            checkpoint={},
            provenance_path=str(provenance_path),
            registered_tools=self.registry.names(),
            recalled_tasks=[entry.content for entry in self.memory.recall("task", limit=5)],
        )
        health = self.health_auditor.audit(preliminary)
        self.health_auditor.write(health_path, health)
        self.provenance.write(provenance_path, self.provenance.build(self.config))
        checkpoint = self.checkpoints.save_if_healthy(health_path)
        report = EvolutionReport(**{**asdict(preliminary), "checkpoint": asdict(checkpoint)})
        (self.workspace / "evolution_report.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        self.provenance.write(provenance_path, self.provenance.build(self.config))
        checkpoint = self.checkpoints.refresh(checkpoint)
        report = EvolutionReport(**{**asdict(report), "checkpoint": asdict(checkpoint)})
        (self.workspace / "evolution_report.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        self.provenance.write(provenance_path, self.provenance.build(self.config))
        self.checkpoints.refresh(checkpoint)
        return report

    def current_parent_total(self, parent: ArchiveRecord | None) -> float | None:
        """Score a parent under the same current oracle used for its children."""
        if parent is None:
            return None
        return self.oracle.judge(parent.expression).score.weighted_total

    def archive_shortlist(self) -> list[ArchiveRecord]:
        """Mix archive elites, historical leaders, and recent stepping stones."""
        accepted = self.archive.accepted()
        if not accepted:
            return []

        limit = max(1, self.config.elite_parent_limit)
        elite_ids = {cell.record_id for cell in self.map_elites.cells.values()}
        elite_records = sorted(
            (record for record in accepted if record.id in elite_ids),
            key=lambda record: record.score.get("weighted_total", 0.0),
            reverse=True,
        )
        historical = sorted(
            accepted,
            key=lambda record: record.score.get("weighted_total", 0.0),
            reverse=True,
        )
        recent = list(reversed(accepted[-limit:]))

        sources = (elite_records, historical, recent)
        positions = [0, 0, 0]
        selected: list[ArchiveRecord] = []
        seen: set[str] = set()
        while len(selected) < limit:
            progressed = False
            for source_index, source in enumerate(sources):
                while positions[source_index] < len(source):
                    record = source[positions[source_index]]
                    positions[source_index] += 1
                    if record.id in seen:
                        continue
                    seen.add(record.id)
                    selected.append(record)
                    progressed = True
                    break
                if len(selected) >= limit:
                    break
            if not progressed:
                break
        return selected

    def current_archive_candidates(self) -> list[CurrentArchiveCandidate]:
        """Re-evaluate bounded archive candidates using today's oracle."""
        evaluated: list[CurrentArchiveCandidate] = []
        for record in self.archive_shortlist():
            decision = self.oracle.judge(record.expression)
            evaluated.append(
                CurrentArchiveCandidate(
                    record=record,
                    score=decision.score.as_dict(),
                    accepted=decision.accepted,
                )
            )
        return evaluated

    def current_champion(self) -> CurrentArchiveCandidate | None:
        """Return the strongest archive member that still clears current gates."""
        current = [candidate for candidate in self.current_archive_candidates() if candidate.accepted]
        if not current:
            return None
        return max(
            current,
            key=lambda candidate: candidate.score.get("weighted_total", 0.0),
        )

    def select_parent(self) -> ArchiveRecord | None:
        current = self.current_archive_candidates()
        if not current:
            return None

        currently_accepted = [candidate for candidate in current if candidate.accepted]
        candidate_pool = currently_accepted or current
        front = pareto_front(candidate_pool)
        pool = sorted(
            front or candidate_pool,
            key=lambda candidate: candidate.score.get("weighted_total", 0.0)
            + 0.15 * uncertainty_score(candidate.score),
            reverse=True,
        )

        if self.cognitive_state.focus in {"increase diversity", "escape stagnation"}:
            elite_ids = {cell.record_id for cell in self.map_elites.cells.values()}
            elite_pool = [candidate for candidate in pool if candidate.record.id in elite_ids]
            if elite_pool:
                return self.rng.choice(elite_pool).record
        return self.rng.choice(pool).record

    def self_instruct(self, parent: ArchiveRecord | None, generation: int) -> list[Candidate]:
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

        candidates: list[Candidate] = []
        expansion = max(1, int((self.config.population // 2) * self.meta_policy.exploration_bias))
        for base in base_pool:
            candidates.append(Candidate(base, "seed"))
            for _ in range(expansion):
                candidates.append(self.mutate(base, generation))
        self.rng.shuffle(candidates)
        return dedupe_candidates(candidates)

    def choose_operator(self, generation: int) -> str:
        learned = self.operator_bandit.choose()
        policy_modes = self.meta_learner.weighted_modes(self.meta_policy)
        if not policy_modes:
            return learned

        exploration_rate = min(
            0.65,
            max(0.10, 0.20 * self.meta_policy.exploration_bias),
        )
        if self.cognitive_state.focus in {"increase diversity", "escape stagnation"}:
            exploration_rate = max(exploration_rate, 0.55)
        elif self.cognitive_state.focus == "repair correctness":
            exploration_rate = max(exploration_rate, 0.40)
            policy_modes = [*policy_modes, "simplify", "simplify", "simplify"]

        if generation % 4 == 0 and self.meta_policy.novelty_bias >= 1.0:
            policy_modes = [*policy_modes, "replace", "replace", "replace"]

        if self.rng.random() < exploration_rate:
            return self.rng.choice(policy_modes)
        return learned

    def mutate(self, expression: str, generation: int) -> Candidate:
        mode = self.choose_operator(generation)
        if mode == "wrap":
            return Candidate(f"({expression}){self.rng.choice(MUTATION_SNIPPETS)}", mode)
        if mode == "append":
            return Candidate(f"{expression}{self.rng.choice(MUTATION_SNIPPETS)}", mode)
        if mode == "simplify":
            return Candidate(expression.replace("b + b + b", "3 * b").replace("(a * a)", "a * a"), mode)
        try:
            replacement = structural_replace(expression, self.rng)
        except (TypeError, ValueError):
            replacement = self.rng.choice(SEED_EXPRESSIONS)
        return Candidate(replacement, mode)

    def evaluate_and_archive(
        self,
        candidate: Candidate,
        parent: ArchiveRecord | None,
        generation: int,
        *,
        parent_total: float | None = None,
    ) -> ArchiveRecord:
        if parent is not None and parent_total is None:
            parent_total = self.current_parent_total(parent)
        decision = self.oracle.judge(candidate.expression, parent_total=parent_total)
        usefulness = decision.score.weighted_total
        reward = improvement_reward(parent_total, usefulness)
        if candidate.operator != "seed":
            self.operator_bandit.update(candidate.operator, reward)
        self.memory.deposit(
            "candidate",
            f"operator={candidate.operator}; reward={reward:.3f}; {candidate.expression} -> {decision.reason}",
            usefulness,
        )
        return self.archive.append(
            generation=generation,
            parent_id=parent.id if parent else None,
            expression=candidate.expression,
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


def dedupe_candidates(items: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    output: list[Candidate] = []
    for item in items:
        if item.expression not in seen:
            seen.add(item.expression)
            output.append(item)
    return output
