from __future__ import annotations

import ast
import math
import random
import time
from dataclasses import dataclass


ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.FloorDiv: lambda a, b: a // b if b else 0,
    ast.Mod: lambda a, b: a % b if b else 0,
}

ALLOWED_UNARY = {ast.USub: lambda a: -a, ast.UAdd: lambda a: a}
ALLOWED_FUNCS = {"abs": abs, "gcd": math.gcd, "max": max, "min": min}


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    a: int
    b: int
    expected: int


@dataclass(frozen=True)
class BenchmarkResult:
    passed: int
    total: int
    elapsed_seconds: float
    errors: list[str]

    @property
    def correctness(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def efficiency(self) -> float:
        return max(0.0, min(1.0, 1.0 / (1.0 + self.elapsed_seconds)))


def canonical_cases(seed: int = 7, count: int = 64) -> list[BenchmarkCase]:
    rng = random.Random(seed)
    cases: list[BenchmarkCase] = []
    for index in range(count):
        a = rng.randint(-30, 30)
        b = rng.randint(-30, 30)
        expected = a * a + 3 * b - math.gcd(a, b)
        cases.append(BenchmarkCase(f"case_{index}", a, b, expected))
    return cases


def eval_expr(expr: str, a: int, b: int) -> int:
    tree = ast.parse(expr, mode="eval")

    def walk(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)
        if isinstance(node, ast.Name) and node.id in {"a", "b"}:
            return a if node.id == "a" else b
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY:
            return ALLOWED_UNARY[type(node.op)](walk(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINOPS:
            return ALLOWED_BINOPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ALLOWED_FUNCS:
            return int(ALLOWED_FUNCS[node.func.id](*[walk(arg) for arg in node.args]))
        raise ValueError(f"unsupported expression node: {type(node).__name__}")

    return walk(tree)


def evaluate_expression(expr: str, cases: list[BenchmarkCase] | None = None) -> BenchmarkResult:
    cases = cases or canonical_cases()
    passed = 0
    errors: list[str] = []
    start = time.perf_counter()
    for case in cases:
        try:
            actual = eval_expr(expr, case.a, case.b)
            if actual == case.expected:
                passed += 1
            else:
                errors.append(f"{case.name}: expected {case.expected}, got {actual}")
        except Exception as exc:
            errors.append(f"{case.name}: {exc}")
    return BenchmarkResult(passed, len(cases), time.perf_counter() - start, errors[:10])
