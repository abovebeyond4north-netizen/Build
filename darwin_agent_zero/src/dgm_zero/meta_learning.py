from __future__ import annotations

from dataclasses import dataclass

from .metacognition import CognitiveState


@dataclass(frozen=True)
class MetaLearningPolicy:
    """Run-time knobs that change how evolution learns."""

    novelty_bias: float = 1.0
    simplification_bias: float = 1.0
    exploration_bias: float = 1.0
    curriculum_bias: float = 1.0


class MetaLearner:
    """Adapts learning pressure from the current self-model.

    This does not change model weights. It changes the search policy: what kinds
    of mutations should be sampled more often and whether to prioritize novelty,
    simplification, or curriculum growth.
    """

    def policy_from_state(self, state: CognitiveState) -> MetaLearningPolicy:
        if state.focus == "repair correctness":
            return MetaLearningPolicy(novelty_bias=0.75, simplification_bias=1.30, exploration_bias=0.85, curriculum_bias=0.60)
        if state.focus == "escape stagnation":
            return MetaLearningPolicy(novelty_bias=1.60, simplification_bias=0.85, exploration_bias=1.50, curriculum_bias=0.75)
        if state.focus == "increase diversity":
            return MetaLearningPolicy(novelty_bias=1.80, simplification_bias=0.90, exploration_bias=1.30, curriculum_bias=0.80)
        if state.focus == "mine failures":
            return MetaLearningPolicy(novelty_bias=1.20, simplification_bias=1.00, exploration_bias=1.10, curriculum_bias=0.90)
        if state.focus == "raise curriculum":
            return MetaLearningPolicy(novelty_bias=1.00, simplification_bias=1.10, exploration_bias=0.95, curriculum_bias=1.40)
        return MetaLearningPolicy()

    def weighted_modes(self, policy: MetaLearningPolicy) -> list[str]:
        modes: list[str] = []
        modes += ["wrap"] * max(1, int(3 * policy.exploration_bias))
        modes += ["append"] * max(1, int(3 * policy.exploration_bias))
        modes += ["replace"] * max(1, int(3 * policy.novelty_bias))
        modes += ["simplify"] * max(1, int(3 * policy.simplification_bias))
        return modes
