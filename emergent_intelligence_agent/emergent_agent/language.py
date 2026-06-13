"""Language processing layer for intent, style, and response shaping."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Intent:
    label: str
    confidence: float


class LanguageProcessor:
    """Rule-based NLP layer used by the prototype.

    Swap this with a real model-backed classifier when external APIs are enabled.
    """

    patterns = {
        "build": re.compile(r"\b(build|implement|code|create|design)\b", re.I),
        "explain": re.compile(r"\b(explain|teach|what is|why|how does)\b", re.I),
        "analyze": re.compile(r"\b(analyze|evaluate|compare|score|audit)\b", re.I),
        "retrieve": re.compile(r"\b(find|search|retrieve|lookup|data)\b", re.I),
    }

    def classify_intent(self, text: str) -> Intent:
        for label, pattern in self.patterns.items():
            if pattern.search(text):
                return Intent(label, 0.78)
        return Intent("general", 0.55)

    def shape_answer(self, text: str, style: str = "direct") -> str:
        text = text.strip()
        if style == "brief":
            return text.split("\n\n")[0]
        if style == "structured" and not text.startswith("#"):
            return "## Result\n\n" + text
        return text
