from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


ToolFn = Callable[..., object]


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: ToolFn
    risk: str = "low"
    tags: set[str] = field(default_factory=set)


class ToolRegistry:
    """Agent Zero style tool layer.

    Tools are explicit, named, documented, and callable only through the registry.
    This prevents accidental hidden capabilities and keeps future self-coded tools
    auditable.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        if spec.risk not in {"low", "medium", "high"}:
            raise ValueError("risk must be low, medium, or high")
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> list[dict[str, object]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "risk": spec.risk,
                "tags": sorted(spec.tags),
            }
            for spec in self._tools.values()
        ]

    def call(self, name: str, *args: object, **kwargs: object) -> object:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        spec = self._tools[name]
        if spec.risk != "low":
            raise PermissionError(f"tool requires explicit review: {name}")
        return spec.fn(*args, **kwargs)


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="score_expression",
            description="Score an arithmetic candidate expression through the empirical oracle.",
            fn=lambda oracle, expression: oracle.judge(str(expression)),
            risk="low",
            tags={"evaluation", "oracle"},
        )
    )
    registry.register(
        ToolSpec(
            name="list_tools",
            description="List currently registered safe tools.",
            fn=lambda reg: reg.describe(),
            risk="low",
            tags={"introspection"},
        )
    )
    return registry
