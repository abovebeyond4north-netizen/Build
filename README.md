# GENESIS v4.0

**Generative Evolving Neural Engine for Self-Improving Systems**

GENESIS is an experimental multi-agent evolution and learning simulation. The current `genesis.py` implementation combines neuroevolution, online adaptation, intrinsic-motivation signals, communication, counterfactual evaluation, shared knowledge, hierarchical goals, social prediction, concept formation, and self-narrative mechanisms in one self-contained Python program.

> **Project status:** research prototype. GENESIS explores mechanisms associated with adaptive and self-improving systems; it is not evidence of artificial general intelligence or a formally verified Gödel machine.

## Current capabilities

The v4 implementation contains 17 major capability areas:

| # | Capability | Implementation focus |
|---|---|---|
| 1 | Passive learning | Agents update behavior from simulated experience |
| 2 | Meta-learning | Evolvable learning-rule parameters |
| 3 | Darwinian evolution | Mutation, crossover, topology change, and speciation |
| 4 | Validated self-modification | Candidate changes are evaluated before retention |
| 5 | Self-directed control | Agents choose actions from internal state and goals |
| 6 | Self-evaluation | Curriculum, diversity, and stagnation signals |
| 7 | Recovery mechanisms | Rollback and anomaly-handling paths |
| 8 | Intrinsic exploration | Curiosity, novelty search, and self-play-inspired signals |
| 9 | Open-ended behavior search | Evolution can discover unprogrammed behavior combinations |
| 10 | Decision intelligence | Causal memory, prediction, and temporal evaluation |
| 11 | Emergent communication | Evolvable signaling between nearby agents |
| 12 | Counterfactual reasoning | Alternative-action replay and regret-based adjustment |
| 13 | Persistent knowledge transfer | Shared knowledge survives individual agents |
| 14 | Hierarchical goal formation | Multi-level goals and sub-goal decomposition |
| 15 | Theory-of-mind approximation | Internal prediction models for other agents |
| 16 | Abstract concept formation | Prototype-based compression of repeated situations |
| 17 | Self-narrative | Compressed autobiographical state influencing later decisions |

## What changed in v4.0

v4 adds four capability families on top of the v3 communication, counterfactual, and shared-knowledge systems:

- **Hierarchical goal formation** — agents can maintain goals and decompose them into smaller objectives.
- **Social prediction** — agents model aspects of other agents' behavior to influence cooperation and competition.
- **Abstract concept formation** — repeated experiences can be compressed into higher-level prototypes.
- **Self-narrative** — agents maintain a compact history that can affect later decisions and inheritance.

## Requirements

- Python 3.11 or 3.12 recommended
- NumPy
- Matplotlib

Install dependencies from the repository manifest:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Run

```bash
python genesis.py
```

The default configuration currently runs **150 generations** with **100 simulation steps per generation**, so a full run is intentionally more substantial than a smoke test.

## Verify core behavior

Run the deterministic fast test suite without starting the full simulation:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The current core tests verify innovation-ID stability, minimal genome topology, finite bounded network activation, structural independence after genome copying, and learning-rule weight bounds.

## Output

Generated plots are written under `genesis_output/`. The v4 visualization paths currently include:

- `genesis_output/genesis_v4_dashboard.png`
- `genesis_output/genesis_v4_universe.png`

Generated output and Python cache files are ignored by Git so experiments do not continuously add local artifacts to source control.

## Continuous integration

The `GENESIS quality` workflow performs fast checks on pull requests and pushes that touch GENESIS:

- compiles `genesis.py` and the core tests on Python 3.11 and 3.12;
- installs the declared runtime dependencies;
- verifies that NumPy and Matplotlib import successfully;
- executes the deterministic GENESIS core behavioral test suite.

The workflow intentionally avoids running the full 150-generation simulation on every commit. Long experiment runs should be executed separately and their parameters/results recorded explicitly when used as evidence.

## Architecture

See [`GENESIS_Architecture.md`](GENESIS_Architecture.md) for the extended architecture notes. Where that document and the executable source disagree, treat `genesis.py` as the current implementation and open an issue or pull request to synchronize the documentation.

## Reproducible research guidance

For comparable experiment results, record at minimum:

1. the Git commit SHA;
2. Python version and dependency versions;
3. random seed, when fixed;
4. configuration changes relative to `Config`;
5. number of generations and steps per generation;
6. the metric definition used for every reported result.

This separates observed experiment results from capability descriptions and makes future improvements easier to validate.

---

**GENESIS v4.0** — an experimental platform for studying evolutionary, adaptive, social, and self-evaluating agent mechanisms.
