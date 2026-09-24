# ADI Genesis-12 preregistration — decision-aligned intervention planning

## Frozen architecture constraint

Genesis-12 is permitted to change **only intervention selection** relative to the Genesis-9 modular architecture. The Base R/D expert, L specialist, Broad fallback, protected evaluator, evidence-gated promotion logic, modular memory, and E0/E1/E2/E3 distributions are frozen. An executable architecture contract must fail closed if any frozen component fingerprint changes.

## Motivation

Genesis-9 eliminated catastrophic retention interference but transferred too weakly because the L specialist was activated only after the Base class became impossible. Genesis-10's 10:1 Bayes-factor route did not switch earlier because deterministic support gave no graded evidence before contradiction. Genesis-11 then maximized Base-versus-Specialist disagreement and was strongly worse on every reported family because class discrimination was not aligned with full causal-graph identification.

## Central hypothesis

A non-myopic adaptive experimental-design policy that minimizes **expected remaining probes to correct causal-model identification** will reduce intervention count on L-bearing worlds without sacrificing old R/D retention or Broad novelty fallback.

For posterior hypothesis state `S`, Genesis-12 evaluates:

`V(S) = 0` when one hypothesis remains, otherwise

`V(S) = min_a [1 + sum_o P(o | a, S) V(S_(a,o))]`.

The implementation memoizes posterior-support states. When the exact planning budget is exceeded, it falls back to the frozen entropy-greedy selector. The fallback is a resource control, not a new model class.

## Primary comparisons

1. Genesis-9 hard routing / original query policy.
2. Flat-growth control retained from Genesis-8.
3. Entropy-greedy query selection.
4. Genesis-11 diagnostic disagreement querying.
5. Genesis-12 expected-stopping-time planning.

All conditions must use the same hidden truths, initial hypothesis sets, priors, observation protocol, stopping rule, and evaluator.

## Resource accounting

Every run records CPU process time, peak traced Python memory, posterior states expanded, branch evaluations, and hypothesis-outcome operations. Primary performance is reported both raw and against matched planning budgets so increased compute cannot be misreported as a free sample-efficiency gain.

## Frozen gates

- E0 old R/D retention regression: <= 2% versus Genesis-9.
- E1 unseen L-6 transfer: >= 10% fewer probes versus Genesis-9.
- E2 unseen L-7 transfer: >= 10% fewer probes versus Genesis-9.
- E3 Q novelty: no >10% regression versus Genesis-9 unless preregistered as a separate stress failure.
- Positive primary claims require disjoint-seed replication.
- Architecture contract must pass before results are interpreted.
- Any evaluator/provenance/hidden-test leakage invalidates the run.

## Interpretation boundary

A pass would establish a better intervention-planning mechanism inside the causal-development slice of ADI. It would not establish open-ended intelligence, general intelligence, or autonomous self-improvement.
