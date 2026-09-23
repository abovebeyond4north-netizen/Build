from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from p3 import PredicateProgram
from p5 import DECODERS, FeatureCapsule, extract_decoder_values


@dataclass(frozen=True)
class QueryStep:
    query_index: int
    candidates_before: int
    candidates_after: int
    true_predictions: int
    false_predictions: int
    disagreement: int


@dataclass(frozen=True)
class ActiveLearningResult:
    feature: FeatureCapsule
    queries_used: int
    initial_candidates: int
    final_candidates: int
    trace: tuple[QueryStep, ...]


def _prediction(
    *,
    controller: PredicateProgram,
    feature: FeatureCapsule,
    raw: str,
) -> bool | None:
    decoder = next(
        decoder
        for decoder in DECODERS
        if decoder.name == feature.decoder_name
    )
    values = extract_decoder_values(raw, decoder)
    if (
        feature.left_index >= len(values)
        or feature.right_index >= len(values)
    ):
        return None
    return controller.apply(
        values[feature.left_index],
        values[feature.right_index],
    )


def enumerate_candidates(
    *,
    family_id: str,
    raw_observations: tuple[str, ...],
) -> tuple[FeatureCapsule, ...]:
    if not raw_observations:
        raise ValueError("raw observation pool must be non-empty")

    candidates: list[FeatureCapsule] = []
    for decoder in DECODERS:
        widths = {
            len(extract_decoder_values(raw, decoder))
            for raw in raw_observations
        }
        if len(widths) != 1:
            continue
        width = next(iter(widths))
        if width < 2:
            continue
        for left_index in range(width):
            for right_index in range(width):
                if left_index == right_index:
                    continue
                candidates.append(
                    FeatureCapsule(
                        family_id=family_id,
                        decoder_name=decoder.name,
                        left_index=left_index,
                        right_index=right_index,
                        support_digest="active_unlabeled_pool",
                    )
                )
    if not candidates:
        raise ValueError("active learner found no structural hypotheses")
    return tuple(candidates)


class ActiveHypothesisLearner:
    """Choose labels that maximally separate the current structural hypotheses."""

    def fit(
        self,
        *,
        controller: PredicateProgram,
        family_id: str,
        raw_observations: tuple[str, ...],
        query_label: Callable[[int], bool],
        max_queries: int,
    ) -> ActiveLearningResult:
        if max_queries < 1:
            raise ValueError("max_queries must be positive")

        candidates = list(
            enumerate_candidates(
                family_id=family_id,
                raw_observations=raw_observations,
            )
        )
        initial_candidates = len(candidates)
        unqueried = set(range(len(raw_observations)))
        trace: list[QueryStep] = []

        while len(candidates) > 1 and len(trace) < max_queries:
            best: tuple[int, int, int, int] | None = None
            for index in sorted(unqueried):
                predictions = [
                    _prediction(
                        controller=controller,
                        feature=candidate,
                        raw=raw_observations[index],
                    )
                    for candidate in candidates
                ]
                if any(prediction is None for prediction in predictions):
                    continue
                true_count = sum(
                    prediction is True
                    for prediction in predictions
                )
                false_count = len(predictions) - true_count
                disagreement = min(true_count, false_count)
                balance = -abs(true_count - false_count)
                proposal = (
                    disagreement,
                    balance,
                    -index,
                    index,
                )
                if best is None or proposal > best:
                    best = proposal

            if best is None or best[0] <= 0:
                break

            query_index = best[3]
            unqueried.remove(query_index)
            label = query_label(query_index)
            before = len(candidates)

            retained: list[FeatureCapsule] = []
            true_count = 0
            false_count = 0
            for candidate in candidates:
                prediction = _prediction(
                    controller=controller,
                    feature=candidate,
                    raw=raw_observations[query_index],
                )
                if prediction is True:
                    true_count += 1
                elif prediction is False:
                    false_count += 1
                if prediction == label:
                    retained.append(candidate)

            candidates = retained
            trace.append(
                QueryStep(
                    query_index=query_index,
                    candidates_before=before,
                    candidates_after=len(candidates),
                    true_predictions=true_count,
                    false_predictions=false_count,
                    disagreement=min(true_count, false_count),
                )
            )

        if len(candidates) != 1:
            raise ValueError(
                f"active curriculum ended with {len(candidates)} hypotheses"
            )

        return ActiveLearningResult(
            feature=candidates[0],
            queries_used=len(trace),
            initial_candidates=initial_candidates,
            final_candidates=1,
            trace=tuple(trace),
        )
