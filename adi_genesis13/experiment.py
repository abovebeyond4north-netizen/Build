from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import numpy as np


LATENT_DIM = 3
OBS_DIM = 8
ACTION_SCALE = 0.6
OBS_NOISE = 0.02
PROCESS_NOISE = 0.01

TRUE_A = np.array(
    [
        [0.65, 0.00, 0.00],
        [0.25, 0.55, 0.00],
        [0.00, 0.30, 0.50],
    ],
    dtype=float,
)
TRUE_B = np.eye(LATENT_DIM, dtype=float) * ACTION_SCALE


@dataclass(frozen=True)
class SurfaceWorld:
    mixing: np.ndarray


@dataclass(frozen=True)
class TransitionBatch:
    x: np.ndarray
    action: np.ndarray
    y: np.ndarray


@dataclass(frozen=True)
class DiagnosticBundle:
    estimated_mixing: np.ndarray
    raw_adaptation: TransitionBatch


@dataclass(frozen=True)
class SeedMetrics:
    seed: int
    pairs_per_action: int
    candidate_rmse: float
    pooled_raw_rmse: float
    raw_fewshot_rmse: float
    shuffled_label_rmse: float
    structure_f1: float
    max_dynamics_abs_error: float
    compression_ratio: float

    @property
    def improvement_vs_pooled(self) -> float:
        return 1.0 - self.candidate_rmse / self.pooled_raw_rmse

    @property
    def improvement_vs_fewshot(self) -> float:
        return 1.0 - self.candidate_rmse / self.raw_fewshot_rmse

    @property
    def shuffled_to_candidate_ratio(self) -> float:
        return self.shuffled_label_rmse / self.candidate_rmse


def _random_mixing(rng: np.random.Generator) -> np.ndarray:
    q, _ = np.linalg.qr(rng.normal(size=(OBS_DIM, LATENT_DIM)))
    scales = rng.uniform(0.7, 1.5, size=LATENT_DIM)
    return q * scales


def make_world(rng: np.random.Generator) -> SurfaceWorld:
    return SurfaceWorld(mixing=_random_mixing(rng))


def observe(
    world: SurfaceWorld,
    z: np.ndarray,
    rng: np.random.Generator,
    noise: float = OBS_NOISE,
) -> np.ndarray:
    return world.mixing @ z + rng.normal(scale=noise, size=OBS_DIM)


def collect_diagnostics(
    rng: np.random.Generator,
    world: SurfaceWorld,
    *,
    pairs_per_action: int,
) -> DiagnosticBundle:
    """Estimate action-aligned representation axes from paired interventions.

    Each opaque action is evaluated against a no-op from the same latent state.
    The learner sees observations and action identity only; it never receives the
    latent state, the mixing matrix, or the evaluator's causal graph.
    """

    if pairs_per_action < 1:
        raise ValueError("pairs_per_action must be >= 1")

    diffs: list[list[np.ndarray]] = [[] for _ in range(LATENT_DIM)]
    xs: list[np.ndarray] = []
    us: list[np.ndarray] = []
    ys: list[np.ndarray] = []

    for action_index in range(LATENT_DIM):
        for _ in range(pairs_per_action):
            z = rng.normal(scale=0.7, size=LATENT_DIM)
            x = observe(world, z, rng)

            noop_next = TRUE_A @ z
            action_vec = np.zeros(LATENT_DIM, dtype=float)
            action_vec[action_index] = 1.0
            action_next = TRUE_A @ z + TRUE_B @ action_vec

            y_noop = observe(world, noop_next, rng)
            y_action = observe(world, action_next, rng)

            xs.append(x)
            us.append(np.zeros(LATENT_DIM, dtype=float))
            ys.append(y_noop)

            xs.append(x)
            us.append(action_vec)
            ys.append(y_action)

            diffs[action_index].append((y_action - y_noop) / ACTION_SCALE)

    estimated_mixing = np.stack(
        [np.mean(np.stack(axis_diffs, axis=0), axis=0) for axis_diffs in diffs],
        axis=1,
    )

    return DiagnosticBundle(
        estimated_mixing=estimated_mixing,
        raw_adaptation=TransitionBatch(
            x=np.stack(xs, axis=0),
            action=np.stack(us, axis=0),
            y=np.stack(ys, axis=0),
        ),
    )


def collect_rollout(
    rng: np.random.Generator,
    world: SurfaceWorld,
    *,
    steps: int,
) -> TransitionBatch:
    xs: list[np.ndarray] = []
    us: list[np.ndarray] = []
    ys: list[np.ndarray] = []

    z = rng.normal(size=LATENT_DIM)
    for _ in range(steps):
        action_index = int(rng.integers(0, LATENT_DIM + 1))
        action_vec = np.zeros(LATENT_DIM, dtype=float)
        if action_index < LATENT_DIM:
            action_vec[action_index] = 1.0

        x = observe(world, z, rng)
        next_z = (
            TRUE_A @ z
            + TRUE_B @ action_vec
            + rng.normal(scale=PROCESS_NOISE, size=LATENT_DIM)
        )
        y = observe(world, next_z, rng)

        xs.append(x)
        us.append(action_vec)
        ys.append(y)
        z = next_z

        if np.linalg.norm(z) > 4.0:
            z = rng.normal(size=LATENT_DIM)

    return TransitionBatch(
        x=np.stack(xs, axis=0),
        action=np.stack(us, axis=0),
        y=np.stack(ys, axis=0),
    )


def _features(state: np.ndarray, action: np.ndarray) -> np.ndarray:
    return np.concatenate(
        [state, action, np.ones((state.shape[0], 1), dtype=float)],
        axis=1,
    )


def fit_shared_latent_dynamics(
    development: Iterable[tuple[DiagnosticBundle, TransitionBatch]],
) -> np.ndarray:
    design: list[np.ndarray] = []
    targets: list[np.ndarray] = []

    for diagnostic, batch in development:
        encoder = np.linalg.pinv(diagnostic.estimated_mixing)
        z = batch.x @ encoder.T
        next_z = batch.y @ encoder.T
        design.append(_features(z, batch.action))
        targets.append(next_z)

    return np.linalg.lstsq(
        np.concatenate(design, axis=0),
        np.concatenate(targets, axis=0),
        rcond=1e-6,
    )[0]


def fit_pooled_raw_dynamics(
    development: Iterable[TransitionBatch],
) -> np.ndarray:
    design: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for batch in development:
        design.append(_features(batch.x, batch.action))
        targets.append(batch.y)
    return np.linalg.lstsq(
        np.concatenate(design, axis=0),
        np.concatenate(targets, axis=0),
        rcond=1e-6,
    )[0]


def fit_raw_fewshot(
    diagnostics: TransitionBatch,
    *,
    ridge_alpha: float = 1e-3,
) -> np.ndarray:
    """Matched-data direct observation-space adaptation baseline.

    ridge_alpha=1e-3 was selected on pilot seeds only and is frozen before the
    confirmatory seed blocks.
    """

    design = _features(diagnostics.x, diagnostics.action)
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[-1, -1] = 0.0
    return np.linalg.solve(
        design.T @ design + ridge_alpha * penalty,
        design.T @ diagnostics.y,
    )


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def _structure_f1(latent_weights: np.ndarray) -> tuple[float, float]:
    learned_a = latent_weights[:LATENT_DIM, :].T
    true_edges = np.abs(TRUE_A) > 0.05
    learned_edges = np.abs(learned_a) > 0.08
    tp = int(np.sum(true_edges & learned_edges))
    fp = int(np.sum(~true_edges & learned_edges))
    fn = int(np.sum(true_edges & ~learned_edges))
    denominator = 2 * tp + fp + fn
    f1 = 1.0 if denominator == 0 else (2 * tp) / denominator
    max_abs_error = float(np.max(np.abs(learned_a - TRUE_A)))
    return float(f1), max_abs_error


def evaluate_seed(
    seed: int,
    *,
    pairs_per_action: int = 1,
    development_worlds: int = 5,
    evaluation_worlds: int = 4,
    development_steps: int = 300,
    evaluation_steps: int = 150,
) -> SeedMetrics:
    rng = np.random.default_rng(seed)

    latent_development: list[tuple[DiagnosticBundle, TransitionBatch]] = []
    raw_development: list[TransitionBatch] = []

    for _ in range(development_worlds):
        world = make_world(rng)
        diagnostic = collect_diagnostics(
            rng,
            world,
            pairs_per_action=pairs_per_action,
        )
        rollout = collect_rollout(rng, world, steps=development_steps)
        latent_development.append((diagnostic, rollout))
        raw_development.append(rollout)

    latent_weights = fit_shared_latent_dynamics(latent_development)
    pooled_raw_weights = fit_pooled_raw_dynamics(raw_development)
    structure_f1, max_abs_error = _structure_f1(latent_weights)

    candidate_errors: list[float] = []
    pooled_errors: list[float] = []
    fewshot_errors: list[float] = []
    shuffled_errors: list[float] = []

    for _ in range(evaluation_worlds):
        world = make_world(rng)
        diagnostic = collect_diagnostics(
            rng,
            world,
            pairs_per_action=pairs_per_action,
        )
        evaluation = collect_rollout(rng, world, steps=evaluation_steps)

        encoder = np.linalg.pinv(diagnostic.estimated_mixing)
        z = evaluation.x @ encoder.T
        predicted_z = _features(z, evaluation.action) @ latent_weights
        candidate_prediction = predicted_z @ diagnostic.estimated_mixing.T
        candidate_errors.append(_rmse(candidate_prediction, evaluation.y))

        pooled_prediction = _features(
            evaluation.x,
            evaluation.action,
        ) @ pooled_raw_weights
        pooled_errors.append(_rmse(pooled_prediction, evaluation.y))

        fewshot_weights = fit_raw_fewshot(diagnostic.raw_adaptation)
        fewshot_prediction = _features(
            evaluation.x,
            evaluation.action,
        ) @ fewshot_weights
        fewshot_errors.append(_rmse(fewshot_prediction, evaluation.y))

        # Causal-credit ablation: preserve exactly the same intervention data and
        # representation rank but rotate opaque action identities.
        permutation = np.roll(np.arange(LATENT_DIM), 1)
        shuffled_mixing = diagnostic.estimated_mixing[:, permutation]
        shuffled_encoder = np.linalg.pinv(shuffled_mixing)
        shuffled_z = evaluation.x @ shuffled_encoder.T
        shuffled_predicted_z = _features(
            shuffled_z,
            evaluation.action,
        ) @ latent_weights
        shuffled_prediction = shuffled_predicted_z @ shuffled_mixing.T
        shuffled_errors.append(_rmse(shuffled_prediction, evaluation.y))

    return SeedMetrics(
        seed=seed,
        pairs_per_action=pairs_per_action,
        candidate_rmse=float(np.mean(candidate_errors)),
        pooled_raw_rmse=float(np.mean(pooled_errors)),
        raw_fewshot_rmse=float(np.mean(fewshot_errors)),
        shuffled_label_rmse=float(np.mean(shuffled_errors)),
        structure_f1=structure_f1,
        max_dynamics_abs_error=max_abs_error,
        compression_ratio=OBS_DIM / LATENT_DIM,
    )


def summarize(metrics: Iterable[SeedMetrics]) -> dict[str, float]:
    rows = list(metrics)
    if not rows:
        raise ValueError("at least one seed result is required")

    def mean(name: str) -> float:
        return float(np.mean([getattr(row, name) for row in rows]))

    return {
        "n_seeds": float(len(rows)),
        "candidate_rmse": mean("candidate_rmse"),
        "pooled_raw_rmse": mean("pooled_raw_rmse"),
        "raw_fewshot_rmse": mean("raw_fewshot_rmse"),
        "shuffled_label_rmse": mean("shuffled_label_rmse"),
        "improvement_vs_pooled": float(
            np.mean([row.improvement_vs_pooled for row in rows])
        ),
        "improvement_vs_fewshot": float(
            np.mean([row.improvement_vs_fewshot for row in rows])
        ),
        "shuffled_to_candidate_ratio": float(
            np.mean([row.shuffled_to_candidate_ratio for row in rows])
        ),
        "structure_f1": mean("structure_f1"),
        "max_dynamics_abs_error": mean("max_dynamics_abs_error"),
        "compression_ratio": mean("compression_ratio"),
    }


def run_block(seeds: Iterable[int], *, pairs_per_action: int = 1) -> dict:
    rows = [
        evaluate_seed(seed, pairs_per_action=pairs_per_action)
        for seed in seeds
    ]
    return {
        "summary": summarize(rows),
        "seeds": [
            {
                "seed": row.seed,
                "candidate_rmse": row.candidate_rmse,
                "pooled_raw_rmse": row.pooled_raw_rmse,
                "raw_fewshot_rmse": row.raw_fewshot_rmse,
                "shuffled_label_rmse": row.shuffled_label_rmse,
                "structure_f1": row.structure_f1,
                "max_dynamics_abs_error": row.max_dynamics_abs_error,
            }
            for row in rows
        ],
    }


def write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
