# ConceptLab Zero — P0/P1/P2/P3/P4/P5 Measurement Harness

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

## P2 composition, revision, and restart persistence

P2 adds three gates without changing P0 or P1:

- **D4 composition:** two primitives are learned independently, frozen into
  capsules, and then combined by learning a Boolean composition operator from
  separate composition examples. The D4 holdout uses new numeric ranges and new
  encodings. The full composition must beat either primitive alone and every
  wrong composition operator.
- **Contradiction-driven revision:** an intentionally ambiguous concept first
  selects `distance_ge:4`. Fresh evidence containing direct contradictions at
  distances 4 and 5 must trigger revision to `distance_ge:6`. An unrelated
  stored concept must retain both its digest and held-out accuracy.
- **Restart persistence:** only content-addressed concept/composition capsules
  are persisted. A new Python process reloads the store and must recover the
  primitive, revised, and composite capabilities on fresh evaluation suites.
  Raw discovery episodes are not stored.

P2 gates require D4 accuracy >= 0.90, D4 gain over the strongest control >=
0.15, revised-concept holdout >= 0.95, unaffected-concept retention >= 0.95,
all fresh-process scores >= 0.90, zero composition train/holdout collisions,
and zero persisted raw-episode artifacts. P2 still does not unlock CLG-1.

## P3 withheld-predicate symbolic synthesis

P3 removes one important P0 scaffold: the four target predicates are not supplied
as named rules. Instead the learner receives a bounded program-construction
language containing integer linear expressions, optional absolute value, modular
equality, equality, and threshold comparison. It enumerates candidate programs,
scores them on discovery episodes, and uses a minimum-description-length tie
break.

The targets include modulo-3, weighted-linear, absolute-sum, and modulo-5
relations that are absent from the P0 rule list. P3 compares the synthesized
program against the original P0 learner on the same held-out D5 suites. Programs
are content-addressed and reloaded by a fresh Python process.

P3 gates require discovery accuracy >= 0.98, D5 accuracy >= 0.95, improvement
over the P0 control >= 0.20 for every target, compression >= 4x, zero structural
train/holdout collisions, and fresh-process accuracy >= 0.95. This is bounded
symbolic synthesis from supplied operators, not unrestricted program invention;
CLG-1 remains locked.

## P4 adaptive observation interfaces

P4 keeps the P3 weighted-linear controller frozen and changes the observation
problem. Each new domain contains 6 or 8 numeric slots with four or more
distractors. The two controller inputs occur at different ordered positions in
each layout.

The learner receives 32 labeled support examples for the new observation space
and searches only for an ordered projection into the frozen controller. It then
faces 160 held-out examples on a wider numeric range. Controls include default
first/last slots, the reversed learned projection, and a prior domain adapter
when dimensionally valid.

The learned controller's content digest must remain unchanged during adaptation.
Adapters are persisted independently and a fresh Python process must reload both
controller and adapter and recover the capability.

P4 gates require support accuracy >= 0.95, D6 accuracy >= 0.95, gain over the
strongest non-adapted control >= 0.20, zero support/holdout signal-pair overlap,
fresh-process accuracy >= 0.95, exact adapter identification, and an unchanged
controller digest. This removes the fixed pair-selection rule, but a generic
numeric flattener and bounded ordered-slot adapter search are still supplied.

## P5 raw token and latent-slot discovery

P5 removes another P4 scaffold: observations are now raw heterogeneous strings,
and the actual controller inputs are not emitted as ordinary integers. Four
independently seeded task families use opaque signed lexical encodings in bases
2, 10, 16, and 36, different raw layouts, distractor token families, unrelated
numeric metadata, while a single frozen P3 controller is held constant across
all four families so representation learning is the only experimental variable.

The learner receives only raw labeled support examples plus the frozen controller.
It searches a bounded lexical-decoder grammar and ordered latent-token slots,
then persists the selected feature capsule. The old P4 generic numeric flattener,
wrong slot pairs, reversed slots, and the runner-up tokenizer hypothesis are
evaluated as controls.

P5v1 mixed two controller semantics; its first run showed that a partially
ablated feature could remain above 0.80 simply because one input of a weighted
threshold controller was predictive. P5v1 was therefore invalidated as a
representation-isolation experiment. P5v2 holds the controller constant while
keeping the original acceptance thresholds unchanged.

A sealed P5 manifest commits family definitions and thresholds before results
are produced. P5 gates require support accuracy >= 0.95, D7 held-out accuracy >=
0.95, gain over the strongest control >= 0.20, zero support/holdout signal-pair
collisions, exact decoder/slot recovery, fresh-process accuracy >= 0.95, and
unchanged frozen-controller digests.

P5 therefore demonstrates token-decoder and latent-slot discovery from raw text
inside a bounded character-level decoder grammar. It does not establish
unrestricted tokenization or representation invention.

## Run

```bash
cd conceptlab_zero
python -m unittest discover -s tests
python scripts/validate.py
python scripts/validate_p1.py
python scripts/validate_p2.py
python scripts/validate_p3.py
python scripts/validate_p4.py
python scripts/validate_p5.py
```

The validation run creates `.conceptlab_ci/` containing:

- `manifest.commitment`
- `sealed_manifest.revealed.json`
- `evidence_ledger.jsonl`
- `campaign_result.json`
- `p1_evidence_ledger.jsonl`
- `p1_campaign_result.json`
- `p2_evidence_ledger.jsonl`
- `p2_campaign_result.json`
- `p2_restart_receipt.json`
- `concept_store/` (content-addressed capsules only)
- `p3_evidence_ledger.jsonl`
- `p3_campaign_result.json`
- `p3_restart_receipt.json`
- `symbolic_program_store/`
- `p4_evidence_ledger.jsonl`
- `p4_campaign_result.json`
- `p4_restart_receipt.json`
- `adapter_store/`
- `p5_manifest.commitment`
- `p5_manifest.revealed.json`
- `p5_evidence_ledger.jsonl`
- `p5_campaign_result.json`
- `p5_restart_receipt.json`
- `raw_feature_store/`

GitHub Actions reruns the P0, P1, P2, P3, P4, and P5 campaigns on Python 3.11 and 3.12 and uploads the Python 3.12 evidence bundle.

## Claim boundary

A passing P0 campaign means the learner transformed examples into a compact reusable rule that survived the specified representation changes and causal controls **within the supplied grammar and numeric-pair extractor**.

P3 reduces the rule-vocabulary scaffold, P4 learns ordered observation adapters, and P5 learns lexical decoders plus latent token slots directly from raw heterogeneous strings. The decoder/search language is still bounded and hand-specified. Broader families with learned character/substructure primitives, self-generated hypotheses, and protected cross-family evaluation are still required before a CLG-1 campaign can be justified.
