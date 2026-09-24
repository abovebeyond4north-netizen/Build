# ADI Genesis-13 results — learned intervention-aligned representation boundary

## Verdict

**PASS for the preregistered narrow Stage-B claim.**

Genesis-13 demonstrates that, in the controlled linear causal-world family used here, an action-aligned representation inferred from one paired intervention per action transfers a shared latent dynamics model across unseen 8-dimensional observation mixtures substantially more accurately than both pooled raw prediction and a matched-data direct few-shot observation-space baseline.

This is a validated component result, not a claim of general representation learning or a complete predictive world model.

## Provenance

- Frozen implementation head: `a9e53586858f119038b850b140937da07c3da8e7`
- GitHub Actions run: `35959025933`
- Confirmatory artifact: `genesis13-confirmatory-ledger`
- Artifact ID: `10790923308`
- Artifact SHA-256: `71300e23b30156e03f8fad6bd0a262ee7ab5c927a7faa9a4d141607491d9e378`
- Primary seeds: 5000–5019
- Disjoint replication seeds: 9000–9019
- Python 3.11 unit/architecture tests: PASS
- Python 3.12 unit/architecture tests: PASS
- Frozen confirmatory job: PASS

## Primary confirmatory block

| Metric | Result | Gate |
|---|---:|---:|
| Candidate RMSE | 0.053327 | — |
| Pooled raw RMSE | 0.282581 | — |
| Improvement vs pooled raw | **80.95%** | >=70% |
| Matched-data raw few-shot RMSE | 0.176936 | — |
| Improvement vs raw few-shot | **68.23%** | >=50% |
| Shuffled-label RMSE | 0.311622 | — |
| Shuffled / candidate error ratio | **5.90x** | >=2.5x |
| Hidden causal-structure F1 | **1.000** | >=0.95 |
| Mean max dynamics absolute error | **0.01650** | <=0.10 |
| Compression ratio | **2.667x** | >=2.5x |

All six primary gates passed.

## Disjoint-seed replication

| Metric | Result | Gate |
|---|---:|---:|
| Candidate RMSE | 0.050746 | — |
| Pooled raw RMSE | 0.275255 | — |
| Improvement vs pooled raw | **81.47%** | >=70% |
| Matched-data raw few-shot RMSE | 0.175768 | — |
| Improvement vs raw few-shot | **69.68%** | >=50% |
| Shuffled-label RMSE | 0.303172 | — |
| Shuffled / candidate error ratio | **6.03x** | >=2.5x |
| Hidden causal-structure F1 | **1.000** | >=0.95 |
| Mean max dynamics absolute error | **0.02066** | <=0.10 |
| Compression ratio | **2.667x** | >=2.5x |

All six gates replicated on the disjoint seed block.

## Causal-credit interpretation

The shuffled-action ablation preserves:
- the same intervention observations;
- the same representation rank;
- the same latent fitting procedure;
- the same evaluation worlds.

Only the association between opaque action identity and learned representation axis is cyclically permuted.

Its error is roughly six times the candidate error in both confirmatory blocks. Therefore the improvement is not explained by compression alone. Correct intervention identity carries causal credit.

The evaluator-only latent dynamics graph is recovered with F1 = 1.0 in both blocks, while the learner never receives the hidden causal graph during fitting.

## Secondary adaptation-budget sweep

The preregistered descriptive sweep exposed an important boundary.

| Paired interventions per action | Candidate RMSE | Raw few-shot RMSE | Candidate change vs raw few-shot |
|---:|---:|---:|---:|
| 1 | 0.050746 | 0.175768 | **69.68% lower error** |
| 2 | 0.040494 | 0.038441 | **6.57% higher error** |
| 4 | 0.032232 | 0.030815 | **5.37% higher error** |

The representation's advantage is therefore **low-shot sample efficiency**, not universal superiority. Once the direct observation-space learner receives two or more paired diagnostics per action, it can estimate the surface-specific mapping well enough to catch up and slightly outperform the representation method.

This boundary is retained as part of the positive result rather than treated as a failed comparison.

## Expected vs actual

Expected:
- strong transfer advantage under an extremely small diagnostic budget;
- correct intervention identity should be necessary;
- compact representation should preserve hidden causal dynamics;
- direct raw adaptation may catch up with more data.

Actual:
- the candidate exceeded every primary gate in the original confirmatory block;
- every gate replicated on disjoint seeds;
- shuffled action identity destroyed most of the gain;
- hidden causal structure was recovered exactly under the evaluator metric;
- direct raw adaptation did catch up at 2–4 intervention pairs per action.

The observed result therefore matches the preregistered mechanism and its expected boundary.

## Why Genesis-13 succeeded where Genesis-12R did not

Genesis-12R attempted to improve planning over a large raw posterior state. Its bounded lookahead became expensive and activated too late.

Genesis-13 instead reduces the state representation before planning:
1. matched interventions cancel the shared baseline transition;
2. their differences expose surface-specific action directions;
3. these directions define a compact action-aligned coordinate system;
4. dynamics learned in those coordinates become reusable across new surface mixtures;
5. the representation compresses 8 observed dimensions to 3 task-relevant coordinates.

That changes the sample complexity of adaptation rather than spending more compute searching the same raw hypothesis state.

## Architecture status

Genesis-9 remains the frozen causal-growth control.

Genesis-13 is promoted only as a **validated Stage-B representation mechanism for this controlled environment family**. It does not replace the symbolic shadow model, protected evaluator, memory system, planner, or promotion authority.

The rollback registry remains fail-closed: a candidate representation that fails learner-side validation does not replace the active version.

## Highest-value next experiment

Do not scale this linear result directly into a large neural model.

The next experiment should test whether the same principle survives when the easy assumptions are removed:

1. nonlinear and partially observed surface transformations;
2. interventions without perfect paired counterfactual resets;
3. temporally extended latent states;
4. stochastic mechanism changes;
5. multi-step prediction and calibration;
6. an uncertainty-aware latent dynamics ensemble;
7. comparison against direct recurrent prediction and a non-causal latent baseline;
8. hidden surface and mechanism shifts;
9. model-exploitation-gap measurement during imagined rollouts.

Only if the learned representation remains sufficient and intervention-grounded under those tests should ADI advance to the full predictive world-model stage.
