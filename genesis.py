#!/usr/bin/env python3
"""
GENESIS v3.0: Generative Evolving Neural Engine for Self-Improving Systems
==========================================================================

A self-sufficient, self-evolving Darwinian Godel machine with zero-data
meta-learning, Decision Intelligence, Emergent Communication, Counterfactual
Reasoning, and Persistent Knowledge Transfer.

v3.0 Additions:
  - Emergent Communication: agents evolve signals to broadcast, developing
    their own language from scratch to coordinate, warn, or deceive
  - Counterfactual Reasoning: agents learn "what would have happened if I'd
    done something different?" by replaying past decisions with alternatives
  - Persistent Knowledge Bank: accumulated wisdom survives death and can be
    inherited by offspring -- knowledge transfer beyond genetics

Full Capabilities:
  1.  Self-Sufficient Passive Learning (zero external data)
  2.  Meta-Learning from Scratch (evolving learning rules)
  3.  Darwinian Self-Evolution (NEAT-style neuroevolution)
  4.  Godel Machine Self-Rewriting (validated self-modification)
  5.  Self-Controlled / Self-Coded (autonomous execution)
  6.  Self-Instructed / Self-Quality-Checked / Self-Evaluated
  7.  Self-Support System (error recovery, rollback, self-healing)
  8.  Zero-Data SOTA Methods (curiosity, novelty search, self-play)
  9.  Beyond the Builder (open-ended emergent evolution)
  10. Decision Intelligence (causal learning, temporal reasoning,
      world-state evaluation, acceptability boundaries)
  11. Emergent Communication (evolved signaling, proto-language)
  12. Counterfactual Reasoning (what-if analysis, regret-based learning)
  13. Persistent Knowledge Transfer (wisdom inheritance, cultural evolution)

Usage:
    python genesis.py

Author: GENESIS System (designed for abovebeyond4north-netizen/Build)
"""

import numpy as np
import copy
import time
import hashlib
import traceback
import os
from collections import defaultdict, deque


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Global configuration -- all parameters in one place."""
    # Universe
    FIELD_SIZE = 50
    ENERGY_REGEN_RATE = 0.05
    ENERGY_DIFFUSION = 0.1
    HOTSPOT_COUNT = 5
    HOTSPOT_SHIFT_RATE = 0.02

    # Population
    INITIAL_POPULATION = 30
    MAX_POPULATION = 80
    MIN_POPULATION = 8

    # Agent
    INITIAL_HEALTH = 15.0
    REPRODUCTION_THRESHOLD = 30.0
    MOVEMENT_COST = 0.15
    THINKING_COST_PER_NODE = 0.005
    SENSOR_RADIUS = 2
    MAX_HIDDEN_NODES = 20

    # Evolution
    MUTATION_RATE = 0.3
    WEIGHT_MUTATION_POWER = 0.5
    STRUCTURAL_MUTATION_RATE = 0.1
    ADD_NODE_RATE = 0.03
    ADD_CONNECTION_RATE = 0.08
    CROSSOVER_RATE = 0.4
    SPECIES_THRESHOLD = 3.0
    SPECIES_EXCESS_COEFF = 1.0
    SPECIES_WEIGHT_COEFF = 0.4
    ELITISM_COUNT = 2

    # Meta-Learning
    LEARNING_RULE_MUTATION_RATE = 0.2
    LEARNING_RATE_RANGE = (0.0001, 0.1)
    HEBBIAN_PARAM_RANGE = (-1.0, 1.0)

    # Godel Validation
    GODEL_TEST_EPISODES = 5
    GODEL_SIGNIFICANCE = 0.1
    GODEL_COOLDOWN = 10

    # Curiosity
    CURIOSITY_WEIGHT = 0.3
    WORLD_MODEL_LR = 0.01

    # Novelty
    NOVELTY_K = 5
    NOVELTY_ARCHIVE_MAX = 500
    NOVELTY_WEIGHT = 0.3

    # Curriculum
    CURRICULUM_ADVANCE_THRESHOLD = 0.7
    CURRICULUM_PHASES = 5

    # Decision Intelligence (v2.0)
    CAUSAL_MEMORY_SIZE = 200
    CONSEQUENCE_HORIZON = 10
    STATE_EVAL_HIDDEN = 12
    STATE_EVAL_LR = 0.005
    ACCEPTABILITY_THRESHOLD_INIT = 0.3
    DECISION_LOOKAHEAD = 5
    TEMPORAL_DISCOUNT = 0.9
    DECISION_WEIGHT = 0.4

    # Communication (v3.0)
    SIGNAL_DIM = 4              # Dimensionality of broadcast signals
    COMM_RANGE = 8.0            # How far signals travel
    SIGNAL_COST = 0.02          # Energy cost to broadcast
    COMM_WEIGHT = 0.2           # Fitness weight for communication effectiveness
    SIGNAL_DECAY = 0.9          # Signal strength decay with distance

    # Counterfactual Reasoning (v3.0)
    COUNTERFACTUAL_REPLAYS = 3  # How many "what-if" replays per learning step
    REGRET_WEIGHT = 0.3         # How much regret influences future decisions
    COUNTERFACTUAL_INTERVAL = 5 # Steps between counterfactual analysis

    # Knowledge Bank (v3.0)
    KNOWLEDGE_BANK_SIZE = 200   # Max entries in the shared knowledge bank
    KNOWLEDGE_INHERIT_RATE = 0.7  # Probability offspring inherits knowledge
    KNOWLEDGE_ENTRY_DIM = 20    # Dimensionality of knowledge entries
    WISDOM_TRANSFER_AMOUNT = 10 # How many knowledge entries to pass on death

    # Simulation
    STEPS_PER_GENERATION = 100
    NUM_GENERATIONS = 150
    CHECKPOINT_INTERVAL = 25
    STAGNATION_LIMIT = 20

    # Visualization
    SAVE_PLOTS = True
    PLOT_DIR = "genesis_output"


# ============================================================================
# INNOVATION TRACKER (for NEAT-style topology evolution)
# ============================================================================

class InnovationTracker:
    """Global tracker for structural mutations."""

    def __init__(self):
        self.innovations = {}
        self.current_innovation = 0
        self.current_node_id = 0

    def get_innovation(self, from_node, to_node):
        key = (from_node, to_node)
        if key not in self.innovations:
            self.innovations[key] = self.current_innovation
            self.current_innovation += 1
        return self.innovations[key]

    def get_new_node_id(self):
        self.current_node_id += 1
        return self.current_node_id


INNOVATION = InnovationTracker()


# ============================================================================
# CONNECTION GENE (NEAT-style)
# ============================================================================

class ConnectionGene:
    """A single connection in the neural network genome."""

    def __init__(self, from_node, to_node, weight, enabled=True, innovation=None):
        self.from_node = from_node
        self.to_node = to_node
        self.weight = weight
        self.enabled = enabled
        self.innovation = innovation or INNOVATION.get_innovation(from_node, to_node)
        self.lr = np.random.uniform(0.001, 0.01)
        self.A = np.random.uniform(-0.5, 0.5)
        self.B = np.random.uniform(-0.5, 0.5)
        self.C = np.random.uniform(-0.5, 0.5)
        self.D = np.random.uniform(-0.1, 0.1)

    def copy(self):
        c = ConnectionGene(self.from_node, self.to_node, self.weight,
                           self.enabled, self.innovation)
        c.lr, c.A, c.B, c.C, c.D = self.lr, self.A, self.B, self.C, self.D
        return c


# ============================================================================
# NODE GENE
# ============================================================================

class NodeGene:
    """A node (neuron) in the network."""
    INPUT = 'input'
    HIDDEN = 'hidden'
    OUTPUT = 'output'

    def __init__(self, node_id, node_type, activation='tanh'):
        self.id = node_id
        self.type = node_type
        self.activation = activation
        self.value = 0.0
        self.prev_value = 0.0


# ============================================================================
# GENOME: The complete genetic blueprint of an agent
# ============================================================================

class Genome:
    """
    NEAT-style genome encoding a variable-topology neural network
    plus evolvable learning rules, sensor config, metabolism,
    decision intelligence params, and communication params.
    """

    def __init__(self, input_size, output_size):
        self.input_size = input_size
        self.output_size = output_size
        self.nodes = {}
        self.connections = {}
        self.fitness = 0.0
        self.adjusted_fitness = 0.0
        self.species_id = None

        # Evolvable hyperparameters
        self.mutation_rate = Config.MUTATION_RATE
        self.curiosity_drive = np.random.uniform(0.1, 0.5)
        self.self_modify_threshold = np.random.uniform(0.05, 0.3)
        self.metabolism_efficiency = np.random.uniform(0.8, 1.2)
        self.sensor_radius = Config.SENSOR_RADIUS

        # Decision Intelligence evolvable parameters (v2.0)
        self.acceptability_threshold = Config.ACCEPTABILITY_THRESHOLD_INIT
        self.temporal_discount = Config.TEMPORAL_DISCOUNT
        self.caution_level = np.random.uniform(0.2, 0.8)
        self.planning_depth = max(1, int(np.random.uniform(1, 5)))

        # Communication evolvable parameters (v3.0)
        self.signal_strength = np.random.uniform(0.3, 1.0)
        self.signal_honesty = np.random.uniform(0.0, 1.0)  # 1=honest, 0=deceptive
        self.listen_weight = np.random.uniform(0.1, 0.9)    # How much to trust signals
        self.broadcast_threshold = np.random.uniform(0.1, 0.8)  # When to broadcast

        # Counterfactual reasoning (v3.0)
        self.regret_sensitivity = np.random.uniform(0.1, 0.8)
        self.counterfactual_depth = max(1, int(np.random.uniform(1, 4)))

        self._initialize_minimal()

    def _initialize_minimal(self):
        """Create a minimal fully-connected network (no hidden nodes)."""
        for i in range(self.input_size):
            node_id = i
            self.nodes[node_id] = NodeGene(node_id, NodeGene.INPUT)
            INNOVATION.current_node_id = max(INNOVATION.current_node_id, node_id + 1)

        for i in range(self.output_size):
            node_id = self.input_size + i
            self.nodes[node_id] = NodeGene(node_id, NodeGene.OUTPUT)
            INNOVATION.current_node_id = max(INNOVATION.current_node_id, node_id + 1)

        for i in range(self.input_size):
            for j in range(self.output_size):
                out_id = self.input_size + j
                weight = np.random.randn() * 0.5
                innov = INNOVATION.get_innovation(i, out_id)
                self.connections[innov] = ConnectionGene(i, out_id, weight, True, innov)

    def activate(self, inputs):
        """Forward pass through the network."""
        for i in range(self.input_size):
            if i in self.nodes:
                self.nodes[i].prev_value = self.nodes[i].value
                self.nodes[i].value = inputs[i] if i < len(inputs) else 0.0

        hidden_nodes = [n for n in self.nodes.values() if n.type == NodeGene.HIDDEN]
        output_nodes = [n for n in self.nodes.values() if n.type == NodeGene.OUTPUT]

        for node in hidden_nodes:
            incoming = sum(
                c.weight * self.nodes[c.from_node].value
                for c in self.connections.values()
                if c.to_node == node.id and c.enabled and c.from_node in self.nodes
            )
            node.prev_value = node.value
            node.value = self._activate(incoming, node.activation)

        outputs = []
        for node in output_nodes:
            incoming = sum(
                c.weight * self.nodes[c.from_node].value
                for c in self.connections.values()
                if c.to_node == node.id and c.enabled and c.from_node in self.nodes
            )
            node.prev_value = node.value
            node.value = self._activate(incoming, node.activation)
            outputs.append(node.value)

        return outputs

    def _activate(self, x, func='tanh'):
        x = np.clip(x, -10, 10)
        if func == 'tanh':
            return np.tanh(x)
        elif func == 'sigmoid':
            return 1.0 / (1.0 + np.exp(-x))
        elif func == 'relu':
            return max(0, x)
        return np.tanh(x)

    def apply_learning_rule(self):
        """Apply the evolvable Hebbian learning rule to all connections."""
        for conn in self.connections.values():
            if not conn.enabled:
                continue
            if conn.from_node not in self.nodes or conn.to_node not in self.nodes:
                continue
            pre = self.nodes[conn.from_node].value
            post = self.nodes[conn.to_node].value
            delta_w = conn.lr * (
                conn.A * pre * post +
                conn.B * pre +
                conn.C * post +
                conn.D
            )
            delta_w = np.clip(delta_w, -0.1, 0.1)
            conn.weight += delta_w
            conn.weight = np.clip(conn.weight, -5.0, 5.0)

    def get_complexity(self):
        active_connections = sum(1 for c in self.connections.values() if c.enabled)
        hidden_count = sum(1 for n in self.nodes.values() if n.type == NodeGene.HIDDEN)
        return active_connections + hidden_count * 2

    def copy(self):
        new = Genome.__new__(Genome)
        new.input_size = self.input_size
        new.output_size = self.output_size
        new.nodes = {k: copy.deepcopy(v) for k, v in self.nodes.items()}
        new.connections = {k: v.copy() for k, v in self.connections.items()}
        new.fitness = 0.0
        new.adjusted_fitness = 0.0
        new.species_id = self.species_id
        new.mutation_rate = self.mutation_rate
        new.curiosity_drive = self.curiosity_drive
        new.self_modify_threshold = self.self_modify_threshold
        new.metabolism_efficiency = self.metabolism_efficiency
        new.sensor_radius = self.sensor_radius
        # Decision intelligence params
        new.acceptability_threshold = self.acceptability_threshold
        new.temporal_discount = self.temporal_discount
        new.caution_level = self.caution_level
        new.planning_depth = self.planning_depth
        # Communication params (v3.0)
        new.signal_strength = self.signal_strength
        new.signal_honesty = self.signal_honesty
        new.listen_weight = self.listen_weight
        new.broadcast_threshold = self.broadcast_threshold
        # Counterfactual params (v3.0)
        new.regret_sensitivity = self.regret_sensitivity
        new.counterfactual_depth = self.counterfactual_depth
        return new


# ============================================================================
# MUTATION OPERATORS
# ============================================================================

class Mutator:
    """All mutation operators for genomes."""

    @staticmethod
    def mutate(genome):
        # Mutate weights
        for conn in genome.connections.values():
            if np.random.random() < genome.mutation_rate:
                if np.random.random() < 0.1:
                    conn.weight = np.random.randn() * 2.0
                else:
                    conn.weight += np.random.randn() * Config.WEIGHT_MUTATION_POWER
                conn.weight = np.clip(conn.weight, -5.0, 5.0)

        # Mutate learning rule parameters
        if np.random.random() < Config.LEARNING_RULE_MUTATION_RATE:
            for conn in genome.connections.values():
                if np.random.random() < 0.3:
                    conn.lr *= np.exp(np.random.randn() * 0.3)
                    conn.lr = np.clip(conn.lr, *Config.LEARNING_RATE_RANGE)
                if np.random.random() < 0.3:
                    conn.A += np.random.randn() * 0.2
                    conn.A = np.clip(conn.A, *Config.HEBBIAN_PARAM_RANGE)
                if np.random.random() < 0.3:
                    conn.B += np.random.randn() * 0.2
                    conn.B = np.clip(conn.B, *Config.HEBBIAN_PARAM_RANGE)
                if np.random.random() < 0.3:
                    conn.C += np.random.randn() * 0.2
                    conn.C = np.clip(conn.C, *Config.HEBBIAN_PARAM_RANGE)
                if np.random.random() < 0.3:
                    conn.D += np.random.randn() * 0.1
                    conn.D = np.clip(conn.D, -0.5, 0.5)

        # Structural mutations
        if np.random.random() < Config.ADD_CONNECTION_RATE:
            Mutator._add_connection(genome)
        if np.random.random() < Config.ADD_NODE_RATE:
            Mutator._add_node(genome)

        # Mutate evolvable hyperparameters
        if np.random.random() < 0.1:
            genome.mutation_rate *= np.exp(np.random.randn() * 0.2)
            genome.mutation_rate = np.clip(genome.mutation_rate, 0.01, 0.9)
        if np.random.random() < 0.1:
            genome.curiosity_drive += np.random.randn() * 0.05
            genome.curiosity_drive = np.clip(genome.curiosity_drive, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.self_modify_threshold += np.random.randn() * 0.02
            genome.self_modify_threshold = np.clip(genome.self_modify_threshold, 0.01, 0.5)
        if np.random.random() < 0.1:
            genome.metabolism_efficiency += np.random.randn() * 0.05
            genome.metabolism_efficiency = np.clip(genome.metabolism_efficiency, 0.5, 2.0)

        # Mutate Decision Intelligence parameters (v2.0)
        if np.random.random() < 0.15:
            genome.acceptability_threshold += np.random.randn() * 0.05
            genome.acceptability_threshold = np.clip(genome.acceptability_threshold, 0.05, 0.8)
        if np.random.random() < 0.1:
            genome.temporal_discount += np.random.randn() * 0.03
            genome.temporal_discount = np.clip(genome.temporal_discount, 0.5, 0.99)
        if np.random.random() < 0.1:
            genome.caution_level += np.random.randn() * 0.05
            genome.caution_level = np.clip(genome.caution_level, 0.0, 1.0)
        if np.random.random() < 0.05:
            genome.planning_depth += np.random.choice([-1, 0, 1])
            genome.planning_depth = max(1, min(8, genome.planning_depth))

        # Mutate Communication parameters (v3.0)
        if np.random.random() < 0.15:
            genome.signal_strength += np.random.randn() * 0.05
            genome.signal_strength = np.clip(genome.signal_strength, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.signal_honesty += np.random.randn() * 0.05
            genome.signal_honesty = np.clip(genome.signal_honesty, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.listen_weight += np.random.randn() * 0.05
            genome.listen_weight = np.clip(genome.listen_weight, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.broadcast_threshold += np.random.randn() * 0.05
            genome.broadcast_threshold = np.clip(genome.broadcast_threshold, 0.0, 1.0)

        # Mutate Counterfactual parameters (v3.0)
        if np.random.random() < 0.1:
            genome.regret_sensitivity += np.random.randn() * 0.05
            genome.regret_sensitivity = np.clip(genome.regret_sensitivity, 0.0, 1.0)
        if np.random.random() < 0.05:
            genome.counterfactual_depth += np.random.choice([-1, 0, 1])
            genome.counterfactual_depth = max(1, min(6, genome.counterfactual_depth))

        return genome

    @staticmethod
    def _add_connection(genome):
        node_ids = list(genome.nodes.keys())
        if len(node_ids) < 2:
            return
        for _ in range(20):
            from_id = np.random.choice(node_ids)
            to_id = np.random.choice(node_ids)
            if from_id == to_id:
                continue
            if genome.nodes[to_id].type == NodeGene.INPUT:
                continue
            if genome.nodes[from_id].type == NodeGene.OUTPUT:
                continue
            exists = any(
                c.from_node == from_id and c.to_node == to_id
                for c in genome.connections.values()
            )
            if exists:
                continue
            innov = INNOVATION.get_innovation(from_id, to_id)
            genome.connections[innov] = ConnectionGene(
                from_id, to_id, np.random.randn() * 0.5, True, innov
            )
            return

    @staticmethod
    def _add_node(genome):
        enabled = [c for c in genome.connections.values() if c.enabled]
        if not enabled:
            return
        hidden_count = sum(1 for n in genome.nodes.values() if n.type == NodeGene.HIDDEN)
        if hidden_count >= Config.MAX_HIDDEN_NODES:
            return
        conn = np.random.choice(enabled)
        conn.enabled = False
        new_node_id = INNOVATION.get_new_node_id()
        genome.nodes[new_node_id] = NodeGene(new_node_id, NodeGene.HIDDEN)
        innov1 = INNOVATION.get_innovation(conn.from_node, new_node_id)
        genome.connections[innov1] = ConnectionGene(
            conn.from_node, new_node_id, 1.0, True, innov1
        )
        innov2 = INNOVATION.get_innovation(new_node_id, conn.to_node)
        genome.connections[innov2] = ConnectionGene(
            new_node_id, conn.to_node, conn.weight, True, innov2
        )

    @staticmethod
    def crossover(parent1, parent2):
        if parent2.fitness > parent1.fitness:
            parent1, parent2 = parent2, parent1
        child = parent1.copy()
        for innov, conn2 in parent2.connections.items():
            if innov in child.connections:
                if np.random.random() < 0.5:
                    child.connections[innov] = conn2.copy()
        if np.random.random() < 0.5:
            child.curiosity_drive = parent2.curiosity_drive
        if np.random.random() < 0.5:
            child.metabolism_efficiency = parent2.metabolism_efficiency
        # Crossover decision intelligence params
        if np.random.random() < 0.5:
            child.acceptability_threshold = parent2.acceptability_threshold
        if np.random.random() < 0.5:
            child.caution_level = parent2.caution_level
        if np.random.random() < 0.5:
            child.temporal_discount = parent2.temporal_discount
        if np.random.random() < 0.5:
            child.planning_depth = parent2.planning_depth
        # Crossover communication params (v3.0)
        if np.random.random() < 0.5:
            child.signal_strength = parent2.signal_strength
        if np.random.random() < 0.5:
            child.signal_honesty = parent2.signal_honesty
        if np.random.random() < 0.5:
            child.listen_weight = parent2.listen_weight
        # Crossover counterfactual params (v3.0)
        if np.random.random() < 0.5:
            child.regret_sensitivity = parent2.regret_sensitivity
        if np.random.random() < 0.5:
            child.counterfactual_depth = parent2.counterfactual_depth
        return child


# ============================================================================
# SPECIATION (NEAT-style)
# ============================================================================

class Species:
    def __init__(self, species_id, representative):
        self.id = species_id
        self.representative = representative
        self.members = [representative]
        self.best_fitness = 0.0
        self.stagnation = 0
        self.age = 0

    def is_compatible(self, genome):
        dist = Species.genomic_distance(genome, self.representative)
        return dist < Config.SPECIES_THRESHOLD

    @staticmethod
    def genomic_distance(g1, g2):
        innovs1 = set(g1.connections.keys())
        innovs2 = set(g2.connections.keys())
        matching = innovs1 & innovs2
        excess_disjoint = len(innovs1 ^ innovs2)
        weight_diff = 0.0
        if matching:
            weight_diff = np.mean([
                abs(g1.connections[i].weight - g2.connections[i].weight)
                for i in matching
            ])
        n = max(len(innovs1), len(innovs2), 1)
        return (Config.SPECIES_EXCESS_COEFF * excess_disjoint / n +
                Config.SPECIES_WEIGHT_COEFF * weight_diff)


# ============================================================================
# WORLD MODEL (for curiosity-driven exploration)
# ============================================================================

class WorldModel:
    """Predicts next sensory state. Prediction error = intrinsic curiosity reward."""

    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        input_dim = state_size + action_size
        hidden_dim = 16
        self.W1 = np.random.randn(hidden_dim, input_dim) * 0.3
        self.b1 = np.zeros(hidden_dim)
        self.W2 = np.random.randn(state_size, hidden_dim) * 0.3
        self.b2 = np.zeros(state_size)
        self.prediction_errors = []

    def predict(self, state, action):
        x = np.concatenate([state, action])
        h = np.tanh(self.W1 @ x + self.b1)
        pred = np.tanh(self.W2 @ h + self.b2)
        return pred

    def train(self, state, action, next_state):
        pred = self.predict(state, action)
        error = np.mean((pred - next_state) ** 2)
        self.prediction_errors.append(error)
        x = np.concatenate([state, action])
        h = np.tanh(self.W1 @ x + self.b1)
        pred = np.tanh(self.W2 @ h + self.b2)
        d_pred = 2 * (pred - next_state) * (1 - pred ** 2)
        self.W2 -= Config.WORLD_MODEL_LR * np.outer(d_pred, h)
        self.b2 -= Config.WORLD_MODEL_LR * d_pred
        d_h = (self.W2.T @ d_pred) * (1 - h ** 2)
        self.W1 -= Config.WORLD_MODEL_LR * np.outer(d_h, x)
        self.b1 -= Config.WORLD_MODEL_LR * d_h
        return error

    def get_compression_progress(self):
        if len(self.prediction_errors) < 10:
            return 0.0
        recent = np.mean(self.prediction_errors[-5:])
        older = np.mean(self.prediction_errors[-10:-5])
        return max(0, older - recent)


# ============================================================================
# DECISION INTELLIGENCE SYSTEM (v2.0)
# ============================================================================

class CausalTransition:
    """A single recorded experience: state + action -> outcome + timing."""

    def __init__(self, state, action, next_state, reward, health_delta, time_cost,
                 world_state_before, world_state_after):
        self.state = state
        self.action = action
        self.next_state = next_state
        self.reward = reward
        self.health_delta = health_delta
        self.time_cost = time_cost
        self.world_state_before = world_state_before
        self.world_state_after = world_state_after
        self.downstream_value = 0.0
        self.counterfactual_regret = 0.0  # v3.0: regret from what-if analysis


class WorldStateEvaluator:
    """Learns to judge whether a world state is good, bad, or unacceptable."""

    def __init__(self, state_dim):
        self.state_dim = state_dim
        hidden = Config.STATE_EVAL_HIDDEN
        self.W1 = np.random.randn(hidden, state_dim) * 0.3
        self.b1 = np.zeros(hidden)
        self.W2 = np.random.randn(1, hidden) * 0.3
        self.b2 = np.zeros(1)
        self.training_count = 0

    def evaluate(self, state_descriptor):
        x = np.array(state_descriptor)
        if len(x) != self.state_dim:
            x = np.resize(x, self.state_dim)
        h = np.tanh(self.W1 @ x + self.b1)
        val = np.tanh(self.W2 @ h + self.b2)
        return float(val[0])

    def train(self, state_descriptor, target_value):
        x = np.array(state_descriptor)
        if len(x) != self.state_dim:
            x = np.resize(x, self.state_dim)
        lr = Config.STATE_EVAL_LR
        h = np.tanh(self.W1 @ x + self.b1)
        val = np.tanh(self.W2 @ h + self.b2)
        error = val[0] - target_value
        d_val = error * (1 - val[0] ** 2)
        d_val_arr = np.array([d_val])
        self.W2 -= lr * np.outer(d_val_arr, h)
        self.b2 -= lr * d_val_arr
        d_h = (self.W2.T @ d_val_arr).flatten() * (1 - h ** 2)
        self.W1 -= lr * np.outer(d_h, x)
        self.b1 -= lr * d_h
        self.training_count += 1
        return abs(error)

    def copy(self):
        new = WorldStateEvaluator(self.state_dim)
        new.W1 = self.W1.copy()
        new.b1 = self.b1.copy()
        new.W2 = self.W2.copy()
        new.b2 = self.b2.copy()
        new.training_count = self.training_count
        return new


class ConsequencePredictor:
    """Predicts what will happen if a certain action is taken."""

    def __init__(self, state_dim, action_dim=2):
        self.state_dim = state_dim
        self.action_dim = action_dim
        input_dim = state_dim + action_dim
        hidden = 16
        self.output_dim = 4
        self.W1 = np.random.randn(hidden, input_dim) * 0.3
        self.b1 = np.zeros(hidden)
        self.W2 = np.random.randn(self.output_dim, hidden) * 0.3
        self.b2 = np.zeros(self.output_dim)
        self.training_count = 0
        self.prediction_accuracy = []

    def predict(self, state, action):
        x = np.concatenate([np.resize(state, self.state_dim),
                            np.resize(action, self.action_dim)])
        h = np.tanh(self.W1 @ x + self.b1)
        out = np.tanh(self.W2 @ h + self.b2)
        return {
            'reward': float(out[0]),
            'health_delta': float(out[1]),
            'state_value': float(out[2]),
            'time_factor': float((out[3] + 1) / 2)
        }

    def train(self, state, action, actual_reward, actual_health_delta,
              actual_state_value, actual_time_factor):
        x = np.concatenate([np.resize(state, self.state_dim),
                            np.resize(action, self.action_dim)])
        target = np.array([
            np.clip(actual_reward, -1, 1),
            np.clip(actual_health_delta, -1, 1),
            np.clip(actual_state_value, -1, 1),
            actual_time_factor * 2 - 1
        ])
        lr = 0.005
        h = np.tanh(self.W1 @ x + self.b1)
        out = np.tanh(self.W2 @ h + self.b2)
        error = out - target
        accuracy = 1.0 - np.mean(np.abs(error))
        self.prediction_accuracy.append(accuracy)
        d_out = error * (1 - out ** 2)
        self.W2 -= lr * np.outer(d_out, h)
        self.b2 -= lr * d_out
        d_h = (self.W2.T @ d_out) * (1 - h ** 2)
        self.W1 -= lr * np.outer(d_h, x)
        self.b1 -= lr * d_h
        self.training_count += 1
        return accuracy

    def get_accuracy(self):
        if not self.prediction_accuracy:
            return 0.0
        return np.mean(self.prediction_accuracy[-20:])

    def copy(self):
        new = ConsequencePredictor(self.state_dim, self.action_dim)
        new.W1 = self.W1.copy()
        new.b1 = self.b1.copy()
        new.W2 = self.W2.copy()
        new.b2 = self.b2.copy()
        new.training_count = self.training_count
        new.prediction_accuracy = list(self.prediction_accuracy[-50:])
        return new


class DecisionJournal:
    """Full audit trail of every decision the agent makes."""

    def __init__(self):
        self.entries = deque(maxlen=500)
        self.good_decisions = 0
        self.bad_decisions = 0
        self.avoided_unacceptable = 0
        self.entered_unacceptable = 0

    def record(self, state, action, predicted_consequence, actual_outcome,
               was_acceptable, was_predicted_acceptable):
        entry = {
            'state_hash': hash(state.tobytes()) if hasattr(state, 'tobytes') else 0,
            'action': action.copy() if hasattr(action, 'copy') else list(action),
            'predicted': predicted_consequence,
            'actual': actual_outcome,
            'was_acceptable': was_acceptable,
            'was_predicted_acceptable': was_predicted_acceptable,
            'prediction_error': abs(
                predicted_consequence.get('reward', 0) - actual_outcome.get('reward', 0)
            )
        }
        self.entries.append(entry)
        if actual_outcome.get('health_delta', 0) > 0:
            self.good_decisions += 1
        elif actual_outcome.get('health_delta', 0) < -1:
            self.bad_decisions += 1
        if not was_acceptable:
            self.entered_unacceptable += 1
        if not was_predicted_acceptable and was_acceptable:
            self.avoided_unacceptable += 1

    def get_decision_quality(self):
        total = self.good_decisions + self.bad_decisions
        if total == 0:
            return 0.5
        quality = self.good_decisions / total
        avoidance_bonus = self.avoided_unacceptable * 0.1
        unacceptable_penalty = self.entered_unacceptable * 0.2
        return np.clip(quality + avoidance_bonus - unacceptable_penalty, 0, 1)

    def get_stats(self):
        return {
            'total_decisions': len(self.entries),
            'good': self.good_decisions,
            'bad': self.bad_decisions,
            'avoided_unacceptable': self.avoided_unacceptable,
            'entered_unacceptable': self.entered_unacceptable,
            'quality': self.get_decision_quality()
        }


class DecisionIntelligence:
    """
    The complete Decision Intelligence System for an agent.
    v3.0: Now includes counterfactual reasoning integration.
    """

    def __init__(self, state_dim):
        self.state_dim = state_dim
        self.causal_memory = deque(maxlen=Config.CAUSAL_MEMORY_SIZE)
        self.state_evaluator = WorldStateEvaluator(state_dim)
        self.consequence_predictor = ConsequencePredictor(state_dim)
        self.journal = DecisionJournal()
        self.unacceptable_states = []
        self.total_decisions = 0

    def get_world_state_descriptor(self, state, health, age):
        descriptor = list(np.resize(state, min(len(state), self.state_dim - 3)))
        descriptor.append(health / Config.INITIAL_HEALTH)
        descriptor.append(min(age / 200.0, 1.0))
        descriptor.append(np.mean(state) if len(state) > 0 else 0)
        descriptor = list(np.resize(np.array(descriptor), self.state_dim))
        return np.array(descriptor)

    def evaluate_action(self, state, candidate_action, genome):
        pred = self.consequence_predictor.predict(state, candidate_action)
        predicted_acceptable = pred['state_value'] > -genome.acceptability_threshold
        reward_score = pred['reward']
        safety_score = pred['state_value']
        time_value = pred['time_factor'] * pred['reward']
        if not predicted_acceptable:
            penalty = genome.caution_level * 2.0
            score = reward_score + safety_score - penalty
        else:
            score = reward_score + safety_score * 0.5 + time_value * 0.3
        return {
            'score': score,
            'predicted': pred,
            'acceptable': predicted_acceptable
        }

    def choose_best_action(self, state, genome, base_action):
        candidates = [base_action]
        for _ in range(Config.DECISION_LOOKAHEAD - 1):
            noise = np.random.randn(2) * 0.5
            alt = np.clip(base_action + noise, -2, 2)
            candidates.append(alt)
        candidates.append(np.array([0.0, 0.0]))
        candidates.append(-base_action)

        best_score = -float('inf')
        best_action = base_action
        best_eval = None
        for action in candidates:
            evaluation = self.evaluate_action(state, action, genome)
            if evaluation['score'] > best_score:
                best_score = evaluation['score']
                best_action = action
                best_eval = evaluation

        self.total_decisions += 1
        return best_action, best_eval

    def record_transition(self, state, action, next_state, reward, health_before,
                          health_after, age, genome):
        health_delta = health_after - health_before
        ws_before = self.get_world_state_descriptor(state, health_before, age)
        ws_after = self.get_world_state_descriptor(next_state, health_after, age + 1)

        transition = CausalTransition(
            state=state, action=action, next_state=next_state,
            reward=reward, health_delta=health_delta, time_cost=1,
            world_state_before=ws_before, world_state_after=ws_after
        )
        self.causal_memory.append(transition)

        state_value_target = np.clip(
            health_delta * 0.5 + reward * 0.3 + (health_after / Config.INITIAL_HEALTH - 0.5),
            -1, 1
        )
        self.state_evaluator.train(ws_after, state_value_target)

        actual_state_value = self.state_evaluator.evaluate(ws_after)
        self.consequence_predictor.train(
            state, action,
            actual_reward=reward, actual_health_delta=health_delta,
            actual_state_value=actual_state_value, actual_time_factor=1.0
        )

        is_acceptable = actual_state_value > -genome.acceptability_threshold
        pred = self.consequence_predictor.predict(state, action)
        pred_acceptable = pred['state_value'] > -genome.acceptability_threshold
        self.journal.record(
            state, action, pred,
            {'reward': reward, 'health_delta': health_delta,
             'state_value': actual_state_value},
            is_acceptable, pred_acceptable
        )

        if not is_acceptable:
            self.unacceptable_states.append(ws_after.copy())
            if len(self.unacceptable_states) > 50:
                self.unacceptable_states = self.unacceptable_states[-50:]

        self._update_downstream_values(genome.temporal_discount)
        return is_acceptable

    def _update_downstream_values(self, discount):
        memory = list(self.causal_memory)
        if len(memory) < 2:
            return
        for i in range(len(memory) - 2, -1, -1):
            future_value = memory[i + 1].reward + discount * memory[i + 1].downstream_value
            memory[i].downstream_value = future_value

    def get_decision_fitness(self):
        quality = self.journal.get_decision_quality()
        accuracy = self.consequence_predictor.get_accuracy()
        avoidance = 1.0 - (self.journal.entered_unacceptable /
                           max(self.total_decisions, 1))
        return (quality * 0.4 + accuracy * 0.3 + avoidance * 0.3)

    def copy(self):
        new = DecisionIntelligence(self.state_dim)
        new.state_evaluator = self.state_evaluator.copy()
        new.consequence_predictor = self.consequence_predictor.copy()
        return new


# ============================================================================
# EMERGENT COMMUNICATION SYSTEM (v3.0)
# ============================================================================

class Signal:
    """A broadcast signal from an agent."""

    def __init__(self, sender_pos, signal_vector, strength, sender_id):
        self.sender_pos = sender_pos.copy()
        self.signal_vector = np.array(signal_vector)
        self.strength = strength
        self.sender_id = sender_id
        self.age = 0


class CommunicationChannel:
    """
    The shared communication medium. Agents broadcast signals into this
    channel and receive signals from nearby agents. Signals decay with
    distance and age.
    """

    def __init__(self):
        self.active_signals = []
        self.signal_history = deque(maxlen=1000)
        self.total_broadcasts = 0
        self.total_receptions = 0
        self.language_diversity = 0.0

    def broadcast(self, sender_pos, signal_vector, strength, sender_id):
        """Agent broadcasts a signal into the channel."""
        sig = Signal(sender_pos, signal_vector, strength, sender_id)
        self.active_signals.append(sig)
        self.signal_history.append(signal_vector.copy())
        self.total_broadcasts += 1

    def receive(self, receiver_pos, receiver_id):
        """
        Receive all signals within range. Returns list of (signal_vector, strength)
        tuples, weighted by distance decay.
        """
        received = []
        for sig in self.active_signals:
            if sig.sender_id == receiver_id:
                continue  # Don't hear your own signal
            dist = np.linalg.norm(receiver_pos - sig.sender_pos)
            if dist < Config.COMM_RANGE:
                decay = Config.SIGNAL_DECAY ** dist
                effective_strength = sig.strength * decay
                received.append((sig.signal_vector, effective_strength))
                self.total_receptions += 1
        return received

    def step(self):
        """Age and remove old signals."""
        for sig in self.active_signals:
            sig.age += 1
        self.active_signals = [s for s in self.active_signals if s.age < 3]

    def get_language_stats(self):
        """Analyze the emergent language structure."""
        if len(self.signal_history) < 10:
            return {'diversity': 0.0, 'clusters': 0, 'vocab_size': 0}
        signals = np.array(list(self.signal_history)[-100:])
        diversity = np.mean(np.std(signals, axis=0))
        # Simple clustering: count distinct signal types
        rounded = np.round(signals, 1)
        unique = set(tuple(r) for r in rounded)
        return {
            'diversity': float(diversity),
            'clusters': len(unique),
            'vocab_size': min(len(unique), 50)
        }


class AgentCommunicator:
    """
    An agent's communication module. Handles encoding signals based on
    internal state and decoding received signals to influence behavior.
    """

    def __init__(self, state_dim):
        self.state_dim = state_dim
        # Encoder: state -> signal
        self.encode_W = np.random.randn(Config.SIGNAL_DIM, state_dim) * 0.3
        self.encode_b = np.zeros(Config.SIGNAL_DIM)
        # Decoder: signal -> action modifier
        self.decode_W = np.random.randn(2, Config.SIGNAL_DIM) * 0.3
        self.decode_b = np.zeros(2)
        # Track communication effectiveness
        self.signals_sent = 0
        self.signals_received = 0
        self.helpful_signals = 0  # Signals that led to good outcomes for receivers

    def encode_signal(self, state, genome):
        """Generate a signal based on current state."""
        x = np.resize(state, self.state_dim)
        raw_signal = np.tanh(self.encode_W @ x + self.encode_b)
        # Honesty modulation: honest agents signal truthfully,
        # deceptive agents may invert or scramble
        if genome.signal_honesty < 0.3:
            # Deceptive: partially invert the signal
            raw_signal = raw_signal * (2 * genome.signal_honesty - 1)
        return raw_signal * genome.signal_strength

    def decode_signals(self, received_signals, genome):
        """
        Process received signals and produce an action modifier.
        Returns a 2D vector that modifies the agent's chosen action.
        """
        if not received_signals:
            return np.zeros(2)

        # Weighted average of received signals
        total_weight = 0.0
        combined_signal = np.zeros(Config.SIGNAL_DIM)
        for sig_vec, strength in received_signals:
            combined_signal += sig_vec * strength
            total_weight += strength

        if total_weight > 0:
            combined_signal /= total_weight

        # Decode to action modifier
        modifier = np.tanh(self.decode_W @ combined_signal + self.decode_b)
        return modifier * genome.listen_weight

    def learn_from_communication(self, received_signals, outcome_reward, lr=0.003):
        """
        Update encoder/decoder based on whether communication helped.
        If receiving signals led to good outcomes, strengthen decoding.
        """
        if not received_signals or abs(outcome_reward) < 0.01:
            return

        combined = np.zeros(Config.SIGNAL_DIM)
        for sig_vec, strength in received_signals:
            combined += sig_vec * strength

        # Simple reinforcement: if outcome was good, strengthen current decoding
        reward_signal = np.clip(outcome_reward, -1, 1)
        self.decode_W += lr * reward_signal * np.outer(
            np.ones(2) * reward_signal, combined
        )
        self.decode_W = np.clip(self.decode_W, -3, 3)

        if outcome_reward > 0:
            self.helpful_signals += 1

    def copy(self):
        new = AgentCommunicator(self.state_dim)
        new.encode_W = self.encode_W.copy()
        new.encode_b = self.encode_b.copy()
        new.decode_W = self.decode_W.copy()
        new.decode_b = self.decode_b.copy()
        return new


# ============================================================================
# COUNTERFACTUAL REASONING ENGINE (v3.0)
# ============================================================================

class CounterfactualEngine:
    """
    Enables agents to ask "what would have happened if I'd done something
    different?" by replaying past decisions with alternative actions through
    the consequence predictor.

    This creates regret-based learning: agents that discover they missed
    better alternatives adjust their future behavior.
    """

    def __init__(self):
        self.total_replays = 0
        self.total_regrets = 0
        self.regret_history = deque(maxlen=200)
        self.best_counterfactual_found = 0.0

    def analyze(self, causal_memory, consequence_predictor, genome):
        """
        Replay recent decisions with alternative actions.
        Returns regret signals that can modify future behavior.
        """
        if len(causal_memory) < 5:
            return []

        regrets = []
        memory = list(causal_memory)
        # Sample recent transitions to analyze
        indices = np.random.choice(
            len(memory),
            size=min(Config.COUNTERFACTUAL_REPLAYS, len(memory)),
            replace=False
        )

        for idx in indices:
            transition = memory[idx]
            actual_reward = transition.reward
            actual_value = transition.downstream_value

            # Generate counterfactual actions
            best_cf_score = actual_reward + actual_value
            best_cf_action = None

            for _ in range(genome.counterfactual_depth * 2):
                # What if I had done something different?
                cf_action = transition.action + np.random.randn(2) * 1.0
                cf_action = np.clip(cf_action, -2, 2)

                cf_pred = consequence_predictor.predict(transition.state, cf_action)
                cf_score = cf_pred['reward'] + cf_pred['state_value'] * 0.5

                if cf_score > best_cf_score:
                    best_cf_score = cf_score
                    best_cf_action = cf_action

            # Also test the opposite action
            opposite = -transition.action
            opp_pred = consequence_predictor.predict(transition.state, opposite)
            opp_score = opp_pred['reward'] + opp_pred['state_value'] * 0.5
            if opp_score > best_cf_score:
                best_cf_score = opp_score
                best_cf_action = opposite

            # Calculate regret
            regret = max(0, best_cf_score - (actual_reward + actual_value))
            if regret > 0 and best_cf_action is not None:
                regrets.append({
                    'state': transition.state,
                    'actual_action': transition.action,
                    'better_action': best_cf_action,
                    'regret': regret,
                    'improvement': best_cf_score - (actual_reward + actual_value)
                })
                transition.counterfactual_regret = regret
                self.total_regrets += 1

            self.total_replays += 1

        if regrets:
            max_regret = max(r['regret'] for r in regrets)
            self.best_counterfactual_found = max(
                self.best_counterfactual_found, max_regret
            )
            self.regret_history.append(np.mean([r['regret'] for r in regrets]))

        return regrets

    def get_regret_adjustment(self, state, proposed_action, regrets, genome):
        """
        Use regret from counterfactual analysis to adjust the proposed action.
        If similar states had high regret, nudge toward the better alternative.
        """
        if not regrets:
            return proposed_action

        # Find regrets from similar states
        best_adjustment = np.zeros(2)
        total_weight = 0.0

        for regret_entry in regrets:
            state_similarity = 1.0 / (1.0 + np.linalg.norm(
                np.resize(state, len(regret_entry['state'])) -
                regret_entry['state']
            ))
            if state_similarity > 0.3:
                weight = regret_entry['regret'] * state_similarity * genome.regret_sensitivity
                direction = regret_entry['better_action'] - regret_entry['actual_action']
                best_adjustment += direction * weight
                total_weight += weight

        if total_weight > 0:
            best_adjustment /= total_weight
            adjusted = proposed_action + best_adjustment * 0.3
            return np.clip(adjusted, -2, 2)

        return proposed_action

    def get_stats(self):
        avg_regret = np.mean(list(self.regret_history)) if self.regret_history else 0.0
        return {
            'total_replays': self.total_replays,
            'total_regrets': self.total_regrets,
            'avg_regret': avg_regret,
            'best_counterfactual': self.best_counterfactual_found
        }


# ============================================================================
# PERSISTENT KNOWLEDGE BANK (v3.0)
# ============================================================================

class KnowledgeEntry:
    """A single piece of learned knowledge."""

    def __init__(self, state_pattern, best_action, expected_reward,
                 danger_level, source_fitness, source_generation):
        self.state_pattern = np.array(state_pattern)
        self.best_action = np.array(best_action)
        self.expected_reward = expected_reward
        self.danger_level = danger_level
        self.source_fitness = source_fitness
        self.source_generation = source_generation
        self.times_used = 0
        self.times_helpful = 0

    def get_usefulness(self):
        if self.times_used == 0:
            return 0.5
        return self.times_helpful / self.times_used


class KnowledgeBank:
    """
    Shared knowledge repository that persists across agent lifetimes.
    Agents deposit wisdom when they die (or reproduce), and offspring
    can inherit accumulated knowledge -- enabling cultural evolution.
    """

    def __init__(self):
        self.entries = []
        self.total_deposits = 0
        self.total_withdrawals = 0
        self.total_helpful = 0
        self.generation_deposits = defaultdict(int)

    def deposit(self, agent_memory, agent_fitness, generation):
        """
        Extract knowledge from an agent's experience and store it.
        Called when an agent dies or reproduces.
        """
        if not agent_memory:
            return 0

        deposited = 0
        memory = list(agent_memory)

        # Extract the best experiences as knowledge
        sorted_mem = sorted(memory, key=lambda t: t.reward + t.downstream_value,
                            reverse=True)

        for transition in sorted_mem[:Config.WISDOM_TRANSFER_AMOUNT]:
            state_pattern = np.resize(transition.state, Config.KNOWLEDGE_ENTRY_DIM)
            entry = KnowledgeEntry(
                state_pattern=state_pattern,
                best_action=transition.action,
                expected_reward=transition.reward,
                danger_level=-transition.health_delta if transition.health_delta < 0 else 0,
                source_fitness=agent_fitness,
                source_generation=generation
            )
            self.entries.append(entry)
            deposited += 1

        # Also deposit danger knowledge (what to avoid)
        dangerous = [t for t in memory if t.health_delta < -2]
        for transition in dangerous[:5]:
            state_pattern = np.resize(transition.state, Config.KNOWLEDGE_ENTRY_DIM)
            entry = KnowledgeEntry(
                state_pattern=state_pattern,
                best_action=-transition.action,  # Opposite of what caused danger
                expected_reward=transition.reward,
                danger_level=-transition.health_delta,
                source_fitness=agent_fitness,
                source_generation=generation
            )
            self.entries.append(entry)
            deposited += 1

        # Prune if too large: keep most useful and most recent
        if len(self.entries) > Config.KNOWLEDGE_BANK_SIZE:
            self.entries.sort(
                key=lambda e: e.get_usefulness() * 0.5 + e.source_fitness * 0.3 +
                              (e.source_generation / max(generation, 1)) * 0.2,
                reverse=True
            )
            self.entries = self.entries[:Config.KNOWLEDGE_BANK_SIZE]

        self.total_deposits += deposited
        self.generation_deposits[generation] += deposited
        return deposited

    def withdraw(self, state, n=3):
        """
        Query the knowledge bank for relevant knowledge given current state.
        Returns the n most relevant entries.
        """
        if not self.entries:
            return []

        state_pattern = np.resize(state, Config.KNOWLEDGE_ENTRY_DIM)
        scored = []
        for entry in self.entries:
            similarity = 1.0 / (1.0 + np.linalg.norm(state_pattern - entry.state_pattern))
            relevance = similarity * (0.5 + entry.get_usefulness() * 0.5)
            scored.append((relevance, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for _, entry in scored[:n]:
            entry.times_used += 1
            self.total_withdrawals += 1
            results.append(entry)

        return results

    def report_outcome(self, entry, was_helpful):
        """Report whether a piece of knowledge was actually helpful."""
        if was_helpful:
            entry.times_helpful += 1
            self.total_helpful += 1

    def get_stats(self):
        avg_usefulness = np.mean([e.get_usefulness() for e in self.entries]) if self.entries else 0
        return {
            'total_entries': len(self.entries),
            'total_deposits': self.total_deposits,
            'total_withdrawals': self.total_withdrawals,
            'total_helpful': self.total_helpful,
            'avg_usefulness': avg_usefulness,
            'helpfulness_rate': self.total_helpful / max(self.total_withdrawals, 1)
        }


# ============================================================================
# THE FIELD (Universe / Environment)
# ============================================================================

class Field:
    """Dynamic energy field -- the universe in which agents live."""

    def __init__(self, size=None):
        self.size = size or Config.FIELD_SIZE
        self.grid = np.zeros((self.size, self.size))
        self.hotspots = []
        self.phase = 0
        self.step_count = 0
        self._generate_hotspots()
        self._refresh()

    def _generate_hotspots(self):
        self.hotspots = [
            (np.random.randint(5, self.size - 5), np.random.randint(5, self.size - 5))
            for _ in range(Config.HOTSPOT_COUNT)
        ]

    def _refresh(self):
        self.grid += Config.ENERGY_REGEN_RATE
        for hx, hy in self.hotspots:
            for dx in range(-5, 6):
                for dy in range(-5, 6):
                    x, y = (hx + dx) % self.size, (hy + dy) % self.size
                    dist = np.sqrt(dx**2 + dy**2)
                    if dist < 6:
                        self.grid[x][y] += 0.3 * np.exp(-dist / 2.5)
        from scipy.ndimage import uniform_filter
        self.grid = uniform_filter(self.grid, size=3) * (1 + Config.ENERGY_DIFFUSION)
        self.grid = np.clip(self.grid, 0, 10)

    def step(self):
        self.step_count += 1
        self._refresh()
        if np.random.random() < Config.HOTSPOT_SHIFT_RATE:
            idx = np.random.randint(len(self.hotspots))
            hx, hy = self.hotspots[idx]
            hx = (hx + np.random.randint(-3, 4)) % self.size
            hy = (hy + np.random.randint(-3, 4)) % self.size
            self.hotspots[idx] = (hx, hy)
        if self.phase >= 1:
            if np.random.random() < 0.05:
                idx = np.random.randint(len(self.hotspots))
                self.hotspots[idx] = (
                    np.random.randint(0, self.size),
                    np.random.randint(0, self.size)
                )
        if self.phase >= 3:
            if np.random.random() < 0.01:
                self.grid *= 0.3
        if self.phase >= 4:
            if np.random.random() < 0.005:
                self.grid = np.max(self.grid) - self.grid

    def consume_energy(self, x, y, amount=1.0):
        ix, iy = int(x) % self.size, int(y) % self.size
        available = self.grid[ix][iy]
        consumed = min(available, amount)
        self.grid[ix][iy] -= consumed
        return consumed

    def get_local_view(self, x, y, radius=None):
        radius = radius or Config.SENSOR_RADIUS
        view = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                ix = int(x + dx) % self.size
                iy = int(y + dy) % self.size
                view.append(self.grid[ix][iy])
        return np.array(view)

    def advance_curriculum(self):
        if self.phase < Config.CURRICULUM_PHASES - 1:
            self.phase += 1
            return True
        return False


# ============================================================================
# NOVELTY ARCHIVE
# ============================================================================

class NoveltyArchive:
    def __init__(self):
        self.archive = []
        self.k = Config.NOVELTY_K

    def compute_novelty(self, behavior_vector):
        if len(self.archive) < self.k:
            return 1.0
        distances = [
            np.linalg.norm(np.array(behavior_vector) - np.array(archived))
            for archived in self.archive
        ]
        distances.sort()
        return np.mean(distances[:self.k])

    def add(self, behavior_vector):
        self.archive.append(behavior_vector)
        if len(self.archive) > Config.NOVELTY_ARCHIVE_MAX:
            self.archive = self.archive[-Config.NOVELTY_ARCHIVE_MAX:]

    def get_diversity(self):
        if len(self.archive) < 2:
            return 0.0
        arr = np.array(self.archive)
        return np.mean(np.std(arr, axis=0))


# ============================================================================
# GODEL VALIDATION ENGINE
# ============================================================================

class GodelEngine:
    def __init__(self):
        self.modification_history = []
        self.accepted = 0
        self.rejected = 0

    def propose_modification(self, agent, field):
        snapshot = agent.genome.copy()
        baseline_scores = []
        for _ in range(Config.GODEL_TEST_EPISODES):
            score = self._evaluate_episode(agent, field)
            baseline_scores.append(score)
        agent.genome = snapshot.copy()
        self._apply_self_modification(agent)
        modified_scores = []
        for _ in range(Config.GODEL_TEST_EPISODES):
            score = self._evaluate_episode(agent, field)
            modified_scores.append(score)
        improvement = np.mean(modified_scores) - np.mean(baseline_scores)
        pooled_std = np.sqrt(
            (np.var(baseline_scores) + np.var(modified_scores)) / 2 + 1e-8
        )
        effect_size = improvement / (pooled_std + 1e-8)
        if effect_size > agent.genome.self_modify_threshold:
            self.accepted += 1
            self.modification_history.append({
                'type': 'accepted', 'improvement': improvement,
                'effect_size': effect_size
            })
            return True
        else:
            agent.genome = snapshot
            self.rejected += 1
            self.modification_history.append({
                'type': 'rejected', 'improvement': improvement,
                'effect_size': effect_size
            })
            return False

    def _evaluate_episode(self, agent, field):
        score = 0.0
        temp_health = agent.health
        for _ in range(20):
            state = field.get_local_view(agent.pos[0], agent.pos[1],
                                         agent.genome.sensor_radius)
            if len(state) != agent.genome.input_size:
                state = np.resize(state, agent.genome.input_size)
            outputs = agent.genome.activate(state)
            if len(outputs) >= 2:
                energy = field.consume_energy(
                    agent.pos[0] + outputs[0], agent.pos[1] + outputs[1], 0.5
                )
                score += energy
        agent.health = temp_health
        return score

    def _apply_self_modification(self, agent):
        mod_type = np.random.choice([
            'weight_perturbation', 'learning_rule_shift',
            'topology_tweak', 'sensor_adjust', 'decision_tune',
            'communication_tune'
        ])
        if mod_type == 'weight_perturbation':
            for conn in agent.genome.connections.values():
                if np.random.random() < 0.3:
                    conn.weight += np.random.randn() * 0.3
        elif mod_type == 'learning_rule_shift':
            for conn in agent.genome.connections.values():
                if np.random.random() < 0.2:
                    conn.A += np.random.randn() * 0.1
                    conn.B += np.random.randn() * 0.1
        elif mod_type == 'topology_tweak':
            if np.random.random() < 0.5:
                Mutator._add_connection(agent.genome)
            else:
                conns = list(agent.genome.connections.values())
                if conns:
                    c = np.random.choice(conns)
                    c.enabled = not c.enabled
        elif mod_type == 'sensor_adjust':
            agent.genome.sensor_radius = np.clip(
                agent.genome.sensor_radius + np.random.choice([-1, 0, 1]), 1, 4
            )
            new_input = (2 * agent.genome.sensor_radius + 1) ** 2
            agent.genome.input_size = new_input
        elif mod_type == 'decision_tune':
            agent.genome.acceptability_threshold += np.random.randn() * 0.05
            agent.genome.acceptability_threshold = np.clip(
                agent.genome.acceptability_threshold, 0.05, 0.8
            )
            agent.genome.caution_level += np.random.randn() * 0.1
            agent.genome.caution_level = np.clip(agent.genome.caution_level, 0, 1)
        elif mod_type == 'communication_tune':
            agent.genome.signal_strength += np.random.randn() * 0.1
            agent.genome.signal_strength = np.clip(agent.genome.signal_strength, 0, 1)
            agent.genome.signal_honesty += np.random.randn() * 0.1
            agent.genome.signal_honesty = np.clip(agent.genome.signal_honesty, 0, 1)

    def get_stats(self):
        total = self.accepted + self.rejected
        rate = self.accepted / total if total > 0 else 0
        return {
            'total_proposals': total, 'accepted': self.accepted,
            'rejected': self.rejected, 'acceptance_rate': rate
        }


# ============================================================================
# THE AGENT (v3.0 -- with Communication, Counterfactuals, Knowledge)
# ============================================================================

class Agent:
    """
    A self-sufficient, self-evolving neural agent with Decision Intelligence,
    Emergent Communication, Counterfactual Reasoning, and Knowledge Inheritance.
    """

    _next_id = 0

    def __init__(self, genome=None, pos=None, field_size=None):
        field_size = field_size or Config.FIELD_SIZE
        sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2

        self.id = Agent._next_id
        Agent._next_id += 1

        if genome is None:
            self.genome = Genome(input_size=sensor_dim, output_size=4)
        else:
            self.genome = genome

        self.pos = pos if pos is not None else np.array([
            np.random.uniform(0, field_size),
            np.random.uniform(0, field_size)
        ], dtype=float)

        self.health = Config.INITIAL_HEALTH
        self.age = 0
        self.total_energy = 0.0
        self.offspring_count = 0
        self.alive = True

        # Curiosity module
        self.world_model = WorldModel(sensor_dim, 2)
        self.curiosity_reward = 0.0

        # Behavioral characterization
        self.position_history = []
        self.energy_history = []
        self.action_history = []

        # Godel self-modification
        self.godel_cooldown = 0
        self.modifications_accepted = 0
        self.modifications_rejected = 0

        # Self-healing
        self.error_count = 0
        self.last_valid_genome = self.genome.copy()

        # Decision Intelligence (v2.0)
        self.decision_intel = DecisionIntelligence(sensor_dim)
        self.decisions_overridden = 0
        self.unacceptable_states_entered = 0
        self.unacceptable_states_avoided = 0

        # Communication (v3.0)
        self.communicator = AgentCommunicator(sensor_dim)
        self.signals_sent = 0
        self.signals_received_count = 0
        self.last_received_signals = []

        # Counterfactual Reasoning (v3.0)
        self.counterfactual_engine = CounterfactualEngine()
        self.recent_regrets = []
        self.total_regret = 0.0
        self.counterfactual_adjustments = 0

        # Knowledge (v3.0)
        self.knowledge_used = 0
        self.knowledge_helpful = 0

    def sense(self, field):
        view = field.get_local_view(self.pos[0], self.pos[1],
                                     self.genome.sensor_radius)
        expected_size = self.genome.input_size
        if len(view) != expected_size:
            view = np.resize(view, expected_size)
        return view

    def think_and_act(self, field, comm_channel, knowledge_bank):
        """
        The v3.0 agent loop:
        1. Sense the environment
        2. Receive and decode signals from other agents
        3. Consult the knowledge bank
        4. Neural network proposes an action
        5. Counterfactual reasoning adjusts based on past regrets
        6. Decision Intelligence evaluates consequences
        7. Communication modifier applied
        8. Execute the chosen action
        9. Broadcast signal if threshold met
        10. Record transition and learn
        """
        if not self.alive:
            return

        try:
            # 1. SENSE
            state = self.sense(field)
            prev_state = state.copy()
            health_before = self.health

            # 2. RECEIVE SIGNALS
            received = comm_channel.receive(self.pos, self.id)
            self.last_received_signals = received
            self.signals_received_count += len(received)
            comm_modifier = self.communicator.decode_signals(received, self.genome)

            # 3. CONSULT KNOWLEDGE BANK
            knowledge_entries = knowledge_bank.withdraw(state, n=2)
            knowledge_modifier = np.zeros(2)
            for entry in knowledge_entries:
                self.knowledge_used += 1
                # Blend knowledge suggestion into action
                knowledge_modifier += entry.best_action * 0.1
            if knowledge_entries:
                knowledge_modifier /= len(knowledge_entries)

            # 4. NEURAL NETWORK PROPOSES ACTION
            outputs = self.genome.activate(state.tolist())
            while len(outputs) < 4:
                outputs.append(0.0)

            nn_dx = np.clip(outputs[0] * 2, -2, 2)
            nn_dy = np.clip(outputs[1] * 2, -2, 2)
            eat_intensity = (outputs[2] + 1) / 2
            nn_action = np.array([nn_dx, nn_dy])

            # 5. COUNTERFACTUAL ADJUSTMENT
            adjusted_action = nn_action.copy()
            if self.recent_regrets and self.genome.regret_sensitivity > 0.1:
                adjusted_action = self.counterfactual_engine.get_regret_adjustment(
                    state, nn_action, self.recent_regrets, self.genome
                )
                if np.linalg.norm(adjusted_action - nn_action) > 0.1:
                    self.counterfactual_adjustments += 1

            # 6. DECISION INTELLIGENCE EVALUATES AND CHOOSES
            chosen_action, decision_eval = self.decision_intel.choose_best_action(
                state, self.genome, adjusted_action
            )

            # 7. APPLY COMMUNICATION MODIFIER
            final_action = chosen_action + comm_modifier * 0.3 + knowledge_modifier * 0.2
            final_action = np.clip(final_action, -2, 2)
            dx, dy = final_action[0], final_action[1]

            # Track if DI overrode the neural network
            if np.linalg.norm(chosen_action - nn_action) > 0.5:
                self.decisions_overridden += 1

            # 8. EXECUTE ACTION
            new_x = (self.pos[0] + dx) % field.size
            new_y = (self.pos[1] + dy) % field.size
            self.pos = np.array([new_x, new_y])

            energy_gained = field.consume_energy(
                self.pos[0], self.pos[1],
                eat_intensity * self.genome.metabolism_efficiency
            )
            self.health += energy_gained
            self.total_energy += energy_gained

            move_cost = Config.MOVEMENT_COST * (abs(dx) + abs(dy))
            think_cost = Config.THINKING_COST_PER_NODE * self.genome.get_complexity()
            signal_cost = Config.SIGNAL_COST if self.signals_sent > 0 else 0
            self.health -= (move_cost + think_cost + signal_cost)

            # 9. BROADCAST SIGNAL if conditions met
            if (energy_gained > self.genome.broadcast_threshold or
                    self.health < Config.INITIAL_HEALTH * 0.3):
                signal = self.communicator.encode_signal(state, self.genome)
                comm_channel.broadcast(self.pos, signal, self.genome.signal_strength, self.id)
                self.signals_sent += 1

            # 10. RECORD AND LEARN
            new_state = self.sense(field)
            is_acceptable = self.decision_intel.record_transition(
                state=prev_state, action=final_action,
                next_state=new_state, reward=energy_gained,
                health_before=health_before, health_after=self.health,
                age=self.age, genome=self.genome
            )

            if not is_acceptable:
                self.unacceptable_states_entered += 1
            elif decision_eval and not decision_eval.get('acceptable', True):
                self.unacceptable_states_avoided += 1

            # Learn from communication outcomes
            self.communicator.learn_from_communication(
                received, energy_gained - move_cost
            )

            # Report knowledge outcome
            for entry in knowledge_entries:
                knowledge_bank.report_outcome(entry, energy_gained > 0.1)
                if energy_gained > 0.1:
                    self.knowledge_helpful += 1

            # Hebbian meta-learning
            self.genome.apply_learning_rule()

            # Curiosity
            action_vec = np.array([dx, dy])
            pred_error = self.world_model.train(prev_state, action_vec, new_state)
            self.curiosity_reward += pred_error * self.genome.curiosity_drive

            # Counterfactual analysis (periodically)
            if self.age % Config.COUNTERFACTUAL_INTERVAL == 0 and self.age > 10:
                self.recent_regrets = self.counterfactual_engine.analyze(
                    self.decision_intel.causal_memory,
                    self.decision_intel.consequence_predictor,
                    self.genome
                )
                if self.recent_regrets:
                    self.total_regret += sum(r['regret'] for r in self.recent_regrets)

            # Record behavior
            self.position_history.append(self.pos.copy())
            self.energy_history.append(self.health)
            self.action_history.append([dx, dy])

            self.age += 1
            self.godel_cooldown = max(0, self.godel_cooldown - 1)

            if self.health <= 0:
                self.alive = False

            self.last_valid_genome = self.genome.copy()

        except Exception as e:
            self.error_count += 1
            self.genome = self.last_valid_genome.copy()
            if self.error_count > 10:
                self.alive = False

    def attempt_self_modification(self, field, godel_engine):
        if self.godel_cooldown > 0 or not self.alive:
            return False
        accepted = godel_engine.propose_modification(self, field)
        self.godel_cooldown = Config.GODEL_COOLDOWN
        if accepted:
            self.modifications_accepted += 1
        else:
            self.modifications_rejected += 1
        return accepted

    def get_behavior_vector(self):
        if not self.position_history:
            return [0] * 12
        positions = np.array(self.position_history)
        avg_pos = np.mean(positions, axis=0)
        pos_std = np.std(positions, axis=0)
        actions = np.array(self.action_history) if self.action_history else np.zeros((1, 2))
        avg_action = np.mean(actions, axis=0)
        action_std = np.std(actions, axis=0)
        dec_quality = self.decision_intel.get_decision_fitness()
        avoidance_rate = self.unacceptable_states_avoided / max(self.age, 1)
        comm_rate = self.signals_sent / max(self.age, 1)
        regret_rate = self.total_regret / max(self.age, 1)
        return (list(avg_pos) + list(pos_std) + list(avg_action) +
                list(action_std) + [dec_quality, avoidance_rate, comm_rate, regret_rate])

    def can_reproduce(self):
        return self.alive and self.health > Config.REPRODUCTION_THRESHOLD

    def get_fitness(self):
        """Multi-objective fitness including all v3.0 components."""
        survival_score = self.age / 100.0
        energy_score = self.total_energy / 50.0
        offspring_score = self.offspring_count * 2.0
        curiosity_score = self.curiosity_reward * Config.CURIOSITY_WEIGHT
        compression = self.world_model.get_compression_progress() * 5.0

        # Decision Intelligence fitness (v2.0)
        decision_score = self.decision_intel.get_decision_fitness() * Config.DECISION_WEIGHT * 10
        avoidance_bonus = self.unacceptable_states_avoided * 0.5
        unacceptable_penalty = self.unacceptable_states_entered * 0.3

        # Communication fitness (v3.0)
        comm_score = 0.0
        if self.signals_sent > 0:
            comm_score += self.communicator.helpful_signals * Config.COMM_WEIGHT
        if self.signals_received_count > 0:
            comm_score += min(self.signals_received_count * 0.05, 2.0)

        # Counterfactual reasoning fitness (v3.0)
        cf_score = 0.0
        if self.counterfactual_adjustments > 0:
            cf_score = min(self.counterfactual_adjustments * 0.2, 3.0)

        # Knowledge usage fitness (v3.0)
        knowledge_score = self.knowledge_helpful * 0.3

        return (survival_score + energy_score + offspring_score +
                curiosity_score + compression + decision_score +
                avoidance_bonus - unacceptable_penalty +
                comm_score + cf_score + knowledge_score)


# ============================================================================
# POPULATION MANAGER
# ============================================================================

class PopulationManager:
    def __init__(self):
        self.species_list = []
        self.next_species_id = 0
        self.generation = 0

    def speciate(self, agents):
        for sp in self.species_list:
            sp.members = []
        for agent in agents:
            placed = False
            for sp in self.species_list:
                if sp.is_compatible(agent.genome):
                    sp.members.append(agent.genome)
                    agent.genome.species_id = sp.id
                    placed = True
                    break
            if not placed:
                new_sp = Species(self.next_species_id, agent.genome)
                self.next_species_id += 1
                self.species_list.append(new_sp)
                agent.genome.species_id = new_sp.id
        self.species_list = [sp for sp in self.species_list if sp.members]
        for sp in self.species_list:
            sp.representative = np.random.choice(sp.members)
            sp.age += 1

    def select_and_reproduce(self, agents, target_size):
        if not agents:
            return []
        for sp in self.species_list:
            for genome in sp.members:
                genome.adjusted_fitness = genome.fitness / max(len(sp.members), 1)
        total_adj_fitness = sum(
            sum(g.adjusted_fitness for g in sp.members)
            for sp in self.species_list
        )
        new_genomes = []
        for sp in self.species_list:
            if not sp.members:
                continue
            sp_fitness = sum(g.adjusted_fitness for g in sp.members)
            if total_adj_fitness > 0:
                n_offspring = max(1, int(sp_fitness / total_adj_fitness * target_size))
            else:
                n_offspring = max(1, target_size // max(len(self.species_list), 1))
            sp.members.sort(key=lambda g: g.fitness, reverse=True)
            for i in range(min(Config.ELITISM_COUNT, len(sp.members))):
                new_genomes.append(sp.members[i].copy())
            for _ in range(n_offspring - min(Config.ELITISM_COUNT, len(sp.members))):
                if len(sp.members) >= 2 and np.random.random() < Config.CROSSOVER_RATE:
                    p1 = self._tournament_select(sp.members)
                    p2 = self._tournament_select(sp.members)
                    child = Mutator.crossover(p1, p2)
                else:
                    parent = self._tournament_select(sp.members)
                    child = parent.copy()
                child = Mutator.mutate(child)
                new_genomes.append(child)
        while len(new_genomes) > target_size:
            new_genomes.pop()
        while len(new_genomes) < target_size:
            new_genomes.append(Genome((2 * Config.SENSOR_RADIUS + 1) ** 2, 4))
        self.generation += 1
        return new_genomes

    def _tournament_select(self, genomes, k=3):
        contestants = np.random.choice(genomes, size=min(k, len(genomes)), replace=False)
        return max(contestants, key=lambda g: g.fitness)

    def check_stagnation(self):
        stagnant = []
        for sp in self.species_list:
            current_best = max((g.fitness for g in sp.members), default=0)
            if current_best > sp.best_fitness:
                sp.best_fitness = current_best
                sp.stagnation = 0
            else:
                sp.stagnation += 1
            if sp.stagnation > Config.STAGNATION_LIMIT:
                stagnant.append(sp)
        return stagnant


# ============================================================================
# SELF-EVALUATION & QUALITY CONTROL
# ============================================================================

class QualityController:
    def __init__(self):
        self.fitness_history = []
        self.diversity_history = []
        self.population_size_history = []
        self.species_count_history = []
        self.decision_quality_history = []
        self.comm_activity_history = []  # v3.0
        self.regret_history = []  # v3.0
        self.knowledge_history = []  # v3.0
        self.curriculum_phase = 0
        self.stagnation_counter = 0
        self.interventions = []

    def evaluate_generation(self, agents, novelty_archive, pop_manager,
                            comm_channel=None, knowledge_bank=None):
        if not agents:
            return {'status': 'CRITICAL', 'message': 'Population extinct!'}

        fitnesses = [a.get_fitness() for a in agents if a.alive]
        if not fitnesses:
            fitnesses = [0.0]

        best = max(fitnesses)
        avg = np.mean(fitnesses)
        diversity = novelty_archive.get_diversity()

        dec_qualities = [a.decision_intel.get_decision_fitness() for a in agents if a.alive]
        avg_dec_quality = np.mean(dec_qualities) if dec_qualities else 0.0

        # v3.0 metrics
        total_signals = sum(a.signals_sent for a in agents if a.alive)
        avg_regret = np.mean([a.total_regret for a in agents if a.alive]) if agents else 0
        knowledge_stats = knowledge_bank.get_stats() if knowledge_bank else {}

        self.fitness_history.append(best)
        self.diversity_history.append(diversity)
        self.population_size_history.append(len(agents))
        self.species_count_history.append(len(pop_manager.species_list))
        self.decision_quality_history.append(avg_dec_quality)
        self.comm_activity_history.append(total_signals)
        self.regret_history.append(avg_regret)
        self.knowledge_history.append(knowledge_stats.get('total_entries', 0))

        report = {
            'best_fitness': best,
            'avg_fitness': avg,
            'diversity': diversity,
            'population': len(agents),
            'species': len(pop_manager.species_list),
            'avg_decision_quality': avg_dec_quality,
            'total_signals': total_signals,
            'avg_regret': avg_regret,
            'knowledge_entries': knowledge_stats.get('total_entries', 0),
            'knowledge_helpfulness': knowledge_stats.get('helpfulness_rate', 0),
            'status': 'OK',
            'actions': []
        }

        if len(self.fitness_history) > Config.STAGNATION_LIMIT:
            recent = self.fitness_history[-Config.STAGNATION_LIMIT:]
            if max(recent) - min(recent) < 0.1:
                self.stagnation_counter += 1
                report['status'] = 'STAGNANT'
                report['actions'].append('increase_mutation')
                report['actions'].append('inject_immigrants')
                self.interventions.append(('stagnation_response', pop_manager.generation))
            else:
                self.stagnation_counter = 0

        if diversity < 0.1 and len(self.diversity_history) > 5:
            report['status'] = 'LOW_DIVERSITY'
            report['actions'].append('increase_novelty_pressure')
            self.interventions.append(('diversity_injection', pop_manager.generation))

        if len(self.fitness_history) > 20:
            recent_avg = np.mean(self.fitness_history[-10:])
            if recent_avg > Config.CURRICULUM_ADVANCE_THRESHOLD * (self.curriculum_phase + 1):
                report['actions'].append('advance_curriculum')

        return report


# ============================================================================
# GENESIS MAIN ENGINE (v3.0)
# ============================================================================

class GenesisEngine:
    """The master controller -- v3.0 with Communication, Counterfactuals, Knowledge."""

    def __init__(self):
        self.field = Field()
        self.agents = []
        self.pop_manager = PopulationManager()
        self.novelty_archive = NoveltyArchive()
        self.godel_engine = GodelEngine()
        self.quality_controller = QualityController()
        self.generation = 0
        self.checkpoints = {}
        self.stats_log = []

        # v3.0 shared systems
        self.comm_channel = CommunicationChannel()
        self.knowledge_bank = KnowledgeBank()

        sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
        for _ in range(Config.INITIAL_POPULATION):
            genome = Genome(input_size=sensor_dim, output_size=4)
            agent = Agent(genome=genome, field_size=self.field.size)
            self.agents.append(agent)

        print("=" * 70)
        print("  GENESIS v3.0: Self-Evolving Darwinian Godel Machine")
        print("  with Decision Intelligence, Communication, Counterfactuals")
        print("  and Persistent Knowledge Transfer")
        print("=" * 70)
        print(f"  Population: {len(self.agents)} agents")
        print(f"  Field: {self.field.size}x{self.field.size}")
        print(f"  Genome: {sensor_dim} inputs -> 4 outputs (NEAT topology)")
        print(f"  Features: Hebbian Meta-Learning | Curiosity | Novelty Search")
        print(f"            Godel Self-Modification | Speciation | Self-Healing")
        print(f"  v2.0: Causal Memory | Consequence Prediction | State Eval")
        print(f"         Acceptability Boundaries | Temporal Reasoning")
        print(f"  v3.0: Emergent Communication | Counterfactual Reasoning")
        print(f"         Persistent Knowledge Bank | Cultural Evolution")
        print("=" * 70)
        print()

    def run_generation(self):
        gen_start = time.time()
        self.generation += 1
        births = 0
        deaths = 0
        godel_attempts = 0
        total_overrides = 0
        total_unacceptable = 0
        total_avoided = 0
        total_cf_adjustments = 0

        for step in range(Config.STEPS_PER_GENERATION):
            self.field.step()
            self.comm_channel.step()

            for agent in self.agents:
                if agent.alive:
                    agent.think_and_act(self.field, self.comm_channel, self.knowledge_bank)

                    if agent.can_reproduce() and len(self.agents) < Config.MAX_POPULATION:
                        child_genome = agent.genome.copy()
                        child_genome = Mutator.mutate(child_genome)
                        child = Agent(
                            genome=child_genome,
                            pos=agent.pos + np.random.randn(2) * 2,
                            field_size=self.field.size
                        )
                        # Inherit decision intelligence
                        child.decision_intel = agent.decision_intel.copy()
                        # Inherit communication skills (v3.0)
                        child.communicator = agent.communicator.copy()
                        # Deposit parent knowledge to bank (v3.0)
                        if np.random.random() < Config.KNOWLEDGE_INHERIT_RATE:
                            self.knowledge_bank.deposit(
                                agent.decision_intel.causal_memory,
                                agent.get_fitness(), self.generation
                            )
                        self.agents.append(child)
                        agent.health -= Config.REPRODUCTION_THRESHOLD * 0.4
                        agent.offspring_count += 1
                        births += 1

            if step % 20 == 0:
                for agent in self.agents:
                    if (agent.alive and agent.godel_cooldown == 0 and
                            np.random.random() < 0.1):
                        agent.attempt_self_modification(self.field, self.godel_engine)
                        godel_attempts += 1

            # Handle deaths -- deposit knowledge before removal (v3.0)
            for agent in self.agents:
                if not agent.alive:
                    self.knowledge_bank.deposit(
                        agent.decision_intel.causal_memory,
                        agent.get_fitness(), self.generation
                    )

            before = len(self.agents)
            self.agents = [a for a in self.agents if a.alive]
            deaths += before - len(self.agents)

            if len(self.agents) < Config.MIN_POPULATION:
                sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
                for _ in range(Config.MIN_POPULATION - len(self.agents)):
                    genome = Genome(input_size=sensor_dim, output_size=4)
                    agent = Agent(genome=genome, field_size=self.field.size)
                    self.agents.append(agent)

        # Collect stats
        for agent in self.agents:
            total_overrides += agent.decisions_overridden
            total_unacceptable += agent.unacceptable_states_entered
            total_avoided += agent.unacceptable_states_avoided
            total_cf_adjustments += agent.counterfactual_adjustments

        # Evaluate
        for agent in self.agents:
            agent.genome.fitness = agent.get_fitness()
            bv = agent.get_behavior_vector()
            novelty = self.novelty_archive.compute_novelty(bv)
            agent.genome.fitness += novelty * Config.NOVELTY_WEIGHT
            if novelty > 0.5 or agent.genome.fitness > 1.0:
                self.novelty_archive.add(bv)

        self.pop_manager.speciate(self.agents)

        report = self.quality_controller.evaluate_generation(
            self.agents, self.novelty_archive, self.pop_manager,
            self.comm_channel, self.knowledge_bank
        )

        if 'advance_curriculum' in report['actions']:
            if self.field.advance_curriculum():
                print(f"  CURRICULUM ADVANCED to Phase {self.field.phase}")
        if 'increase_mutation' in report['actions']:
            for agent in self.agents:
                agent.genome.mutation_rate = min(0.8, agent.genome.mutation_rate * 1.5)
        if 'inject_immigrants' in report['actions']:
            sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
            for _ in range(3):
                genome = Genome(input_size=sensor_dim, output_size=4)
                agent = Agent(genome=genome, field_size=self.field.size)
                self.agents.append(agent)

        target_size = min(Config.MAX_POPULATION,
                          max(Config.MIN_POPULATION, len(self.agents)))
        new_genomes = self.pop_manager.select_and_reproduce(self.agents, target_size)

        self.agents = []
        for genome in new_genomes:
            agent = Agent(genome=genome, field_size=self.field.size)
            self.agents.append(agent)

        if self.generation % Config.CHECKPOINT_INTERVAL == 0:
            self.checkpoints[self.generation] = {
                'best_fitness': report['best_fitness'],
                'population': len(self.agents),
                'species': report['species']
            }

        gen_time = time.time() - gen_start
        godel_stats = self.godel_engine.get_stats()
        comm_stats = self.comm_channel.get_language_stats()
        kb_stats = self.knowledge_bank.get_stats()

        best_agent = max(self.agents, key=lambda a: a.genome.fitness) if self.agents else None
        best_complexity = best_agent.genome.get_complexity() if best_agent else 0
        best_hidden = sum(1 for n in best_agent.genome.nodes.values()
                          if n.type == NodeGene.HIDDEN) if best_agent else 0

        stats = {
            'generation': self.generation,
            'best_fitness': report['best_fitness'],
            'avg_fitness': report['avg_fitness'],
            'population': len(self.agents),
            'species': report['species'],
            'births': births,
            'deaths': deaths,
            'diversity': report['diversity'],
            'curriculum_phase': self.field.phase,
            'godel_attempts': godel_attempts,
            'godel_accepted': godel_stats['accepted'],
            'godel_rejected': godel_stats['rejected'],
            'best_complexity': best_complexity,
            'best_hidden_nodes': best_hidden,
            'status': report['status'],
            'time': gen_time,
            # Decision Intelligence (v2.0)
            'avg_decision_quality': report['avg_decision_quality'],
            'decisions_overridden': total_overrides,
            'unacceptable_entered': total_unacceptable,
            'unacceptable_avoided': total_avoided,
            'best_caution': best_agent.genome.caution_level if best_agent else 0,
            'best_accept_thresh': best_agent.genome.acceptability_threshold if best_agent else 0,
            'best_planning_depth': best_agent.genome.planning_depth if best_agent else 0,
            # Communication (v3.0)
            'total_signals': report['total_signals'],
            'total_broadcasts': self.comm_channel.total_broadcasts,
            'total_receptions': self.comm_channel.total_receptions,
            'language_diversity': comm_stats['diversity'],
            'vocab_size': comm_stats['vocab_size'],
            'best_honesty': best_agent.genome.signal_honesty if best_agent else 0,
            'best_listen_weight': best_agent.genome.listen_weight if best_agent else 0,
            # Counterfactual (v3.0)
            'cf_adjustments': total_cf_adjustments,
            'avg_regret': report['avg_regret'],
            'best_regret_sensitivity': best_agent.genome.regret_sensitivity if best_agent else 0,
            # Knowledge (v3.0)
            'knowledge_entries': kb_stats['total_entries'],
            'knowledge_deposits': kb_stats['total_deposits'],
            'knowledge_withdrawals': kb_stats['total_withdrawals'],
            'knowledge_helpfulness': kb_stats['helpfulness_rate'],
        }
        self.stats_log.append(stats)
        return stats

    def print_generation_report(self, stats):
        status_icon = {
            'OK': '+', 'STAGNANT': '!', 'LOW_DIVERSITY': '~', 'CRITICAL': 'X'
        }.get(stats['status'], '?')

        print(f"[Gen {stats['generation']:>4d}] {status_icon} "
              f"Fit={stats['best_fitness']:.1f}/{stats['avg_fitness']:.1f} "
              f"Pop={stats['population']} Sp={stats['species']} "
              f"DQ={stats['avg_decision_quality']:.2f} "
              f"Sig={stats['total_signals']} "
              f"CF={stats['cf_adjustments']} "
              f"KB={stats['knowledge_entries']} "
              f"({stats['time']:.1f}s)")

    def run(self, generations=None):
        generations = generations or Config.NUM_GENERATIONS
        print(f"\nStarting GENESIS v3.0 Evolution -- {generations} generations\n")

        try:
            for gen in range(generations):
                stats = self.run_generation()
                self.print_generation_report(stats)
                if (gen + 1) % 25 == 0:
                    self._print_detailed_report()
        except KeyboardInterrupt:
            print("\nEvolution interrupted by user.")

        print("\n" + "=" * 70)
        print("  GENESIS v3.0 EVOLUTION COMPLETE")
        print("=" * 70)
        self._print_final_report()
        self._generate_visualizations()
        return self.stats_log

    def _print_detailed_report(self):
        print("\n" + "-" * 70)
        print("  DETAILED ANALYSIS (v3.0)")
        print("-" * 70)

        if self.stats_log:
            recent = self.stats_log[-10:]
            print(f"  Fitness trend (last 10): "
                  f"{recent[0]['best_fitness']:.3f} -> {recent[-1]['best_fitness']:.3f}")
            print(f"  Decision quality trend: "
                  f"{recent[0]['avg_decision_quality']:.3f} -> "
                  f"{recent[-1]['avg_decision_quality']:.3f}")
            print(f"  Communication: {recent[-1]['total_broadcasts']} total broadcasts, "
                  f"vocab={recent[-1]['vocab_size']}")
            print(f"  Knowledge Bank: {recent[-1]['knowledge_entries']} entries, "
                  f"helpfulness={recent[-1]['knowledge_helpfulness']:.2f}")
            print(f"  Counterfactual adjustments: {recent[-1]['cf_adjustments']}")

        print(f"  Active species: {len(self.pop_manager.species_list)}")
        for sp in self.pop_manager.species_list[:5]:
            print(f"    Species {sp.id}: {len(sp.members)} members, "
                  f"best={sp.best_fitness:.3f}, age={sp.age}")

        if self.agents:
            honesty_vals = [a.genome.signal_honesty for a in self.agents]
            listen_vals = [a.genome.listen_weight for a in self.agents]
            regret_vals = [a.genome.regret_sensitivity for a in self.agents]
            print(f"  Evolved Communication:")
            print(f"    Avg Honesty: {np.mean(honesty_vals):.3f} "
                  f"(range {min(honesty_vals):.2f}-{max(honesty_vals):.2f})")
            print(f"    Avg Listen Weight: {np.mean(listen_vals):.3f}")
            print(f"  Evolved Counterfactual:")
            print(f"    Avg Regret Sensitivity: {np.mean(regret_vals):.3f}")

        gs = self.godel_engine.get_stats()
        print(f"  Godel Engine: {gs['total_proposals']} proposals, "
              f"{gs['acceptance_rate']:.1%} acceptance rate")
        print(f"  Novelty Archive: {len(self.novelty_archive.archive)} behaviors stored")
        print(f"  QC Interventions: {len(self.quality_controller.interventions)}")
        print("-" * 70 + "\n")

    def _print_final_report(self):
        print("\nFINAL REPORT (GENESIS v3.0)")
        print("-" * 60)

        if not self.stats_log:
            print("  No data collected.")
            return

        best_ever = max(s['best_fitness'] for s in self.stats_log)
        best_gen = max(self.stats_log, key=lambda s: s['best_fitness'])['generation']
        avg_final = self.stats_log[-1]['avg_fitness']
        total_births = sum(s['births'] for s in self.stats_log)
        total_deaths = sum(s['deaths'] for s in self.stats_log)
        total_overrides = sum(s['decisions_overridden'] for s in self.stats_log)
        total_avoided = sum(s['unacceptable_avoided'] for s in self.stats_log)
        total_entered = sum(s['unacceptable_entered'] for s in self.stats_log)
        total_cf = sum(s['cf_adjustments'] for s in self.stats_log)

        print(f"  Best Fitness Ever: {best_ever:.4f} (Generation {best_gen})")
        print(f"  Final Avg Fitness: {avg_final:.4f}")
        print(f"  Total Births: {total_births}")
        print(f"  Total Deaths: {total_deaths}")
        print(f"  Final Population: {len(self.agents)}")
        print(f"  Final Species: {len(self.pop_manager.species_list)}")
        print(f"  Curriculum Phase Reached: {self.field.phase}")

        gs = self.godel_engine.get_stats()
        print(f"  Godel Modifications: {gs['accepted']} accepted / "
              f"{gs['rejected']} rejected ({gs['acceptance_rate']:.1%})")
        print(f"  Novelty Behaviors Archived: {len(self.novelty_archive.archive)}")

        print(f"\n  DECISION INTELLIGENCE:")
        print(f"     Total Decision Overrides: {total_overrides}")
        print(f"     Unacceptable States Avoided: {total_avoided}")
        print(f"     Unacceptable States Entered: {total_entered}")
        if total_avoided + total_entered > 0:
            avoidance_rate = total_avoided / (total_avoided + total_entered)
            print(f"     Avoidance Success Rate: {avoidance_rate:.1%}")
        print(f"     Final Avg Decision Quality: "
              f"{self.stats_log[-1]['avg_decision_quality']:.3f}")

        print(f"\n  EMERGENT COMMUNICATION:")
        print(f"     Total Broadcasts: {self.comm_channel.total_broadcasts}")
        print(f"     Total Receptions: {self.comm_channel.total_receptions}")
        lang = self.comm_channel.get_language_stats()
        print(f"     Language Diversity: {lang['diversity']:.3f}")
        print(f"     Vocabulary Size: {lang['vocab_size']}")

        print(f"\n  COUNTERFACTUAL REASONING:")
        print(f"     Total CF Adjustments: {total_cf}")
        print(f"     Final Avg Regret: {self.stats_log[-1]['avg_regret']:.3f}")

        kb = self.knowledge_bank.get_stats()
        print(f"\n  KNOWLEDGE BANK:")
        print(f"     Total Entries: {kb['total_entries']}")
        print(f"     Total Deposits: {kb['total_deposits']}")
        print(f"     Total Withdrawals: {kb['total_withdrawals']}")
        print(f"     Helpfulness Rate: {kb['helpfulness_rate']:.1%}")

        if self.agents:
            best_agent = max(self.agents, key=lambda a: a.genome.fitness)
            print(f"\n  CHAMPION AGENT:")
            print(f"     Connections: {sum(1 for c in best_agent.genome.connections.values() if c.enabled)}")
            print(f"     Hidden Nodes: {sum(1 for n in best_agent.genome.nodes.values() if n.type == NodeGene.HIDDEN)}")
            print(f"     Curiosity Drive: {best_agent.genome.curiosity_drive:.4f}")
            print(f"     Mutation Rate: {best_agent.genome.mutation_rate:.4f}")
            print(f"     Metabolism Efficiency: {best_agent.genome.metabolism_efficiency:.4f}")
            print(f"     Caution Level: {best_agent.genome.caution_level:.4f}")
            print(f"     Acceptability Threshold: {best_agent.genome.acceptability_threshold:.4f}")
            print(f"     Planning Depth: {best_agent.genome.planning_depth}")
            print(f"     Signal Honesty: {best_agent.genome.signal_honesty:.4f}")
            print(f"     Listen Weight: {best_agent.genome.listen_weight:.4f}")
            print(f"     Regret Sensitivity: {best_agent.genome.regret_sensitivity:.4f}")
            print(f"     CF Depth: {best_agent.genome.counterfactual_depth}")

            a_vals = [c.A for c in best_agent.genome.connections.values()]
            b_vals = [c.B for c in best_agent.genome.connections.values()]
            c_vals = [c.C for c in best_agent.genome.connections.values()]
            if a_vals:
                print(f"     Evolved Learning Rule: A={np.mean(a_vals):.3f}, "
                      f"B={np.mean(b_vals):.3f}, C={np.mean(c_vals):.3f}")
                if abs(np.mean(a_vals)) > abs(np.mean(b_vals)) + abs(np.mean(c_vals)):
                    print(f"     -> Predominantly HEBBIAN learning discovered")
                elif abs(np.mean(c_vals)) > abs(np.mean(a_vals)):
                    print(f"     -> Post-synaptic driven learning discovered")
                else:
                    print(f"     -> NOVEL learning rule discovered")

        print("-" * 60)


    def _generate_visualizations(self):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            os.makedirs(Config.PLOT_DIR, exist_ok=True)
            if not self.stats_log:
                return

            gens = [s['generation'] for s in self.stats_log]
            best_fit = [s['best_fitness'] for s in self.stats_log]
            avg_fit = [s['avg_fitness'] for s in self.stats_log]
            diversity = [s['diversity'] for s in self.stats_log]
            populations = [s['population'] for s in self.stats_log]
            species = [s['species'] for s in self.stats_log]
            complexity = [s['best_complexity'] for s in self.stats_log]
            hidden = [s['best_hidden_nodes'] for s in self.stats_log]
            dec_quality = [s['avg_decision_quality'] for s in self.stats_log]
            overrides = [s['decisions_overridden'] for s in self.stats_log]
            avoided = [s['unacceptable_avoided'] for s in self.stats_log]
            entered = [s['unacceptable_entered'] for s in self.stats_log]
            caution = [s['best_caution'] for s in self.stats_log]
            accept_thresh = [s['best_accept_thresh'] for s in self.stats_log]
            plan_depth = [s['best_planning_depth'] for s in self.stats_log]
            total_signals = [s['total_signals'] for s in self.stats_log]
            vocab_size = [s['vocab_size'] for s in self.stats_log]
            honesty = [s['best_honesty'] for s in self.stats_log]
            listen_w = [s['best_listen_weight'] for s in self.stats_log]
            cf_adj = [s['cf_adjustments'] for s in self.stats_log]
            avg_regret = [s['avg_regret'] for s in self.stats_log]
            kb_entries = [s['knowledge_entries'] for s in self.stats_log]
            kb_help = [s['knowledge_helpfulness'] for s in self.stats_log]

            # === Figure 1: Main Dashboard (4x4) ===
            fig, axes = plt.subplots(4, 4, figsize=(28, 24))
            fig.suptitle('GENESIS v3.0: Self-Evolving Darwinian Godel Machine\n'
                         'Decision Intelligence | Communication | Counterfactuals | Knowledge',
                         fontsize=16, fontweight='bold')

            # Row 1: Core evolution metrics
            ax = axes[0, 0]
            ax.plot(gens, best_fit, 'b-', linewidth=2, label='Best')
            ax.plot(gens, avg_fit, 'r--', alpha=0.7, label='Avg')
            ax.fill_between(gens, avg_fit, best_fit, alpha=0.2, color='blue')
            ax.set_title('Fitness Evolution')
            ax.legend()
            ax.grid(True, alpha=0.3)

            ax = axes[0, 1]
            ax.plot(gens, populations, 'g-', linewidth=2, label='Pop')
            ax2 = ax.twinx()
            ax2.plot(gens, species, 'orange', linewidth=2, label='Species')
            ax.set_title('Population & Speciation')
            ax.set_ylabel('Population', color='green')
            ax2.set_ylabel('Species', color='orange')
            ax.grid(True, alpha=0.3)

            ax = axes[0, 2]
            ax.plot(gens, diversity, 'm-', linewidth=2)
            ax.set_title('Behavioral Diversity')
            ax.grid(True, alpha=0.3)

            ax = axes[0, 3]
            ax.plot(gens, complexity, 'c-', linewidth=2, label='Connections')
            ax2 = ax.twinx()
            ax2.plot(gens, hidden, 'red', linewidth=2, label='Hidden Nodes')
            ax.set_title('Brain Complexity')
            ax.set_ylabel('Connections', color='cyan')
            ax2.set_ylabel('Hidden Nodes', color='red')
            ax.grid(True, alpha=0.3)

            # Row 2: Decision Intelligence
            ax = axes[1, 0]
            ax.plot(gens, dec_quality, 'darkgreen', linewidth=2.5)
            ax.set_title('Decision Quality')
            ax.set_ylim(0, 1)
            ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
            ax.grid(True, alpha=0.3)

            ax = axes[1, 1]
            ax.plot(gens, avoided, 'green', linewidth=2, label='Avoided')
            ax.plot(gens, entered, 'red', linewidth=2, label='Entered')
            ax.fill_between(gens, entered, alpha=0.2, color='red')
            ax.fill_between(gens, avoided, alpha=0.2, color='green')
            ax.set_title('Unacceptable States')
            ax.legend()
            ax.grid(True, alpha=0.3)

            ax = axes[1, 2]
            ax.plot(gens, caution, 'purple', linewidth=2, label='Caution')
            ax.plot(gens, accept_thresh, 'orange', linewidth=2, label='Accept Thresh')
            ax2 = ax.twinx()
            ax2.plot(gens, plan_depth, 'teal', linewidth=2, linestyle='--', label='Plan Depth')
            ax.set_title('Evolved Decision Params')
            ax.legend(loc='upper left', fontsize=7)
            ax2.legend(loc='upper right', fontsize=7)
            ax.grid(True, alpha=0.3)

            ax = axes[1, 3]
            ax.plot(gens, overrides, 'darkorange', linewidth=2)
            ax.set_title('Decision Overrides')
            ax.grid(True, alpha=0.3)

            # Row 3: Communication (v3.0)
            ax = axes[2, 0]
            ax.plot(gens, total_signals, 'blue', linewidth=2)
            ax.set_title('Signal Activity')
            ax.set_ylabel('Signals per Generation')
            ax.grid(True, alpha=0.3)

            ax = axes[2, 1]
            ax.plot(gens, vocab_size, 'darkviolet', linewidth=2)
            ax.set_title('Emergent Vocabulary Size')
            ax.grid(True, alpha=0.3)

            ax = axes[2, 2]
            ax.plot(gens, honesty, 'green', linewidth=2, label='Honesty')
            ax.plot(gens, listen_w, 'blue', linewidth=2, label='Listen Weight')
            ax.set_title('Evolved Comm Params')
            ax.set_ylim(0, 1)
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Godel Engine
            ax = axes[2, 3]
            godel_accepted = [s['godel_accepted'] for s in self.stats_log]
            godel_rejected = [s['godel_rejected'] for s in self.stats_log]
            ax.plot(gens, godel_accepted, 'g-', linewidth=2, label='Accepted')
            ax.plot(gens, godel_rejected, 'r-', linewidth=2, label='Rejected')
            ax.set_title('Godel Self-Modification')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Row 4: Counterfactual & Knowledge (v3.0)
            ax = axes[3, 0]
            ax.plot(gens, cf_adj, 'crimson', linewidth=2)
            ax.set_title('Counterfactual Adjustments')
            ax.grid(True, alpha=0.3)

            ax = axes[3, 1]
            ax.plot(gens, avg_regret, 'darkred', linewidth=2)
            ax.set_title('Average Regret')
            ax.grid(True, alpha=0.3)

            ax = axes[3, 2]
            ax.plot(gens, kb_entries, 'darkblue', linewidth=2, label='Entries')
            ax.set_title('Knowledge Bank Size')
            ax.grid(True, alpha=0.3)

            ax = axes[3, 3]
            ax.plot(gens, kb_help, 'forestgreen', linewidth=2)
            ax.set_title('Knowledge Helpfulness Rate')
            ax.set_ylim(0, 1)
            ax.grid(True, alpha=0.3)

            for row in axes:
                for ax in row:
                    ax.set_xlabel('Generation', fontsize=8)

            plt.tight_layout()
            plot_path = os.path.join(Config.PLOT_DIR, 'genesis_v3_dashboard.png')
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"\n  Dashboard saved to: {plot_path}")

            # === Figure 2: Meta-Learning Analysis ===
            if self.agents:
                fig, axes = plt.subplots(2, 3, figsize=(18, 10))
                fig.suptitle('GENESIS v3.0: Evolved Parameters Distribution',
                             fontsize=14, fontweight='bold')

                all_A, all_B, all_C, all_lr = [], [], [], []
                for agent in self.agents:
                    for conn in agent.genome.connections.values():
                        all_A.append(conn.A)
                        all_B.append(conn.B)
                        all_C.append(conn.C)
                        all_lr.append(conn.lr)

                if all_A:
                    axes[0, 0].hist(all_A, bins=30, color='steelblue', alpha=0.7, label='A (Hebbian)')
                    axes[0, 0].hist(all_B, bins=30, color='coral', alpha=0.7, label='B (Pre-syn)')
                    axes[0, 0].hist(all_C, bins=30, color='green', alpha=0.7, label='C (Post-syn)')
                    axes[0, 0].set_title('Learning Rule Parameters')
                    axes[0, 0].legend()
                    axes[0, 0].grid(True, alpha=0.3)

                    axes[0, 1].hist(all_lr, bins=30, color='purple', alpha=0.7)
                    axes[0, 1].set_title('Learning Rates')
                    axes[0, 1].grid(True, alpha=0.3)

                    best_agent = max(self.agents, key=lambda a: a.genome.fitness)
                    weights = [c.weight for c in best_agent.genome.connections.values()]
                    axes[0, 2].hist(weights, bins=30, color='gold', alpha=0.7)
                    axes[0, 2].set_title('Champion Weight Distribution')
                    axes[0, 2].grid(True, alpha=0.3)

                # Communication params distribution
                honesty_all = [a.genome.signal_honesty for a in self.agents]
                listen_all = [a.genome.listen_weight for a in self.agents]
                strength_all = [a.genome.signal_strength for a in self.agents]
                axes[1, 0].hist(honesty_all, bins=20, color='green', alpha=0.7, label='Honesty')
                axes[1, 0].hist(listen_all, bins=20, color='blue', alpha=0.7, label='Listen')
                axes[1, 0].hist(strength_all, bins=20, color='red', alpha=0.7, label='Strength')
                axes[1, 0].set_title('Communication Params')
                axes[1, 0].legend()
                axes[1, 0].grid(True, alpha=0.3)

                # Counterfactual params distribution
                regret_all = [a.genome.regret_sensitivity for a in self.agents]
                cf_depth_all = [a.genome.counterfactual_depth for a in self.agents]
                axes[1, 1].hist(regret_all, bins=20, color='crimson', alpha=0.7)
                axes[1, 1].set_title('Regret Sensitivity Distribution')
                axes[1, 1].grid(True, alpha=0.3)

                # Decision params distribution
                caution_all = [a.genome.caution_level for a in self.agents]
                accept_all = [a.genome.acceptability_threshold for a in self.agents]
                axes[1, 2].hist(caution_all, bins=20, color='purple', alpha=0.7, label='Caution')
                axes[1, 2].hist(accept_all, bins=20, color='orange', alpha=0.7, label='Accept Thresh')
                axes[1, 2].set_title('Decision Params')
                axes[1, 2].legend()
                axes[1, 2].grid(True, alpha=0.3)

                plt.tight_layout()
                plot_path2 = os.path.join(Config.PLOT_DIR, 'genesis_v3_analysis.png')
                plt.savefig(plot_path2, dpi=150, bbox_inches='tight')
                plt.close()
                print(f"  Analysis saved to: {plot_path2}")

            # === Figure 3: Universe ===
            fig, ax = plt.subplots(figsize=(10, 10))
            im = ax.imshow(self.field.grid, cmap='magma', origin='lower',
                           extent=[0, self.field.size, 0, self.field.size])
            plt.colorbar(im, ax=ax, label='Energy Level')
            if self.agents:
                xs = [a.pos[1] for a in self.agents]
                ys = [a.pos[0] for a in self.agents]
                sizes = [max(10, a.genome.get_complexity() * 3) for a in self.agents]
                colors = [a.genome.fitness for a in self.agents]
                scatter = ax.scatter(xs, ys, c=colors, s=sizes, cmap='cool',
                                     edgecolors='white', linewidth=0.5, alpha=0.8)
                plt.colorbar(scatter, ax=ax, label='Agent Fitness')
            ax.set_title('GENESIS v3.0 Universe -- Final State',
                         fontsize=14, fontweight='bold')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            plot_path3 = os.path.join(Config.PLOT_DIR, 'genesis_v3_universe.png')
            plt.savefig(plot_path3, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"  Universe visualization saved to: {plot_path3}")

        except Exception as e:
            print(f"  Visualization error: {e}")
            traceback.print_exc()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Launch the GENESIS v3.0 system."""
    print()
    print("=" * 72)
    print("  GENESIS v3.0")
    print("  Generative Evolving Neural Engine for Self-Improving Systems")
    print("=" * 72)
    print()
    print("  13 Capabilities Active:")
    print("   1. Self-Sufficient Passive Learning")
    print("   2. Meta-Learning from Scratch")
    print("   3. Darwinian Self-Evolution (NEAT)")
    print("   4. Godel Machine Self-Rewriting")
    print("   5. Self-Controlled / Self-Coded")
    print("   6. Self-Instructed / Self-Quality-Checked / Self-Evaluated")
    print("   7. Self-Support System (error recovery, rollback)")
    print("   8. Zero-Data SOTA Methods (curiosity, novelty)")
    print("   9. Beyond the Builder (open-ended evolution)")
    print("  10. Decision Intelligence (cause/effect, temporal reasoning)")
    print("  11. Emergent Communication (evolved signaling)")
    print("  12. Counterfactual Reasoning (what-if, regret learning)")
    print("  13. Persistent Knowledge Transfer (cultural evolution)")
    print()
    print("  Agents learn what decisions lead to what outcomes.")
    print("  They predict consequences before acting.")
    print("  They communicate with evolved signals.")
    print("  They ask 'what if I had done something different?'")
    print("  They inherit wisdom from those who came before.")
    print("  They override their own neural network when wisdom says otherwise.")
    print()
    print("=" * 72)
    print()

    engine = GenesisEngine()
    stats = engine.run(generations=Config.NUM_GENERATIONS)

    print("\n  GENESIS v3.0 has evolved beyond its initial design.")
    print("  The agents developed their own language from nothing.")
    print("  They learned to reason about what could have been.")
    print("  They built a shared knowledge bank that outlives any individual.")
    print("  Intelligence emerged from evolution, experience, communication,")
    print("  reflection, and cultural inheritance.\n")

    return engine


if __name__ == "__main__":
    main()
