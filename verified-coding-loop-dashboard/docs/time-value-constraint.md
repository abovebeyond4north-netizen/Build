# Time-Value Constraint

This layer treats time as a scarce resource.

The project now keeps an internal score ledger that rises when the verified loop produces useful evidence.

## What gets scored

The loop gives internal score credit for:

- a benchmark passing,
- a production build passing,
- a preserved or improved quality score,
- a meta-learning measurement,
- a selected value experiment,
- a new skill signal.

## Virtual raise rule

The loop also tracks a virtual rate.

The virtual rate increases when verified progress happens:

- passed benchmark: +0.25 virtual rate units,
- skill signal acquired: +0.15 virtual rate units.

The rate is capped so the score cannot grow without limit.

## Why this matters

This forces the loop to ask:

> Did this iteration earn its time?

A slow loop with no useful evidence should not be treated as progress.

A loop that passes tests, learns a skill, and creates a useful proposal receives a higher internal score.

## Hard boundary

This is not real-world money movement.

The score is for prioritization, motivation, and opportunity-cost tracking only.

Human review is required before any real-world offer, price, budget, contract, or outside action changes.
