from __future__ import annotations

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
from p3 import HIDDEN_TARGETS, PredicateProgram, ProgramStore
from p4 import flatten_numeric_values, verify_p4


P5_PROTOCOL_VERSION = 2
SUPPORT_ACCURACY_GATE = 0.95
D7_ACCURACY_GATE = 0.95
CONTROL_GAIN_GATE = 0.20
RESTART_GATE = 0.95
SUPPORT_CASES = 48
HOLDOUT_CASES = 200


@dataclass(frozen=True)
class DecoderSpec:
    name: str
    marker: str
    base: int
    alphabet: str

    @property
    def pattern(self) -> re.Pattern[str]:
        return re.compile(
            re.escape(self.marker)
            + r":([pn])([" + re.escape(self.alphabet) + r"]+)"
        )

    def encode(self, value: int) -> str:
        sign = "n" if value < 0 else "p"
        magnitude = abs(value)
        digits = _encode_unsigned(magnitude, self.base)
        return f"{self.marker}:{sign}{digits}"

    def decode(self, sign: str, digits: str) -> int:
        magnitude = int(digits, self.base)
        return -magnitude if sign == "n" else magnitude


DECODERS: tuple[DecoderSpec, ...] = (
    DecoderSpec("opaque_q16", "Q", 16, "0123456789abcdef"),
    DecoderSpec("opaque_r2", "R", 2, "01"),
    DecoderSpec("opaque_s36", "S", 36, "0123456789abcdefghijklmnopqrstuvwxyz"),
    DecoderSpec("opaque_t10", "T", 10, "0123456789"),
)


@dataclass(frozen=True)
class RawFamilySpec:
    family_id: str
    target_id: str
    decoder_name: str
    width: int
    signal_indices: tuple[int, int]
    renderer: str
    seed: int


FAMILY_SPECS: tuple[RawFamilySpec, ...] = (
    RawFamilySpec(
        "rf_audit_hex",
        "sp_d402",
        "opaque_q16",
        6,
        (3, 1),
        "audit",
        111_017,
    ),
    RawFamilySpec(
        "rf_telemetry_bin",
        "sp_d402",
        "opaque_r2",
        7,
        (4, 2),
        "telemetry",
        211_021,
    ),
    RawFamilySpec(
        "rf_route_b36",
        "sp_d402",
        "opaque_s36",
        8,
        (5, 3),
        "route",
        311_029,
    ),
    RawFamilySpec(
        "rf_journal_dec",
        "sp_d402",
        "opaque_t10",
        9,
        (6, 4),
        "journal",
        411_031,
    ),
)


@dataclass(frozen=True)
class RawEpisode:
    family_id: str
    raw: str
    label: bool
    signal_pair: tuple[int, int]


@dataclass(frozen=True)
class FeatureCapsule:
    family_id: str
    decoder_name: str
    left_index: int
    right_index: int
    support_digest: str

    @property
    def signature(self) -> str:
        return (
            f"{self.family_id}:{self.decoder_name}:"
            f"{self.left_index}->{self.right_index}"
        )


@dataclass(frozen=True)
class FamilyResult:
    family_id: str
    target_id: str
    learned_feature: str
    support_accuracy: float
    d7_accuracy: float
    strongest_control_accuracy: float
    control_gain: float
    legacy_numeric_accuracy: float
    runner_up_accuracy: float
    structural_collisions: int
    restart_accuracy: float
    support_cases: int
    holdout_cases: int
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class P5Manifest:
    protocol_version: int
    families: tuple[tuple[str, str, str, int, tuple[int, int], int], ...]
    gates: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class P5CampaignResult:
    protocol_version: int
    p4_evidence_ledger_tip: str | None
    manifest_commitment: str
    controller_digests_before: tuple[tuple[str, str], ...]
    controller_digests_after: tuple[tuple[str, str], ...]
    controllers_unchanged: bool
    family_results: tuple[FamilyResult, ...]
    all_p5_gates_passed: bool
    clg1_unlocked: bool
    claim: str
    created_at: float
    evidence_ledger_tip: str | None


def _encode_unsigned(value: int, base: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if not (2 <= base <= len(alphabet)):
        raise ValueError("unsupported base")
    if value == 0:
        return "0"
    chars: list[str] = []
    current = value
    while current:
        current, remainder = divmod(current, base)
        chars.append(alphabet[remainder])
    return "".join(reversed(chars))


def decoder_by_name(name: str) -> DecoderSpec:
    for decoder in DECODERS:
        if decoder.name == name:
            return decoder
    raise ValueError(f"unknown decoder: {name}")


def hidden_controller(target_id: str) -> PredicateProgram:
    for candidate_id, program in HIDDEN_TARGETS:
        if candidate_id == target_id:
            return program
    raise ValueError(f"unknown hidden controller: {target_id}")


def default_manifest() -> P5Manifest:
    return P5Manifest(
        protocol_version=P5_PROTOCOL_VERSION,
        families=tuple(
            (
                spec.family_id,
                spec.target_id,
                spec.decoder_name,
                spec.width,
                spec.signal_indices,
                spec.seed,
            )
            for spec in FAMILY_SPECS
        ),
        gates=(
            ("support_accuracy", SUPPORT_ACCURACY_GATE),
            ("d7_accuracy", D7_ACCURACY_GATE),
            ("control_gain", CONTROL_GAIN_GATE),
            ("restart_accuracy", RESTART_GATE),
        ),
    )


def manifest_commitment(manifest: P5Manifest) -> str:
    return sha256_text(canonical_json(asdict(manifest)))


def extract_decoder_values(raw: str, decoder: DecoderSpec) -> tuple[int, ...]:
    return tuple(
        decoder.decode(match.group(1), match.group(2))
        for match in decoder.pattern.finditer(raw)
    )


def raw_suite_digest(episodes: Iterable[RawEpisode]) -> str:
    return sha256_text(
        canonical_json(
            sorted(
                sha256_text(
                    canonical_json(
                        {
                            "family_id": episode.family_id,
                            "raw": episode.raw,
                            "label": episode.label,
                        }
                    )
                )
                for episode in episodes
            )
        )
    )


def _render_raw(
    *,
    renderer: str,
    family_id: str,
    main_tokens: tuple[str, ...],
    decoy_tokens: tuple[str, ...],
    metadata: tuple[int, int, int, int],
) -> str:
    m0, m1, m2, m3 = metadata
    if renderer == "audit":
        body = "|".join(
            f"f{index}<{token}>"
            for index, token in enumerate(main_tokens)
        )
        return (
            f"audit seq={m0} host={m1} ["
            f"{decoy_tokens[0]}] {body} "
            f"[{decoy_tokens[1]}] crc={m2} epoch={m3}"
        )
    if renderer == "telemetry":
        body = " ".join(
            f"c{index}=({token})"
            for index, token in enumerate(main_tokens)
        )
        return (
            f"frame/{m0}/node/{m1} :: {decoy_tokens[0]} :: "
            f"{body} :: {decoy_tokens[1]} :: tick={m2};rev={m3}"
        )
    if renderer == "route":
        body = ",".join(
            f"slot{index}{{{token}}}"
            for index, token in enumerate(main_tokens)
        )
        return (
            f"route#{m0}@{m1} <{decoy_tokens[0]}> "
            f"{body} <{decoy_tokens[1]}> ttl={m2} gen={m3}"
        )
    if renderer == "journal":
        body = ";".join(
            f"k{index}[{token}]"
            for index, token in enumerate(main_tokens)
        )
        return (
            f"journal({m0},{m1}) {decoy_tokens[0]} "
            f":: {body} :: {decoy_tokens[1]} "
            f"page={m2} line={m3}"
        )
    raise ValueError(f"unknown renderer: {renderer}")


def generate_raw_episodes(
    *,
    spec: RawFamilySpec,
    seed: int,
    count: int,
    low: int,
    high: int,
    exclude_signal_pairs: frozenset[tuple[int, int]] = frozenset(),
) -> tuple[RawEpisode, ...]:
    rng = random.Random(seed)
    controller = hidden_controller(spec.target_id)
    decoder = decoder_by_name(spec.decoder_name)
    other_decoders = tuple(
        candidate for candidate in DECODERS
        if candidate.name != decoder.name
    )
    positives: list[RawEpisode] = []
    negatives: list[RawEpisode] = []
    seen = set(exclude_signal_pairs)
    positive_target = count // 2
    attempts = 0

    while len(positives) < positive_target or len(negatives) < count - positive_target:
        attempts += 1
        if attempts > 2_000_000:
            raise ValueError(f"unable to generate balanced family: {spec.family_id}")

        signal = (rng.randint(low, high), rng.randint(low, high))
        if signal in seen:
            continue
        slots = [rng.randint(low, high) for _ in range(spec.width)]
        slots[spec.signal_indices[0]] = signal[0]
        slots[spec.signal_indices[1]] = signal[1]
        label = controller.apply(*signal)
        bucket = positives if label else negatives
        limit = positive_target if label else count - positive_target
        if len(bucket) >= limit:
            continue

        main_tokens = tuple(decoder.encode(value) for value in slots)
        selected_decoys = rng.sample(other_decoders, k=2)
        decoy_tokens = tuple(
            selected_decoys[index].encode(rng.randint(low, high))
            for index in range(2)
        )
        metadata = (
            rng.randint(10_000, 99_999),
            rng.randint(10_000, 99_999),
            rng.randint(100, 999),
            rng.randint(100, 999),
        )
        bucket.append(
            RawEpisode(
                family_id=spec.family_id,
                raw=_render_raw(
                    renderer=spec.renderer,
                    family_id=spec.family_id,
                    main_tokens=main_tokens,
                    decoy_tokens=decoy_tokens,
                    metadata=metadata,
                ),
                label=label,
                signal_pair=signal,
            )
        )
        seen.add(signal)

    episodes = positives + negatives
    rng.shuffle(episodes)
    return tuple(episodes)


def score_feature(
    *,
    controller: PredicateProgram,
    feature: FeatureCapsule,
    episodes: tuple[RawEpisode, ...],
) -> float:
    decoder = decoder_by_name(feature.decoder_name)
    correct = 0
    for episode in episodes:
        values = extract_decoder_values(episode.raw, decoder)
        if (
            feature.left_index >= len(values)
            or feature.right_index >= len(values)
        ):
            continue
        prediction = controller.apply(
            values[feature.left_index],
            values[feature.right_index],
        )
        if prediction == episode.label:
            correct += 1
    return correct / len(episodes) if episodes else 0.0


class TokenizationLearner:
    """Select a lexical decoder and ordered latent slots from raw text."""

    def fit(
        self,
        *,
        controller: PredicateProgram,
        family_id: str,
        episodes: tuple[RawEpisode, ...],
    ) -> tuple[FeatureCapsule, float, FeatureCapsule | None, float, int]:
        if not episodes:
            raise ValueError("support episodes must be non-empty")

        ranked: list[
            tuple[int, str, int, int, FeatureCapsule]
        ] = []
        searched = 0
        digest = raw_suite_digest(episodes)

        for decoder in DECODERS:
            widths = {
                len(extract_decoder_values(episode.raw, decoder))
                for episode in episodes
            }
            if len(widths) != 1:
                continue
            width = next(iter(widths))
            if width < 2:
                continue
            for left_index in range(width):
                for right_index in range(width):
                    if left_index == right_index:
                        continue
                    searched += 1
                    capsule = FeatureCapsule(
                        family_id=family_id,
                        decoder_name=decoder.name,
                        left_index=left_index,
                        right_index=right_index,
                        support_digest=digest,
                    )
                    correct = round(
                        score_feature(
                            controller=controller,
                            feature=capsule,
                            episodes=episodes,
                        )
                        * len(episodes)
                    )
                    ranked.append(
                        (
                            -correct,
                            decoder.name,
                            left_index,
                            right_index,
                            capsule,
                        )
                    )

        if not ranked:
            raise ValueError("tokenization search produced no candidates")
        ranked.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
        best = ranked[0]
        runner = ranked[1] if len(ranked) > 1 else None
        best_accuracy = -best[0] / len(episodes)
        runner_accuracy = (
            -runner[0] / len(episodes)
            if runner is not None
            else 0.0
        )
        return (
            best[4],
            best_accuracy,
            runner[4] if runner is not None else None,
            runner_accuracy,
            searched,
        )


def _legacy_numeric_fit(
    *,
    controller: PredicateProgram,
    support: tuple[RawEpisode, ...],
    holdout: tuple[RawEpisode, ...],
) -> float:
    support_values = tuple(flatten_numeric_values(episode.raw) for episode in support)
    widths = {len(values) for values in support_values}
    if len(widths) != 1:
        return 0.5
    width = next(iter(widths))
    if width < 2:
        return 0.5

    ranked: list[tuple[int, int, int]] = []
    for left_index in range(width):
        for right_index in range(width):
            if left_index == right_index:
                continue
            correct = 0
            for episode, values in zip(support, support_values):
                if controller.apply(
                    values[left_index],
                    values[right_index],
                ) == episode.label:
                    correct += 1
            ranked.append((-correct, left_index, right_index))
    ranked.sort()
    _, left_index, right_index = ranked[0]

    correct = 0
    for episode in holdout:
        values = flatten_numeric_values(episode.raw)
        if left_index >= len(values) or right_index >= len(values):
            continue
        if controller.apply(
            values[left_index],
            values[right_index],
        ) == episode.label:
            correct += 1
    return correct / len(holdout) if holdout else 0.0


def _feature_controls(
    *,
    controller: PredicateProgram,
    learned: FeatureCapsule,
    runner_up: FeatureCapsule | None,
    holdout: tuple[RawEpisode, ...],
    width: int,
) -> tuple[float, ...]:
    controls: list[FeatureCapsule] = [
        FeatureCapsule(
            learned.family_id,
            learned.decoder_name,
            0,
            1,
            "control",
        ),
        FeatureCapsule(
            learned.family_id,
            learned.decoder_name,
            width - 2,
            width - 1,
            "control",
        ),
        FeatureCapsule(
            learned.family_id,
            learned.decoder_name,
            learned.right_index,
            learned.left_index,
            "control",
        ),
    ]
    if runner_up is not None:
        controls.append(runner_up)

    unique: dict[tuple[str, int, int], FeatureCapsule] = {}
    for control in controls:
        key = (
            control.decoder_name,
            control.left_index,
            control.right_index,
        )
        learned_key = (
            learned.decoder_name,
            learned.left_index,
            learned.right_index,
        )
        if key == learned_key:
            continue
        unique[key] = control

    return tuple(
        score_feature(
            controller=controller,
            feature=control,
            episodes=holdout,
        )
        for control in unique.values()
    )


class FeatureStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, capsule: FeatureCapsule) -> str:
        digest = sha256_text(canonical_json(asdict(capsule)))
        path = self.root / f"{capsule.family_id}.json"
        path.write_text(
            json.dumps(
                {"digest": digest, "capsule": asdict(capsule)},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return digest

    def load(self, family_id: str) -> tuple[FeatureCapsule, str]:
        path = self.root / f"{family_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        capsule = FeatureCapsule(**payload["capsule"])
        digest = sha256_text(canonical_json(asdict(capsule)))
        if digest != payload["digest"]:
            raise ValueError(f"feature capsule digest mismatch: {family_id}")
        return capsule, digest


def _controller_store(workspace: Path) -> ProgramStore:
    return ProgramStore(workspace / "symbolic_program_store")


def _restart_probe(
    *,
    workspace: Path,
    feature_store: Path,
) -> dict[str, float]:
    script = Path(__file__).resolve().parent / "scripts" / "p5_restart_probe.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            str(workspace),
            str(feature_store),
        ],
        cwd=str(Path(__file__).resolve().parent),
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )
    return json.loads(completed.stdout)


def run_p5_restart_probe(
    workspace: Path,
    feature_store_path: Path,
) -> dict[str, float]:
    programs = _controller_store(workspace)
    features = FeatureStore(feature_store_path)
    scores: dict[str, float] = {}
    for index, spec in enumerate(FAMILY_SPECS):
        controller, _ = programs.load(spec.target_id)
        feature, _ = features.load(spec.family_id)
        suite = generate_raw_episodes(
            spec=spec,
            seed=spec.seed + 900_000 + index,
            count=140,
            low=-320,
            high=320,
        )
        scores[spec.family_id] = score_feature(
            controller=controller,
            feature=feature,
            episodes=suite,
        )
    return scores


def run_p5(workspace: Path) -> P5CampaignResult:
    p4 = verify_p4(workspace)
    if not p4.all_p4_gates_passed:
        raise ValueError("P5 requires a verified passing P4 campaign")

    manifest = default_manifest()
    commitment = manifest_commitment(manifest)
    (workspace / "p5_manifest.commitment").write_text(
        commitment + "\n",
        encoding="utf-8",
    )

    programs = _controller_store(workspace)
    target_ids = tuple(sorted({spec.target_id for spec in FAMILY_SPECS}))
    controller_digests_before = tuple(
        (target_id, programs.load(target_id)[1])
        for target_id in target_ids
    )

    feature_store_path = workspace / "raw_feature_store"
    if feature_store_path.exists():
        shutil.rmtree(feature_store_path)
    features = FeatureStore(feature_store_path)
    learner = TokenizationLearner()
    preliminary: list[dict[str, Any]] = []

    for index, spec in enumerate(FAMILY_SPECS):
        controller, _ = programs.load(spec.target_id)
        support = generate_raw_episodes(
            spec=spec,
            seed=spec.seed,
            count=SUPPORT_CASES,
            low=-48,
            high=48,
        )
        holdout = generate_raw_episodes(
            spec=spec,
            seed=spec.seed + 100_000,
            count=HOLDOUT_CASES,
            low=-220,
            high=220,
            exclude_signal_pairs=frozenset(
                episode.signal_pair for episode in support
            ),
        )
        (
            feature,
            support_accuracy,
            runner_up,
            runner_support_accuracy,
            searched,
        ) = learner.fit(
            controller=controller,
            family_id=spec.family_id,
            episodes=support,
        )
        d7_accuracy = score_feature(
            controller=controller,
            feature=feature,
            episodes=holdout,
        )
        legacy_accuracy = _legacy_numeric_fit(
            controller=controller,
            support=support,
            holdout=holdout,
        )
        feature_controls = _feature_controls(
            controller=controller,
            learned=feature,
            runner_up=runner_up,
            holdout=holdout,
            width=spec.width,
        )
        runner_holdout = (
            score_feature(
                controller=controller,
                feature=runner_up,
                episodes=holdout,
            )
            if runner_up is not None
            else 0.0
        )
        strongest_control = max(
            (legacy_accuracy, *feature_controls),
            default=legacy_accuracy,
        )
        collisions = len(
            {episode.signal_pair for episode in support}
            & {episode.signal_pair for episode in holdout}
        )
        features.save(feature)
        preliminary.append(
            {
                "spec": spec,
                "feature": feature,
                "support_accuracy": support_accuracy,
                "runner_support_accuracy": runner_support_accuracy,
                "d7_accuracy": d7_accuracy,
                "legacy_accuracy": legacy_accuracy,
                "runner_holdout": runner_holdout,
                "strongest_control": strongest_control,
                "collisions": collisions,
                "searched": searched,
            }
        )

    controller_digests_after = tuple(
        (target_id, programs.load(target_id)[1])
        for target_id in target_ids
    )
    controllers_unchanged = (
        controller_digests_before == controller_digests_after
    )

    restart_scores = _restart_probe(
        workspace=workspace,
        feature_store=feature_store_path,
    )
    ledger = EvidenceLedger(workspace / "p5_evidence_ledger.jsonl")
    results: list[FamilyResult] = []
    ledger_tip: str | None = None

    for row in preliminary:
        spec = row["spec"]
        feature = row["feature"]
        assert isinstance(spec, RawFamilySpec)
        assert isinstance(feature, FeatureCapsule)
        support_accuracy = float(row["support_accuracy"])
        d7_accuracy = float(row["d7_accuracy"])
        strongest_control = float(row["strongest_control"])
        control_gain = d7_accuracy - strongest_control
        collisions = int(row["collisions"])
        restart_accuracy = float(restart_scores[spec.family_id])

        reasons: list[str] = []
        if support_accuracy < SUPPORT_ACCURACY_GATE:
            reasons.append("support_accuracy")
        if d7_accuracy < D7_ACCURACY_GATE:
            reasons.append("d7_accuracy")
        if control_gain < CONTROL_GAIN_GATE:
            reasons.append("control_gain")
        if collisions != 0:
            reasons.append("signal_pair_leakage")
        if restart_accuracy < RESTART_GATE:
            reasons.append("restart_accuracy")
        if feature.decoder_name != spec.decoder_name:
            reasons.append("decoder_identification")
        if (
            feature.left_index,
            feature.right_index,
        ) != spec.signal_indices:
            reasons.append("slot_identification")

        result = FamilyResult(
            family_id=spec.family_id,
            target_id=spec.target_id,
            learned_feature=feature.signature,
            support_accuracy=support_accuracy,
            d7_accuracy=d7_accuracy,
            strongest_control_accuracy=strongest_control,
            control_gain=control_gain,
            legacy_numeric_accuracy=float(row["legacy_accuracy"]),
            runner_up_accuracy=float(row["runner_holdout"]),
            structural_collisions=collisions,
            restart_accuracy=restart_accuracy,
            support_cases=SUPPORT_CASES,
            holdout_cases=HOLDOUT_CASES,
            passed=not reasons,
            failure_reasons=tuple(reasons),
        )
        results.append(result)
        ledger_tip = ledger.append(
            {
                "protocol_version": P5_PROTOCOL_VERSION,
                "p4_evidence_ledger_tip": p4.evidence_ledger_tip,
                "manifest_commitment": commitment,
                "family_result": asdict(result),
                "searched_candidates": row["searched"],
                "runner_support_accuracy": row["runner_support_accuracy"],
            }
        )

    all_passed = (
        controllers_unchanged
        and all(result.passed for result in results)
    )
    campaign = P5CampaignResult(
        protocol_version=P5_PROTOCOL_VERSION,
        p4_evidence_ledger_tip=p4.evidence_ledger_tip,
        manifest_commitment=commitment,
        controller_digests_before=controller_digests_before,
        controller_digests_after=controller_digests_after,
        controllers_unchanged=controllers_unchanged,
        family_results=tuple(results),
        all_p5_gates_passed=all_passed,
        clg1_unlocked=False,
        claim=(
            "p5_raw_token_and_slot_discovery_passed"
            if all_passed
            else "p5_raw_token_and_slot_discovery_failed"
        ),
        created_at=time.time(),
        evidence_ledger_tip=ledger_tip,
    )
    (workspace / "p5_manifest.revealed.json").write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / "p5_campaign_result.json").write_text(
        json.dumps(asdict(campaign), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / "p5_restart_receipt.json").write_text(
        json.dumps(restart_scores, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return campaign


def verify_p5(workspace: Path) -> P5CampaignResult:
    p4 = verify_p4(workspace)
    commitment = (
        workspace / "p5_manifest.commitment"
    ).read_text(encoding="utf-8").strip()
    manifest_data = json.loads(
        (workspace / "p5_manifest.revealed.json").read_text(encoding="utf-8")
    )
    manifest = P5Manifest(
        protocol_version=manifest_data["protocol_version"],
        families=tuple(
            (
                item[0],
                item[1],
                item[2],
                item[3],
                tuple(item[4]),
                item[5],
            )
            for item in manifest_data["families"]
        ),
        gates=tuple(tuple(item) for item in manifest_data["gates"]),
    )
    if manifest_commitment(manifest) != commitment:
        raise ValueError("P5 manifest commitment mismatch")

    data = json.loads(
        (workspace / "p5_campaign_result.json").read_text(encoding="utf-8")
    )
    results = tuple(
        FamilyResult(
            **{
                **item,
                "failure_reasons": tuple(item["failure_reasons"]),
            }
        )
        for item in data["family_results"]
    )
    campaign = P5CampaignResult(
        protocol_version=data["protocol_version"],
        p4_evidence_ledger_tip=data["p4_evidence_ledger_tip"],
        manifest_commitment=data["manifest_commitment"],
        controller_digests_before=tuple(
            tuple(item) for item in data["controller_digests_before"]
        ),
        controller_digests_after=tuple(
            tuple(item) for item in data["controller_digests_after"]
        ),
        controllers_unchanged=data["controllers_unchanged"],
        family_results=results,
        all_p5_gates_passed=data["all_p5_gates_passed"],
        clg1_unlocked=data["clg1_unlocked"],
        claim=data["claim"],
        created_at=data["created_at"],
        evidence_ledger_tip=data["evidence_ledger_tip"],
    )
    if campaign.p4_evidence_ledger_tip != p4.evidence_ledger_tip:
        raise ValueError("P5 is bound to the wrong P4 evidence ledger")
    if campaign.manifest_commitment != commitment:
        raise ValueError("P5 campaign references wrong manifest")

    rows = [
        json.loads(line)
        for line in (workspace / "p5_evidence_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    previous_hash: str | None = None
    for line_number, row in enumerate(rows, start=1):
        if row.get("previous_hash") != previous_hash:
            raise ValueError(
                f"P5 evidence predecessor mismatch on line {line_number}"
            )
        payload = {
            key: value
            for key, value in row.items()
            if key != "record_hash"
        }
        record_hash = sha256_text(canonical_json(payload))
        if record_hash != row.get("record_hash"):
            raise ValueError(f"P5 evidence hash mismatch on line {line_number}")
        previous_hash = record_hash
    if not rows or previous_hash != campaign.evidence_ledger_tip:
        raise ValueError("P5 evidence ledger tip mismatch")
    return campaign
