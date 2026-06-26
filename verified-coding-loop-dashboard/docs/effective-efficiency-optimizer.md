# Effective Efficiency Optimizer

This layer ranks weak subprocesses by practical return.

## Scoring factors

```text
impact
low effort
verification strength
low risk
credit preservation
```

## Input

The optimizer reads the process focus report and compute credit state.

## Output

It writes an efficiency report with:

```text
selected improvement target
ranked candidates
score breakdown
next focused step
```

## Purpose

The system should not improve everything equally.

It should choose the smallest focused improvement that is likely to produce the highest verified gain.

## Practical rule

```text
High impact + low effort + strong verification + low risk = best next move.
```
