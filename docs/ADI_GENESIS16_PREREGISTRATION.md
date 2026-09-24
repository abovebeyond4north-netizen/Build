# ADI Genesis-16 preregistration — nonlinear stochastic dynamics and epistemic uncertainty

Status: **FROZEN BEFORE CONFIRMATORY EXECUTION**

## Architecture placement

Genesis-16 advances one component at a time from the validated Genesis-15 control.

Genesis-15 remains the active parent for:
- the validated Genesis-13 representation coordinates;
- the partial-observation interface;
- the measurement-update semantics;
- the bounded action interface;
- the protected evaluator boundary;
- the causal-growth control, memory, promotion, and split infrastructure.

Genesis-16 does **not** yet replace the analytic measurement update with a learned
recurrent belief encoder. It isolates the next causal question:

> Under the same partially observed state interface, does a learned nonlinear
> stochastic dynamics ensemble improve multi-step prediction and planning over a
> linear dynamics control, while adding calibrated epistemic uncertainty that is
> useful under hidden mechanism shifts?

The permitted experimental surface is limited to:
1. the nonlinear latent dynamics predictor;
2. bootstrap-ensemble epistemic uncertainty;
3. the uncertainty/innovation shift detector.

An executable architecture contract fails closed if protected evaluator,
representation, partial-observation interface, measurement update, causal control,
memory, promotion rules, data split, or planning protocol are represented as changed.

## Frozen implementation

Scientific implementation head before this preregistration:

`1b0783ec76294b074f1edd4c730e26992142bdbf`

The confirmatory seeds and promotion gates are already encoded in
`adi_genesis16/confirmatory.py` at this head.

No confirmatory seed listed below has been executed before this preregistration.

## Development-pilot disclosure

Development only; not confirmatory evidence.

Final pilot workflow:
- run: `36074375978`
- seeds: 61, 193, 487, 809, 1231, 1777.

Pilot summary after the final causal-ablation correction:
- eight-step RMSE improvement vs linear: 19.96%;
- planning-regret improvement vs linear: 93.55%;
- empirical 90% coverage: 89.94%;
- mean 90% interval width: 0.1043;
- proper-score NLL gain from epistemic covariance, holding the ensemble mean fixed:
  +0.1787 nats-equivalent score units;
- abrupt-shift detection: 100%;
- gradual-shift detection: 98.61%;
- false-positive rate on no-shift episodes: 0%;
- abrupt detection delay: 4.60 steps;
- gradual detection delay: 13.28 steps;
- timed prediction/planning inference ratio vs linear control: 1.63x.

Two pilot defects were fixed before freezing:
1. ensemble-member inference was vectorized and mean-only rollouts stopped computing
   unused covariance; scientific metrics were unchanged while timed inference cost
   fell from ~22.5x to ~1.6x the linear control;
2. the uncertainty ablation was corrected so candidate and ablation use the **same
   ensemble predictive mean**. Only epistemic covariance differs. The original
   single-member comparison was therefore not used for confirmation.

No hidden-confirmatory result was used in either repair.

## Frozen environment

Latent dimension: 3.
Action set: three bounded interventions plus no-op.
Observation interface: Genesis-15 partial observation; exactly one latent coordinate
is hidden per observation and the mask is explicit.
Observation noise standard deviation: 0.04.
Process noise standard deviation: 0.025.

The base hidden transition is nonlinear:

`TRUE_A @ state + TRUE_B @ action + nonlinear_term(state)`

The nonlinear term contains smooth sine, cross-product, and quadratic components.

Development and normal evaluation use fixed base nonlinear coefficients.

Shift tests include:
- **abrupt** change to all four nonlinear coefficients after step 35;
- **gradual** interpolation to the same changed coefficients over 15 steps;
- **no-shift** negative-control episodes.

The learner never receives the hidden coefficient values, hidden shift type, or
hidden shift time.

## Candidate

A seven-member bootstrap ensemble is fitted on development transitions using a fixed
nonlinear feature basis and ridge regression.

The predictive mean is the ensemble mean.
Predictive covariance combines:
- bootstrapped-member disagreement (epistemic);
- fitted residual covariance (aleatoric);
- propagated belief covariance.

The same ensemble mean is used in the no-epistemic ablation.

This is a learned nonlinear dynamics model over a fixed feature basis. It is **not**
a claim of neural representation discovery.

## Controls and ablations

### C1 — linear dynamics control

A ridge-fitted linear latent dynamics model receives the same development
transitions, action interface, partial observations, measurement update, evaluation
states, action sequences, and planning targets.

### C2 — no-epistemic uncertainty ablation

Uses exactly the candidate's ensemble predictive mean and mean residual covariance
but removes member-disagreement covariance.

Primary causal metric:
- Gaussian negative-log-likelihood gain of the full ensemble over this ablation.

Because the predictive means are identical, this comparison attributes the scoring
difference to the uncertainty representation rather than to ensemble averaging.

### C3 — no-shift negative control

The hidden dynamics never change. Any alarm is a false positive.

### C4 — evaluator-only oracle planning

The evaluator computes the best finite action sequence only for regret scoring. The
candidate and linear control cannot inspect oracle costs during selection.

## Primary tests

### T1 — eight-step prediction

Both candidate and linear control roll forward eight actions from matched belief
states.

Metric:
- final latent-state RMSE.

### T2 — horizon-four planning

Both models search the identical finite action-sequence set and choose the sequence
minimizing their own predicted target error.

Metric:
- regret versus evaluator-only oracle execution.

### T3 — calibrated uncertainty

Evaluate one-step predictive distributions under normal nonlinear dynamics.

Metrics:
- empirical 90% interval coverage;
- mean interval width;
- Gaussian NLL;
- NLL gain over the no-epistemic ablation.

### T4 — hidden mechanism shifts

Use the candidate's innovation statistic with a frozen five-step window and
threshold 3.6.

Metrics:
- abrupt detection rate and delay;
- gradual detection rate and delay;
- no-shift false-positive rate.

### T5 — resource accounting

Time only the matched model-inference work used for T1 and T2:
- candidate nonlinear mean prediction;
- linear-control prediction.

Training, environment generation, evaluator oracle work, and calibration/detection
bookkeeping are not included in this ratio and must not be described as total system
compute.

## Confirmatory populations

Frozen before first execution:

Primary:
- seeds 30000 through 30019 inclusive.

Disjoint replication:
- seeds 34000 through 34019 inclusive.

Positive claims require **both** blocks to pass every primary gate.

## Frozen promotion gates

For each seed block independently:

1. eight-step RMSE improvement vs linear >= 12%;
2. planning-regret improvement vs linear >= 75%;
3. candidate mean planning regret <= 0.002;
4. empirical 90% coverage in [0.84, 0.96];
5. mean 90% interval width <= 0.18;
6. Gaussian-NLL gain vs same-mean no-epistemic ablation >= 0.08;
7. abrupt-shift detection rate >= 0.90;
8. gradual-shift detection rate >= 0.80;
9. no-shift false-positive rate <= 0.10;
10. mean abrupt detection delay <= 8 steps;
11. mean gradual detection delay <= 18 steps;
12. timed prediction/planning inference ratio vs linear <= 4.0x;
13. all reported metrics finite.

Failure of any gate prevents promotion.

## Fairness and leakage rules

- same development data within each seed for candidate and linear control;
- same observation interface and measurement update;
- same hidden initial states and action sequences for matched prediction comparisons;
- same planning search space and targets;
- no evaluator-only coefficients or oracle costs enter learner fitting;
- no confirmatory tuning;
- confirmation output must be preserved as a CI artifact;
- positive interpretation requires disjoint-seed replication.

## Expected result and failure interpretation

Expected from pilot:
- moderate multi-step prediction gain;
- larger planning gain;
- near-nominal predictive coverage;
- positive proper-score contribution from epistemic covariance;
- robust abrupt and gradual shift detection with low false alarms;
- inference overhead small enough to justify the nonlinear model.

A failure is informative:
- prediction failure means the fixed nonlinear model does not generalize reliably;
- NLL failure means ensemble disagreement does not add calibrated uncertainty beyond
  residual noise;
- shift-detection failure means the uncertainty signal is not operationally useful;
- compute failure means the gain is too expensive under this implementation even if
  task metrics improve.

No gate will be relaxed after confirmation.

## Interpretation boundary

A replicated PASS would establish only:

> in this controlled low-dimensional nonlinear stochastic family, a bootstrap
> nonlinear latent dynamics model improves predictive/control utility over the
> matched linear control, and member-disagreement uncertainty adds measurable
> calibrated information under the frozen partial-observation interface.

It would **not** establish:
- a learned recurrent belief representation;
- robustness to raw pixels, language, audio, or unstructured observations;
- general world modeling;
- open-ended intelligence;
- human-level intelligence;
- unrestricted recursive self-improvement.

A genuine PASS authorizes the next experiment to replace the analytic belief update
with a learned recurrent belief state while keeping Genesis-16 as the dynamics and
uncertainty control.
