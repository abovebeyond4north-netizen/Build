from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .capability import CapabilityAcquirer
from .capability_model import CapabilitySpec
from .capability_sandbox import SkillSandbox
from .checkpoint import CheckpointManager
from .evolver import DarwinAgentZero, EvolutionConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Darwin Agent Zero safe local evolution"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run bounded expression evolution")
    run.add_argument("--generations", type=int, default=12)
    run.add_argument("--population", type=int, default=6)
    run.add_argument("--seed", type=int, default=11)
    run.add_argument("--accept-threshold", type=float, default=0.72)
    run.add_argument("--elite-parent-limit", type=int, default=16)
    run.add_argument(
        "--workspace",
        type=Path,
        default=Path(".dgm_workspace"),
    )

    acquire = sub.add_parser(
        "acquire",
        help=(
            "acquire a bounded pure-function capability from a JSON "
            "train/validation/holdout specification"
        ),
    )
    acquire.add_argument(
        "spec",
        type=Path,
        help="path to a capability JSON specification",
    )
    acquire.add_argument(
        "--workspace",
        type=Path,
        default=Path(".dgm_workspace"),
    )
    acquire.add_argument("--max-candidates", type=int, default=96)
    acquire.add_argument("--validation-budget", type=int, default=12)
    acquire.add_argument("--timeout", type=float, default=2.0)

    restore = sub.add_parser(
        "restore",
        help="restore latest healthy checkpoint",
    )
    restore.add_argument(
        "--workspace",
        type=Path,
        default=Path(".dgm_workspace"),
    )
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
        print(f"health report: {report.health_path}")
        print(f"provenance: {report.provenance_path}")
        print(f"checkpoint: {report.checkpoint}")
        print(f"champion: {report.champion_expression}")
        print(f"score: {report.champion_score}")
        return 0

    if args.command == "acquire":
        try:
            spec = CapabilitySpec.load(args.spec)
            acquirer = CapabilityAcquirer(
                args.workspace,
                sandbox=SkillSandbox(timeout_seconds=args.timeout),
            )
            report = acquirer.acquire(
                spec,
                max_candidates=args.max_candidates,
                validation_budget=args.validation_budget,
            )
        except ValueError as exc:
            print(f"Capability acquisition error: {exc}", file=sys.stderr)
            return 2

        print("Darwin Agent Zero capability acquisition complete")
        print(f"capability: {report.capability}")
        print(f"status: {report.status}")
        print(f"baseline score: {report.baseline_score:.3f}")
        print(f"final score: {report.final_score}")
        print(f"train score: {report.train_score}")
        print(f"validation score: {report.validation_score}")
        print(f"holdout score: {report.holdout_score}")
        print(f"holdout evaluations: {report.holdout_evaluations}")
        print(f"candidates generated: {report.candidates_generated}")
        print(f"installed skill: {report.installed_path}")
        print(f"report: {report.report_path}")
        return 0

    if args.command == "restore":
        manager = CheckpointManager(args.workspace)
        report = manager.restore_latest()
        print("Darwin Agent Zero restore")
        print(f"workspace: {args.workspace}")
        print(f"restored: {report.restored}")
        print(f"checkpoint: {report.checkpoint_id}")
        print(f"files: {report.restored_files}")
        print(f"reason: {report.reason}")
        return 0 if report.restored else 1

    raise AssertionError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
