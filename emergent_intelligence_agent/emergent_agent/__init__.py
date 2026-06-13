"""Safe emergent agent framework prototype."""

from .core import EmergentAgent, AgentConfig, AgentResponse
from .evolution import EvolutionConfig, EvolutionaryOptimizer
from .data_skills import KnowledgeBase
from .safety import SafetyGate

__all__ = [
    "EmergentAgent",
    "AgentConfig",
    "AgentResponse",
    "EvolutionConfig",
    "EvolutionaryOptimizer",
    "KnowledgeBase",
    "SafetyGate",
]
