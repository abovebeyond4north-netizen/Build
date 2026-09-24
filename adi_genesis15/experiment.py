from __future__ import annotations

from dataclasses import dataclass
import itertools
from typing import Iterable

import numpy as np

from adi_genesis13.experiment import LATENT_DIM, TRUE_A, TRUE_B
from adi_genesis14.experiment import SHIFTED_A


OBS_NOISE = 0.04
PROCESS_NOISE = 0.02
OBS_VAR = OBS_NOISE ** 2
ACTION_COUNT = LATENT_DIM + 1
HISTORY = 3

DETECTION_WINDOW = 5
DETECTION_THRESHOLD = 4.0
SHIFT_CHANGE_STEP = 30
SHIFT_MONITOR_STEPS = 65
PRIMARY_ADAPTATION_STEPS = 12


@dataclass(frozen=True)
class TransitionBatch:
    state: np.ndarray
    action: np.ndarray
    next_state: np.ndarray


@dataclass(frozen=True)
class BaseDynamics:
    A: np.ndarray
    B: np.ndarray
    bias: np.ndarray
    Q: np.ndarray


@dataclass(frozen=True)
class RawRecurrent:
    weights: np.ndarray


@dataclass(frozen=True)
class SeedMetrics:
    seed: int
    multistep_candidate_rmse: float
    multistep_raw_rmse: float
    planning_candidate_regret: float
    planning_raw_regret: float
    coverage_90: float
    interval_width_90: float
    shift_detection_rate: float
    false_positive_rate: float
    mean_detection_delay: float
    adapted_candidate_rmse: float
    unadapted_candidate_rmse: float
    adapted_raw_rmse: float

    @property
    def multistep_improvement_vs_raw(self) -> float:
        return 1.0 - self.multistep_candidate_rmse / self.multistep_raw_rmse

    @property
    def planning_regret_improvement_vs_raw(self) -> float:
        return 1.0 - self.planning_candidate_regret / self.planning_raw_regret

    @property
    def adaptation_improvement_vs_unadapted(self) -> float:
        return 1.0 - self.adapted_candidate_rmse / self.unadapted_candidate_rmse

    @property
    def adaptation_improvement_vs_raw(self) -> float:
        return 1.0 - self.adapted_candidate_rmse / self.adapted_raw_rmse


def action_vector(index: int) -> np.ndarray:
    if index < 0 or index >= ACTION_COUNT:
        raise ValueError("invalid action index")
    action = np.zeros(LATENT_DIM, dtype=float)
    if index < LATENT_DIM:
        action[index] = 1.0
    return action


def random_mask(rng: np.random.Generator) -> np.ndarray:
    """Expose exactly two of the three representation coordinates."""

    mask = np.ones(LATENT_DIM, dtype=bool)
    mask[int(rng.integers(0, LATENT_DIM))] = False
    return mask


def partial_observation(
    rng: np.random.Generator,
    state: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    noise = rng.normal(scale=OBS_NOISE, size=LATENT_DIM)
    return np.where(mask, state + noise, 0.0)


def collect_full_rollout(
    rng: np.random.Generator,
    *,
    steps: int,
    dynamics: np.ndarray = TRUE_A,
) -> TransitionBatch:
    state = rng.normal(scale=0.8, size=LATENT_DIM)
    states: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    next_states: list[np.ndarray] = []

    for _ in range(steps):
        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        next_state = (
            dynamics @ state
            + TRUE_B @ action
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        states.append(state)
        actions.append(action)
        next_states.append(next_state)
        state = next_state

    return TransitionBatch(
        state=np.stack(states),
        action=np.stack(actions),
        next_state=np.stack(next_states),
    )


def fit_base_dynamics(
    batches: Iterable[TransitionBatch],
    *,
    ridge_alpha: float = 1e-4,
) -> BaseDynamics:
    rows = list(batches)
    state = np.concatenate([row.state for row in rows], axis=0)
    action = np.concatenate([row.action for row in rows], axis=0)
    target = np.concatenate([row.next_state for row in rows], axis=0)

    design = np.concatenate(
        [state, action, np.ones((len(state), 1), dtype=float)],
        axis=1,
    )
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[-1, -1] = 0.0
    weights = np.linalg.solve(
        design.T @ design + ridge_alpha * penalty,
        design.T @ target,
    )

    residual = target - design @ weights
    covariance = np.cov(residual.T) + np.eye(LATENT_DIM) * 1e-6

    return BaseDynamics(
        A=weights[:LATENT_DIM, :].T,
        B=weights[LATENT_DIM : 2 * LATENT_DIM, :].T,
        bias=weights[-1, :],
        Q=covariance,
    )


def raw_feature(
    observations: list[np.ndarray],
    masks: list[np.ndarray],
    action: np.ndarray,
) -> np.ndarray:
    if len(observations) != HISTORY or len(masks) != HISTORY:
        raise ValueError("raw recurrent history length mismatch")
    parts: list[np.ndarray] = []
    for observation, mask in zip(observations, masks):
        parts.append(observation)
        parts.append(mask.astype(float))
    parts.append(action)
    parts.append(np.ones(1, dtype=float))
    return np.concatenate(parts)


def fit_raw_recurrent(
    rng: np.random.Generator,
    development: Iterable[TransitionBatch],
    *,
    ridge_alpha: float = 1e-3,
) -> RawRecurrent:
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []

    for batch in development:
        states = np.vstack([batch.state, batch.next_state[-1]])
        observations: list[np.ndarray] = []
        masks: list[np.ndarray] = []
        for state in states:
            mask = random_mask(rng)
            masks.append(mask)
            observations.append(partial_observation(rng, state, mask))

        for step in range(HISTORY - 1, len(batch.state)):
            history_observations = observations[step - HISTORY + 1 : step + 1]
            history_masks = masks[step - HISTORY + 1 : step + 1]
            features.append(
                raw_feature(
                    history_observations,
                    history_masks,
                    batch.action[step],
                )
            )
            targets.append(batch.next_state[step])

    design = np.stack(features)
    target = np.stack(targets)
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[-1, -1] = 0.0
    weights = np.linalg.solve(
        design.T @ design + ridge_alpha * penalty,
        design.T @ target,
    )
    return RawRecurrent(weights=weights)


def kalman_measurement_update(
    mean: np.ndarray,
    covariance: np.ndarray,
    observation: np.ndarray,
    mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    indices = np.where(mask)[0]
    H = np.eye(LATENT_DIM)[indices]
    innovation_covariance = (
        H @ covariance @ H.T
        + np.eye(len(indices), dtype=float) * OBS_VAR
    )
    gain = covariance @ H.T @ np.linalg.inv(innovation_covariance)
    innovation = observation[indices] - H @ mean
    updated_mean = mean + gain @ innovation
    updated_covariance = (
        np.eye(LATENT_DIM) - gain @ H
    ) @ covariance
    return updated_mean, updated_covariance


def kalman_predict(
    mean: np.ndarray,
    covariance: np.ndarray,
    action: np.ndarray,
    dynamics: BaseDynamics,
) -> tuple[np.ndarray, np.ndarray]:
    predicted_mean = (
        dynamics.A @ mean
        + dynamics.B @ action
        + dynamics.bias
    )
    predicted_covariance = (
        dynamics.A @ covariance @ dynamics.A.T
        + dynamics.Q
    )
    return predicted_mean, predicted_covariance


def innovation_score(
    predicted_mean: np.ndarray,
    predicted_covariance: np.ndarray,
    observation: np.ndarray,
    mask: np.ndarray,
) -> float:
    indices = np.where(mask)[0]
    H = np.eye(LATENT_DIM)[indices]
    innovation = observation[indices] - H @ predicted_mean
    covariance = (
        H @ predicted_covariance @ H.T
        + np.eye(len(indices), dtype=float) * OBS_VAR
    )
    return float(
        innovation @ np.linalg.solve(covariance, innovation)
        / len(indices)
    )


def warmup_belief(
    rng: np.random.Generator,
    dynamics: BaseDynamics,
    *,
    steps: int = 8,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    list[np.ndarray],
    list[np.ndarray],
]:
    true_state = rng.normal(scale=0.8, size=LATENT_DIM)
    mean = np.zeros(LATENT_DIM, dtype=float)
    covariance = np.eye(LATENT_DIM, dtype=float)
    history_observations = [
        np.zeros(LATENT_DIM, dtype=float)
        for _ in range(HISTORY - 1)
    ]
    history_masks = [
        np.zeros(LATENT_DIM, dtype=bool)
        for _ in range(HISTORY - 1)
    ]

    for _ in range(steps):
        mask = random_mask(rng)
        observation = partial_observation(rng, true_state, mask)
        mean, covariance = kalman_measurement_update(
            mean,
            covariance,
            observation,
            mask,
        )
        history_observations.append(observation)
        history_masks.append(mask)
        history_observations = history_observations[-HISTORY:]
        history_masks = history_masks[-HISTORY:]

        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        true_state = (
            TRUE_A @ true_state
            + TRUE_B @ action
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        mean, covariance = kalman_predict(
            mean,
            covariance,
            action,
            dynamics,
        )

    mask = random_mask(rng)
    observation = partial_observation(rng, true_state, mask)
    mean, covariance = kalman_measurement_update(
        mean,
        covariance,
        observation,
        mask,
    )
    history_observations.append(observation)
    history_masks.append(mask)

    return (
        true_state,
        mean,
        covariance,
        history_observations[-HISTORY:],
        history_masks[-HISTORY:],
    )


def evaluate_multistep(
    rng: np.random.Generator,
    dynamics: BaseDynamics,
    raw: RawRecurrent,
    *,
    cases: int = 80,
    horizon: int = 6,
) -> tuple[float, float]:
    candidate_errors: list[float] = []
    raw_errors: list[float] = []

    for _ in range(cases):
        (
            true_state,
            belief,
            _,
            history_observations,
            history_masks,
        ) = warmup_belief(rng, dynamics)

        actions = [
            int(rng.integers(0, ACTION_COUNT))
            for _ in range(horizon)
        ]
        future_masks = [random_mask(rng) for _ in range(horizon)]

        candidate_state = belief.copy()
        raw_observations = [row.copy() for row in history_observations]
        raw_masks = [row.copy() for row in history_masks]
        raw_prediction = belief.copy()

        for action_index, mask in zip(actions, future_masks):
            action = action_vector(action_index)
            true_state = TRUE_A @ true_state + TRUE_B @ action
            candidate_state = (
                dynamics.A @ candidate_state
                + dynamics.B @ action
                + dynamics.bias
            )
            raw_prediction = (
                raw_feature(raw_observations, raw_masks, action)
                @ raw.weights
            )
            raw_observations = (
                raw_observations
                + [np.where(mask, raw_prediction, 0.0)]
            )[-HISTORY:]
            raw_masks = (raw_masks + [mask])[-HISTORY:]

        candidate_errors.append(
            float(
                np.sqrt(
                    np.mean((candidate_state - true_state) ** 2)
                )
            )
        )
        raw_errors.append(
            float(
                np.sqrt(
                    np.mean((raw_prediction - true_state) ** 2)
                )
            )
        )

    return float(np.mean(candidate_errors)), float(np.mean(raw_errors))


def _raw_rollout(
    raw: RawRecurrent,
    observations: list[np.ndarray],
    masks: list[np.ndarray],
    sequence: tuple[int, ...],
    future_masks: list[np.ndarray],
) -> np.ndarray:
    current_observations = [row.copy() for row in observations]
    current_masks = [row.copy() for row in masks]
    prediction = np.zeros(LATENT_DIM, dtype=float)

    for action_index, mask in zip(sequence, future_masks):
        action = action_vector(action_index)
        prediction = (
            raw_feature(current_observations, current_masks, action)
            @ raw.weights
        )
        current_observations = (
            current_observations
            + [np.where(mask, prediction, 0.0)]
        )[-HISTORY:]
        current_masks = (current_masks + [mask])[-HISTORY:]

    return prediction


def _true_rollout(
    state: np.ndarray,
    sequence: tuple[int, ...],
    *,
    dynamics: np.ndarray = TRUE_A,
) -> np.ndarray:
    current = state.copy()
    for action_index in sequence:
        current = (
            dynamics @ current
            + TRUE_B @ action_vector(action_index)
        )
    return current


def evaluate_planning(
    rng: np.random.Generator,
    dynamics: BaseDynamics,
    raw: RawRecurrent,
    *,
    cases: int = 40,
    horizon: int = 4,
) -> tuple[float, float]:
    sequences = list(
        itertools.product(range(ACTION_COUNT), repeat=horizon)
    )
    candidate_regret: list[float] = []
    raw_regret: list[float] = []

    for _ in range(cases):
        (
            true_state,
            belief,
            _,
            history_observations,
            history_masks,
        ) = warmup_belief(rng, dynamics)
        target = rng.normal(scale=0.8, size=LATENT_DIM)
        future_masks = [random_mask(rng) for _ in range(horizon)]

        candidate_best: tuple[float, tuple[int, ...]] | None = None
        raw_best: tuple[float, tuple[int, ...]] | None = None
        oracle_best: tuple[float, tuple[int, ...]] | None = None

        for sequence in sequences:
            predicted = belief.copy()
            for action_index in sequence:
                action = action_vector(action_index)
                predicted = (
                    dynamics.A @ predicted
                    + dynamics.B @ action
                    + dynamics.bias
                )
            candidate_cost = float(
                np.sum((predicted - target) ** 2)
            )
            if (
                candidate_best is None
                or candidate_cost < candidate_best[0]
            ):
                candidate_best = (candidate_cost, sequence)

            raw_prediction = _raw_rollout(
                raw,
                history_observations,
                history_masks,
                sequence,
                future_masks,
            )
            raw_cost = float(
                np.sum((raw_prediction - target) ** 2)
            )
            if raw_best is None or raw_cost < raw_best[0]:
                raw_best = (raw_cost, sequence)

            true_final = _true_rollout(true_state, sequence)
            oracle_cost = float(
                np.sum((true_final - target) ** 2)
            )
            if oracle_best is None or oracle_cost < oracle_best[0]:
                oracle_best = (oracle_cost, sequence)

        assert candidate_best is not None
        assert raw_best is not None
        assert oracle_best is not None

        candidate_actual = float(
            np.sum(
                (
                    _true_rollout(
                        true_state,
                        candidate_best[1],
                    )
                    - target
                )
                ** 2
            )
        )
        raw_actual = float(
            np.sum(
                (
                    _true_rollout(
                        true_state,
                        raw_best[1],
                    )
                    - target
                )
                ** 2
            )
        )

        candidate_regret.append(
            max(0.0, candidate_actual - oracle_best[0])
        )
        raw_regret.append(
            max(0.0, raw_actual - oracle_best[0])
        )

    return float(np.mean(candidate_regret)), float(np.mean(raw_regret))


def evaluate_calibration(
    rng: np.random.Generator,
    dynamics: BaseDynamics,
    *,
    steps: int = 240,
) -> tuple[float, float]:
    true_state = rng.normal(scale=0.8, size=LATENT_DIM)
    mean = np.zeros(LATENT_DIM, dtype=float)
    covariance = np.eye(LATENT_DIM, dtype=float)

    mask = random_mask(rng)
    observation = partial_observation(rng, true_state, mask)
    mean, covariance = kalman_measurement_update(
        mean,
        covariance,
        observation,
        mask,
    )

    covered: list[bool] = []
    widths: list[float] = []

    for _ in range(steps):
        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        predicted_mean, predicted_covariance = kalman_predict(
            mean,
            covariance,
            action,
            dynamics,
        )
        next_state = (
            TRUE_A @ true_state
            + TRUE_B @ action
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )

        standard_deviation = np.sqrt(
            np.maximum(
                np.diag(predicted_covariance),
                1e-12,
            )
        )
        covered.extend(
            (
                np.abs(next_state - predicted_mean)
                <= 1.645 * standard_deviation
            ).tolist()
        )
        widths.extend(
            (2.0 * 1.645 * standard_deviation).tolist()
        )

        mask = random_mask(rng)
        observation = partial_observation(rng, next_state, mask)
        mean, covariance = kalman_measurement_update(
            predicted_mean,
            predicted_covariance,
            observation,
            mask,
        )
        true_state = next_state

    return float(np.mean(covered)), float(np.mean(widths))


def detect_shift(
    rng: np.random.Generator,
    dynamics: BaseDynamics,
    *,
    shift: bool,
    change_step: int = SHIFT_CHANGE_STEP,
    total_steps: int = SHIFT_MONITOR_STEPS,
) -> int | None:
    true_state = rng.normal(scale=0.8, size=LATENT_DIM)
    mean = np.zeros(LATENT_DIM, dtype=float)
    covariance = np.eye(LATENT_DIM, dtype=float)

    mask = random_mask(rng)
    observation = partial_observation(rng, true_state, mask)
    mean, covariance = kalman_measurement_update(
        mean,
        covariance,
        observation,
        mask,
    )

    scores: list[float] = []
    trigger: int | None = None

    for step in range(total_steps):
        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        hidden_dynamics = (
            SHIFTED_A
            if shift and step >= change_step
            else TRUE_A
        )
        next_state = (
            hidden_dynamics @ true_state
            + TRUE_B @ action
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        predicted_mean, predicted_covariance = kalman_predict(
            mean,
            covariance,
            action,
            dynamics,
        )

        mask = random_mask(rng)
        observation = partial_observation(rng, next_state, mask)
        scores.append(
            innovation_score(
                predicted_mean,
                predicted_covariance,
                observation,
                mask,
            )
        )

        mean, covariance = kalman_measurement_update(
            predicted_mean,
            predicted_covariance,
            observation,
            mask,
        )

        if (
            trigger is None
            and len(scores) >= DETECTION_WINDOW
            and float(np.mean(scores[-DETECTION_WINDOW:]))
            > DETECTION_THRESHOLD
        ):
            trigger = step

        true_state = next_state

    return trigger


def evaluate_detection(
    rng: np.random.Generator,
    dynamics: BaseDynamics,
    *,
    episodes: int = 10,
) -> tuple[float, float, float]:
    detected = 0
    false_positive = 0
    delays: list[int] = []

    for _ in range(episodes):
        trigger = detect_shift(
            rng,
            dynamics,
            shift=True,
        )
        if trigger is not None and trigger >= SHIFT_CHANGE_STEP:
            detected += 1
            delays.append(trigger - SHIFT_CHANGE_STEP)

    for _ in range(episodes):
        trigger = detect_shift(
            rng,
            dynamics,
            shift=False,
        )
        if trigger is not None:
            false_positive += 1

    detection_rate = detected / episodes
    false_positive_rate = false_positive / episodes
    mean_delay = (
        float(np.mean(delays))
        if delays
        else float(SHIFT_MONITOR_STEPS)
    )
    return detection_rate, false_positive_rate, mean_delay


def generate_partial_sequence(
    rng: np.random.Generator,
    *,
    steps: int,
    dynamics: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    true_state = rng.normal(scale=0.8, size=LATENT_DIM)
    states = [true_state.copy()]
    actions: list[np.ndarray] = []
    observations: list[np.ndarray] = []
    masks: list[np.ndarray] = []

    mask = random_mask(rng)
    masks.append(mask)
    observations.append(
        partial_observation(rng, true_state, mask)
    )

    for _ in range(steps):
        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        actions.append(action)
        true_state = (
            dynamics @ true_state
            + TRUE_B @ action
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        states.append(true_state.copy())
        mask = random_mask(rng)
        masks.append(mask)
        observations.append(
            partial_observation(rng, true_state, mask)
        )

    return (
        np.stack(states),
        np.stack(actions),
        np.stack(observations),
        np.stack(masks),
    )


def smooth_states(
    observations: np.ndarray,
    masks: np.ndarray,
    actions: np.ndarray,
    dynamics: BaseDynamics,
) -> np.ndarray:
    steps = len(actions)
    filtered_means: list[np.ndarray] = []
    filtered_covariances: list[np.ndarray] = []
    predicted_means: list[np.ndarray] = [
        np.zeros(LATENT_DIM, dtype=float)
        for _ in range(steps + 1)
    ]
    predicted_covariances: list[np.ndarray] = [
        np.eye(LATENT_DIM, dtype=float)
        for _ in range(steps + 1)
    ]

    mean = np.zeros(LATENT_DIM, dtype=float)
    covariance = np.eye(LATENT_DIM, dtype=float)

    for step in range(steps + 1):
        if step > 0:
            mean, covariance = kalman_predict(
                mean,
                covariance,
                actions[step - 1],
                dynamics,
            )
        predicted_means[step] = mean.copy()
        predicted_covariances[step] = covariance.copy()
        mean, covariance = kalman_measurement_update(
            mean,
            covariance,
            observations[step],
            masks[step],
        )
        filtered_means.append(mean.copy())
        filtered_covariances.append(covariance.copy())

    smoothed = [row.copy() for row in filtered_means]

    for step in range(steps - 1, -1, -1):
        gain = (
            filtered_covariances[step]
            @ dynamics.A.T
            @ np.linalg.inv(predicted_covariances[step + 1])
        )
        smoothed[step] = (
            filtered_means[step]
            + gain
            @ (
                smoothed[step + 1]
                - predicted_means[step + 1]
            )
        )

    return np.stack(smoothed)


def fit_smoothed_residual(
    observations: np.ndarray,
    masks: np.ndarray,
    actions: np.ndarray,
    base: BaseDynamics,
    *,
    ridge_alpha: float = 0.1,
    iterations: int = 2,
) -> BaseDynamics:
    current = base

    for _ in range(iterations):
        smoothed = smooth_states(
            observations,
            masks,
            actions,
            current,
        )
        state = smoothed[:-1]
        target = (
            smoothed[1:]
            - actions @ base.B.T
            - base.bias
        )
        gram = state.T @ state
        adapted_A = np.empty_like(base.A)

        for output in range(LATENT_DIM):
            rhs = (
                state.T @ target[:, output]
                + ridge_alpha * base.A[output]
            )
            adapted_A[output] = np.linalg.solve(
                gram
                + ridge_alpha * np.eye(LATENT_DIM),
                rhs,
            )

        current = BaseDynamics(
            A=adapted_A,
            B=base.B,
            bias=base.bias,
            Q=base.Q,
        )

    return current


def raw_adaptation_samples(
    observations: np.ndarray,
    masks: np.ndarray,
    actions: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    history_observations = [
        np.zeros(LATENT_DIM, dtype=float)
        for _ in range(HISTORY - 1)
    ] + [observations[0]]
    history_masks = [
        np.zeros(LATENT_DIM, dtype=bool)
        for _ in range(HISTORY - 1)
    ] + [masks[0]]

    samples: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    for step, action in enumerate(actions):
        feature = raw_feature(
            history_observations[-HISTORY:],
            history_masks[-HISTORY:],
            action,
        )
        samples.append(
            (
                feature,
                observations[step + 1],
                masks[step + 1],
            )
        )
        history_observations.append(observations[step + 1])
        history_masks.append(masks[step + 1])

    return samples


def fit_raw_residual(
    raw: RawRecurrent,
    samples: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    *,
    ridge_alpha: float = 10.0,
) -> RawRecurrent:
    adapted = raw.weights.copy()
    width = adapted.shape[0]

    for output in range(LATENT_DIM):
        design: list[np.ndarray] = []
        residual: list[float] = []
        for feature, observation, mask in samples:
            if mask[output]:
                design.append(feature)
                residual.append(
                    float(
                        observation[output]
                        - feature @ raw.weights[:, output]
                    )
                )

        if not design:
            continue

        X = np.stack(design)
        y = np.asarray(residual)
        penalty = np.eye(width, dtype=float)
        penalty[-1, -1] = 0.0
        correction = np.linalg.solve(
            X.T @ X + ridge_alpha * penalty,
            X.T @ y,
        )
        adapted[:, output] += correction

    return RawRecurrent(weights=adapted)


def evaluate_shift_adaptation(
    rng: np.random.Generator,
    base: BaseDynamics,
    raw: RawRecurrent,
    *,
    adaptation_steps: int = PRIMARY_ADAPTATION_STEPS,
    test_steps: int = 120,
) -> tuple[float, float, float]:
    _, actions, observations, masks = generate_partial_sequence(
        rng,
        steps=adaptation_steps,
        dynamics=SHIFTED_A,
    )

    adapted = fit_smoothed_residual(
        observations,
        masks,
        actions,
        base,
    )
    adapted_raw = fit_raw_residual(
        raw,
        raw_adaptation_samples(
            observations,
            masks,
            actions,
        ),
    )

    true_state = rng.normal(scale=0.8, size=LATENT_DIM)

    adapted_mean = np.zeros(LATENT_DIM, dtype=float)
    adapted_covariance = np.eye(LATENT_DIM, dtype=float)
    base_mean = np.zeros(LATENT_DIM, dtype=float)
    base_covariance = np.eye(LATENT_DIM, dtype=float)

    history_observations = [
        np.zeros(LATENT_DIM, dtype=float)
        for _ in range(HISTORY)
    ]
    history_masks = [
        np.zeros(LATENT_DIM, dtype=bool)
        for _ in range(HISTORY)
    ]

    adapted_errors: list[float] = []
    base_errors: list[float] = []
    raw_errors: list[float] = []

    for _ in range(test_steps):
        mask = random_mask(rng)
        observation = partial_observation(
            rng,
            true_state,
            mask,
        )

        adapted_mean, adapted_covariance = kalman_measurement_update(
            adapted_mean,
            adapted_covariance,
            observation,
            mask,
        )
        base_mean, base_covariance = kalman_measurement_update(
            base_mean,
            base_covariance,
            observation,
            mask,
        )

        history_observations = (
            history_observations + [observation]
        )[-HISTORY:]
        history_masks = (
            history_masks + [mask]
        )[-HISTORY:]

        action = action_vector(int(rng.integers(0, ACTION_COUNT)))

        adapted_prediction, adapted_prediction_covariance = kalman_predict(
            adapted_mean,
            adapted_covariance,
            action,
            adapted,
        )
        base_prediction, base_prediction_covariance = kalman_predict(
            base_mean,
            base_covariance,
            action,
            base,
        )
        raw_prediction = (
            raw_feature(
                history_observations,
                history_masks,
                action,
            )
            @ adapted_raw.weights
        )

        next_state = (
            SHIFTED_A @ true_state
            + TRUE_B @ action
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )

        adapted_errors.append(
            float(
                np.sqrt(
                    np.mean(
                        (adapted_prediction - next_state) ** 2
                    )
                )
            )
        )
        base_errors.append(
            float(
                np.sqrt(
                    np.mean(
                        (base_prediction - next_state) ** 2
                    )
                )
            )
        )
        raw_errors.append(
            float(
                np.sqrt(
                    np.mean(
                        (raw_prediction - next_state) ** 2
                    )
                )
            )
        )

        adapted_mean = adapted_prediction
        adapted_covariance = adapted_prediction_covariance
        base_mean = base_prediction
        base_covariance = base_prediction_covariance
        true_state = next_state

    return (
        float(np.mean(adapted_errors)),
        float(np.mean(base_errors)),
        float(np.mean(raw_errors)),
    )


def build_models(
    seed: int,
    *,
    development_worlds: int = 5,
    development_steps: int = 450,
) -> tuple[np.random.Generator, BaseDynamics, RawRecurrent]:
    rng = np.random.default_rng(seed)
    development = [
        collect_full_rollout(
            rng,
            steps=development_steps,
        )
        for _ in range(development_worlds)
    ]
    base = fit_base_dynamics(development)
    raw = fit_raw_recurrent(rng, development)
    return rng, base, raw


def evaluate_seed(seed: int) -> SeedMetrics:
    rng, base, raw = build_models(seed)

    multistep_candidate, multistep_raw = evaluate_multistep(
        rng,
        base,
        raw,
    )
    planning_candidate, planning_raw = evaluate_planning(
        rng,
        base,
        raw,
    )
    coverage, width = evaluate_calibration(
        rng,
        base,
    )
    detection, false_positive, delay = evaluate_detection(
        rng,
        base,
    )
    adapted, unadapted, raw_adapted = evaluate_shift_adaptation(
        rng,
        base,
        raw,
    )

    return SeedMetrics(
        seed=seed,
        multistep_candidate_rmse=multistep_candidate,
        multistep_raw_rmse=multistep_raw,
        planning_candidate_regret=planning_candidate,
        planning_raw_regret=planning_raw,
        coverage_90=coverage,
        interval_width_90=width,
        shift_detection_rate=detection,
        false_positive_rate=false_positive,
        mean_detection_delay=delay,
        adapted_candidate_rmse=adapted,
        unadapted_candidate_rmse=unadapted,
        adapted_raw_rmse=raw_adapted,
    )


def evaluate_adaptation_budget(
    seed: int,
    *,
    adaptation_steps: int,
) -> dict[str, float]:
    rng, base, raw = build_models(seed)
    adapted, unadapted, raw_adapted = evaluate_shift_adaptation(
        rng,
        base,
        raw,
        adaptation_steps=adaptation_steps,
    )
    return {
        "adapted_candidate_rmse": adapted,
        "unadapted_candidate_rmse": unadapted,
        "adapted_raw_rmse": raw_adapted,
        "improvement_vs_unadapted": 1.0 - adapted / unadapted,
        "improvement_vs_raw": 1.0 - adapted / raw_adapted,
    }


def summarize(rows: Iterable[SeedMetrics]) -> dict[str, float]:
    values = list(rows)
    if not values:
        raise ValueError("at least one seed result is required")

    def mean(name: str) -> float:
        return float(np.mean([getattr(row, name) for row in values]))

    return {
        "n_seeds": float(len(values)),
        "multistep_candidate_rmse": mean("multistep_candidate_rmse"),
        "multistep_raw_rmse": mean("multistep_raw_rmse"),
        "multistep_improvement_vs_raw": float(
            np.mean(
                [
                    row.multistep_improvement_vs_raw
                    for row in values
                ]
            )
        ),
        "planning_candidate_regret": mean("planning_candidate_regret"),
        "planning_raw_regret": mean("planning_raw_regret"),
        "planning_regret_improvement_vs_raw": float(
            np.mean(
                [
                    row.planning_regret_improvement_vs_raw
                    for row in values
                ]
            )
        ),
        "coverage_90": mean("coverage_90"),
        "interval_width_90": mean("interval_width_90"),
        "shift_detection_rate": mean("shift_detection_rate"),
        "false_positive_rate": mean("false_positive_rate"),
        "mean_detection_delay": mean("mean_detection_delay"),
        "adapted_candidate_rmse": mean("adapted_candidate_rmse"),
        "unadapted_candidate_rmse": mean("unadapted_candidate_rmse"),
        "adapted_raw_rmse": mean("adapted_raw_rmse"),
        "adaptation_improvement_vs_unadapted": float(
            np.mean(
                [
                    row.adaptation_improvement_vs_unadapted
                    for row in values
                ]
            )
        ),
        "adaptation_improvement_vs_raw": float(
            np.mean(
                [
                    row.adaptation_improvement_vs_raw
                    for row in values
                ]
            )
        ),
    }


def run_block(seeds: Iterable[int]) -> dict:
    rows = [evaluate_seed(seed) for seed in seeds]
    return {
        "summary": summarize(rows),
        "seeds": [row.__dict__ for row in rows],
    }


def run_adaptation_sweep(
    seeds: Iterable[int],
    budgets: Iterable[int],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    seed_list = list(seeds)

    for budget in budgets:
        rows = [
            evaluate_adaptation_budget(
                seed,
                adaptation_steps=budget,
            )
            for seed in seed_list
        ]
        result[str(budget)] = {
            key: float(np.mean([row[key] for row in rows]))
            for key in rows[0]
        }

    return result
