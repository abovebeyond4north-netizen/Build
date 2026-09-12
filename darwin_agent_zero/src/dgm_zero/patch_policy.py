from __future__ import annotations

import ast


ABSOLUTE_IMPORTS_BY_PATH: dict[str, frozenset[str]] = {
    "src/dgm_zero/mutation.py": frozenset(
        {"__future__", "ast", "random"}
    ),
    "src/dgm_zero/search_schedule.py": frozenset(
        {
            "__future__",
            "random",
            "collections",
            "collections.abc",
            "typing",
        }
    ),
    "src/dgm_zero/meta_learning.py": frozenset(
        {"__future__", "dataclasses"}
    ),
    "src/dgm_zero/self_instruction.py": frozenset(
        {"__future__", "dataclasses"}
    ),
}

RELATIVE_IMPORTS_BY_PATH: dict[str, frozenset[str]] = {
    "src/dgm_zero/mutation.py": frozenset(),
    "src/dgm_zero/search_schedule.py": frozenset(),
    "src/dgm_zero/meta_learning.py": frozenset({"metacognition"}),
    "src/dgm_zero/self_instruction.py": frozenset({"archive", "memory"}),
}


def patch_import_reasons(relative_path: str, source: str) -> tuple[str, ...]:
    """Reject imports outside the exact dependencies of an editable strategy file."""
    allowed_absolute = ABSOLUTE_IMPORTS_BY_PATH.get(relative_path)
    allowed_relative = RELATIVE_IMPORTS_BY_PATH.get(relative_path)
    if allowed_absolute is None or allowed_relative is None:
        return (f"no import policy exists for editable path: {relative_path}",)

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return (f"syntax error: {exc}",)

    reasons: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_absolute:
                    reasons.append(
                        f"import not allowed for {relative_path}: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(alias.name == "*" for alias in node.names):
                reasons.append(
                    f"star import not allowed for {relative_path}: {module}"
                )
                continue
            if node.level > 0:
                if node.level != 1 or module not in allowed_relative:
                    reasons.append(
                        f"relative import not allowed for {relative_path}: "
                        f"{'.' * node.level}{module}"
                    )
            elif module not in allowed_absolute:
                reasons.append(
                    f"import not allowed for {relative_path}: {module}"
                )
    return tuple(dict.fromkeys(reasons))
