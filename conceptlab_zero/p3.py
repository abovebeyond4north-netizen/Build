from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from conceptlab import (
    EvidenceLedger,
    Episode,
    GRAMMAR,
    RuleInducer,
    canonical_json,
    episodes_size_bytes,
    extract_numeric_pair,
    normalized_pair,
    render_observation,
    score_principle,
    sha256_text,
)
from p2 import verify_p2


P3_PROTOCOL_VERSION = 1
TRAIN_ACCURACY_GATE = 0.98
D5_ACCURACY_GATE = 0.95
P0_CONTROL_GAIN_GATE = 0.20
COMPRESSION_GATE = 4.0
RESTART_GATE = 0.95


@dataclass(frozen=True)
class PredicateProgram:
    a: int
    b: int
    bias: int
    absolute: bool
    predicate: str
    modulus: int = 0
    target: int = 0

    def scalar(self, left: int, right: int) -> int:
        value = self.a * left + self.b * right + self.bias
        return abs(value) if self.absolute else value

    def apply(self, left: int, right: int) -> bool:
        value = self.scalar(left, right)
        if self.predicate == "mod_eq":
            if self.modulus < 2:
                raise ValueError("modulus must be >= 2")
            return value % self.modulus == self.target
        if self.predicate == "ge":
            return value >= self.target
        if self.predicate == "eq":
            return value == self.target
        raise ValueError(f"unknown predicate: {self.predicate}")

    @property
    def signature(self) -> str:
        scalar = (
            f"abs({self.a}*x+{self.b}*y+{self.bias})"
            if self.absolute
            else f"{self.a}*x+{self.b}*y+{self.bias}"
        )
        if self.predicate == "mod_eq":
            return f"({scalar})%{self.modulus}=={self.target}"
        return f"{scalar}{'>=' if self.predicate == 'ge' else '=='}{self.target}"

    @property
    def complexity(self) -> int:
        coefficient_cost = abs(self.a) + abs(self.b)
        bias_cost = abs(self.bias)
        absolute_cost = 2 if self.absolute else 0
        predicate_cost = 3 if self.predicate == "mod_eq" else 1
        modulus_cost = self.modulus if self.predicate == "mod_eq" else 0
        return coefficient_cost + bias_cost + absolute_cost + predicate_cost + modulus_cost


@dataclass(frozen=True)
class SynthesisResult:
    opaque_target_id: str
    synthesized_signature: str
    search_candidates: int
    train_accuracy: float
    d5_accuracy: float
    p0_control_accuracy: float
    p0_control_gain: float
    compression_ratio: float
    structural_collisions: int
    restart_accuracy: float
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class P3CampaignResult:
    protocol_version: int
    p2_evidence_ledger_tip: str | None
    synthesis_results: tuple[SynthesisResult, ...]
    all_p3_gates_passed: bool
    clg1_unlocked: bool
    claim: str
    created_at: float
    evidence_ledger_tip: str | None


HIDDEN_TARGETS: tuple[tuple[str, PredicateProgram], ...] = (
    (
        "sp_31c9",
        PredicateProgram(
            a=1,
            b=1,
            bias=0,
            absolute=False,
            predicate="mod_eq",
            modulus=3,
            target=1,
        ),
    ),
    (
        "sp_7a20",
        PredicateProgram(
            a=2,
            b=1,
            bias=0,
            absolute=False,
            predicate="ge",
            target=3,
        ),
    ),
    (
        "sp_b816",
        PredicateProgram(
            a=1,
            b=1,
            bias=0,
            absolute=True,
            predicate="ge",
            target=7,
        ),
    ),
    (
        "sp_d402",
        PredicateProgram(
            a=1,
            b=-2,
            bias=1,
            absolute=False,
            predicate="mod_eq",
            modulus=5,
            target=2,
        ),
    ),
)


def generate_program_grammar() -> tuple[PredicateProgram, ...]:
    programs: list[PredicateProgram] = []
    seen: set[str] = set()
    for a in range(-2, 3):
        for b in range(-2, 3):
            if a == 0 and b == 0:
                continue
            for bias in range(-3, 4):
                for absolute in (False, True):
                    for modulus in (2, 3, 5):
                        for residue in range(modulus):
                            program = PredicateProgram(
                                a=a,
                                b=b,
                                bias=bias,
                                absolute=absolute,
                                predicate="mod_eq",
                                modulus=modulus,
                                target=residue,
                            )
                            if program.signature not in seen:
                                seen.add(program.signature)
                                programs.append(program)
                    for threshold in (-7, -3, 0, 3, 7):
                        for predicate in ("ge", "eq"):
                            program = PredicateProgram(
                                a=a,
                                b=b,
                                bias=bias,
                                absolute=absolute,
                                predicate=predicate,
                                target=threshold,
                            )
                            if program.signature not in seen:
                                seen.add(program.signature)
                                programs.append(program)
    programs.sort(key=lambda p: (p.complexity, p.signature))
    return tuple(programs)


PROGRAM_GRAMMAR = generate_program_grammar()


def score_program(program: PredicateProgram, episodes: tuple[Episode, ...]) -> float:
    if not episodes:
        return 0.0
    correct = 0
    for episode in episodes:
        left, right = extract_numeric_pair(episode.observation)
        if program.apply(left, right) == episode.label:
            correct += 1
    return correct / len(episodes)


class SymbolicSynthesizer:
    """Enumerate compact predicates from lower-level arithmetic operators.

    Hidden P3 predicates are not provided as named candidates. The learner gets
    only this program-construction language and selects a minimal program from
    experience. This remains a bounded symbolic search, not unrestricted program
    invention.
    """

    def __init__(self, programs: tuple[PredicateProgram, ...] = PROGRAM_GRAMMAR) -> None:
        if not programs:
            raise ValueError("program grammar must be non-empty")
        self.programs = programs

    def fit(self, episodes: tuple[Episode, ...]) -> tuple[PredicateProgram, float, int]:
        if not episodes:
            raise ValueError("episodes must be non-empty")
        ranked: list[tuple[int, int, str, PredicateProgram]] = []
        for program in self.programs:
            correct = sum(
                program.apply(*extract_numeric_pair(episode.observation))
                == episode.label
                for episode in episodes
            )
            ranked.append(
                (
                    -correct,
                    program.complexity,
                    program.signature,
                    program,
                )
            )
        ranked.sort(key=lambda row: (row[0], row[1], row[2]))
        best = ranked[0]
        return best[3], -best[0] / len(episodes), len(self.programs)


def _value_pool(low: int, high: int) -> tuple[int, ...]:
    if low >= high:
        raise ValueError("low must be less than high")
    return tuple(range(low, high + 1))


def generate_program_episodes(
    hidden: PredicateProgram,
    *,
    domains: tuple[str, ...],
    seed: int,
    count: int,
    low: int,
    high: int,
    exclude_pairs: frozenset[tuple[int, int]] = frozenset(),
) -> tuple[Episode, ...]:
    if count < 2:
        raise ValueError("count must be at least two")
    rng = random.Random(seed)
    values = _value_pool(low, high)
    pairs = [
        (left, right)
        for left in values
        for right in values
        if normalized_pair(left, right) not in exclude_pairs
    ]
    rng.shuffle(pairs)
    positives = [pair for pair in pairs if hidden.apply(*pair)]
    negatives = [pair for pair in pairs if not hidden.apply(*pair)]
    pos_count = count // 2
    neg_count = count - pos_count
    if len(positives) < pos_count or len(negatives) < neg_count:
        raise ValueError("program target cannot support balanced suite")
    chosen = positives[:pos_count] + negatives[:neg_count]
    rng.shuffle(chosen)
    episodes = []
    for index, pair in enumerate(chosen):
        domain = domains[index % len(domains)]
        episodes.append(
            Episode(
                domain=domain,
                observation=render_observation(
                    domain,
                    pair[0],
                    pair[1],
                    rng,
                ),
                label=hidden.apply(*pair),
            )
        )
    return tuple(episodes)


def pair_keys(episodes: Iterable[Episode]) -> frozenset[tuple[int, int]]:
    return frozenset(
        normalized_pair(*extract_numeric_pair(episode.observation))
        for episode in episodes
    )


def program_size_bytes(program: PredicateProgram) -> int:
    return len(canonical_json(asdict(program)).encode("utf-8"))


class ProgramStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, program_id: str, program: PredicateProgram) -> str:
        digest = sha256_text(canonical_json(asdict(program)))
        versions = self.root / program_id / "versions"
        versions.mkdir(parents=True, exist_ok=True)
        version_path = versions / f"{digest}.json"
        version_path.write_text(
            json.dumps(asdict(program), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "program_id": program_id,
            "digest": digest,
            "relative_path": str(version_path.relative_to(self.root / program_id)),
        }
        (self.root / program_id / "current.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return digest

    def load(self, program_id: str) -> tuple[PredicateProgram, str]:
        root = self.root / program_id
        manifest = json.loads((root / "current.json").read_text(encoding="utf-8"))
        path = (root / manifest["relative_path"]).resolve()
        resolved = root.resolve()
        if resolved not in path.parents:
            raise ValueError("program path escapes store")
        program = PredicateProgram(**json.loads(path.read_text(encoding="utf-8")))
        digest = sha256_text(canonical_json(asdict(program)))
        if digest != manifest["digest"]:
            raise ValueError("program digest mismatch")
        return program, digest


def _best_p0_control(
    training: tuple[Episode, ...],
    holdout: tuple[Episode, ...],
) -> tuple[float, str]:
    capsule, _ = RuleInducer().fit(training)
    return score_principle(capsule.principle(), holdout), capsule.signature


def _fresh_probe(
    *,
    store_path: Path,
) -> dict[str, float]:
    script = Path(__file__).resolve().parent / "scripts" / "p3_restart_probe.py"
    completed = subprocess.run(
        [sys.executable, str(script), str(store_path)],
        cwd=str(Path(__file__).resolve().parent),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def run_p3_restart_probe(store_path: Path) -> dict[str, float]:
    store = ProgramStore(store_path)
    scores: dict[str, float] = {}
    for index, (target_id, hidden) in enumerate(HIDDEN_TARGETS):
        program, _ = store.load(target_id)
        suite = generate_program_episodes(
            hidden,
            domains=("deep", "pipe"),
            seed=99000 + index,
            count=100,
            low=-220,
            high=220,
        )
        scores[target_id] = score_program(program, suite)
    return scores


def run_p3(workspace: Path) -> P3CampaignResult:
    p2 = verify_p2(workspace)
    if not p2.all_p2_gates_passed:
        raise ValueError("P3 requires a verified passing P2 campaign")

    store_path = workspace / "symbolic_program_store"
    if store_path.exists():
        shutil.rmtree(store_path)
    store = ProgramStore(store_path)
    synthesizer = SymbolicSynthesizer()
    preliminary: list[dict[str, object]] = []

    for index, (target_id, hidden) in enumerate(HIDDEN_TARGETS):
        training = generate_program_episodes(
            hidden,
            domains=("list", "map"),
            seed=81000 + index,
            count=96,
            low=-36,
            high=36,
        )
        holdout = generate_program_episodes(
            hidden,
            domains=("deep", "pipe"),
            seed=82000 + index,
            count=120,
            low=-180,
            high=180,
            exclude_pairs=pair_keys(training),
        )
        program, train_accuracy, searched = synthesizer.fit(training)
        d5_accuracy = score_program(program, holdout)
        p0_control, p0_signature = _best_p0_control(training, holdout)
        collisions = len(pair_keys(training) & pair_keys(holdout))
        compression = episodes_size_bytes(training) / program_size_bytes(program)
        store.save(target_id, program)
        preliminary.append(
            {
                "target_id": target_id,
                "program": program,
                "searched": searched,
                "train_accuracy": train_accuracy,
                "d5_accuracy": d5_accuracy,
                "p0_control": p0_control,
                "p0_signature": p0_signature,
                "collisions": collisions,
                "compression": compression,
            }
        )

    restart_scores = _fresh_probe(store_path=store_path)
    results: list[SynthesisResult] = []
    ledger = EvidenceLedger(workspace / "p3_evidence_ledger.jsonl")
    ledger_tip: str | None = None

    for row in preliminary:
        target_id = str(row["target_id"])
        program = row["program"]
        assert isinstance(program, PredicateProgram)
        train_accuracy = float(row["train_accuracy"])
        d5_accuracy = float(row["d5_accuracy"])
        p0_control = float(row["p0_control"])
        gain = d5_accuracy - p0_control
        compression = float(row["compression"])
        collisions = int(row["collisions"])
        restart_accuracy = float(restart_scores[target_id])

        reasons: list[str] = []
        if train_accuracy < TRAIN_ACCURACY_GATE:
            reasons.append("train_accuracy")
        if d5_accuracy < D5_ACCURACY_GATE:
            reasons.append("d5_accuracy")
        if gain < P0_CONTROL_GAIN_GATE:
            reasons.append("p0_control_gain")
        if compression < COMPRESSION_GATE:
            reasons.append("compression")
        if collisions != 0:
            reasons.append("structural_leakage")
        if restart_accuracy < RESTART_GATE:
            reasons.append("restart_accuracy")
        if any(program.signature == principle.signature for principle in GRAMMAR):
            reasons.append("p0_literal_reuse")

        result = SynthesisResult(
            opaque_target_id=target_id,
            synthesized_signature=program.signature,
            search_candidates=int(row["searched"]),
            train_accuracy=train_accuracy,
            d5_accuracy=d5_accuracy,
            p0_control_accuracy=p0_control,
            p0_control_gain=gain,
            compression_ratio=compression,
            structural_collisions=collisions,
            restart_accuracy=restart_accuracy,
            passed=not reasons,
            failure_reasons=tuple(reasons),
        )
        results.append(result)
        ledger_tip = ledger.append(
            {
                "protocol_version": P3_PROTOCOL_VERSION,
                "p2_evidence_ledger_tip": p2.evidence_ledger_tip,
                "opaque_target_id": target_id,
                "p0_control_signature": row["p0_signature"],
                "result": asdict(result),
            }
        )

    all_passed = all(result.passed for result in results)
    campaign = P3CampaignResult(
        protocol_version=P3_PROTOCOL_VERSION,
        p2_evidence_ledger_tip=p2.evidence_ledger_tip,
        synthesis_results=tuple(results),
        all_p3_gates_passed=all_passed,
        clg1_unlocked=False,
        claim=(
            "p3_withheld_predicate_synthesis_passed"
            if all_passed
            else "p3_withheld_predicate_synthesis_failed"
        ),
        created_at=time.time(),
        evidence_ledger_tip=ledger_tip,
    )
    (workspace / "p3_campaign_result.json").write_text(
        json.dumps(asdict(campaign), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / "p3_restart_receipt.json").write_text(
        json.dumps(restart_scores, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return campaign


def verify_p3(workspace: Path) -> P3CampaignResult:
    p2 = verify_p2(workspace)
    path = workspace / "p3_campaign_result.json"
    if not path.is_file():
        raise ValueError("P3 campaign result is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    results = tuple(
        SynthesisResult(
            **{
                **item,
                "failure_reasons": tuple(item["failure_reasons"]),
            }
        )
        for item in data["synthesis_results"]
    )
    campaign = P3CampaignResult(
        protocol_version=data["protocol_version"],
        p2_evidence_ledger_tip=data["p2_evidence_ledger_tip"],
        synthesis_results=results,
        all_p3_gates_passed=data["all_p3_gates_passed"],
        clg1_unlocked=data["clg1_unlocked"],
        claim=data["claim"],
        created_at=data["created_at"],
        evidence_ledger_tip=data["evidence_ledger_tip"],
    )
    if campaign.p2_evidence_ledger_tip != p2.evidence_ledger_tip:
        raise ValueError("P3 is bound to the wrong P2 evidence ledger")

    rows = [
        json.loads(line)
        for line in (workspace / "p3_evidence_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    previous_hash: str | None = None
    for line_number, row in enumerate(rows, start=1):
        if row.get("previous_hash") != previous_hash:
            raise ValueError(
                f"P3 evidence predecessor mismatch on line {line_number}"
            )
        payload = {
            key: value
            for key, value in row.items()
            if key != "record_hash"
        }
        record_hash = sha256_text(canonical_json(payload))
        if record_hash != row.get("record_hash"):
            raise ValueError(f"P3 evidence hash mismatch on line {line_number}")
        previous_hash = record_hash
    if not rows or previous_hash != campaign.evidence_ledger_tip:
        raise ValueError("P3 evidence ledger tip mismatch")
    return campaign
