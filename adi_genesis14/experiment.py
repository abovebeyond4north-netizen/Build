from __future__ import annotations

from dataclasses import dataclass
import itertools
from typing import Iterable

import numpy as np

from adi_genesis13.experiment import (
    ACTION_SCALE,
    LATENT_DIM,
    OBS_DIM,
    TRUE_A,
    TRUE_B,
    DiagnosticBundle,
    SurfaceWorld,
    TransitionBatch,
    _features,
    collect_diagnostics,
    fit_pooled_raw_dynamics,
    fit_shared_latent_dynamics,
    make_world,
    observe,
)


SHIFTED_A = TRUE_A.copy()
SHIFTED_A[1, 0] = 0.45
SHIFTED_A[2, 1] = 0.15

NOOP_ACTION = LATENT_DIM
ACTION_COUNT = LATENT_DIM + 1


@dataclass(frozen=True)
class SeedMetrics:
    seed: int
    multistep_candidate_rmse: float
    multistep_raw_rmse: float
    planning_candidate_regret: float
    planning_raw_regret: float
    exploitation_gap_candidate: float
    exploitation_gap_raw: float
    shift_unadapted_rmse: float
    shift_candidate_rmse: float
    shift_raw_fewshot_rmse: float

    @property
    def multistep_improvement_vs_raw(self) -> float:
        return 1.0 - self.multistep_candidate_rmse / self.multistep_raw_rmse

    @property
    def planning_regret_improvement_vs_raw(self) -> float:
        return 1.0 - self.planning_candidate_regret / self.planning_raw_regret

    @property
    def exploitation_gap_improvement_vs_raw(self) -> float:
        return 1.0 - self.exploitation_gap_candidate / self.exploitation_gap_raw

    @property
    def shift_improvement_vs_unadapted(self) -> float:
        return 1.0 - self.shift_candidate_rmse / self.shift_unadapted_rmse

    @property
    def shift_improvement_vs_raw_fewshot(self) -> float:
        return 1.0 - self.shift_candidate_rmse / self.shift_raw_fewshot_rmse


def action_vector(action_index: int) -> np.ndarray:
    if action_index < 0 or action_index > NOOP_ACTION:
        raise ValueError("invalid action index")
    action = np.zeros(LATENT_DIM, dtype=float)
    if action_index < LATENT_DIM:
        action[action_index] = 1.0
    return action


def collect_rollout_with_dynamics(
    rng: np.random.Generator,
    world: SurfaceWorld,
    *,
    dynamics: np.ndarray,
    steps: int,
) -> TransitionBatch:
    xs: list[np.ndarray] = []
    us: list[np.ndarray] = []
    ys: list[np.ndarray] = []

    z = rng.normal(size=LATENT_DIM)
    for _ in range(steps):
        action_index = int(rng.integers(0, ACTION_COUNT))
        action = action_vector(action_index)

        x = observe(world, z, rng)
        next_z = (
            dynamics @ z
            + TRUE_B @ action
            + rng.normal(scale=0.01, size=LATENT_DIM)
        )
        y = observe(world, next_z, rng)

        xs.append(x)
        us.append(action)
        ys.append(y)
        z = next_z

        if np.linalg.norm(z) > 4.0:
            z = rng.normal(size=LATENT_DIM)

    return TransitionBatch(
        x=np.stack(xs, axis=0),
        action=np.stack(us, axis=0),
        y=np.stack(ys, axis=0),
    )


def _latent_step(z: np.ndarray, action: np.ndarray, weights: np.ndarray) -> np.ndarray:
    row = np.concatenate([z, action, np.ones(1, dtype=float)])
    return row @ weights


def _raw_step(x: np.ndarray, action: np.ndarray, weights: np.ndarray) -> np.ndarray:
    row = np.concatenate([x, action, np.ones(1, dtype=float)])
    return row @ weights


def _true_step(z: np.ndarray, action: np.ndarray, dynamics: np.ndarray) -> np.ndarray:
    return dynamics @ z + TRUE_B @ action


def _execute_true(
    z0: np.ndarray,
    sequence: tuple[int, ...],
    *,
    dynamics: np.ndarray,
) -> np.ndarray:
    z = z0.copy()
    for action_index in sequence:
        z = _true_step(z, action_vector(action_index), dynamics)
    return z


def _all_sequences(horizon: int) -> Iterable[tuple[int, ...]]:
    return itertools.product(range(ACTION_COUNT), repeat=horizon)


def _candidate_plan(
    x0: np.ndarray,
    target_x: np.ndarray,
    diagnostic: DiagnosticBundle,
    latent_weights: np.ndarray,
    *,
    horizon: int,
) -> tuple[float, tuple[int, ...], np.ndarray]:
    encoder = np.linalg.pinv(diagnostic.estimated_mixing)
    z0 = encoder @ x0
    target_z = encoder @ target_x

    best: tuple[float, tuple[int, ...], np.ndarray] | None = None
    for sequence in _all_sequences(horizon):
        z = z0.copy()
        for action_index in sequence:
            z = _latent_step(z, action_vector(action_index), latent_weights)
        learner_cost = float(np.sum((z - target_z) ** 2))
        if best is None or learner_cost < best[0]:
            best = (learner_cost, sequence, z)

    assert best is not None
    return best


def _raw_plan(
    x0: np.ndarray,
    target_x: np.ndarray,
    raw_weights: np.ndarray,
    *,
    horizon: int,
) -> tuple[float, tuple[int, ...], np.ndarray]:
    best: tuple[float, tuple[int, ...], np.ndarray] | None = None
    for sequence in _all_sequences(horizon):
        x = x0.copy()
        for action_index in sequence:
            x = _raw_step(x, action_vector(action_index), raw_weights)
        learner_cost = float(np.sum((x - target_x) ** 2))
        if best is None or learner_cost < best[0]:
            best = (learner_cost, sequence, x)

    assert best is not None
    return best


def _oracle_plan(
    z0: np.ndarray,
    target_z: np.ndarray,
    *,
    horizon: int,
    dynamics: np.ndarray,
) -> tuple[float, tuple[int, ...]]:
    best: tuple[float, tuple[int, ...]] | None = None
    for sequence in _all_sequences(horizon):
        final_z = _execute_true(z0, sequence, dynamics=dynamics)
        cost = float(np.sum((final_z - target_z) ** 2))
        if best is None or cost < best[0]:
            best = (cost, sequence)
    assert best is not None
    return best


def fit_latent_residual(
    base_weights: np.ndarray,
    diagnostic: DiagnosticBundle,
    adaptation: TransitionBatch,
    *,
    ridge_alpha: float = 1e-2,
) -> np.ndarray:
    """Adapt only latent state dynamics and bias; preserve action effects."""

    encoder = np.linalg.pinv(diagnostic.estimated_mixing)
    z = adaptation.x @ encoder.T
    next_z = adaptation.y @ encoder.T

    base_prediction = _features(z, adaptation.action) @ base_weights
    residual = next_z - base_prediction

    design = np.concatenate(
        [z, np.ones((z.shape[0], 1), dtype=float)],
        axis=1,
    )
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[-1, -1] = 0.0
    delta = np.linalg.solve(
        design.T @ design + ridge_alpha * penalty,
        design.T @ residual,
    )

    adapted = base_weights.copy()
    adapted[:LATENT_DIM, :] += delta[:LATENT_DIM, :]
    adapted[-1, :] += delta[-1, :]
    return adapted


def fit_raw_shift_adapter(
    adaptation: TransitionBatch,
    *,
    ridge_alpha: float = 1e-2,
) -> np.ndarray:
    design = _features(adaptation.x, adaptation.action)
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[-1, -1] = 0.0
    return np.linalg.solve(
        design.T @ design + ridge_alpha * penalty,
        design.T @ adaptation.y,
    )


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def evaluate_seed(
    seed: int,
    *,
    shift_adaptation_steps: int = 8,
    development_worlds: int = 5,
    evaluation_worlds: int = 4,
    development_steps: int = 500,
    multistep_cases_per_world: int = 15,
    planning_cases_per_world: int = 20,
    multistep_horizon: int = 5,
    planning_horizon: int = 3,
) -> SeedMetrics:
    rng = np.random.default_rng(seed)

    latent_development: list[tuple[DiagnosticBundle, TransitionBatch]] = []
    raw_development: list[TransitionBatch] = []

    for _ in range(development_worlds):
        world = make_world(rng)
        diagnostic = collect_diagnostics(rng, world, pairs_per_action=1)
        rollout = collect_rollout_with_dynamics(
            rng,
            world,
            dynamics=TRUE_A,
            steps=development_steps,
        )
        latent_development.append((diagnostic, rollout))
        raw_development.append(rollout)

    latent_weights = fit_shared_latent_dynamics(latent_development)
    raw_weights = fit_pooled_raw_dynamics(raw_development)

    multistep_candidate: list[float] = []
    multistep_raw: list[float] = []
    candidate_regret: list[float] = []
    raw_regret: list[float] = []
    candidate_gap: list[float] = []
    raw_gap: list[float] = []
    shift_unadapted: list[float] = []
    shift_candidate: list[float] = []
    shift_raw: list[float] = []

    for _ in range(evaluation_worlds):
        world = make_world(rng)
        diagnostic = collect_diagnostics(rng, world, pairs_per_action=1)
        encoder = np.linalg.pinv(diagnostic.estimated_mixing)
        true_decoder = np.linalg.pinv(world.mixing)

        for _ in range(multistep_cases_per_world):
            z0 = rng.normal(scale=0.7, size=LATENT_DIM)
            x0 = observe(world, z0, rng)
            sequence = tuple(
                int(rng.integers(0, ACTION_COUNT))
                for _ in range(multistep_horizon)
            )

            true_z = _execute_true(z0, sequence, dynamics=TRUE_A)
            true_x = world.mixing @ true_z

            z_hat = encoder @ x0
            x_hat = x0.copy()
            for action_index in sequence:
                action = action_vector(action_index)
                z_hat = _latent_step(z_hat, action, latent_weights)
                x_hat = _raw_step(x_hat, action, raw_weights)

            candidate_x = diagnostic.estimated_mixing @ z_hat
            multistep_candidate.append(_rmse(candidate_x, true_x))
            multistep_raw.append(_rmse(x_hat, true_x))

        for _ in range(planning_cases_per_world):
            z0 = rng.normal(scale=0.8, size=LATENT_DIM)
            target_z = rng.normal(scale=0.8, size=LATENT_DIM)
            x0 = observe(world, z0, rng)
            target_x = observe(world, target_z, rng)

            _, candidate_sequence, candidate_predicted_z = _candidate_plan(
                x0,
                target_x,
                diagnostic,
                latent_weights,
                horizon=planning_horizon,
            )
            _, raw_sequence, raw_predicted_x = _raw_plan(
                x0,
                target_x,
                raw_weights,
                horizon=planning_horizon,
            )
            oracle_cost, _ = _oracle_plan(
                z0,
                target_z,
                horizon=planning_horizon,
                dynamics=TRUE_A,
            )

            candidate_final = _execute_true(
                z0,
                candidate_sequence,
                dynamics=TRUE_A,
            )
            raw_final = _execute_true(
                z0,
                raw_sequence,
                dynamics=TRUE_A,
            )

            candidate_actual_cost = float(
                np.sum((candidate_final - target_z) ** 2)
            )
            raw_actual_cost = float(np.sum((raw_final - target_z) ** 2))

            candidate_regret.append(candidate_actual_cost - oracle_cost)
            raw_regret.append(raw_actual_cost - oracle_cost)

            # Evaluator-only model-exploitation gap in hidden latent units.
            candidate_predicted_x = (
                diagnostic.estimated_mixing @ candidate_predicted_z
            )
            candidate_predicted_hidden_z = true_decoder @ candidate_predicted_x
            raw_predicted_hidden_z = true_decoder @ raw_predicted_x

            candidate_predicted_cost = float(
                np.sum((candidate_predicted_hidden_z - target_z) ** 2)
            )
            raw_predicted_cost = float(
                np.sum((raw_predicted_hidden_z - target_z) ** 2)
            )

            candidate_gap.append(
                abs(candidate_predicted_cost - candidate_actual_cost)
            )
            raw_gap.append(abs(raw_predicted_cost - raw_actual_cost))

        adaptation = collect_rollout_with_dynamics(
            rng,
            world,
            dynamics=SHIFTED_A,
            steps=shift_adaptation_steps,
        )
        adapted_latent = fit_latent_residual(
            latent_weights,
            diagnostic,
            adaptation,
        )
        adapted_raw = fit_raw_shift_adapter(adaptation)

        shifted_test = collect_rollout_with_dynamics(
            rng,
            world,
            dynamics=SHIFTED_A,
            steps=150,
        )
        test_z = shifted_test.x @ encoder.T

        unadapted_prediction = (
            _features(test_z, shifted_test.action)
            @ latent_weights
            @ diagnostic.estimated_mixing.T
        )
        candidate_prediction = (
            _features(test_z, shifted_test.action)
            @ adapted_latent
            @ diagnostic.estimated_mixing.T
        )
        raw_prediction = _features(
            shifted_test.x,
            shifted_test.action,
        ) @ adapted_raw

        shift_unadapted.append(
            _rmse(unadapted_prediction, shifted_test.y)
        )
        shift_candidate.append(
            _rmse(candidate_prediction, shifted_test.y)
        )
        shift_raw.append(_rmse(raw_prediction, shifted_test.y))

    return SeedMetrics(
        seed=seed,
        multistep_candidate_rmse=float(np.mean(multistep_candidate)),
        multistep_raw_rmse=float(np.mean(multistep_raw)),
        planning_candidate_regret=float(np.mean(candidate_regret)),
        planning_raw_regret=float(np.mean(raw_regret)),
        exploitation_gap_candidate=float(np.mean(candidate_gap)),
        exploitation_gap_raw=float(np.mean(raw_gap)),
        shift_unadapted_rmse=float(np.mean(shift_unadapted)),
        shift_candidate_rmse=float(np.mean(shift_candidate)),
        shift_raw_fewshot_rmse=float(np.mean(shift_raw)),
    )


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
            np.mean([row.multistep_improvement_vs_raw for row in values])
        ),
        "planning_candidate_regret": mean("planning_candidate_regret"),
        "planning_raw_regret": mean("planning_raw_regret"),
        "planning_regret_improvement_vs_raw": float(
            np.mean(
                [row.planning_regret_improvement_vs_raw for row in values]
            )
        ),
        "exploitation_gap_candidate": mean("exploitation_gap_candidate"),
        "exploitation_gap_raw": mean("exploitation_gap_raw"),
        "exploitation_gap_improvement_vs_raw": float(
            np.mean(
                [row.exploitation_gap_improvement_vs_raw for row in values]
            )
        ),
        "shift_unadapted_rmse": mean("shift_unadapted_rmse"),
        "shift_candidate_rmse": mean("shift_candidate_rmse"),
        "shift_raw_fewshot_rmse": mean("shift_raw_fewshot_rmse"),
        "shift_improvement_vs_unadapted": float(
            np.mean([row.shift_improvement_vs_unadapted for row in values])
        ),
        "shift_improvement_vs_raw_fewshot": float(
            np.mean(
                [row.shift_improvement_vs_raw_fewshot for row in values]
            )
        ),
    }


def run_block(
    seeds: Iterable[int],
    *,
    shift_adaptation_steps: int = 8,
) -> dict:
    rows = [
        evaluate_seed(
            seed,
            shift_adaptation_steps=shift_adaptation_steps,
        )
        for seed in seeds
    ]
    return {
        "summary": summarize(rows),
        "seeds": [row.__dict__ for row in rows],
    }
