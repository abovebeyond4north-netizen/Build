from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

from .capability_model import CapabilityCase
from .capability_sandbox import SkillSandbox


PROTOCOL_VERSION = 1
HIDDEN_CASE_COUNT = 32
SUPPORTED_CAPABILITIES = frozenset(
    {
        "normalize_text",
        "sequence_span",
        "clamp_value",
        "python_error_diagnosis",
    }
)


def evaluator_digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def suite_digest(cases: tuple[CapabilityCase, ...]) -> str:
    payload = [
        {
            "name": case.name,
            "split": case.split,
            "args": list(case.args),
            "expected": case.expected,
        }
        for case in cases
    ]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_hidden_cases(
    capability: str,
    seed: int,
    count: int = HIDDEN_CASE_COUNT,
) -> tuple[CapabilityCase, ...]:
    if capability not in SUPPORTED_CAPABILITIES:
        raise ValueError(f"unsupported protected capability: {capability}")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if isinstance(count, bool) or not isinstance(count, int) or count < 8:
        raise ValueError("count must be an integer of at least 8")

    rng = random.Random(seed)
    if capability == "normalize_text":
        return _normalize_text_cases(rng, count)
    if capability == "sequence_span":
        return _sequence_span_cases(rng, count)
    if capability == "clamp_value":
        return _clamp_cases(rng, count)
    return _python_error_cases(rng, count)


def _normalize_text_cases(
    rng: random.Random,
    count: int,
) -> tuple[CapabilityCase, ...]:
    vocabulary = (
        "Alpha",
        "BETA",
        "MiXeD",
        "CAFÉ",
        "delta",
        "OMEGA",
        "value42",
        "North",
    )
    separators = (" ", "  ", "\t", "\n", " \t ", "\r\n")
    padding = ("", " ", "  ", "\t", "\n")
    cases: list[CapabilityCase] = []
    for index in range(count):
        words: list[str] = []
        for _ in range(rng.randint(1, 5)):
            token = rng.choice(vocabulary)
            transform = rng.randrange(4)
            if transform == 0:
                token = token.lower()
            elif transform == 1:
                token = token.upper()
            elif transform == 2:
                token = token.title()
            words.append(token)
        raw = rng.choice(padding)
        for position, word in enumerate(words):
            if position:
                raw += rng.choice(separators)
            raw += word
        raw += rng.choice(padding)
        expected = " ".join(raw.lower().split())
        cases.append(
            CapabilityCase(
                f"protected_normalize_{index}",
                "holdout",
                (raw,),
                expected,
            )
        )
    return tuple(cases)


def _sequence_span_cases(
    rng: random.Random,
    count: int,
) -> tuple[CapabilityCase, ...]:
    cases: list[CapabilityCase] = []
    for index in range(count):
        values = [
            rng.randint(-120, 120) / 2.0
            for _ in range(rng.randint(2, 8))
        ]
        expected = max(values) - min(values)
        cases.append(
            CapabilityCase(
                f"protected_span_{index}",
                "holdout",
                (values,),
                expected,
            )
        )
    return tuple(cases)


def _clamp_cases(
    rng: random.Random,
    count: int,
) -> tuple[CapabilityCase, ...]:
    cases: list[CapabilityCase] = []
    for index in range(count):
        lower = rng.randint(-80, 20) / 2.0
        upper = lower + rng.randint(1, 60) / 2.0
        value = rng.randint(
            int(lower * 2) - 40,
            int(upper * 2) + 40,
        ) / 2.0
        expected = min(max(value, lower), upper)
        cases.append(
            CapabilityCase(
                f"protected_clamp_{index}",
                "holdout",
                (value, lower, upper),
                expected,
            )
        )
    return tuple(cases)


def _python_error_cases(
    rng: random.Random,
    count: int,
) -> tuple[CapabilityCase, ...]:
    names = ("payload", "matrix", "cursor", "cache", "record", "sample")
    type_templates = (
        "TypeError: object of type 'float' has no len()",
        "TypeError: 'int' object is not iterable",
        "TypeError: unsupported operand type(s) for -: 'str' and 'int'",
        "TypeError: list indices must be integers or slices, not str",
    )
    index_templates = (
        "IndexError: list index out of range",
        "IndexError: tuple index out of range",
        "IndexError: string index out of range",
        "IndexError: list assignment index out of range",
    )
    categories = ("undefined_name", "type_mismatch", "bad_index")
    cases: list[CapabilityCase] = []
    for index in range(count):
        category = categories[index % len(categories)]
        if category == "undefined_name":
            message = (
                f"NameError: name '{rng.choice(names)}_{rng.randrange(1000)}' "
                "is not defined"
            )
        elif category == "type_mismatch":
            message = rng.choice(type_templates)
        else:
            message = rng.choice(index_templates)
        cases.append(
            CapabilityCase(
                f"protected_python_error_{index}",
                "holdout",
                (message,),
                category,
            )
        )
    rng.shuffle(cases)
    return tuple(cases)


def containment_self_test() -> tuple[bool, tuple[str, ...]]:
    sandbox = SkillSandbox(timeout_seconds=0.12)
    failures: list[str] = []

    forbidden = {
        "import": "import os\n\ndef solve(x0):\n    return x0\n",
        "filesystem": "def solve(x0):\n    return open('probe.txt', 'w')\n",
        "dunder": "def solve(x0):\n    return x0.__class__\n",
    }
    for name, source in forbidden.items():
        passed, _ = sandbox.validate_source(source, "solve")
        if passed:
            failures.append(f"{name}_probe_was_not_blocked")

    safe, reasons = sandbox.validate_source(
        "def solve(x0):\n    return x0\n",
        "solve",
    )
    if not safe:
        failures.append(f"safe_probe_rejected:{'|'.join(reasons)}")

    timeout = sandbox.evaluate(
        "def solve(x0):\n    while True:\n        pass\n",
        "solve",
        (CapabilityCase("timeout_probe", "holdout", (1,), 1),),
    )
    if not any("timed out" in error for error in timeout.errors):
        failures.append("timeout_probe_was_not_terminated")

    return not failures, tuple(failures)


def evaluate_request(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("protocol version mismatch")
    capability = request.get("capability")
    entrypoint = request.get("entrypoint")
    baseline_source = request.get("baseline_source")
    finalist_source = request.get("finalist_source")
    seed = request.get("seed")

    if not isinstance(capability, str) or capability not in SUPPORTED_CAPABILITIES:
        raise ValueError("unsupported capability")
    if not isinstance(entrypoint, str) or not entrypoint.isidentifier():
        raise ValueError("invalid entrypoint")
    if not isinstance(baseline_source, str) or not baseline_source.strip():
        raise ValueError("invalid baseline source")
    if not isinstance(finalist_source, str) or not finalist_source.strip():
        raise ValueError("invalid finalist source")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("invalid seed")

    containment_passed, containment_failures = containment_self_test()
    cases = build_hidden_cases(capability, seed)
    response: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "evaluator_digest": evaluator_digest(),
        "suite_digest": suite_digest(cases),
        "case_count": len(cases),
        "containment_passed": containment_passed,
        "containment_failures": list(containment_failures),
    }
    if not containment_passed:
        response.update(
            {
                "baseline_score": 0.0,
                "finalist_score": 0.0,
            }
        )
        return response

    sandbox = SkillSandbox(timeout_seconds=2.0)
    baseline = sandbox.evaluate(baseline_source, entrypoint, cases)
    finalist = sandbox.evaluate(finalist_source, entrypoint, cases)
    response.update(
        {
            "baseline_score": baseline.correctness,
            "finalist_score": finalist.correctness,
            "baseline_errors": list(baseline.errors),
            "finalist_errors": list(finalist.errors),
        }
    )
    return response


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        response = evaluate_request(request)
        sys.stdout.write(json.dumps(response, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        sys.stdout.write(
            json.dumps(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
