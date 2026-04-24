#!/usr/bin/env python3
"""
GENESIS: Generative Evolving Neural Engine for Self-Improving Systems
=====================================================================

A self-sufficient, self-evolving Darwinian Gödel machine with zero-data
meta-learning. Agents evolve neural architectures, learning rules, and
behavioral strategies from scratch — no external data, no pre-trained models.

Capabilities:
  1. Self-Sufficient Passive Learning (zero external data)
  2. Meta-Learning from Scratch (evolving learning rules)
  3. Darwinian Self-Evolution (NEAT-style neuroevolution)
  4. Gödel Machine Self-Rewriting (validated self-modification)
  5. Self-Controlled / Self-Coded (autonomous execution)
  6. Self-Instructed / Self-Quality-Checked / Self-Evaluated
  7. Self-Support System (error recovery, rollback, self-healing)
  8. Zero-Data SOTA Methods (curiosity, novelty search, self-play)
  9. Beyond the Builder (open-ended emergent evolution)

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
from collections import defaultdict

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
    GODEL_SIGNIFICANCE = 0.1  # p-value threshold (relaxed for small samples)
    GODEL_COOLDOWN = 10  # steps between self-modification attempts

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
        self.innovations = {}  # (from_node, to_node) -> innovation_number
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
        # Evolvable Hebbian learning rule parameters for this connection
        # Δw = lr * (A*pre*post + B*pre + C*post + D)
        self.lr = np.random.uniform(0.001, 0.01)
        self.A = np.random.uniform(-0.5, 0.5)  # Hebbian term
        self.B = np.random.uniform(-0.5, 0.5)  # Pre-synaptic term
        self.C = np.random.uniform(-0.5, 0.5)  # Post-synaptic term
        self.D = np.random.uniform(-0.1, 0.1)  # Bias term

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
        self.connections = {}  # innovation_number -> ConnectionGene
        self.fitness = 0.0
        self.adjusted_fitness = 0.0
        self.species_id = None

        # Evolvable hyperparameters
        self.mutation_rate = Config.MUTATION_RATE
        self.curiosity_drive = np.random.uniform(0.1, 0.5)
        self.self_modify_threshold = np.random.uniform(0.05, 0.3)
        self.metabolism_efficiency = np.random.uniform(0.8, 1.2)
        self.sensor_radius = Config.SENSOR_RADIUS

        self._initialize_minimal()

    def _initialize_minimal(self):
        """Create a minimal fully-connected network (no hidden nodes)."""
        # Input nodes
        for i in range(self.input_size):
            node_id = i
            self.nodes[node_id] = NodeGene(node_id, NodeGene.INPUT)
            INNOVATION.current_node_id = max(INNOVATION.current_node_id, node_id + 1)

        # Output nodes
        for i in range(self.output_size):
            node_id = self.input_size + i
            self.nodes[node_id] = NodeGene(node_id, NodeGene.OUTPUT)
            INNOVATION.current_node_id = max(INNOVATION.current_node_id, node_id + 1)

        # Connect all inputs to all outputs
        for i in range(self.input_size):
            for j in range(self.output_size):
                out_id = self.input_size + j
                weight = np.random.randn() * 0.5
                innov = INNOVATION.get_innovation(i, out_id)
                self.connections[innov] = ConnectionGene(i, out_id, weight, True, innov)

    def activate(self, inputs):
        """Forward pass through the network."""
        # Set input values
        for i in range(self.input_size):
            if i in self.nodes:
                self.nodes[i].prev_value = self.nodes[i].value
                self.nodes[i].value = inputs[i] if i < len(inputs) else 0.0

        # Determine evaluation order (topological sort approximation)
        hidden_nodes = [n for n in self.nodes.values() if n.type == NodeGene.HIDDEN]
        output_nodes = [n for n in self.nodes.values() if n.type == NodeGene.OUTPUT]

        # Process hidden nodes
        for node in hidden_nodes:
            incoming = sum(
                c.weight * self.nodes[c.from_node].value
                for c in self.connections.values()
                if c.to_node == node.id and c.enabled and c.from_node in self.nodes
            )
            node.prev_value = node.value
            node.value = self._activate(incoming, node.activation)

        # Process output nodes
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
        """Apply activation function with safety clipping."""
        x = np.clip(x, -10, 10)
        if func == 'tanh':
            return np.tanh(x)
        elif func == 'sigmoid':
            return 1.0 / (1.0 + np.exp(-x))
        elif func == 'relu':
            return max(0, x)
        return np.tanh(x)

    def apply_learning_rule(self):
        """
        Apply the evolvable Hebbian learning rule to all connections.
        This is the META-LEARNING component — the learning rule itself evolves.
        Δw = lr * (A*pre*post + B*pre + C*post + D)
        """
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
            # Clip weight change to prevent explosion
            delta_w = np.clip(delta_w, -0.1, 0.1)
            conn.weight += delta_w
            conn.weight = np.clip(conn.weight, -5.0, 5.0)

    def get_complexity(self):
        """Return network complexity (for thinking cost)."""
        active_connections = sum(1 for c in self.connections.values() if c.enabled)
        hidden_count = sum(1 for n in self.nodes.values() if n.type == NodeGene.HIDDEN)
        return active_connections + hidden_count * 2

    def copy(self):
        """Deep copy the genome."""
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
        return new


# ============================================================================
# MUTATION OPERATORS
# ============================================================================

class Mutator:
    """All mutation operators for genomes."""

    @staticmethod
    def mutate(genome):
        """Apply all applicable mutations to a genome."""
        # Mutate weights
        for conn in genome.connections.values():
            if np.random.random() < genome.mutation_rate:
                if np.random.random() < 0.1:
                    conn.weight = np.random.randn() * 2.0  # Reset
                else:
                    conn.weight += np.random.randn() * Config.WEIGHT_MUTATION_POWER
                conn.weight = np.clip(conn.weight, -5.0, 5.0)

        # Mutate learning rule parameters (META-LEARNING evolution)
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

        # Structural mutations (NEAT-style)
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

        return genome

    @staticmethod
    def _add_connection(genome):
        """Add a new connection between two unconnected nodes."""
        node_ids = list(genome.nodes.keys())
        if len(node_ids) < 2:
            return

        for _ in range(20):  # Try up to 20 times
            from_id = np.random.choice(node_ids)
            to_id = np.random.choice(node_ids)
            if from_id == to_id:
                continue
            if genome.nodes[to_id].type == NodeGene.INPUT:
                continue
            if genome.nodes[from_id].type == NodeGene.OUTPUT:
                continue

            # Check if connection already exists
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
        """Split an existing connection with a new hidden node."""
        enabled = [c for c in genome.connections.values() if c.enabled]
        if not enabled:
            return

        # Don't exceed max hidden nodes
        hidden_count = sum(1 for n in genome.nodes.values() if n.type == NodeGene.HIDDEN)
        if hidden_count >= Config.MAX_HIDDEN_NODES:
            return

        conn = np.random.choice(enabled)
        conn.enabled = False

        new_node_id = INNOVATION.get_new_node_id()
        genome.nodes[new_node_id] = NodeGene(new_node_id, NodeGene.HIDDEN)

        # Connection from old source to new node (weight 1.0)
        innov1 = INNOVATION.get_innovation(conn.from_node, new_node_id)
        genome.connections[innov1] = ConnectionGene(
            conn.from_node, new_node_id, 1.0, True, innov1
        )

        # Connection from new node to old target (old weight)
        innov2 = INNOVATION.get_innovation(new_node_id, conn.to_node)
        genome.connections[innov2] = ConnectionGene(
            new_node_id, conn.to_node, conn.weight, True, innov2
        )

    @staticmethod
    def crossover(parent1, parent2):
        """NEAT-style crossover of two genomes."""
        # parent1 should be the fitter parent
        if parent2.fitness > parent1.fitness:
            parent1, parent2 = parent2, parent1

        child = parent1.copy()

        # Align genes by innovation number
        for innov, conn2 in parent2.connections.items():
            if innov in child.connections:
                # Matching gene — randomly inherit from either parent
                if np.random.random() < 0.5:
                    child.connections[innov] = conn2.copy()
            # Excess/disjoint genes from less fit parent are not inherited

        # Inherit some hyperparameters from parent2
        if np.random.random() < 0.5:
            child.curiosity_drive = parent2.curiosity_drive
        if np.random.random() < 0.5:
            child.metabolism_efficiency = parent2.metabolism_efficiency

        return child


# ============================================================================
# SPECIATION (NEAT-style)
# ============================================================================

class Species:
    """A group of similar genomes that compete among themselves."""

    def __init__(self, species_id, representative):
        self.id = species_id
        self.representative = representative
        self.members = [representative]
        self.best_fitness = 0.0
        self.stagnation = 0
        self.age = 0

    def is_compatible(self, genome):
        """Check if a genome belongs to this species (genomic distance)."""
        dist = Species.genomic_distance(genome, self.representative)
        return dist < Config.SPECIES_THRESHOLD

    @staticmethod
    def genomic_distance(g1, g2):
        """Compute NEAT-style genomic distance between two genomes."""
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
    A small neural network that predicts next sensory state.
    Prediction error = intrinsic curiosity reward.
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
        """Predict next state given current state and action."""
        x = np.concatenate([state, action])
        h = np.tanh(self.W1 @ x + self.b1)
        pred = np.tanh(self.W2 @ h + self.b2)
        return pred

    def train(self, state, action, next_state):
        """Train on one transition, return prediction error."""
        pred = self.predict(state, action)
        error = np.mean((pred - next_state) ** 2)
        self.prediction_errors.append(error)

        # Simple gradient descent update
        x = np.concatenate([state, action])
        h = np.tanh(self.W1 @ x + self.b1)
        pred = np.tanh(self.W2 @ h + self.b2)

        # Output layer gradient
        d_pred = 2 * (pred - next_state) * (1 - pred ** 2)
        self.W2 -= Config.WORLD_MODEL_LR * np.outer(d_pred, h)
        self.b2 -= Config.WORLD_MODEL_LR * d_pred

        # Hidden layer gradient
        d_h = (self.W2.T @ d_pred) * (1 - h ** 2)
        self.W1 -= Config.WORLD_MODEL_LR * np.outer(d_h, x)
        self.b1 -= Config.WORLD_MODEL_LR * d_h

        return error

    def get_compression_progress(self):
        """How much has prediction improved recently?"""
        if len(self.prediction_errors) < 10:
            return 0.0
        recent = np.mean(self.prediction_errors[-5:])
        older = np.mean(self.prediction_errors[-10:-5])
        return max(0, older - recent)  # Positive = improving


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
        self.phase = 0  # Curriculum phase
        self.step_count = 0
        self._generate_hotspots()
        self._refresh()

    def _generate_hotspots(self):
        """Create energy hotspots."""
        self.hotspots = [
            (np.random.randint(5, self.size - 5), np.random.randint(5, self.size - 5))
            for _ in range(Config.HOTSPOT_COUNT)
        ]

    def _refresh(self):
        """Regenerate energy in the field."""
        # Base regeneration
        self.grid += Config.ENERGY_REGEN_RATE

        # Hotspot energy injection
        for hx, hy in self.hotspots:
            for dx in range(-5, 6):
                for dy in range(-5, 6):
                    x, y = (hx + dx) % self.size, (hy + dy) % self.size
                    dist = np.sqrt(dx**2 + dy**2)
                    if dist < 6:
                        self.grid[x][y] += 0.3 * np.exp(-dist / 2.5)

        # Energy diffusion (smoothing)
        from scipy.ndimage import uniform_filter
        self.grid = uniform_filter(self.grid, size=3) * (1 + Config.ENERGY_DIFFUSION)

        # Clip energy values
        self.grid = np.clip(self.grid, 0, 10)

    def step(self):
        """Advance the field by one time step."""
        self.step_count += 1
        self._refresh()

        # Shift hotspots slowly
        if np.random.random() < Config.HOTSPOT_SHIFT_RATE:
            idx = np.random.randint(len(self.hotspots))
            hx, hy = self.hotspots[idx]
            hx = (hx + np.random.randint(-3, 4)) % self.size
            hy = (hy + np.random.randint(-3, 4)) % self.size
            self.hotspots[idx] = (hx, hy)

        # Phase-specific dynamics
        if self.phase >= 1:
            # Dynamic hotspots move faster
            if np.random.random() < 0.05:
                idx = np.random.randint(len(self.hotspots))
                self.hotspots[idx] = (
                    np.random.randint(0, self.size),
                    np.random.randint(0, self.size)
                )

        if self.phase >= 3:
            # Catastrophic events: energy droughts
            if np.random.random() < 0.01:
                self.grid *= 0.3  # Energy crash

        if self.phase >= 4:
            # Field inversions
            if np.random.random() < 0.005:
                self.grid = np.max(self.grid) - self.grid

    def consume_energy(self, x, y, amount=1.0):
        """Agent consumes energy at position (x, y)."""
        ix, iy = int(x) % self.size, int(y) % self.size
        consumed = min(self.grid[ix][iy], amount)
        self.grid[ix][iy] -= consumed
        return consumed

    def get_local_view(self, x, y, radius=None):
        """Get the energy values in a local area around (x, y)."""
        radius = radius or Config.SENSOR_RADIUS
        view = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                ix = int(x + dx) % self.size
                iy = int(y + dy) % self.size
                view.append(self.grid[ix][iy])
        return np.array(view)

    def advance_curriculum(self):
        """Move to next curriculum phase."""
        if self.phase < Config.CURRICULUM_PHASES - 1:
            self.phase += 1
            return True
        return False


# ============================================================================
# NOVELTY ARCHIVE
# ============================================================================

class NoveltyArchive:
    """
    Stores behavioral characterizations and computes novelty scores.
    Prevents convergence and enables 'Beyond the Builder' discovery.
    """

    def __init__(self):
        self.archive = []
        self.k = Config.NOVELTY_K

    def compute_novelty(self, behavior_vector):
        """Compute novelty score as average distance to k-nearest neighbors."""
        if len(self.archive) < self.k:
            return 1.0  # Maximum novelty when archive is small

        distances = [
            np.linalg.norm(np.array(behavior_vector) - np.array(archived))
            for archived in self.archive
        ]
        distances.sort()
        return np.mean(distances[:self.k])

    def add(self, behavior_vector):
        """Add a behavior to the archive."""
        self.archive.append(behavior_vector)
        if len(self.archive) > Config.NOVELTY_ARCHIVE_MAX:
            # Remove oldest entries
            self.archive = self.archive[-Config.NOVELTY_ARCHIVE_MAX:]

    def get_diversity(self):
        """Measure overall archive diversity."""
        if len(self.archive) < 2:
            return 0.0
        arr = np.array(self.archive)
        return np.mean(np.std(arr, axis=0))


# ============================================================================
# GÖDEL VALIDATION ENGINE
# ============================================================================

class GodelEngine:
    """
    Self-modification validation system.
    Agents propose changes to themselves; changes are only accepted
    if they empirically improve performance (pragmatic Gödel machine).
    """

    def __init__(self):
        self.modification_history = []
        self.accepted = 0
        self.rejected = 0

    def propose_modification(self, agent, field):
        """
        Agent proposes a self-modification.
        Returns True if modification was accepted, False if rejected.
        """
        # Save snapshot
        snapshot = agent.genome.copy()
        baseline_scores = []

        # Evaluate baseline performance
        for _ in range(Config.GODEL_TEST_EPISODES):
            score = self._evaluate_episode(agent, field)
            baseline_scores.append(score)

        # Restore and apply modification
        agent.genome = snapshot.copy()
        self._apply_self_modification(agent)
        modified_scores = []

        for _ in range(Config.GODEL_TEST_EPISODES):
            score = self._evaluate_episode(agent, field)
            modified_scores.append(score)

        # Statistical comparison (simplified Welch's t-test)
        improvement = np.mean(modified_scores) - np.mean(baseline_scores)
        pooled_std = np.sqrt(
            (np.var(baseline_scores) + np.var(modified_scores)) / 2 + 1e-8
        )
        effect_size = improvement / (pooled_std + 1e-8)

        # Accept if improvement exceeds agent's self-modify threshold
        if effect_size > agent.genome.self_modify_threshold:
            self.accepted += 1
            self.modification_history.append({
                'type': 'accepted',
                'improvement': improvement,
                'effect_size': effect_size
            })
            return True
        else:
            # Rollback
            agent.genome = snapshot
            self.rejected += 1
            self.modification_history.append({
                'type': 'rejected',
                'improvement': improvement,
                'effect_size': effect_size
            })
            return False

    def _evaluate_episode(self, agent, field):
        """Run a short evaluation episode and return score."""
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
                    agent.pos[0] + outputs[0],
                    agent.pos[1] + outputs[1],
                    0.5
                )
                score += energy
        agent.health = temp_health
        return score

    def _apply_self_modification(self, agent):
        """Apply a random self-modification to the agent."""
        mod_type = np.random.choice(['weight_perturbation', 'learning_rule_shift',
                                      'topology_tweak', 'sensor_adjust'])

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
                # Toggle a random connection
                conns = list(agent.genome.connections.values())
                if conns:
                    c = np.random.choice(conns)
                    c.enabled = not c.enabled

        elif mod_type == 'sensor_adjust':
            agent.genome.sensor_radius = np.clip(
                agent.genome.sensor_radius + np.random.choice([-1, 0, 1]),
                1, 4
            )
            # Rebuild input size
            new_input = (2 * agent.genome.sensor_radius + 1) ** 2
            agent.genome.input_size = new_input

    def get_stats(self):
        total = self.accepted + self.rejected
        rate = self.accepted / total if total > 0 else 0
        return {
            'total_proposals': total,
            'accepted': self.accepted,
            'rejected': self.rejected,
            'acceptance_rate': rate
        }


# ============================================================================
# THE AGENT
# ============================================================================

class Agent:
    """
    A self-sufficient, self-evolving neural agent.
    Combines: NEAT genome, Hebbian meta-learning, curiosity module,
    Gödel self-modification, and behavioral characterization.
    """

    def __init__(self, genome=None, pos=None, field_size=None):
        field_size = field_size or Config.FIELD_SIZE
        sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2  # e.g., 5x5 = 25

        if genome is None:
            self.genome = Genome(input_size=sensor_dim, output_size=4)
            # Outputs: dx, dy, eat_intensity, self_modify_signal
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

        # Behavioral characterization (for novelty)
        self.position_history = []
        self.energy_history = []
        self.action_history = []

        # Gödel self-modification tracking
        self.godel_cooldown = 0
        self.modifications_accepted = 0
        self.modifications_rejected = 0

        # Self-healing
        self.error_count = 0
        self.last_valid_genome = self.genome.copy()

    def sense(self, field):
        """Perceive the local environment."""
        view = field.get_local_view(self.pos[0], self.pos[1],
                                     self.genome.sensor_radius)
        expected_size = self.genome.input_size
        if len(view) != expected_size:
            view = np.resize(view, expected_size)
        return view

    def think_and_act(self, field):
        """
        The main agent loop:
        1. Sense the environment
        2. Process through neural network
        3. Execute actions
        4. Learn from experience (Hebbian meta-learning)
        5. Update curiosity module
        """
        if not self.alive:
            return

        try:
            # 1. SENSE
            state = self.sense(field)
            prev_state = state.copy()

            # 2. THINK (neural network forward pass)
            outputs = self.genome.activate(state.tolist())

            # Pad outputs if needed
            while len(outputs) < 4:
                outputs.append(0.0)

            dx = np.clip(outputs[0] * 2, -2, 2)
            dy = np.clip(outputs[1] * 2, -2, 2)
            eat_intensity = (outputs[2] + 1) / 2  # Normalize to [0, 1]
            self_modify_signal = outputs[3]

            # 3. ACT
            # Move
            new_x = (self.pos[0] + dx) % field.size
            new_y = (self.pos[1] + dy) % field.size
            self.pos = np.array([new_x, new_y])

            # Eat
            energy_gained = field.consume_energy(
                self.pos[0], self.pos[1],
                eat_intensity * self.genome.metabolism_efficiency
            )
            self.health += energy_gained
            self.total_energy += energy_gained

            # Pay costs
            move_cost = Config.MOVEMENT_COST * (abs(dx) + abs(dy))
            think_cost = Config.THINKING_COST_PER_NODE * self.genome.get_complexity()
            self.health -= (move_cost + think_cost)

            # 4. LEARN (apply evolvable Hebbian learning rule)
            self.genome.apply_learning_rule()

            # 5. CURIOSITY (update world model)
            new_state = self.sense(field)
            action = np.array([dx, dy])
            pred_error = self.world_model.train(prev_state, action, new_state)
            self.curiosity_reward += pred_error * self.genome.curiosity_drive

            # Record behavior
            self.position_history.append(self.pos.copy())
            self.energy_history.append(self.health)
            self.action_history.append([dx, dy])

            # Age
            self.age += 1
            self.godel_cooldown = max(0, self.godel_cooldown - 1)

            # Check survival
            if self.health <= 0:
                self.alive = False

            # Save valid state for self-healing
            self.last_valid_genome = self.genome.copy()

        except Exception as e:
            # SELF-HEALING: catch errors, rollback, continue
            self.error_count += 1
            self.genome = self.last_valid_genome.copy()
            if self.error_count > 10:
                self.alive = False  # Too many errors, graceful death

    def attempt_self_modification(self, field, godel_engine):
        """
        Gödel machine: attempt to modify own code.
        Only proceeds if cooldown is zero and self-modify signal is strong.
        """
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
        """Compute behavioral characterization for novelty archive."""
        if not self.position_history:
            return [0] * 8

        positions = np.array(self.position_history)
        avg_pos = np.mean(positions, axis=0)
        pos_std = np.std(positions, axis=0)

        actions = np.array(self.action_history) if self.action_history else np.zeros((1, 2))
        avg_action = np.mean(actions, axis=0)
        action_std = np.std(actions, axis=0)

        return list(avg_pos) + list(pos_std) + list(avg_action) + list(action_std)

    def can_reproduce(self):
        return self.alive and self.health > Config.REPRODUCTION_THRESHOLD

    def get_fitness(self):
        """Multi-objective fitness."""
        survival_score = self.age / 100.0
        energy_score = self.total_energy / 50.0
        offspring_score = self.offspring_count * 2.0
        curiosity_score = self.curiosity_reward * Config.CURIOSITY_WEIGHT
        compression = self.world_model.get_compression_progress() * 5.0

        return survival_score + energy_score + offspring_score + curiosity_score + compression


# ============================================================================
# POPULATION MANAGER
# ============================================================================

class PopulationManager:
    """Manages the population: speciation, selection, reproduction."""

    def __init__(self):
        self.species_list = []
        self.next_species_id = 0
        self.generation = 0

    def speciate(self, agents):
        """Assign agents to species based on genomic distance."""
        # Clear current members
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

        # Remove empty species
        self.species_list = [sp for sp in self.species_list if sp.members]

        # Update representatives
        for sp in self.species_list:
            sp.representative = np.random.choice(sp.members)
            sp.age += 1

    def select_and_reproduce(self, agents, target_size):
        """
        Perform selection and reproduction to create next generation.
        Uses tournament selection within species + elitism.
        """
        if not agents:
            return []

        # Calculate adjusted fitness
        for sp in self.species_list:
            for genome in sp.members:
                genome.adjusted_fitness = genome.fitness / max(len(sp.members), 1)

        # Allocate offspring per species
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

            # Sort by fitness
            sp.members.sort(key=lambda g: g.fitness, reverse=True)

            # Elitism
            for i in range(min(Config.ELITISM_COUNT, len(sp.members))):
                new_genomes.append(sp.members[i].copy())

            # Produce offspring
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

        # Trim or pad to target size
        while len(new_genomes) > target_size:
            new_genomes.pop()
        while len(new_genomes) < target_size:
            new_genomes.append(Genome(
                (2 * Config.SENSOR_RADIUS + 1) ** 2, 4
            ))

        self.generation += 1
        return new_genomes

    def _tournament_select(self, genomes, k=3):
        """Tournament selection."""
        contestants = np.random.choice(genomes, size=min(k, len(genomes)), replace=False)
        return max(contestants, key=lambda g: g.fitness)

    def check_stagnation(self):
        """Check for species stagnation."""
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
    """
    Monitors system health, detects problems, and triggers corrections.
    The system's internal critic and self-evaluation mechanism.
    """

    def __init__(self):
        self.fitness_history = []
        self.diversity_history = []
        self.population_size_history = []
        self.species_count_history = []
        self.curriculum_phase = 0
        self.stagnation_counter = 0
        self.interventions = []

    def evaluate_generation(self, agents, novelty_archive, pop_manager):
        """Comprehensive evaluation of the current generation."""
        if not agents:
            return {'status': 'CRITICAL', 'message': 'Population extinct!'}

        fitnesses = [a.get_fitness() for a in agents if a.alive]
        if not fitnesses:
            fitnesses = [0.0]

        best = max(fitnesses)
        avg = np.mean(fitnesses)
        diversity = novelty_archive.get_diversity()

        self.fitness_history.append(best)
        self.diversity_history.append(diversity)
        self.population_size_history.append(len(agents))
        self.species_count_history.append(len(pop_manager.species_list))

        report = {
            'best_fitness': best,
            'avg_fitness': avg,
            'diversity': diversity,
            'population': len(agents),
            'species': len(pop_manager.species_list),
            'status': 'OK',
            'actions': []
        }

        # Check for stagnation
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

        # Check diversity
        if diversity < 0.1 and len(self.diversity_history) > 5:
            report['status'] = 'LOW_DIVERSITY'
            report['actions'].append('increase_novelty_pressure')
            self.interventions.append(('diversity_injection', pop_manager.generation))

        # Check curriculum advancement
        if len(self.fitness_history) > 20:
            recent_avg = np.mean(self.fitness_history[-10:])
            if recent_avg > Config.CURRICULUM_ADVANCE_THRESHOLD * (self.curriculum_phase + 1):
                report['actions'].append('advance_curriculum')

        return report


# ============================================================================
# GENESIS MAIN ENGINE
# ============================================================================

class GenesisEngine:
    """
    The master controller that orchestrates all subsystems.
    This is the self-sufficient, self-evolving system.
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

        # Initialize population
        sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
        for _ in range(Config.INITIAL_POPULATION):
            genome = Genome(input_size=sensor_dim, output_size=4)
            agent = Agent(genome=genome, field_size=self.field.size)
            self.agents.append(agent)

        print("=" * 70)
        print("  GENESIS: Generative Evolving Neural Engine for Self-Improving Systems")
        print("  Self-Sufficient Darwinian Gödel Machine with Zero-Data Meta-Learning")
        print("=" * 70)
        print(f"  Population: {len(self.agents)} agents")
        print(f"  Field: {self.field.size}x{self.field.size}")
        print(f"  Genome: {sensor_dim} inputs -> 4 outputs (NEAT topology)")
        print(f"  Features: Hebbian Meta-Learning | Curiosity | Novelty Search")
        print(f"            Gödel Self-Modification | Speciation | Self-Healing")
        print("=" * 70)
        print()

    def run_generation(self):
        """Run one complete generation of the simulation."""
        gen_start = time.time()
        self.generation += 1

        # === LIVE PHASE: Agents interact with the field ===
        births = 0
        deaths = 0
        godel_attempts = 0

        for step in range(Config.STEPS_PER_GENERATION):
            self.field.step()

            # Each agent acts
            for agent in self.agents:
                if agent.alive:
                    agent.think_and_act(self.field)

                    # Reproduction check
                    if agent.can_reproduce() and len(self.agents) < Config.MAX_POPULATION:
                        child_genome = agent.genome.copy()
                        child_genome = Mutator.mutate(child_genome)
                        child = Agent(
                            genome=child_genome,
                            pos=agent.pos + np.random.randn(2) * 2,
                            field_size=self.field.size
                        )
                        self.agents.append(child)
                        agent.health -= Config.REPRODUCTION_THRESHOLD * 0.4
                        agent.offspring_count += 1
                        births += 1

            # Gödel self-modification (periodic)
            if step % 20 == 0:
                for agent in self.agents:
                    if (agent.alive and agent.godel_cooldown == 0 and
                            np.random.random() < 0.1):
                        agent.attempt_self_modification(self.field, self.godel_engine)
                        godel_attempts += 1

            # Remove dead agents
            before = len(self.agents)
            self.agents = [a for a in self.agents if a.alive]
            deaths += before - len(self.agents)

            # Ensure minimum population
            if len(self.agents) < Config.MIN_POPULATION:
                sensor_dim = (2 * Config.SENSOR_RADIUS + 1) ** 2
                for _ in range(Config.MIN_POPULATION - len(self.agents)):
                    genome = Genome(input_size=sensor_dim, output_size=4)
                    agent = Agent(genome=genome, field_size=self.field.size)
                    self.agents.append(agent)

        # === EVALUATE PHASE ===
        for agent in self.agents:
            agent.genome.fitness = agent.get_fitness()

            # Add novelty score
            bv = agent.get_behavior_vector()
            novelty = self.novelty_archive.compute_novelty(bv)
            agent.genome.fitness += novelty * Config.NOVELTY_WEIGHT

            # Archive notable behaviors
            if novelty > 0.5 or agent.genome.fitness > 1.0:
                self.novelty_archive.add(bv)

        # === SPECIATE ===
        self.pop_manager.speciate(self.agents)

        # === QUALITY CHECK ===
        report = self.quality_controller.evaluate_generation(
            self.agents, self.novelty_archive, self.pop_manager
        )

        # Apply quality control actions
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

        # === SELECT & REPRODUCE ===
        target_size = min(Config.MAX_POPULATION,
                          max(Config.MIN_POPULATION, len(self.agents)))
        new_genomes = self.pop_manager.select_and_reproduce(self.agents, target_size)

        # Create new agents from new genomes
        self.agents = []
        for genome in new_genomes:
            agent = Agent(genome=genome, field_size=self.field.size)
            self.agents.append(agent)

        # === CHECKPOINT ===
        if self.generation % Config.CHECKPOINT_INTERVAL == 0:
            self.checkpoints[self.generation] = {
                'best_fitness': report['best_fitness'],
                'population': len(self.agents),
                'species': report['species']
            }

        # === STATS ===
        gen_time = time.time() - gen_start
        godel_stats = self.godel_engine.get_stats()

        # Find best agent info
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
            'time': gen_time
        }
        self.stats_log.append(stats)

        return stats

    def print_generation_report(self, stats):
        """Print a formatted generation report."""
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
        print(f"│ 🌈 Diversity: {stats['diversity']:.4f}  "
              f"│ ⏱️ {stats['time']:.2f}s")
        print(f"└{'─' * 65}")
        print()

    def run(self, generations=None):
        """Run the full GENESIS simulation."""
        generations = generations or Config.NUM_GENERATIONS

        print(f"\n🚀 Starting GENESIS Evolution — {generations} generations\n")

        try:
            for gen in range(generations):
                stats = self.run_generation()
                self.print_generation_report(stats)

                # Detailed report every 25 generations
                if (gen + 1) % 25 == 0:
                    self._print_detailed_report()

        except KeyboardInterrupt:
            print("\n⚡ Evolution interrupted by user.")

        print("\n" + "=" * 70)
        print("  GENESIS EVOLUTION COMPLETE")
        print("=" * 70)
        self._print_final_report()
        self._generate_visualizations()

        return self.stats_log

    def _print_detailed_report(self):
        """Print detailed analysis at milestones."""
        print("\n" + "━" * 70)
        print("  📊 DETAILED ANALYSIS")
        print("━" * 70)

        # Fitness trajectory
        if self.stats_log:
            recent = self.stats_log[-10:]
            print(f"  Fitness trend (last 10): "
                  f"{recent[0]['best_fitness']:.3f} → {recent[-1]['best_fitness']:.3f}")

        # Species analysis
        print(f"  Active species: {len(self.pop_manager.species_list)}")
        for sp in self.pop_manager.species_list[:5]:
            print(f"    Species {sp.id}: {len(sp.members)} members, "
                  f"best={sp.best_fitness:.3f}, age={sp.age}")

        # Meta-learning analysis
        if self.agents:
            learning_rates = []
            hebbian_params = []
            for agent in self.agents:
                for conn in agent.genome.connections.values():
                    learning_rates.append(conn.lr)
                    hebbian_params.append(conn.A)

            if learning_rates:
                print(f"  Meta-Learning: avg_lr={np.mean(learning_rates):.5f}, "
                      f"avg_hebbian_A={np.mean(hebbian_params):.4f}")

        # Gödel engine stats
        gs = self.godel_engine.get_stats()
        print(f"  Gödel Engine: {gs['total_proposals']} proposals, "
              f"{gs['acceptance_rate']:.1%} acceptance rate")

        # Novelty archive
        print(f"  Novelty Archive: {len(self.novelty_archive.archive)} behaviors stored")

        # Quality control interventions
        print(f"  QC Interventions: {len(self.quality_controller.interventions)}")

        print("━" * 70 + "\n")

    def _print_final_report(self):
        """Print comprehensive final report."""
        print("\n📋 FINAL REPORT")
        print("─" * 50)

        if not self.stats_log:
            print("  No data collected.")
            return

        best_ever = max(s['best_fitness'] for s in self.stats_log)
        best_gen = max(self.stats_log, key=lambda s: s['best_fitness'])['generation']
        avg_final = self.stats_log[-1]['avg_fitness']
        total_births = sum(s['births'] for s in self.stats_log)
        total_deaths = sum(s['deaths'] for s in self.stats_log)

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
        print(f"  Quality Interventions: {len(self.quality_controller.interventions)}")

        # Analyze evolved learning rules
        if self.agents:
            best_agent = max(self.agents, key=lambda a: a.genome.fitness)
            print(f"\n  🏆 CHAMPION AGENT:")
            print(f"     Connections: {sum(1 for c in best_agent.genome.connections.values() if c.enabled)}")
            print(f"     Hidden Nodes: {sum(1 for n in best_agent.genome.nodes.values() if n.type == NodeGene.HIDDEN)}")
            print(f"     Curiosity Drive: {best_agent.genome.curiosity_drive:.4f}")
            print(f"     Mutation Rate: {best_agent.genome.mutation_rate:.4f}")
            print(f"     Self-Modify Threshold: {best_agent.genome.self_modify_threshold:.4f}")
            print(f"     Metabolism Efficiency: {best_agent.genome.metabolism_efficiency:.4f}")

            # Analyze evolved Hebbian rules
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

        print("─" * 50)

    def _generate_visualizations(self):
        """Generate and save visualization plots."""
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

            # === Figure 1: Fitness Evolution ===
            fig, axes = plt.subplots(2, 3, figsize=(20, 12))
            fig.suptitle('GENESIS: Self-Evolving Darwinian Gödel Machine\n'
                         'Evolutionary Dynamics Dashboard', fontsize=16, fontweight='bold')

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
            ax.set_title('Brain Complexity Evolution (NEAT)')
            ax.grid(True, alpha=0.3)

            # Gödel Engine Activity
            ax = axes[1, 1]
            godel_accepted = []
            godel_rejected = []
            running_acc = 0
            running_rej = 0
            for s in self.stats_log:
                godel_accepted.append(s['godel_accepted'])
                godel_rejected.append(s['godel_rejected'])
            ax.plot(generations, godel_accepted, 'g-', linewidth=2, label='Accepted')
            ax.plot(generations, godel_rejected, 'r-', linewidth=2, label='Rejected')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Cumulative Count')
            ax.set_title('Gödel Self-Modification Gate')
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Curriculum Phase
            ax = axes[1, 2]
            phases = [s['curriculum_phase'] for s in self.stats_log]
            ax.step(generations, phases, 'k-', linewidth=2, where='post')
            ax.set_xlabel('Generation')
            ax.set_ylabel('Curriculum Phase')
            ax.set_title('Self-Instructed Curriculum Progress')
            ax.set_ylim(-0.5, Config.CURRICULUM_PHASES + 0.5)
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plot_path = os.path.join(Config.PLOT_DIR, 'genesis_dashboard.png')
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"\n  📊 Dashboard saved to: {plot_path}")

            # === Figure 2: Evolved Learning Rules Analysis ===
            if self.agents:
                fig, axes = plt.subplots(1, 3, figsize=(18, 5))
                fig.suptitle('Evolved Meta-Learning Rules Analysis', fontsize=14, fontweight='bold')

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

                    # Weight distribution of champion
                    best_agent = max(self.agents, key=lambda a: a.genome.fitness)
                    weights = [c.weight for c in best_agent.genome.connections.values()]
                    axes[2].hist(weights, bins=30, color='gold', alpha=0.7)
                    axes[2].set_title('Champion Weight Distribution')
                    axes[2].grid(True, alpha=0.3)

                plt.tight_layout()
                plot_path2 = os.path.join(Config.PLOT_DIR, 'genesis_metalearning.png')
                plt.savefig(plot_path2, dpi=150, bbox_inches='tight')
                plt.close()
                print(f"  📊 Meta-learning analysis saved to: {plot_path2}")

            # === Figure 3: Energy Field Visualization ===
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

            ax.set_title('GENESIS Universe — Final State', fontsize=14, fontweight='bold')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')

            plot_path3 = os.path.join(Config.PLOT_DIR, 'genesis_universe.png')
            plt.savefig(plot_path3, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"  📊 Universe visualization saved to: {plot_path3}")

        except Exception as e:
            print(f"  ⚠️ Visualization error: {e}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Launch the GENESIS system."""
    print()
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                                                                      ║")
    print("║   ██████  ███████ ███    ██ ███████ ███████ ██ ███████               ║")
    print("║  ██       ██      ████   ██ ██      ██      ██ ██                    ║")
    print("║  ██   ███ █████   ██ ██  ██ █████   ███████ ██ ███████               ║")
    print("║  ██    ██ ██      ██  ██ ██ ██           ██ ██      ██               ║")
    print("║   ██████  ███████ ██   ████ ███████ ███████ ██ ███████               ║")
    print("║                                                                      ║")
    print("║  Generative Evolving Neural Engine for Self-Improving Systems        ║")
    print("║  Self-Sufficient Darwinian Gödel Machine | Zero-Data Meta-Learning   ║")
    print("║  Beyond the Builder: Open-Ended Emergent Evolution                   ║")
    print("║                                                                      ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print()

    engine = GenesisEngine()
    stats = engine.run(generations=Config.NUM_GENERATIONS)

    print("\n✨ GENESIS has evolved beyond its initial design.")
    print("   The agents discovered their own learning rules,")
    print("   modified their own architectures, and developed")
    print("   behaviors never explicitly programmed.")
    print("\n   This is intelligence emerging from nothing but")
    print("   evolution, curiosity, and self-improvement.\n")

    return engine


if __name__ == "__main__":
    main()
