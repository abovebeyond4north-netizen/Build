from __future__ import annotations

import json
import math
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
    """Build a self-critique from context-aware archive dynamics."""

    def assess(
        self,
        records: list[ArchiveRecord],
        elite_cell_count: int = 0,
        mined_case_count: int = 0,
    ) -> CognitiveState:
        if not records:
            return CognitiveState(
                confidence=0.0,
                uncertainty=1.0,
                stagnation=0.0,
                diversity=0.0,
                safety_pressure=0.0,
                focus="bootstrap",
                critique=(
                    "No archive exists yet. Establish a baseline before judging "
                    "progress."
                ),
            )

        recent = records[-20:]
        latest_context = next(
            (
                record.evaluation_context
                for record in reversed(records)
                if record.evaluation_context is not None
            ),
            None,
        )
        evidence_records = (
            [
                record
                for record in records
                if record.evaluation_context == latest_context
            ]
            if latest_context is not None
            else recent
        )
        evidence_accepted = [record for record in evidence_records if record.accepted]
        recent_accepted = [record for record in recent if record.accepted]
        best = max(
            (
                record.score.get("weighted_total", 0.0)
                for record in evidence_accepted
            ),
            default=0.0,
        )
        recent_best = max(
            (
                record.score.get("weighted_total", 0.0)
                for record in recent_accepted
            ),
            default=0.0,
        )
        accepted_rate = len(evidence_accepted) / max(1, len(evidence_records))
        verified_deltas = [
            float(record.verified_delta)
            for record in evidence_records[-20:]
            if record.verified_delta is not None
        ]
        diversity = min(1.0, elite_cell_count / 12.0)
        uncertainty = max(0.0, 1.0 - best)
        stagnation = stagnation_score(
            records,
            recent_best=recent_best,
            accepted_rate=accepted_rate,
            verified_deltas=verified_deltas,
        )
        safety_pressure = min(
            1.0,
            sum(
                1
                for record in recent
                if "forbidden" in record.reason.lower()
            )
            / max(1, len(recent)),
        )

        if best < 0.50:
            focus = "repair correctness"
            critique = (
                "The latest evaluation context has not produced a strong "
                "candidate. Favor simpler mutations and clearer benchmark feedback."
            )
        elif stagnation > 0.70:
            focus = "escape stagnation"
            critique = (
                "Recent same-context parent-to-child evidence shows little verified "
                "gain. Increase novelty pressure and sample MAP-Elites side paths."
            )
        elif diversity < 0.35:
            focus = "increase diversity"
            critique = (
                "The archive is too narrow. Preserve more behavioral niches "
                "before pushing difficulty higher."
            )
        elif mined_case_count == 0:
            focus = "mine failures"
            critique = (
                "The system lacks self-generated pressure. Mine failure and "
                "disagreement cases from the archive."
            )
        else:
            focus = "raise curriculum"
            critique = (
                "The system has measurable verified progress and some diversity. "
                "Increase benchmark pressure carefully."
            )

        return CognitiveState(
            confidence=max(0.0, min(1.0, best)),
            uncertainty=max(0.0, min(1.0, uncertainty)),
            stagnation=max(0.0, min(1.0, stagnation)),
            diversity=diversity,
            safety_pressure=safety_pressure,
            focus=focus,
            critique=critique,
        )

    def write(self, path: Path, state: CognitiveState) -> None:
        path.write_text(
            json.dumps(asdict(state), indent=2, sort_keys=True),
            encoding="utf-8",
        )


def stagnation_score(
    records: list[ArchiveRecord],
    *,
    recent_best: float,
    accepted_rate: float,
    recent_window: int = 20,
    meaningful_gain: float = 0.05,
    verified_deltas: list[float] | None = None,
) -> float:
    """Estimate whether recent search is still producing verified improvement.

    New records carry parent-to-child deltas measured within one frozen evaluation
    context. When present, these are the preferred progress signal and avoid
    comparing raw scores produced by different curricula/evaluator contexts.
    Legacy archives fall back to the historical-frontier heuristic.
    """

    if (
        isinstance(recent_window, bool)
        or not isinstance(recent_window, int)
        or recent_window <= 0
    ):
        raise ValueError("recent_window must be a positive integer")
    if (
        isinstance(meaningful_gain, bool)
        or not isinstance(meaningful_gain, (int, float))
        or not math.isfinite(float(meaningful_gain))
        or float(meaningful_gain) <= 0.0
    ):
        raise ValueError("meaningful_gain must be finite and positive")
    if not math.isfinite(float(accepted_rate)):
        raise ValueError("accepted_rate must be finite")

    deltas = verified_deltas or []
    if deltas:
        for delta in deltas:
            if not math.isfinite(float(delta)) or not -1.0 <= float(delta) <= 1.0:
                raise ValueError(
                    "verified deltas must be finite and between -1 and 1"
                )
        best_gain = max(0.0, max(float(delta) for delta in deltas))
        progress = min(1.0, best_gain / float(meaningful_gain))
        return 1.0 - progress

    if len(records) > recent_window:
        historical = [
            record
            for record in records[:-recent_window]
            if record.accepted
        ]
        if historical:
            historical_best = max(
                record.score.get("weighted_total", 0.0)
                for record in historical
            )
            gain = max(0.0, recent_best - historical_best)
            progress = min(1.0, gain / float(meaningful_gain))
            return 1.0 - progress

    bounded_rate = max(0.0, min(1.0, float(accepted_rate)))
    return max(0.0, 1.0 - bounded_rate * 4.0)
