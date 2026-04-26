# GENESIS v2.0: Generative Evolving Neural Engine for Self-Improving Systems

## A Self-Sufficient Darwinian Gödel Machine with Zero-Data Meta-Learning and Decision Intelligence

---

## 1. Executive Summary

**GENESIS** (Generative Evolving Neural Engine for Self-Improving Systems) is a fully autonomous, self-sufficient artificial intelligence framework that requires no external data, no human supervision, and no pre-trained models. It bootstraps intelligence from random initialization through a combination of **Darwinian evolution**, **Gödel machine self-rewriting**, **meta-learning from scratch**, and **curiosity-driven exploration**.

The system is designed to go **"Beyond the Builder"** — to discover solutions, architectures, and strategies that were never explicitly programmed. It achieves this through open-ended evolution, novelty search, and emergent complexity arising from the interaction of simple self-modifying agents in a competitive environment.

> "A Gödel machine is a self-referential universal problem solver that modifies its own code whenever it can prove the modification is an improvement." — Jürgen Schmidhuber, 2003 [1]

This document describes the complete architecture, theoretical grounding, and implementation design of GENESIS, building upon the foundation established in the **EvolvingNeuralAgentsinaField** notebook.

**v2.0** introduces the **Decision Intelligence System** — agents now learn what decisions lead to what outcomes, how long consequences take to manifest, which world states are acceptable vs. unacceptable, and they predict consequences before committing to actions. This transforms agents from reactive stimulus-response machines into deliberative decision-makers with causal understanding.

---

## 2. Theoretical Foundations

### 2.1 The Gödel Machine Paradigm

The Gödel machine, introduced by Schmidhuber (2003), is a theoretical framework for a self-improving AI that can rewrite any part of its own code — including the rewriting mechanism itself — provided it can construct a formal proof that the rewrite will improve its performance according to a utility function [1]. GENESIS implements a **pragmatic Gödel machine** that replaces formal proofs with empirical validation through statistical testing and rollback safety nets.

### 2.2 Neuroevolution of Augmenting Topologies (NEAT)

Stanley and Miikkulainen (2002) demonstrated that evolving both the topology and weights of neural networks simultaneously produces more powerful solutions than fixed-topology evolution [2]. GENESIS extends this principle: agents evolve not just their network weights and topology, but their **learning rules**, **sensor configurations**, and **behavioral strategies**.

### 2.3 Curiosity-Driven Exploration and Intrinsic Motivation

Pathak et al. (2017) showed that agents driven by prediction error as intrinsic reward can explore complex environments without extrinsic rewards [3]. GENESIS agents are motivated by **compression progress** — the improvement in their ability to predict and compress their experiences — following Schmidhuber's formal theory of curiosity and creativity [4].

### 2.4 Open-Ended Evolution and Novelty Search

Lehman and Stanley (2011) demonstrated that searching for novelty rather than fitness alone produces more diverse and ultimately more capable solutions [5]. GENESIS maintains a **novelty archive** that rewards behavioral diversity, preventing premature convergence and enabling the discovery of solutions "beyond the builder."

### 2.5 Meta-Learning and Learning to Learn

The system implements meta-learning in the truest sense: agents evolve their own learning algorithms. Rather than using a fixed optimizer like gradient descent, the learning rule itself is encoded in the agent's genome and subject to evolutionary pressure, following the approach of Bengio et al. (1990) on learning learning algorithms [6].

### 2.6 Decision Intelligence and Causal Reasoning (v2.0)

Agents in GENESIS v2.0 develop **causal models** of their environment through experience. Drawing on the framework of temporal difference learning (Sutton, 1988) [9] and model-based reinforcement learning, agents maintain internal representations of cause-and-effect relationships. They learn that certain actions in certain states lead to specific outcomes over specific time horizons. Crucially, agents also evolve **acceptability boundaries** — internal standards for which world states are tolerable and which must be avoided — creating a form of artificial moral reasoning that emerges from evolutionary pressure rather than explicit programming.

---

## 3. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GENESIS CORE ENGINE                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   UNIVERSE    │  │  POPULATION  │  │   GÖDEL VALIDATION       │  │
│  │   (Field +    │◄─┤  (Agents +   │──┤   ENGINE                 │  │
│  │   Physics)    │  │  Species)    │  │   (Proof/Test Gate)      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                 │                      │                  │
│         ▼                 ▼                      ▼                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  ENERGY      │  │  EVOLUTION   │  │   SELF-MODIFICATION      │  │
│  │  DYNAMICS    │  │  ENGINE      │  │   PIPELINE               │  │
│  │  (Resources) │  │  (Selection  │  │   (Code Rewrite +        │  │
│  └──────────────┘  │   Mutation   │  │    Rollback)             │  │
│                    │   Crossover) │  └──────────────────────────┘  │
│                    └──────┬───────┘                                 │
│                           │                                        │
│         ┌─────────────────┼─────────────────┐                      │
│         ▼                 ▼                 ▼                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  META-LEARN  │  │  CURIOSITY   │  │  NOVELTY     │             │
│  │  ENGINE      │  │  MODULE      │  │  ARCHIVE     │             │
│  │  (Learn to   │  │  (Intrinsic  │  │  (Behavioral │             │
│  │   Learn)     │  │   Reward)    │  │   Diversity) │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              SELF-EVALUATION & QUALITY CONTROL                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │  │
│  │  │ Internal   │  │ Curriculum │  │ Health Monitor &       │  │  │
│  │  │ Critic     │  │ Generator  │  │ Self-Healing           │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Core Subsystems

### 4.1 The Universe: Field and Physics Engine

The **Universe** is the environment in which agents exist. It extends the original `Field` class from the EvolvingNeuralAgentsinaField notebook with richer dynamics.

**Energy Field** — A 2D grid of energy values that agents consume to survive. The field has dynamic hotspots that shift over time, creating a non-stationary environment that demands continuous adaptation. Energy regenerates through diffusion and random injection, simulating a living ecosystem.

**Physics Rules** — Movement costs energy. Sensing costs energy. Thinking costs energy proportional to brain complexity. This creates natural pressure toward efficient architectures — agents that are too complex starve, while agents that are too simple cannot compete.

**Environmental Challenges** — The universe periodically introduces catastrophic events (energy droughts, field inversions, obstacle walls) that test the robustness and adaptability of the population. Only agents with genuine generalization survive these black swan events.

### 4.2 The Agent: Neural Connectome and Genome

Each agent in GENESIS is defined by a **Genome** that encodes:

| Component | Description | Evolvable |
|-----------|-------------|-----------|
| **Connectome** | Neural weight matrix mapping sensors to actions | Yes — weights mutate |
| **Topology** | Network structure (number of hidden nodes, connections) | Yes — NEAT-style |
| **Learning Rule** | How weights update during lifetime (Hebbian parameters) | Yes — meta-learning |
| **Sensor Config** | What the agent perceives (field radius, resolution) | Yes — sensory evolution |
| **Metabolism Rate** | Energy efficiency of the agent | Yes — efficiency pressure |
| **Curiosity Drive** | Strength of intrinsic motivation | Yes — exploration vs exploitation |
| **Self-Modify Gate** | Threshold for accepting self-modifications | Yes — conservatism evolves |
| **Caution Level** | Risk aversion in decision-making | Yes — safety evolves |
| **Acceptability Threshold** | Boundary for unacceptable world states | Yes — standards evolve |
| **Planning Depth** | How many steps ahead the agent considers | Yes — foresight evolves |
| **Temporal Discount** | How much future consequences matter vs. present | Yes — patience evolves |

The agent's **brain** is a variable-topology neural network. Unlike the original notebook's fixed 2×9 weight matrix, GENESIS agents can grow new neurons, prune unnecessary connections, and rewire their architecture during their lifetime.

### 4.3 The Evolution Engine: Darwinian Selection

The evolution engine implements a multi-objective evolutionary algorithm with the following selection pressures:

**Fitness Components:**

1. **Survival Duration** — How long the agent stays alive. The most fundamental fitness signal.
2. **Energy Accumulated** — Total energy harvested, measuring foraging effectiveness.
3. **Offspring Count** — Reproductive success, the ultimate Darwinian metric.
4. **Novelty Score** — Behavioral uniqueness compared to the novelty archive, preventing convergence.
5. **Compression Progress** — Improvement in the agent's internal world model, rewarding learning.

**Evolutionary Operators:**

**Tournament Selection** — Agents compete in small groups; the winner reproduces. This maintains selection pressure while preserving diversity.

**Mutation** — Gaussian noise applied to weights, with the mutation rate itself being evolvable. Structural mutations add/remove neurons and connections (NEAT-style). Learning rule parameters mutate, enabling meta-learning evolution.

**Crossover** — Two parent agents combine their genomes. Connection genes are aligned by innovation number (as in NEAT), allowing meaningful recombination of different topologies.

**Speciation** — Agents are grouped into species based on genomic distance. Each species is allocated reproduction slots proportional to its average fitness, protecting innovative but not-yet-optimized lineages from premature extinction.

### 4.4 The Gödel Validation Engine: Self-Modification with Safety

This is the heart of what makes GENESIS a Gödel machine. Agents can propose modifications to their own code (weights, topology, learning rules), but modifications must pass through a **validation gate** before being accepted.

**The Validation Pipeline:**

```
Proposed Modification
        │
        ▼
┌───────────────────┐
│  SNAPSHOT STATE    │  ← Save current weights, topology, performance
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  APPLY CANDIDATE  │  ← Tentatively apply the modification
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  EMPIRICAL TEST   │  ← Run N evaluation episodes
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  STATISTICAL      │  ← Compare performance: new vs. baseline
│  COMPARISON       │  ← Welch's t-test, p < 0.05
└───────┬───────────┘
        │
    ┌───┴───┐
    │       │
 ACCEPT   REJECT
    │       │
    ▼       ▼
 Keep    Rollback
 New     to Snapshot
```

**Key Properties:**

The validation gate is **self-referential** — the threshold for accepting modifications is itself part of the genome and subject to evolution. Agents that are too conservative miss improvements; agents that are too liberal accept harmful mutations. Evolution finds the optimal balance.

The system maintains a **modification history** with full rollback capability. If a series of accepted modifications leads to degraded performance over time, the agent can revert to any previous checkpoint.

### 4.5 Meta-Learning Engine: Learning to Learn

The meta-learning engine is what enables GENESIS to discover its own learning algorithms. Each agent carries a set of **learning rule parameters** that define how its weights change during its lifetime.

**The Evolvable Learning Rule:**

Each connection in the network has a local learning rule of the form:

```
Δw = η * (A*pre*post + B*pre + C*post + D)
```

where `η` (learning rate), `A` (Hebbian term), `B` (pre-synaptic term), `C` (post-synaptic term), and `D` (bias term) are all encoded in the genome and subject to evolution. This parameterization can express:

| Parameters | Learning Rule |
|-----------|---------------|
| A=1, B=C=D=0 | Pure Hebbian learning |
| A=-1, B=0, C=1, D=0 | Oja's rule (normalized Hebbian) |
| A=0, B=0, C=0, D≠0 | Random walk |
| Evolved values | Novel, potentially undiscovered rules |

The critical insight is that evolution operates on **two timescales**: within a lifetime (learning rule application) and across generations (genetic evolution of the learning rule itself). This is true meta-learning — the system discovers which learning algorithms work best for the environment it faces.

### 4.6 Curiosity Module: Intrinsic Motivation

Agents maintain an internal **world model** — a small neural network that predicts the next sensory state given the current state and action. The prediction error of this world model serves as **intrinsic reward**.

**Curiosity Reward = |Predicted_State - Actual_State|**

This drives agents to seek out novel, unpredictable experiences. Critically, the curiosity drive strength is itself evolvable — some agents may evolve to be highly curious explorers while others become efficient exploiters of known resources.

The world model also provides **compression progress** as a fitness signal. An agent that is learning (improving its predictions) is rewarded, while an agent in a fully predicted environment receives no curiosity bonus.

### 4.7 Novelty Archive: Beyond the Builder

The novelty archive stores **behavioral characterizations** of agents — not what they are, but what they do. Each agent's behavior is characterized by a vector describing:

- Average position over lifetime
- Movement pattern (variance, directionality)
- Energy harvesting strategy (peak-seeking vs. area-coverage)
- Interaction patterns with other agents
- Lifetime learning trajectory

New agents receive a **novelty score** based on their distance from the k-nearest neighbors in the archive. This score is combined with fitness in a multi-objective selection scheme, ensuring that the population explores the space of possible behaviors rather than converging on a single strategy.

This is the mechanism that enables **"Beyond the Builder"** emergence. By rewarding novelty, the system discovers strategies that no designer anticipated.

### 4.8 Self-Instruction and Curriculum Generation

The system generates its own training curriculum through **environmental complexity scheduling**:

**Phase 1: Primordial Soup** — Simple, static energy field. Agents learn basic survival (movement toward energy).

**Phase 2: Dynamic World** — Energy hotspots shift. Agents must learn to track moving resources.

**Phase 3: Competition** — Population density increases. Agents must compete and develop social strategies.

**Phase 4: Catastrophe** — Random environmental shocks. Agents must develop robustness and generalization.

**Phase 5: Open-Ended** — All challenges active simultaneously with increasing complexity. No ceiling on difficulty.

The curriculum advances automatically based on population performance metrics. If the population masters a phase (average fitness exceeds threshold), the next phase activates.

### 4.9 Self-Quality-Check and Self-Evaluation

The system continuously monitors its own health through multiple mechanisms:

**Population Diversity Monitor** — If genetic diversity drops below a threshold, the system injects random immigrants and increases mutation rates to prevent premature convergence.

**Fitness Stagnation Detector** — If the best fitness hasn't improved for N generations, the system triggers environmental changes and increases novelty selection pressure.

**Self-Healing** — If a mutation produces an agent that crashes (NaN weights, infinite values), the system catches the error, logs the failure, and rolls back to the parent's genome. The failure mode is recorded to avoid similar mutations in the future.

**Statistical Validation** — All performance claims are backed by statistical tests. The system doesn't just track "best fitness" — it tracks confidence intervals, effect sizes, and significance levels.

### 4.10 Decision Intelligence System (v2.0)

The Decision Intelligence System is the most significant addition in v2.0. It gives agents the ability to **think before acting** — to evaluate the consequences of candidate actions, check whether the predicted outcome is acceptable, and override the neural network's reflexive response when deliberation suggests a better path.

**Causal Memory** — Each agent maintains a buffer of recent transitions: what state it was in, what action it took, what happened next, how its health changed, and how the world state changed. This is the raw experiential data from which causal understanding emerges.

**Consequence Predictor** — A small neural network that takes (state, action) as input and predicts four outputs: expected reward, expected health change, expected quality of the resulting world state, and how quickly the effect manifests. This network is trained online from the agent's own causal memory, giving each agent a personalized model of cause and effect.

**World State Evaluator** — Another small neural network that judges whether a given world state is good (positive value) or bad (negative value). It learns from the agent's own experience: states where health increased are labeled good; states where health crashed are labeled bad. This gives agents an internal "gut feeling" about situations.

**Acceptability Boundaries** — Each agent has an evolvable threshold that defines the boundary between acceptable and unacceptable world states. If the World State Evaluator rates a predicted future state below this threshold, the agent treats it as unacceptable and avoids actions that lead there. The threshold itself evolves: agents that set it too high become paralyzed (everything seems dangerous); agents that set it too low walk into fatal situations. Evolution finds the right balance.

**Temporal Reasoning** — The system propagates downstream values backward through the causal memory, teaching agents that decisions have delayed consequences. An action that yields immediate reward but leads to a bad state 5 steps later will eventually be recognized as harmful. The temporal discount factor (how much future consequences matter vs. present ones) is itself evolvable.

**Decision Override** — When the Decision Intelligence System evaluates the neural network's proposed action and finds a better alternative (or finds the proposed action leads to an unacceptable state), it overrides the neural network. This creates a two-level cognitive architecture: fast reactive responses from the neural network, and slow deliberative oversight from the Decision Intelligence System.

**Decision Journal** — Every decision is recorded with full audit trail: what was decided, what was predicted, what actually happened, and whether the outcome was acceptable. This enables the agent to learn from its own decision-making mistakes.

```
┌─────────────────────────────────────────────────────────────────┐
│              DECISION INTELLIGENCE SYSTEM (v2.0)                │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │ CAUSAL       │───►│ CONSEQUENCE      │───►│ WORLD STATE  │  │
│  │ MEMORY       │    │ PREDICTOR        │    │ EVALUATOR    │  │
│  │ (Experience) │    │ (What will       │    │ (Is this     │  │
│  │              │    │  happen?)        │    │  acceptable?)│  │
│  └──────────────┘    └────────┬─────────┘    └──────┬───────┘  │
│                               │                      │         │
│                               ▼                      ▼         │
│                    ┌──────────────────────────────────────┐     │
│                    │     DECISION GATE                     │     │
│                    │  Compare candidates, check bounds,   │     │
│                    │  override if needed, record in       │     │
│                    │  Decision Journal                    │     │
│                    └──────────────────────────────────────┘     │
│                               │                                │
│                    ┌──────────▼──────────┐                     │
│                    │ TEMPORAL REASONING   │                     │
│                    │ Backpropagate future │                     │
│                    │ consequences through │                     │
│                    │ causal memory        │                     │
│                    └─────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

### 4.11 Self-Support and Error Recovery

The self-support system ensures GENESIS never crashes or degrades irrecoverably:

**Checkpoint System** — Full population state is saved every N generations. If catastrophic failure occurs, the system can restore from any checkpoint.

**Graceful Degradation** — If computational resources are limited, the system automatically reduces population size, simplifies environments, or shortens evaluation episodes while maintaining evolutionary progress.

**Anomaly Detection** — Weight values, fitness scores, and population statistics are monitored for anomalies (NaN, infinity, extreme outliers). Anomalous agents are quarantined and analyzed before being removed.

**Self-Repair Protocol** — When an error is detected, the system follows a hierarchy: (1) retry with noise, (2) rollback to checkpoint, (3) reinitialize the affected component, (4) log and continue with reduced capability.

---

## 5. The Complete Evolutionary Cycle

```
                    ┌─────────────────────┐
                    │   INITIALIZE        │
                    │   Random Population │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
              ┌────►│   LIVE              │
              │     │   Agents sense,     │
              │     │   think, act in     │
              │     │   the field         │
              │     └─────────┬───────────┘
              │               │
              │     ┌─────────▼───────────┐
              │     │   LEARN             │
              │     │   Apply evolvable   │
              │     │   learning rules    │
              │     │   Update world model│
              │     └─────────┬───────────┘
              │               │
              │     ┌─────────▼───────────┐
              │     │   SELF-MODIFY       │
              │     │   Propose changes   │◄── Gödel Gate
              │     │   Validate & apply  │
              │     └─────────┬───────────┘
              │               │
              │     ┌─────────▼───────────┐
              │     │   EVALUATE          │
              │     │   Fitness + Novelty │
              │     │   + Curiosity       │
              │     └─────────┬───────────┘
              │               │
              │     ┌─────────▼───────────┐
              │     │   SELECT            │
              │     │   Tournament +      │
              │     │   Speciation        │
              │     └─────────┬───────────┘
              │               │
              │     ┌─────────▼───────────┐
              │     │   REPRODUCE         │
              │     │   Crossover +       │
              │     │   Mutation          │
              │     └─────────┬───────────┘
              │               │
              │     ┌─────────▼───────────┐
              │     │   QUALITY CHECK     │
              │     │   Diversity monitor │
              │     │   Stagnation check  │
              │     │   Self-healing      │
              │     └─────────┬───────────┘
              │               │
              └───────────────┘
```

---

## 6. How GENESIS Achieves "Beyond the Builder"

The concept of going "beyond the builder" means the system discovers solutions, behaviors, and architectures that its creator never explicitly programmed or anticipated. GENESIS achieves this through several synergistic mechanisms:

**Open-Ended Search Space** — By evolving topology (NEAT-style), learning rules, sensor configurations, and behavioral strategies simultaneously, the search space is combinatorially vast. The system can discover configurations that no human would think to try.

**Novelty-Driven Exploration** — The novelty archive actively rewards agents for being different. This prevents the population from settling into a local optimum and pushes it to explore the full space of possible behaviors.

**Meta-Learning Emergence** — When agents evolve their own learning rules, they can discover learning algorithms that are better suited to their environment than any hand-designed algorithm. The learning rule itself becomes a creative output of the system.

**Self-Modification Chains** — Through the Gödel machine mechanism, agents can make sequences of self-modifications that compound into qualitative behavioral changes. A series of small, validated improvements can lead to emergent capabilities that weren't present in any single modification.

**Environmental Co-Evolution** — As agents become more capable, the environment (through curriculum generation) becomes more challenging. This arms race drives continuous innovation without any external input.

---

## 7. Relationship to the Original Notebook

GENESIS builds directly on the **EvolvingNeuralAgentsinaField** notebook, extending each component:

| Original Component | GENESIS Extension |
|-------------------|-------------------|
| Fixed 2×9 weight matrix | Variable-topology NEAT network |
| Random weight initialization | Evolved initialization strategies |
| Simple Gaussian mutation | Structural mutation + crossover + speciation |
| Health-based survival | Multi-objective fitness (survival + novelty + curiosity + decision quality) |
| Static 3×3 sensor | Evolvable sensor radius and resolution |
| No learning during lifetime | Evolvable Hebbian learning rules |
| No self-modification | Gödel validation gate for self-rewriting |
| No intrinsic motivation | Curiosity-driven exploration module |
| Single energy field | Dynamic multi-phase curriculum |
| No diversity maintenance | Novelty archive + speciation |
| Reactive behavior only | Decision Intelligence with consequence prediction |
| No concept of good/bad states | Evolved acceptability boundaries |
| No temporal reasoning | Causal memory with downstream value propagation |
| No decision audit | Full Decision Journal with prediction vs. outcome tracking |

---

## 8. References

[1] Schmidhuber, J. (2003). "Gödel Machines: Self-Referential Universal Problem Solvers Making Provably Optimal Self-Improvements." arXiv:cs/0309048.

[2] Stanley, K.O. and Miikkulainen, R. (2002). "Evolving Neural Networks through Augmenting Topologies." Evolutionary Computation, 10(2), 99-127.

[3] Pathak, D., Agrawal, P., Efros, A.A., and Darrell, T. (2017). "Curiosity-driven Exploration by Self-Predictive Learning." ICML.

[4] Schmidhuber, J. (2010). "Formal Theory of Creativity, Fun, and Intrinsic Motivation." IEEE Transactions on Autonomous Mental Development, 2(3), 230-247.

[5] Lehman, J. and Stanley, K.O. (2011). "Abandoning Objectives: Evolution Through the Search for Novelty Alone." Evolutionary Computation, 19(2), 189-223.

[6] Bengio, Y., Bengio, S., and Cloutier, J. (1990). "Learning a Synaptic Learning Rule." IJCNN.

[7] Such, F.P., Madhavan, V., Conti, E., Lehman, J., Stanley, K.O., and Clune, J. (2017). "Deep Neuroevolution: Genetic Algorithms Are a Competitive Alternative for Training Deep Neural Networks for Reinforcement Learning." arXiv:1712.06567.

[8] Wang, R., Lehman, J., Clune, J., and Stanley, K.O. (2019). "POET: Endlessly Generating Increasingly Complex and Diverse Learning Environments and Their Solutions through the Paired Open-Ended Trailblazer." arXiv:1901.01753.

[9] Sutton, R.S. (1988). "Learning to Predict by the Methods of Temporal Differences." Machine Learning, 3(1), 9-44.

[10] Ha, D. and Schmidhuber, J. (2018). "World Models." arXiv:1803.10122.

---

*GENESIS v2.0 — Agents that learn what decisions lead where, predict consequences before acting, evolve their own standards for what is acceptable, and override their instincts when wisdom says otherwise.*
