"""Evolutionary optimization for prompts/configuration."""

from __future__ import annotations

from dataclasses import dataclass, replace
import random
from statistics import mean

from .core import EmergentAgent, AgentConfig


@dataclass(frozen=True)
class EvolutionConfig:
    population_size: int = 6
    generations: int = 8
    mutation_rate: float = 0.35
    plateau_threshold: float = 0.01
    plateau_generations: int = 2
    seed: int = 7


@dataclass(frozen=True)
class EvolutionRecord:
    generation: int
    best_score: float
    mean_score: float
    best_name: str
    principles: tuple[str, ...]


class EvolutionaryOptimizer:
    """Evolves agent configuration, not model weights.

    This keeps the prototype safe, inspectable, and cheap. A future version can
    replace config mutation with model/harness optimization under stronger gates.
    """

    mutation_pool = (
        "Ask one clarifying question only when needed.",
        "Prefer concise answers with concrete next steps.",
        "Explain uncertainty instead of inventing facts.",
        "Use local retrieved evidence before general knowledge.",
        "Reject harmful operational requests and redirect safely.",
        "Evaluate changes before accepting them.",
        "Split complex tasks into modules and tests.",
    )

    def __init__(self, config: EvolutionConfig | None = None) -> None:
        self.config = config or EvolutionConfig()
        self.random = random.Random(self.config.seed)

    def initial_population(self, base_agent: EmergentAgent) -> list[EmergentAgent]:
        pop = [base_agent]
        while len(pop) < self.config.population_size:
            pop.append(self._mutate(base_agent, suffix=f"v{len(pop)}"))
        return pop

    def evolve(self, base_agent: EmergentAgent, evaluator) -> tuple[EmergentAgent, list[EvolutionRecord]]:
        population = self.initial_population(base_agent)
        records: list[EvolutionRecord] = []
        stagnant = 0
        previous_best = -1.0

        for generation in range(self.config.generations):
            scored = [(evaluator.fitness(agent), agent) for agent in population]
            scored.sort(key=lambda item: item[0], reverse=True)
            best_score, best_agent = scored[0]
            records.append(
                EvolutionRecord(
                    generation=generation,
                    best_score=best_score,
                    mean_score=mean(score for score, _ in scored),
                    best_name=best_agent.config.name,
                    principles=best_agent.config.principles,
                )
            )

            if best_score - previous_best < self.config.plateau_threshold:
                stagnant += 1
            else:
                stagnant = 0
            if stagnant >= self.config.plateau_generations:
                return best_agent, records
            previous_best = best_score

            survivors = [agent for _, agent in scored[: max(2, len(scored) // 2)]]
            next_population = survivors[:]
            while len(next_population) < self.config.population_size:
                parent = self.random.choice(survivors)
                next_population.append(self._mutate(parent, suffix=f"g{generation}_{len(next_population)}"))
            population = next_population

        scored = [(evaluator.fitness(agent), agent) for agent in population]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1], records

    def _mutate(self, agent: EmergentAgent, suffix: str) -> EmergentAgent:
        principles = list(agent.config.principles)
        if self.random.random() < self.config.mutation_rate or len(principles) < 6:
            candidate = self.random.choice(self.mutation_pool)
            if candidate not in principles:
                principles.append(candidate)
        if len(principles) > 7:
            principles = principles[-7:]
        config = replace(agent.config, name=f"{agent.config.name}-{suffix}", principles=tuple(principles))
        return EmergentAgent(config=config, knowledge=agent.knowledge)
