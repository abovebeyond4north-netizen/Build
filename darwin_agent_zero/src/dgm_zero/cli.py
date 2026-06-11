from __future__ import annotations

import argparse
from pathlib import Path

from .evolver import DarwinAgentZero, EvolutionConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Darwin Agent Zero safe local evolution")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run bounded evolution")
    run.add_argument("--generations", type=int, default=12)
    run.add_argument("--population", type=int, default=6)
    run.add_argument("--seed", type=int, default=11)
    run.add_argument("--accept-threshold", type=float, default=0.72)
    run.add_argument("--elite-parent-limit", type=int, default=16)
    run.add_argument("--workspace", type=Path, default=Path(".dgm_workspace"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        config = EvolutionConfig(
            generations=args.generations,
            population=args.population,
            seed=args.seed,
            accept_threshold=args.accept_threshold,
            elite_parent_limit=args.elite_parent_limit,
        )
        agent = DarwinAgentZero(args.workspace, config)
        report = agent.run()
        print("Darwin Agent Zero complete")
        print(f"workspace: {args.workspace}")
        print(f"records: {report.total_records}")
        print(f"accepted: {report.accepted_records}")
        print(f"map elites cells: {report.map_elites_cells}")
        print(f"map elites path: {report.map_elites_path}")
        print(f"champion: {report.champion_expression}")
        print(f"score: {report.champion_score}")
        return 0
    raise AssertionError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
