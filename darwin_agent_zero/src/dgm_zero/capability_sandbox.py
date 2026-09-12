from __future__ import annotations

import ast
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from .capability_model import CapabilityCase, SuiteScore
from .safety import scan_source


SAFE_CALL_NAMES = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
}
BLOCKED_NAMES = {
    "__builtins__",
    "breakpoint",
    "classmethod",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "object",
    "open",
    "property",
    "setattr",
    "staticmethod",
    "super",
    "type",
    "vars",
}
MAX_SOURCE_BYTES = 16_384
MAX_AST_NODES = 512


class SkillSandbox:
    """Execute pure candidate functions in an isolated Python subprocess.

    Static checks forbid imports, reflective builtins, private/dunder attribute
    traversal, extra top-level execution, and non-allowlisted direct calls.
    Runtime execution uses isolated/no-site Python, a wall-clock timeout, and
    resource bounds where the host supports them.
    """

    def __init__(self, timeout_seconds: float = 2.0) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.timeout_seconds = timeout_seconds

    def validate_source(
        self,
        source: str,
        entrypoint: str,
    ) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if not isinstance(source, str):
            return False, ("candidate source must be text",)
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
            reasons.append(f"candidate source exceeds {MAX_SOURCE_BYTES} bytes")

        safety = scan_source(source)
        reasons.extend(safety.reasons)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return False, tuple(
                dict.fromkeys([*reasons, f"syntax error: {exc}"])
            )

        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            reasons.append(f"candidate AST exceeds {MAX_AST_NODES} nodes")

        functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                continue
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            reasons.append(
                "candidate module may contain only a module docstring "
                "and function definition"
            )
            break

        if len(functions) != 1 or functions[0].name != entrypoint:
            reasons.append(
                f"candidate must define exactly one function named {entrypoint}"
            )
        elif isinstance(functions[0], ast.AsyncFunctionDef):
            reasons.append("async candidate functions are not supported")
        else:
            function = functions[0]
            if function.decorator_list:
                reasons.append("candidate decorators are not supported")
            if (
                function.args.vararg
                or function.args.kwarg
                or function.args.kwonlyargs
            ):
                reasons.append(
                    "candidate functions must use fixed positional arguments"
                )
            if function.args.defaults:
                reasons.append(
                    "candidate functions may not define default arguments"
                )

        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ClassDef,
                    ast.Lambda,
                    ast.Global,
                    ast.Nonlocal,
                ),
            ):
                reasons.append(
                    f"unsupported candidate syntax: {type(node).__name__}"
                )
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                reasons.append(
                    f"private/dunder attribute access is forbidden: {node.attr}"
                )
            if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
                reasons.append(f"forbidden name: {node.id}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id not in SAFE_CALL_NAMES:
                    reasons.append(
                        "call is not in the pure builtin allowlist: "
                        f"{node.func.id}"
                    )

        unique_reasons = tuple(dict.fromkeys(reasons))
        return not unique_reasons, unique_reasons

    def evaluate(
        self,
        source: str,
        entrypoint: str,
        cases: Iterable[CapabilityCase],
    ) -> SuiteScore:
        case_list = list(cases)
        passed_source, reasons = self.validate_source(source, entrypoint)
        if not passed_source:
            return SuiteScore(0, len(case_list), 0.0, reasons)
        if not case_list:
            return SuiteScore(0, 0, 0.0, ())

        with tempfile.TemporaryDirectory(prefix="dgm-capability-") as tmp:
            tmp_path = Path(tmp)
            candidate_path = tmp_path / "candidate.py"
            cases_path = tmp_path / "cases.json"
            result_path = tmp_path / "result.json"
            runner_path = tmp_path / "runner.py"
            candidate_path.write_text(source, encoding="utf-8")
            cases_path.write_text(
                json.dumps(
                    [
                        {"name": case.name, "args": list(case.args)}
                        for case in case_list
                    ],
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            runner_path.write_text(_RUNNER_SOURCE, encoding="utf-8")

            start = time.perf_counter()
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-S",
                        str(runner_path),
                        str(candidate_path),
                        entrypoint,
                        str(cases_path),
                        str(result_path),
                    ],
                    cwd=tmp,
                    env={
                        "PYTHONHASHSEED": "0",
                        "PATH": os.environ.get("PATH", ""),
                    },
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return SuiteScore(
                    0,
                    len(case_list),
                    time.perf_counter() - start,
                    ("candidate execution timed out",),
                )
            elapsed = time.perf_counter() - start

            if not result_path.exists():
                detail = (
                    completed.stderr
                    or completed.stdout
                    or f"runner exited with code {completed.returncode}"
                ).strip()[:500]
                return SuiteScore(
                    0,
                    len(case_list),
                    elapsed,
                    (f"runner failure: {detail}",),
                )
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return SuiteScore(
                    0,
                    len(case_list),
                    elapsed,
                    (f"invalid runner result: {exc}",),
                )

        outputs = payload.get("outputs")
        if not isinstance(outputs, list) or len(outputs) != len(case_list):
            return SuiteScore(
                0,
                len(case_list),
                elapsed,
                ("runner returned an invalid output vector",),
            )

        passed = 0
        errors: list[str] = []
        for case, output in zip(case_list, outputs):
            if not isinstance(output, dict) or not output.get("ok"):
                error = (
                    output.get("error", "unknown error")
                    if isinstance(output, dict)
                    else "invalid output"
                )
                errors.append(f"{case.name}: {error}")
                continue
            actual = output.get("value")
            if json_equal(actual, case.expected):
                passed += 1
            else:
                errors.append(
                    f"{case.name}: expected {case.expected!r}, got {actual!r}"
                )
        return SuiteScore(
            passed,
            len(case_list),
            elapsed,
            tuple(errors[:10]),
        )


def json_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(
            float(actual),
            float(expected),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            json_equal(a, b) for a, b in zip(actual, expected)
        )
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            json_equal(actual[key], expected[key]) for key in actual
        )
    return actual == expected


_RUNNER_SOURCE = r"""
import importlib.util
import json
import sys
import time

try:
    import resource
except ImportError:
    resource = None

if resource is not None:
    try:
        memory = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (1024 * 1024, 1024 * 1024),
        )
    except (ValueError, OSError):
        pass

candidate_path, entrypoint, cases_path, result_path = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("candidate", candidate_path)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load candidate")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fn = getattr(module, entrypoint)
with open(cases_path, "r", encoding="utf-8") as handle:
    cases = json.load(handle)

outputs = []
started = time.perf_counter()
for case in cases:
    try:
        value = fn(*case["args"])
        json.dumps(value, allow_nan=False)
        outputs.append({"ok": True, "value": value})
    except BaseException as exc:
        outputs.append({"ok": False, "error": type(exc).__name__})

payload = {
    "outputs": outputs,
    "elapsed_seconds": time.perf_counter() - started,
}
with open(result_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, allow_nan=False)
"""
