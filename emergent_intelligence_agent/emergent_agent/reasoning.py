"""Reasoning helpers for decomposition, critique, and synthesis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReasoningTrace:
    goal: str
    plan: list[str]
    checks: list[str]
    conclusion: str


class Reasoner:
    """Transparent reasoning scaffold.

    This class does not expose hidden chain-of-thought. It creates a concise,
    user-facing reasoning summary: plan, checks, and conclusion.
    """

    def decompose(self, goal: str) -> list[str]:
        goal_lower = goal.lower()
        steps = ["Clarify the goal and constraints"]
        if any(word in goal_lower for word in ["data", "document", "search", "retrieve"]):
            steps.append("Retrieve relevant local knowledge")
        if any(word in goal_lower for word in ["design", "build", "implement", "code"]):
            steps.append("Propose a modular design")
            steps.append("Define interfaces and validation checks")
        if any(word in goal_lower for word in ["reason", "solve", "proof", "logic"]):
            steps.append("Break the problem into smaller reasoning units")
        steps.append("Synthesize a useful answer")
        return steps

    def critique(self, answer: str) -> list[str]:
        checks = []
        if len(answer.strip()) < 40:
            checks.append("Answer may be too short to be useful")
        if "I don't know" in answer or "uncertain" in answer.lower():
            checks.append("Uncertainty is visible")
        if not checks:
            checks.append("Answer is complete enough for the current prototype")
        return checks

    def build_trace(self, goal: str, conclusion: str) -> ReasoningTrace:
        return ReasoningTrace(
            goal=goal,
            plan=self.decompose(goal),
            checks=self.critique(conclusion),
            conclusion=conclusion,
        )
