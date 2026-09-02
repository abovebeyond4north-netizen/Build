# Verified Automation Policy

This project uses a conservative verified automation loop.

## What the workflow can do

The GitHub Actions workflow can:

1. Install dependencies.
2. Run deterministic quality tests.
3. Build the dashboard.
4. Run the verified improvement gate.
5. Re-run tests after any approved state update.
6. Re-build after the approved state update.
7. Open a pull request with verified learning-state updates.

## What the workflow cannot do

The workflow does not:

- Auto-merge to the default branch.
- Execute arbitrary generated code.
- Browse the web.
- Deploy automatically.
- Rewrite protected files without tests.
- Bypass human review.

## Definition of proven better

A change is considered acceptable only when:

- tests pass before the update,
- the production build passes before the update,
- the quality score is not lower than the previous best score,
- the verified gate approves the update,
- tests pass again after the update,
- the production build passes again after the update.

## Current scope

The first version updates a tracked learning-state file. It does not rewrite application logic automatically.

That is intentional. The safe path is:

1. Start with verified state tracking.
2. Add deterministic formatting and refactoring.
3. Add generated tests only when they pass mutation checks.
4. Add patch proposal branches.
5. Keep human review before merge.

## Upgrade path

Future versions can safely add:

- coverage thresholds,
- mutation testing,
- visual regression checks,
- dependency audit checks,
- generated unit tests,
- generated refactor branches,
- pull-request comments with evidence summaries,
- rollback snapshots for every accepted update.
