# ADI Genesis-14 results — predictive world-model readiness

## Verdict

**PASS for the preregistered narrow Stage-B -> Stage-D readiness claim.**

With the validated Genesis-13 representation frozen, a shared latent dynamics model
supports substantially better multi-step prediction, planning, and model calibration
than a pooled observation-space dynamics model in this controlled world family. A
low-data latent residual adapter also improves adaptation after a hidden dynamics
shift at the preregistered eight-transition budget.

This does not establish a general world model. It establishes that the validated
representation is useful for downstream predictive functions under the tested
assumptions.

## Provenance

Frozen experimental head before first confirmatory execution:

`224b20ad70a6b08f1c8fcb16799ad7a9a5daec0c`

Authoritative pull-request execution:
- GitHub Actions run: `35959799569`
- confirmatory artifact: `genesis14-confirmatory-ledger`
- artifact ID: `10791059123`
- archive digest: `sha256:df848237d6d3691bd10fad3e082cd7bc23c50a0e8e47a71cf137acdeb7720ffe`

Independent duplicate push execution:
- GitHub Actions run: `35959787431`
- artifact ID: `10791673755`
- archive digest: `sha256:601fba2e8a0530e8288035dcbf3773989e7f304c5147ff2374204271dfd5e94c`

The complete decoded scientific result objects from the two runs are byte-for-byte
identical after removing GitHub log timestamps. The ZIP digests differ because the
archives contain run-specific packaging metadata; archive-byte identity was not used
as a reproducibility criterion.

Primary seeds: 12000–12019.
Disjoint replication seeds: 16000–16019.

Python 3.11 architecture/pilot tests: PASS.
Python 3.12 architecture/pilot tests: PASS.
Primary confirmatory block: PASS.
Disjoint replication block: PASS.

## Primary confirmatory block

| Metric | Candidate | Raw / control | Relative result | Frozen gate |
|---|---:|---:|---:|---:|
| 5-step final RMSE | 0.045394 | 0.464980 | **90.18% lower** | >=80% |
| Planning regret | 0.005560 | 1.360479 | **99.59% lower** | >=80%; candidate <=0.05 |
| Model-exploitation gap | 0.061532 | 1.362775 | **95.38% lower** | >=75% |
| Shift RMSE, 8 samples | 0.060189 | unadapted 0.083869 | **27.69% lower** | >=15% |
| Shift RMSE, 8 samples | 0.060189 | raw few-shot 0.097777 | **33.93% lower** | >=30% |

All six primary gates passed.

## Disjoint-seed replication

| Metric | Candidate | Raw / control | Relative result | Frozen gate |
|---|---:|---:|---:|---:|
| 5-step final RMSE | 0.046305 | 0.477218 | **90.19% lower** | >=80% |
| Planning regret | 0.004846 | 1.169123 | **99.54% lower** | >=80%; candidate <=0.05 |
| Model-exploitation gap | 0.059551 | 1.285718 | **95.10% lower** | >=75% |
| Shift RMSE, 8 samples | 0.061863 | unadapted 0.085456 | **27.13% lower** | >=15% |
| Shift RMSE, 8 samples | 0.061863 | raw few-shot 0.097636 | **34.10% lower** | >=30% |

Every gate replicated.

## What the downstream tests establish

### Multi-step predictive sufficiency

The Genesis-13 representation was learned from intervention-aligned diagnostics, not
from the five-step evaluation objective. Reusing the shared latent dynamics across
new observation mixtures reduced final-observation prediction error by about 90% in
both untouched seed blocks.

This is evidence that the representation preserves dynamics-relevant information
rather than only reconstructing its diagnostic intervention task.

### Planning usefulness

The candidate and raw model searched exactly the same finite action-sequence space.
The evaluator then executed the selected sequence in the hidden true dynamics.

Candidate regret versus the evaluator-only oracle was about 0.005 in both blocks,
versus roughly 1.17–1.36 for pooled raw prediction. The result therefore reflects
useful model structure for action selection rather than only low one-step loss.

### Model-exploitation gap

A learned model can be dangerous as a planner if it predicts attractive outcomes
that fail when executed. The candidate's prediction/realization gap was about 95%
smaller than the raw control in both blocks.

This is still a small deterministic environment; it is not evidence that arbitrary
long imagined rollouts are calibrated.

## Hidden-dynamics adaptation

At the frozen eight-transition adaptation budget, the latent residual adapter:
- improves over the unadapted latent model by 27.69% / 27.13%;
- improves over a matched-data raw few-shot adapter by 33.93% / 34.10%.

Only latent state-dynamics rows and bias are adapted. Action-effect rows and the
Genesis-13 representation stay frozen.

This provides narrow evidence that a compact representation can make low-data
mechanism adaptation easier.

## Secondary adaptation-budget boundary

Replication-seed sweep:

| Shift transitions | Latent residual RMSE | Raw few-shot RMSE | Unadapted RMSE | Interpretation |
|---:|---:|---:|---:|---|
| 4 | 0.089539 | 0.263711 | 0.083257 | latent beats raw, but adaptation is too data-poor and slightly harms the frozen base |
| 8 | 0.061863 | 0.097636 | 0.085456 | **latent adapter is best** |
| 12 | 0.055797 | 0.054124 | 0.085467 | raw catches up and is ~3% lower RMSE |
| 24 | 0.051645 | 0.027982 | 0.083864 | raw decisively overtakes latent adapter |

The positive adaptation claim is therefore specifically **low-data**. With enough
surface-specific transitions, the more flexible raw model becomes superior.

The four-transition result is equally important: an adapter should sometimes abstain.
A future world-model layer needs uncertainty and an adaptation gate rather than
always modifying itself when a tiny amount of shift evidence appears.

## Expected versus actual

Expected:
- strong multi-step and planning benefit if Genesis-13 captures dynamics-sufficient
  state;
- lower model-exploitation gap than pooled raw prediction;
- a low-data region where latent residual adaptation is more sample-efficient;
- raw adaptation eventually catches up as data increases.

Actual:
- all predictive/planning gates passed with large margins in both seed blocks;
- the complete result object reproduced identically in two independent CI executions;
- the eight-sample latent adaptation advantage replicated;
- raw adaptation caught up at 12 samples and strongly won by 24;
- at four samples, adaptation should have abstained.

The result is therefore stronger than a one-metric prediction win while still having
clear, measured limits.

## Architecture verdict

Genesis-14 is architecture-conformant:
- Genesis-13 representation remained frozen;
- Genesis-9 causal control remained frozen;
- evaluator, hidden generator, memory, promotion rules, and train/eval split remained
  outside the mutable experimental surface;
- only latent dynamics and residual adaptation were experimental.

The validated component may be merged as research infrastructure. It should not yet
replace a general ADI runtime world model.

## Highest-value next experiment

Advance to **Genesis-15 — uncertainty-gated partially observed world model** rather
than increasing model size.

The next experiment should simultaneously remove several easy assumptions:

1. partial observability: one observation is insufficient to recover current state;
2. nonlinear/stochastic latent dynamics;
3. imperfect/non-reset interventions rather than matched counterfactual pairs;
4. learned recurrent belief state from short histories;
5. an ensemble or distributional uncertainty head;
6. adaptation only when uncertainty/evidence crosses a preregistered gate;
7. hidden mechanism changes and false-shift controls;
8. longer rollouts with calibration measured by horizon;
9. planning under uncertainty compared with reactive, raw recurrent, and oracle
   controls;
10. explicit abstention scoring so the four-sample Genesis-14 failure mode cannot be
    hidden by always adapting.

A pass should require gains in prediction, planning, calibration, shift detection,
and adaptation while preserving the protected evaluator and rollback boundary.
