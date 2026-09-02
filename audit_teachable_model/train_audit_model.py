#!/usr/bin/env python3
"""
train_audit_model.py

Dependency-free trainer for a tiny audit issue classifier.
It generates synthetic teaching examples from the self_audit_improve.py taxonomy,
trains a pure-Python multinomial Naive Bayes model, and writes audit_model.json.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

LABELS = {
    "syntax_error": {
        "category": "syntax",
        "severity": 10,
        "recommendation": "Fix syntax before deeper analysis.",
    },
    "bare_except": {
        "category": "reliability",
        "severity": 9,
        "recommendation": "Catch a specific exception type.",
    },
    "broad_exception": {
        "category": "reliability",
        "severity": 6,
        "recommendation": "Catch the narrowest expected exception.",
    },
    "high_complexity": {
        "category": "complexity",
        "severity": 7,
        "recommendation": "Split it into smaller functions with one responsibility each.",
    },
    "todo_marker": {
        "category": "maintainability",
        "severity": 4,
        "recommendation": "Resolve it or convert it into a tracked task.",
    },
    "magic_number": {
        "category": "maintainability",
        "severity": 3,
        "recommendation": "Move this value into a named constant if it has domain meaning.",
    },
    "long_line": {
        "category": "style",
        "severity": 3,
        "recommendation": "Wrap the line or extract part of the expression.",
    },
    "missing_docstring": {
        "category": "documentation",
        "severity": 2,
        "recommendation": "Add a short docstring explaining purpose, inputs, and output.",
    },
    "print_usage": {
        "category": "observability",
        "severity": 2,
        "recommendation": "Use logging for production code, or keep print only for CLI output.",
    },
}

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+|==|!=|<=|>=|[(){}\[\]:.,#=+\-*/'\"<>]")


def tokenize(text: str) -> list[str]:
    """Convert code text into simple lexical tokens."""
    return [tok.lower() for tok in TOKEN_RE.findall(text)]


def make_examples() -> list[dict[str, Any]]:
    """Generate synthetic labeled examples from the audit taxonomy."""
    examples: list[dict[str, Any]] = []

    def add(label: str, snippets: list[str]) -> None:
        meta = LABELS[label]
        for snippet in snippets:
            examples.append({"text": snippet, "label": label, **meta})

    add("syntax_error", [
        "def broken(:\n    return 1",
        "if True print('bad')",
        "class Thing\n    pass",
        "for item in items\n    print(item)",
        "def f()\n    return None",
        "x = [1, 2, 3",
    ])
    add("bare_except", [
        "try:\n    risky()\nexcept:\n    pass",
        "try:\n    value = int(raw)\nexcept:\n    value = 0",
        "try:\n    open(path)\nexcept:\n    return None",
        "try:\n    process()\nexcept:\n    print('failed')",
    ])
    add("broad_exception", [
        "try:\n    risky()\nexcept Exception:\n    pass",
        "try:\n    parse(data)\nexcept BaseException:\n    return None",
        "try:\n    value = int(text)\nexcept Exception as error:\n    print(error)",
        "try:\n    run_job()\nexcept Exception:\n    logger.warning('job failed')",
    ])
    add("high_complexity", [
        "def route(x):\n    if x:\n        for i in x:\n            if i > 2:\n                while i:\n                    i -= 1\n    return x",
        "def decide(a,b,c):\n    if a and b:\n        return 1\n    elif b or c:\n        return 2\n    else:\n        return 3",
        "def process(items):\n    for item in items:\n        try:\n            if item.active:\n                handle(item)\n        except ValueError:\n            continue",
        "def nested(x):\n    if x:\n        if x.a:\n            if x.b:\n                if x.c:\n                    return True\n    return False",
    ])
    add("todo_marker", [
        "# TODO fix this parser later",
        "# FIXME handle empty input",
        "# HACK temporary path override",
        "value = 1  # TODO remove hardcoded fallback",
    ])
    add("magic_number", [
        "timeout = 37",
        "if retries > 17:\n    fail()",
        "limit = 256",
        "if score >= 73:\n    approve()",
    ])
    add("long_line", [
        "message = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'",
        "result = some_function_with_a_very_long_name(argument_one, argument_two, argument_three, argument_four, argument_five)",
        "logger.info('This is a very long operational status message that should probably be wrapped or extracted into a constant')",
    ])
    add("missing_docstring", [
        "def analyze(source):\n    return source",
        "class ReportBuilder:\n    pass",
        "async def fetch_data(client):\n    return await client.get('/')",
        "def result_to_dict(result):\n    return result.__dict__",
    ])
    add("print_usage", [
        "print('hello')",
        "def main():\n    print('running')",
        "for issue in issues:\n    print(issue)",
        "print(f'Quality score: {score}')",
    ])

    augmented: list[dict[str, Any]] = []
    for example in examples:
        for prefix in ["", "\n", "# sample\n"]:
            for suffix in ["", "\n", "\n# end"]:
                row = dict(example)
                row["text"] = prefix + example["text"] + suffix
                augmented.append(row)

    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for row in augmented:
        key = (row["text"], row["label"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


@dataclass
class NaiveBayesTextModel:
    """Pure-Python multinomial Naive Bayes classifier."""

    labels: list[str]
    log_priors: dict[str, float]
    log_likelihoods: dict[str, dict[str, float]]
    unknown_log_likelihoods: dict[str, float]
    vocabulary: list[str]
    metadata: dict[str, Any]

    @classmethod
    def train(cls, rows: list[dict[str, Any]], alpha: float = 1.0) -> "NaiveBayesTextModel":
        """Train a bag-of-tokens classifier from labeled audit examples."""
        label_counts = Counter(row["label"] for row in rows)
        token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        vocabulary: set[str] = set()

        for row in rows:
            tokens = tokenize(row["text"])
            token_counts[row["label"]].update(tokens)
            vocabulary.update(tokens)

        labels = sorted(label_counts)
        vocab = sorted(vocabulary)
        total_docs = len(rows)
        log_priors = {label: math.log(label_counts[label] / total_docs) for label in labels}
        log_likelihoods: dict[str, dict[str, float]] = {}
        unknown_log_likelihoods: dict[str, float] = {}

        for label in labels:
            total_tokens = sum(token_counts[label].values())
            denom = total_tokens + alpha * (len(vocab) + 1)
            log_likelihoods[label] = {
                token: math.log((token_counts[label][token] + alpha) / denom)
                for token in vocab
            }
            unknown_log_likelihoods[label] = math.log(alpha / denom)

        return cls(
            labels=labels,
            log_priors=log_priors,
            log_likelihoods=log_likelihoods,
            unknown_log_likelihoods=unknown_log_likelihoods,
            vocabulary=vocab,
            metadata={
                "model_type": "pure_python_multinomial_naive_bayes",
                "training_rows": len(rows),
                "alpha": alpha,
                "purpose": "Classify Python audit issues based on self_audit_improve.py.",
                "labels": LABELS,
            },
        )

    def predict_scores(self, text: str) -> dict[str, float]:
        """Return raw log scores for each label."""
        tokens = tokenize(text)
        scores: dict[str, float] = {}
        for label in self.labels:
            score = self.log_priors[label]
            likelihoods = self.log_likelihoods[label]
            unknown = self.unknown_log_likelihoods[label]
            for token in tokens:
                score += likelihoods.get(token, unknown)
            scores[label] = score
        return scores

    def predict(self, text: str) -> dict[str, Any]:
        """Predict the audit label and attach recommendation metadata."""
        scores = self.predict_scores(text)
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        label = ranked[0][0]
        meta = LABELS[label]
        return {
            "label": label,
            "category": meta["category"],
            "severity": meta["severity"],
            "recommendation": meta["recommendation"],
            "confidence_gap": ranked[0][1] - ranked[1][1] if len(ranked) > 1 else 0.0,
            "top_scores": ranked[:3],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trained model."""
        return asdict(self)


def evaluate(model: NaiveBayesTextModel, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate classification accuracy and per-label behavior."""
    correct = 0
    per_label_total = Counter()
    per_label_correct = Counter()

    for row in rows:
        predicted = model.predict(row["text"])["label"]
        gold = row["label"]
        correct += int(predicted == gold)
        per_label_total[gold] += 1
        per_label_correct[gold] += int(predicted == gold)

    return {
        "accuracy": correct / len(rows) if rows else 0,
        "correct": correct,
        "total": len(rows),
        "per_label_accuracy": {
            label: per_label_correct[label] / per_label_total[label]
            for label in sorted(per_label_total)
        },
    }


def main() -> None:
    """Train the model and write audit_model.json + metrics."""
    random.seed(42)
    rows = make_examples()
    random.shuffle(rows)
    split = int(len(rows) * 0.78)
    train_rows = rows[:split]
    test_rows = rows[split:]

    model = NaiveBayesTextModel.train(train_rows)
    metrics = evaluate(model, test_rows)
    metrics["training_rows"] = len(train_rows)
    metrics["test_rows"] = len(test_rows)
    metrics["note"] = "Synthetic rule-shaped holdout; not proof of real-world generalization."

    Path("audit_model.json").write_text(
        json.dumps(model.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    Path("training_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"trained_rows={len(train_rows)} test_rows={len(test_rows)}")
    print(f"accuracy={metrics['accuracy']:.3f}")


if __name__ == "__main__":
    main()
