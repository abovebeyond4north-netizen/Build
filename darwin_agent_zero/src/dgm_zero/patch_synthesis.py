from __future__ import annotations

import ast
import copy
import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from .self_patch import PatchProposal, RepositoryPatchLab


META_POLICY_PATH = "src/dgm_zero/meta_learning.py"
POLICY_KNOBS = (
    "novelty_bias",
    "simplification_bias",
    "exploration_bias",
    "curriculum_bias",
)
POLICY_MIN = 0.50
POLICY_MAX = 2.00
PERTURBATIONS = (-0.15, 0.15)
KNOWN_FOCI = (
    "repair correctness",
    "escape stagnation",
    "increase diversity",
    "mine failures",
    "raise curriculum",
)


@dataclass(frozen=True)
class PolicySite:
    focus: str
    call_index: int
    values: dict[str, float]


@dataclass(frozen=True)
class SynthesizedPatch:
    focus: str
    knob: str
    old_value: float
    new_value: float
    proposal: PatchProposal

    @property
    def direction(self) -> int:
        return 1 if self.new_value > self.old_value else -1

    @property
    def step(self) -> float:
        return abs(self.new_value - self.old_value)


class BoundedPolicyPatchSynthesizer:
    """Generate small strategy-only source variants without applying them."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.path = self.repo_root / META_POLICY_PATH
        if not self.path.is_file():
            raise ValueError(f"missing meta-learning source: {self.path}")

    def generate(
        self,
        *,
        max_candidates: int = 12,
        focus: str | None = None,
        priority_fn: Callable[[str, str, int], float] | None = None,
    ) -> list[SynthesizedPatch]:
        if (
            isinstance(max_candidates, bool)
            or not isinstance(max_candidates, int)
            or max_candidates <= 0
        ):
            raise ValueError("max_candidates must be a positive integer")
        if focus is not None and focus not in KNOWN_FOCI:
            raise ValueError(f"unsupported metacognitive focus: {focus}")

        source = self.path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        sites = policy_sites(tree)
        candidates: list[SynthesizedPatch] = []
        seen: set[str] = set()
        for site in sites:
            if focus is not None and site.focus != focus:
                continue
            for knob in POLICY_KNOBS:
                old_value = site.values.get(knob)
                if old_value is None:
                    continue
                for delta in PERTURBATIONS:
                    new_value = round(
                        max(POLICY_MIN, min(POLICY_MAX, old_value + delta)),
                        3,
                    )
                    if new_value == old_value:
                        continue
                    replacement = rewrite_policy_value(
                        tree,
                        call_index=site.call_index,
                        knob=knob,
                        new_value=new_value,
                    )
                    proposal = PatchProposal.for_replacements(
                        self.repo_root,
                        rationale=(
                            f"bounded policy search: focus={site.focus}; "
                            f"{knob} {old_value:.3f}->{new_value:.3f}"
                        ),
                        replacements={META_POLICY_PATH: replacement},
                    )
                    if proposal.digest in seen:
                        continue
                    seen.add(proposal.digest)
                    candidates.append(
                        SynthesizedPatch(
                            focus=site.focus,
                            knob=knob,
                            old_value=old_value,
                            new_value=new_value,
                            proposal=proposal,
                        )
                    )

        if priority_fn is not None:
            scored: list[tuple[float, int, int, int, str, SynthesizedPatch]] = []
            for candidate in candidates:
                raw_priority = priority_fn(
                    candidate.focus,
                    candidate.knob,
                    candidate.direction,
                )
                if (
                    isinstance(raw_priority, bool)
                    or not isinstance(raw_priority, (int, float))
                    or not math.isfinite(float(raw_priority))
                ):
                    raise ValueError("patch synthesis priority must be finite numeric")
                scored.append(
                    (
                        -float(raw_priority),
                        KNOWN_FOCI.index(candidate.focus),
                        POLICY_KNOBS.index(candidate.knob),
                        0 if candidate.direction > 0 else 1,
                        candidate.proposal.digest,
                        candidate,
                    )
                )
            candidates = [entry[-1] for entry in sorted(scored)]

        return candidates[:max_candidates]

    def generate_validated(
        self,
        lab: RepositoryPatchLab,
        *,
        max_candidates: int = 12,
        focus: str | None = None,
        priority_fn: Callable[[str, str, int], float] | None = None,
    ) -> list[SynthesizedPatch]:
        """Generate proposals and discard any that fail static patch policy."""
        output: list[SynthesizedPatch] = []
        for candidate in self.generate(
            max_candidates=max_candidates,
            focus=focus,
            priority_fn=priority_fn,
        ):
            if lab.validate(candidate.proposal).passed:
                output.append(candidate)
        return output


def policy_sites(tree: ast.AST) -> list[PolicySite]:
    calls: list[ast.Call] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "MetaLearningPolicy"
    ]
    call_positions = {id(call): index for index, call in enumerate(calls)}
    sites: list[PolicySite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        focus = focus_from_test(node.test)
        if focus is None:
            continue
        return_call = policy_return_call(node.body)
        if return_call is None:
            continue
        values: dict[str, float] = {}
        for keyword in return_call.keywords:
            if keyword.arg in POLICY_KNOBS:
                value = numeric_literal(keyword.value)
                if value is not None:
                    values[keyword.arg] = value
        if values:
            sites.append(
                PolicySite(
                    focus=focus,
                    call_index=call_positions[id(return_call)],
                    values=values,
                )
            )
    sites.sort(key=lambda site: KNOWN_FOCI.index(site.focus))
    return sites


def focus_from_test(node: ast.AST) -> str | None:
    if (
        not isinstance(node, ast.Compare)
        or len(node.ops) != 1
        or len(node.comparators) != 1
    ):
        return None
    if not isinstance(node.ops[0], ast.Eq):
        return None
    left = node.left
    right = node.comparators[0]
    if not (
        isinstance(left, ast.Attribute)
        and isinstance(left.value, ast.Name)
        and left.value.id == "state"
        and left.attr == "focus"
        and isinstance(right, ast.Constant)
        and isinstance(right.value, str)
    ):
        return None
    return right.value if right.value in KNOWN_FOCI else None


def policy_return_call(statements: list[ast.stmt]) -> ast.Call | None:
    for statement in statements:
        if (
            isinstance(statement, ast.Return)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "MetaLearningPolicy"
        ):
            return statement.value
    return None


def numeric_literal(node: ast.AST) -> float | None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return float(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
        and not isinstance(node.operand.value, bool)
    ):
        return -float(node.operand.value)
    return None


def rewrite_policy_value(
    tree: ast.AST,
    *,
    call_index: int,
    knob: str,
    new_value: float,
) -> str:
    if knob not in POLICY_KNOBS:
        raise ValueError(f"unsupported policy knob: {knob}")
    if not POLICY_MIN <= float(new_value) <= POLICY_MAX:
        raise ValueError("new policy value is outside bounded range")
    cloned = copy.deepcopy(tree)
    calls = [
        node
        for node in ast.walk(cloned)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "MetaLearningPolicy"
    ]
    if call_index < 0 or call_index >= len(calls):
        raise ValueError("policy call index is out of range")
    call = calls[call_index]
    changed = False
    for keyword in call.keywords:
        if keyword.arg == knob:
            keyword.value = ast.Constant(value=float(new_value))
            changed = True
            break
    if not changed:
        raise ValueError(f"policy call does not define knob: {knob}")
    ast.fix_missing_locations(cloned)
    return ast.unparse(cloned).rstrip() + "\n"


def write_synthesized_patches(
    output_dir: Path,
    candidates: list[SynthesizedPatch],
) -> list[Path]:
    """Write proposal JSON files that can be passed directly to evaluate-patch."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, candidate in enumerate(candidates, start=1):
        path = output_dir / f"{index:03d}-{candidate.proposal.digest}.json"
        payload = {
            **asdict(candidate.proposal),
            "synthesis": {
                "focus": candidate.focus,
                "knob": candidate.knob,
                "old_value": candidate.old_value,
                "new_value": candidate.new_value,
            },
        }
        temp = path.with_name(f".{path.name}.tmp")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        temp.replace(path)
        paths.append(path)
    return paths
