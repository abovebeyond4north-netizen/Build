from __future__ import annotations

import json
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from conceptlab import EvidenceLedger, canonical_json, sha256_text
from p3 import ProgramStore
from p5 import (
    DECODERS,
    FAMILY_SPECS,
    FeatureStore,
    RawEpisode,
    RawFamilySpec,
    _render_raw,
    decoder_by_name,
    generate_raw_episodes,
    hidden_controller,
    score_feature,
    verify_p5,
)
from p6_learner import (
    ActiveHypothesisLearner,
    ActiveLearningResult,
    _prediction,
    enumerate_candidates,
)


P6_PROTOCOL_VERSION = 1
POOL_SIZE = 256
AMBIGUOUS_CASES = 192
DIAGNOSTIC_CASES = 64
MAX_ACTIVE_QUERIES = 8
PASSIVE_TRIALS = 32
D8_ACCURACY_GATE = 0.95
EFFICIENCY_RATIO_GATE = 2.0


@dataclass(frozen=True)
class P6Manifest:
    protocol_version: int
    pool_size: int
    ambiguous_cases: int
    diagnostic_cases: int
    max_active_queries: int
    passive_trials: int
    d8_accuracy_gate: float
    efficiency_ratio_gate: float
    families: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class CurriculumResult:
    family_id: str
    learned_feature: str
    initial_candidates: int
    active_queries: int
    passive_mean_queries: float
    passive_median_queries: float
    passive_max_queries: int
    efficiency_ratio: float
    d8_accuracy: float
    all_queries_discriminative: bool
    exact_feature_recovery: bool
    queried_indices_unique: bool
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class P6CampaignResult:
    protocol_version: int
    p5_evidence_ledger_tip: str | None
    manifest_commitment: str
    controller_digest_before: str
    controller_digest_after: str
    controller_unchanged: bool
    curriculum_results: tuple[CurriculumResult, ...]
    all_p6_gates_passed: bool
    clg1_unlocked: bool
    claim: str
    created_at: float
    evidence_ledger_tip: str | None


class LabelOracle:
    """Evaluator-owned labels. The learner receives only query(index)."""

    def __init__(
        self,
        episodes: tuple[RawEpisode, ...],
        *,
        max_queries: int,
    ) -> None:
        self._episodes = episodes
        self._max_queries = max_queries
        self._queried: list[int] = []

    def query(self, index: int) -> bool:
        if index < 0 or index >= len(self._episodes):
            raise IndexError("oracle index out of range")
        if index in self._queried:
            raise ValueError("duplicate label query")
        if len(self._queried) >= self._max_queries:
            raise ValueError("label query budget exceeded")
        self._queried.append(index)
        return self._episodes[index].label

    @property
    def queried_indices(self) -> tuple[int, ...]:
        return tuple(self._queried)


def default_manifest() -> P6Manifest:
    return P6Manifest(
        protocol_version=P6_PROTOCOL_VERSION,
        pool_size=POOL_SIZE,
        ambiguous_cases=AMBIGUOUS_CASES,
        diagnostic_cases=DIAGNOSTIC_CASES,
        max_active_queries=MAX_ACTIVE_QUERIES,
        passive_trials=PASSIVE_TRIALS,
        d8_accuracy_gate=D8_ACCURACY_GATE,
        efficiency_ratio_gate=EFFICIENCY_RATIO_GATE,
        families=tuple(
            (spec.family_id, spec.seed)
            for spec in FAMILY_SPECS
        ),
    )


def manifest_commitment(manifest: P6Manifest) -> str:
    return sha256_text(canonical_json(asdict(manifest)))


def _make_ambiguous_pool(
    *,
    spec: RawFamilySpec,
    seed: int,
    count: int,
) -> tuple[RawEpisode, ...]:
    rng = random.Random(seed)
    decoder = decoder_by_name(spec.decoder_name)
    controller = hidden_controller(spec.target_id)
    other_decoders = tuple(
        candidate
        for candidate in DECODERS
        if candidate.name != decoder.name
    )
    episodes: list[RawEpisode] = []
    used_values: set[int] = set()

    while len(episodes) < count:
        value = rng.randint(-2_000, 2_000)
        if value in used_values:
            continue
        used_values.add(value)

        # All main slots carry the same value. Every structurally valid slot-pair
        # hypothesis therefore predicts the same label on this example.
        main_tokens = tuple(
            decoder.encode(value)
            for _ in range(spec.width)
        )
        selected_decoys = rng.sample(other_decoders, k=2)
        decoy_tokens = tuple(
            selected_decoys[index].encode(
                rng.randint(-2_000, 2_000)
            )
            for index in range(2)
        )
        metadata = (
            rng.randint(10_000, 99_999),
            rng.randint(10_000, 99_999),
            rng.randint(100, 999),
            rng.randint(100, 999),
        )
        episodes.append(
            RawEpisode(
                family_id=spec.family_id,
                raw=_render_raw(
                    renderer=spec.renderer,
                    family_id=spec.family_id,
                    main_tokens=main_tokens,
                    decoy_tokens=decoy_tokens,
                    metadata=metadata,
                ),
                label=controller.apply(value, value),
                signal_pair=(value, value),
            )
        )
    return tuple(episodes)


def generate_active_pool(
    *,
    spec: RawFamilySpec,
) -> tuple[RawEpisode, ...]:
    ambiguous = _make_ambiguous_pool(
        spec=spec,
        seed=spec.seed + 600_000,
        count=AMBIGUOUS_CASES,
    )
    diagnostic = generate_raw_episodes(
        spec=spec,
        seed=spec.seed + 700_000,
        count=DIAGNOSTIC_CASES,
        low=-100,
        high=100,
        exclude_signal_pairs=frozenset(
            episode.signal_pair
            for episode in ambiguous
        ),
    )
    pool = list(ambiguous + diagnostic)
    random.Random(spec.seed + 800_000).shuffle(pool)
    if len(pool) != POOL_SIZE:
        raise ValueError("active pool size mismatch")
    return tuple(pool)


def _passive_queries_to_identify(
    *,
    spec: RawFamilySpec,
    pool: tuple[RawEpisode, ...],
    seed: int,
) -> int:
    controller = hidden_controller(spec.target_id)
    candidates = list(
        enumerate_candidates(
            family_id=spec.family_id,
            raw_observations=tuple(
                episode.raw for episode in pool
            ),
        )
    )
    order = list(range(len(pool)))
    random.Random(seed).shuffle(order)
    queries = 0

    for index in order:
        if len(candidates) <= 1:
            break
        queries += 1
        label = pool[index].label
        candidates = [
            candidate
            for candidate in candidates
            if _prediction(
                controller=controller,
                feature=candidate,
                raw=pool[index].raw,
            )
            == label
        ]
    if len(candidates) != 1:
        raise ValueError(
            f"passive curriculum ended with {len(candidates)} hypotheses"
        )
    return queries


def _run_family(
    *,
    spec: RawFamilySpec,
    feature_store: FeatureStore,
) -> tuple[CurriculumResult, ActiveLearningResult]:
    controller = hidden_controller(spec.target_id)
    pool = generate_active_pool(spec=spec)
    oracle = LabelOracle(
        pool,
        max_queries=MAX_ACTIVE_QUERIES,
    )
    active = ActiveHypothesisLearner().fit(
        controller=controller,
        family_id=spec.family_id,
        raw_observations=tuple(
            episode.raw for episode in pool
        ),
        query_label=oracle.query,
        max_queries=MAX_ACTIVE_QUERIES,
    )
    feature_store.save(active.feature)

    holdout = generate_raw_episodes(
        spec=spec,
        seed=spec.seed + 900_000,
        count=200,
        low=-320,
        high=320,
        exclude_signal_pairs=frozenset(
            episode.signal_pair for episode in pool
        ),
    )
    d8_accuracy = score_feature(
        controller=controller,
        feature=active.feature,
        episodes=holdout,
    )
    passive_counts = tuple(
        _passive_queries_to_identify(
            spec=spec,
            pool=pool,
            seed=spec.seed + 1_000_000 + trial,
        )
        for trial in range(PASSIVE_TRIALS)
    )
    passive_mean = statistics.fmean(passive_counts)
    passive_median = float(statistics.median(passive_counts))
    efficiency_ratio = (
        passive_mean / active.queries_used
        if active.queries_used > 0
        else float("inf")
    )
    exact = (
        active.feature.decoder_name == spec.decoder_name
        and (
            active.feature.left_index,
            active.feature.right_index,
        )
        == spec.signal_indices
    )
    all_discriminative = all(
        step.disagreement > 0
        and step.candidates_after < step.candidates_before
        for step in active.trace
    )
    queried_unique = (
        len(oracle.queried_indices)
        == len(set(oracle.queried_indices))
        == active.queries_used
    )

    reasons: list[str] = []
    if active.queries_used > MAX_ACTIVE_QUERIES:
        reasons.append("active_query_budget")
    if d8_accuracy < D8_ACCURACY_GATE:
        reasons.append("d8_accuracy")
    if efficiency_ratio < EFFICIENCY_RATIO_GATE:
        reasons.append("label_efficiency")
    if not exact:
        reasons.append("feature_recovery")
    if not all_discriminative:
        reasons.append("non_discriminative_query")
    if not queried_unique:
        reasons.append("oracle_query_integrity")
    if active.final_candidates != 1:
        reasons.append("hypothesis_not_resolved")

    return (
        CurriculumResult(
            family_id=spec.family_id,
            learned_feature=active.feature.signature,
            initial_candidates=active.initial_candidates,
            active_queries=active.queries_used,
            passive_mean_queries=passive_mean,
            passive_median_queries=passive_median,
            passive_max_queries=max(passive_counts),
            efficiency_ratio=efficiency_ratio,
            d8_accuracy=d8_accuracy,
            all_queries_discriminative=all_discriminative,
            exact_feature_recovery=exact,
            queried_indices_unique=queried_unique,
            passed=not reasons,
            failure_reasons=tuple(reasons),
        ),
        active,
    )


def run_p6(workspace: Path) -> P6CampaignResult:
    p5 = verify_p5(workspace)
    if not p5.all_p5_gates_passed:
        raise ValueError("P6 requires a verified passing P5 campaign")

    manifest = default_manifest()
    commitment = manifest_commitment(manifest)
    (workspace / "p6_manifest.commitment").write_text(
        commitment + "\n",
        encoding="utf-8",
    )

    programs = ProgramStore(workspace / "symbolic_program_store")
    controller_digest_before = programs.load("sp_d402")[1]

    feature_store_path = workspace / "active_feature_store"
    if feature_store_path.exists():
        import shutil

        shutil.rmtree(feature_store_path)
    feature_store = FeatureStore(feature_store_path)

    results: list[CurriculumResult] = []
    traces: dict[str, Any] = {}
    ledger = EvidenceLedger(workspace / "p6_evidence_ledger.jsonl")
    ledger_tip: str | None = None

    for spec in FAMILY_SPECS:
        result, active = _run_family(
            spec=spec,
            feature_store=feature_store,
        )
        results.append(result)
        traces[spec.family_id] = [
            asdict(step)
            for step in active.trace
        ]
        ledger_tip = ledger.append(
            {
                "protocol_version": P6_PROTOCOL_VERSION,
                "p5_evidence_ledger_tip": p5.evidence_ledger_tip,
                "manifest_commitment": commitment,
                "curriculum_result": asdict(result),
                "query_trace": traces[spec.family_id],
            }
        )

    controller_digest_after = programs.load("sp_d402")[1]
    controller_unchanged = (
        controller_digest_before == controller_digest_after
    )
    all_passed = (
        controller_unchanged
        and all(result.passed for result in results)
    )
    campaign = P6CampaignResult(
        protocol_version=P6_PROTOCOL_VERSION,
        p5_evidence_ledger_tip=p5.evidence_ledger_tip,
        manifest_commitment=commitment,
        controller_digest_before=controller_digest_before,
        controller_digest_after=controller_digest_after,
        controller_unchanged=controller_unchanged,
        curriculum_results=tuple(results),
        all_p6_gates_passed=all_passed,
        clg1_unlocked=False,
        claim=(
            "p6_active_curriculum_passed"
            if all_passed
            else "p6_active_curriculum_failed"
        ),
        created_at=time.time(),
        evidence_ledger_tip=ledger_tip,
    )
    (workspace / "p6_manifest.revealed.json").write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / "p6_query_traces.json").write_text(
        json.dumps(traces, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / "p6_campaign_result.json").write_text(
        json.dumps(asdict(campaign), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return campaign


def verify_p6(workspace: Path) -> P6CampaignResult:
    p5 = verify_p5(workspace)
    commitment = (
        workspace / "p6_manifest.commitment"
    ).read_text(encoding="utf-8").strip()
    manifest_data = json.loads(
        (workspace / "p6_manifest.revealed.json").read_text(encoding="utf-8")
    )
    manifest = P6Manifest(
        protocol_version=manifest_data["protocol_version"],
        pool_size=manifest_data["pool_size"],
        ambiguous_cases=manifest_data["ambiguous_cases"],
        diagnostic_cases=manifest_data["diagnostic_cases"],
        max_active_queries=manifest_data["max_active_queries"],
        passive_trials=manifest_data["passive_trials"],
        d8_accuracy_gate=manifest_data["d8_accuracy_gate"],
        efficiency_ratio_gate=manifest_data["efficiency_ratio_gate"],
        families=tuple(
            tuple(item) for item in manifest_data["families"]
        ),
    )
    if manifest_commitment(manifest) != commitment:
        raise ValueError("P6 manifest commitment mismatch")

    data = json.loads(
        (workspace / "p6_campaign_result.json").read_text(encoding="utf-8")
    )
    results = tuple(
        CurriculumResult(
            **{
                **item,
                "failure_reasons": tuple(item["failure_reasons"]),
            }
        )
        for item in data["curriculum_results"]
    )
    campaign = P6CampaignResult(
        protocol_version=data["protocol_version"],
        p5_evidence_ledger_tip=data["p5_evidence_ledger_tip"],
        manifest_commitment=data["manifest_commitment"],
        controller_digest_before=data["controller_digest_before"],
        controller_digest_after=data["controller_digest_after"],
        controller_unchanged=data["controller_unchanged"],
        curriculum_results=results,
        all_p6_gates_passed=data["all_p6_gates_passed"],
        clg1_unlocked=data["clg1_unlocked"],
        claim=data["claim"],
        created_at=data["created_at"],
        evidence_ledger_tip=data["evidence_ledger_tip"],
    )
    if campaign.p5_evidence_ledger_tip != p5.evidence_ledger_tip:
        raise ValueError("P6 is bound to the wrong P5 evidence ledger")
    if campaign.manifest_commitment != commitment:
        raise ValueError("P6 campaign references wrong manifest")

    rows = [
        json.loads(line)
        for line in (workspace / "p6_evidence_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    previous_hash: str | None = None
    for line_number, row in enumerate(rows, start=1):
        if row.get("previous_hash") != previous_hash:
            raise ValueError(
                f"P6 evidence predecessor mismatch on line {line_number}"
            )
        payload = {
            key: value
            for key, value in row.items()
            if key != "record_hash"
        }
        record_hash = sha256_text(canonical_json(payload))
        if record_hash != row.get("record_hash"):
            raise ValueError(f"P6 evidence hash mismatch on line {line_number}")
        previous_hash = record_hash
    if not rows or previous_hash != campaign.evidence_ledger_tip:
        raise ValueError("P6 evidence ledger tip mismatch")
    return campaign
