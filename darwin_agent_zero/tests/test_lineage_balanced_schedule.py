import random
import unittest

from dgm_zero.evolver import Candidate
from dgm_zero.search_schedule import round_robin_by_lineage


def lineage(candidate: Candidate) -> str:
    return candidate.source_expression or candidate.expression


class LineageBalancedScheduleTests(unittest.TestCase):
    def test_first_round_covers_distinct_lineages(self):
        items = [
            Candidate("a1", "wrap", "a"),
            Candidate("a2", "wrap", "a"),
            Candidate("b1", "append", "b"),
            Candidate("b2", "append", "b"),
            Candidate("c1", "replace", "c"),
            Candidate("c2", "replace", "c"),
        ]
        scheduled = round_robin_by_lineage(
            items,
            lineage_key=lineage,
            rng=random.Random(7),
        )
        self.assertEqual(len({lineage(item) for item in scheduled[:3]}), 3)

    def test_schedule_preserves_every_candidate_exactly_once(self):
        items = [
            Candidate(f"a{i}", "wrap", "a") for i in range(4)
        ] + [
            Candidate(f"b{i}", "append", "b") for i in range(2)
        ]
        scheduled = round_robin_by_lineage(
            items,
            lineage_key=lineage,
            rng=random.Random(11),
        )
        self.assertEqual(len(scheduled), len(items))
        self.assertEqual(
            {item.expression for item in scheduled},
            {item.expression for item in items},
        )

    def test_schedule_is_seed_deterministic(self):
        items = [
            Candidate(f"{source}{index}", "wrap", source)
            for source in ("a", "b", "c")
            for index in range(3)
        ]
        first = round_robin_by_lineage(
            items,
            lineage_key=lineage,
            rng=random.Random(19),
        )
        second = round_robin_by_lineage(
            items,
            lineage_key=lineage,
            rng=random.Random(19),
        )
        self.assertEqual(
            [item.expression for item in first],
            [item.expression for item in second],
        )

    def test_root_seed_and_mutation_share_source_lineage(self):
        root = Candidate("a + b", "seed")
        mutation = Candidate("a + b + 1", "append", "a + b")
        other = Candidate("a * a + b", "seed")
        scheduled = round_robin_by_lineage(
            [root, mutation, other],
            lineage_key=lineage,
            rng=random.Random(3),
        )
        self.assertNotEqual(lineage(scheduled[0]), lineage(scheduled[1]))

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(
            round_robin_by_lineage(
                [],
                lineage_key=lambda item: item,
                rng=random.Random(1),
            ),
            [],
        )

    def test_rng_type_is_enforced(self):
        with self.assertRaisesRegex(TypeError, "random.Random"):
            round_robin_by_lineage(
                [1],
                lineage_key=lambda item: item,
                rng=object(),  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
