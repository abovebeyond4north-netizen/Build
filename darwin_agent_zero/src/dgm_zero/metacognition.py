from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .archive import ArchiveRecord


@dataclass(frozen=True)
class CognitiveState:
    """A compact self-model of the current evolution run.

    This is metacognition, not consciousness: the system estimates what it knows,
    what it is weak at, and where it should focus next.
    """

    confidence: float
    uncertainty: float
    stagnation: float
    diversity: float
    safety_pressure: float
    focus: str
    critique: str


class MetacognitiveMonitor:
    """Builds a self-critique from archive dynamics."""

    def assess(self, records: list[ArchiveRecord], elite_cell_count: int = 0, mined_case_count: int = 0) -> CognitiveState:
        if not records:
            return CognitiveState(
                confidence=0.0,
                uncertainty=1.0,
                stagnation=0.0,
                diversity=0.0,
                safety_pressure=0.0,
                focus="bootstrap",
                critique="No archive exists yet. Establish a baseline before judging progress.",
            )

        accepted = [record for record in records if record.accepted]
        recent = records[-20:]
        best = max((record.score.get("weighted_total", 0.0) for record in accepted), default=0.0)
        recent_best = max((record.score.get("weighted_total", 0.0) for record in recent), default=0.0)
        accepted_rate = len(accepted) / len(records)
        diversity = min(1.0, elite_cell_count / 12.0)
        uncertainty = max(0.0, 1.0 - best)
        stagnation = 1.0 if accepted and recent_best < best else max(0.0, 1.0 - accepted_rate * 4.0)
        safety_pressure = min(1.0, sum(1 for record in recent if "forbidden" in record.reason.lower()) / max(1, len(recent)))

        if best < 0.50:
            focus = "repair correctness"
            critique = "The system has not found a strong candidate. Favor simpler mutations and clearer benchmark feedback."
        elif stagnation > 0.70:
            focus = "escape stagnation"
            critique = "Recent candidates are not improving. Increase novelty pressure and sample from MAP-Elites side paths."
        elif diversity < 0.35:
            focus = "increase diversity"
            critique = "The archive is too narrow. Preserve more behavioral niches before pushing difficulty higher."
        elif mined_case_count == 0:
            focus = "mine failures"
            critique = "The system lacks self-generated pressure. Mine disagreement cases from the archive."
        else:
            focus = "raise curriculum"
            critique = "The system has stable performance and some diversity. Increase benchmark pressure carefully."

        return CognitiveState(
            confidence=max(0.0, min(1.0, best)),
            uncertainty=uncertainty,
            stagnation=max(0.0, min(1.0, stagnation)),
            diversity=diversity,
            safety_pressure=safety_pressure,
            focus=focus,
            critique=critique,
        )

    def write(self, path: Path, state: CognitiveState) -> None:
        path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")
