from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .benchmark import eval_expr


PROBES: tuple[tuple[int, int], ...] = (
    (-8, -3),
    (-5, 0),
    (-2, 7),
    (0, 0),
    (1, -9),
    (3, 4),
    (9, -1),
    (12, 5),
)


@dataclass(frozen=True)
class BehaviorSignature:
    digest: str
    bucket: str
    outputs: tuple[int | str, ...]


def expression_signature(expression: str) -> BehaviorSignature:
    """Create a compact behaviour signature for quality-diversity tracking."""

    outputs: list[int | str] = []
    for a, b in PROBES:
        try:
            outputs.append(eval_expr(expression, a, b))
        except Exception as exc:
            outputs.append(type(exc).__name__)
    payload = repr(tuple(outputs)).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    size_bucket = "short" if len(expression) <= 24 else "medium" if len(expression) <= 64 else "long"
    sign_bucket = classify_outputs(outputs)
    return BehaviorSignature(digest=digest, bucket=f"{size_bucket}:{sign_bucket}", outputs=tuple(outputs))


def classify_outputs(outputs: list[int | str]) -> str:
    numeric = [value for value in outputs if isinstance(value, int)]
    if not numeric:
        return "error"
    has_negative = any(value < 0 for value in numeric)
    has_positive = any(value > 0 for value in numeric)
    if has_negative and has_positive:
        return "mixed"
    if has_negative:
        return "negative"
    if has_positive:
        return "positive"
    return "zero"
