#!/usr/bin/env python3
"""
predict_audit_issue.py

Use audit_model.json to classify a small Python snippet into the audit taxonomy.
Run `python train_audit_model.py` first to generate audit_model.json.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+|==|!=|<=|>=|[(){}\[\]:.,#=+\-*/'\"<>]")


def tokenize(text: str) -> list[str]:
    """Convert code text into simple lexical tokens."""
    return [tok.lower() for tok in TOKEN_RE.findall(text)]


def load_model(path: Path) -> dict[str, Any]:
    """Load the trained JSON model."""
    return json.loads(path.read_text(encoding="utf-8"))


def predict(model: dict[str, Any], text: str) -> dict[str, Any]:
    """Predict the most likely audit issue for the given code text."""
    tokens = tokenize(text)
    scores: dict[str, float] = {}

    for label in model["labels"]:
        score = model["log_priors"][label]
        likelihoods = model["log_likelihoods"][label]
        unknown = model["unknown_log_likelihoods"][label]

        for token in tokens:
            score += likelihoods.get(token, unknown)

        scores[label] = score

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    label = ranked[0][0]
    labels_meta = model["metadata"]["labels"]
    meta = labels_meta[label]

    return {
        "label": label,
        "category": meta["category"],
        "severity": meta["severity"],
        "recommendation": meta["recommendation"],
        "confidence_gap": ranked[0][1] - ranked[1][1] if len(ranked) > 1 else 0.0,
        "top_scores": ranked[:3],
    }


def main() -> None:
    """Read a file path or stdin, then print a JSON prediction."""
    model_path = Path("audit_model.json")
    if not model_path.exists():
        raise SystemExit("Missing audit_model.json. Run: python train_audit_model.py")

    model = load_model(model_path)

    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    print(json.dumps(predict(model, text), indent=2))


if __name__ == "__main__":
    main()
