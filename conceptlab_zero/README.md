# ConceptLab Zero — P0/P1 Measurement Harness

ConceptLab Zero is the first executable measurement substrate for the Recursive-AI Concept Discovery Protocol.

It tests a deliberately narrow question:

> Can a learner infer a compact structural rule from examples, preserve that rule under hostile surface changes, and beat fresh-clone controls on far-domain tests without train/test leakage?

The current learner is intentionally limited to a hand-authored grammar of small boolean relations over two extracted numeric values. Passing this lab therefore **does not** establish open-ended intelligence, unrestricted invention, general intelligence, consciousness, or CLG-1. It establishes that the measurement machinery can detect reusable structure inside a known hypothesis class.

## P0 protocol

Each campaign:

1. constructs an evaluator-only manifest containing opaque hidden principles, domain splits, seeds, and fixed gates;
2. writes only the manifest SHA-256 commitment before evaluation;
3. generates balanced discovery episodes in two training surfaces;
4. lets a deterministic rule inducer select a capsule from its bounded grammar;
5. evaluates fresh D0/D1/D2/D3 suites under progressively different surfaces;
6. runs A–E-style isolation controls:
   - episodes only,
   - capsule only,
   - episodes plus capsule,
   - irrelevant capsule,
   - complexity-matched sham capsule;
7. checks exact train/evaluation digest separation;
8. measures capsule compression against the discovery episodes;
9. appends each result to a hash-chained evidence ledger;
10. reveals the sealed manifest and verifies its commitment after evaluation.

Current P0 gates require:

- train accuracy = 1.00;
- D0 surface-randomized accuracy >= 0.90;
- D1 unseen-structure accuracy >= 0.85;
- D2 alternate-encoding accuracy >= 0.85;
- D3 far-surface accuracy >= 0.85;
- D3 advantage over the strongest irrelevant/sham control >= 0.10;
- false-transfer rate <= 0.10;
- compression >= 4x;
- exact hidden-principle recovery;
- zero exact train/evaluation collisions.

## P1 causal utility

P1 is a separate evidence layer bound to the verified P0 manifest. It does not
retroactively change the P0 thresholds.

For every recovered principle it creates 64 evaluator-owned interventions from a
numeric range outside the P0 discovery distribution. Half of the interventions
change the hidden principle's outcome and half preserve it. The capsule must
predict both the post-intervention outcome and whether the intervention changes
the outcome.

P1 also performs an explicit whole-capsule ablation. The learned capsule is
compared with the stronger of an irrelevant learned principle and a
complexity-matched sham on a fresh balanced D3-style suite. The attributable
ablation fraction is:

```text
(capsule_score - ablated_score) / (capsule_score - 0.5)
```

P1 gates are fixed at counterfactual accuracy >= 0.80 and ablation fraction >=
0.50. Passing P1 still leaves CLG-1 locked.

## Run

```bash
cd conceptlab_zero
python -m unittest discover -s tests
python scripts/validate.py
python scripts/validate_p1.py
```

The validation run creates `.conceptlab_ci/` containing:

- `manifest.commitment`
- `sealed_manifest.revealed.json`
- `evidence_ledger.jsonl`
- `campaign_result.json`
- `p1_evidence_ledger.jsonl`
- `p1_campaign_result.json`

GitHub Actions reruns the P0 and P1 campaigns on Python 3.11 and 3.12 and uploads the Python 3.12 evidence bundle.

## Claim boundary

A passing P0 campaign means the learner transformed examples into a compact reusable rule that survived the specified representation changes and causal controls **within the supplied grammar and numeric-pair extractor**.

It does not establish learned representation invention because the extraction mechanism and rule vocabulary are provided. The next stages should remove progressively more of that scaffolding: learned adapters, withheld rule families, contradiction-driven revision, composition, restart persistence, and eventually the preregistered multi-family CLG-1 campaign.
