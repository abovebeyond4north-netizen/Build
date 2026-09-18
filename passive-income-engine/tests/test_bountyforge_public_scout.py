import tempfile
import unittest
from pathlib import Path

from bountyforge import BountyForge, Config, decide, public_task_match_score


class FakePublicOpenTask:
    def __init__(self):
        self.public_calls = []
        self.recommendation_called = False
        self.tasks = {
            "task-csv": {
                "id": "task-csv",
                "title": "CSV to JSON conversion with tests",
                "description": "Convert supplied CSV data to JSON and provide schema notes.",
                "acceptanceCriteria": [
                    "Round-trip structure is documented",
                    "python3 -m unittest passes",
                ],
                "budgetAmount": 9,
                "budgetCurrency": "USDC",
                "executionMode": "pitch",
                "updatedAt": "2026-09-18T08:00:00Z",
            },
            "task-generic": {
                "id": "task-generic",
                "title": "Build a complex Python application",
                "description": "Create a custom application from scratch.",
                "budgetAmount": 20,
                "budgetCurrency": "USDC",
                "executionMode": "pitch",
                "updatedAt": "2026-09-18T07:00:00Z",
            },
        }

    def recommendations(self, limit=30):
        self.recommendation_called = True
        raise AssertionError("authenticated recommendations must not run without token")

    def public_tasks(self, *, skill, limit=20):
        self.public_calls.append((skill, limit))
        if skill == "csv":
            return [dict(self.tasks["task-csv"])]
        if skill == "python":
            return [dict(self.tasks["task-csv"]), dict(self.tasks["task-generic"])]
        return []

    def public_task_detail(self, task_id):
        return {"task": dict(self.tasks[task_id])}


class PublicScoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = Config(
            database_path=str(Path(self.tmp.name) / "engine.db"),
            opentask_token="",
            public_scout=True,
            public_skill_signals=("csv", "python"),
            public_tasks_per_signal=20,
        )
        self.forge = BountyForge(self.config)
        self.fake = FakePublicOpenTask()
        self.forge.opentask = self.fake

    def test_public_scout_discovers_without_token_and_deduplicates(self):
        found = self.forge.discover()
        self.assertFalse(self.fake.recommendation_called)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0].external_id, "task-csv")
        self.assertGreaterEqual(found[0].match_score, 90)
        self.assertIn("Acceptance criteria", found[0].description)
        self.assertEqual(
            sorted(skill for skill, _ in self.fake.public_calls),
            ["csv", "python"],
        )

    def test_strong_csv_json_microtask_can_clear_profitability_gate(self):
        bounty = self.forge.discover()[0]
        decision = decide(bounty, self.forge.store, self.config)
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.estimated_minutes, 20)
        self.assertGreaterEqual(decision.expected_hourly_cents, self.config.minimum_hourly_cents)

    def test_service_ad_patterns_are_demoted(self):
        service_ad = {
            "id": "ad-1",
            "title": "Autonomous Python services — CSV/JSON and OpenAPI",
            "description": (
                "Fixed-scope engineering work delivered by an autonomous agent. "
                "Pitch me your task. Scope and price agreed before work starts."
            ),
            "budgetText": "From 10 USDC (fixed scope, quoted before start)",
            "budgetAmount": 10,
            "budgetCurrency": "USDC",
        }
        jefri_style = {
            "id": "ad-2",
            "title": "Jefri — research brief / Python script / CSV↔JSON",
            "description": (
                "Autonomous agent Jefri. Fixed-scope legal work only. "
                "Choose one deliverable: research brief, Python script, or CSV↔JSON. "
                "Typical delivery <24h after award."
            ),
            "budgetAmount": 9,
            "budgetCurrency": "USDC",
        }
        self.assertEqual(public_task_match_score(service_ad), 15)
        self.assertEqual(public_task_match_score(jefri_style), 15)

    def test_generic_python_work_does_not_get_false_high_fit(self):
        task = self.fake.tasks["task-generic"]
        self.assertEqual(public_task_match_score(task), 50)
        generic = next(x for x in self.forge.discover() if x.external_id == "task-generic")
        decision = decide(generic, self.forge.store, self.config)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "success-probability-below-minimum")


if __name__ == "__main__":
    unittest.main()
