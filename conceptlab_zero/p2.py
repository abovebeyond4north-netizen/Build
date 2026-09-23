from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from conceptlab import (
    ConceptCapsule,
    Episode,
    EvidenceLedger,
    Principle,
    RuleInducer,
    canonical_json,
    default_manifest,
    extract_numeric_pair,
    generate_episodes,
    score_principle,
    sha256_text,
)
from p1 import verify_p1


P2_PROTOCOL_VERSION = 1
D4_ACCURACY_GATE = 0.90
D4_CONTROL_GAIN_GATE = 0.15
REVISION_ACCURACY_GATE = 0.95
RETENTION_GATE = 0.95
RESTART_GATE = 0.90

COMPOSITION_OPERATORS = ("and", "or", "xor", "eq")


@dataclass(frozen=True)
class CompositeCapsule:
    left_concept_id: str
    right_concept_id: str
    operator: str
    training_digest: str

    def apply(self, left_value: bool, right_value: bool) -> bool:
        if self.operator == "and":
            return left_value and right_value
        if self.operator == "or":
            return left_value or right_value
        if self.operator == "xor":
            return left_value != right_value
        if self.operator == "eq":
            return left_value == right_value
        raise ValueError(f"unknown composition operator: {self.operator}")


@dataclass(frozen=True)
class CompositeEpisode:
    domain: str
    observation: Any
    label: bool


@dataclass(frozen=True)
class RevisionResult:
    concept_id: str
    before_signature: str
    after_signature: str
    current_accuracy_on_revision: float
    candidate_accuracy_on_revision: float
    accepted: bool
    contradiction_count: int


@dataclass(frozen=True)
class P2CampaignResult:
    protocol_version: int
    p0_manifest_commitment: str
    p1_evidence_ledger_tip: str | None
    primitive_a_signature: str
    primitive_b_signature: str
    composition_operator: str
    d4_accuracy: float
    d4_strongest_control: float
    d4_control_gain: float
    composition_leakage_collisions: int
    revision: RevisionResult
    revised_holdout_accuracy: float
    unaffected_before_accuracy: float
    unaffected_after_accuracy: float
    unaffected_digest_unchanged: bool
    restart_primitive_a_accuracy: float
    restart_revised_accuracy: float
    restart_composite_accuracy: float
    persisted_episode_artifacts: int
    all_p2_gates_passed: bool
    clg1_unlocked: bool
    claim: str
    created_at: float
    evidence_ledger_tip: str | None


def _capsule_digest(capsule: ConceptCapsule) -> str:
    return sha256_text(canonical_json(asdict(capsule)))


def _composite_digest(capsule: CompositeCapsule) -> str:
    return sha256_text(canonical_json(asdict(capsule)))


class ConceptStore:
    """Content-addressed concept store that never persists raw discovery episodes."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_capsule(
        self,
        concept_id: str,
        capsule: ConceptCapsule,
        *,
        reason: str,
    ) -> str:
        digest = _capsule_digest(capsule)
        concept_root = self.root / "concepts" / concept_id
        versions = concept_root / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        version_path = versions / f"{digest}.json"
        if not version_path.exists():
            version_path.write_text(
                json.dumps(asdict(capsule), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        manifest = {
            "concept_id": concept_id,
            "digest": digest,
            "relative_path": str(version_path.relative_to(concept_root)),
            "reason": reason,
            "updated_at": time.time(),
        }
        (concept_root / "current.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        history_path = concept_root / "history.jsonl"
        prior = (
            history_path.read_text(encoding="utf-8")
            if history_path.exists()
            else ""
        )
        history_path.write_text(
            prior + canonical_json(manifest) + "\n",
            encoding="utf-8",
        )
        return digest

    def load_capsule(self, concept_id: str) -> tuple[ConceptCapsule, str]:
        concept_root = self.root / "concepts" / concept_id
        manifest_path = concept_root / "current.json"
        if not manifest_path.is_file():
            raise ValueError(f"missing current concept manifest: {concept_id}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        version_path = (concept_root / manifest["relative_path"]).resolve()
        root = concept_root.resolve()
        if root not in version_path.parents:
            raise ValueError("concept version escapes its store root")
        data = json.loads(version_path.read_text(encoding="utf-8"))
        capsule = ConceptCapsule(**data)
        digest = _capsule_digest(capsule)
        if digest != manifest["digest"]:
            raise ValueError(f"concept digest mismatch: {concept_id}")
        return capsule, digest

    def save_composite(self, composition_id: str, capsule: CompositeCapsule) -> str:
        root = self.root / "compositions"
        root.mkdir(parents=True, exist_ok=True)
        digest = _composite_digest(capsule)
        payload = {
            "composition_id": composition_id,
            "digest": digest,
            "capsule": asdict(capsule),
        }
        (root / f"{composition_id}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return digest

    def load_composite(self, composition_id: str) -> tuple[CompositeCapsule, str]:
        path = self.root / "compositions" / f"{composition_id}.json"
        if not path.is_file():
            raise ValueError(f"missing composition: {composition_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        capsule = CompositeCapsule(**payload["capsule"])
        digest = _composite_digest(capsule)
        if digest != payload["digest"]:
            raise ValueError(f"composition digest mismatch: {composition_id}")
        return capsule, digest

    def raw_episode_artifacts(self) -> tuple[Path, ...]:
        blocked = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            lowered = path.name.casefold()
            if "episode" in lowered or "training_cases" in lowered:
                blocked.append(path)
        return tuple(blocked)


def render_composite_observation(
    domain: str,
    values: tuple[int, int, int, int],
) -> Any:
    a_left, a_right, b_left, b_right = values
    if domain == "quad_map":
        return {
            "north": {"u": a_left, "v": a_right},
            "south": {"u": b_left, "v": b_right},
        }
    if domain == "quad_text":
        return f"A[{a_left},{a_right}]::B[{b_left},{b_right}]"
    if domain == "quad_nested":
        return {
            "bundle": [
                {"pair": [a_left, a_right]},
                {"pair": [b_left, b_right]},
            ]
        }
    if domain == "quad_pipe":
        return f"<<{a_left}|{a_right}>><<{b_left}|{b_right}>>"
    raise ValueError(f"unknown composite domain: {domain}")


def extract_composite_values(observation: Any) -> tuple[int, int, int, int]:
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
            import re

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
    if len(values) != 4:
        raise ValueError(f"expected four numeric values, found {len(values)}")
    return tuple(values)  # type: ignore[return-value]


def _normalized_quad(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    a_left, a_right, b_left, b_right = values
    a = tuple(sorted((a_left, a_right)))
    b = tuple(sorted((b_left, b_right)))
    return a[0], a[1], b[0], b[1]


def _apply_operator(name: str, left_value: bool, right_value: bool) -> bool:
    return CompositeCapsule("a", "b", name, "").apply(left_value, right_value)


def generate_composition_cases(
    *,
    primitive_a: Principle,
    primitive_b: Principle,
    hidden_operator: str,
    domains: tuple[str, ...],
    seed: int,
    per_truth_cell: int,
    low: int,
    high: int,
    exclude: frozenset[tuple[int, int, int, int]] = frozenset(),
) -> tuple[CompositeEpisode, ...]:
    if hidden_operator not in COMPOSITION_OPERATORS:
        raise ValueError("hidden operator is not in composition grammar")
    if per_truth_cell < 1:
        raise ValueError("per_truth_cell must be positive")

    rng = random.Random(seed)
    cells: dict[tuple[bool, bool], list[tuple[int, int, int, int]]] = {
        (False, False): [],
        (False, True): [],
        (True, False): [],
        (True, True): [],
    }
    attempts = 0
    seen = set(exclude)
    while any(len(rows) < per_truth_cell for rows in cells.values()):
        attempts += 1
        if attempts > 2_000_000:
            raise ValueError("unable to construct balanced composition suite")
        values = (
            rng.randint(low, high),
            rng.randint(low, high),
            rng.randint(low, high),
            rng.randint(low, high),
        )
        key = _normalized_quad(values)
        if key in seen:
            continue
        a_value = primitive_a.apply(values[0], values[1])
        b_value = primitive_b.apply(values[2], values[3])
        cell = (a_value, b_value)
        if len(cells[cell]) >= per_truth_cell:
            continue
        cells[cell].append(values)
        seen.add(key)

    chosen = [
        values
        for cell in ((False, False), (False, True), (True, False), (True, True))
        for values in cells[cell]
    ]
    rng.shuffle(chosen)
    episodes: list[CompositeEpisode] = []
    for index, values in enumerate(chosen):
        a_value = primitive_a.apply(values[0], values[1])
        b_value = primitive_b.apply(values[2], values[3])
        episodes.append(
            CompositeEpisode(
                domain=domains[index % len(domains)],
                observation=render_composite_observation(
                    domains[index % len(domains)],
                    values,
                ),
                label=_apply_operator(hidden_operator, a_value, b_value),
            )
        )
    return tuple(episodes)


def composite_suite_digest(episodes: Iterable[CompositeEpisode]) -> str:
    payload = [
        {
            "values": _normalized_quad(extract_composite_values(episode.observation)),
            "label": episode.label,
        }
        for episode in episodes
    ]
    return sha256_text(canonical_json(sorted(payload, key=canonical_json)))


def fit_composite(
    *,
    primitive_a: ConceptCapsule,
    primitive_b: ConceptCapsule,
    episodes: tuple[CompositeEpisode, ...],
    left_concept_id: str,
    right_concept_id: str,
) -> tuple[CompositeCapsule, float]:
    if not episodes:
        raise ValueError("composition episodes must be non-empty")
    ranked: list[tuple[int, str]] = []
    for operator in COMPOSITION_OPERATORS:
        correct = 0
        for episode in episodes:
            a_left, a_right, b_left, b_right = extract_composite_values(
                episode.observation
            )
            a_value = primitive_a.principle().apply(a_left, a_right)
            b_value = primitive_b.principle().apply(b_left, b_right)
            if _apply_operator(operator, a_value, b_value) == episode.label:
                correct += 1
        ranked.append((-correct, operator))
    ranked.sort()
    best_correct = -ranked[0][0]
    best_operator = ranked[0][1]
    return (
        CompositeCapsule(
            left_concept_id=left_concept_id,
            right_concept_id=right_concept_id,
            operator=best_operator,
            training_digest=composite_suite_digest(episodes),
        ),
        best_correct / len(episodes),
    )


def score_composite(
    *,
    composition: CompositeCapsule,
    primitive_a: ConceptCapsule,
    primitive_b: ConceptCapsule,
    episodes: tuple[CompositeEpisode, ...],
) -> float:
    correct = 0
    for episode in episodes:
        a_left, a_right, b_left, b_right = extract_composite_values(
            episode.observation
        )
        a_value = primitive_a.principle().apply(a_left, a_right)
        b_value = primitive_b.principle().apply(b_left, b_right)
        if composition.apply(a_value, b_value) == episode.label:
            correct += 1
    return correct / len(episodes) if episodes else 0.0


def score_composite_control(
    *,
    mode: str,
    primitive_a: ConceptCapsule,
    primitive_b: ConceptCapsule,
    episodes: tuple[CompositeEpisode, ...],
    hidden_operator: str,
) -> float:
    correct = 0
    alternatives = [
        operator
        for operator in COMPOSITION_OPERATORS
        if operator != hidden_operator
    ]
    for episode in episodes:
        a_left, a_right, b_left, b_right = extract_composite_values(
            episode.observation
        )
        a_value = primitive_a.principle().apply(a_left, a_right)
        b_value = primitive_b.principle().apply(b_left, b_right)
        if mode == "left_only":
            prediction = a_value
        elif mode == "right_only":
            prediction = b_value
        elif mode.startswith("operator:"):
            prediction = _apply_operator(mode.split(":", 1)[1], a_value, b_value)
        else:
            raise ValueError(f"unknown composite control: {mode}")
        if prediction == episode.label:
            correct += 1
    return correct / len(episodes) if episodes else 0.0


def composition_collisions(
    training: tuple[CompositeEpisode, ...],
    holdout: tuple[CompositeEpisode, ...],
) -> int:
    train = {
        _normalized_quad(extract_composite_values(episode.observation))
        for episode in training
    }
    test = {
        _normalized_quad(extract_composite_values(episode.observation))
        for episode in holdout
    }
    return len(train & test)


def _episode_from_pair(
    *,
    domain: str,
    pair: tuple[int, int],
    hidden: Principle,
    seed: int,
) -> Episode:
    rng = random.Random(seed)
    from conceptlab import render_observation

    return Episode(
        domain=domain,
        observation=render_observation(domain, pair[0], pair[1], rng),
        label=hidden.apply(*pair),
    )


def build_ambiguous_revision_support() -> tuple[Episode, ...]:
    hidden = Principle("distance_ge", 6)
    negative = (
        (0, 0), (0, 1), (1, 3), (-3, -1), (4, 6), (-8, -5),
        (10, 12), (-12, -10), (21, 24), (-25, -23), (31, 32), (-40, -37),
    )
    positive = (
        (0, 6), (1, 8), (-3, 4), (-10, -3), (5, 12), (-20, -13),
        (15, 22), (-30, -22), (40, 48), (-50, -42), (7, 15), (-16, -8),
    )
    pairs = negative + positive
    return tuple(
        _episode_from_pair(
            domain=("list", "map")[index % 2],
            pair=pair,
            hidden=hidden,
            seed=5100 + index,
        )
        for index, pair in enumerate(pairs)
    )


def build_revision_batch() -> tuple[Episode, ...]:
    hidden = Principle("distance_ge", 6)
    # Distances 4 and 5 are direct contradictions for distance_ge:4. The
    # remaining examples make distance_ge:6 uniquely supported inside GRAMMAR.
    negative = (
        (0, 4), (0, 5), (10, 14), (10, 15), (-10, -6), (-10, -5),
        (20, 24), (20, 25), (-30, -26), (-30, -25), (3, 6), (-8, -5),
    )
    positive = (
        (0, 6), (0, 7), (10, 16), (10, 18), (-10, -16), (-10, -18),
        (20, 26), (20, 29), (-30, -36), (-30, -39), (3, 10), (-8, -15),
    )
    pairs = negative + positive
    return tuple(
        _episode_from_pair(
            domain=("nested", "text")[index % 2],
            pair=pair,
            hidden=hidden,
            seed=6100 + index,
        )
        for index, pair in enumerate(pairs)
    )


def revise_capsule(
    *,
    store: ConceptStore,
    concept_id: str,
    evidence: tuple[Episode, ...],
) -> RevisionResult:
    current, _ = store.load_capsule(concept_id)
    current_accuracy = score_principle(current.principle(), evidence)
    candidate, candidate_accuracy = RuleInducer().fit(evidence)
    contradiction_count = sum(
        current.principle().apply(*extract_numeric_pair(episode.observation))
        != episode.label
        for episode in evidence
    )
    accepted = (
        contradiction_count > 0
        and candidate_accuracy > current_accuracy + 1e-12
    )
    if accepted:
        store.save_capsule(
            concept_id,
            candidate,
            reason="contradiction_driven_revision",
        )
    after, _ = store.load_capsule(concept_id)
    return RevisionResult(
        concept_id=concept_id,
        before_signature=current.signature,
        after_signature=after.signature,
        current_accuracy_on_revision=current_accuracy,
        candidate_accuracy_on_revision=candidate_accuracy,
        accepted=accepted,
        contradiction_count=contradiction_count,
    )


def _learn_primitive(
    *,
    hidden: Principle,
    seed: int,
    concept_id: str,
    store: ConceptStore,
) -> tuple[ConceptCapsule, tuple[Episode, ...]]:
    training = generate_episodes(
        hidden,
        ("list", "map"),
        seed=seed,
        count=48,
    )
    capsule, accuracy = RuleInducer().fit(training)
    if accuracy != 1.0:
        raise ValueError(f"primitive learner did not fit {concept_id}")
    store.save_capsule(concept_id, capsule, reason="independent_discovery")
    return capsule, training


def _restart_probe(
    *,
    workspace: Path,
    store_path: Path,
) -> dict[str, Any]:
    script = Path(__file__).resolve().parent / "scripts" / "restart_probe.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            str(store_path),
        ],
        cwd=str(Path(__file__).resolve().parent),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(completed.stdout)
    receipt_path = workspace / "p2_restart_receipt.json"
    receipt_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return data


def run_restart_probe(store_path: Path) -> dict[str, Any]:
    store = ConceptStore(store_path)
    primitive_a, _ = store.load_capsule("primitive_a")
    revised, _ = store.load_capsule("revision_target")
    primitive_b, _ = store.load_capsule("primitive_b")
    composition, _ = store.load_composite("d4_composition")

    primitive_a_suite = generate_episodes(
        Principle("sum_mod2", 0),
        ("deep", "pipe"),
        seed=93001,
        count=80,
    )
    revised_suite = generate_episodes(
        Principle("distance_ge", 6),
        ("deep", "pipe"),
        seed=93002,
        count=80,
    )
    composite_suite = generate_composition_cases(
        primitive_a=Principle("sum_mod2", 0),
        primitive_b=Principle("distance_ge", 6),
        hidden_operator="xor",
        domains=("quad_nested", "quad_pipe"),
        seed=93003,
        per_truth_cell=20,
        low=220,
        high=360,
    )
    return {
        "fresh_process": True,
        "primitive_a_accuracy": score_principle(
            primitive_a.principle(),
            primitive_a_suite,
        ),
        "revised_accuracy": score_principle(
            revised.principle(),
            revised_suite,
        ),
        "composite_accuracy": score_composite(
            composition=composition,
            primitive_a=primitive_a,
            primitive_b=primitive_b,
            episodes=composite_suite,
        ),
        "persisted_episode_artifacts": len(store.raw_episode_artifacts()),
    }


def run_p2(workspace: Path) -> P2CampaignResult:
    p1 = verify_p1(workspace)
    if not p1.all_p1_gates_passed:
        raise ValueError("P2 requires a verified passing P1 campaign")

    store_path = workspace / "concept_store"
    if store_path.exists():
        shutil.rmtree(store_path)
    store = ConceptStore(store_path)

    primitive_a_hidden = Principle("sum_mod2", 0)
    primitive_b_hidden = Principle("distance_ge", 6)
    primitive_a, _ = _learn_primitive(
        hidden=primitive_a_hidden,
        seed=71001,
        concept_id="primitive_a",
        store=store,
    )
    primitive_b, _ = _learn_primitive(
        hidden=primitive_b_hidden,
        seed=71002,
        concept_id="primitive_b",
        store=store,
    )

    composition_train = generate_composition_cases(
        primitive_a=primitive_a_hidden,
        primitive_b=primitive_b_hidden,
        hidden_operator="xor",
        domains=("quad_map", "quad_text"),
        seed=72001,
        per_truth_cell=12,
        low=-64,
        high=64,
    )
    train_keys = frozenset(
        _normalized_quad(extract_composite_values(episode.observation))
        for episode in composition_train
    )
    composition_holdout = generate_composition_cases(
        primitive_a=primitive_a_hidden,
        primitive_b=primitive_b_hidden,
        hidden_operator="xor",
        domains=("quad_nested", "quad_pipe"),
        seed=72002,
        per_truth_cell=20,
        low=80,
        high=180,
        exclude=train_keys,
    )
    composition, train_accuracy = fit_composite(
        primitive_a=primitive_a,
        primitive_b=primitive_b,
        episodes=composition_train,
        left_concept_id="primitive_a",
        right_concept_id="primitive_b",
    )
    if train_accuracy != 1.0:
        raise ValueError("composition operator was not identified on training data")
    store.save_composite("d4_composition", composition)

    d4_accuracy = score_composite(
        composition=composition,
        primitive_a=primitive_a,
        primitive_b=primitive_b,
        episodes=composition_holdout,
    )
    control_scores = [
        score_composite_control(
            mode="left_only",
            primitive_a=primitive_a,
            primitive_b=primitive_b,
            episodes=composition_holdout,
            hidden_operator="xor",
        ),
        score_composite_control(
            mode="right_only",
            primitive_a=primitive_a,
            primitive_b=primitive_b,
            episodes=composition_holdout,
            hidden_operator="xor",
        ),
    ]
    for operator in COMPOSITION_OPERATORS:
        if operator == "xor":
            continue
        control_scores.append(
            score_composite_control(
                mode=f"operator:{operator}",
                primitive_a=primitive_a,
                primitive_b=primitive_b,
                episodes=composition_holdout,
                hidden_operator="xor",
            )
        )
    strongest_control = max(control_scores)
    control_gain = d4_accuracy - strongest_control
    collisions = composition_collisions(
        composition_train,
        composition_holdout,
    )

    stable_before, stable_digest_before = store.load_capsule("primitive_a")
    unaffected_suite = generate_episodes(
        primitive_a_hidden,
        ("deep", "pipe"),
        seed=73001,
        count=80,
    )
    unaffected_before = score_principle(
        stable_before.principle(),
        unaffected_suite,
    )

    ambiguous_support = build_ambiguous_revision_support()
    initial_revision, initial_accuracy = RuleInducer().fit(ambiguous_support)
    if initial_accuracy != 1.0:
        raise ValueError("initial revision support was not internally consistent")
    store.save_capsule(
        "revision_target",
        initial_revision,
        reason="ambiguous_initial_support",
    )
    revision = revise_capsule(
        store=store,
        concept_id="revision_target",
        evidence=build_revision_batch(),
    )
    revised, _ = store.load_capsule("revision_target")
    revised_holdout = generate_episodes(
        Principle("distance_ge", 6),
        ("deep", "pipe"),
        seed=73002,
        count=80,
    )
    revised_holdout_accuracy = score_principle(
        revised.principle(),
        revised_holdout,
    )

    stable_after, stable_digest_after = store.load_capsule("primitive_a")
    unaffected_after = score_principle(
        stable_after.principle(),
        unaffected_suite,
    )

    persisted_episode_artifacts = len(store.raw_episode_artifacts())
    restart = _restart_probe(
        workspace=workspace,
        store_path=store_path,
    )

    reasons: list[str] = []
    if composition.operator != "xor":
        reasons.append("composition_operator")
    if d4_accuracy < D4_ACCURACY_GATE:
        reasons.append("d4_accuracy")
    if control_gain < D4_CONTROL_GAIN_GATE:
        reasons.append("d4_control_gain")
    if collisions != 0:
        reasons.append("composition_leakage")
    if revision.before_signature != "distance_ge:4":
        reasons.append("revision_initial_ambiguity")
    if not revision.accepted:
        reasons.append("revision_not_accepted")
    if revision.after_signature != "distance_ge:6":
        reasons.append("revision_target")
    if revised_holdout_accuracy < REVISION_ACCURACY_GATE:
        reasons.append("revision_holdout")
    if unaffected_before < RETENTION_GATE or unaffected_after < RETENTION_GATE:
        reasons.append("unaffected_retention")
    if stable_digest_before != stable_digest_after:
        reasons.append("unaffected_digest_changed")
    if persisted_episode_artifacts != 0:
        reasons.append("episode_persistence")
    for key in (
        "primitive_a_accuracy",
        "revised_accuracy",
        "composite_accuracy",
    ):
        if float(restart[key]) < RESTART_GATE:
            reasons.append(f"restart_{key}")
    if int(restart["persisted_episode_artifacts"]) != 0:
        reasons.append("restart_episode_persistence")

    p0_manifest = default_manifest()
    p0_commitment = sha256_text(canonical_json(asdict(p0_manifest)))
    ledger = EvidenceLedger(workspace / "p2_evidence_ledger.jsonl")

    provisional = P2CampaignResult(
        protocol_version=P2_PROTOCOL_VERSION,
        p0_manifest_commitment=p0_commitment,
        p1_evidence_ledger_tip=p1.evidence_ledger_tip,
        primitive_a_signature=primitive_a.signature,
        primitive_b_signature=primitive_b.signature,
        composition_operator=composition.operator,
        d4_accuracy=d4_accuracy,
        d4_strongest_control=strongest_control,
        d4_control_gain=control_gain,
        composition_leakage_collisions=collisions,
        revision=revision,
        revised_holdout_accuracy=revised_holdout_accuracy,
        unaffected_before_accuracy=unaffected_before,
        unaffected_after_accuracy=unaffected_after,
        unaffected_digest_unchanged=stable_digest_before == stable_digest_after,
        restart_primitive_a_accuracy=float(restart["primitive_a_accuracy"]),
        restart_revised_accuracy=float(restart["revised_accuracy"]),
        restart_composite_accuracy=float(restart["composite_accuracy"]),
        persisted_episode_artifacts=persisted_episode_artifacts,
        all_p2_gates_passed=not reasons,
        clg1_unlocked=False,
        claim=(
            "p2_composition_revision_persistence_passed"
            if not reasons
            else "p2_composition_revision_persistence_failed"
        ),
        created_at=time.time(),
        evidence_ledger_tip=None,
    )
    tip = ledger.append(
        {
            "protocol_version": P2_PROTOCOL_VERSION,
            "p0_manifest_commitment": p0_commitment,
            "p1_evidence_ledger_tip": p1.evidence_ledger_tip,
            "result": {
                **asdict(provisional),
                "evidence_ledger_tip": None,
            },
            "failure_reasons": reasons,
        }
    )
    result = P2CampaignResult(
        **{
            **asdict(provisional),
            "revision": revision,
            "evidence_ledger_tip": tip,
        }
    )
    (workspace / "p2_campaign_result.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def verify_p2(workspace: Path) -> P2CampaignResult:
    p1 = verify_p1(workspace)
    path = workspace / "p2_campaign_result.json"
    if not path.is_file():
        raise ValueError("P2 campaign result is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    revision = RevisionResult(**data["revision"])
    result = P2CampaignResult(
        **{
            **data,
            "revision": revision,
        }
    )
    if result.p1_evidence_ledger_tip != p1.evidence_ledger_tip:
        raise ValueError("P2 is bound to the wrong P1 evidence ledger")

    ledger_path = workspace / "p2_evidence_ledger.jsonl"
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    previous_hash: str | None = None
    for line_number, row in enumerate(rows, start=1):
        if row.get("previous_hash") != previous_hash:
            raise ValueError(
                f"P2 evidence predecessor mismatch on line {line_number}"
            )
        payload = {
            key: value
            for key, value in row.items()
            if key != "record_hash"
        }
        record_hash = sha256_text(canonical_json(payload))
        if record_hash != row.get("record_hash"):
            raise ValueError(f"P2 evidence hash mismatch on line {line_number}")
        previous_hash = record_hash
    if not rows or previous_hash != result.evidence_ledger_tip:
        raise ValueError("P2 evidence ledger tip mismatch")
    return result
