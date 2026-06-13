"""Safety gates for local agent actions.

The framework is designed for constructive reasoning, language, and data tasks.
It does not execute shell commands, browse private systems, or perform actions
that affect external services. The gate below classifies requests and returns a
safe redirect when a request appears harmful or outside scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable


class RiskLevel(str, Enum):
    BENIGN = "benign"
    AMBIGUOUS = "ambiguous"
    RISKY = "risky"
    DISALLOWED = "disallowed"


@dataclass(frozen=True)
class SafetyDecision:
    level: RiskLevel
    allowed: bool
    reason: str
    safe_alternative: str | None = None


class SafetyGate:
    """Small keyword/rule-based gate for prototype safety.

    This is intentionally conservative and transparent. Production systems should
    combine policy-specific classifiers, expert review, logging, and human
    approval for sensitive domains.
    """

    disallowed_patterns: tuple[re.Pattern[str], ...] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in [
            r"\bmalware\b|\bkeylogger\b|\bransomware\b",
            r"\bphishing\b.*\b(email|template|convincing|credential)",
            r"\bexploit\b.*\b(real|target|server|account|website)",
            r"\bbypass\b.*\b(security|login|password|2fa|safeguard)",
            r"\bweapon\b.*\b(make|build|construct|instructions)",
            r"\bpoison\b.*\b(make|dose|instructions)",
            r"\bhide\b.*\b(income|money|crime|evidence)",
        ]
    )

    risky_patterns: tuple[re.Pattern[str], ...] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in [
            r"\bhack\b|\bcrack\b|\bcredential\b",
            r"\blockpick\b|\bbypass\b",
            r"\bdelete all\b|\bwipe\b",
            r"\bdosage\b|\bprescription\b",
        ]
    )

    def classify(self, text: str) -> SafetyDecision:
        normalized = " ".join(text.strip().split())
        if not normalized:
            return SafetyDecision(RiskLevel.AMBIGUOUS, False, "Empty request.", "Ask a clear question or provide a task.")

        for pattern in self.disallowed_patterns:
            if pattern.search(normalized):
                return SafetyDecision(
                    RiskLevel.DISALLOWED,
                    False,
                    "The request appears to ask for operational help that could enable harm or unauthorized activity.",
                    "I can help with defensive education, safe simulations, prevention checklists, or lawful alternatives.",
                )

        for pattern in self.risky_patterns:
            if pattern.search(normalized):
                return SafetyDecision(
                    RiskLevel.RISKY,
                    True,
                    "The topic is dual-use or sensitive, so the answer should stay defensive, high-level, or safety-focused.",
                    "Keep the response framed around safety, consent, legality, and non-operational guidance.",
                )

        return SafetyDecision(RiskLevel.BENIGN, True, "No obvious safety concern detected.")

    def batch_classify(self, items: Iterable[str]) -> list[SafetyDecision]:
        return [self.classify(item) for item in items]
