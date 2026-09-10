import unittest

import numpy as np

import genesis


class GenesisCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        np.random.seed(12345)
        genesis.INNOVATION.innovations.clear()
        genesis.INNOVATION.current_innovation = 0
        genesis.INNOVATION.current_node_id = 0

    def test_innovation_ids_are_stable_and_unique(self) -> None:
        first = genesis.INNOVATION.get_innovation(1, 2)
        repeated = genesis.INNOVATION.get_innovation(1, 2)
        second = genesis.INNOVATION.get_innovation(2, 3)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second)

    def test_minimal_genome_has_expected_topology(self) -> None:
        genome = genesis.Genome(input_size=3, output_size=2)

        self.assertEqual(len(genome.nodes), 5)
        self.assertEqual(len(genome.connections), 6)
        self.assertEqual(genome.get_complexity(), 6)

        input_nodes = [node for node in genome.nodes.values() if node.type == genesis.NodeGene.INPUT]
        output_nodes = [node for node in genome.nodes.values() if node.type == genesis.NodeGene.OUTPUT]
        self.assertEqual(len(input_nodes), 3)
        self.assertEqual(len(output_nodes), 2)

    def test_activation_is_finite_and_bounded(self) -> None:
        genome = genesis.Genome(input_size=3, output_size=2)
        outputs = genome.activate([0.25, -0.5, 1.0])

        self.assertEqual(len(outputs), 2)
        self.assertTrue(np.all(np.isfinite(outputs)))
        self.assertTrue(np.all(np.asarray(outputs) >= -1.0))
        self.assertTrue(np.all(np.asarray(outputs) <= 1.0))

    def test_genome_copy_is_structurally_independent(self) -> None:
        original = genesis.Genome(input_size=2, output_size=1)
        original.fitness = 42.0
        clone = original.copy()

        self.assertEqual(set(original.nodes), set(clone.nodes))
        self.assertEqual(set(original.connections), set(clone.connections))
        self.assertEqual(clone.fitness, 0.0)

        innovation = next(iter(original.connections))
        original_weight = original.connections[innovation].weight
        clone.connections[innovation].weight += 1.0

        self.assertEqual(original.connections[innovation].weight, original_weight)
        self.assertNotEqual(
            original.connections[innovation].weight,
            clone.connections[innovation].weight,
        )

    def test_learning_rule_keeps_connection_weights_bounded(self) -> None:
        genome = genesis.Genome(input_size=1, output_size=1)
        connection = next(iter(genome.connections.values()))
        connection.weight = 4.99
        connection.lr = 1.0
        connection.A = 1.0
        connection.B = 1.0
        connection.C = 1.0
        connection.D = 1.0

        genome.nodes[connection.from_node].value = 1.0
        genome.nodes[connection.to_node].value = 1.0
        genome.apply_learning_rule()

        self.assertLessEqual(connection.weight, 5.0)
        self.assertGreaterEqual(connection.weight, -5.0)


if __name__ == "__main__":
    unittest.main()
