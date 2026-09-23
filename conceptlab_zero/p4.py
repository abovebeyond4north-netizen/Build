from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from conceptlab import EvidenceLedger, canonical_json, sha256_text
from p3 import HIDDEN_TARGETS, PredicateProgram, ProgramStore, verify_p3


P4_PROTOCOL_VERSION = 1
SUPPORT_ACCURACY_GATE = 0.95
D6_ACCURACY_GATE = 0.95
ADAPTATION_GAIN_GATE = 0.20
RESTART_GATE = 0.95
SUPPORT_CASES = 32
HOLDOUT_CASES = 160


@dataclass(frozen=True)
class AdapterCapsule:
    domain_id: str
    left_index: int
    right_index: int
    support_digest: str

    @property
    def signature(self) -> str:
        return f"{self.domain_id}:{self.left_index}->{self.right_index}"


@dataclass(frozen=True)
class InterfaceEpisode:
    domain_id: str
    observation: Any
    label: bool
    signal_pair: tuple[int, int]


@dataclass(frozen=True)
class DomainResult:
    domain_id: str
    width: int
    learned_adapter: str
    support_accuracy: float
    d6_accuracy: float
    strongest_control_accuracy: float
    adaptation_gain: float
    signal_pair_collisions: int
    restart_accuracy: float
    support_cases: int
    holdout_cases: int
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class P4CampaignResult:
    protocol_version: int
    p3_evidence_ledger_tip: str | None
    controller_signature: str
    controller_digest_before: str
    controller_digest_after: str
    controller_unchanged: bool
    domain_results: tuple[DomainResult, ...]
    all_p4_gates_passed: bool
    clg1_unlocked: bool
    claim: str
    created_at: float
    evidence_ledger_tip: str | None


DOMAIN_SPECS: tuple[tuple[str, int, tuple[int, int]], ...] = (
    ("novel_nested_6", 6, (4, 1)),
    ("novel_text_8", 8, (6, 2)),
)


def controller_hidden_target() -> PredicateProgram:
    for target_id, program in HIDDEN_TARGETS:
        if target_id == "sp_7a20":
            return program
    raise ValueError("P4 controller target is unavailable")


def flatten_numeric_values(observation: Any) -> tuple[int, ...]:
    values: list[int] = []

    def visit(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            values.append(value)
            return
        if isinstance(value, float) and value.is_integer():
            values.append(int(value))
            return
        if isinstance(value, str):
            values.extend(
                int(match)
                for match in re.findall(
                    r"(?<![A-Za-z0-9_])-?\d+(?![A-Za-z0-9_])",
                    value,
                )
            )
            return
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(observation)
    return tuple(values)


def render_interface_observation(domain_id: str, slots: tuple[int, ...]) -> Any:
    if domain_id == "novel_nested_6":
        if len(slots) != 6:
            raise ValueError("novel_nested_6 requires six slots")
        return {
            "header": [slots[0], {"mid": slots[1]}],
            "body": {
                "cluster": [slots[2], slots[3]],
                "tail": {"x": slots[4], "y": slots[5]},
            },
        }
    if domain_id == "novel_text_8":
        if len(slots) != 8:
            raise ValueError("novel_text_8 requires eight slots")
        return (
            f"q={slots[0]};r={slots[1]};s={slots[2]};t={slots[3]};"
            f"u={slots[4]};v={slots[5]};w={slots[6]};z={slots[7]}"
        )
    raise ValueError(f"unknown domain: {domain_id}")


def _episode_digest(episode: InterfaceEpisode) -> str:
    return sha256_text(
        canonical_json(
            {
                "domain_id": episode.domain_id,
                "observation": episode.observation,
                "label": episode.label,
            }
        )
    )


def interface_suite_digest(episodes: Iterable[InterfaceEpisode]) -> str:
    return sha256_text(
        canonical_json(
            sorted(_episode_digest(episode) for episode in episodes)
        )
    )


def generate_interface_episodes(
    *,
    domain_id: str,
    width: int,
    signal_indices: tuple[int, int],
    hidden_controller: PredicateProgram,
    seed: int,
    count: int,
    low: int,
    high: int,
    exclude_signal_pairs: frozenset[tuple[int, int]] = frozenset(),
) -> tuple[InterfaceEpisode, ...]:
    if width < 3:
        raise ValueError("interface width must be >= 3")
    left_index, right_index = signal_indices
    if left_index == right_index:
        raise ValueError("signal indices must differ")
    if not (0 <= left_index < width and 0 <= right_index < width):
        raise ValueError("signal indices out of range")

    rng = random.Random(seed)
    positives: list[InterfaceEpisode] = []
    negatives: list[InterfaceEpisode] = []
    seen_signals = set(exclude_signal_pairs)
    attempts = 0
    target_each = count // 2
    while len(positives) < target_each or len(negatives) < count - target_each:
        attempts += 1
        if attempts > 1_000_000:
            raise ValueError("unable to generate balanced interface suite")
        signal = (rng.randint(low, high), rng.randint(low, high))
        if signal in seen_signals:
            continue
        slots = [rng.randint(low, high) for _ in range(width)]
        slots[left_index] = signal[0]
        slots[right_index] = signal[1]
        label = hidden_controller.apply(*signal)
        episode = InterfaceEpisode(
            domain_id=domain_id,
            observation=render_interface_observation(
                domain_id,
                tuple(slots),
            ),
            label=label,
            signal_pair=signal,
        )
        bucket = positives if label else negatives
        limit = target_each if label else count - target_each
        if len(bucket) >= limit:
            continue
        bucket.append(episode)
        seen_signals.add(signal)

    combined = positives + negatives
    rng.shuffle(combined)
    return tuple(combined)


def score_adapter(
    *,
    controller: PredicateProgram,
    adapter: AdapterCapsule,
    episodes: tuple[InterfaceEpisode, ...],
) -> float:
    if not episodes:
        return 0.0
    correct = 0
    for episode in episodes:
        values = flatten_numeric_values(episode.observation)
        if adapter.left_index >= len(values) or adapter.right_index >= len(values):
            continue
        prediction = controller.apply(
            values[adapter.left_index],
            values[adapter.right_index],
        )
        if prediction == episode.label:
            correct += 1
    return correct / len(episodes)


class AdapterLearner:
    """Learn an ordered projection from generic numeric slots to a frozen controller."""

    def fit(
        self,
        *,
        controller: PredicateProgram,
        domain_id: str,
        episodes: tuple[InterfaceEpisode, ...],
    ) -> tuple[AdapterCapsule, float, int]:
        if not episodes:
            raise ValueError("adapter support episodes must be non-empty")
        widths = {
            len(flatten_numeric_values(episode.observation))
            for episode in episodes
        }
        if len(widths) != 1:
            raise ValueError("adapter support has inconsistent numeric widths")
        width = next(iter(widths))
        ranked: list[tuple[int, int, int]] = []
        for left_index in range(width):
            for right_index in range(width):
                if left_index == right_index:
                    continue
                correct = 0
                for episode in episodes:
                    values = flatten_numeric_values(episode.observation)
                    if controller.apply(
                        values[left_index],
                        values[right_index],
                    ) == episode.label:
                        correct += 1
                ranked.append((-correct, left_index, right_index))
        ranked.sort()
        best = ranked[0]
        capsule = AdapterCapsule(
            domain_id=domain_id,
            left_index=best[1],
            right_index=best[2],
            support_digest=interface_suite_digest(episodes),
        )
        return capsule, -best[0] / len(episodes), len(ranked)


def adapter_control_scores(
    *,
    controller: PredicateProgram,
    learned: AdapterCapsule,
    episodes: tuple[InterfaceEpisode, ...],
    prior_adapter: AdapterCapsule | None,
) -> tuple[float, ...]:
    width = len(flatten_numeric_values(episodes[0].observation))
    controls: list[AdapterCapsule] = [
        AdapterCapsule(learned.domain_id, 0, 1, "control"),
        AdapterCapsule(learned.domain_id, width - 2, width - 1, "control"),
        AdapterCapsule(
            learned.domain_id,
            learned.right_index,
            learned.left_index,
            "control",
        ),
    ]
    if (
        prior_adapter is not None
        and prior_adapter.left_index < width
        and prior_adapter.right_index < width
    ):
        controls.append(
            AdapterCapsule(
                learned.domain_id,
                prior_adapter.left_index,
                prior_adapter.right_index,
                "control",
            )
        )
    unique: dict[tuple[int, int], AdapterCapsule] = {}
    for control in controls:
        if (
            control.left_index == learned.left_index
            and control.right_index == learned.right_index
        ):
            continue
        unique[(control.left_index, control.right_index)] = control
    return tuple(
        score_adapter(
            controller=controller,
            adapter=control,
            episodes=episodes,
        )
        for control in unique.values()
    )


class AdapterStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, adapter: AdapterCapsule) -> str:
        digest = sha256_text(canonical_json(asdict(adapter)))
        path = self.root / f"{adapter.domain_id}.json"
        path.write_text(
            json.dumps(
                {
                    "digest": digest,
                    "adapter": asdict(adapter),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return digest

    def load(self, domain_id: str) -> tuple[AdapterCapsule, str]:
        path = self.root / f"{domain_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        adapter = AdapterCapsule(**payload["adapter"])
        digest = sha256_text(canonical_json(asdict(adapter)))
        if digest != payload["digest"]:
            raise ValueError(f"adapter digest mismatch: {domain_id}")
        return adapter, digest


def _controller_store(workspace: Path) -> ProgramStore:
    return ProgramStore(workspace / "symbolic_program_store")


def _restart_probe(
    *,
    workspace: Path,
    adapter_store: Path,
) -> dict[str, float]:
    script = Path(__file__).resolve().parent / "scripts" / "p4_restart_probe.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            str(workspace),
            str(adapter_store),
        ],
        cwd=str(Path(__file__).resolve().parent),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def run_p4_restart_probe(
    workspace: Path,
    adapter_store_path: Path,
) -> dict[str, float]:
    controller, _ = _controller_store(workspace).load("sp_7a20")
    adapters = AdapterStore(adapter_store_path)
    hidden = controller_hidden_target()
    scores: dict[str, float] = {}
    for index, (domain_id, width, signal_indices) in enumerate(DOMAIN_SPECS):
        adapter, _ = adapters.load(domain_id)
        suite = generate_interface_episodes(
            domain_id=domain_id,
            width=width,
            signal_indices=signal_indices,
            hidden_controller=hidden,
            seed=96000 + index,
            count=120,
            low=-260,
            high=260,
        )
        scores[domain_id] = score_adapter(
            controller=controller,
            adapter=adapter,
            episodes=suite,
        )
    return scores


def run_p4(workspace: Path) -> P4CampaignResult:
    p3 = verify_p3(workspace)
    if not p3.all_p3_gates_passed:
        raise ValueError("P4 requires a verified passing P3 campaign")

    program_store = _controller_store(workspace)
    controller, controller_digest_before = program_store.load("sp_7a20")
    hidden = controller_hidden_target()

    adapter_store_path = workspace / "adapter_store"
    if adapter_store_path.exists():
        shutil.rmtree(adapter_store_path)
    adapter_store = AdapterStore(adapter_store_path)
    learner = AdapterLearner()
    preliminary: list[dict[str, Any]] = []
    prior_adapter: AdapterCapsule | None = None

    for index, (domain_id, width, signal_indices) in enumerate(DOMAIN_SPECS):
        support = generate_interface_episodes(
            domain_id=domain_id,
            width=width,
            signal_indices=signal_indices,
            hidden_controller=hidden,
            seed=91000 + index,
            count=SUPPORT_CASES,
            low=-40,
            high=40,
        )
        holdout = generate_interface_episodes(
            domain_id=domain_id,
            width=width,
            signal_indices=signal_indices,
            hidden_controller=hidden,
            seed=92000 + index,
            count=HOLDOUT_CASES,
            low=-180,
            high=180,
            exclude_signal_pairs=frozenset(
                episode.signal_pair for episode in support
            ),
        )
        adapter, support_accuracy, searched = learner.fit(
            controller=controller,
            domain_id=domain_id,
            episodes=support,
        )
        d6_accuracy = score_adapter(
            controller=controller,
            adapter=adapter,
            episodes=holdout,
        )
        controls = adapter_control_scores(
            controller=controller,
            learned=adapter,
            episodes=holdout,
            prior_adapter=prior_adapter,
        )
        strongest_control = max(controls) if controls else 0.0
        collisions = len(
            {episode.signal_pair for episode in support}
            & {episode.signal_pair for episode in holdout}
        )
        adapter_store.save(adapter)
        preliminary.append(
            {
                "domain_id": domain_id,
                "width": width,
                "expected_indices": signal_indices,
                "adapter": adapter,
                "searched": searched,
                "support_accuracy": support_accuracy,
                "d6_accuracy": d6_accuracy,
                "strongest_control": strongest_control,
                "collisions": collisions,
            }
        )
        prior_adapter = adapter

    controller_after, controller_digest_after = program_store.load("sp_7a20")
    if controller_after.signature != controller.signature:
        raise ValueError("controller changed during adapter learning")

    restart_scores = _restart_probe(
        workspace=workspace,
        adapter_store=adapter_store_path,
    )

    ledger = EvidenceLedger(workspace / "p4_evidence_ledger.jsonl")
    results: list[DomainResult] = []
    ledger_tip: str | None = None
    for row in preliminary:
        adapter = row["adapter"]
        assert isinstance(adapter, AdapterCapsule)
        support_accuracy = float(row["support_accuracy"])
        d6_accuracy = float(row["d6_accuracy"])
        strongest_control = float(row["strongest_control"])
        gain = d6_accuracy - strongest_control
        collisions = int(row["collisions"])
        restart_accuracy = float(restart_scores[str(row["domain_id"])])

        reasons: list[str] = []
        if support_accuracy < SUPPORT_ACCURACY_GATE:
            reasons.append("support_accuracy")
        if d6_accuracy < D6_ACCURACY_GATE:
            reasons.append("d6_accuracy")
        if gain < ADAPTATION_GAIN_GATE:
            reasons.append("adaptation_gain")
        if collisions != 0:
            reasons.append("signal_pair_leakage")
        if restart_accuracy < RESTART_GATE:
            reasons.append("restart_accuracy")
        if (
            adapter.left_index,
            adapter.right_index,
        ) != tuple(row["expected_indices"]):
            reasons.append("adapter_identification")

        result = DomainResult(
            domain_id=str(row["domain_id"]),
            width=int(row["width"]),
            learned_adapter=adapter.signature,
            support_accuracy=support_accuracy,
            d6_accuracy=d6_accuracy,
            strongest_control_accuracy=strongest_control,
            adaptation_gain=gain,
            signal_pair_collisions=collisions,
            restart_accuracy=restart_accuracy,
            support_cases=SUPPORT_CASES,
            holdout_cases=HOLDOUT_CASES,
            passed=not reasons,
            failure_reasons=tuple(reasons),
        )
        results.append(result)
        ledger_tip = ledger.append(
            {
                "protocol_version": P4_PROTOCOL_VERSION,
                "p3_evidence_ledger_tip": p3.evidence_ledger_tip,
                "controller_digest": controller_digest_before,
                "domain_result": asdict(result),
                "searched_adapters": row["searched"],
            }
        )

    controller_unchanged = controller_digest_before == controller_digest_after
    all_passed = controller_unchanged and all(result.passed for result in results)
    campaign = P4CampaignResult(
        protocol_version=P4_PROTOCOL_VERSION,
        p3_evidence_ledger_tip=p3.evidence_ledger_tip,
        controller_signature=controller.signature,
        controller_digest_before=controller_digest_before,
        controller_digest_after=controller_digest_after,
        controller_unchanged=controller_unchanged,
        domain_results=tuple(results),
        all_p4_gates_passed=all_passed,
        clg1_unlocked=False,
        claim=(
            "p4_adaptive_observation_interfaces_passed"
            if all_passed
            else "p4_adaptive_observation_interfaces_failed"
        ),
        created_at=time.time(),
        evidence_ledger_tip=ledger_tip,
    )
    (workspace / "p4_campaign_result.json").write_text(
        json.dumps(asdict(campaign), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / "p4_restart_receipt.json").write_text(
        json.dumps(restart_scores, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return campaign


def verify_p4(workspace: Path) -> P4CampaignResult:
    p3 = verify_p3(workspace)
    data = json.loads(
        (workspace / "p4_campaign_result.json").read_text(encoding="utf-8")
    )
    results = tuple(
        DomainResult(
            **{
                **item,
                "failure_reasons": tuple(item["failure_reasons"]),
            }
        )
        for item in data["domain_results"]
    )
    campaign = P4CampaignResult(
        protocol_version=data["protocol_version"],
        p3_evidence_ledger_tip=data["p3_evidence_ledger_tip"],
        controller_signature=data["controller_signature"],
        controller_digest_before=data["controller_digest_before"],
        controller_digest_after=data["controller_digest_after"],
        controller_unchanged=data["controller_unchanged"],
        domain_results=results,
        all_p4_gates_passed=data["all_p4_gates_passed"],
        clg1_unlocked=data["clg1_unlocked"],
        claim=data["claim"],
        created_at=data["created_at"],
        evidence_ledger_tip=data["evidence_ledger_tip"],
    )
    if campaign.p3_evidence_ledger_tip != p3.evidence_ledger_tip:
        raise ValueError("P4 is bound to the wrong P3 evidence ledger")

    rows = [
        json.loads(line)
        for line in (workspace / "p4_evidence_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    previous_hash: str | None = None
    for line_number, row in enumerate(rows, start=1):
        if row.get("previous_hash") != previous_hash:
            raise ValueError(
                f"P4 evidence predecessor mismatch on line {line_number}"
            )
        payload = {
            key: value
            for key, value in row.items()
            if key != "record_hash"
        }
        record_hash = sha256_text(canonical_json(payload))
        if record_hash != row.get("record_hash"):
            raise ValueError(f"P4 evidence hash mismatch on line {line_number}")
        previous_hash = record_hash
    if not rows or previous_hash != campaign.evidence_ledger_tip:
        raise ValueError("P4 evidence ledger tip mismatch")
    return campaign
