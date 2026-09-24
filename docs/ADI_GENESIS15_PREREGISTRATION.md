# ADI Genesis-15 preregistration — uncertainty-gated partially observed world model

Status: FROZEN BEFORE CONFIRMATORY EXECUTION

## Architecture boundary

Genesis-15 tests the next Stage-B -> Stage-D boundary without modifying the protected evaluator, Genesis-9 causal-growth control, Genesis-13 representation result, or Genesis-14 evidence. The mutable surface is limited to the partially observed belief/world-model experiment and its uncertainty-gated residual adapter.

The learner never receives evaluator-only true latent state during evaluation, the hidden shift time, or the hidden dynamics matrix. Adaptation data are collected only after the learner-side detector fires. A pre-shift alarm invalidates adaptation for that episode.

## Hypothesis

A compact belief state with explicit predictive uncertainty can preserve useful dynamics under partial observability, detect hidden mechanism changes with low false-alarm rate, and gate low-data adaptation more reliably than an observation-history recurrent baseline.

## Frozen implementation

Candidate branch head before this preregistration: `4a3f9d9cdbece31472f52a298677ce44ba1907ef`.

Fixed mechanisms:
- exactly two of three latent coordinates observed at each step;
- observation noise = 0.04; process noise = 0.02;
- belief update = Kalman measurement/prediction recursion;
- raw control = ridge-fitted 3-step observation+mask recurrent linear predictor;
- detector window = 5; normalized innovation threshold = 4.0;
- hidden shift begins at step 30;
- primary post-detection adaptation budget = 12 transitions;
- adapter changes latent state-dynamics rows only; action effects and representation stay frozen.

## Confirmatory populations

Primary seeds: 20000–20019.
Disjoint replication seeds: 24000–24019.

No gate may be changed after either confirmatory block is observed.

## Primary gates

Both blocks must independently satisfy every gate:

1. six-step candidate RMSE improvement vs raw recurrent >= 50%;
2. planning-regret improvement vs raw recurrent >= 50%;
3. empirical 90% predictive-interval coverage in [0.82, 0.96];
4. mean 90% interval width <= 0.50;
5. hidden-shift detection rate >= 0.80;
6. false-positive rate <= 0.10;
7. mean post-shift detection delay <= 10 steps;
8. detector-gated adaptation improvement vs unadapted belief model >= 10%;
9. detector-gated adaptation improvement vs matched-data adapted raw recurrent >= 10%.

A block fails if any metric is non-finite.

## Causal / failure controls

The false-shift episodes are mandatory negative controls. Adaptation is not permitted before a detector alarm. The alarm-causing transition is not reused as an adaptation target. A secondary adaptation-budget sweep at 4, 8, 12, and 24 post-detection transitions is descriptive only and cannot rescue a failed primary gate.

## Expected boundary

The uncertainty gate should abstain when evidence is insufficient. More raw surface-specific data may eventually let the flexible raw recurrent control catch up or overtake the compact latent adapter, as in Genesis-14. Such a crossover is a measured boundary, not a reason to retune the primary gate.

## Promotion rule

PASS permits promotion only as a validated component for this controlled partially observed family. It does not establish a general world model, open-ended intelligence, or human-level general intelligence. FAIL preserves Genesis-14 as the active validated frontier and triggers failure analysis before any redesign.
