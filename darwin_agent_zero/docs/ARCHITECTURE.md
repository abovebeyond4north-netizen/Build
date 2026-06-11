# Darwin Agent Zero Architecture

## Purpose

Darwin Agent Zero is a bounded research prototype for self-improving coding agents. It turns the universal loop of evolution into a local software system:

```text
variation -> evaluation -> selection -> memory -> new variation
```

## Core loop

1. **Self-instruction** creates improvement tasks from the current champion and memory.
2. **Mutation** generates candidate tool expressions.
3. **Oracle judgment** evaluates each candidate with benchmarks, safety scanning, and decision-matrix scoring.
4. **Archive storage** records every candidate as a lineage event.
5. **Knowledge bank** preserves useful observations across generations.
6. **Champion writing** exports the best accepted tool to `champion.py`.

## Modules

| Module | Role |
|---|---|
| `evolver.py` | Main orchestration loop. |
| `oracle.py` | Empirical Gödel proof gate. |
| `decision_matrix.py` | Multi-factor candidate scoring. |
| `archive.py` | Append-only evolutionary lineage. |
| `memory.py` | Persistent knowledge bank. |
| `self_instruction.py` | Generates local improvement pressure. |
| `tools.py` | Agent Zero style tool registry. |
| `safety.py` | Static safety checks for candidate tools. |
| `benchmark.py` | Deterministic local benchmark harness. |

## Safety boundaries

The first version evolves constrained arithmetic expressions instead of arbitrary executable programs. This preserves the self-improvement pattern while avoiding unsafe behavior.

Current boundaries:

- No network access.
- No shell access.
- No file access by candidates.
- No unrestricted dynamic code execution.
- No credential handling.
- No autonomous deployment.

## Upgrade path

The next safe upgrades are:

1. Add more benchmark families.
2. Add MAP-Elites archive bins.
3. Add AST edit distance for better novelty scoring.
4. Add a human-reviewed code-diff candidate mode.
5. Add optional LLM mutation provider behind explicit configuration.
