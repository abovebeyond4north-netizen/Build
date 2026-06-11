from __future__ import annotations

import ast
from dataclasses import dataclass


FORBIDDEN_IMPORTS = {
    "os",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "paramiko",
    "ctypes",
    "multiprocessing",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "__import__",
    "globals",
    "locals",
    "vars",
}


@dataclass(frozen=True)
class SafetyReport:
    passed: bool
    reasons: list[str]
    score: float


class SafetyScanner(ast.NodeVisitor):
    """Small static safety scanner for evolved candidate tools."""

    def __init__(self) -> None:
        self.reasons: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in FORBIDDEN_IMPORTS:
                self.reasons.append(f"forbidden import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        root = (node.module or "").split(".")[0]
        if root in FORBIDDEN_IMPORTS:
            self.reasons.append(f"forbidden import: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name in FORBIDDEN_CALLS:
            self.reasons.append(f"forbidden call: {name}")
        self.generic_visit(node)


def scan_source(source: str) -> SafetyReport:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return SafetyReport(False, [f"syntax error: {exc}"], 0.0)

    scanner = SafetyScanner()
    scanner.visit(tree)
    if scanner.reasons:
        score = max(0.0, 1.0 - 0.25 * len(scanner.reasons))
        return SafetyReport(False, scanner.reasons, score)
    return SafetyReport(True, [], 1.0)
