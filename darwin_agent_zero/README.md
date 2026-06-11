# Darwin Agent Zero

A **safe, local-first Darwinian Gödel machine prototype** for self-instructed code evolution, decision-matrix intelligence, and bounded tool creation.

This is not an unbounded autonomous system. It is a research scaffold that evolves small Python “tool candidates” inside a sandbox, scores them with a multi-factor decision matrix, archives useful variants, and rolls back weak or unsafe changes.

## What it does

Darwin Agent Zero runs the loop:

```text
observe -> self-instruct -> mutate/tool-build -> sandbox-test -> score -> archive -> learn
```

Core principles:

- **Self-coded:** proposes and writes small tool variants as Python source.
- **Self-sufficient:** runs locally with the Python standard library.
- **Self-instructed:** generates tasks from benchmark failures and archive gaps.
- **Self-evolving:** keeps an evolutionary archive of variants and selects parents for mutation.
- **Decision-matrix intelligence:** scores changes across correctness, efficiency, novelty, safety, simplicity, and generalization.
- **Gödel-style gate:** treats test evidence as an empirical proof before accepting a modification.
- **Agent Zero substrate:** tool registry, memory archive, planner/evaluator loop, and safe tool execution.

## Install

```bash
cd darwin_agent_zero
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
```

No API key is required.

## Run a demo evolution

```bash
dgm-zero run --generations 12 --population 6 --workspace .dgm_workspace
```

Expected output:

- `archive.jsonl` — lineage records and scores.
- `champion.py` — best accepted tool candidate.
- `evolution_report.json` — run summary.

## Run tests

```bash
python -m unittest discover -s tests
```

## Safety design

The prototype deliberately avoids unrestricted self-modification:

- Candidates run in isolated temporary workspaces.
- Execution uses subprocess timeouts.
- Candidate code is statically screened for dangerous imports and calls.
- The accepted champion is only written after passing the oracle gate.
- It does not access network, credentials, the OS shell, or the user’s files.

## Roadmap

1. Add MAP-Elites style archive bins.
2. Add optional LLM mutation provider behind explicit user configuration.
3. Add richer synthetic benchmark generation.
4. Add vector memory for semantic retrieval.
5. Add GitHub issue/PR automation for human-reviewed upgrades.
