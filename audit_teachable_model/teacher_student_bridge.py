#!/usr/bin/env python3
"""Teacher-student bridge: self_audit_improve.py labels snippets, then the tiny model learns them."""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SELF_AUDIT = ROOT / "self_audit_improve.py"
MODEL_OUT = HERE / "teacher_audit_model.json"
ROWS_OUT = HERE / "teacher_labeled_examples.jsonl"
METRICS_OUT = HERE / "teacher_training_metrics.json"

sys.path.insert(0, str(HERE))
from train_audit_model import LABELS, NaiveBayesTextModel, evaluate  # noqa: E402

BARE_EXCEPT_RE = re.compile(r"except\s*:")
BROAD_EXCEPTION_RE = re.compile(r"except\s+(Exception|BaseException)\b")
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)


def load_teacher() -> Any:
    spec = importlib.util.spec_from_file_location("self_audit_improve", SELF_AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {SELF_AUDIT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["self_audit_improve"] = module
    spec.loader.exec_module(module)
    return module.SelfAuditImproveTool()


def issue_label(issue: Any) -> str | None:
    cat, problem = issue.category.lower(), issue.problem.lower()
    if cat == "syntax":
        return "syntax_error"
    if cat == "style" and "line exceeds" in problem:
        return "long_line"
    if cat == "documentation" and "no docstring" in problem:
        return "missing_docstring"
    if cat == "observability" and "print" in problem:
        return "print_usage"
    if cat == "complexity":
        return "high_complexity"
    if cat == "reliability" and "bare except" in problem:
        return "bare_except"
    if cat == "reliability" and "broad" in problem:
        return "broad_exception"
    if cat == "maintainability" and "marker" in problem:
        return "todo_marker"
    if cat == "maintainability" and "magic number" in problem:
        return "magic_number"
    return None


def snippets() -> list[str]:
    long_text = "x" * 130
    return [
        "def broken(:\n    return 1",
        "if True print('bad')",
        "class MissingColon\n    pass",
        "for item in items\n    print(item)",
        "try:\n    risky()\nexcept:\n    pass",
        "try:\n    value = int(raw)\nexcept:\n    value = 0",
        "try:\n    risky()\nexcept Exception:\n    pass",
        "try:\n    risky()\nexcept BaseException:\n    pass",
        "try:\n    parse(data)\nexcept Exception as error:\n    print(error)",
        "def monster(a,b,c,d):\n    if a and b:\n        for x in a:\n            if x:\n                while b:\n                    try:\n                        if c or d:\n                            return x\n                    except ValueError:\n                        break\n    return None",
        "# TODO replace temporary fallback\nvalue = 1",
        "# FIXME validate file shape\nreturn_value = None",
        "# HACK keep compatibility for legacy callers\nlegacy = True",
        "timeout = 37",
        "if score >= 73:\n    approve()",
        "buffer_size = 256",
        f"message = '{long_text}'",
        "result = some_function_with_a_very_long_name(argument_one, argument_two, argument_three, argument_four, argument_five)",
        "def analyze(source):\n    return source",
        "class ReportBuilder:\n    pass",
        "async def fetch_data(client):\n    return await client.get('/')",
        "print('hello')",
        "def main():\n    print('running')",
        "for issue in issues:\n    print(issue)",
        "print(f'Quality score: {score}')",
    ]


def variants(text: str) -> list[str]:
    seen, out = set(), []
    for prefix in ("", "\n", "# sample\n"):
        for suffix in ("", "\n", "\n# end"):
            value = prefix + text + suffix
            if value not in seen:
                seen.add(value)
                out.append(value)
    return out


def generate_rows(strictness: str = "high") -> list[dict[str, Any]]:
    teacher, rows = load_teacher(), []
    for i, seed in enumerate(snippets(), 1):
        for j, text in enumerate(variants(seed), 1):
            result = teacher.run(text, target=f"teacher_{i}_{j}", strictness=strictness, allow_patch_generation=False)
            for issue in result.issues:
                label = issue_label(issue)
                if label:
                    rows.append({
                        "text": text,
                        "label": label,
                        "category": issue.category,
                        "severity": issue.severity,
                        "problem": issue.problem,
                        "recommendation": issue.recommendation,
                        "teacher": "self_audit_improve.py",
                        "target": result.target,
                        "line": issue.line,
                    })
    unique, seen = [], set()
    for row in rows:
        key = (row["text"], row["label"], row["problem"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def balance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["label"], []).append(row)
    n = max(len(group) for group in grouped.values())
    out: list[dict[str, Any]] = []
    for group in grouped.values():
        out.extend((group * ((n + len(group) - 1) // len(group)))[:n])
    return out


def save_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def train(rows: list[dict[str, Any]]) -> tuple[NaiveBayesTextModel, dict[str, Any]]:
    training_rows = balance(rows)
    model = NaiveBayesTextModel.train(training_rows)
    metrics = evaluate(model, rows)
    metrics.update({
        "teacher_rows": len(rows),
        "balanced_training_rows": len(training_rows),
        "teacher": "self_audit_improve.py",
        "metric_type": "fit_accuracy_on_teacher_rows",
        "note": "Verifies teacher-to-student label transfer; not a real-world generalization benchmark.",
    })
    return model, metrics


def meta(label: str, source: str) -> dict[str, Any]:
    data = LABELS[label]
    return {"label": label, "category": data["category"], "severity": data["severity"], "recommendation": data["recommendation"], "source": source}


def hybrid_predict(model: dict[str, Any], text: str) -> dict[str, Any]:
    try:
        ast.parse(text)
    except SyntaxError:
        return meta("syntax_error", "deterministic_syntax_check") | {"model_fallback_used": False}
    if BARE_EXCEPT_RE.search(text):
        return meta("bare_except", "deterministic_exception_check") | {"model_fallback_used": False}
    if BROAD_EXCEPTION_RE.search(text):
        return meta("broad_exception", "deterministic_exception_check") | {"model_fallback_used": False}
    if any(len(line) > 100 for line in text.splitlines()):
        return meta("long_line", "deterministic_line_length_check") | {"model_fallback_used": False}
    if TODO_RE.search(text):
        return meta("todo_marker", "deterministic_marker_check") | {"model_fallback_used": False}
    if re.search(r"\bprint\s*\(", text):
        return meta("print_usage", "deterministic_print_check") | {"model_fallback_used": False}
    from predict_audit_issue import predict as model_predict
    result = model_predict(model, text)
    result.update({"source": "naive_bayes_student", "model_fallback_used": True})
    return result


def run() -> None:
    rows = generate_rows()
    save_jsonl(rows, ROWS_OUT)
    model, metrics = train(rows)
    MODEL_OUT.write_text(json.dumps(model.to_dict(), indent=2), encoding="utf-8")
    METRICS_OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    smoke = hybrid_predict(model.to_dict(), "try:\n    run()\nexcept:\n    pass")
    assert smoke["label"] == "bare_except", smoke
    labels = sorted({row["label"] for row in rows})
    print(f"teacher_rows={len(rows)}")
    print(f"balanced_training_rows={metrics['balanced_training_rows']}")
    print(f"fit_accuracy={metrics['accuracy']:.3f}")
    print(f"labels={','.join(labels)}")
    print("smoke=passed")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command == "run":
        run()
        return
    if command == "predict":
        path = MODEL_OUT if MODEL_OUT.exists() else HERE / "audit_model.json"
        model = json.loads(path.read_text(encoding="utf-8"))
        text = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else sys.stdin.read()
        print(json.dumps(hybrid_predict(model, text), indent=2))
        return
    raise SystemExit("Usage: teacher_student_bridge.py [run|predict]")


if __name__ == "__main__":
    main()
