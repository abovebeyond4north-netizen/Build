# Implementation Planner

This layer turns a selected improvement target into a concrete work plan.

## Inputs

```text
general improvement report
efficiency optimizer report
latest verified proposal
```

## Output

```text
selected target
work phases
acceptance checks
rollback notes
risk controls
next review step
```

## Planning rule

```text
Smallest useful patch first.
Checks and build before review.
Rollback notes before approval.
```

## Purpose

A recommendation is not enough.

The system needs a plan that a human can review, test, and revert safely.
