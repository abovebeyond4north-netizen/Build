"""Core emergent agent composition."""

from __future__ import annotations

from dataclasses import dataclass, field

from .data_skills import KnowledgeBase
from .language import LanguageProcessor
from .reasoning import Reasoner, ReasoningTrace
from .safety import SafetyDecision, SafetyGate


@dataclass
class AgentConfig:
    name: str = "EmergentAgent"
    style: str = "structured"
    max_retrievals: int = 3
    principles: tuple[str, ...] = (
        "Be useful and grounded.",
        "Break complex work into steps.",
        "Prefer safe, lawful, constructive outputs.",
        "Use retrieved data when available.",
    )

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.style, str) or not self.style.strip():
            raise ValueError("style must be a non-empty string")
        if (
            isinstance(self.max_retrievals, bool)
            or not isinstance(self.max_retrievals, int)
            or self.max_retrievals < 0
        ):
            raise ValueError("max_retrievals must be a non-negative integer")
        if not isinstance(self.principles, tuple):
            raise ValueError("principles must be a tuple of strings")
        normalized: list[str] = []
        for principle in self.principles:
            if not isinstance(principle, str) or not principle.strip():
                raise ValueError("principles must contain non-empty strings")
            normalized.append(principle.strip())
        self.name = self.name.strip()
        self.style = self.style.strip()
        self.principles = tuple(normalized)


@dataclass
class AgentResponse:
    answer: str
    intent: str
    safety: SafetyDecision
    trace: ReasoningTrace
    retrieved_context: str = ""


@dataclass
class EmergentAgent:
    config: AgentConfig = field(default_factory=AgentConfig)
    knowledge: KnowledgeBase = field(default_factory=KnowledgeBase)
    safety_gate: SafetyGate = field(default_factory=SafetyGate)
    language: LanguageProcessor = field(default_factory=LanguageProcessor)
    reasoner: Reasoner = field(default_factory=Reasoner)

    def answer(self, user_input: str) -> AgentResponse:
        if not isinstance(user_input, str):
            raise TypeError("user_input must be a string")
        safety = self.safety_gate.classify(user_input)
        intent = self.language.classify_intent(user_input)

        if not safety.allowed:
            answer = safety.safe_alternative or "I can help with a safe alternative."
            trace = self.reasoner.build_trace(user_input, answer)
            return AgentResponse(answer, intent.label, safety, trace)

        hits = self.knowledge.search(
            user_input,
            top_k=self.config.max_retrievals,
        )
        context = self.knowledge.summarize_hits(hits)
        raw_answer = self._compose_answer(
            user_input,
            intent.label,
            context,
            safety.reason,
        )
        shaped = self.language.shape_answer(
            raw_answer,
            style=self.config.style,
        )
        trace = self.reasoner.build_trace(user_input, shaped)
        return AgentResponse(shaped, intent.label, safety, trace, context)

    def _compose_answer(
        self,
        user_input: str,
        intent: str,
        context: str,
        safety_note: str,
    ) -> str:
        principles = " ".join(self.config.principles)
        parts = [
            f"Agent: {self.config.name}",
            f"Intent: {intent}",
            f"Safety: {safety_note}",
            f"Principles: {principles}",
        ]
        if context:
            parts.append("Relevant local context:\n" + context)
        parts.append(
            "Plan:\n- Clarify the target outcome.\n"
            "- Use local evidence when available.\n"
            "- Produce a grounded next action."
        )
        parts.append(
            "Answer:\n" + self._intent_answer(user_input, intent, bool(context))
        )
        return "\n\n".join(parts)

    @staticmethod
    def _intent_answer(user_input: str, intent: str, has_context: bool) -> str:
        if intent == "build":
            return (
                "Build it as small modules first: safety gate, language processor, "
                "knowledge base, reasoner, evaluator, and evolutionary optimizer. "
                "Then run tests and improve only when metrics prove the change helps."
            )
        if intent == "retrieve":
            return (
                "I searched the local knowledge base and used the most relevant matches."
                if has_context
                else "No local match was found yet; add documents to the knowledge base first."
            )
        if intent == "analyze":
            return (
                "Use a rubric with accuracy, grounding, usefulness, safety, latency, "
                "and cost. Compare scores before accepting a change."
            )
        if intent == "explain":
            return (
                "Emergent intelligence is best modeled as useful behavior arising "
                "from interacting modules, feedback, memory, and evaluation pressure."
            )
        return (
            "I can help turn the request into a safe plan, implementation, "
            "or evaluation loop."
        )
