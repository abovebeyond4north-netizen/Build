# Darwin Agent Zero

A **safe, local-first research platform for bounded code evolution and verifiable capability acquisition**.

Darwin Agent Zero now contains two related experimental loops:

1. the original arithmetic-expression evolution loop, which evolves and scores small candidate tools; and
2. a general capability-acquisition protocol that can synthesize pure Python skills from training examples, select them with validation cases, certify one finalist on a sealed holdout suite, version verified skills, and compare later attempts against the installed baseline.

This is not an unbounded autonomous system or evidence of AGI. The capability layer is deliberately narrow, inspectable, and fail-closed so that measured improvement can be distinguished from benchmark leakage or unsafe execution.

## General capability acquisition

The new loop is:

```text
objective/spec
    -> construct or load train/validation/holdout tasks
    -> measure installed baseline
    -> create explicit improvement tasks
    -> synthesize candidate pure functions from TRAINING ONLY
    -> sandbox-test all candidates on training
    -> validate the strongest survivors
    -> select one finalist
    -> evaluate that finalist ONCE on holdout
    -> require measurable gain over the installed skill
    -> content-address + version the verified skill
    -> persist evidence and memory
```

### Natural-language objectives

Supported objective families can be compiled into benchmark suites directly. For example:

```bash
dgm-zero acquire-objective Improve Python debugging ability \
  --workspace .dgm_workspace \
  --validation-budget 24
```

The current Python-debugging objective asks the system to acquire a small runtime-error diagnostic capability. The synthesizer receives only training examples and learns a candidate classifier; separate validation and holdout error messages determine whether the skill is promoted.

Other built-in objective families currently include text normalization, sequence-span calculation, and scalar clamping. Unsupported objectives fail explicitly instead of receiving invented tests.

### Explicit capability specifications

For capability families not built into the objective compiler, provide a JSON specification:

```bash
dgm-zero acquire examples/capabilities/normalize_text.json \
  --workspace .dgm_workspace
```

A specification defines:

- a capability name and description;
- a pure-function entrypoint;
- JSON-serializable positional inputs and expected outputs;
- non-empty `train`, `validation`, and `holdout` splits;
- optional per-split correctness thresholds and minimum required gain.

Example specifications are under `examples/capabilities/`.

## Why the holdout gate matters

Candidate generation never receives validation or holdout cases. Training is used for search, validation is used for finalist selection, and holdout is evaluated once for certification.

Each capability holdout suite receives a cryptographic digest. Once that suite has been consumed, Darwin Agent Zero will not expose it to another adaptive acquisition attempt. A failed certification therefore requires fresh holdout evidence rather than allowing the system to repeatedly tune against the same hidden test.

This is a major distinction between **actual capability evidence** and simply optimizing a score until a fixed benchmark passes.

## Versioned skill library

Promoted capabilities are stored beneath:

```text
.dgm_workspace/
├── capabilities/
│   └── <capability>/
│       ├── current.json
│       ├── history.jsonl
│       └── versions/
│           └── <sha256>.py
├── capability_certifications.jsonl
├── capability_reports/
└── capability_acquisition_report.json
```

Skill source is content-addressed by SHA-256. Failed candidates never replace the installed skill. Each later acquisition attempt is measured against the current verified baseline before promotion.

## Starter synthesizer

The local deterministic synthesizer currently explores a bounded grammar containing:

- identity and scalar transformations;
- text stripping, case normalization, whitespace normalization, and reversal;
- sequence length, sum, min/max, span, sorting, reversal, and endpoint extraction;
- common binary arithmetic/string operations;
- scalar clamping;
- exact small affine numeric relationships inferred from training examples;
- simple diagnostic classifiers inferred from discriminative tokens in labeled training text.

The acquisition protocol accepts a pluggable candidate generator interface. A future model-backed or more advanced program-synthesis provider can therefore replace the starter search grammar without being given validation/holdout data or bypassing sandbox and promotion gates.

## Candidate sandbox

Generated skills are deliberately restricted to pure JSON-in/JSON-out functions. Candidate modules are statically checked before execution:

- imports are rejected;
- reflective/dangerous builtins are rejected;
- private and dunder attribute traversal is rejected;
- extra top-level execution is rejected;
- direct calls are restricted to a small pure-builtin allowlist;
- source size and AST size are bounded.

Candidates execute under isolated Python (`-I -S`) in temporary directories with wall-clock timeouts and host-supported resource limits. The sandbox is a research containment layer, not a claim of perfect adversarial isolation.

## Original Darwin evolution loop

The original loop remains available:

```text
observe -> self-instruct -> mutate/tool-build -> sandbox-test -> score -> archive -> learn
```

Run it with:

```bash
dgm-zero run --generations 12 --population 6 --workspace .dgm_workspace
```

It evolves arithmetic candidate expressions and scores them across correctness, efficiency, novelty, safety, simplicity, and generalization. The system also maintains an evolutionary archive, MAP-Elites diversity state, metacognitive signals, curriculum state, provenance, health checks, and healthy-checkpoint recovery.

Expected artifacts include:

- `archive.jsonl` — candidate lineage and scores;
- `champion.py` — best accepted arithmetic tool;
- `evolution_report.json` — run summary;
- `map_elites.json` — quality-diversity cells;
- `health_report.json` — run health invariants;
- `provenance.json` — source/artifact fingerprints;
- `checkpoints/` — last-known-good recovery state.

## Install

```bash
cd darwin_agent_zero
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -e .
```

No API key is required for the current local synthesizer.

## Verify

Run all unit tests:

```bash
python -m unittest discover -s tests
```

Run the full Darwin integration validation:

```bash
python scripts/validate.py
```

Run the capability-acquisition integration proof:

```bash
python scripts/validate_capabilities.py
```

The capability validator must demonstrate, from a clean workspace, that the system:

1. acquires and versions a text-normalization skill;
2. acquires and versions a different sequence skill;
3. compiles `Improve Python debugging ability` into a bounded diagnostic benchmark and acquires a passing skill;
4. reaches 1.0 on train, validation, and holdout for those demonstrations; and
5. refuses to evaluate an already-consumed holdout suite again.

GitHub Actions runs compilation, unit/integration validation, and the capability proof on Python 3.11 and 3.12.

## Current boundary

What is general now is the **acquisition protocol**: objective/specification, task construction, synthesis interface, sandboxing, train/validation separation, one-shot certification, measurable promotion, persistent memory, and versioned skill retention.

What is not general yet is the starter synthesizer's search space. It cannot autonomously solve arbitrary software-engineering problems, design arbitrary libraries, or infer reliable benchmarks for every natural-language goal. New benchmark factories and stronger candidate generators must be added for broader capability families while keeping the same independent verification boundary.

That boundary is intentional: Darwin Agent Zero should expand what it can learn without weakening the evidence required to claim that it learned it.
