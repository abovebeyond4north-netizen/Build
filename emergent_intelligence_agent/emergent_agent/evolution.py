"""Evolutionary optimization for prompts/configuration."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import random
from statistics import mean

from .core import AgentConfig, EmergentAgent


@dataclass(frozen=True)
class EvolutionConfig:
    population_size: int = 6
    generations: int = 8
    mutation_rate: float = 0.35
    plateau_threshold: float = 0.01
    plateau_generations: int = 2
    seed: int = 7

    def __post_init__(self) -> None:
        if (
            isinstance(self.population_size, bool)
            or not isinstance(self.population_size, int)
            or self.population_size < 1
        ):
            raise ValueError("population_size must be a positive integer")
        if (
            isinstance(self.generations, bool)
            or not isinstance(self.generations, int)
            or self.generations < 1
        ):
            raise ValueError("generations must be a positive integer")
        if (
            isinstance(self.plateau_generations, bool)
            or not isinstance(self.plateau_generations, int)
            or self.plateau_generations < 1
        ):
            raise ValueError("plateau_generations must be a positive integer")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")

        for name in ("mutation_rate", "plateau_threshold"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, value)

        if not 0.0 <= self.mutation_rate <= 1.0:
            raise ValueError("mutation_rate must be between 0 and 1")
        if self.plateau_threshold < 0.0:
            raise ValueError("plateau_threshold must be non-negative")


@dataclass(frozen=True)
class EvolutionRecord:
    generation: int
    best_score: float
    mean_score: float
    best_name: str
    principles: tuple[str, ...]


class EvolutionaryOptimizer:
    """Evolve agent configuration under deterministic bounded controls."""

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

    @staticmethod
    def _fitness(evaluator, agent: EmergentAgent) -> float:
        value = float(evaluator.fitness(agent))
        if not math.isfinite(value):
            raise ValueError("evaluator fitness must be finite")
        return value

    def initial_population(self, base_agent: EmergentAgent) -> list[EmergentAgent]:
        pop = [base_agent]
        while len(pop) < self.config.population_size:
            pop.append(self._mutate(base_agent, suffix=f"v{len(pop)}"))
        return pop

    def evolve(
        self,
        base_agent: EmergentAgent,
        evaluator,
    ) -> tuple[EmergentAgent, list[EvolutionRecord]]:
        population = self.initial_population(base_agent)
        records: list[EvolutionRecord] = []
        stagnant = 0
        previous_best: float | None = None
        best_observed_agent = base_agent
        best_observed_score = float("-inf")

        for generation in range(self.config.generations):
            scored = [
                (self._fitness(evaluator, agent), agent)
                for agent in population
            ]
            scored.sort(key=lambda item: item[0], reverse=True)
            best_score, best_agent = scored[0]
            if best_score > best_observed_score:
                best_observed_score = best_score
                best_observed_agent = best_agent

            records.append(
                EvolutionRecord(
                    generation=generation,
                    best_score=best_score,
                    mean_score=mean(score for score, _ in scored),
                    best_name=best_agent.config.name,
                    principles=best_agent.config.principles,
                )
            )

            if (
                previous_best is not None
                and best_score - previous_best < self.config.plateau_threshold
            ):
                stagnant += 1
            else:
                stagnant = 0
            if stagnant >= self.config.plateau_generations:
                return best_observed_agent, records
            previous_best = best_score

            survivor_count = max(1, (len(scored) + 1) // 2)
            survivors = [agent for _, agent in scored[:survivor_count]]
            next_population = survivors[:]
            while len(next_population) < self.config.population_size:
                parent = self.random.choice(survivors)
                next_population.append(
                    self._mutate(
                        parent,
                        suffix=f"g{generation}_{len(next_population)}",
                    )
                )
            population = next_population

        final_scored = [
            (self._fitness(evaluator, agent), agent)
            for agent in population
        ]
        final_scored.sort(key=lambda item: item[0], reverse=True)
        final_score, final_agent = final_scored[0]
        if final_score > best_observed_score:
            best_observed_agent = final_agent
        return best_observed_agent, records

    def _mutate(self, agent: EmergentAgent, suffix: str) -> EmergentAgent:
        principles = list(agent.config.principles)
        if (
            self.random.random() < self.config.mutation_rate
            or len(principles) < 6
        ):
            candidate = self.random.choice(self.mutation_pool)
            if candidate not in principles:
                principles.append(candidate)
        if len(principles) > 7:
            principles = principles[-7:]
        config: AgentConfig = replace(
            agent.config,
            name=f"{agent.config.name}-{suffix}",
            principles=tuple(principles),
        )
        return EmergentAgent(config=config, knowledge=agent.knowledge)
