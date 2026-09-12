from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .capability import CapabilityAcquirer
from .capability_model import CapabilitySpec
from .capability_sandbox import SkillSandbox
from .checkpoint import CheckpointManager
from .evolver import DarwinAgentZero, EvolutionConfig
from .objective import ObjectiveCompiler
from .self_patch import PatchProposal, RepositoryPatchLab


def add_acquisition_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(".dgm_workspace"),
    )
    parser.add_argument("--max-candidates", type=int, default=96)
    parser.add_argument("--validation-budget", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=2.0)


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
    add_acquisition_options(acquire)

    objective = sub.add_parser(
        "acquire-objective",
        help=(
            "compile a supported natural-language objective into a sealed "
            "benchmark and attempt capability acquisition"
        ),
    )
    objective.add_argument(
        "objective",
        nargs="+",
        help="objective text, for example: Improve Python debugging ability",
    )
    add_acquisition_options(objective)

    patch = sub.add_parser(
        "evaluate-patch",
        help=(
            "evaluate a content-addressed strategy-layer patch in an ephemeral "
            "copy; never modify or merge the live source tree"
        ),
    )
    patch.add_argument(
        "proposal",
        type=Path,
        help="path to a patch proposal JSON document",
    )
    patch.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Darwin Agent Zero project root containing pyproject.toml",
    )
    patch.add_argument(
        "--workspace",
        type=Path,
        default=Path(".dgm_workspace"),
        help="persistent evidence-report workspace",
    )
    patch.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="per-gate timeout in seconds",
    )

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


def run_acquisition(args: argparse.Namespace, spec: CapabilitySpec) -> int:
    acquirer = CapabilityAcquirer(
        args.workspace,
        sandbox=SkillSandbox(timeout_seconds=args.timeout),
    )
    report = acquirer.acquire(
        spec,
        max_candidates=args.max_candidates,
        validation_budget=args.validation_budget,
    )
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
            return run_acquisition(args, CapabilitySpec.load(args.spec))
        except ValueError as exc:
            print(f"Capability acquisition error: {exc}", file=sys.stderr)
            return 2

    if args.command == "acquire-objective":
        try:
            spec = ObjectiveCompiler().compile(" ".join(args.objective))
            return run_acquisition(args, spec)
        except ValueError as exc:
            print(f"Capability acquisition error: {exc}", file=sys.stderr)
            return 2

    if args.command == "evaluate-patch":
        try:
            proposal = PatchProposal.load(args.proposal)
            lab = RepositoryPatchLab(
                args.repo_root,
                args.workspace,
            )
            report = lab.evaluate(
                proposal,
                timeout_seconds=args.timeout,
            )
        except (TypeError, ValueError) as exc:
            print(f"Patch evaluation error: {exc}", file=sys.stderr)
            return 2

        print("Darwin Agent Zero patch evaluation")
        print(f"proposal: {report.proposal_digest}")
        print(f"passed: {report.passed}")
        print(f"report: {report.report_path}")
        for reason in report.validation.reasons:
            print(f"validation: {reason}")
        for gate in report.gates:
            print(
                f"gate {gate.name}: passed={gate.passed} "
                f"returncode={gate.returncode} elapsed={gate.elapsed_seconds:.3f}s"
            )
        if report.comparison is not None:
            comparison = report.comparison
            print(
                "strategy comparison: "
                f"passed={comparison.passed} "
                f"baseline={comparison.baseline_aggregate_score:.6f} "
                f"candidate={comparison.candidate_aggregate_score:.6f} "
                f"delta={comparison.aggregate_delta:+.6f}"
            )
            print(
                "champion comparison: "
                f"mean_delta={comparison.mean_champion_delta:+.6f} "
                f"worst_seed_delta={comparison.worst_seed_champion_delta:+.6f}"
            )
            for reason in comparison.reasons:
                print(f"comparison: {reason}")
        return 0 if report.passed else 1

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
