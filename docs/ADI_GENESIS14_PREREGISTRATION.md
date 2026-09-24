# ADI Genesis-14 preregistration — predictive world-model readiness

## Architecture placement

Genesis-14 is the Stage-B -> Stage-D bridge in the frozen ADI v8 architecture.

Genesis-13 established a narrow, replicated result: an intervention-aligned latent
representation can improve low-shot transfer across unseen linear observation
mixtures. Genesis-14 asks a harder question:

> Is that frozen representation sufficient to support useful downstream predictive
> behavior that it was not trained to optimize?

Genesis-14 does **not** change the Genesis-13 representation mechanism. It keeps the
protected evaluator, Genesis-9 causal control, memory system, promotion rules, and
train/evaluation split frozen.

The only permitted experimental components are:
- the latent dynamics model;
- a low-data latent residual adapter used after a hidden dynamics shift.

An executable architecture contract fails closed if any frozen component changes.

## Motivation

Genesis-12R failed because deeper planning over a large raw causal hypothesis state
was expensive, late-acting, and non-replicating. Genesis-13 instead reduced the state
representation before planning and obtained a replicated low-shot transfer result.

The next architectural requirement is not a larger planner. It is evidence that the
learned state is sufficient for:
1. multi-step prediction;
2. goal-directed planning;
3. calibrated model use rather than model exploitation;
4. low-data adaptation after a hidden mechanism change.

This follows the project rule that a learned representation must be tested on
downstream functions not used to construct it.

## Pilot disclosure

Pilot seeds only were used to choose:
- task horizons;
- hidden dynamics shift magnitude;
- latent residual-adaptation form;
- regularization;
- primary thresholds.

Pilot seeds are not confirmatory evidence and are not included in either frozen
confirmation block.

No seed in either confirmatory block below has been evaluated before this
preregistration commit.

## Frozen environment

Latent state dimensionality: 3.
Observed dimensionality: 8.
Observation surface: a newly sampled linear mixing in every world.
Action set: three opaque interventions plus no-op.

Development worlds use the Genesis-13 hidden dynamics.

Hidden-shift evaluation changes two latent causal coefficients:
- A[1,0]: 0.25 -> 0.45
- A[2,1]: 0.30 -> 0.15

The learner is not told those values.

## Frozen representation

Each evaluation world receives the Genesis-13 diagnostic budget:
- one paired intervention per action against no-op from the same latent state.

The resulting 3-dimensional action-aligned representation is frozen for all
Genesis-14 downstream comparisons.

The learner never receives:
- the true latent state;
- the true observation mixing;
- the true latent dynamics;
- evaluator-only oracle plans.

## Downstream tests

### T1 — five-step predictive rollout

From an unseen surface world:
1. sample a hidden initial state;
2. sample five actions;
3. predict the final observation after all five actions.

Primary metric:
- final-observation RMSE.

Candidate:
- frozen Genesis-13 encoder + shared latent dynamics.

Control:
- pooled observation-space dynamics trained over the same development worlds.

### T2 — horizon-three planning

For each unseen surface world:
1. sample hidden initial and target states;
2. enumerate the same finite action-sequence set for every model;
3. let each model select the sequence minimizing its own predicted target error;
4. execute the chosen sequence in the hidden evaluator.

Primary metric:
- regret versus the evaluator-only oracle sequence.

The learner cannot inspect the oracle during planning.

### T3 — model-exploitation gap

For the sequence chosen by each learned model, compare:
- model-predicted final target cost;
- evaluator-realized final target cost.

Primary metric:
- absolute prediction/realization gap in evaluator latent units.

The evaluator-only inverse surface transform is used only for scoring and never
returned to the learner.

### T4 — low-data hidden-dynamics adaptation

After the latent dynamics changes, both candidate and direct raw control receive
exactly eight ordinary transition samples from the shifted world.

Candidate:
- keep the Genesis-13 representation fixed;
- fit a regularized residual only to latent state-dynamics rows and bias;
- keep learned action effects frozen.

Matched raw control:
- fit a regularized direct observation-space transition model on the same eight
  shifted transitions.

Additional control:
- unadapted latent dynamics.

Primary metric:
- one-step RMSE on fresh shifted-world transitions.

## Confirmatory seeds

These are frozen before first confirmatory execution.

Primary confirmatory block:
- seeds 12000 through 12019 inclusive.

Disjoint replication block:
- seeds 16000 through 16019 inclusive.

Positive claims require **both** blocks to pass every primary gate.

## Frozen primary gates

For each seed block independently:

1. five-step prediction error improvement versus pooled raw >= 80%;
2. planning-regret improvement versus pooled raw >= 80%;
3. candidate mean planning regret <= 0.05;
4. model-exploitation-gap improvement versus pooled raw >= 75%;
5. shifted-world latent residual adaptation improves over unadapted latent dynamics
   by >= 15%;
6. shifted-world latent residual adaptation improves over matched-data raw few-shot
   adaptation by >= 30%.

Failure of any gate prevents promotion.

## Secondary shift-data sweep

After the frozen primary eight-transition comparison, run the same replication seed
block with shift-adaptation budgets:

- 4 transitions;
- 8 transitions;
- 12 transitions;
- 24 transitions.

This sweep is descriptive and does not alter the primary verdict.

Pilot evidence suggests that the direct raw model may catch up or overtake the latent
residual adapter as shift data increases. If that occurs, it must be reported as a
boundary of the method, not hidden by the primary low-data result.

## Resource and fairness rules

- same development worlds within each seed;
- same unseen evaluation worlds within each seed;
- same action-sequence search space in planning;
- same hidden target states;
- same shift transitions for candidate and raw adaptation;
- same evaluator and stopping rules;
- no tuning on confirmatory outputs;
- no evaluator truth enters learner fitting;
- all confirmatory outputs written to an immutable CI artifact.

## Interpretation boundary

A replicated pass would establish only:

> the validated Genesis-13 representation is sufficient for useful multi-step
> prediction, planning, and low-data dynamics adaptation in this controlled
> latent-linear world family.

It would not establish:
- a general world model;
- robust nonlinear representation learning;
- language or visual understanding;
- open-ended intelligence;
- human-level planning;
- unrestricted autonomous self-improvement.

A pass authorizes the next experiment to make the world model itself harder:
partial observability, stochastic/nonlinear dynamics, imperfect interventions,
uncertainty ensembles, and longer imagined rollouts.
