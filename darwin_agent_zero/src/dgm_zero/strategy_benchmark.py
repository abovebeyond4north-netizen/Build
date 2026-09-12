from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .evolver import DarwinAgentZero, EvolutionConfig


DEFAULT_SEEDS = (11, 23, 47)
DEFAULT_GENERATIONS = 4
DEFAULT_POPULATION = 6
DIVERSITY_TARGET = 12


@dataclass(frozen=True)
class StrategyRunResult:
    seed: int
    champion_score: float
    accepted_rate: float
    diversity: float
    budget_utilization: float
    aggregate_score: float
    total_records: int
    accepted_records: int
    map_elites_cells: int
    generations: int


@dataclass(frozen=True)
class StrategyBenchmarkReport:
    seeds: tuple[int, ...]
    generations: int
    population: int
    runs: tuple[StrategyRunResult, ...]
    aggregate_score: float
    mean_champion_score: float
    worst_champion_score: float


def score_run(
    *,
    champion_score: float,
    accepted_rate: float,
    diversity: float,
    budget_utilization: float,
) -> float:
    """Deterministic quality-diversity score for one bounded evolution run."""
    values = {
        "champion_score": champion_score,
        "accepted_rate": accepted_rate,
        "diversity": diversity,
        "budget_utilization": budget_utilization,
    }
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be numeric")
        if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{name} must be finite and between 0 and 1")
    return (
        0.65 * float(champion_score)
        + 0.20 * float(diversity)
        + 0.10 * float(accepted_rate)
        + 0.05 * float(budget_utilization)
    )


def run_strategy_benchmark(
    workspace_root: Path,
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    generations: int = DEFAULT_GENERATIONS,
    population: int = DEFAULT_POPULATION,
) -> StrategyBenchmarkReport:
    if not seeds or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
        raise ValueError("seeds must contain integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")
    if isinstance(generations, bool) or not isinstance(generations, int) or generations <= 0:
        raise ValueError("generations must be a positive integer")
    if isinstance(population, bool) or not isinstance(population, int) or population <= 0:
        raise ValueError("population must be a positive integer")

    workspace_root = workspace_root.resolve()
    if workspace_root.exists():
        shutil.rmtree(workspace_root)
    workspace_root.mkdir(parents=True, exist_ok=True)

    runs: list[StrategyRunResult] = []
    for seed in seeds:
        workspace = workspace_root / f"seed-{seed}"
        report = DarwinAgentZero(
            workspace,
            EvolutionConfig(
                generations=generations,
                population=population,
                seed=seed,
                curriculum_enabled=False,
            ),
        ).run()
        champion_score = (
            float(report.champion_score.get("weighted_total", 0.0))
            if report.champion_score
            else 0.0
        )
        accepted_rate = report.accepted_records / max(1, report.total_records)
        diversity = min(1.0, report.map_elites_cells / DIVERSITY_TARGET)
        budget = max(1, generations * population)
        budget_utilization = min(1.0, report.total_records / budget)
        aggregate = score_run(
            champion_score=champion_score,
            accepted_rate=accepted_rate,
            diversity=diversity,
            budget_utilization=budget_utilization,
        )
        runs.append(
            StrategyRunResult(
                seed=seed,
                champion_score=champion_score,
                accepted_rate=accepted_rate,
                diversity=diversity,
                budget_utilization=budget_utilization,
                aggregate_score=aggregate,
                total_records=report.total_records,
                accepted_records=report.accepted_records,
                map_elites_cells=report.map_elites_cells,
                generations=report.generations,
            )
        )

    aggregate_score = sum(run.aggregate_score for run in runs) / len(runs)
    mean_champion = sum(run.champion_score for run in runs) / len(runs)
    worst_champion = min(run.champion_score for run in runs)
    return StrategyBenchmarkReport(
        seeds=tuple(seeds),
        generations=generations,
        population=population,
        runs=tuple(runs),
        aggregate_score=aggregate_score,
        mean_champion_score=mean_champion,
        worst_champion_score=worst_champion,
    )


def write_report(path: Path, report: StrategyBenchmarkReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    temp.replace(path)


def parse_seeds(value: str) -> tuple[int, ...]:
    try:
        seeds = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    if len(set(seeds)) != len(seeds):
        raise argparse.ArgumentTypeError("seeds must be unique")
    return seeds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Darwin strategy benchmark")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=parse_seeds, default=DEFAULT_SEEDS)
    parser.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    parser.add_argument("--population", type=int, default=DEFAULT_POPULATION)
    args = parser.parse_args(argv)
    report = run_strategy_benchmark(
        args.workspace_root,
        seeds=args.seeds,
        generations=args.generations,
        population=args.population,
    )
    write_report(args.output, report)
    print(json.dumps(asdict(report), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
