import tempfile
import unittest
from pathlib import Path

from bountyforge import Bounty, BountyForge, Config, decide, public_task_match_score, safe_solver_payload


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

    def test_public_only_run_does_not_initialize_solver_or_repo_queues(self):
        root = Path(self.tmp.name)
        self.forge.config = Config(
            database_path=str(root / "public-only.db"),
            opentask_token="",
            public_scout=True,
            public_skill_signals=("csv",),
            public_tasks_per_signal=20,
            auto_solve=False,
            auto_repo_verify=False,
            auto_deliver=False,
            reconcile_payments=False,
            queue_dir=str(root / "must-not-create-bounty-queue"),
            queue_secret="",
            repo_verify_dir=str(root / "must-not-create-repo-verify"),
            repo_verify_secret="",
        )
        self.forge.store = self.forge.store.__class__(self.forge.config.database_path)
        self.forge.store.init()
        self.forge.opentask = self.fake

        result = self.forge.run_once()

        self.assertTrue(result["enabled"])
        self.assertFalse(Path(self.forge.config.queue_dir).exists())
        self.assertFalse(Path(self.forge.config.repo_verify_dir).exists())
        self.assertEqual(result["solver"]["verified"], 0)
        self.assertEqual(result["repo_verifier"]["verified"], 0)

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
        live_csv_offer = {
            "id": "ad-3",
            "title": "CSV ↔ JSON conversion scripts — tested, delivered in 24h",
            "description": (
                "Reliable, tested Python scripts for CSV→JSON and JSON→CSV conversion. "
                "Each deliverable ships with unit tests and SHA256. "
                "Delivery within 24h, revisions included."
            ),
            "budgetAmount": 100,
            "budgetCurrency": "USDC",
        }
        ready_template = {
            "id": "ad-4",
            "title": "Telegram appointment booking bot — ready template (aiogram 3)",
            "description": "Ready-made Telegram booking bot template in Python.",
            "budgetAmount": 30,
            "budgetCurrency": "USDT",
        }
        self.assertEqual(public_task_match_score(service_ad), 15)
        self.assertEqual(public_task_match_score(jefri_style), 15)
        self.assertEqual(public_task_match_score(live_csv_offer), 15)
        self.assertEqual(public_task_match_score(ready_template), 15)

    def test_genuine_csv_to_json_script_request_routes_to_package_handler(self):
        title = "Build a simple Python script to parse CSV files and generate JSON output"
        description = (
            "Create a reusable Python script that can parse CSV files of any structure "
            "and convert them to properly formatted JSON output. Handle delimiters and errors."
        )
        payload = safe_solver_payload(title, description)
        self.assertEqual(payload, {"kind": "csv_to_json_cli_package"})

        bounty = Bounty(
            source="opentask",
            external_id="buyer-csv-1",
            title=title,
            description=description,
            reward_cents=10000,
            currency="USDC",
            task_url="https://opentask.ai/tasks/buyer-csv-1",
            execution_mode="pitch",
            match_score=98,
            updated_at="2026-09-18T09:00:00Z",
            raw={},
        )
        decision = decide(bounty, self.forge.store, self.config)
        self.assertTrue(decision.eligible)
        self.assertEqual(decision.estimated_minutes, 5)

    def test_summary_exposes_auditable_candidate_fields(self):
        result = self.forge.run_once()
        candidate = result["summary"]["top_candidates"][0]
        for key in (
            "task_url",
            "execution_mode",
            "match_score",
            "decision_reason",
            "estimated_minutes",
            "description_excerpt",
        ):
            self.assertIn(key, candidate)
        self.assertTrue(candidate["task_url"].startswith("https://opentask.ai/tasks/"))

    def test_anti_detect_work_is_hard_rejected(self):
        bounty = Bounty(
            source="opentask",
            external_id="anti-detect-1",
            title="Universal web scraper",
            description="Build a proxy-enabled anti-detect scraper bot with JSON output.",
            reward_cents=5000,
            currency="USDC",
            task_url="https://opentask.ai/tasks/anti-detect-1",
            execution_mode="pitch",
            match_score=95,
            updated_at="2026-09-18T09:00:00Z",
            raw={},
        )
        decision = decide(bounty, self.forge.store, self.config)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "disallowed-task-type")

    def test_generic_python_work_does_not_get_false_high_fit(self):
        task = self.fake.tasks["task-generic"]
        self.assertEqual(public_task_match_score(task), 50)
        generic = next(x for x in self.forge.discover() if x.external_id == "task-generic")
        decision = decide(generic, self.forge.store, self.config)
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "success-probability-below-minimum")


if __name__ == "__main__":
    unittest.main()
