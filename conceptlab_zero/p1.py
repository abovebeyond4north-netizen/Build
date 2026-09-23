from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

from conceptlab import (
    EvidenceLedger,
    HIDDEN_PRINCIPLES,
    RuleInducer,
    default_manifest,
    generate_episodes,
    matched_sham,
    score_principle,
    verify_campaign,
)


P1_PROTOCOL_VERSION = 1
COUNTERFACTUAL_GATE = 0.80
ABLATION_FRACTION_GATE = 0.50


@dataclass(frozen=True)
class CounterfactualCase:
    base_left: int
    base_right: int
    intervened_left: int
    intervened_right: int
    expected_after: bool
    expected_changed: bool


@dataclass(frozen=True)
class P1PrincipleResult:
    opaque_principle_id: str
    recovered_signature: str
    counterfactual_accuracy: float
    counterfactual_cases: int
    capsule_score: float
    ablated_score: float
    balanced_control_score: float
    ablation_fraction: float
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class P1CampaignResult:
    protocol_version: int
    p0_manifest_commitment: str
    principle_results: tuple[P1PrincipleResult, ...]
    all_p1_gates_passed: bool
    clg1_unlocked: bool
    claim: str
    created_at: float
    evidence_ledger_tip: str | None


def build_counterfactual_cases(
    *,
    hidden,
    seed: int,
    count: int = 64,
) -> tuple[CounterfactualCase, ...]:
    if count < 4 or count % 2:
        raise ValueError("counterfactual count must be an even integer >= 4")

    values = tuple(range(-160, -79, 8)) + tuple(range(80, 161, 8))
    deltas = (-220, -13, -8, 8, 13, 220)
    candidates: list[CounterfactualCase] = []
    for left, right in product(values, repeat=2):
        before = hidden.apply(left, right)
        for side in (0, 1):
            for delta in deltas:
                after_left = left + delta if side == 0 else left
                after_right = right + delta if side == 1 else right
                after = hidden.apply(after_left, after_right)
                candidates.append(
                    CounterfactualCase(
                        base_left=left,
                        base_right=right,
                        intervened_left=after_left,
                        intervened_right=after_right,
                        expected_after=after,
                        expected_changed=after != before,
                    )
                )

    rng = random.Random(seed)
    changed = [case for case in candidates if case.expected_changed]
    unchanged = [case for case in candidates if not case.expected_changed]
    rng.shuffle(changed)
    rng.shuffle(unchanged)
    half = count // 2
    if len(changed) < half or len(unchanged) < half:
        raise ValueError("counterfactual generator cannot produce balanced change cases")
    selected = changed[:half] + unchanged[:half]
    rng.shuffle(selected)
    return tuple(selected)


def counterfactual_accuracy(capsule, cases: tuple[CounterfactualCase, ...]) -> float:
    if not cases:
        return 0.0
    principle = capsule.principle()
    correct = 0
    for case in cases:
        predicted_before = principle.apply(case.base_left, case.base_right)
        predicted_after = principle.apply(
            case.intervened_left,
            case.intervened_right,
        )
        predicted_changed = predicted_after != predicted_before
        if (
            predicted_after == case.expected_after
            and predicted_changed == case.expected_changed
        ):
            correct += 1
    return correct / len(cases)


def ablation_fraction(
    *,
    capsule_score: float,
    ablated_score: float,
    control_score: float = 0.5,
) -> float:
    denominator = capsule_score - control_score
    if denominator <= 0:
        return 0.0
    return (capsule_score - ablated_score) / denominator


def run_p1(workspace: Path) -> P1CampaignResult:
    p0 = verify_campaign(workspace)
    if not p0.all_p0_gates_passed:
        raise ValueError("P1 requires a verified passing P0 campaign")

    manifest = default_manifest()
    ledger = EvidenceLedger(workspace / "p1_evidence_ledger.jsonl")
    results: list[P1PrincipleResult] = []
    ledger_tip: str | None = None

    for index, (opaque_id, hidden) in enumerate(HIDDEN_PRINCIPLES):
        seed = manifest.seeds[index]
        training = generate_episodes(
            hidden,
            manifest.train_domains,
            seed=seed,
            count=manifest.train_cases,
        )
        capsule, train_accuracy = RuleInducer().fit(training)
        if train_accuracy != 1.0:
            raise ValueError(f"P1 could not reconstruct P0 capsule for {opaque_id}")

        counterfactuals = build_counterfactual_cases(
            hidden=hidden,
            seed=seed + 90_000,
        )
        cf_accuracy = counterfactual_accuracy(capsule, counterfactuals)

        ablation_suite = generate_episodes(
            hidden,
            manifest.d3_domains,
            seed=seed + 80_000,
            count=80,
        )
        capsule_score = score_principle(capsule.principle(), ablation_suite)
        irrelevant = HIDDEN_PRINCIPLES[(index + 1) % len(HIDDEN_PRINCIPLES)][1]
        sham = matched_sham(capsule)
        ablated_score = max(
            score_principle(irrelevant, ablation_suite),
            score_principle(sham, ablation_suite),
        )
        control_score = 0.5
        attributable_fraction = ablation_fraction(
            capsule_score=capsule_score,
            ablated_score=ablated_score,
            control_score=control_score,
        )

        reasons: list[str] = []
        if cf_accuracy < COUNTERFACTUAL_GATE:
            reasons.append("counterfactual_accuracy")
        if attributable_fraction < ABLATION_FRACTION_GATE:
            reasons.append("ablation_fraction")
        if capsule.signature != hidden.signature:
            reasons.append("exact_recovery")

        result = P1PrincipleResult(
            opaque_principle_id=opaque_id,
            recovered_signature=capsule.signature,
            counterfactual_accuracy=cf_accuracy,
            counterfactual_cases=len(counterfactuals),
            capsule_score=capsule_score,
            ablated_score=ablated_score,
            balanced_control_score=control_score,
            ablation_fraction=attributable_fraction,
            passed=not reasons,
            failure_reasons=tuple(reasons),
        )
        results.append(result)
        ledger_tip = ledger.append(
            {
                "protocol_version": P1_PROTOCOL_VERSION,
                "p0_manifest_commitment": p0.manifest_commitment,
                "opaque_principle_id": opaque_id,
                "result": asdict(result),
            }
        )

    all_passed = all(result.passed for result in results)
    campaign = P1CampaignResult(
        protocol_version=P1_PROTOCOL_VERSION,
        p0_manifest_commitment=p0.manifest_commitment,
        principle_results=tuple(results),
        all_p1_gates_passed=all_passed,
        clg1_unlocked=False,
        claim=(
            "p1_causal_utility_passed"
            if all_passed
            else "p1_causal_utility_failed"
        ),
        created_at=time.time(),
        evidence_ledger_tip=ledger_tip,
    )
    (workspace / "p1_campaign_result.json").write_text(
        json.dumps(asdict(campaign), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return campaign


def verify_p1(workspace: Path) -> P1CampaignResult:
    p0 = verify_campaign(workspace)
    path = workspace / "p1_campaign_result.json"
    if not path.is_file():
        raise ValueError("P1 campaign result is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    results = tuple(
        P1PrincipleResult(
            **{
                **item,
                "failure_reasons": tuple(item["failure_reasons"]),
            }
        )
        for item in data["principle_results"]
    )
    campaign = P1CampaignResult(
        protocol_version=data["protocol_version"],
        p0_manifest_commitment=data["p0_manifest_commitment"],
        principle_results=results,
        all_p1_gates_passed=data["all_p1_gates_passed"],
        clg1_unlocked=data["clg1_unlocked"],
        claim=data["claim"],
        created_at=data["created_at"],
        evidence_ledger_tip=data["evidence_ledger_tip"],
    )
    if campaign.p0_manifest_commitment != p0.manifest_commitment:
        raise ValueError("P1 is bound to the wrong P0 manifest")

    previous_hash: str | None = None
    ledger_path = workspace / "p1_evidence_ledger.jsonl"
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("P1 evidence ledger is empty")
    from conceptlab import canonical_json, sha256_text

    for line_number, row in enumerate(rows, start=1):
        if row.get("previous_hash") != previous_hash:
            raise ValueError(
                f"P1 evidence predecessor mismatch on line {line_number}"
            )
        payload = {
            key: value
            for key, value in row.items()
            if key != "record_hash"
        }
        record_hash = sha256_text(canonical_json(payload))
        if record_hash != row.get("record_hash"):
            raise ValueError(f"P1 evidence hash mismatch on line {line_number}")
        previous_hash = record_hash
    if previous_hash != campaign.evidence_ledger_tip:
        raise ValueError("P1 evidence ledger tip mismatch")
    return campaign
