# Roadmap

## Phase 1 — Safe seed engine

Status: started.

- Bounded expression evolution.
- Empirical Gödel oracle.
- Decision matrix scoring.
- Evolution archive.
- Knowledge bank.
- Tool registry.
- CI smoke tests.

## Phase 2 — Broader tool evolution

- Add benchmark suites for string transforms, list transforms, and simple parsers.
- Add typed candidate interfaces.
- Add curriculum raising when champion scores stay high.
- Add code complexity metrics.

## Phase 3 — Quality-diversity archive

- Add MAP-Elites bins.
- Track behaviour signatures.
- Preserve stepping stones, not just top scores.
- Add lineage visualization.

## Phase 4 — Human-reviewed code diffs

- Generate patch proposals.
- Run test and safety gates.
- Open GitHub issues or PRs for review.
- Never auto-merge self-modifications.

## Phase 5 — Optional model-assisted mutation

- Add provider interface.
- Require explicit user-supplied API configuration.
- Keep all generated code inside the same oracle gate.
- Log prompts, diffs, and benchmark evidence.

## Phase 6 — Agent network

- Multiple specialists evolve candidate tools.
- Debate and peer review before oracle scoring.
- Shared memory with provenance.
- External deployment only by human approval.
