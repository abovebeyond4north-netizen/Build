# ADI Genesis-15 results — uncertainty-gated partially observed world model

## Verdict

**PASS for the preregistered narrow Genesis-15 component claim.**

The frozen Genesis-15 belief-state experiment passed every primary gate in the
original confirmatory block and in the disjoint replication block. The supported
claim is limited to the controlled 3-dimensional latent world family used here.

## Provenance

Preregistration froze the implementation at:

`4a3f9d9cdbece31472f52a298677ce44ba1907ef`

First authoritative confirmatory workflow:
- GitHub Actions run: `36071932095`
- confirmatory job: PASS
- Python 3.11 unit job: PASS
- Python 3.12 unit job: PASS
- result artifact: `genesis15-confirmatory-ledger`
- artifact ID: `10838767602`
- archive SHA-256: `29e61b8388b1627cb3cb9db1f5e60cdb755ca73864230659af4fc2ecb7ebde00`

Primary seeds: 20000–20019.
Disjoint replication seeds: 24000–24019.

The executable architecture contract was added after the first scientific result
without changing the frozen experiment or gates. The unchanged confirmatory
experiment was then rerun as an independent architecture-enforced reproduction.

Architecture-enforced reproduction:
- GitHub Actions run: `36073140451`
- Python 3.11 contract/unit job: PASS
- Python 3.12 contract/unit job: PASS
- confirmatory job: PASS
- result artifact ID: `10839112389`
- archive SHA-256: `b4d9754fbadb6f7b3b63cc0a8476b1e41175b9d02a06dfedf2ee528e8e8c8742`

After GitHub log timestamps were stripped, the complete decoded scientific result
object from the architecture-enforced reproduction was exactly identical to the
first confirmatory run.

## Confirmatory result

| Metric | Primary | Replication | Frozen gate |
|---|---:|---:|---:|
| 6-step candidate RMSE | 0.002830 | 0.002899 | — |
| raw recurrent RMSE | 0.114109 | 0.116310 | — |
| improvement vs raw | **97.51%** | **97.50%** | >=50% |
| planning-regret improvement vs raw | **99.98%** | **99.98%** | >=50% |
| empirical 90% coverage | **90.40%** | **90.20%** | 82–96% |
| mean 90% interval width | **0.08413** | **0.08420** | <=0.50 |
| hidden-shift detection rate | **99.5%** | **100%** | >=80% |
| false-positive rate | **0%** | **0%** | <=10% |
| mean detection delay | **3.74** | **3.53** steps | <=10 |
| adaptation improvement vs unadapted | **31.18%** | **31.85%** | >=10% |
| adaptation improvement vs adapted raw | **36.13%** | **35.38%** | >=10% |

Every gate passed in both blocks.

## Adaptation-budget boundary

The preregistered replication-seed sweep remained positive at every tested
post-detection budget:

| Post-detection transitions | Candidate RMSE | Adapted raw RMSE | Improvement vs unadapted | Improvement vs raw |
|---:|---:|---:|---:|---:|
| 4 | 0.097851 | 0.164848 | 24.53% | 36.86% |
| 8 | 0.089009 | 0.146707 | 32.01% | 38.00% |
| 12 | 0.083844 | 0.136306 | 35.03% | 37.63% |
| 24 | 0.077217 | 0.125729 | 38.20% | 38.20% |

Unlike Genesis-14's direct-observation adaptation boundary, the raw recurrent
control did not catch the latent adapter within this 4–24 transition range. This
does not establish that no crossover exists at larger budgets.

## Expected versus actual

Expected:
- history/belief integration should strongly outperform a short raw observation
  history under partial observability;
- calibrated predictive covariance should yield near-nominal 90% coverage;
- innovation-based uncertainty should detect the hidden dynamics change while
  abstaining on no-shift controls;
- post-alarm latent adaptation should improve shifted-world prediction;
- positive claims should reproduce on untouched seeds.

Actual:
- prediction and planning margins were much larger than the minimum gates;
- empirical interval coverage stayed close to the nominal 90% target in both
  blocks;
- shift detection was effectively complete with zero measured false positives;
- mean detection occurred about 3.5–3.7 steps after the hidden change;
- detector-gated adaptation beat both the unadapted belief model and matched raw
  recurrent adaptation;
- every primary result replicated on the disjoint seed block.

## Why the result is positive

The experiment removes one state coordinate from every observation, so a single
observation is insufficient. The belief filter integrates temporally separated
partial measurements with action-conditioned dynamics. Its covariance provides a
task-relevant uncertainty signal. When innovation statistics become inconsistent
with the frozen dynamics, adaptation is enabled; otherwise it abstains.

This directly addresses the Genesis-14 four-sample failure mode in which adapting
without an uncertainty/evidence gate could make the model worse.

## Architecture audit

The Genesis-15 PR adds only:
- the Genesis-15 experiment package;
- its tests;
- its preregistration/results;
- its dedicated CI workflow.

It does not modify Genesis-9 causal growth, Genesis-13 representation code,
Genesis-14 predictive model code, memory, promotion authority, or protected
evaluator infrastructure.

The executable contract additionally fails closed if any frozen parent component
is represented as changed. The permitted mutable surface is:
- belief filtering;
- uncertainty/shift detection;
- detector-gated residual adaptation.

## Claim boundary

This PASS does **not** establish a general predictive world model.

Important easy assumptions remain:
1. the validated Genesis-13 representation coordinates are already available;
2. dynamics remain linear and low-dimensional;
3. missingness is clean and explicitly marked by a mask;
4. process and observation noise are simple and stationary before the shift;
5. the hidden mechanism change is abrupt rather than gradual;
6. the action space is tiny and discrete;
7. the uncertainty model is analytic rather than learned;
8. the planner enumerates a small finite action-sequence space.

## Highest-value next experiment

Proceed to **Genesis-16 — learned nonlinear stochastic belief dynamics** rather
than scaling the current linear filter.

Genesis-16 should preserve Genesis-15 as control and remove the most important
remaining crutches:
- nonlinear latent transition and observation functions;
- learned recurrent belief state rather than analytic Kalman equations;
- learned uncertainty calibrated with a proper scoring rule;
- gradual, abrupt, and false mechanism shifts;
- missingness that is not always explicitly signalled;
- longer-horizon planning under uncertainty;
- ensemble or distributional uncertainty ablation;
- latent-world-model versus raw recurrent and oracle controls;
- model-exploitation-gap and compute accounting;
- untouched mechanism families and disjoint replication.

Recent world-model evidence supports this direction: DreamerV3 demonstrates the
utility of recurrent latent world models across diverse tasks; TD-MPC2 emphasizes
control-centric latent prediction; and recent calibrated world-model work shows
that uncertainty can be learned in latent space and used for out-of-distribution
detection. These are design references, not evidence for Genesis-16.
