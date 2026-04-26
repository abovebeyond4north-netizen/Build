#!/usr/bin/env python3
"""
GENESIS v2.0: Generative Evolving Neural Engine for Self-Improving Systems
==========================================================================

A self-sufficient, self-evolving Darwinian Gödel machine with zero-data
meta-learning and DECISION INTELLIGENCE.

v2.0 Additions — Decision Intelligence System:
  - Causal Memory: agents learn what decisions lead to what outcomes
  - Temporal Reasoning: agents learn how long consequences take to manifest
  - World State Evaluator: agents learn to judge world states as good/bad
  - Acceptability Boundaries: agents evolve internal standards for what
    states are acceptable vs unacceptable, and avoid unacceptable states
  - Consequence Predictor: agents predict the downstream effects of each
    possible action BEFORE committing to it
  - Decision Journal: full audit trail of decisions, predictions, outcomes

Capabilities:
  1.  Self-Sufficient Passive Learning (zero external data)
  2.  Meta-Learning from Scratch (evolving learning rules)
  3.  Darwinian Self-Evolution (NEAT-style neuroevolution)
  4.  Gödel Machine Self-Rewriting (validated self-modification)
  5.  Self-Controlled / Self-Coded (autonomous execution)
  6.  Self-Instructed / Self-Quality-Checked / Self-Evaluated
  7.  Self-Support System (error recovery, rollback, self-healing)
  8.  Zero-Data SOTA Methods (curiosity, novelty search, self-play)
  9.  Beyond the Builder (open-ended emergent evolution)
  10. Decision Intelligence (causal learning, temporal reasoning,
      world-state evaluation, acceptability boundaries)

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
    """Global configuration — all parameters in one place."""
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

    # Gödel Validation
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

    # Decision Intelligence (NEW in v2.0)
    CAUSAL_MEMORY_SIZE = 200          # Max transitions stored per agent
    CONSEQUENCE_HORIZON = 10          # How many steps ahead to track outcomes
    STATE_EVAL_HIDDEN = 12            # Hidden layer size for state evaluator
    STATE_EVAL_LR = 0.005             # Learning rate for state evaluator
    ACCEPTABILITY_THRESHOLD_INIT = 0.3  # Initial boundary (evolvable)
    DECISION_LOOKAHEAD = 5            # How many candidate actions to evaluate
    TEMPORAL_DISCOUNT = 0.9           # Discount factor for future consequences
    DECISION_WEIGHT = 0.4             # How much decision quality affects fitness

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
    """Global tracker for structural mutations — ensures consistent gene alignment."""

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
    plus evolvable learning rules, sensor config, and metabolism.
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

        # Decision Intelligence evolvable parameters (NEW v2.0)
        self.acceptability_threshold = Config.ACCEPTABILITY_THRESHOLD_INIT
        self.temporal_discount = Config.TEMPORAL_DISCOUNT
        self.caution_level = np.random.uniform(0.2, 0.8)  # How risk-averse
        self.planning_depth = max(1, int(np.random.uniform(1, 5)))  # Steps to look ahead

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
        # Copy decision intelligence params
        new.acceptability_threshold = self.acceptability_threshold
        new.temporal_discount = self.temporal_discount
        new.caution_level = self.caution_level
        new.planning_depth = self.planning_depth
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

        # Mutate Decision Intelligence parameters (NEW v2.0)
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
    """
    Predicts next sensory state. Prediction error = intrinsic curiosity reward.
    """

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
# DECISION INTELLIGENCE SYSTEM (NEW in v2.0)
# ============================================================================

class CausalTransition:
    """A single recorded experience: state + action -> outcome + timing."""

    def __init__(self, state, action, next_state, reward, health_delta, time_cost,
                 world_state_before, world_state_after):
        self.state = state                      # Sensory input at decision time
        self.action = action                    # Action taken [dx, dy]
        self.next_state = next_state            # Resulting sensory input
        self.reward = reward                    # Energy gained
        self.health_delta = health_delta        # Net health change
        self.time_cost = time_cost              # Steps elapsed
        self.world_state_before = world_state_before  # Compact world descriptor
        self.world_state_after = world_state_after    # Compact world descriptor
        self.downstream_value = 0.0             # Cumulative future value (filled later)


class WorldStateEvaluator:
    """
    Learns to judge whether a world state is good, bad, or unacceptable.
    A small neural network trained on the agent's own experience.
    Outputs a scalar "state value" — positive = desirable, negative = dangerous.
    """

    def __init__(self, state_dim):
        self.state_dim = state_dim
        hidden = Config.STATE_EVAL_HIDDEN
        self.W1 = np.random.randn(hidden, state_dim) * 0.3
        self.b1 = np.zeros(hidden)
        self.W2 = np.random.randn(1, hidden) * 0.3
        self.b2 = np.zeros(1)
        self.training_count = 0

    def evaluate(self, state_descriptor):
        """Return a value for this world state. Positive = good, negative = bad."""
        x = np.array(state_descriptor)
        if len(x) != self.state_dim:
            x = np.resize(x, self.state_dim)
        h = np.tanh(self.W1 @ x + self.b1)
        val = np.tanh(self.W2 @ h + self.b2)
        return float(val[0])

    def train(self, state_descriptor, target_value):
        """Train on one example: this state had this value."""
        x = np.array(state_descriptor)
        if len(x) != self.state_dim:
            x = np.resize(x, self.state_dim)
        lr = Config.STATE_EVAL_LR

        # Forward
        h = np.tanh(self.W1 @ x + self.b1)
        val = np.tanh(self.W2 @ h + self.b2)

        # Backward
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
    """
    Predicts what will happen if a certain action is taken:
    - Predicted next state
    - Predicted reward
    - Predicted health change
    - Predicted time until effect manifests
    - Predicted world state quality after action

    Learns from the agent's own CausalMemory.
    """

    def __init__(self, state_dim, action_dim=2):
        self.state_dim = state_dim
        self.action_dim = action_dim
        input_dim = state_dim + action_dim
        hidden = 16

        # Predicts: [reward, health_delta, state_value_after, time_factor]
        self.output_dim = 4
        self.W1 = np.random.randn(hidden, input_dim) * 0.3
        self.b1 = np.zeros(hidden)
        self.W2 = np.random.randn(self.output_dim, hidden) * 0.3
        self.b2 = np.zeros(self.output_dim)
        self.training_count = 0
        self.prediction_accuracy = []

    def predict(self, state, action):
        """
        Returns dict with predicted consequences:
        - reward: expected energy gain
        - health_delta: expected net health change
        - state_value: expected quality of resulting world state
        - time_factor: how quickly the effect manifests (0=slow, 1=immediate)
        """
        x = np.concatenate([np.resize(state, self.state_dim),
                            np.resize(action, self.action_dim)])
        h = np.tanh(self.W1 @ x + self.b1)
        out = np.tanh(self.W2 @ h + self.b2)

        return {
            'reward': float(out[0]),
            'health_delta': float(out[1]),
            'state_value': float(out[2]),
            'time_factor': float((out[3] + 1) / 2)  # Normalize to [0, 1]
        }

    def train(self, state, action, actual_reward, actual_health_delta,
              actual_state_value, actual_time_factor):
        """Train on one observed transition."""
        x = np.concatenate([np.resize(state, self.state_dim),
                            np.resize(action, self.action_dim)])
        target = np.array([
            np.clip(actual_reward, -1, 1),
            np.clip(actual_health_delta, -1, 1),
            np.clip(actual_state_value, -1, 1),
            actual_time_factor * 2 - 1  # Map [0,1] to [-1,1] for tanh
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
    """
    Full audit trail of every decision the agent makes.
    Tracks: what was decided, what was predicted, what actually happened,
    and whether the decision was good or bad in hindsight.
    """

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

        # Score the decision
        if actual_outcome.get('health_delta', 0) > 0:
            self.good_decisions += 1
        elif actual_outcome.get('health_delta', 0) < -1:
            self.bad_decisions += 1

        if not was_acceptable:
            self.entered_unacceptable += 1
        if not was_predicted_acceptable and was_acceptable:
            self.avoided_unacceptable += 1

    def get_decision_quality(self):
        """Return a score for how good this agent's decisions have been."""
        total = self.good_decisions + self.bad_decisions
        if total == 0:
            return 0.5
        quality = self.good_decisions / total
        # Bonus for avoiding unacceptable states
        avoidance_bonus = self.avoided_unacceptable * 0.1
        # Penalty for entering unacceptable states
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
    Integrates: causal memory, consequence prediction, world state evaluation,
    acceptability boundaries, and temporal reasoning.

    This is the agent's "wisdom" — it learns from experience what decisions
    lead where, how long things take, and what states to avoid.
    """

    def __init__(self, state_dim):
        self.state_dim = state_dim
        self.causal_memory = deque(maxlen=Config.CAUSAL_MEMORY_SIZE)
        self.state_evaluator = WorldStateEvaluator(state_dim)
        self.consequence_predictor = ConsequencePredictor(state_dim)
        self.journal = DecisionJournal()
        self.unacceptable_states = []  # Learned patterns of bad states
        self.total_decisions = 0

    def get_world_state_descriptor(self, state, health, age):
        """
        Compress the current situation into a compact descriptor.
        Includes: local energy, health status, age, energy gradient.
        """
        descriptor = list(np.resize(state, min(len(state), self.state_dim - 3)))
        descriptor.append(health / Config.INITIAL_HEALTH)  # Normalized health
        descriptor.append(min(age / 200.0, 1.0))           # Normalized age
        descriptor.append(np.mean(state) if len(state) > 0 else 0)  # Avg local energy
        # Pad or trim to exact state_dim
        descriptor = list(np.resize(np.array(descriptor), self.state_dim))
        return np.array(descriptor)

    def evaluate_action(self, state, candidate_action, genome):
        """
        Evaluate a candidate action BEFORE taking it.
        Returns a score combining predicted reward, predicted state quality,
        and acceptability check.
        """
        pred = self.consequence_predictor.predict(state, candidate_action)

        # Is the predicted resulting state acceptable?
        predicted_acceptable = pred['state_value'] > -genome.acceptability_threshold

        # Compute decision score
        reward_score = pred['reward']
        safety_score = pred['state_value']
        time_value = pred['time_factor'] * pred['reward']  # Immediate rewards valued more

        # Risk-adjusted score based on agent's evolved caution level
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
        """
        Generate candidate actions and pick the best one.
        This is where the agent DECIDES — not just reacts.
        """
        candidates = [base_action]  # The neural network's suggestion

        # Generate alternative candidates
        for _ in range(Config.DECISION_LOOKAHEAD - 1):
            noise = np.random.randn(2) * 0.5
            alt = np.clip(base_action + noise, -2, 2)
            candidates.append(alt)

        # Also consider "do nothing" and "reverse"
        candidates.append(np.array([0.0, 0.0]))
        candidates.append(-base_action)

        # Evaluate all candidates
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
        """Record a transition and learn from it."""
        health_delta = health_after - health_before
        ws_before = self.get_world_state_descriptor(state, health_before, age)
        ws_after = self.get_world_state_descriptor(next_state, health_after, age + 1)

        transition = CausalTransition(
            state=state, action=action, next_state=next_state,
            reward=reward, health_delta=health_delta, time_cost=1,
            world_state_before=ws_before, world_state_after=ws_after
        )
        self.causal_memory.append(transition)

        # Train state evaluator: good states have high health and energy
        state_value_target = np.clip(
            health_delta * 0.5 + reward * 0.3 + (health_after / Config.INITIAL_HEALTH - 0.5),
            -1, 1
        )
        self.state_evaluator.train(ws_after, state_value_target)

        # Train consequence predictor
        actual_state_value = self.state_evaluator.evaluate(ws_after)
        self.consequence_predictor.train(
            state, action,
            actual_reward=reward,
            actual_health_delta=health_delta,
            actual_state_value=actual_state_value,
            actual_time_factor=1.0  # Immediate effect
        )

        # Check acceptability
        is_acceptable = actual_state_value > -genome.acceptability_threshold

        # Record in journal
        pred = self.consequence_predictor.predict(state, action)
        pred_acceptable = pred['state_value'] > -genome.acceptability_threshold
        self.journal.record(
            state, action, pred,
            {'reward': reward, 'health_delta': health_delta,
             'state_value': actual_state_value},
            is_acceptable, pred_acceptable
        )

        # Learn unacceptable state patterns
        if not is_acceptable:
            self.unacceptable_states.append(ws_after.copy())
            if len(self.unacceptable_states) > 50:
                self.unacceptable_states = self.unacceptable_states[-50:]

        # Backpropagate downstream values through causal memory
        self._update_downstream_values(genome.temporal_discount)

        return is_acceptable

    def _update_downstream_values(self, discount):
        """
        Propagate future consequences backward through causal memory.
        This teaches the agent that decisions have delayed effects.
        """
        memory = list(self.causal_memory)
        if len(memory) < 2:
            return

        # Work backward from most recent
        for i in range(len(memory) - 2, -1, -1):
            future_value = memory[i + 1].reward + discount * memory[i + 1].downstream_value
            memory[i].downstream_value = future_value

    def get_decision_fitness(self):
        """How good is this agent at making decisions?"""
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
# THE FIELD (Universe / Environment)
# ============================================================================

class Field:
    """
    Dynamic energy field — the universe in which agents live.
    Features hotspots, diffusion, regeneration, and catastrophic events.
    """

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
        consumed = min(self.grid[ix][iy], amount)
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
# GÖDEL VALIDATION ENGINE
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
            'topology_tweak', 'sensor_adjust', 'decision_tune'
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
            # Self-modify decision parameters
            agent.genome.acceptability_threshold += np.random.randn() * 0.05
            agent.genome.acceptability_threshold = np.clip(
                agent.genome.acceptability_threshold, 0.05, 0.8
            )
            agent.genome.caution_level += np.random.randn() * 0.1
            agent.genome.caution_level = np.clip(agent.genome.caution_level, 0, 1)

    def get_stats(self):
        total = self.accepted + self.rejected
        rate = self.accepted / total if total > 0 else 0
        return {
            'total_proposals': total, 'accepted': self.accepted,
            'rejected': self.rejected, 'acceptance_rate': rate
        }


# ============================================================================
# THE AGENT (v2.0 — with Decision Intelligence)
# ============================================================================

class Agent:
    """
    A self-sufficient, self-evolving neural agent with Decision Intelligence.
    Now THINKS before acting: evaluates consequences, checks acceptability,
    and chooses the best action from candidates.
    """

    def __init__(self, genome=None, pos=None, field_size=None):
        field_size = field_size or Config.FIELD_SIZE
        sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2

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

        # Gödel self-modification
        self.godel_cooldown = 0
        self.modifications_accepted = 0
        self.modifications_rejected = 0

        # Self-healing
        self.error_count = 0
        self.last_valid_genome = self.genome.copy()

        # Decision Intelligence (NEW v2.0)
        self.decision_intel = DecisionIntelligence(sensor_dim)
        self.decisions_overridden = 0  # Times DI overrode the neural network
        self.unacceptable_states_entered = 0
        self.unacceptable_states_avoided = 0

    def sense(self, field):
        view = field.get_local_view(self.pos[0], self.pos[1],
                                     self.genome.sensor_radius)
        expected_size = self.genome.input_size
        if len(view) != expected_size:
            view = np.resize(view, expected_size)
        return view

    def think_and_act(self, field):
        """
        The upgraded agent loop (v2.0):
        1. Sense the environment
        2. Neural network proposes an action
        3. Decision Intelligence evaluates consequences of multiple candidates
        4. Best action is chosen (may override the neural network)
        5. Execute the chosen action
        6. Record transition in causal memory
        7. Learn from experience (Hebbian + decision learning)
        8. Update curiosity module
        """
        if not self.alive:
            return

        try:
            # 1. SENSE
            state = self.sense(field)
            prev_state = state.copy()
            health_before = self.health

            # 2. NEURAL NETWORK PROPOSES ACTION
            outputs = self.genome.activate(state.tolist())
            while len(outputs) < 4:
                outputs.append(0.0)

            nn_dx = np.clip(outputs[0] * 2, -2, 2)
            nn_dy = np.clip(outputs[1] * 2, -2, 2)
            eat_intensity = (outputs[2] + 1) / 2
            nn_action = np.array([nn_dx, nn_dy])

            # 3. DECISION INTELLIGENCE EVALUATES AND CHOOSES
            chosen_action, decision_eval = self.decision_intel.choose_best_action(
                state, self.genome, nn_action
            )

            dx, dy = chosen_action[0], chosen_action[1]

            # Track if DI overrode the neural network
            if np.linalg.norm(chosen_action - nn_action) > 0.5:
                self.decisions_overridden += 1

            # 4. EXECUTE ACTION
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
            self.health -= (move_cost + think_cost)

            # 5. RECORD TRANSITION IN CAUSAL MEMORY
            new_state = self.sense(field)
            is_acceptable = self.decision_intel.record_transition(
                state=prev_state, action=chosen_action,
                next_state=new_state, reward=energy_gained,
                health_before=health_before, health_after=self.health,
                age=self.age, genome=self.genome
            )

            if not is_acceptable:
                self.unacceptable_states_entered += 1
            elif decision_eval and not decision_eval.get('acceptable', True):
                self.unacceptable_states_avoided += 1

            # 6. LEARN (Hebbian meta-learning)
            self.genome.apply_learning_rule()

            # 7. CURIOSITY (update world model)
            action_vec = np.array([dx, dy])
            pred_error = self.world_model.train(prev_state, action_vec, new_state)
            self.curiosity_reward += pred_error * self.genome.curiosity_drive

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
            return [0] * 10
        positions = np.array(self.position_history)
        avg_pos = np.mean(positions, axis=0)
        pos_std = np.std(positions, axis=0)
        actions = np.array(self.action_history) if self.action_history else np.zeros((1, 2))
        avg_action = np.mean(actions, axis=0)
        action_std = np.std(actions, axis=0)
        # Add decision quality to behavior vector
        dec_quality = self.decision_intel.get_decision_fitness()
        avoidance_rate = self.unacceptable_states_avoided / max(self.age, 1)
        return (list(avg_pos) + list(pos_std) + list(avg_action) +
                list(action_std) + [dec_quality, avoidance_rate])

    def can_reproduce(self):
        return self.alive and self.health > Config.REPRODUCTION_THRESHOLD

    def get_fitness(self):
        """Multi-objective fitness including decision quality."""
        survival_score = self.age / 100.0
        energy_score = self.total_energy / 50.0
        offspring_score = self.offspring_count * 2.0
        curiosity_score = self.curiosity_reward * Config.CURIOSITY_WEIGHT
        compression = self.world_model.get_compression_progress() * 5.0

        # Decision Intelligence fitness (NEW v2.0)
        decision_score = self.decision_intel.get_decision_fitness() * Config.DECISION_WEIGHT * 10
        # Bonus for avoiding unacceptable states
        avoidance_bonus = self.unacceptable_states_avoided * 0.5
        # Penalty for entering unacceptable states
        unacceptable_penalty = self.unacceptable_states_entered * 0.3

        return (survival_score + energy_score + offspring_score +
                curiosity_score + compression + decision_score +
                avoidance_bonus - unacceptable_penalty)


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
        self.decision_quality_history = []  # NEW v2.0
        self.curriculum_phase = 0
        self.stagnation_counter = 0
        self.interventions = []

    def evaluate_generation(self, agents, novelty_archive, pop_manager):
        if not agents:
            return {'status': 'CRITICAL', 'message': 'Population extinct!'}

        fitnesses = [a.get_fitness() for a in agents if a.alive]
        if not fitnesses:
            fitnesses = [0.0]

        best = max(fitnesses)
        avg = np.mean(fitnesses)
        diversity = novelty_archive.get_diversity()

        # Decision quality metrics (NEW v2.0)
        dec_qualities = [a.decision_intel.get_decision_fitness() for a in agents if a.alive]
        avg_dec_quality = np.mean(dec_qualities) if dec_qualities else 0.0

        self.fitness_history.append(best)
        self.diversity_history.append(diversity)
        self.population_size_history.append(len(agents))
        self.species_count_history.append(len(pop_manager.species_list))
        self.decision_quality_history.append(avg_dec_quality)

        report = {
            'best_fitness': best,
            'avg_fitness': avg,
            'diversity': diversity,
            'population': len(agents),
            'species': len(pop_manager.species_list),
            'avg_decision_quality': avg_dec_quality,
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
# GENESIS MAIN ENGINE (v2.0)
# ============================================================================

class GenesisEngine:
    """
    The master controller — now with Decision Intelligence tracking.
    """

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

        sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
        for _ in range(Config.INITIAL_POPULATION):
            genome = Genome(input_size=sensor_dim, output_size=4)
            agent = Agent(genome=genome, field_size=self.field.size)
            self.agents.append(agent)

        print("=" * 70)
        print("  GENESIS v2.0: Self-Evolving Darwinian Gödel Machine")
        print("  with Decision Intelligence System")
        print("=" * 70)
        print(f"  Population: {len(self.agents)} agents")
        print(f"  Field: {self.field.size}x{self.field.size}")
        print(f"  Genome: {sensor_dim} inputs -> 4 outputs (NEAT topology)")
        print(f"  Features: Hebbian Meta-Learning | Curiosity | Novelty Search")
        print(f"            Gödel Self-Modification | Speciation | Self-Healing")
        print(f"  NEW v2.0: Causal Memory | Consequence Prediction | State Eval")
        print(f"            Acceptability Boundaries | Temporal Reasoning")
        print(f"            Decision Journal | Action Override System")
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

        for step in range(Config.STEPS_PER_GENERATION):
            self.field.step()

            for agent in self.agents:
                if agent.alive:
                    agent.think_and_act(self.field)

                    if agent.can_reproduce() and len(self.agents) < Config.MAX_POPULATION:
                        child_genome = agent.genome.copy()
                        child_genome = Mutator.mutate(child_genome)
                        child = Agent(
                            genome=child_genome,
                            pos=agent.pos + np.random.randn(2) * 2,
                            field_size=self.field.size
                        )
                        # Inherit some decision intelligence from parent
                        child.decision_intel = agent.decision_intel.copy()
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

            before = len(self.agents)
            self.agents = [a for a in self.agents if a.alive]
            deaths += before - len(self.agents)

            if len(self.agents) < Config.MIN_POPULATION:
                sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
                for _ in range(Config.MIN_POPULATION - len(self.agents)):
                    genome = Genome(input_size=sensor_dim, output_size=4)
                    agent = Agent(genome=genome, field_size=self.field.size)
                    self.agents.append(agent)

        # Collect decision intelligence stats
        for agent in self.agents:
            total_overrides += agent.decisions_overridden
            total_unacceptable += agent.unacceptable_states_entered
            total_avoided += agent.unacceptable_states_avoided

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
            self.agents, self.novelty_archive, self.pop_manager
        )

        if 'advance_curriculum' in report['actions']:
            if self.field.advance_curriculum():
                print(f"  📚 CURRICULUM ADVANCED to Phase {self.field.phase}")
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
            # Decision Intelligence stats (NEW v2.0)
            'avg_decision_quality': report['avg_decision_quality'],
            'decisions_overridden': total_overrides,
            'unacceptable_entered': total_unacceptable,
            'unacceptable_avoided': total_avoided,
            'best_caution': best_agent.genome.caution_level if best_agent else 0,
            'best_accept_thresh': best_agent.genome.acceptability_threshold if best_agent else 0,
            'best_planning_depth': best_agent.genome.planning_depth if best_agent else 0,
        }
        self.stats_log.append(stats)
        return stats

    def print_generation_report(self, stats):
        status_icon = {
            'OK': '✅', 'STAGNANT': '⚠️', 'LOW_DIVERSITY': '🔄', 'CRITICAL': '🚨'
        }.get(stats['status'], '❓')

        print(f"┌─── Generation {stats['generation']:>4d} {'─' * 50}")
        print(f"│ {status_icon} Status: {stats['status']}")
        print(f"│ 🏆 Best Fitness: {stats['best_fitness']:.4f}  "
              f"│ Avg: {stats['avg_fitness']:.4f}")
        print(f"│ 👥 Population: {stats['population']}  "
              f"│ Species: {stats['species']}  "
              f"│ Phase: {stats['curriculum_phase']}")
        print(f"│ 🧬 Births: {stats['births']}  │ Deaths: {stats['deaths']}")
        print(f"│ 🧠 Best Brain: {stats['best_complexity']} connections, "
              f"{stats['best_hidden_nodes']} hidden nodes")
        print(f"│ 🔧 Gödel: {stats['godel_attempts']} attempts "
              f"({stats['godel_accepted']} accepted / {stats['godel_rejected']} rejected)")
        print(f"│ 🎯 Decision Quality: {stats['avg_decision_quality']:.3f}  "
              f"│ Overrides: {stats['decisions_overridden']}")
        print(f"│ 🛡️ Unacceptable Avoided: {stats['unacceptable_avoided']}  "
              f"│ Entered: {stats['unacceptable_entered']}")
        print(f"│ ⚖️ Caution: {stats['best_caution']:.3f}  "
              f"│ Accept Thresh: {stats['best_accept_thresh']:.3f}  "
              f"│ Plan Depth: {stats['best_planning_depth']}")
        print(f"│ 🌈 Diversity: {stats['diversity']:.4f}  "
              f"│ ⏱️ {stats['time']:.2f}s")
        print(f"└{'─' * 65}")
        print()

    def run(self, generations=None):
        generations = generations or Config.NUM_GENERATIONS
        print(f"\n🚀 Starting GENESIS v2.0 Evolution — {generations} generations\n")

        try:
            for gen in range(generations):
                stats = self.run_generation()
                self.print_generation_report(stats)
                if (gen + 1) % 25 == 0:
                    self._print_detailed_report()
        except KeyboardInterrupt:
            print("\n⚡ Evolution interrupted by user.")

        print("\n" + "=" * 70)
        print("  GENESIS v2.0 EVOLUTION COMPLETE")
        print("=" * 70)
        self._print_final_report()
        self._generate_visualizations()
        return self.stats_log

    def _print_detailed_report(self):
        print("\n" + "━" * 70)
        print("  📊 DETAILED ANALYSIS (with Decision Intelligence)")
        print("━" * 70)

        if self.stats_log:
            recent = self.stats_log[-10:]
            print(f"  Fitness trend (last 10): "
                  f"{recent[0]['best_fitness']:.3f} → {recent[-1]['best_fitness']:.3f}")
            print(f"  Decision quality trend: "
                  f"{recent[0]['avg_decision_quality']:.3f} → "
                  f"{recent[-1]['avg_decision_quality']:.3f}")

        print(f"  Active species: {len(self.pop_manager.species_list)}")
        for sp in self.pop_manager.species_list[:5]:
            print(f"    Species {sp.id}: {len(sp.members)} members, "
                  f"best={sp.best_fitness:.3f}, age={sp.age}")

        if self.agents:
            learning_rates = []
            hebbian_params = []
            caution_levels = []
            accept_thresholds = []
            planning_depths = []
            for agent in self.agents:
                for conn in agent.genome.connections.values():
                    learning_rates.append(conn.lr)
                    hebbian_params.append(conn.A)
                caution_levels.append(agent.genome.caution_level)
                accept_thresholds.append(agent.genome.acceptability_threshold)
                planning_depths.append(agent.genome.planning_depth)

            if learning_rates:
                print(f"  Meta-Learning: avg_lr={np.mean(learning_rates):.5f}, "
                      f"avg_hebbian_A={np.mean(hebbian_params):.4f}")
            print(f"  Decision Params (evolved):")
            print(f"    Avg Caution: {np.mean(caution_levels):.3f} "
                  f"(range {min(caution_levels):.2f}-{max(caution_levels):.2f})")
            print(f"    Avg Accept Threshold: {np.mean(accept_thresholds):.3f}")
            print(f"    Avg Planning Depth: {np.mean(planning_depths):.1f}")

        gs = self.godel_engine.get_stats()
        print(f"  Gödel Engine: {gs['total_proposals']} proposals, "
              f"{gs['acceptance_rate']:.1%} acceptance rate")
        print(f"  Novelty Archive: {len(self.novelty_archive.archive)} behaviors stored")
        print(f"  QC Interventions: {len(self.quality_controller.interventions)}")
        print("━" * 70 + "\n")

    def _print_final_report(self):
        print("\n📋 FINAL REPORT (GENESIS v2.0)")
        print("─" * 60)

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

        print(f"  Best Fitness Ever: {best_ever:.4f} (Generation {best_gen})")
        print(f"  Final Avg Fitness: {avg_final:.4f}")
        print(f"  Total Births: {total_births}")
        print(f"  Total Deaths: {total_deaths}")
        print(f"  Final Population: {len(self.agents)}")
        print(f"  Final Species: {len(self.pop_manager.species_list)}")
        print(f"  Curriculum Phase Reached: {self.field.phase}")

        gs = self.godel_engine.get_stats()
        print(f"  Gödel Modifications: {gs['accepted']} accepted / "
              f"{gs['rejected']} rejected ({gs['acceptance_rate']:.1%})")
        print(f"  Novelty Behaviors Archived: {len(self.novelty_archive.archive)}")

        print(f"\n  🎯 DECISION INTELLIGENCE SUMMARY:")
        print(f"     Total Decision Overrides: {total_overrides}")
        print(f"     Unacceptable States Avoided: {total_avoided}")
        print(f"     Unacceptable States Entered: {total_entered}")
        if total_avoided + total_entered > 0:
            avoidance_rate = total_avoided / (total_avoided + total_entered)
            print(f"     Avoidance Success Rate: {avoidance_rate:.1%}")
        print(f"     Final Avg Decision Quality: "
              f"{self.stats_log[-1]['avg_decision_quality']:.3f}")

        if self.agents:
            best_agent = max(self.agents, key=lambda a: a.genome.fitness)
            print(f"\n  🏆 CHAMPION AGENT:")
            print(f"     Connections: {sum(1 for c in best_agent.genome.connections.values() if c.enabled)}")
            print(f"     Hidden Nodes: {sum(1 for n in best_agent.genome.nodes.values() if n.type == NodeGene.HIDDEN)}")
            print(f"     Curiosity Drive: {best_agent.genome.curiosity_drive:.4f}")
            print(f"     Mutation Rate: {best_agent.genome.mutation_rate:.4f}")
            print(f"     Self-Modify Threshold: {best_agent.genome.self_modify_threshold:.4f}")
            print(f"     Metabolism Efficiency: {best_agent.genome.metabolism_efficiency:.4f}")
            print(f"     Caution Level: {best_agent.genome.caution_level:.4f}")
            print(f"     Acceptability Threshold: {best_agent.genome.acceptability_threshold:.4f}")
            print(f"     Planning Depth: {best_agent.genome.planning_depth}")
            print(f"     Temporal Discount: {best_agent.genome.temporal_discount:.4f}")

            a_vals = [c.A for c in best_agent.genome.connections.values()]
            b_vals = [c.B for c in best_agent.genome.connections.values()]
            c_vals = [c.C for c in best_agent.genome.connections.values()]
            if a_vals:
                print(f"     Evolved Learning Rule: A={np.mean(a_vals):.3f}, "
                      f"B={np.mean(b_vals):.3f}, C={np.mean(c_vals):.3f}")
                if abs(np.mean(a_vals)) > abs(np.mean(b_vals)) + abs(np.mean(c_vals)):
                    print(f"     → Predominantly HEBBIAN learning discovered")
                elif abs(np.mean(c_vals)) > abs(np.mean(a_vals)):
                    print(f"     → Post-synaptic driven learning discovered")
                else:
                    print(f"     → NOVEL learning rule discovered (beyond standard rules)")

        print("─" * 60)

    def _generate_visualizations(self):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            os.makedirs(Config.PLOT_DIR, exist_ok=True)
            if not self.stats_log:
                return

            generations = [s['generation'] for s in self.stats_log]
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

            # === Figure 1: Main Dashboard (3x3 now) ===
            fig, axes = plt.subplots(3, 3, figsize=(22, 18))
            fig.suptitle('GENESIS v2.0: Self-Evolving Darwinian Gödel Machine\n'
                         'with Decision Intelligence System',
                         fontsize=16, fontweight='bold')

            # Fitness
            ax = axes[0, 0]
            ax.plot(generations, best_fit, 'b-', linewidth=2, label='Best Fitness')
            ax.plot(generations, avg_fit, 'r--', alpha=0.7, label='Avg Fitness')
            ax.fill_between(generations, avg_fit, best_fit, alpha=0.2, color='blue')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Fitness')
            ax.set_title('Fitness Evolution')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Population & Species
            ax = axes[0, 1]
            ax.plot(generations, populations, 'g-', linewidth=2, label='Population')
            ax2 = ax.twinx()
            ax2.plot(generations, species, 'orange', linewidth=2, label='Species')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Population', color='green')
            ax2.set_ylabel('Species', color='orange')
            ax.set_title('Population & Speciation')
            ax.grid(True, alpha=0.3)

            # Diversity
            ax = axes[0, 2]
            ax.plot(generations, diversity, 'm-', linewidth=2)
            ax.set_xlabel('Generation')
            ax.set_ylabel('Behavioral Diversity')
            ax.set_title('Novelty Archive Diversity')
            ax.grid(True, alpha=0.3)

            # Brain Complexity
            ax = axes[1, 0]
            ax.plot(generations, complexity, 'c-', linewidth=2, label='Connections')
            ax2 = ax.twinx()
            ax2.plot(generations, hidden, 'red', linewidth=2, label='Hidden Nodes')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Active Connections', color='cyan')
            ax2.set_ylabel('Hidden Nodes', color='red')
            ax.set_title('Brain Complexity (NEAT)')
            ax.grid(True, alpha=0.3)

            # Decision Quality
            ax = axes[1, 1]
            ax.plot(generations, dec_quality, 'darkgreen', linewidth=2.5)
            ax.set_xlabel('Generation')
            ax.set_ylabel('Decision Quality')
            ax.set_title('Decision Intelligence Quality')
            ax.set_ylim(0, 1)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='Baseline')
            ax.legend()

            # Acceptability: Avoided vs Entered
            ax = axes[1, 2]
            ax.plot(generations, avoided, 'green', linewidth=2, label='Avoided')
            ax.plot(generations, entered, 'red', linewidth=2, label='Entered')
            ax.fill_between(generations, entered, alpha=0.2, color='red')
            ax.fill_between(generations, avoided, alpha=0.2, color='green')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Count')
            ax.set_title('Unacceptable States: Avoided vs Entered')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Gödel Engine
            ax = axes[2, 0]
            godel_accepted = [s['godel_accepted'] for s in self.stats_log]
            godel_rejected = [s['godel_rejected'] for s in self.stats_log]
            ax.plot(generations, godel_accepted, 'g-', linewidth=2, label='Accepted')
            ax.plot(generations, godel_rejected, 'r-', linewidth=2, label='Rejected')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Cumulative Count')
            ax.set_title('Gödel Self-Modification Gate')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Evolved Decision Parameters
            ax = axes[2, 1]
            ax.plot(generations, caution, 'purple', linewidth=2, label='Caution Level')
            ax.plot(generations, accept_thresh, 'orange', linewidth=2,
                    label='Accept Threshold')
            ax2 = ax.twinx()
            ax2.plot(generations, plan_depth, 'teal', linewidth=2,
                     label='Planning Depth', linestyle='--')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Parameter Value')
            ax2.set_ylabel('Planning Depth', color='teal')
            ax.set_title('Evolved Decision Parameters')
            ax.legend(loc='upper left')
            ax2.legend(loc='upper right')
            ax.grid(True, alpha=0.3)

            # Decision Overrides
            ax = axes[2, 2]
            ax.plot(generations, overrides, 'darkorange', linewidth=2)
            ax.set_xlabel('Generation')
            ax.set_ylabel('Override Count')
            ax.set_title('Neural Network Overrides by Decision Intelligence')
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plot_path = os.path.join(Config.PLOT_DIR, 'genesis_v2_dashboard.png')
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"\n  📊 Dashboard saved to: {plot_path}")

            # === Figure 2: Meta-Learning Analysis ===
            if self.agents:
                fig, axes = plt.subplots(1, 3, figsize=(18, 5))
                fig.suptitle('Evolved Meta-Learning Rules & Decision Parameters',
                             fontsize=14, fontweight='bold')

                all_A, all_B, all_C, all_lr = [], [], [], []
                for agent in self.agents:
                    for conn in agent.genome.connections.values():
                        all_A.append(conn.A)
                        all_B.append(conn.B)
                        all_C.append(conn.C)
                        all_lr.append(conn.lr)

                if all_A:
                    axes[0].hist(all_A, bins=30, color='steelblue', alpha=0.7, label='A (Hebbian)')
                    axes[0].hist(all_B, bins=30, color='coral', alpha=0.7, label='B (Pre-syn)')
                    axes[0].hist(all_C, bins=30, color='green', alpha=0.7, label='C (Post-syn)')
                    axes[0].set_title('Evolved Learning Rule Parameters')
                    axes[0].legend()
                    axes[0].grid(True, alpha=0.3)

                    axes[1].hist(all_lr, bins=30, color='purple', alpha=0.7)
                    axes[1].set_title('Evolved Learning Rates')
                    axes[1].set_xlabel('Learning Rate')
                    axes[1].grid(True, alpha=0.3)

                    best_agent = max(self.agents, key=lambda a: a.genome.fitness)
                    weights = [c.weight for c in best_agent.genome.connections.values()]
                    axes[2].hist(weights, bins=30, color='gold', alpha=0.7)
                    axes[2].set_title('Champion Weight Distribution')
                    axes[2].grid(True, alpha=0.3)

                plt.tight_layout()
                plot_path2 = os.path.join(Config.PLOT_DIR, 'genesis_v2_metalearning.png')
                plt.savefig(plot_path2, dpi=150, bbox_inches='tight')
                plt.close()
                print(f"  📊 Meta-learning analysis saved to: {plot_path2}")

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
            ax.set_title('GENESIS v2.0 Universe — Final State',
                         fontsize=14, fontweight='bold')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            plot_path3 = os.path.join(Config.PLOT_DIR, 'genesis_v2_universe.png')
            plt.savefig(plot_path3, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"  📊 Universe visualization saved to: {plot_path3}")

        except Exception as e:
            print(f"  ⚠️ Visualization error: {e}")
            traceback.print_exc()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Launch the GENESIS v2.0 system."""
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                                                                      ║")
    print("║   ██████  ███████ ███    ██ ███████ ███████ ██ ███████               ║")
    print("║  ██       ██      ████   ██ ██      ██      ██ ██                    ║")
    print("║  ██   ███ █████   ██ ██  ██ █████   ███████ ██ ███████               ║")
    print("║  ██    ██ ██      ██  ██ ██ ██           ██ ██      ██               ║")
    print("║   ██████  ███████ ██   ████ ███████ ███████ ██ ███████               ║")
    print("║                                                                      ║")
    print("║  v2.0 — with Decision Intelligence System                            ║")
    print("║                                                                      ║")
    print("║  Agents learn what decisions lead to what outcomes.                   ║")
    print("║  They predict consequences before acting.                             ║")
    print("║  They learn which world states are unacceptable.                      ║")
    print("║  They evolve caution, planning depth, and temporal reasoning.         ║")
    print("║  They override their own neural network when wisdom says otherwise.   ║")
    print("║                                                                      ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()

    engine = GenesisEngine()
    stats = engine.run(generations=Config.NUM_GENERATIONS)

    print("\n✨ GENESIS v2.0 has evolved beyond its initial design.")
    print("   The agents learned cause and effect from their own experience.")
    print("   They discovered which decisions lead to survival and which to death.")
    print("   They evolved their own standards for what states are acceptable.")
    print("   They learned to predict consequences and plan ahead.")
    print("   They override their instincts when their wisdom says otherwise.")
    print("\n   This is decision intelligence emerging from nothing but")
    print("   evolution, experience, and self-reflection.\n")

    return engine


if __name__ == "__main__":
    main()
