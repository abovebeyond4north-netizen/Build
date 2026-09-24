from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
import time
from typing import Iterable

import numpy as np

from adi_genesis13.experiment import LATENT_DIM, TRUE_A, TRUE_B
from adi_genesis15.experiment import (
    ACTION_COUNT,
    OBS_NOISE,
    OBS_VAR,
    action_vector,
    kalman_measurement_update,
    partial_observation,
    random_mask,
)


PROCESS_NOISE = 0.025
ENSEMBLE_SIZE = 7
RIDGE_ALPHA = 3e-3
DEVELOPMENT_EPISODES = 6
DEVELOPMENT_STEPS = 220
DETECTION_WINDOW = 5
DETECTION_THRESHOLD = 3.6
SHIFT_STEP = 35
MONITOR_STEPS = 75


@dataclass(frozen=True)
class NonlinearCoefficients:
    sin_y: float = 0.12
    cross_xz: float = 0.09
    square_y: float = -0.07
    sin_x: float = 0.05


BASE_COEFFICIENTS = NonlinearCoefficients()
ABRUPT_COEFFICIENTS = NonlinearCoefficients(
    sin_y=0.22,
    cross_xz=0.16,
    square_y=-0.13,
    sin_x=0.10,
)


@dataclass(frozen=True)
class TransitionBatch:
    state: np.ndarray
    action: np.ndarray
    next_state: np.ndarray


@dataclass(frozen=True)
class EnsembleDynamics:
    # weights: [ensemble, feature, output]
    # Q: [ensemble, output, output]
    weights: np.ndarray
    Q: np.ndarray
    mean_weights: np.ndarray


@dataclass(frozen=True)
class LinearDynamics:
    weights: np.ndarray
    Q: np.ndarray


@dataclass(frozen=True)
class SeedMetrics:
    seed: int
    multistep_candidate_rmse: float
    multistep_linear_rmse: float
    planning_candidate_regret: float
    planning_linear_regret: float
    coverage_90: float
    interval_width_90: float
    gaussian_nll: float
    single_model_nll: float
    abrupt_detection_rate: float
    gradual_detection_rate: float
    false_positive_rate: float
    abrupt_detection_delay: float
    gradual_detection_delay: float
    candidate_compute_seconds: float
    linear_compute_seconds: float

    @property
    def multistep_improvement_vs_linear(self) -> float:
        return 1.0 - self.multistep_candidate_rmse / self.multistep_linear_rmse

    @property
    def planning_improvement_vs_linear(self) -> float:
        return 1.0 - self.planning_candidate_regret / self.planning_linear_regret

    @property
    def nll_gain_vs_single(self) -> float:
        """Absolute proper-scoring-rule gain; positive means ensemble is better."""
        return self.single_model_nll - self.gaussian_nll

    @property
    def compute_ratio(self) -> float:
        return self.candidate_compute_seconds / max(self.linear_compute_seconds, 1e-9)


def nonlinear_term(
    state: np.ndarray,
    coefficients: NonlinearCoefficients,
) -> np.ndarray:
    x, y, z = state
    return np.array(
        [
            coefficients.sin_y * math.sin(1.7 * y),
            coefficients.cross_xz * x * z,
            coefficients.square_y * y * y
            + coefficients.sin_x * math.sin(x),
        ],
        dtype=float,
    )


def hidden_step(
    state: np.ndarray,
    action: np.ndarray,
    *,
    coefficients: NonlinearCoefficients = BASE_COEFFICIENTS,
) -> np.ndarray:
    return (
        TRUE_A @ state
        + TRUE_B @ action
        + nonlinear_term(state, coefficients)
    )


def interpolate_coefficients(
    fraction: float,
) -> NonlinearCoefficients:
    fraction = float(np.clip(fraction, 0.0, 1.0))
    return NonlinearCoefficients(
        sin_y=BASE_COEFFICIENTS.sin_y
        + fraction * (ABRUPT_COEFFICIENTS.sin_y - BASE_COEFFICIENTS.sin_y),
        cross_xz=BASE_COEFFICIENTS.cross_xz
        + fraction * (ABRUPT_COEFFICIENTS.cross_xz - BASE_COEFFICIENTS.cross_xz),
        square_y=BASE_COEFFICIENTS.square_y
        + fraction * (ABRUPT_COEFFICIENTS.square_y - BASE_COEFFICIENTS.square_y),
        sin_x=BASE_COEFFICIENTS.sin_x
        + fraction * (ABRUPT_COEFFICIENTS.sin_x - BASE_COEFFICIENTS.sin_x),
    )


def nonlinear_features(
    state: np.ndarray,
    action: np.ndarray,
) -> np.ndarray:
    x, y, z = state
    return np.concatenate(
        [
            state,
            np.array(
                [
                    x * y,
                    x * z,
                    y * z,
                    x * x,
                    y * y,
                    z * z,
                    math.sin(x),
                    math.sin(y),
                    math.sin(z),
                    math.sin(1.7 * x),
                    math.sin(1.7 * y),
                    math.sin(1.7 * z),
                ],
                dtype=float,
            ),
            action,
            np.ones(1, dtype=float),
        ]
    )


def linear_features(
    state: np.ndarray,
    action: np.ndarray,
) -> np.ndarray:
    return np.concatenate([state, action, np.ones(1, dtype=float)])


def collect_rollout(
    rng: np.random.Generator,
    *,
    steps: int,
    coefficients: NonlinearCoefficients = BASE_COEFFICIENTS,
) -> TransitionBatch:
    state = rng.normal(scale=0.7, size=LATENT_DIM)
    states: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    next_states: list[np.ndarray] = []

    for _ in range(steps):
        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        next_state = (
            hidden_step(state, action, coefficients=coefficients)
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        states.append(state)
        actions.append(action)
        next_states.append(next_state)
        state = next_state
        if np.linalg.norm(state) > 4.0:
            state = rng.normal(scale=0.7, size=LATENT_DIM)

    return TransitionBatch(
        state=np.stack(states),
        action=np.stack(actions),
        next_state=np.stack(next_states),
    )


def _ridge(
    design: np.ndarray,
    target: np.ndarray,
    *,
    alpha: float,
) -> np.ndarray:
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[-1, -1] = 0.0
    return np.linalg.solve(
        design.T @ design + alpha * penalty,
        design.T @ target,
    )


def fit_ensemble(
    rng: np.random.Generator,
    batches: Iterable[TransitionBatch],
    *,
    ensemble_size: int = ENSEMBLE_SIZE,
    ridge_alpha: float = RIDGE_ALPHA,
) -> EnsembleDynamics:
    rows = list(batches)
    state = np.concatenate([r.state for r in rows], axis=0)
    action = np.concatenate([r.action for r in rows], axis=0)
    target = np.concatenate([r.next_state for r in rows], axis=0)
    design = np.stack(
        [nonlinear_features(s, a) for s, a in zip(state, action)]
    )

    member_weights: list[np.ndarray] = []
    member_covariances: list[np.ndarray] = []
    n = len(target)
    for _ in range(ensemble_size):
        indices = rng.integers(0, n, size=n)
        weights = _ridge(
            design[indices],
            target[indices],
            alpha=ridge_alpha,
        )
        residual = target - design @ weights
        Q = np.cov(residual.T) + np.eye(LATENT_DIM) * 1e-6
        member_weights.append(weights)
        member_covariances.append(Q)
    stacked_weights = np.stack(member_weights, axis=0)
    return EnsembleDynamics(
        weights=stacked_weights,
        Q=np.stack(member_covariances, axis=0),
        mean_weights=stacked_weights.mean(axis=0),
    )


def fit_linear(
    batches: Iterable[TransitionBatch],
    *,
    ridge_alpha: float = 1e-3,
) -> LinearDynamics:
    rows = list(batches)
    state = np.concatenate([r.state for r in rows], axis=0)
    action = np.concatenate([r.action for r in rows], axis=0)
    target = np.concatenate([r.next_state for r in rows], axis=0)
    design = np.stack(
        [linear_features(s, a) for s, a in zip(state, action)]
    )
    weights = _ridge(design, target, alpha=ridge_alpha)
    residual = target - design @ weights
    Q = np.cov(residual.T) + np.eye(LATENT_DIM) * 1e-6
    return LinearDynamics(weights=weights, Q=Q)


def ensemble_mean_predict(
    model: EnsembleDynamics,
    state: np.ndarray,
    action: np.ndarray,
) -> np.ndarray:
    return nonlinear_features(state, action) @ model.mean_weights


def ensemble_predict(
    model: EnsembleDynamics,
    state: np.ndarray,
    action: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    features = nonlinear_features(state, action)
    predictions = np.einsum("f,efd->ed", features, model.weights)
    mean = predictions.mean(axis=0)
    epistemic = (
        np.cov(predictions.T)
        if model.weights.shape[0] > 1
        else np.zeros((LATENT_DIM, LATENT_DIM), dtype=float)
    )
    aleatoric = model.Q.mean(axis=0)
    covariance = epistemic + aleatoric + np.eye(LATENT_DIM) * 1e-7
    return mean, covariance


def single_predict(
    model: EnsembleDynamics,
    state: np.ndarray,
    action: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    features = nonlinear_features(state, action)
    return features @ model.weights[0], model.Q[0]


def linear_predict(
    model: LinearDynamics,
    state: np.ndarray,
    action: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    return linear_features(state, action) @ model.weights, model.Q


def _jacobian(
    predictor,
    state: np.ndarray,
    action: np.ndarray,
    *,
    epsilon: float = 1e-4,
) -> np.ndarray:
    base = predictor(state, action)[0]
    columns = []
    for index in range(LATENT_DIM):
        shifted = state.copy()
        shifted[index] += epsilon
        columns.append((predictor(shifted, action)[0] - base) / epsilon)
    return np.stack(columns, axis=1)


def belief_predict_ensemble(
    mean: np.ndarray,
    covariance: np.ndarray,
    action: np.ndarray,
    model: EnsembleDynamics,
    *,
    include_epistemic: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    predictor = (
        (lambda s, a: ensemble_predict(model, s, a))
        if include_epistemic
        else (lambda s, a: single_predict(model, s, a))
    )
    next_mean, model_covariance = predictor(mean, action)
    J = _jacobian(predictor, mean, action)
    next_covariance = (
        J @ covariance @ J.T
        + model_covariance
        + np.eye(LATENT_DIM) * 1e-7
    )
    return next_mean, next_covariance


def belief_predict_linear(
    mean: np.ndarray,
    covariance: np.ndarray,
    action: np.ndarray,
    model: LinearDynamics,
) -> tuple[np.ndarray, np.ndarray]:
    next_mean, _ = linear_predict(model, mean, action)
    A = model.weights[:LATENT_DIM, :].T
    return (
        next_mean,
        A @ covariance @ A.T + model.Q + np.eye(LATENT_DIM) * 1e-7,
    )


def warmup_dual(
    rng: np.random.Generator,
    ensemble: EnsembleDynamics,
    linear: LinearDynamics,
    *,
    steps: int = 10,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    true_state = rng.normal(scale=0.7, size=LATENT_DIM)
    e_mean = np.zeros(LATENT_DIM, dtype=float)
    e_cov = np.eye(LATENT_DIM, dtype=float)
    l_mean = np.zeros(LATENT_DIM, dtype=float)
    l_cov = np.eye(LATENT_DIM, dtype=float)

    for _ in range(steps):
        mask = random_mask(rng)
        observation = partial_observation(rng, true_state, mask)
        e_mean, e_cov = kalman_measurement_update(
            e_mean, e_cov, observation, mask
        )
        l_mean, l_cov = kalman_measurement_update(
            l_mean, l_cov, observation, mask
        )
        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        true_state = (
            hidden_step(true_state, action)
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        e_mean, e_cov = belief_predict_ensemble(
            e_mean, e_cov, action, ensemble
        )
        l_mean, l_cov = belief_predict_linear(
            l_mean, l_cov, action, linear
        )

    mask = random_mask(rng)
    observation = partial_observation(rng, true_state, mask)
    e_mean, e_cov = kalman_measurement_update(
        e_mean, e_cov, observation, mask
    )
    l_mean, l_cov = kalman_measurement_update(
        l_mean, l_cov, observation, mask
    )
    return true_state, e_mean, e_cov, l_mean, l_cov


def evaluate_multistep(
    rng: np.random.Generator,
    ensemble: EnsembleDynamics,
    linear: LinearDynamics,
    *,
    cases: int = 70,
    horizon: int = 8,
) -> tuple[float, float, float, float]:
    candidate_errors: list[float] = []
    linear_errors: list[float] = []
    candidate_time = 0.0
    linear_time = 0.0

    for _ in range(cases):
        true_state, e_mean, _, l_mean, _ = warmup_dual(
            rng, ensemble, linear
        )
        actions = [
            action_vector(int(rng.integers(0, ACTION_COUNT)))
            for _ in range(horizon)
        ]

        candidate = e_mean.copy()
        baseline = l_mean.copy()
        for action in actions:
            true_state = (
                hidden_step(true_state, action)
                + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
            )
            start = time.process_time()
            candidate = ensemble_mean_predict(ensemble, candidate, action)
            candidate_time += time.process_time() - start
            start = time.process_time()
            baseline = linear_predict(linear, baseline, action)[0]
            linear_time += time.process_time() - start

        candidate_errors.append(
            float(np.sqrt(np.mean((candidate - true_state) ** 2)))
        )
        linear_errors.append(
            float(np.sqrt(np.mean((baseline - true_state) ** 2)))
        )

    return (
        float(np.mean(candidate_errors)),
        float(np.mean(linear_errors)),
        candidate_time,
        linear_time,
    )


def _true_rollout(
    state: np.ndarray,
    sequence: tuple[int, ...],
    *,
    coefficients: NonlinearCoefficients = BASE_COEFFICIENTS,
) -> np.ndarray:
    current = state.copy()
    for action_index in sequence:
        current = hidden_step(
            current,
            action_vector(action_index),
            coefficients=coefficients,
        )
    return current


def evaluate_planning(
    rng: np.random.Generator,
    ensemble: EnsembleDynamics,
    linear: LinearDynamics,
    *,
    cases: int = 28,
    horizon: int = 4,
) -> tuple[float, float, float, float]:
    sequences = list(itertools.product(range(ACTION_COUNT), repeat=horizon))
    candidate_regrets: list[float] = []
    linear_regrets: list[float] = []
    candidate_time = 0.0
    linear_time = 0.0

    for _ in range(cases):
        true_state, e_mean, _, l_mean, _ = warmup_dual(
            rng, ensemble, linear
        )
        target = rng.normal(scale=0.65, size=LATENT_DIM)

        oracle_costs: list[tuple[float, tuple[int, ...]]] = []
        candidate_costs: list[tuple[float, tuple[int, ...]]] = []
        linear_costs: list[tuple[float, tuple[int, ...]]] = []

        for sequence in sequences:
            truth = _true_rollout(true_state, sequence)
            oracle_costs.append(
                (float(np.sum((truth - target) ** 2)), sequence)
            )

            candidate = e_mean.copy()
            start = time.process_time()
            for action_index in sequence:
                candidate = ensemble_mean_predict(
                    ensemble,
                    candidate,
                    action_vector(action_index),
                )
            candidate_time += time.process_time() - start
            candidate_costs.append(
                (float(np.sum((candidate - target) ** 2)), sequence)
            )

            baseline = l_mean.copy()
            start = time.process_time()
            for action_index in sequence:
                baseline = linear_predict(
                    linear,
                    baseline,
                    action_vector(action_index),
                )[0]
            linear_time += time.process_time() - start
            linear_costs.append(
                (float(np.sum((baseline - target) ** 2)), sequence)
            )

        oracle_cost, _ = min(oracle_costs, key=lambda row: row[0])
        _, candidate_sequence = min(candidate_costs, key=lambda row: row[0])
        _, linear_sequence = min(linear_costs, key=lambda row: row[0])

        candidate_actual = float(
            np.sum(
                (
                    _true_rollout(true_state, candidate_sequence)
                    - target
                )
                ** 2
            )
        )
        linear_actual = float(
            np.sum(
                (
                    _true_rollout(true_state, linear_sequence)
                    - target
                )
                ** 2
            )
        )
        candidate_regrets.append(max(0.0, candidate_actual - oracle_cost))
        linear_regrets.append(max(0.0, linear_actual - oracle_cost))

    return (
        float(np.mean(candidate_regrets)),
        float(np.mean(linear_regrets)),
        candidate_time,
        linear_time,
    )


def _gaussian_nll(
    error: np.ndarray,
    covariance: np.ndarray,
) -> float:
    covariance = covariance + np.eye(LATENT_DIM) * 1e-8
    sign, logdet = np.linalg.slogdet(covariance)
    if sign <= 0:
        return float("inf")
    return float(
        0.5
        * (
            LATENT_DIM * math.log(2.0 * math.pi)
            + logdet
            + error @ np.linalg.solve(covariance, error)
        )
    )


def evaluate_calibration(
    rng: np.random.Generator,
    ensemble: EnsembleDynamics,
    *,
    steps: int = 260,
) -> tuple[float, float, float, float]:
    true_state = rng.normal(scale=0.7, size=LATENT_DIM)
    mean = np.zeros(LATENT_DIM, dtype=float)
    covariance = np.eye(LATENT_DIM, dtype=float)
    single_mean = mean.copy()
    single_covariance = covariance.copy()

    covered: list[bool] = []
    widths: list[float] = []
    nll: list[float] = []
    single_nll: list[float] = []

    for _ in range(steps):
        mask = random_mask(rng)
        observation = partial_observation(rng, true_state, mask)
        mean, covariance = kalman_measurement_update(
            mean, covariance, observation, mask
        )
        single_mean, single_covariance = kalman_measurement_update(
            single_mean, single_covariance, observation, mask
        )

        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        predicted_mean, predicted_covariance = belief_predict_ensemble(
            mean,
            covariance,
            action,
            ensemble,
            include_epistemic=True,
        )
        single_predicted_mean, single_predicted_covariance = (
            belief_predict_ensemble(
                single_mean,
                single_covariance,
                action,
                ensemble,
                include_epistemic=False,
            )
        )

        next_state = (
            hidden_step(true_state, action)
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        sd = np.sqrt(
            np.maximum(np.diag(predicted_covariance), 1e-12)
        )
        covered.extend(
            (
                np.abs(next_state - predicted_mean)
                <= 1.645 * sd
            ).tolist()
        )
        widths.extend((2.0 * 1.645 * sd).tolist())
        nll.append(
            _gaussian_nll(next_state - predicted_mean, predicted_covariance)
        )
        single_nll.append(
            _gaussian_nll(
                next_state - single_predicted_mean,
                single_predicted_covariance,
            )
        )

        mean, covariance = predicted_mean, predicted_covariance
        single_mean, single_covariance = (
            single_predicted_mean,
            single_predicted_covariance,
        )
        true_state = next_state

    return (
        float(np.mean(covered)),
        float(np.mean(widths)),
        float(np.mean(nll)),
        float(np.mean(single_nll)),
    )


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
        + np.eye(len(indices)) * OBS_VAR
    )
    return float(
        innovation @ np.linalg.solve(covariance, innovation)
        / len(indices)
    )


def detect_shift(
    rng: np.random.Generator,
    ensemble: EnsembleDynamics,
    *,
    mode: str,
) -> int | None:
    if mode not in {"none", "abrupt", "gradual"}:
        raise ValueError("invalid shift mode")

    true_state = rng.normal(scale=0.7, size=LATENT_DIM)
    mean = np.zeros(LATENT_DIM, dtype=float)
    covariance = np.eye(LATENT_DIM, dtype=float)
    scores: list[float] = []

    for step in range(MONITOR_STEPS):
        mask = random_mask(rng)
        observation = partial_observation(rng, true_state, mask)
        mean, covariance = kalman_measurement_update(
            mean, covariance, observation, mask
        )
        action = action_vector(int(rng.integers(0, ACTION_COUNT)))
        predicted_mean, predicted_covariance = belief_predict_ensemble(
            mean,
            covariance,
            action,
            ensemble,
        )

        if mode == "none" or step < SHIFT_STEP:
            coefficients = BASE_COEFFICIENTS
        elif mode == "abrupt":
            coefficients = ABRUPT_COEFFICIENTS
        else:
            coefficients = interpolate_coefficients(
                (step - SHIFT_STEP + 1) / 15.0
            )

        next_state = (
            hidden_step(
                true_state,
                action,
                coefficients=coefficients,
            )
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        next_mask = random_mask(rng)
        next_observation = partial_observation(
            rng, next_state, next_mask
        )
        scores.append(
            innovation_score(
                predicted_mean,
                predicted_covariance,
                next_observation,
                next_mask,
            )
        )
        if (
            len(scores) >= DETECTION_WINDOW
            and float(np.mean(scores[-DETECTION_WINDOW:]))
            > DETECTION_THRESHOLD
        ):
            return step

        mean, covariance = kalman_measurement_update(
            predicted_mean,
            predicted_covariance,
            next_observation,
            next_mask,
        )
        true_state = next_state

    return None


def evaluate_detection(
    rng: np.random.Generator,
    ensemble: EnsembleDynamics,
    *,
    episodes: int = 12,
) -> tuple[float, float, float, float, float]:
    abrupt_detected = 0
    gradual_detected = 0
    false_positive = 0
    abrupt_delays: list[int] = []
    gradual_delays: list[int] = []

    for _ in range(episodes):
        trigger = detect_shift(rng, ensemble, mode="abrupt")
        if trigger is not None and trigger >= SHIFT_STEP:
            abrupt_detected += 1
            abrupt_delays.append(trigger - SHIFT_STEP)

    for _ in range(episodes):
        trigger = detect_shift(rng, ensemble, mode="gradual")
        if trigger is not None and trigger >= SHIFT_STEP:
            gradual_detected += 1
            gradual_delays.append(trigger - SHIFT_STEP)

    for _ in range(episodes):
        trigger = detect_shift(rng, ensemble, mode="none")
        if trigger is not None:
            false_positive += 1

    def delay(values: list[int]) -> float:
        return float(np.mean(values)) if values else float(MONITOR_STEPS)

    return (
        abrupt_detected / episodes,
        gradual_detected / episodes,
        false_positive / episodes,
        delay(abrupt_delays),
        delay(gradual_delays),
    )


def build_models(
    seed: int,
) -> tuple[np.random.Generator, EnsembleDynamics, LinearDynamics]:
    rng = np.random.default_rng(seed)
    development = [
        collect_rollout(rng, steps=DEVELOPMENT_STEPS)
        for _ in range(DEVELOPMENT_EPISODES)
    ]
    ensemble = fit_ensemble(rng, development)
    linear = fit_linear(development)
    return rng, ensemble, linear


def evaluate_seed(seed: int) -> SeedMetrics:
    rng, ensemble, linear = build_models(seed)

    (
        candidate_rmse,
        linear_rmse,
        multistep_candidate_time,
        multistep_linear_time,
    ) = evaluate_multistep(rng, ensemble, linear)

    (
        candidate_regret,
        linear_regret,
        planning_candidate_time,
        planning_linear_time,
    ) = evaluate_planning(rng, ensemble, linear)

    coverage, width, nll, single_nll = evaluate_calibration(
        rng, ensemble
    )

    (
        abrupt_rate,
        gradual_rate,
        false_positive,
        abrupt_delay,
        gradual_delay,
    ) = evaluate_detection(rng, ensemble)

    return SeedMetrics(
        seed=seed,
        multistep_candidate_rmse=candidate_rmse,
        multistep_linear_rmse=linear_rmse,
        planning_candidate_regret=candidate_regret,
        planning_linear_regret=linear_regret,
        coverage_90=coverage,
        interval_width_90=width,
        gaussian_nll=nll,
        single_model_nll=single_nll,
        abrupt_detection_rate=abrupt_rate,
        gradual_detection_rate=gradual_rate,
        false_positive_rate=false_positive,
        abrupt_detection_delay=abrupt_delay,
        gradual_detection_delay=gradual_delay,
        candidate_compute_seconds=(
            multistep_candidate_time + planning_candidate_time
        ),
        linear_compute_seconds=(
            multistep_linear_time + planning_linear_time
        ),
    )


def summarize(rows: Iterable[SeedMetrics]) -> dict[str, float]:
    values = list(rows)
    if not values:
        raise ValueError("at least one seed required")

    def mean(name: str) -> float:
        return float(np.mean([getattr(row, name) for row in values]))

    return {
        "n_seeds": float(len(values)),
        "multistep_candidate_rmse": mean("multistep_candidate_rmse"),
        "multistep_linear_rmse": mean("multistep_linear_rmse"),
        "multistep_improvement_vs_linear": float(
            np.mean([row.multistep_improvement_vs_linear for row in values])
        ),
        "planning_candidate_regret": mean("planning_candidate_regret"),
        "planning_linear_regret": mean("planning_linear_regret"),
        "planning_improvement_vs_linear": float(
            np.mean([row.planning_improvement_vs_linear for row in values])
        ),
        "coverage_90": mean("coverage_90"),
        "interval_width_90": mean("interval_width_90"),
        "gaussian_nll": mean("gaussian_nll"),
        "single_model_nll": mean("single_model_nll"),
        "nll_gain_vs_single": float(
            np.mean([row.nll_gain_vs_single for row in values])
        ),
        "abrupt_detection_rate": mean("abrupt_detection_rate"),
        "gradual_detection_rate": mean("gradual_detection_rate"),
        "false_positive_rate": mean("false_positive_rate"),
        "abrupt_detection_delay": mean("abrupt_detection_delay"),
        "gradual_detection_delay": mean("gradual_detection_delay"),
        "candidate_compute_seconds": mean("candidate_compute_seconds"),
        "linear_compute_seconds": mean("linear_compute_seconds"),
        "compute_ratio": float(
            np.mean([row.compute_ratio for row in values])
        ),
    }


def run_block(seeds: Iterable[int]) -> dict:
    rows = [evaluate_seed(seed) for seed in seeds]
    return {
        "summary": summarize(rows),
        "seeds": [row.__dict__ for row in rows],
    }
