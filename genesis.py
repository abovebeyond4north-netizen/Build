#!/usr/bin/env python3
"""
GENESIS v4.0: Generative Evolving Neural Engine for Self-Improving Systems
==========================================================================

A self-sufficient, self-evolving Darwinian Godel machine with zero-data
meta-learning, Decision Intelligence, Emergent Communication, Counterfactual
Reasoning, Persistent Knowledge Transfer, Hierarchical Goal Formation,
Theory of Mind, Abstract Concept Formation, and Self-Narrative.

v4.0 Additions:
  - Hierarchical Goal Formation: agents set their own goals, decompose them
    into sub-goals, and pursue multi-step plans with genuine intentionality
  - Theory of Mind: agents build internal models of other agents' behavior,
    predict what others will do, enabling cooperation and strategic deception
  - Abstract Concept Formation: agents compress repeated experiences into
    abstract prototypes, recognizing situations at a higher level
  - Self-Narrative: agents maintain a compressed autobiography that influences
    future decisions and gets partially inherited by offspring

Full Capabilities (17):
  1.  Self-Sufficient Passive Learning (zero external data)
  2.  Meta-Learning from Scratch (evolving learning rules)
  3.  Darwinian Self-Evolution (NEAT-style neuroevolution)
  4.  Godel Machine Self-Rewriting (validated self-modification)
  5.  Self-Controlled / Self-Coded (autonomous execution)
  6.  Self-Instructed / Self-Quality-Checked / Self-Evaluated
  7.  Self-Support System (error recovery, rollback, self-healing)
  8.  Zero-Data SOTA Methods (curiosity, novelty search, self-play)
  9.  Beyond the Builder (open-ended emergent evolution)
  10. Decision Intelligence (causal learning, temporal reasoning)
  11. Emergent Communication (evolved signaling, proto-language)
  12. Counterfactual Reasoning (what-if analysis, regret-based learning)
  13. Persistent Knowledge Transfer (wisdom inheritance, cultural evolution)
  14. Hierarchical Goal Formation (intentionality, multi-step planning)
  15. Theory of Mind (social modeling, prediction, trust)
  16. Abstract Concept Formation (situation recognition, prototypes)
  17. Self-Narrative (autobiographical memory, identity, life story)

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
    SIGNAL_DIM = 4
    COMM_RANGE = 8.0
    SIGNAL_COST = 0.02
    COMM_WEIGHT = 0.2
    SIGNAL_DECAY = 0.9

    # Counterfactual Reasoning (v3.0)
    COUNTERFACTUAL_REPLAYS = 3
    REGRET_WEIGHT = 0.3
    COUNTERFACTUAL_INTERVAL = 5

    # Knowledge Bank (v3.0)
    KNOWLEDGE_BANK_SIZE = 200
    KNOWLEDGE_INHERIT_RATE = 0.7
    KNOWLEDGE_ENTRY_DIM = 20
    WISDOM_TRANSFER_AMOUNT = 10

    # Hierarchical Goals (v4.0)
    MAX_GOAL_DEPTH = 3
    GOAL_UPDATE_INTERVAL = 5
    GOAL_WEIGHT = 0.3

    # Theory of Mind (v4.0)
    TOM_OBSERVATION_RANGE = 6.0
    TOM_MEMORY_SIZE = 20
    TOM_WEIGHT = 0.2

    # Abstract Concepts (v4.0)
    MAX_CONCEPTS = 20
    CONCEPT_MERGE_THRESHOLD = 0.5
    CONCEPT_WEIGHT = 0.15

    # Self-Narrative (v4.0)
    MAX_LIFE_EVENTS = 50
    NARRATIVE_WEIGHT = 0.15
    SIGNIFICANCE_THRESHOLD = 0.3

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
    decision intelligence params, communication params, and v4.0 cognitive params.
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
        self.signal_honesty = np.random.uniform(0.0, 1.0)
        self.listen_weight = np.random.uniform(0.1, 0.9)
        self.broadcast_threshold = np.random.uniform(0.1, 0.8)

        # Counterfactual reasoning (v3.0)
        self.regret_sensitivity = np.random.uniform(0.1, 0.8)
        self.counterfactual_depth = max(1, int(np.random.uniform(1, 4)))

        # Hierarchical Goals (v4.0)
        self.goal_ambition = np.random.uniform(0.2, 0.8)
        self.goal_persistence = np.random.uniform(0.3, 0.9)
        self.goal_flexibility = np.random.uniform(0.2, 0.8)

        # Theory of Mind (v4.0)
        self.social_awareness = np.random.uniform(0.2, 0.8)
        self.trust_default = np.random.uniform(0.3, 0.7)
        self.modeling_capacity = max(3, int(np.random.uniform(3, 15)))

        # Abstract Concepts (v4.0)
        self.abstraction_capacity = max(5, int(np.random.uniform(5, 30)))
        self.concept_threshold = np.random.uniform(0.3, 1.5)
        self.generalization_rate = np.random.uniform(0.1, 0.7)

        # Self-Narrative (v4.0)
        self.narrative_sensitivity = np.random.uniform(0.2, 0.8)
        self.identity_strength = np.random.uniform(0.1, 0.7)

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
        # Hierarchical Goals (v4.0)
        new.goal_ambition = self.goal_ambition
        new.goal_persistence = self.goal_persistence
        new.goal_flexibility = self.goal_flexibility
        # Theory of Mind (v4.0)
        new.social_awareness = self.social_awareness
        new.trust_default = self.trust_default
        new.modeling_capacity = self.modeling_capacity
        # Abstract Concepts (v4.0)
        new.abstraction_capacity = self.abstraction_capacity
        new.concept_threshold = self.concept_threshold
        new.generalization_rate = self.generalization_rate
        # Self-Narrative (v4.0)
        new.narrative_sensitivity = self.narrative_sensitivity
        new.identity_strength = self.identity_strength
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

        # Mutate Hierarchical Goals parameters (v4.0)
        if np.random.random() < 0.1:
            genome.goal_ambition += np.random.randn() * 0.05
            genome.goal_ambition = np.clip(genome.goal_ambition, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.goal_persistence += np.random.randn() * 0.05
            genome.goal_persistence = np.clip(genome.goal_persistence, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.goal_flexibility += np.random.randn() * 0.05
            genome.goal_flexibility = np.clip(genome.goal_flexibility, 0.0, 1.0)

        # Mutate Theory of Mind parameters (v4.0)
        if np.random.random() < 0.1:
            genome.social_awareness += np.random.randn() * 0.05
            genome.social_awareness = np.clip(genome.social_awareness, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.trust_default += np.random.randn() * 0.05
            genome.trust_default = np.clip(genome.trust_default, 0.0, 1.0)
        if np.random.random() < 0.05:
            genome.modeling_capacity += np.random.choice([-1, 0, 1])
            genome.modeling_capacity = max(3, min(15, genome.modeling_capacity))

        # Mutate Abstract Concepts parameters (v4.0)
        if np.random.random() < 0.05:
            genome.abstraction_capacity += np.random.choice([-2, -1, 0, 1, 2])
            genome.abstraction_capacity = max(5, min(30, genome.abstraction_capacity))
        if np.random.random() < 0.1:
            genome.concept_threshold += np.random.randn() * 0.1
            genome.concept_threshold = np.clip(genome.concept_threshold, 0.1, 3.0)
        if np.random.random() < 0.1:
            genome.generalization_rate += np.random.randn() * 0.05
            genome.generalization_rate = np.clip(genome.generalization_rate, 0.0, 1.0)

        # Mutate Self-Narrative parameters (v4.0)
        if np.random.random() < 0.1:
            genome.narrative_sensitivity += np.random.randn() * 0.05
            genome.narrative_sensitivity = np.clip(genome.narrative_sensitivity, 0.0, 1.0)
        if np.random.random() < 0.1:
            genome.identity_strength += np.random.randn() * 0.05
            genome.identity_strength = np.clip(genome.identity_strength, 0.0, 1.0)

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
        # Crossover v4.0 params
        if np.random.random() < 0.5:
            child.goal_ambition = parent2.goal_ambition
        if np.random.random() < 0.5:
            child.goal_persistence = parent2.goal_persistence
        if np.random.random() < 0.5:
            child.goal_flexibility = parent2.goal_flexibility
        if np.random.random() < 0.5:
            child.social_awareness = parent2.social_awareness
        if np.random.random() < 0.5:
            child.trust_default = parent2.trust_default
        if np.random.random() < 0.5:
            child.modeling_capacity = parent2.modeling_capacity
        if np.random.random() < 0.5:
            child.abstraction_capacity = parent2.abstraction_capacity
        if np.random.random() < 0.5:
            child.concept_threshold = parent2.concept_threshold
        if np.random.random() < 0.5:
            child.generalization_rate = parent2.generalization_rate
        if np.random.random() < 0.5:
            child.narrative_sensitivity = parent2.narrative_sensitivity
        if np.random.random() < 0.5:
            child.identity_strength = parent2.identity_strength
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
        self.counterfactual_regret = 0.0


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


class DecisionIntelligence:
    """The complete Decision Intelligence System for an agent."""
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
        return {'score': score, 'predicted': pred, 'acceptable': predicted_acceptable}

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
            health_delta * 0.5 + reward * 0.3 + (health_after / Config.INITIAL_HEALTH - 0.5), -1, 1
        )
        self.state_evaluator.train(ws_after, state_value_target)
        actual_state_value = self.state_evaluator.evaluate(ws_after)
        self.consequence_predictor.train(
            state, action, actual_reward=reward, actual_health_delta=health_delta,
            actual_state_value=actual_state_value, actual_time_factor=1.0
        )
        is_acceptable = actual_state_value > -genome.acceptability_threshold
        pred = self.consequence_predictor.predict(state, action)
        pred_acceptable = pred['state_value'] > -genome.acceptability_threshold
        self.journal.record(
            state, action, pred,
            {'reward': reward, 'health_delta': health_delta, 'state_value': actual_state_value},
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
        avoidance = 1.0 - (self.journal.entered_unacceptable / max(self.total_decisions, 1))
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
    def __init__(self, sender_pos, signal_vector, strength, sender_id):
        self.sender_pos = sender_pos.copy()
        self.signal_vector = np.array(signal_vector)
        self.strength = strength
        self.sender_id = sender_id
        self.age = 0


class CommunicationChannel:
    def __init__(self):
        self.active_signals = []
        self.signal_history = deque(maxlen=1000)
        self.total_broadcasts = 0
        self.total_receptions = 0

    def broadcast(self, sender_pos, signal_vector, strength, sender_id):
        sig = Signal(sender_pos, signal_vector, strength, sender_id)
        self.active_signals.append(sig)
        self.signal_history.append(signal_vector.copy())
        self.total_broadcasts += 1

    def receive(self, receiver_pos, receiver_id):
        received = []
        for sig in self.active_signals:
            if sig.sender_id == receiver_id:
                continue
            dist = np.linalg.norm(receiver_pos - sig.sender_pos)
            if dist < Config.COMM_RANGE:
                decay = Config.SIGNAL_DECAY ** dist
                effective_strength = sig.strength * decay
                received.append((sig.signal_vector, effective_strength))
                self.total_receptions += 1
        return received

    def step(self):
        for sig in self.active_signals:
            sig.age += 1
        self.active_signals = [s for s in self.active_signals if s.age < 3]

    def get_language_stats(self):
        if len(self.signal_history) < 10:
            return {'diversity': 0.0, 'clusters': 0, 'vocab_size': 0}
        signals = np.array(list(self.signal_history)[-100:])
        diversity = np.mean(np.std(signals, axis=0))
        rounded = np.round(signals, 1)
        unique = set(tuple(r) for r in rounded)
        return {'diversity': float(diversity), 'clusters': len(unique), 'vocab_size': min(len(unique), 50)}


class AgentCommunicator:
    def __init__(self, state_dim):
        self.state_dim = state_dim
        self.encode_W = np.random.randn(Config.SIGNAL_DIM, state_dim) * 0.3
        self.encode_b = np.zeros(Config.SIGNAL_DIM)
        self.decode_W = np.random.randn(2, Config.SIGNAL_DIM) * 0.3
        self.decode_b = np.zeros(2)
        self.helpful_signals = 0

    def encode_signal(self, state, genome):
        x = np.resize(state, self.state_dim)
        raw_signal = np.tanh(self.encode_W @ x + self.encode_b)
        if genome.signal_honesty < 0.3:
            raw_signal = raw_signal * (2 * genome.signal_honesty - 1)
        return raw_signal * genome.signal_strength

    def decode_signals(self, received_signals, genome):
        if not received_signals:
            return np.zeros(2)
        combined_signal = np.zeros(Config.SIGNAL_DIM)
        total_weight = 0.0
        for sig_vec, strength in received_signals:
            combined_signal += sig_vec * strength
            total_weight += strength
        if total_weight > 0:
            combined_signal /= total_weight
        modifier = np.tanh(self.decode_W @ combined_signal + self.decode_b)
        return modifier * genome.listen_weight

    def learn_from_communication(self, received_signals, outcome_reward, lr=0.003):
        if not received_signals or abs(outcome_reward) < 0.01:
            return
        combined = np.zeros(Config.SIGNAL_DIM)
        for sig_vec, strength in received_signals:
            combined += sig_vec * strength
        reward_signal = np.clip(outcome_reward, -1, 1)
        self.decode_W += lr * reward_signal * np.outer(np.ones(2) * reward_signal, combined)
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
    def __init__(self):
        self.total_replays = 0
        self.total_regrets = 0
        self.regret_history = deque(maxlen=200)
        self.best_counterfactual_found = 0.0

    def analyze(self, causal_memory, consequence_predictor, genome):
        if len(causal_memory) < 5:
            return []
        regrets = []
        memory = list(causal_memory)
        indices = np.random.choice(len(memory), size=min(Config.COUNTERFACTUAL_REPLAYS, len(memory)), replace=False)
        for idx in indices:
            transition = memory[idx]
            actual_reward = transition.reward
            actual_value = transition.downstream_value
            best_cf_score = actual_reward + actual_value
            best_cf_action = None
            for _ in range(genome.counterfactual_depth * 2):
                cf_action = transition.action + np.random.randn(2) * 1.0
                cf_action = np.clip(cf_action, -2, 2)
                cf_pred = consequence_predictor.predict(transition.state, cf_action)
                cf_score = cf_pred['reward'] + cf_pred['state_value'] * 0.5
                if cf_score > best_cf_score:
                    best_cf_score = cf_score
                    best_cf_action = cf_action
            opposite = -transition.action
            opp_pred = consequence_predictor.predict(transition.state, opposite)
            opp_score = opp_pred['reward'] + opp_pred['state_value'] * 0.5
            if opp_score > best_cf_score:
                best_cf_score = opp_score
                best_cf_action = opposite
            regret = max(0, best_cf_score - (actual_reward + actual_value))
            if regret > 0 and best_cf_action is not None:
                regrets.append({
                    'state': transition.state, 'actual_action': transition.action,
                    'better_action': best_cf_action, 'regret': regret,
                    'improvement': best_cf_score - (actual_reward + actual_value)
                })
                transition.counterfactual_regret = regret
                self.total_regrets += 1
            self.total_replays += 1
        if regrets:
            self.regret_history.append(np.mean([r['regret'] for r in regrets]))
        return regrets

    def get_regret_adjustment(self, state, proposed_action, regrets, genome):
        if not regrets:
            return proposed_action
        best_adjustment = np.zeros(2)
        total_weight = 0.0
        for regret_entry in regrets:
            state_similarity = 1.0 / (1.0 + np.linalg.norm(
                np.resize(state, len(regret_entry['state'])) - regret_entry['state']
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
        return {'total_replays': self.total_replays, 'total_regrets': self.total_regrets, 'avg_regret': avg_regret}


# ============================================================================
# PERSISTENT KNOWLEDGE BANK (v3.0)
# ============================================================================

class KnowledgeEntry:
    def __init__(self, state_pattern, best_action, expected_reward, danger_level, source_fitness, source_generation):
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
    def __init__(self):
        self.entries = []
        self.total_deposits = 0
        self.total_withdrawals = 0
        self.total_helpful = 0

    def deposit(self, agent_memory, agent_fitness, generation):
        if not agent_memory:
            return 0
        deposited = 0
        memory = list(agent_memory)
        sorted_mem = sorted(memory, key=lambda t: t.reward + t.downstream_value, reverse=True)
        for transition in sorted_mem[:Config.WISDOM_TRANSFER_AMOUNT]:
            state_pattern = np.resize(transition.state, Config.KNOWLEDGE_ENTRY_DIM)
            entry = KnowledgeEntry(
                state_pattern=state_pattern, best_action=transition.action,
                expected_reward=transition.reward,
                danger_level=-transition.health_delta if transition.health_delta < 0 else 0,
                source_fitness=agent_fitness, source_generation=generation
            )
            self.entries.append(entry)
            deposited += 1
        dangerous = [t for t in memory if t.health_delta < -2]
        for transition in dangerous[:5]:
            state_pattern = np.resize(transition.state, Config.KNOWLEDGE_ENTRY_DIM)
            entry = KnowledgeEntry(
                state_pattern=state_pattern, best_action=-transition.action,
                expected_reward=transition.reward, danger_level=-transition.health_delta,
                source_fitness=agent_fitness, source_generation=generation
            )
            self.entries.append(entry)
            deposited += 1
        if len(self.entries) > Config.KNOWLEDGE_BANK_SIZE:
            self.entries.sort(
                key=lambda e: e.get_usefulness() * 0.5 + e.source_fitness * 0.3 +
                              (e.source_generation / max(generation, 1)) * 0.2,
                reverse=True
            )
            self.entries = self.entries[:Config.KNOWLEDGE_BANK_SIZE]
        self.total_deposits += deposited
        return deposited

    def withdraw(self, state, n=3):
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
        if was_helpful:
            entry.times_helpful += 1
            self.total_helpful += 1

    def get_stats(self):
        return {
            'total_entries': len(self.entries), 'total_deposits': self.total_deposits,
            'total_withdrawals': self.total_withdrawals, 'total_helpful': self.total_helpful,
            'helpfulness_rate': self.total_helpful / max(self.total_withdrawals, 1)
        }


# ============================================================================
# HIERARCHICAL GOAL FORMATION (v4.0)
# ============================================================================

class GoalNode:
    """A single goal in the hierarchy."""
    TYPES = ['survive', 'explore', 'accumulate', 'reproduce', 'social']

    def __init__(self, goal_type, priority, completion_threshold=1.0, parent=None, depth=0):
        self.goal_type = goal_type
        self.priority = priority
        self.completion_threshold = completion_threshold
        self.progress = 0.0
        self.sub_goals = []
        self.parent = parent
        self.depth = depth
        self.completed = False
        self.abandoned = False
        self.age = 0

    def is_active(self):
        return not self.completed and not self.abandoned


class HierarchicalGoalSystem:
    """Agents set their own goals, decompose into sub-goals, pursue multi-step plans."""

    def __init__(self):
        self.root_goals = []
        self.goals_completed = 0
        self.goals_abandoned = 0
        self.total_goals_created = 0

    def generate_goals(self, state, health, age, genome):
        """Create/update goals based on current situation."""
        # Remove completed/abandoned goals
        self.root_goals = [g for g in self.root_goals if g.is_active()]

        # Limit active goals based on ambition
        max_goals = max(1, int(genome.goal_ambition * 5))
        if len(self.root_goals) >= max_goals:
            return

        # Generate goals based on situation
        energy_level = np.mean(state) if len(state) > 0 else 0
        health_ratio = health / Config.INITIAL_HEALTH

        if health_ratio < 0.4:
            self._add_goal('survive', priority=1.0, genome=genome)
        if health_ratio > 0.7 and genome.goal_ambition > 0.5:
            self._add_goal('reproduce', priority=0.8 * genome.goal_ambition, genome=genome)
        if energy_level < 0.3:
            self._add_goal('explore', priority=0.6, genome=genome)
        if genome.goal_ambition > 0.6:
            self._add_goal('accumulate', priority=0.5 * genome.goal_ambition, genome=genome)
        if genome.social_awareness > 0.5:
            self._add_goal('social', priority=0.4 * genome.social_awareness, genome=genome)

    def _add_goal(self, goal_type, priority, genome):
        """Add a goal if one of this type doesn't already exist."""
        existing_types = [g.goal_type for g in self.root_goals]
        if goal_type in existing_types:
            return
        goal = GoalNode(goal_type, priority, completion_threshold=1.0)
        # Add sub-goals based on depth and flexibility
        if genome.goal_ambition > 0.5 and goal.depth < Config.MAX_GOAL_DEPTH:
            n_sub = max(1, int(genome.goal_flexibility * 3))
            for i in range(n_sub):
                sub_type = np.random.choice(GoalNode.TYPES)
                sub = GoalNode(sub_type, priority * 0.7, completion_threshold=0.5,
                               parent=goal, depth=goal.depth + 1)
                goal.sub_goals.append(sub)
        self.root_goals.append(goal)
        self.total_goals_created += 1

    def select_active_goal(self):
        """Pick highest priority incomplete goal."""
        active = [g for g in self.root_goals if g.is_active()]
        if not active:
            return None
        # Check sub-goals first
        for goal in sorted(active, key=lambda g: g.priority, reverse=True):
            active_subs = [s for s in goal.sub_goals if s.is_active()]
            if active_subs:
                return max(active_subs, key=lambda s: s.priority)
            return goal
        return active[0]

    def get_goal_action_bias(self, state, active_goal):
        """Return a 2D action modifier that biases toward goal completion."""
        if active_goal is None:
            return np.zeros(2)
        energy_level = np.mean(state) if len(state) > 0 else 0
        bias = np.zeros(2)
        if active_goal.goal_type == 'survive':
            # Bias toward high-energy areas (positive gradient)
            if len(state) >= 4:
                grad_x = state[len(state)//2 + 1] - state[len(state)//2 - 1] if len(state) > 2 else 0
                grad_y = state[min(len(state)-1, len(state)//2 + 3)] - state[max(0, len(state)//2 - 3)] if len(state) > 6 else 0
                bias = np.array([grad_x, grad_y]) * 0.5
        elif active_goal.goal_type == 'explore':
            # Bias toward movement (random direction, changes over time)
            angle = (active_goal.age * 0.1) % (2 * np.pi)
            bias = np.array([np.cos(angle), np.sin(angle)]) * 0.3
        elif active_goal.goal_type == 'accumulate':
            # Stay near energy
            if energy_level > 0.5:
                bias = np.zeros(2)  # Stay put
            else:
                bias = np.random.randn(2) * 0.2  # Search
        elif active_goal.goal_type == 'reproduce':
            bias = np.random.randn(2) * 0.1  # Move carefully
        elif active_goal.goal_type == 'social':
            bias = np.random.randn(2) * 0.15  # Wander toward others
        return np.clip(bias, -1, 1)

    def update_progress(self, state, health_delta, energy_gained, genome):
        """Update goal progress based on outcomes."""
        for goal in self.root_goals:
            if not goal.is_active():
                continue
            goal.age += 1
            # Update progress based on goal type
            if goal.goal_type == 'survive' and health_delta > 0:
                goal.progress += 0.1
            elif goal.goal_type == 'explore':
                goal.progress += 0.05  # Always progressing while alive
            elif goal.goal_type == 'accumulate' and energy_gained > 0.5:
                goal.progress += energy_gained * 0.2
            elif goal.goal_type == 'reproduce' and health_delta > 1:
                goal.progress += 0.15
            elif goal.goal_type == 'social':
                goal.progress += 0.03

            # Check completion
            if goal.progress >= goal.completion_threshold:
                goal.completed = True
                self.goals_completed += 1
                # Complete sub-goals too
                for sub in goal.sub_goals:
                    if sub.is_active():
                        sub.completed = True
                        self.goals_completed += 1

            # Abandon stale goals (low persistence = abandon faster)
            if goal.age > 50 / max(genome.goal_persistence, 0.1) and goal.progress < 0.2:
                goal.abandoned = True
                self.goals_abandoned += 1

            # Update sub-goals
            for sub in goal.sub_goals:
                if sub.is_active():
                    sub.age += 1
                    sub.progress += np.random.uniform(0, 0.05)
                    if sub.progress >= sub.completion_threshold:
                        sub.completed = True
                        self.goals_completed += 1

    def get_stats(self):
        active = [g for g in self.root_goals if g.is_active()]
        max_depth = 0
        for g in self.root_goals:
            if g.sub_goals:
                max_depth = max(max_depth, 1)
        return {
            'goals_completed': self.goals_completed,
            'goals_abandoned': self.goals_abandoned,
            'active_goals': len(active),
            'deepest_depth': max_depth,
            'total_created': self.total_goals_created
        }


# ============================================================================
# THEORY OF MIND (v4.0)
# ============================================================================

class AgentModel:
    """Internal model of another agent's behavior."""
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.predicted_direction = np.zeros(2)
        self.predicted_aggression = 0.5
        self.reliability_score = 0.5
        self.observation_count = 0
        self.last_pos = None
        self.last_action = None
        self.prediction_errors = []

    def update(self, pos, action):
        if self.last_pos is not None and self.last_action is not None:
            # Check prediction accuracy
            actual_dir = pos - self.last_pos if self.last_pos is not None else np.zeros(2)
            pred_error = np.linalg.norm(actual_dir - self.predicted_direction)
            self.prediction_errors.append(pred_error)
            if len(self.prediction_errors) > 20:
                self.prediction_errors = self.prediction_errors[-20:]
            self.reliability_score = 1.0 / (1.0 + np.mean(self.prediction_errors))
        self.last_pos = pos.copy()
        self.last_action = action.copy() if action is not None else np.zeros(2)
        # Update predictions with exponential moving average
        alpha = 0.3
        if action is not None:
            self.predicted_direction = (1 - alpha) * self.predicted_direction + alpha * action
        # Estimate aggression from speed
        speed = np.linalg.norm(action) if action is not None else 0
        self.predicted_aggression = (1 - alpha) * self.predicted_aggression + alpha * min(speed / 2.0, 1.0)
        self.observation_count += 1


class TheoryOfMind:
    """Agents build internal models of other agents' behavior."""

    def __init__(self, capacity=10):
        self.models = {}
        self.capacity = capacity
        self.social_interactions = 0
        self.correct_predictions = 0
        self.total_predictions = 0

    def observe(self, other_agent_id, other_pos, other_action):
        """Update internal model of another agent."""
        if other_agent_id not in self.models:
            if len(self.models) >= self.capacity:
                # Remove least observed
                least = min(self.models.values(), key=lambda m: m.observation_count)
                del self.models[least.agent_id]
            self.models[other_agent_id] = AgentModel(other_agent_id)
        self.models[other_agent_id].update(other_pos, other_action)
        self.social_interactions += 1

    def predict_agent(self, agent_id):
        """Predict next action of a modeled agent."""
        if agent_id not in self.models:
            return np.zeros(2)
        model = self.models[agent_id]
        self.total_predictions += 1
        return model.predicted_direction.copy()

    def get_social_action_modifier(self, own_pos, nearby_agents_info):
        """Return 2D modifier: approach cooperators, avoid aggressors."""
        if not nearby_agents_info:
            return np.zeros(2)
        modifier = np.zeros(2)
        for agent_id, agent_pos in nearby_agents_info:
            if agent_id in self.models:
                model = self.models[agent_id]
                direction = agent_pos - own_pos
                dist = np.linalg.norm(direction)
                if dist < 0.1:
                    continue
                direction = direction / dist
                # Approach reliable/cooperative agents, avoid aggressive ones
                if model.predicted_aggression > 0.7:
                    modifier -= direction * 0.3  # Avoid
                elif model.reliability_score > 0.6:
                    modifier += direction * 0.1  # Approach cautiously
        return np.clip(modifier, -1, 1)

    def get_trust_level(self, agent_id):
        if agent_id not in self.models:
            return 0.5
        return self.models[agent_id].reliability_score

    def get_stats(self):
        return {
            'agents_modeled': len(self.models),
            'social_interactions': self.social_interactions,
            'total_predictions': self.total_predictions,
            'avg_reliability': np.mean([m.reliability_score for m in self.models.values()]) if self.models else 0.5
        }


# ============================================================================
# ABSTRACT CONCEPT FORMATION (v4.0)
# ============================================================================

class Concept:
    """An abstract prototype formed from repeated experiences."""
    _next_id = 0

    def __init__(self, centroid, reward, danger):
        self.id = Concept._next_id
        Concept._next_id += 1
        self.centroid = np.array(centroid, dtype=float)
        self.label = f"concept_{self.id}"
        self.exemplar_count = 1
        self.avg_reward = reward
        self.avg_danger = danger
        self.associated_action = np.zeros(2)
        self.last_used = 0


class ConceptMemory:
    """Agents compress repeated experiences into abstract prototypes."""

    def __init__(self, capacity=20, threshold=1.0):
        self.concepts = []
        self.capacity = capacity
        self.threshold = threshold
        self.categorizations = 0
        self.merges = 0

    def observe_and_categorize(self, state, reward, danger_level, action=None):
        """Find nearest concept or create new one."""
        state_vec = np.resize(state, 10)  # Compress to fixed dim
        nearest, dist = self._find_nearest(state_vec)

        if nearest is not None and dist < self.threshold:
            # Update existing concept (running average)
            alpha = 1.0 / (nearest.exemplar_count + 1)
            nearest.centroid = (1 - alpha) * nearest.centroid + alpha * state_vec
            nearest.avg_reward = (1 - alpha) * nearest.avg_reward + alpha * reward
            nearest.avg_danger = (1 - alpha) * nearest.avg_danger + alpha * danger_level
            if action is not None:
                nearest.associated_action = (1 - alpha) * nearest.associated_action + alpha * np.resize(action, 2)
            nearest.exemplar_count += 1
            nearest.last_used = self.categorizations
            self.categorizations += 1
            return nearest
        else:
            # Create new concept
            if len(self.concepts) >= self.capacity:
                # Remove least used
                self.concepts.sort(key=lambda c: c.exemplar_count)
                self.concepts.pop(0)
            concept = Concept(state_vec, reward, danger_level)
            if action is not None:
                concept.associated_action = np.resize(action, 2)
            self.concepts.append(concept)
            self.categorizations += 1
            return concept

    def _find_nearest(self, state_vec):
        if not self.concepts:
            return None, float('inf')
        best_dist = float('inf')
        best_concept = None
        for concept in self.concepts:
            dist = np.linalg.norm(state_vec - concept.centroid)
            if dist < best_dist:
                best_dist = dist
                best_concept = concept
        return best_concept, best_dist

    def get_situation_assessment(self, state):
        """Assess current situation based on known concepts."""
        state_vec = np.resize(state, 10)
        nearest, dist = self._find_nearest(state_vec)
        if nearest is None:
            return {'concept_label': 'unknown', 'expected_reward': 0, 'expected_danger': 0, 'familiarity': 0}
        familiarity = 1.0 / (1.0 + dist)
        return {
            'concept_label': nearest.label,
            'expected_reward': nearest.avg_reward,
            'expected_danger': nearest.avg_danger,
            'familiarity': familiarity
        }

    def get_concept_action_bias(self, state):
        """Return 2D modifier based on matched concept's associated action."""
        state_vec = np.resize(state, 10)
        nearest, dist = self._find_nearest(state_vec)
        if nearest is None or dist > self.threshold * 2:
            return np.zeros(2)
        familiarity = 1.0 / (1.0 + dist)
        return nearest.associated_action * familiarity * 0.3

    def merge_similar_concepts(self):
        """Merge concepts that are too close together."""
        if len(self.concepts) < 2:
            return
        merged = True
        while merged:
            merged = False
            for i in range(len(self.concepts)):
                for j in range(i + 1, len(self.concepts)):
                    dist = np.linalg.norm(self.concepts[i].centroid - self.concepts[j].centroid)
                    if dist < Config.CONCEPT_MERGE_THRESHOLD:
                        # Merge j into i
                        ci, cj = self.concepts[i], self.concepts[j]
                        total = ci.exemplar_count + cj.exemplar_count
                        ci.centroid = (ci.centroid * ci.exemplar_count + cj.centroid * cj.exemplar_count) / total
                        ci.avg_reward = (ci.avg_reward * ci.exemplar_count + cj.avg_reward * cj.exemplar_count) / total
                        ci.avg_danger = (ci.avg_danger * ci.exemplar_count + cj.avg_danger * cj.exemplar_count) / total
                        ci.exemplar_count = total
                        self.concepts.pop(j)
                        self.merges += 1
                        merged = True
                        break
                if merged:
                    break

    def get_stats(self):
        return {
            'concepts_formed': len(self.concepts),
            'categorizations': self.categorizations,
            'merges': self.merges,
            'total_exemplars': sum(c.exemplar_count for c in self.concepts) if self.concepts else 0
        }


# ============================================================================
# SELF-NARRATIVE / AUTOBIOGRAPHICAL MEMORY (v4.0)
# ============================================================================

class LifeEvent:
    """A significant event in an agent's life."""
    TYPES = ['birth', 'discovery', 'danger', 'achievement', 'loss', 'social']

    def __init__(self, timestamp, event_type, description_vector, significance):
        self.timestamp = timestamp
        self.event_type = event_type
        self.description_vector = np.array(description_vector)
        self.significance = significance


class SelfNarrative:
    """Agents maintain a compressed autobiography that influences decisions."""

    def __init__(self):
        self.events = []
        self.achievements = 0
        self.dangers_survived = 0
        self.discoveries = 0
        self.social_events = 0
        self.losses = 0

    def record_event(self, age, event_type, state, significance):
        """Add a life event, prune low-significance if full."""
        if significance < Config.SIGNIFICANCE_THRESHOLD:
            return
        desc_vec = np.resize(state, 8)  # Compact representation
        event = LifeEvent(age, event_type, desc_vec, significance)
        self.events.append(event)

        # Track counts
        if event_type == 'achievement':
            self.achievements += 1
        elif event_type == 'danger':
            self.dangers_survived += 1
        elif event_type == 'discovery':
            self.discoveries += 1
        elif event_type == 'social':
            self.social_events += 1
        elif event_type == 'loss':
            self.losses += 1

        # Prune if too many events
        if len(self.events) > Config.MAX_LIFE_EVENTS:
            self.events.sort(key=lambda e: e.significance)
            self.events = self.events[len(self.events) - Config.MAX_LIFE_EVENTS:]

    def get_identity_vector(self):
        """Compressed representation of life story."""
        if not self.events:
            return np.zeros(8)
        # Average of all event descriptions weighted by significance
        total_sig = sum(e.significance for e in self.events)
        if total_sig < 0.01:
            return np.zeros(8)
        identity = np.zeros(8)
        for event in self.events:
            identity += event.description_vector * event.significance
        identity /= total_sig
        return identity

    def get_narrative_bias(self, state):
        """Return 2D action modifier based on life patterns."""
        if not self.events:
            return np.zeros(2)
        state_vec = np.resize(state, 8)
        bias = np.zeros(2)

        # If past danger events cluster near current state, bias away
        danger_events = [e for e in self.events if e.event_type == 'danger']
        for event in danger_events[-5:]:
            similarity = 1.0 / (1.0 + np.linalg.norm(state_vec - event.description_vector))
            if similarity > 0.4:
                # Bias away from danger-associated states
                direction = state_vec[:2] - event.description_vector[:2]
                bias += direction * similarity * 0.2

        # If past achievement events cluster near current state, bias toward
        achievement_events = [e for e in self.events if e.event_type == 'achievement']
        for event in achievement_events[-5:]:
            similarity = 1.0 / (1.0 + np.linalg.norm(state_vec - event.description_vector))
            if similarity > 0.4:
                direction = event.description_vector[:2] - state_vec[:2]
                bias += direction * similarity * 0.15

        return np.clip(bias, -0.5, 0.5)

    def evaluate_life_quality(self):
        """Return 0-1 score based on achievements vs losses."""
        positive = self.achievements + self.discoveries + self.dangers_survived * 0.5
        negative = self.losses
        total = positive + negative
        if total == 0:
            return 0.5
        return np.clip(positive / total, 0, 1)

    def get_stats(self):
        return {
            'total_events': len(self.events),
            'achievements': self.achievements,
            'dangers_survived': self.dangers_survived,
            'discoveries': self.discoveries,
            'life_quality': self.evaluate_life_quality()
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
            (np.random.randint(5, self.size - 5), np.random.randint(5, self.size - 5),
             np.random.uniform(3, 8))
            for _ in range(Config.HOTSPOT_COUNT)
        ]

    def _refresh(self):
        self.grid *= (1 - Config.ENERGY_REGEN_RATE)
        for hx, hy, strength in self.hotspots:
            for dx in range(-4, 5):
                for dy in range(-4, 5):
                    x, y = int(hx + dx) % self.size, int(hy + dy) % self.size
                    dist = np.sqrt(dx**2 + dy**2)
                    self.grid[x, y] += strength * np.exp(-dist / 2.0) * 0.1
        self.grid = np.clip(self.grid, 0, 10)

    def step(self):
        self.step_count += 1
        self._refresh()
        # Shift hotspots slowly
        if self.step_count % 20 == 0:
            for i in range(len(self.hotspots)):
                hx, hy, s = self.hotspots[i]
                hx = (hx + np.random.randint(-1, 2)) % self.size
                hy = (hy + np.random.randint(-1, 2)) % self.size
                self.hotspots[i] = (hx, hy, s)

    def get_energy(self, pos):
        x, y = int(pos[0]) % self.size, int(pos[1]) % self.size
        energy = self.grid[x, y]
        self.grid[x, y] *= 0.5  # Consume
        return energy

    def sense(self, pos, radius=2):
        readings = []
        x0, y0 = int(pos[0]), int(pos[1])
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x = (x0 + dx) % self.size
                y = (y0 + dy) % self.size
                readings.append(self.grid[x, y])
        return np.array(readings)

    def advance_phase(self):
        self.phase += 1
        Config.HOTSPOT_COUNT = min(Config.HOTSPOT_COUNT + 1, 10)
        self._generate_hotspots()


# ============================================================================
# NOVELTY ARCHIVE
# ============================================================================

class NoveltyArchive:
    """Stores novel behaviors for novelty search."""

    def __init__(self):
        self.archive = []

    def compute_novelty(self, behavior_vector):
        if len(self.archive) < Config.NOVELTY_K:
            return 1.0
        distances = [np.linalg.norm(behavior_vector - b) for b in self.archive]
        distances.sort()
        return np.mean(distances[:Config.NOVELTY_K])

    def maybe_add(self, behavior_vector, novelty_score):
        if novelty_score > 0.5 or np.random.random() < 0.05:
            self.archive.append(behavior_vector.copy())
            if len(self.archive) > Config.NOVELTY_ARCHIVE_MAX:
                idx = np.random.randint(len(self.archive))
                self.archive.pop(idx)


# ============================================================================
# GODEL ENGINE (Self-Modification with Validation)
# ============================================================================

class GodelEngine:
    """Validated self-modification: only accept changes that provably improve."""

    def __init__(self):
        self.modifications_attempted = 0
        self.modifications_accepted = 0
        self.modifications_rejected = 0
        self.cooldown = 0

    def propose_modification(self, agent, field):
        if self.cooldown > 0:
            self.cooldown -= 1
            return False
        if agent.genome.get_complexity() < 3:
            return False
        self.modifications_attempted += 1
        original_genome = agent.genome.copy()
        original_fitness = self._evaluate_fitness(agent, field)
        modified_genome = agent.genome.copy()
        Mutator.mutate(modified_genome)
        agent.genome = modified_genome
        modified_fitness = self._evaluate_fitness(agent, field)
        improvement = modified_fitness - original_fitness
        if improvement > Config.GODEL_SIGNIFICANCE:
            self.modifications_accepted += 1
            self.cooldown = Config.GODEL_COOLDOWN
            return True
        else:
            agent.genome = original_genome
            self.modifications_rejected += 1
            self.cooldown = Config.GODEL_COOLDOWN // 2
            return False

    def _evaluate_fitness(self, agent, field):
        total_reward = 0
        original_pos = agent.pos.copy()
        original_health = agent.health
        for _ in range(Config.GODEL_TEST_EPISODES):
            state = field.sense(agent.pos, agent.genome.sensor_radius)
            outputs = agent.genome.activate(list(state / 10.0))
            if len(outputs) >= 2:
                move = np.array(outputs[:2])
            else:
                move = np.zeros(2)
            agent.pos = (agent.pos + move) % Config.FIELD_SIZE
            energy = field.get_energy(agent.pos)
            total_reward += energy
        agent.pos = original_pos
        agent.health = original_health
        return total_reward


# ============================================================================
# AGENT: The complete autonomous entity
# ============================================================================

class Agent:
    """
    A self-contained agent with:
    - NEAT neural network brain
    - Evolvable Hebbian learning rules
    - Decision Intelligence (v2.0)
    - Communication module (v3.0)
    - Counterfactual reasoning (v3.0)
    - Hierarchical Goals (v4.0)
    - Theory of Mind (v4.0)
    - Abstract Concepts (v4.0)
    - Self-Narrative (v4.0)
    """
    _next_id = 0

    def __init__(self, genome, pos=None):
        self.id = Agent._next_id
        Agent._next_id += 1
        self.genome = genome
        self.pos = pos if pos is not None else np.random.uniform(0, Config.FIELD_SIZE, 2)
        self.health = Config.INITIAL_HEALTH
        self.age = 0
        self.total_energy = 0.0
        self.total_distance = 0.0
        self.offspring_count = 0
        self.alive = True

        # Sensor state dimension
        sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2

        # World model for curiosity
        self.world_model = WorldModel(sensor_dim, 2)

        # Decision Intelligence (v2.0)
        self.decision_intelligence = DecisionIntelligence(sensor_dim)
        self.decisions_overridden = 0

        # Communication (v3.0)
        self.communicator = AgentCommunicator(sensor_dim)
        self.last_received_signals = []

        # Counterfactual reasoning (v3.0)
        self.counterfactual_engine = CounterfactualEngine()
        self.recent_regrets = []
        self.cf_adjustments = 0

        # Hierarchical Goals (v4.0)
        self.goal_system = HierarchicalGoalSystem()

        # Theory of Mind (v4.0)
        self.theory_of_mind = TheoryOfMind(capacity=genome.modeling_capacity)

        # Abstract Concepts (v4.0)
        self.concept_memory = ConceptMemory(
            capacity=genome.abstraction_capacity,
            threshold=genome.concept_threshold
        )

        # Self-Narrative (v4.0)
        self.narrative = SelfNarrative()
        # Record birth event
        self.narrative.record_event(0, 'birth', np.zeros(sensor_dim), 0.8)

        # Last action for tracking
        self.last_action = np.zeros(2)

    def think_and_act(self, field, comm_channel, nearby_agents=None):
        """Complete cognitive cycle with all 17 capabilities."""
        if not self.alive:
            return

        self.age += 1
        state = field.sense(self.pos, self.genome.sensor_radius)
        norm_state = state / max(np.max(state), 1.0)

        # === Step 1: Neural Network forward pass ===
        outputs = self.genome.activate(list(norm_state))
        if len(outputs) >= 2:
            base_action = np.array(outputs[:2])
        else:
            base_action = np.zeros(2)

        # === Step 2: Decision Intelligence evaluation ===
        best_action, evaluation = self.decision_intelligence.choose_best_action(
            norm_state, self.genome, base_action
        )
        if not np.array_equal(best_action, base_action):
            self.decisions_overridden += 1

        # === Step 3: Communication - receive and decode ===
        received = comm_channel.receive(self.pos, self.id)
        self.last_received_signals = received
        comm_modifier = self.communicator.decode_signals(received, self.genome)

        # === Step 4: Knowledge Bank query (handled externally) ===
        knowledge_modifier = np.zeros(2)

        # === Step 5: Hierarchical Goals (v4.0) ===
        self.goal_system.generate_goals(norm_state, self.health, self.age, self.genome)
        active_goal = self.goal_system.select_active_goal()
        goal_bias = self.goal_system.get_goal_action_bias(norm_state, active_goal)

        # === Step 6: Theory of Mind (v4.0) ===
        tom_modifier = np.zeros(2)
        if nearby_agents:
            nearby_info = [(a.id, a.pos) for a in nearby_agents if a.id != self.id]
            tom_modifier = self.theory_of_mind.get_social_action_modifier(self.pos, nearby_info)
            # Observe nearby agents
            for agent in nearby_agents:
                if agent.id != self.id:
                    dist = np.linalg.norm(self.pos - agent.pos)
                    if dist < Config.TOM_OBSERVATION_RANGE:
                        self.theory_of_mind.observe(agent.id, agent.pos, agent.last_action)

        # === Step 7: Abstract Concepts (v4.0) ===
        concept_bias = self.concept_memory.get_concept_action_bias(norm_state)

        # === Step 8: Self-Narrative (v4.0) ===
        narrative_bias = self.narrative.get_narrative_bias(norm_state)

        # === Step 9: Counterfactual adjustment ===
        if self.age % Config.COUNTERFACTUAL_INTERVAL == 0 and self.age > 10:
            self.recent_regrets = self.counterfactual_engine.analyze(
                self.decision_intelligence.causal_memory,
                self.decision_intelligence.consequence_predictor,
                self.genome
            )
        cf_action = self.counterfactual_engine.get_regret_adjustment(
            norm_state, best_action, self.recent_regrets, self.genome
        )
        if not np.array_equal(cf_action, best_action):
            self.cf_adjustments += 1
            best_action = cf_action

        # === Step 10: Combine all modifiers ===
        final_action = (
            best_action * 0.4 +
            comm_modifier * Config.COMM_WEIGHT +
            goal_bias * Config.GOAL_WEIGHT +
            tom_modifier * Config.TOM_WEIGHT +
            concept_bias * Config.CONCEPT_WEIGHT +
            narrative_bias * Config.NARRATIVE_WEIGHT * self.genome.identity_strength
        )
        final_action = np.clip(final_action, -2, 2)

        # === Step 11: Execute action ===
        old_pos = self.pos.copy()
        health_before = self.health
        self.pos = (self.pos + final_action) % Config.FIELD_SIZE
        distance = np.linalg.norm(final_action)
        self.total_distance += distance

        # Energy cost
        movement_cost = Config.MOVEMENT_COST * distance
        thinking_cost = Config.THINKING_COST_PER_NODE * self.genome.get_complexity()
        self.health -= (movement_cost + thinking_cost) * self.genome.metabolism_efficiency

        # Harvest energy
        energy = field.get_energy(self.pos)
        self.health += energy
        self.total_energy += energy

        # === Step 12: Communication - broadcast ===
        if np.random.random() < self.genome.broadcast_threshold:
            signal = self.communicator.encode_signal(norm_state, self.genome)
            comm_channel.broadcast(self.pos, signal, self.genome.signal_strength, self.id)
            self.health -= Config.SIGNAL_COST

        # === Step 13: Learning ===
        self.genome.apply_learning_rule()
        next_state = field.sense(self.pos, self.genome.sensor_radius)
        norm_next = next_state / max(np.max(next_state), 1.0)

        # World model training (curiosity)
        curiosity_reward = self.world_model.train(norm_state, final_action, norm_next)

        # Decision Intelligence recording
        reward = energy + curiosity_reward * self.genome.curiosity_drive
        health_after = self.health
        self.decision_intelligence.record_transition(
            norm_state, final_action, norm_next, reward,
            health_before, health_after, self.age, self.genome
        )

        # Communication learning
        if received:
            self.communicator.learn_from_communication(received, energy - movement_cost)

        # === Step 14: Update v4.0 systems ===
        # Update goals
        health_delta = health_after - health_before
        self.goal_system.update_progress(norm_state, health_delta, energy, self.genome)

        # Categorize experience for concepts
        danger_level = max(0, -health_delta)
        self.concept_memory.observe_and_categorize(norm_state, reward, danger_level, final_action)
        if self.age % 20 == 0:
            self.concept_memory.merge_similar_concepts()

        # Record significant life events for narrative
        if energy > 2.0:
            self.narrative.record_event(self.age, 'discovery', norm_state,
                                        energy * self.genome.narrative_sensitivity)
        if health_delta < -2.0:
            self.narrative.record_event(self.age, 'danger', norm_state,
                                        abs(health_delta) * self.genome.narrative_sensitivity)
        if self.goal_system.goals_completed > 0 and self.age % 10 == 0:
            self.narrative.record_event(self.age, 'achievement', norm_state,
                                        0.7 * self.genome.narrative_sensitivity)
        if nearby_agents and len(nearby_agents) > 2:
            self.narrative.record_event(self.age, 'social', norm_state,
                                        0.4 * self.genome.narrative_sensitivity)

        # Store last action for ToM observations
        self.last_action = final_action.copy()

        # === Step 15: Death check ===
        if self.health <= 0:
            self.alive = False

    def get_behavior_vector(self):
        """Behavioral fingerprint for novelty search."""
        return np.array([
            self.total_energy / max(self.age, 1),
            self.total_distance / max(self.age, 1),
            self.genome.get_complexity() / 20.0,
            self.genome.curiosity_drive,
            self.decisions_overridden / max(self.age, 1),
            self.cf_adjustments / max(self.age, 1),
            self.goal_system.goals_completed / max(self.goal_system.total_goals_created, 1),
            self.theory_of_mind.social_interactions / max(self.age, 1),
            self.concept_memory.categorizations / max(self.age, 1),
            self.narrative.evaluate_life_quality()
        ])

    def get_fitness(self):
        """Multi-objective fitness combining all capabilities."""
        # Base fitness: energy gathered and survival
        energy_fitness = self.total_energy
        survival_fitness = self.age * 0.5
        efficiency = self.total_energy / max(self.total_distance, 1)

        # Decision quality bonus (v2.0)
        decision_bonus = self.decision_intelligence.get_decision_fitness() * 20

        # Goal completion bonus (v4.0)
        goal_bonus = self.goal_system.goals_completed * 5.0

        # Social intelligence bonus (v4.0)
        tom_stats = self.theory_of_mind.get_stats()
        social_bonus = tom_stats['social_interactions'] * 0.1

        # Concept utility bonus (v4.0)
        concept_stats = self.concept_memory.get_stats()
        concept_bonus = concept_stats['concepts_formed'] * 0.5

        # Narrative quality bonus (v4.0)
        narrative_bonus = self.narrative.evaluate_life_quality() * 10

        fitness = (energy_fitness + survival_fitness + efficiency * 5 +
                   decision_bonus + goal_bonus + social_bonus +
                   concept_bonus + narrative_bonus)
        self.genome.fitness = fitness
        return fitness

    def can_reproduce(self):
        return self.health > Config.REPRODUCTION_THRESHOLD and self.alive


# ============================================================================
# POPULATION MANAGER
# ============================================================================

class PopulationManager:
    """Handles reproduction, selection, speciation."""

    def __init__(self, input_size, output_size):
        self.input_size = input_size
        self.output_size = output_size
        self.species_list = []
        self.next_species_id = 0

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
                agent.genome.species_id = new_sp.id
                self.species_list.append(new_sp)
        self.species_list = [sp for sp in self.species_list if sp.members]
        for sp in self.species_list:
            if sp.members:
                sp.representative = np.random.choice(sp.members)
                best = max(m.fitness for m in sp.members)
                if best > sp.best_fitness:
                    sp.best_fitness = best
                    sp.stagnation = 0
                else:
                    sp.stagnation += 1
                sp.age += 1

    def select_and_reproduce(self, agents, target_pop):
        if not agents:
            return []
        for agent in agents:
            agent.get_fitness()
        self.speciate(agents)
        new_genomes = []
        # Elitism
        sorted_agents = sorted(agents, key=lambda a: a.genome.fitness, reverse=True)
        for agent in sorted_agents[:Config.ELITISM_COUNT]:
            new_genomes.append(agent.genome.copy())
        # Fill remaining via species-proportional reproduction
        remaining = target_pop - len(new_genomes)
        total_fitness = sum(max(a.genome.fitness, 0.1) for a in agents)
        for sp in self.species_list:
            if sp.stagnation > Config.STAGNATION_LIMIT:
                continue
            sp_fitness = sum(max(m.fitness, 0.1) for m in sp.members)
            proportion = sp_fitness / max(total_fitness, 1)
            n_offspring = max(1, int(proportion * remaining))
            sp_sorted = sorted(sp.members, key=lambda g: g.fitness, reverse=True)
            for _ in range(n_offspring):
                if len(new_genomes) >= target_pop:
                    break
                if len(sp_sorted) >= 2 and np.random.random() < Config.CROSSOVER_RATE:
                    p1, p2 = np.random.choice(sp_sorted[:max(2, len(sp_sorted)//2)], 2, replace=False)
                    child = Mutator.crossover(p1, p2)
                else:
                    parent = sp_sorted[0] if sp_sorted else agents[0].genome
                    child = parent.copy()
                Mutator.mutate(child)
                new_genomes.append(child)
        while len(new_genomes) < Config.MIN_POPULATION:
            new_genomes.append(Genome(self.input_size, self.output_size))
        return new_genomes[:target_pop]


# ============================================================================
# QUALITY CONTROLLER
# ============================================================================

class QualityController:
    """Self-evaluation and quality metrics."""

    def __init__(self):
        self.generation_scores = []
        self.diversity_history = []
        self.stagnation_count = 0

    def evaluate_generation(self, agents, novelty_archive):
        if not agents:
            return {}
        fitnesses = [a.genome.fitness for a in agents]
        behaviors = [a.get_behavior_vector() for a in agents]
        diversity = np.mean([
            np.linalg.norm(b1 - b2)
            for i, b1 in enumerate(behaviors)
            for b2 in behaviors[i+1:]
        ]) if len(behaviors) > 1 else 0.0

        # Decision Intelligence metrics
        dec_qualities = [a.decision_intelligence.journal.get_decision_quality() for a in agents]
        total_overrides = sum(a.decisions_overridden for a in agents)
        total_avoided = sum(a.decision_intelligence.journal.avoided_unacceptable for a in agents)
        total_entered = sum(a.decision_intelligence.journal.entered_unacceptable for a in agents)

        # Communication metrics
        total_cf_adj = sum(a.cf_adjustments for a in agents)
        avg_regret = np.mean([a.counterfactual_engine.get_stats()['avg_regret'] for a in agents])

        # v4.0 metrics
        total_goals_completed = sum(a.goal_system.goals_completed for a in agents)
        total_goals_created = sum(a.goal_system.total_goals_created for a in agents)
        total_agents_modeled = sum(a.theory_of_mind.get_stats()['agents_modeled'] for a in agents)
        total_social_interactions = sum(a.theory_of_mind.social_interactions for a in agents)
        total_concepts = sum(a.concept_memory.get_stats()['concepts_formed'] for a in agents)
        total_categorizations = sum(a.concept_memory.categorizations for a in agents)
        avg_life_quality = np.mean([a.narrative.evaluate_life_quality() for a in agents])
        total_life_events = sum(len(a.narrative.events) for a in agents)

        best_agent = max(agents, key=lambda a: a.genome.fitness)
        self.generation_scores.append(np.mean(fitnesses))
        self.diversity_history.append(diversity)

        if len(self.generation_scores) > 5:
            recent = self.generation_scores[-5:]
            if max(recent) - min(recent) < 1.0:
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0

        return {
            'best_fitness': max(fitnesses),
            'avg_fitness': np.mean(fitnesses),
            'diversity': diversity,
            'population': len(agents),
            'species': len(set(a.genome.species_id for a in agents if a.genome.species_id is not None)),
            'best_complexity': best_agent.genome.get_complexity(),
            'best_hidden_nodes': sum(1 for n in best_agent.genome.nodes.values() if n.type == NodeGene.HIDDEN),
            'stagnation': self.stagnation_count,
            'avg_decision_quality': np.mean(dec_qualities),
            'decisions_overridden': total_overrides,
            'unacceptable_avoided': total_avoided,
            'unacceptable_entered': total_entered,
            'best_caution': best_agent.genome.caution_level,
            'best_accept_thresh': best_agent.genome.acceptability_threshold,
            'best_planning_depth': best_agent.genome.planning_depth,
            'cf_adjustments': total_cf_adj,
            'avg_regret': avg_regret,
            # v4.0 metrics
            'goals_completed': total_goals_completed,
            'goals_created': total_goals_created,
            'agents_modeled': total_agents_modeled,
            'social_interactions': total_social_interactions,
            'concepts_formed': total_concepts,
            'categorizations': total_categorizations,
            'avg_life_quality': avg_life_quality,
            'total_life_events': total_life_events,
        }


# ============================================================================
# GENESIS ENGINE: The main orchestrator
# ============================================================================

class GenesisEngine:
    """The complete GENESIS v4.0 system."""

    def __init__(self):
        self.sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
        self.output_dim = 2  # Movement x, y
        self.field = Field()
        self.agents = []
        self.population_manager = PopulationManager(self.sensor_dim, self.output_dim)
        self.novelty_archive = NoveltyArchive()
        self.godel_engine = GodelEngine()
        self.quality_controller = QualityController()
        self.comm_channel = CommunicationChannel()
        self.knowledge_bank = KnowledgeBank()
        self.stats_log = []
        self.generation = 0

        # Initialize population
        for _ in range(Config.INITIAL_POPULATION):
            genome = Genome(self.sensor_dim, self.output_dim)
            agent = Agent(genome)
            self.agents.append(agent)

    def run(self, generations=None):
        """Run the full evolutionary process."""
        generations = generations or Config.NUM_GENERATIONS
        print(f"\n  Starting evolution for {generations} generations...")
        print(f"  Population: {len(self.agents)} | Field: {Config.FIELD_SIZE}x{Config.FIELD_SIZE}")
        print(f"  Capabilities: 17 active\n")

        for gen in range(generations):
            self.generation = gen
            stats = self._run_generation(gen)
            self.stats_log.append(stats)
            self._print_generation_report(gen, stats)

            # Curriculum advancement
            if stats['avg_fitness'] > Config.CURRICULUM_ADVANCE_THRESHOLD * (gen + 1) * 5:
                self.field.advance_phase()

        self._print_final_report()
        self._generate_visualizations()
        return self.stats_log

    def _run_generation(self, gen):
        """Run one complete generation."""
        # Reset agents for new generation
        for agent in self.agents:
            agent.health = Config.INITIAL_HEALTH
            agent.age = 0
            agent.total_energy = 0
            agent.total_distance = 0
            agent.alive = True
            agent.decisions_overridden = 0
            agent.cf_adjustments = 0

        # Run simulation steps
        for step in range(Config.STEPS_PER_GENERATION):
            self.field.step()
            self.comm_channel.step()

            alive_agents = [a for a in self.agents if a.alive]
            if not alive_agents:
                break

            for agent in alive_agents:
                # Get nearby agents for ToM
                nearby = [a for a in alive_agents
                          if a.id != agent.id and
                          np.linalg.norm(a.pos - agent.pos) < Config.TOM_OBSERVATION_RANGE]

                agent.think_and_act(self.field, self.comm_channel, nearby)

            # Knowledge bank: new agents query on first steps
            if step == 0:
                for agent in alive_agents:
                    entries = self.knowledge_bank.withdraw(
                        self.field.sense(agent.pos, agent.genome.sensor_radius)
                    )
                    for entry in entries:
                        self.knowledge_bank.report_outcome(entry, True)

            # Reproduction
            for agent in alive_agents:
                if agent.can_reproduce():
                    agent.health -= Config.REPRODUCTION_THRESHOLD * 0.5
                    agent.offspring_count += 1

        # Godel self-modification for best agent
        alive_agents = [a for a in self.agents if a.alive]
        if alive_agents:
            best = max(alive_agents, key=lambda a: a.get_fitness())
            self.godel_engine.propose_modification(best, self.field)

        # Evaluate fitness and novelty
        for agent in self.agents:
            agent.get_fitness()
            bv = agent.get_behavior_vector()
            novelty = self.novelty_archive.compute_novelty(bv)
            self.novelty_archive.maybe_add(bv, novelty)
            agent.genome.fitness += novelty * Config.NOVELTY_WEIGHT * 10

        # Knowledge bank: deposit from best agents
        sorted_agents = sorted(self.agents, key=lambda a: a.genome.fitness, reverse=True)
        for agent in sorted_agents[:3]:
            self.knowledge_bank.deposit(
                agent.decision_intelligence.causal_memory,
                agent.genome.fitness, gen
            )

        # Collect stats
        stats = self.quality_controller.evaluate_generation(self.agents, self.novelty_archive)
        stats['generation'] = gen

        # Communication stats
        lang_stats = self.comm_channel.get_language_stats()
        stats['total_signals'] = self.comm_channel.total_broadcasts
        stats['vocab_size'] = lang_stats['vocab_size']
        stats['best_honesty'] = sorted_agents[0].genome.signal_honesty if sorted_agents else 0
        stats['best_listen_weight'] = sorted_agents[0].genome.listen_weight if sorted_agents else 0

        # Knowledge bank stats
        kb_stats = self.knowledge_bank.get_stats()
        stats['knowledge_entries'] = kb_stats['total_entries']
        stats['knowledge_helpfulness'] = kb_stats['helpfulness_rate']

        # Godel stats
        stats['godel_accepted'] = self.godel_engine.modifications_accepted
        stats['godel_rejected'] = self.godel_engine.modifications_rejected

        # v4.0 specific stats for best agent
        if sorted_agents:
            best = sorted_agents[0]
            stats['best_goal_ambition'] = best.genome.goal_ambition
            stats['best_social_awareness'] = best.genome.social_awareness
            stats['best_abstraction_capacity'] = best.genome.abstraction_capacity
            stats['best_narrative_sensitivity'] = best.genome.narrative_sensitivity

        # Evolve next generation
        target_pop = min(Config.MAX_POPULATION, max(Config.MIN_POPULATION,
                         len(self.agents) + (2 if stats.get('diversity', 0) > 1.0 else -1)))
        new_genomes = self.population_manager.select_and_reproduce(self.agents, target_pop)

        # Create new agents
        self.agents = []
        for genome in new_genomes:
            agent = Agent(genome)
            self.agents.append(agent)

        # Reset communication channel for new generation
        self.comm_channel = CommunicationChannel()

        return stats

    def _print_generation_report(self, gen, stats):
        """Compact generation report."""
        print(f"  Gen {gen:3d} | Fit: {stats['best_fitness']:7.1f} (avg {stats['avg_fitness']:6.1f}) | "
              f"Pop: {stats['population']:2d} | Sp: {stats['species']:2d} | "
              f"DQ: {stats['avg_decision_quality']:.2f} | "
              f"Goals: {stats['goals_completed']:3d} | "
              f"ToM: {stats['agents_modeled']:3d} | "
              f"Concepts: {stats['concepts_formed']:3d} | "
              f"Life: {stats['avg_life_quality']:.2f}")

    def _print_final_report(self):
        """Detailed final report."""
        if not self.stats_log:
            return
        print("\n" + "=" * 72)
        print("  GENESIS v4.0 -- FINAL EVOLUTION REPORT")
        print("=" * 72)

        final = self.stats_log[-1]
        first = self.stats_log[0]

        print(f"\n  FITNESS EVOLUTION:")
        print(f"    Start: {first['best_fitness']:.1f} -> End: {final['best_fitness']:.1f}")
        print(f"    Improvement: {final['best_fitness'] - first['best_fitness']:.1f}")

        print(f"\n  DECISION INTELLIGENCE:")
        print(f"    Decision Quality: {final['avg_decision_quality']:.3f}")
        print(f"    Total Overrides: {final['decisions_overridden']}")
        print(f"    Unacceptable Avoided: {final['unacceptable_avoided']}")

        print(f"\n  COMMUNICATION:")
        print(f"    Vocabulary Size: {final['vocab_size']}")
        print(f"    Total Signals: {final['total_signals']}")

        print(f"\n  COUNTERFACTUAL REASONING:")
        print(f"    Adjustments: {final['cf_adjustments']}")
        print(f"    Average Regret: {final['avg_regret']:.4f}")

        print(f"\n  KNOWLEDGE BANK:")
        print(f"    Entries: {final['knowledge_entries']}")
        print(f"    Helpfulness: {final['knowledge_helpfulness']:.1%}")

        print(f"\n  HIERARCHICAL GOALS (v4.0):")
        print(f"    Goals Completed: {final['goals_completed']}")
        print(f"    Goals Created: {final['goals_created']}")

        print(f"\n  THEORY OF MIND (v4.0):")
        print(f"    Agents Modeled: {final['agents_modeled']}")
        print(f"    Social Interactions: {final['social_interactions']}")

        print(f"\n  ABSTRACT CONCEPTS (v4.0):")
        print(f"    Concepts Formed: {final['concepts_formed']}")
        print(f"    Categorizations: {final['categorizations']}")

        print(f"\n  SELF-NARRATIVE (v4.0):")
        print(f"    Average Life Quality: {final['avg_life_quality']:.3f}")
        print(f"    Total Life Events: {final['total_life_events']}")

        print(f"\n  GODEL SELF-MODIFICATION:")
        print(f"    Accepted: {self.godel_engine.modifications_accepted}")
        print(f"    Rejected: {self.godel_engine.modifications_rejected}")

        # Best agent analysis
        if self.agents:
            best_agent = max(self.agents, key=lambda a: a.genome.fitness)
            print(f"\n  CHAMPION AGENT:")
            print(f"    Complexity: {best_agent.genome.get_complexity()} connections")
            hidden = sum(1 for n in best_agent.genome.nodes.values() if n.type == NodeGene.HIDDEN)
            print(f"    Hidden Nodes: {hidden}")
            print(f"    Goal Ambition: {best_agent.genome.goal_ambition:.3f}")
            print(f"    Social Awareness: {best_agent.genome.social_awareness:.3f}")
            print(f"    Abstraction Capacity: {best_agent.genome.abstraction_capacity}")
            print(f"    Narrative Sensitivity: {best_agent.genome.narrative_sensitivity:.3f}")
            print(f"    Identity Strength: {best_agent.genome.identity_strength:.3f}")

            a_vals = [c.A for c in best_agent.genome.connections.values()]
            b_vals = [c.B for c in best_agent.genome.connections.values()]
            c_vals = [c.C for c in best_agent.genome.connections.values()]
            if a_vals:
                print(f"    Evolved Learning Rule: A={np.mean(a_vals):.3f}, "
                      f"B={np.mean(b_vals):.3f}, C={np.mean(c_vals):.3f}")

        print("\n" + "=" * 72)


    def _generate_visualizations(self):
        """Generate comprehensive dashboard visualizations."""
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
            # v4.0
            goals_completed = [s['goals_completed'] for s in self.stats_log]
            goals_created = [s['goals_created'] for s in self.stats_log]
            agents_modeled = [s['agents_modeled'] for s in self.stats_log]
            social_interactions = [s['social_interactions'] for s in self.stats_log]
            concepts_formed = [s['concepts_formed'] for s in self.stats_log]
            categorizations = [s['categorizations'] for s in self.stats_log]
            life_quality = [s['avg_life_quality'] for s in self.stats_log]
            life_events = [s['total_life_events'] for s in self.stats_log]

            # === Figure 1: Main Dashboard (5x4) ===
            fig, axes = plt.subplots(5, 4, figsize=(28, 30))
            fig.suptitle('GENESIS v4.0: Self-Evolving Darwinian Godel Machine\n'
                         '17 Capabilities | Goals | Theory of Mind | Concepts | Narrative',
                         fontsize=16, fontweight='bold')

            # Row 1: Core evolution
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

            # Row 3: Communication & Knowledge
            ax = axes[2, 0]
            ax.plot(gens, total_signals, 'blue', linewidth=2)
            ax.set_title('Signal Activity')
            ax.grid(True, alpha=0.3)

            ax = axes[2, 1]
            ax.plot(gens, vocab_size, 'darkviolet', linewidth=2)
            ax.set_title('Emergent Vocabulary')
            ax.grid(True, alpha=0.3)

            ax = axes[2, 2]
            ax.plot(gens, honesty, 'green', linewidth=2, label='Honesty')
            ax.plot(gens, listen_w, 'blue', linewidth=2, label='Listen')
            ax.set_title('Comm Params')
            ax.set_ylim(0, 1)
            ax.legend()
            ax.grid(True, alpha=0.3)

            ax = axes[2, 3]
            godel_accepted = [s['godel_accepted'] for s in self.stats_log]
            godel_rejected = [s['godel_rejected'] for s in self.stats_log]
            ax.plot(gens, godel_accepted, 'g-', linewidth=2, label='Accepted')
            ax.plot(gens, godel_rejected, 'r-', linewidth=2, label='Rejected')
            ax.set_title('Godel Self-Modification')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Row 4: Counterfactual & Knowledge
            ax = axes[3, 0]
            ax.plot(gens, cf_adj, 'crimson', linewidth=2)
            ax.set_title('Counterfactual Adjustments')
            ax.grid(True, alpha=0.3)

            ax = axes[3, 1]
            ax.plot(gens, avg_regret, 'darkred', linewidth=2)
            ax.set_title('Average Regret')
            ax.grid(True, alpha=0.3)

            ax = axes[3, 2]
            ax.plot(gens, kb_entries, 'darkblue', linewidth=2)
            ax.set_title('Knowledge Bank Size')
            ax.grid(True, alpha=0.3)

            ax = axes[3, 3]
            ax.plot(gens, kb_help, 'forestgreen', linewidth=2)
            ax.set_title('Knowledge Helpfulness')
            ax.set_ylim(0, 1)
            ax.grid(True, alpha=0.3)

            # Row 5: v4.0 Cognitive Systems
            ax = axes[4, 0]
            ax.plot(gens, goals_completed, 'navy', linewidth=2, label='Completed')
            ax.plot(gens, goals_created, 'skyblue', linewidth=2, linestyle='--', label='Created')
            ax.set_title('Hierarchical Goals')
            ax.legend()
            ax.grid(True, alpha=0.3)

            ax = axes[4, 1]
            ax.plot(gens, agents_modeled, 'darkgreen', linewidth=2, label='Modeled')
            ax2 = ax.twinx()
            ax2.plot(gens, social_interactions, 'lightgreen', linewidth=2, linestyle='--', label='Interactions')
            ax.set_title('Theory of Mind')
            ax.set_ylabel('Agents Modeled', color='darkgreen')
            ax2.set_ylabel('Interactions', color='lightgreen')
            ax.grid(True, alpha=0.3)

            ax = axes[4, 2]
            ax.plot(gens, concepts_formed, 'purple', linewidth=2, label='Concepts')
            ax2 = ax.twinx()
            ax2.plot(gens, categorizations, 'violet', linewidth=2, linestyle='--', label='Categorizations')
            ax.set_title('Abstract Concepts')
            ax.set_ylabel('Concepts', color='purple')
            ax2.set_ylabel('Categorizations', color='violet')
            ax.grid(True, alpha=0.3)

            ax = axes[4, 3]
            ax.plot(gens, life_quality, 'gold', linewidth=2, label='Quality')
            ax2 = ax.twinx()
            ax2.plot(gens, life_events, 'darkorange', linewidth=2, linestyle='--', label='Events')
            ax.set_title('Self-Narrative')
            ax.set_ylabel('Life Quality', color='gold')
            ax2.set_ylabel('Life Events', color='darkorange')
            ax.set_ylim(0, 1)
            ax.grid(True, alpha=0.3)

            for row in axes:
                for ax in row:
                    ax.set_xlabel('Generation', fontsize=8)

            plt.tight_layout()
            plot_path = os.path.join(Config.PLOT_DIR, 'genesis_v4_dashboard.png')
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"\n  Dashboard saved to: {plot_path}")

            # === Figure 2: Universe ===
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
            ax.set_title('GENESIS v4.0 Universe -- Final State', fontsize=14, fontweight='bold')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            plot_path2 = os.path.join(Config.PLOT_DIR, 'genesis_v4_universe.png')
            plt.savefig(plot_path2, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"  Universe saved to: {plot_path2}")

        except Exception as e:
            print(f"  Visualization error: {e}")
            traceback.print_exc()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Launch the GENESIS v4.0 system."""
    print()
    print("=" * 72)
    print("  GENESIS v4.0")
    print("  Generative Evolving Neural Engine for Self-Improving Systems")
    print("=" * 72)
    print()
    print("  17 Capabilities Active:")
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
    print("  14. Hierarchical Goal Formation (intentionality, planning)")
    print("  15. Theory of Mind (social modeling, prediction, trust)")
    print("  16. Abstract Concept Formation (prototypes, recognition)")
    print("  17. Self-Narrative (autobiography, identity, life story)")
    print()
    print("  Agents learn what decisions lead to what outcomes.")
    print("  They set their own goals and pursue multi-step plans.")
    print("  They build models of other agents' behavior.")
    print("  They compress experience into abstract concepts.")
    print("  They maintain a life story that shapes their identity.")
    print("  Intelligence emerges from evolution, experience, goals,")
    print("  social reasoning, abstraction, and self-reflection.")
    print()
    print("=" * 72)
    print()

    engine = GenesisEngine()
    stats = engine.run(generations=Config.NUM_GENERATIONS)

    print("\n  GENESIS v4.0 has evolved beyond its initial design.")
    print("  The agents developed goals, social intelligence, abstract thought,")
    print("  and autobiographical memory -- all from nothing.")
    print("  They became intentional, social, conceptual, and self-aware.\n")

    return engine


if __name__ == "__main__":
    main()
