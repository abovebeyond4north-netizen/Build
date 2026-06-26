# Refactor Map

The learning-loop scripts now share a small utility layer instead of duplicating file, math, history, quality, and signal logic.

## Shared modules

```text
scripts/lib/json-store.mjs
scripts/lib/number-tools.mjs
scripts/lib/history-tools.mjs
scripts/lib/learning-signals.mjs
scripts/lib/command-runner.mjs
scripts/lib/dashboard-contract.mjs
scripts/lib/quality-score.mjs
```

## Refactored scripts

```text
scripts/quality-check.mjs
scripts/verified-improve.mjs
scripts/propose-improvement.mjs
scripts/revenue-learning-loop.mjs
scripts/meta-learning-loop.mjs
scripts/time-value-loop.mjs
scripts/compute-budget-loop.mjs
```

## Design rule

Every future loop should follow this structure:

```text
load state
extract signals
score or decide
write state
write report
print machine-readable summary
```

## Safety boundary

The refactor does not add external side effects. The loop still only writes local repository artifacts and relies on review before changes are merged.
