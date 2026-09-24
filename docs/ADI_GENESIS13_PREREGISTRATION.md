# ADI Genesis-13 preregistration — learned intervention-aligned representation boundary

## Placement in the frozen architecture

Genesis-13 targets **Stage B — Learned Representation Boundary** of the ADI v8 architecture. It does not replace Genesis-9, change the protected evaluator, alter the planner, modify memory, or change promotion rules.

The only permitted experimental degree of freedom is the representation encoder.

## Evidence motivating the experiment

Genesis-12R showed that deeper planning over the existing raw causal hypothesis state did not replicate and incurred large compute overhead. The current architecture requires a learned representation boundary before the full predictive world-model stage.

Recent research also supports this direction:

- DreamerV3 demonstrates broad utility from compact predictive latent dynamics rather than planning directly in raw observations.
- TD-MPC2 performs local planning in a learned latent world model.
- recent causal-representation work shows that interventions can identify or improve structured latent factors.
- object-centric latent-dynamics work reports benefits from structured latent state for relational reasoning.

These motivate the experiment but do not count as evidence that Genesis-13 works.

## Pilot disclosure

The mechanism and thresholds were designed using **pilot seeds only**. Pilot results are not confirmatory evidence.

No confirmatory seed listed below was used to select:
- architecture,
- intervention budget,
- ridge coefficient,
- thresholds,
- model dimensions,
- evaluation metrics.

## Central hypothesis

A representation learned from matched intervention responses can create action-aligned latent coordinates that allow one shared dynamics model to transfer across unseen observation mixtures more sample-efficiently than direct observation-space adaptation.

The learner receives:
- opaque observations,
- opaque action identities,
- paired no-op/action outcomes from the same state,
- ordinary transition traces on development worlds.

The learner never receives:
- latent state vectors,
- the hidden mixing matrices,
- the evaluator's causal graph,
- hidden evaluation outcomes before acting.

## Environment

Each world has the same hidden 3-dimensional causal dynamics but a different unseen 8-dimensional observation mixing.

The learner must therefore distinguish:
- invariant dynamics,
- surface-specific observation coordinates.

Every held-out evaluation world has a newly sampled observation mixing matrix.

## Primary treatment

For each opaque action, the learner receives **one paired intervention** against a no-op from the same hidden state.

The difference identifies one candidate action-aligned observation direction. The three directions form a learned 3-dimensional representation. A shared latent dynamics model is trained only on development worlds and reused on unseen surface mixtures.

Representation size: 3 dimensions.
Raw observation size: 8 dimensions.
Nominal compression ratio: 8/3 = 2.667x.

## Controls

1. **Pooled raw** — one observation-space dynamics model trained across development surfaces.
2. **Raw few-shot ridge** — direct observation-space adaptation using exactly the same held-out diagnostic transitions available to the candidate. Ridge alpha is frozen at 1e-3 from pilot work.
3. **Shuffled action identity** — same intervention data, same rank, same fitting procedure, but the learned action-aligned representation axes are cyclically permuted. This is the causal-credit ablation.
4. **Hidden evaluator structure check** — evaluator-only comparison between the learned latent dynamics graph and hidden causal graph. The learner never receives this score.

## Confirmatory seeds

These are frozen before first execution.

Primary confirmatory block:
- seeds 5000 through 5019 inclusive.

Disjoint replication block:
- seeds 9000 through 9019 inclusive.

Positive claims require both blocks to pass.

## Primary gates

For **each** seed block independently:

1. candidate mean prediction RMSE must be at least 70% lower than pooled raw;
2. candidate mean prediction RMSE must be at least 50% lower than matched-data raw few-shot ridge;
3. shuffled-action RMSE / candidate RMSE must be at least 2.5;
4. evaluator-only learned causal-structure F1 must be at least 0.95;
5. mean maximum absolute hidden-dynamics error must be <= 0.10;
6. compression ratio must be at least 2.5x.

Architecture-contract and rollback tests must also pass.

Failure of any primary gate prevents promotion.

## Secondary adaptation-budget sweep

After the primary one-pair test, run the same disjoint replication seeds with:
- 1 pair/action,
- 2 pairs/action,
- 4 pairs/action.

This sweep is descriptive. It is expected that direct few-shot observation models may catch up as their sample count grows. That does not invalidate a demonstrated low-shot advantage, but it defines the boundary of the representation's usefulness and must be reported.

## Representation rollback

Representation candidates are versioned. A candidate is promoted only when learner-side validation error improves by the frozen margin. A worse candidate must leave the previous active version unchanged.

## Interpretation boundary

A pass would establish a narrow result:

> intervention-grounded representation learning can improve low-shot predictive transfer across unseen surface transformations in this controlled causal world.

It would **not** establish:
- general intelligence,
- a complete world model,
- unrestricted concept discovery,
- human-level representation learning,
- successful transfer to language, vision, code, or physical robotics.

The next architectural step after a genuine replicated pass would be a richer predictive world model that consumes this representation boundary.
