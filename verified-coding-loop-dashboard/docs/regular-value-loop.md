# Regular Value Learning Loop

This project now has a scheduled learning workflow that runs every six hours.

## Purpose

The loop improves the project by producing reviewed proposals and learning-state updates.

It is designed to help the project become more useful as a portfolio asset, template, and service demonstration while staying safe and transparent.

## Schedule

The workflow uses this cron schedule:

```text
23 */6 * * *
```

That means it runs four times per day on the default branch.

## Loop

1. Install dependencies.
2. Run quality checks.
3. Build the app.
4. Generate a verified improvement proposal.
5. Run the verified gate.
6. Generate a value experiment proposal.
7. Re-run tests.
8. Re-build.
9. Open a pull request with state and report changes.

## Boundaries

The workflow does not:

- auto-merge,
- send outreach,
- deploy,
- make purchases,
- process money,
- access private data,
- promise income.

## Why this is safer

The system is allowed to learn and propose.

A human still reviews before anything reaches the main branch or external world.
