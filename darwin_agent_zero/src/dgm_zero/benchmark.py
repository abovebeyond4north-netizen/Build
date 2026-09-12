from __future__ import annotations

import ast
import math
import operator
import random
import time
from dataclasses import dataclass


MAX_AST_NODES = 256
EFFICIENCY_COST_SCALE = 64.0
ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
ALLOWED_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
ALLOWED_FUNCS = {"abs": abs, "gcd": math.gcd, "max": max, "min": min}
BINOP_COST = {
    ast.Add: 1,
    ast.Sub: 1,
    ast.Mult: 2,
    ast.FloorDiv: 3,
    ast.Mod: 3,
}


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    a: int
    b: int
    expected: int


@dataclass(frozen=True)
class BenchmarkConfig:
    value_min: int = -30
    value_max: int = 30
    train_count: int = 64
    validation_count: int = 64
    adversarial_scale: int = 1


@dataclass(frozen=True)
class BenchmarkResult:
    passed: int
    total: int
    elapsed_seconds: float
    errors: list[str]
    structural_cost: int | None = None

    @property
    def correctness(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def efficiency(self) -> float:
        """Deterministic efficiency when structural cost evidence is available.

        ``elapsed_seconds`` remains useful operational telemetry, but using raw wall
        time in evolutionary fitness makes identical candidates score differently
        under varying host load. New benchmark evaluations therefore use a bounded
        AST operation-cost surrogate. Legacy manually constructed results that do
        not carry structural cost retain the historical timing interpretation.
        """
        if self.structural_cost is not None:
            cost = max(0, int(self.structural_cost))
            return max(
                0.0,
                min(1.0, 1.0 / (1.0 + cost / EFFICIENCY_COST_SCALE)),
            )
        return max(
            0.0,
            min(1.0, 1.0 / (1.0 + self.elapsed_seconds)),
        )


@dataclass(frozen=True)
class SplitBenchmarkResult:
    train: BenchmarkResult
    validation: BenchmarkResult
    adversarial: BenchmarkResult

    @property
    def correctness(self) -> float:
        """Conservative score: candidate must work across all benchmark pressure."""
        return min(
            self.train.correctness,
            self.validation.correctness,
            self.adversarial.correctness,
        )

    @property
    def efficiency(self) -> float:
        return (
            self.train.efficiency
            + self.validation.efficiency
            + self.adversarial.efficiency
        ) / 3.0

    @property
    def errors(self) -> list[str]:
        return [
            *self.train.errors[:3],
            *self.validation.errors[:3],
            *self.adversarial.errors[:4],
        ]


def target_function(a: int, b: int) -> int:
    """Hidden objective for the seed benchmark family."""
    return a * a + 3 * b - math.gcd(a, b)


def canonical_cases(
    seed: int = 7,
    count: int = 64,
    label: str = "case",
    value_min: int = -30,
    value_max: int = 30,
) -> list[BenchmarkCase]:
    if count < 0:
        raise ValueError("count must be non-negative")
    if value_min > value_max:
        raise ValueError("value_min must not exceed value_max")

    rng = random.Random(seed)
    cases: list[BenchmarkCase] = []
    for index in range(count):
        a = rng.randint(value_min, value_max)
        b = rng.randint(value_min, value_max)
        expected = target_function(a, b)
        cases.append(BenchmarkCase(f"{label}_{index}", a, b, expected))
    return cases


def adversarial_cases(scale: int = 1) -> list[BenchmarkCase]:
    """Edge cases that catch overfitting and arithmetic shortcuts."""
    scale = max(1, scale)
    base_pairs = [
        (0, 0),
        (0, 31),
        (0, -31),
        (1, 0),
        (-1, 0),
        (2, 2),
        (-2, -2),
        (30, -30),
        (-30, 30),
        (31, 31),
        (-31, -31),
        (97, 13),
        (-97, 13),
        (97, -13),
        (144, 89),
        (-144, -89),
    ]
    pairs = [(a * scale, b * scale) for a, b in base_pairs]
    return [
        BenchmarkCase(f"adversarial_{idx}", a, b, target_function(a, b))
        for idx, (a, b) in enumerate(pairs)
    ]


def split_cases(
    train_seed: int = 7,
    validation_seed: int = 404,
    config: BenchmarkConfig | None = None,
) -> tuple[list[BenchmarkCase], list[BenchmarkCase], list[BenchmarkCase]]:
    cfg = config or BenchmarkConfig()
    return (
        canonical_cases(
            train_seed,
            cfg.train_count,
            "train",
            cfg.value_min,
            cfg.value_max,
        ),
        canonical_cases(
            validation_seed,
            cfg.validation_count,
            "validation",
            cfg.value_min,
            cfg.value_max,
        ),
        adversarial_cases(cfg.adversarial_scale),
    )


def _validate_tree(tree: ast.AST) -> None:
    """Reject expressions large enough to make verification disproportionately costly."""
    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > MAX_AST_NODES:
        raise ValueError(
            f"expression is too complex: {node_count} AST nodes exceeds {MAX_AST_NODES}"
        )


def expression_structural_cost(expr: str) -> int:
    """Return a deterministic operation-cost surrogate for the tiny DSL."""
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("expression must be a non-empty string")
    tree = ast.parse(expr, mode="eval")
    _validate_tree(tree)
    cost = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            cost += BINOP_COST.get(type(node.op), 4)
        elif isinstance(node, ast.UnaryOp):
            cost += 1
        elif isinstance(node, ast.Call):
            cost += 4
        elif isinstance(node, ast.Name):
            cost += 1
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            cost += 1
    return max(1, cost)


def eval_expr(expr: str, a: int, b: int) -> int:
    """Evaluate a deliberately tiny arithmetic expression language.

    Every syntactic component must be explicitly supported. Unsupported keywords,
    names, calls, or operators fail closed rather than being ignored. Native Python
    arithmetic semantics are retained, including division/modulo by zero errors.
    """
    tree = ast.parse(expr, mode="eval")
    _validate_tree(tree)

    def walk(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            return int(node.value)
        if isinstance(node, ast.Name) and node.id in {"a", "b"}:
            return a if node.id == "a" else b
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_UNARY:
            return int(ALLOWED_UNARY[type(node.op)](walk(node.operand)))
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINOPS:
            return int(ALLOWED_BINOPS[type(node.op)](walk(node.left), walk(node.right)))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ALLOWED_FUNCS
        ):
            if node.keywords:
                raise ValueError("keyword arguments are not supported")
            args = [walk(arg) for arg in node.args]
            return int(ALLOWED_FUNCS[node.func.id](*args))
        raise ValueError(f"unsupported expression node: {type(node).__name__}")

    return walk(tree)


def evaluate_expression(
    expr: str,
    cases: list[BenchmarkCase] | None = None,
) -> BenchmarkResult:
    """Evaluate an expression against exactly the supplied cases.

    ``None`` selects the canonical suite. An explicitly empty list remains empty,
    which keeps callers in control of benchmark composition. Wall time is retained
    as telemetry; structural cost is the deterministic efficiency evidence.
    """
    evaluation_cases = canonical_cases() if cases is None else cases
    try:
        structural_cost = expression_structural_cost(expr)
    except (SyntaxError, TypeError, ValueError):
        structural_cost = MAX_AST_NODES

    passed = 0
    errors: list[str] = []
    start = time.perf_counter()
    for case in evaluation_cases:
        try:
            actual = eval_expr(expr, case.a, case.b)
            if actual == case.expected:
                passed += 1
            else:
                errors.append(
                    f"{case.name}: expected {case.expected}, got {actual}"
                )
        except Exception as exc:
            errors.append(f"{case.name}: {exc}")
    return BenchmarkResult(
        passed=passed,
        total=len(evaluation_cases),
        elapsed_seconds=time.perf_counter() - start,
        errors=errors[:10],
        structural_cost=structural_cost,
    )


def evaluate_expression_split(
    expr: str,
    config: BenchmarkConfig | None = None,
) -> SplitBenchmarkResult:
    train, validation, adversarial = split_cases(config=config)
    return SplitBenchmarkResult(
        evaluate_expression(expr, train),
        evaluate_expression(expr, validation),
        evaluate_expression(expr, adversarial),
    )
