from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
WORKSPACE = PROJECT_ROOT / ".dgm_dashboard_evidence"
EVIDENCE_PATH = WORKSPACE / "capability-evidence.json"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dgm_zero.capability import CapabilityAcquirer
from dgm_zero.capability_model import (
    CapabilityCase,
    CapabilityEvidencePolicy,
    CapabilitySpec,
    CapabilityThresholds,
)
from dgm_zero.reliability_gate import ReliabilityLedger
from dgm_zero.skill_library import certification_record_hash


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def build_spec() -> CapabilitySpec:
    train = (
        ("train_basic", "  Hello   WORLD  ", "hello world"),
        ("train_two_tokens", "A  B", "a b"),
        ("train_mixed_ws", "\tMixed\nCASE ", "mixed case"),
        ("train_accent", "  Café   TEST ", "café test"),
        ("train_crlf", "ONE\r\nTwo", "one two"),
        ("train_leading", "  Leading", "leading"),
    )
    validation = (
        ("validation_trailing", " Trailing   ", "trailing"),
        ("validation_tabs", "Alpha\t BETA\tGamma", "alpha beta gamma"),
        ("validation_gaps", "  many    internal   gaps ", "many internal gaps"),
        ("validation_lines", "Line1\nLine2", "line1 line2"),
        ("validation_accent", "ÉCOLE   TEST", "école test"),
        ("validation_clean", "Already clean", "already clean"),
    )
    holdout = (
        ("holdout_01", "\tNEW   Value\n", "new value"),
        ("holdout_02", "FOO\tBAR", "foo bar"),
        ("holdout_03", "  Hello\nthere  WORLD ", "hello there world"),
        ("holdout_04", "Mixed\r\nWhitespace\tHERE", "mixed whitespace here"),
        ("holdout_05", "  café\tAU lait ", "café au lait"),
        ("holdout_06", "Résumé   TEST", "résumé test"),
        ("holdout_07", "ONE TWO THREE", "one two three"),
        ("holdout_08", " lower  CASE ", "lower case"),
        ("holdout_09", "UPPER", "upper"),
        ("holdout_10", "  single  ", "single"),
        ("holdout_11", "a\tb\nc\rd", "a b c d"),
        ("holdout_12", "  Numbers  123  ", "numbers 123"),
        ("holdout_13", "Symbols !  OK ?", "symbols ! ok ?"),
        ("holdout_14", "Alpha\u00a0Beta", "alpha beta"),
        ("holdout_15", "  déjà   VU  ", "déjà vu"),
        ("holdout_16", "MÜNCHEN  CITY", "münchen city"),
        ("holdout_17", "  naïve\tTEST", "naïve test"),
        ("holdout_18", "line\n\nbreak", "line break"),
        ("holdout_19", "CRLF\r\nTEST", "crlf test"),
        ("holdout_20", "spaces      only", "spaces only"),
        ("holdout_21", " x \t y \n z ", "x y z"),
        ("holdout_22", "CASE with Mixed", "case with mixed"),
        ("holdout_23", "trim\tand   lower", "trim and lower"),
        ("holdout_24", "Final   HOLDOUT", "final holdout"),
    )

    cases = tuple(
        CapabilityCase(name, split, (value,), expected)
        for split, rows in (
            ("train", train),
            ("validation", validation),
            ("holdout", holdout),
        )
        for name, value, expected in rows
    )
    return CapabilitySpec(
        name="normalize_text_evidence_v1",
        description=(
            "Acquire a pure text-normalization skill while keeping a 24-case "
            "holdout unavailable to candidate generation and finalist selection."
        ),
        entrypoint="solve",
        cases=cases,
        thresholds=CapabilityThresholds(
            train=1.0,
            validation=1.0,
            holdout=1.0,
            min_gain=0.50,
        ),
        evidence=CapabilityEvidencePolicy(
            min_train_cases=len(train),
            min_validation_cases=len(validation),
            min_holdout_cases=len(holdout),
            max_validation_trials_per_case=4,
        ),
    )


def latest_certification(capability: str) -> dict[str, object]:
    path = WORKSPACE / "capability_certifications.jsonl"
    require(path.is_file(), "capability certification ledger is missing")
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [row for row in rows if row.get("capability") == capability]
    require(bool(matches), "capability certification record is missing")
    record = matches[-1]
    require(
        certification_record_hash(record) == record.get("record_hash"),
        "capability certification record hash is invalid",
    )
    return record


def receipt_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)

    spec = build_spec()
    report = CapabilityAcquirer(WORKSPACE).acquire(
        spec,
        validation_budget=24,
    )

    require(report.promoted, f"evidence capability was not promoted: {report.status}")
    require(report.baseline_score == 0.0, "expected a zero-score null baseline")
    require(report.final_score == 1.0, "candidate did not reach a perfect final score")
    require(report.holdout_score == 1.0, "candidate did not pass the sealed holdout")
    require(report.holdout_evaluations == 1, "holdout must be evaluated exactly once")
    require(report.finalist_digest is not None, "finalist digest is missing")

    reliability_records = [
        record
        for record in ReliabilityLedger(WORKSPACE).records()
        if record.capability == spec.name
        and record.finalist_digest == report.finalist_digest
    ]
    require(bool(reliability_records), "reliability-gate receipt is missing")
    reliability = reliability_records[-1]
    require(reliability.passed, f"reliability gate failed: {reliability.reason}")
    require(reliability.baseline_stable, "baseline replay was order-sensitive")
    require(reliability.finalist_stable, "finalist replay was order-sensitive")
    require(len(reliability.trials) >= 2, "reliability evidence did not replicate")

    certification = latest_certification(spec.name)
    require(certification.get("passed") is True, "holdout certification did not pass")
    require(
        certification.get("holdout_digest") == report.holdout_digest,
        "certification holdout digest does not match report",
    )
    require(
        certification.get("finalist_digest") == report.finalist_digest,
        "certification finalist digest does not match report",
    )

    receipt_payload = {
        "report": asdict(report),
        "reliability_record_hash": reliability.record_hash,
        "certification_record_hash": certification.get("record_hash"),
    }
    sealed_receipt_hash = receipt_hash(receipt_payload)

    evidence = {
        "schemaVersion": 1,
        "capability": spec.name,
        "scope": "bounded_pure_function_skill_acquisition",
        "learnerPrior": (
            "The starter learner uses a hand-authored template grammar; this receipt "
            "demonstrates verified acquisition/selection, not unrestricted invention."
        ),
        "evaluator": {
            "independent": True,
            "hiddenFromLearner": True,
            "independenceType": "architectural",
            "mechanism": (
                "Candidate generation receives TrainingView containing training cases "
                "only. Validation is owned by the acquisition controller and the "
                "holdout opens only after finalist selection and reliability replay."
            ),
        },
        "holdout": {
            "unseen": True,
            "taskCount": len(spec.cases_for("holdout")),
            "contaminationDetected": False,
            "contaminationBasis": (
                "No validation or holdout cases are passed through the CandidateGenerator "
                "interface; the holdout is evaluated exactly once after the finalist is fixed."
            ),
            "digest": report.holdout_digest,
        },
        "baseline": {
            "score": report.baseline_score,
            "artifactDigest": report.baseline_digest,
        },
        "candidate": {
            "score": report.final_score,
            "artifactDigest": report.finalist_digest,
        },
        "replication": {
            "count": len(reliability.trials),
            "consistent": (
                reliability.passed
                and reliability.baseline_stable
                and reliability.finalist_stable
            ),
            "minimumGain": reliability.minimum_gain,
            "worstDelta": reliability.worst_delta,
            "meanDelta": reliability.mean_delta,
        },
        "unrelatedRegressionDetected": False,
        "unrelatedRegressionBasis": (
            "The promoted artifact is a content-addressed capability-specific pure "
            "function; promotion does not mutate shared runtime or other installed skills."
        ),
        "provenance": {
            "baselineArtifact": f"sha256:{report.baseline_digest}",
            "candidateArtifact": f"sha256:{report.finalist_digest}",
            "taskSetCommitment": report.holdout_digest,
            "receiptHash": sealed_receipt_hash,
            "reliabilityRecordHash": reliability.record_hash,
            "certificationRecordHash": certification.get("record_hash"),
        },
        "generatedAt": report.created_at,
    }

    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Dashboard capability evidence generated")
    print(f"path: {EVIDENCE_PATH}")
    print(f"capability: {spec.name}")
    print(f"held-out tasks: {len(spec.cases_for('holdout'))}")
    print(f"baseline -> candidate: {report.baseline_score:.3f} -> {report.final_score:.3f}")
    print(f"replay trials: {len(reliability.trials)}")
    print(f"receipt: {sealed_receipt_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
