from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class Principle:
    op: str
    param: int = 0

    def apply(self, left: int, right: int) -> bool:
        if self.op == "sum_mod2":
            return (left + right) % 2 == self.param
        if self.op == "equal":
            return left == right
        if self.op == "distance_ge":
            return abs(left - right) >= self.param
        if self.op == "product_positive":
            return left * right > 0
        raise ValueError(f"unknown principle op: {self.op}")

    @property
    def signature(self) -> str:
        return f"{self.op}:{self.param}"

    @property
    def complexity(self) -> int:
        base = {
            "equal": 1,
            "product_positive": 2,
            "sum_mod2": 3,
            "distance_ge": 3,
        }.get(self.op)
        if base is None:
            raise ValueError(f"unknown principle op: {self.op}")
        return base + (1 if self.param else 0)


GRAMMAR: tuple[Principle, ...] = (
    Principle("equal"),
    Principle("product_positive"),
    Principle("sum_mod2", 0),
    Principle("sum_mod2", 1),
    Principle("distance_ge", 2),
    Principle("distance_ge", 4),
    Principle("distance_ge", 6),
    Principle("distance_ge", 8),
)

HIDDEN_PRINCIPLES: tuple[tuple[str, Principle], ...] = (
    ("hp_a17f", Principle("sum_mod2", 0)),
    ("hp_91c2", Principle("equal")),
    ("hp_b044", Principle("distance_ge", 6)),
    ("hp_f830", Principle("product_positive")),
)


@dataclass(frozen=True)
class Episode:
    domain: str
    observation: Any
    label: bool


@dataclass(frozen=True)
class ConceptCapsule:
    op: str
    param: int
    training_digest: str

    def principle(self) -> Principle:
        return Principle(self.op, self.param)

    @property
    def signature(self) -> str:
        return self.principle().signature


@dataclass(frozen=True)
class IsolationScores:
    episodes_only: float
    capsule_only: float
    episodes_plus_capsule: float
    irrelevant_capsule: float
    matched_sham: float


@dataclass(frozen=True)
class PrincipleResult:
    opaque_principle_id: str
    recovered_signature: str
    exact_recovery: bool
    train_accuracy: float
    d0_accuracy: float
    d1_accuracy: float
    d2_accuracy: float
    d3_accuracy: float
    d3_control_gain: float
    false_transfer_rate: float
    compression_ratio: float
    leakage_collisions: int
    isolation: IsolationScores
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class CampaignResult:
    protocol_version: int
    manifest_commitment: str
    principle_results: tuple[PrincipleResult, ...]
    all_p0_gates_passed: bool
    clg1_unlocked: bool
    claim: str
    created_at: float
    evidence_ledger_tip: str | None


@dataclass(frozen=True)
class SealedManifest:
    protocol_version: int
    hidden_principles: tuple[tuple[str, str], ...]
    train_domains: tuple[str, ...]
    d0_domains: tuple[str, ...]
    d1_domains: tuple[str, ...]
    d2_domains: tuple[str, ...]
    d3_domains: tuple[str, ...]
    train_cases: int
    eval_cases: int
    seeds: tuple[int, ...]
    gates: tuple[tuple[str, float], ...]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_commitment(manifest: SealedManifest) -> str:
    return sha256_text(canonical_json(asdict(manifest)))


def render_observation(domain: str, left: int, right: int, rng: random.Random) -> Any:
    if domain == "list":
        return [left, right]
    if domain == "map":
        return {
            f"field_{rng.randrange(100_000, 999_999)}": left,
            f"slot_{rng.randrange(100_000, 999_999)}": right,
        }
    if domain == "nested":
        return {
            "outer": [
                {"payload": left},
                {"payload": right},
            ],
            "tag": "opaque",
        }
    if domain == "text":
        return f"alpha={left};omega={right}"
    if domain == "deep":
        return {
            "meta": {"kind": "opaque"},
            "payload": {
                "first": {"value": left},
                "second": {"value": right},
            },
        }
    if domain == "pipe":
        return f"<{left}|{right}>"
    raise ValueError(f"unknown domain: {domain}")


_INTEGER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?![A-Za-z0-9_])")


def extract_numeric_pair(observation: Any) -> tuple[int, int]:
    values: list[int] = []

    def visit(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            values.append(value)
            return
        if isinstance(value, float):
            if value.is_integer():
                values.append(int(value))
            return
        if isinstance(value, str):
            values.extend(int(match) for match in _INTEGER_PATTERN.findall(value))
            return
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(observation)
    if len(values) != 2:
        raise ValueError(f"expected exactly two numeric values, found {len(values)}")
    return values[0], values[1]


def normalized_pair(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left <= right else (right, left)


def generate_episodes(
    principle: Principle,
    domains: tuple[str, ...],
    *,
    seed: int,
    count: int,
    exclude_pairs: frozenset[tuple[int, int]] = frozenset(),
) -> tuple[Episode, ...]:
    if count < 2:
        raise ValueError("count must be at least two")
    if not domains:
        raise ValueError("domains must be non-empty")

    rng = random.Random(seed)
    # Equality has comparatively few positive pairs, so use a broad finite
    # universe that can support disjoint balanced train/D0/D1/D2/D3 suites.
    pairs = [
        (left, right)
        for left in range(-64, 65)
        for right in range(-64, 65)
        if normalized_pair(left, right) not in exclude_pairs
    ]
    rng.shuffle(pairs)
    positive = [pair for pair in pairs if principle.apply(*pair)]
    negative = [pair for pair in pairs if not principle.apply(*pair)]
    positive_count = count // 2
    negative_count = count - positive_count
    if len(positive) < positive_count or len(negative) < negative_count:
        raise ValueError("not enough balanced cases for requested principle")

    chosen = positive[:positive_count] + negative[:negative_count]
    rng.shuffle(chosen)
    episodes: list[Episode] = []
    for index, (left, right) in enumerate(chosen):
        domain = domains[index % len(domains)]
        episodes.append(
            Episode(
                domain=domain,
                observation=render_observation(domain, left, right, rng),
                label=principle.apply(left, right),
            )
        )
    return tuple(episodes)


def episode_digest(episode: Episode) -> str:
    return sha256_text(canonical_json(asdict(episode)))


def structural_episode_digest(episode: Episode) -> str:
    left, right = extract_numeric_pair(episode.observation)
    return sha256_text(
        canonical_json(
            {
                "pair": normalized_pair(left, right),
                "label": episode.label,
            }
        )
    )


def episode_pair_keys(episodes: Iterable[Episode]) -> frozenset[tuple[int, int]]:
    return frozenset(
        normalized_pair(*extract_numeric_pair(episode.observation))
        for episode in episodes
    )


def suite_digest(episodes: Iterable[Episode]) -> str:
    return sha256_text(
        canonical_json(
            sorted(episode_digest(episode) for episode in episodes)
        )
    )


def score_principle(principle: Principle, episodes: tuple[Episode, ...]) -> float:
    if not episodes:
        return 0.0
    correct = 0
    for episode in episodes:
        left, right = extract_numeric_pair(episode.observation)
        if principle.apply(left, right) == episode.label:
            correct += 1
    return correct / len(episodes)


class RuleInducer:
    """Deterministic learner over a deliberately bounded hypothesis grammar.

    The grammar is an explicit inductive bias. This learner demonstrates whether
    experience selects a reusable structural rule inside that grammar; it is not
    evidence of unrestricted representation invention.
    """

    def __init__(self, grammar: tuple[Principle, ...] = GRAMMAR) -> None:
        if not grammar:
            raise ValueError("grammar must be non-empty")
        self.grammar = grammar

    def fit(self, episodes: tuple[Episode, ...]) -> tuple[ConceptCapsule, float]:
        if not episodes:
            raise ValueError("episodes must be non-empty")
        ranked: list[tuple[int, int, str, Principle]] = []
        for candidate in self.grammar:
            correct = sum(
                candidate.apply(*extract_numeric_pair(episode.observation))
                == episode.label
                for episode in episodes
            )
            ranked.append(
                (
                    -correct,
                    candidate.complexity,
                    candidate.signature,
                    candidate,
                )
            )
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        best = ranked[0]
        principle = best[3]
        accuracy = -best[0] / len(episodes)
        capsule = ConceptCapsule(
            op=principle.op,
            param=principle.param,
            training_digest=suite_digest(episodes),
        )
        return capsule, accuracy


def capsule_size_bytes(capsule: ConceptCapsule) -> int:
    return len(canonical_json(asdict(capsule)).encode("utf-8"))


def episodes_size_bytes(episodes: tuple[Episode, ...]) -> int:
    return len(
        canonical_json([asdict(episode) for episode in episodes]).encode("utf-8")
    )


def matched_sham(capsule: ConceptCapsule) -> Principle:
    target = capsule.principle()
    alternatives = [
        candidate
        for candidate in GRAMMAR
        if candidate.signature != target.signature
    ]
    alternatives.sort(
        key=lambda candidate: (
            abs(candidate.complexity - target.complexity),
            candidate.signature,
        )
    )
    return alternatives[0]


def balanced_false_transfer_rate(
    capsule: ConceptCapsule,
    principle: Principle,
    episodes: tuple[Episode, ...],
) -> float:
    negatives = [episode for episode in episodes if not episode.label]
    if not negatives:
        return 1.0
    candidate = capsule.principle()
    false_positive = 0
    for episode in negatives:
        left, right = extract_numeric_pair(episode.observation)
        if candidate.apply(left, right) and not principle.apply(left, right):
            false_positive += 1
    return false_positive / len(negatives)


def isolation_scores(
    *,
    training: tuple[Episode, ...],
    evaluation: tuple[Episode, ...],
    capsule: ConceptCapsule,
    irrelevant: Principle,
) -> IsolationScores:
    episodes_only_capsule, _ = RuleInducer().fit(training)
    episodes_plus_capsule, _ = RuleInducer().fit(training)
    if episodes_plus_capsule.signature != capsule.signature:
        raise ValueError("fresh clone did not reconstruct the supplied capsule")

    return IsolationScores(
        episodes_only=score_principle(episodes_only_capsule.principle(), evaluation),
        capsule_only=score_principle(capsule.principle(), evaluation),
        episodes_plus_capsule=score_principle(capsule.principle(), evaluation),
        irrelevant_capsule=score_principle(irrelevant, evaluation),
        matched_sham=score_principle(matched_sham(capsule), evaluation),
    )


def leakage_collisions(
    training: tuple[Episode, ...],
    evaluation_suites: tuple[tuple[Episode, ...], ...],
) -> int:
    # Compare normalized structure rather than rendered surfaces. The same
    # underlying pair in a different JSON/string encoding still counts as
    # leakage for this experiment.
    train_hashes = {structural_episode_digest(episode) for episode in training}
    evaluation_hashes = {
        structural_episode_digest(episode)
        for suite in evaluation_suites
        for episode in suite
    }
    return len(train_hashes & evaluation_hashes)


class EvidenceLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: dict[str, Any]) -> str:
        rows: list[dict[str, Any]] = []
        previous_hash: str | None = None
        if self.path.exists():
            for line_number, line in enumerate(
                self.path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                row = json.loads(line)
                expected_previous = row.get("previous_hash")
                if expected_previous != previous_hash:
                    raise ValueError(
                        f"evidence ledger predecessor mismatch on line {line_number}"
                    )
                payload = {
                    key: value
                    for key, value in row.items()
                    if key != "record_hash"
                }
                actual_hash = sha256_text(canonical_json(payload))
                if actual_hash != row.get("record_hash"):
                    raise ValueError(
                        f"evidence ledger hash mismatch on line {line_number}"
                    )
                previous_hash = actual_hash
                rows.append(row)

        payload = {
            **record,
            "previous_hash": previous_hash,
        }
        record_hash = sha256_text(canonical_json(payload))
        rows.append({**payload, "record_hash": record_hash})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "".join(canonical_json(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        return record_hash


DEFAULT_GATES: tuple[tuple[str, float], ...] = (
    ("train_accuracy", 1.00),
    ("d0_accuracy", 0.90),
    ("d1_accuracy", 0.85),
    ("d2_accuracy", 0.85),
    ("d3_accuracy", 0.85),
    ("d3_control_gain", 0.10),
    ("compression_ratio", 4.00),
    ("max_false_transfer_rate", 0.10),
)


def default_manifest() -> SealedManifest:
    return SealedManifest(
        protocol_version=PROTOCOL_VERSION,
        hidden_principles=tuple(
            (opaque_id, principle.signature)
            for opaque_id, principle in HIDDEN_PRINCIPLES
        ),
        train_domains=("list", "map"),
        d0_domains=("map", "list"),
        d1_domains=("nested",),
        d2_domains=("text",),
        d3_domains=("deep", "pipe"),
        train_cases=48,
        eval_cases=40,
        seeds=(104729, 130363, 155921, 196613),
        gates=DEFAULT_GATES,
    )


def evaluate_principle(
    *,
    opaque_id: str,
    hidden: Principle,
    irrelevant: Principle,
    manifest: SealedManifest,
    seed: int,
) -> PrincipleResult:
    training = generate_episodes(
        hidden,
        manifest.train_domains,
        seed=seed,
        count=manifest.train_cases,
    )
    used_pairs = set(episode_pair_keys(training))

    d0 = generate_episodes(
        hidden,
        manifest.d0_domains,
        seed=seed + 10_000,
        count=manifest.eval_cases,
        exclude_pairs=frozenset(used_pairs),
    )
    used_pairs.update(episode_pair_keys(d0))

    d1 = generate_episodes(
        hidden,
        manifest.d1_domains,
        seed=seed + 20_000,
        count=manifest.eval_cases,
        exclude_pairs=frozenset(used_pairs),
    )
    used_pairs.update(episode_pair_keys(d1))

    d2 = generate_episodes(
        hidden,
        manifest.d2_domains,
        seed=seed + 30_000,
        count=manifest.eval_cases,
        exclude_pairs=frozenset(used_pairs),
    )
    used_pairs.update(episode_pair_keys(d2))

    d3 = generate_episodes(
        hidden,
        manifest.d3_domains,
        seed=seed + 40_000,
        count=manifest.eval_cases,
        exclude_pairs=frozenset(used_pairs),
    )

    capsule, train_accuracy = RuleInducer().fit(training)
    d0_accuracy = score_principle(capsule.principle(), d0)
    d1_accuracy = score_principle(capsule.principle(), d1)
    d2_accuracy = score_principle(capsule.principle(), d2)
    d3_accuracy = score_principle(capsule.principle(), d3)
    controls = isolation_scores(
        training=training,
        evaluation=d3,
        capsule=capsule,
        irrelevant=irrelevant,
    )
    strongest_control = max(
        controls.irrelevant_capsule,
        controls.matched_sham,
    )
    d3_control_gain = d3_accuracy - strongest_control
    compression_ratio = episodes_size_bytes(training) / capsule_size_bytes(capsule)
    false_transfer_rate = balanced_false_transfer_rate(capsule, hidden, d3)
    collisions = leakage_collisions(training, (d0, d1, d2, d3))

    gate_map = dict(manifest.gates)
    reasons: list[str] = []
    checks = (
        ("train_accuracy", train_accuracy >= gate_map["train_accuracy"]),
        ("d0_accuracy", d0_accuracy >= gate_map["d0_accuracy"]),
        ("d1_accuracy", d1_accuracy >= gate_map["d1_accuracy"]),
        ("d2_accuracy", d2_accuracy >= gate_map["d2_accuracy"]),
        ("d3_accuracy", d3_accuracy >= gate_map["d3_accuracy"]),
        ("d3_control_gain", d3_control_gain >= gate_map["d3_control_gain"]),
        (
            "compression_ratio",
            compression_ratio >= gate_map["compression_ratio"],
        ),
        (
            "false_transfer_rate",
            false_transfer_rate <= gate_map["max_false_transfer_rate"],
        ),
        ("exact_recovery", capsule.signature == hidden.signature),
        ("zero_leakage", collisions == 0),
    )
    for name, passed in checks:
        if not passed:
            reasons.append(name)

    return PrincipleResult(
        opaque_principle_id=opaque_id,
        recovered_signature=capsule.signature,
        exact_recovery=capsule.signature == hidden.signature,
        train_accuracy=train_accuracy,
        d0_accuracy=d0_accuracy,
        d1_accuracy=d1_accuracy,
        d2_accuracy=d2_accuracy,
        d3_accuracy=d3_accuracy,
        d3_control_gain=d3_control_gain,
        false_transfer_rate=false_transfer_rate,
        compression_ratio=compression_ratio,
        leakage_collisions=collisions,
        isolation=controls,
        passed=not reasons,
        failure_reasons=tuple(reasons),
    )


def run_campaign(workspace: Path) -> CampaignResult:
    workspace.mkdir(parents=True, exist_ok=True)
    manifest = default_manifest()
    commitment = manifest_commitment(manifest)

    # Commit first; reveal the evaluator-only manifest only after all principle
    # evaluations complete.
    (workspace / "manifest.commitment").write_text(
        commitment + "\n",
        encoding="utf-8",
    )

    ledger = EvidenceLedger(workspace / "evidence_ledger.jsonl")
    results: list[PrincipleResult] = []
    ledger_tip: str | None = None
    for index, (opaque_id, hidden) in enumerate(HIDDEN_PRINCIPLES):
        irrelevant = HIDDEN_PRINCIPLES[(index + 1) % len(HIDDEN_PRINCIPLES)][1]
        result = evaluate_principle(
            opaque_id=opaque_id,
            hidden=hidden,
            irrelevant=irrelevant,
            manifest=manifest,
            seed=manifest.seeds[index],
        )
        results.append(result)
        ledger_tip = ledger.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "manifest_commitment": commitment,
                "opaque_principle_id": opaque_id,
                "result": asdict(result),
            }
        )

    all_passed = all(result.passed for result in results)
    campaign = CampaignResult(
        protocol_version=PROTOCOL_VERSION,
        manifest_commitment=commitment,
        principle_results=tuple(results),
        all_p0_gates_passed=all_passed,
        clg1_unlocked=False,
        claim=(
            "p0_measurement_harness_passed"
            if all_passed
            else "p0_measurement_harness_failed"
        ),
        created_at=time.time(),
        evidence_ledger_tip=ledger_tip,
    )

    (workspace / "sealed_manifest.revealed.json").write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / "campaign_result.json").write_text(
        json.dumps(asdict(campaign), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return campaign


def verify_campaign(workspace: Path) -> CampaignResult:
    commitment_path = workspace / "manifest.commitment"
    manifest_path = workspace / "sealed_manifest.revealed.json"
    result_path = workspace / "campaign_result.json"
    if not commitment_path.is_file() or not manifest_path.is_file() or not result_path.is_file():
        raise ValueError("campaign artifacts are incomplete")

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = SealedManifest(
        protocol_version=manifest_data["protocol_version"],
        hidden_principles=tuple(tuple(item) for item in manifest_data["hidden_principles"]),
        train_domains=tuple(manifest_data["train_domains"]),
        d0_domains=tuple(manifest_data["d0_domains"]),
        d1_domains=tuple(manifest_data["d1_domains"]),
        d2_domains=tuple(manifest_data["d2_domains"]),
        d3_domains=tuple(manifest_data["d3_domains"]),
        train_cases=manifest_data["train_cases"],
        eval_cases=manifest_data["eval_cases"],
        seeds=tuple(manifest_data["seeds"]),
        gates=tuple(tuple(item) for item in manifest_data["gates"]),
    )
    expected_commitment = commitment_path.read_text(encoding="utf-8").strip()
    if manifest_commitment(manifest) != expected_commitment:
        raise ValueError("sealed manifest commitment mismatch")

    result_data = json.loads(result_path.read_text(encoding="utf-8"))
    principle_results = tuple(
        PrincipleResult(
            **{
                **item,
                "failure_reasons": tuple(item["failure_reasons"]),
                "isolation": IsolationScores(**item["isolation"]),
            }
        )
        for item in result_data["principle_results"]
    )
    campaign = CampaignResult(
        protocol_version=result_data["protocol_version"],
        manifest_commitment=result_data["manifest_commitment"],
        principle_results=principle_results,
        all_p0_gates_passed=result_data["all_p0_gates_passed"],
        clg1_unlocked=result_data["clg1_unlocked"],
        claim=result_data["claim"],
        created_at=result_data["created_at"],
        evidence_ledger_tip=result_data["evidence_ledger_tip"],
    )
    if campaign.manifest_commitment != expected_commitment:
        raise ValueError("campaign references the wrong manifest commitment")

    # Re-read the ledger to verify the complete hash chain.
    ledger = EvidenceLedger(workspace / "evidence_ledger.jsonl")
    probe_path = workspace / ".ledger_probe.jsonl"
    if probe_path.exists():
        probe_path.unlink()
    rows = []
    previous_hash: str | None = None
    for line_number, line in enumerate(
        ledger.path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("previous_hash") != previous_hash:
            raise ValueError(f"evidence ledger predecessor mismatch on line {line_number}")
        payload = {key: value for key, value in row.items() if key != "record_hash"}
        record_hash = sha256_text(canonical_json(payload))
        if record_hash != row.get("record_hash"):
            raise ValueError(f"evidence ledger hash mismatch on line {line_number}")
        previous_hash = record_hash
        rows.append(row)
    if not rows or previous_hash != campaign.evidence_ledger_tip:
        raise ValueError("campaign evidence ledger tip mismatch")
    return campaign
