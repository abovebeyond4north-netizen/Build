from __future__ import annotations

import ast
import random
from dataclasses import dataclass


CONSTANT_POOL = (-3, -2, -1, 0, 1, 2, 3, 4, 5, 7)
BINOP_TYPES = (ast.Add, ast.Sub, ast.Mult)


@dataclass(frozen=True)
class MutationTarget:
    kind: str
    node: ast.AST


def structural_replace(expression: str, rng: random.Random) -> str:
    """Create a bounded structural variant of the arithmetic expression.

    Only variable identities, small integer constants, and the existing arithmetic
    operator nodes are changed. The normal oracle/safety evaluator remains the
    authority on whether the resulting expression is useful or acceptable.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression must be a non-empty string")
    if not isinstance(rng, random.Random):
        raise TypeError("rng must be random.Random")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("expression must be valid Python syntax") from exc

    targets: list[MutationTarget] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in {"a", "b"}:
            targets.append(MutationTarget("name", node))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            targets.append(MutationTarget("constant", node))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, BINOP_TYPES):
            targets.append(MutationTarget("binop", node))

    if not targets:
        return f"({expression}) + 1"

    target = rng.choice(targets)
    if target.kind == "name":
        node = target.node
        assert isinstance(node, ast.Name)
        node.id = "b" if node.id == "a" else "a"
    elif target.kind == "constant":
        node = target.node
        assert isinstance(node, ast.Constant)
        choices = [value for value in CONSTANT_POOL if value != node.value]
        node.value = rng.choice(choices)
    else:
        node = target.node
        assert isinstance(node, ast.BinOp)
        current = type(node.op)
        choices = [operator_type for operator_type in BINOP_TYPES if operator_type is not current]
        node.op = rng.choice(choices)()

    ast.fix_missing_locations(tree)
    mutated = ast.unparse(tree)
    if mutated == expression:
        return f"({expression}) + 1"
    return mutated
