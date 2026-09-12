import tempfile
import unittest
from pathlib import Path

from dgm_zero.archive import Archive
from dgm_zero.evolver import Candidate, DarwinAgentZero, EvolutionConfig


class LineageCorrectCreditTests(unittest.TestCase):
    @staticmethod
    def accepted_score(total: float) -> dict[str, float]:
        return {
            "correctness": total,
            "efficiency": total,
            "novelty": total,
            "safety": 1.0,
            "simplicity": total,
            "generalization": total,
            "weighted_total": total,
        }

    def test_archive_infers_source_from_referenced_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            parent = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.5},
                accepted=True,
                reason="parent",
            )
            child = archive.append(
                generation=1,
                parent_id=parent.id,
                expression="a + b + 1",
                score={"weighted_total": 0.6},
                accepted=True,
                reason="child",
            )
            self.assertEqual(child.source_expression, parent.expression)
            self.assertEqual(archive.records()[-1].source_expression, parent.expression)

    def test_archive_rejects_parent_source_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Archive(Path(tmp))
            parent = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score={"weighted_total": 0.5},
                accepted=True,
                reason="parent",
            )
            with self.assertRaisesRegex(ValueError, "does not match"):
                archive.append(
                    generation=1,
                    parent_id=parent.id,
                    expression="a + b + 1",
                    score={"weighted_total": 0.6},
                    accepted=True,
                    reason="wrong lineage",
                    source_expression="a * a + b",
                )

    def test_self_instruction_preserves_each_elite_as_its_own_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            archive = Archive(workspace)
            first = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score=self.accepted_score(0.80),
                accepted=True,
                reason="first",
            )
            second = archive.append(
                generation=0,
                parent_id=None,
                expression="a * a + b",
                score=self.accepted_score(0.82),
                accepted=True,
                reason="second",
            )
            agent = DarwinAgentZero(
                workspace,
                EvolutionConfig(
                    generations=1,
                    population=4,
                    seed=3,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            agent.mutate = (  # type: ignore[method-assign]
                lambda expression, generation: Candidate(
                    f"({expression}) + 7",
                    "wrap",
                )
            )
            candidates = agent.self_instruct(first, 0)
            by_source = {
                candidate.source_expression: candidate
                for candidate in candidates
                if candidate.source_expression in {first.expression, second.expression}
            }
            self.assertEqual(by_source[first.expression].parent_id, first.id)
            self.assertEqual(by_source[second.expression].parent_id, second.id)

    def test_evaluation_records_actual_source_and_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            archive = Archive(workspace)
            first = archive.append(
                generation=0,
                parent_id=None,
                expression="a + b",
                score=self.accepted_score(0.75),
                accepted=True,
                reason="first",
            )
            second = archive.append(
                generation=0,
                parent_id=None,
                expression="a * a + b",
                score=self.accepted_score(0.80),
                accepted=True,
                reason="second",
            )
            agent = DarwinAgentZero(
                workspace,
                EvolutionConfig(
                    generations=1,
                    population=1,
                    seed=4,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            source_total = agent.oracle.judge(second.expression).score.weighted_total
            candidate = Candidate(
                expression="a * a + 3 * b - gcd(a, b)",
                operator="wrap",
                source_expression=second.expression,
                parent_id=second.id,
            )
            child = agent.evaluate_and_archive(
                candidate,
                second,
                1,
                parent_total=source_total,
            )
            self.assertEqual(child.parent_id, second.id)
            self.assertNotEqual(child.parent_id, first.id)
            self.assertEqual(child.source_expression, second.expression)
            self.assertIsNotNone(child.verified_delta)

    def test_root_mutation_can_have_verified_source_without_fake_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            agent = DarwinAgentZero(
                workspace,
                EvolutionConfig(
                    generations=1,
                    population=1,
                    seed=2,
                    curriculum_enabled=False,
                    mined_case_limit=0,
                ),
            )
            source = "a + b"
            source_total = agent.oracle.judge(source).score.weighted_total
            candidate = Candidate(
                expression="a + b + 1",
                operator="append",
                source_expression=source,
                parent_id=None,
            )
            child = agent.evaluate_and_archive(
                candidate,
                None,
                0,
                parent_total=source_total,
            )
            self.assertIsNone(child.parent_id)
            self.assertEqual(child.source_expression, source)
            self.assertIsNotNone(child.verified_delta)

    def test_dedupe_prefers_candidate_with_archived_lineage(self):
        from dgm_zero.evolver import dedupe_candidates

        root = Candidate(
            "a + b + 1",
            "append",
            source_expression="a + b",
        )
        linked = Candidate(
            "a + b + 1",
            "append",
            source_expression="a + b",
            parent_id="parent-1",
        )
        result = dedupe_candidates([root, linked])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].parent_id, "parent-1")


if __name__ == "__main__":
    unittest.main()
