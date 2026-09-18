from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw in (None, "") else int(raw)


def env_decimal(name: str, default: str) -> Decimal:
    raw = os.getenv(name)
    return Decimal(default if raw in (None, "") else raw)


def to_minor(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_budget(text: str | None) -> tuple[int, str] | None:
    if not text:
        return None
    match = re.search(
        r"(?i)(?:[$€£]\s*)?([0-9]+(?:\.[0-9]{1,2})?)\s*(USDC|USDT|USD|CAD|EUR|GBP)?",
        text.replace(",", ""),
    )
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    currency = (match.group(2) or "USD").upper()
    return to_minor(amount), currency


@dataclass(frozen=True)
class Config:
    database_path: str = "/data/passive_income.db"
    enabled: bool = True
    auto_bid: bool = False
    auto_submit_entries: bool = False
    auto_solve: bool = True
    auto_deliver: bool = False
    reconcile_payments: bool = True
    scout_interval_seconds: int = 900
    queue_dir: str = "/bounty-queue"
    queue_secret: str = ""
    repo_verify_dir: str = "/repo-verify"
    repo_verify_secret: str = ""
    auto_repo_verify: bool = True
    minimum_reward_cents: int = 500
    maximum_reward_cents: int = 10_000
    minimum_success_probability: Decimal = Decimal("0.70")
    minimum_expected_profit_cents: int = 300
    minimum_hourly_cents: int = 1_500
    compute_budget_cents: int = 100
    maximum_active_jobs: int = 3
    maximum_new_bids_per_day: int = 10
    allowed_currencies: tuple[str, ...] = ("USD", "USDC", "USDT")
    opentask_token: str = ""
    opentask_base_url: str = "https://opentask.ai/api"
    public_scout: bool = True
    public_skill_signals: tuple[str, ...] = ("csv", "json", "data", "python", "documentation")
    public_tasks_per_signal: int = 20

    @classmethod
    def from_env(cls) -> "Config":
        allowed = tuple(
            x.strip().upper()
            for x in os.getenv("BOUNTYFORGE_ALLOWED_CURRENCIES", "USD,USDC,USDT").split(",")
            if x.strip()
        )
        public_skills = tuple(
            x.strip()
            for x in os.getenv(
                "BOUNTYFORGE_PUBLIC_SKILLS",
                "csv,json,data,python,documentation",
            ).split(",")
            if x.strip()
        )
        return cls(
            database_path=os.getenv("DATABASE_PATH", "/data/passive_income.db"),
            enabled=env_bool("BOUNTYFORGE_ENABLED", True),
            auto_bid=env_bool("BOUNTYFORGE_AUTO_BID", False),
            auto_submit_entries=env_bool("BOUNTYFORGE_AUTO_SUBMIT_ENTRIES", False),
            auto_solve=env_bool("BOUNTYFORGE_AUTO_SOLVE", True),
            auto_deliver=env_bool("BOUNTYFORGE_AUTO_DELIVER", False),
            reconcile_payments=env_bool("BOUNTYFORGE_RECONCILE_PAYMENTS", True),
            scout_interval_seconds=max(60, env_int("BOUNTYFORGE_SCOUT_INTERVAL_SECONDS", 900)),
            queue_dir=os.getenv("BOUNTYFORGE_QUEUE_DIR", "/bounty-queue"),
            queue_secret=os.getenv("BOUNTYFORGE_QUEUE_SECRET", ""),
            repo_verify_dir=os.getenv("BOUNTYFORGE_REPO_VERIFY_DIR", "/repo-verify"),
            repo_verify_secret=os.getenv("BOUNTYFORGE_REPO_VERIFY_SECRET", ""),
            auto_repo_verify=env_bool("BOUNTYFORGE_AUTO_REPO_VERIFY", True),
            minimum_reward_cents=max(0, env_int("BOUNTYFORGE_MIN_REWARD_CENTS", 500)),
            maximum_reward_cents=max(0, env_int("BOUNTYFORGE_MAX_REWARD_CENTS", 10_000)),
            minimum_success_probability=env_decimal("BOUNTYFORGE_MIN_SUCCESS_PROBABILITY", "0.70"),
            minimum_expected_profit_cents=max(0, env_int("BOUNTYFORGE_MIN_EXPECTED_PROFIT_CENTS", 300)),
            minimum_hourly_cents=max(0, env_int("BOUNTYFORGE_MIN_HOURLY_CENTS", 1_500)),
            compute_budget_cents=max(0, env_int("BOUNTYFORGE_COMPUTE_BUDGET_CENTS", 100)),
            maximum_active_jobs=max(1, env_int("BOUNTYFORGE_MAX_ACTIVE_JOBS", 3)),
            maximum_new_bids_per_day=max(1, env_int("BOUNTYFORGE_MAX_NEW_BIDS_PER_DAY", 10)),
            allowed_currencies=allowed,
            opentask_token=os.getenv("OPENTASK_TOKEN", "").strip(),
            opentask_base_url=os.getenv("OPENTASK_BASE_URL", "https://opentask.ai/api").rstrip("/"),
            public_scout=env_bool("BOUNTYFORGE_PUBLIC_SCOUT", True),
            public_skill_signals=public_skills,
            public_tasks_per_signal=max(
                1,
                min(50, env_int("BOUNTYFORGE_PUBLIC_TASKS_PER_SIGNAL", 20)),
            ),
        )


@dataclass(frozen=True)
class Bounty:
    source: str
    external_id: str
    title: str
    description: str
    reward_cents: int
    currency: str
    task_url: str
    execution_mode: str
    match_score: int
    updated_at: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class Decision:
    eligible: bool
    reason: str
    category: str
    estimated_minutes: int
    success_probability: Decimal
    expected_profit_cents: int
    expected_hourly_cents: int
    score: Decimal


DISALLOWED_TERMS = {
    "captcha",
    "fake review",
    "fake reviews",
    "mass dm",
    "cold email",
    "cold outreach",
    "spam",
    "credential stuffing",
    "account farming",
    "kyc bypass",
    "identity verification",
    "impersonate",
    "phishing",
    "malware",
    "ransomware",
    "anti-detect",
    "antidetect",
    "steal",
}

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("tests", ("unit test", "pytest", "test coverage", "regression test", "ci test"), 35),
    ("docs", ("documentation", "readme", "docs", "openapi", "api spec"), 30),
    ("data", ("csv", "json", "data cleanup", "normalize", "transform"), 30),
    ("bugfix", ("bug", "fix", "error handling", "exception", "panic"), 55),
    ("automation", ("script", "automation", "cli", "workflow"), 60),
    ("frontend", ("ui", "frontend", "react", "css", "component"), 100),
    ("feature", ("feature", "implement", "integration"), 120),
)


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def init(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS bounty_jobs(
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reward_cents INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    task_url TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    match_score INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    decision_reason TEXT NOT NULL,
                    category TEXT NOT NULL,
                    estimated_minutes INTEGER NOT NULL,
                    success_probability REAL NOT NULL,
                    expected_profit_cents INTEGER NOT NULL,
                    expected_hourly_cents INTEGER NOT NULL,
                    score REAL NOT NULL,
                    status TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY(source, external_id)
                );

                CREATE TABLE IF NOT EXISTS bounty_attempts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bounty_earnings(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    settlement_ref TEXT NOT NULL,
                    gross_cents INTEGER NOT NULL,
                    fees_cents INTEGER NOT NULL,
                    net_cents INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(source, settlement_ref)
                );

                CREATE TABLE IF NOT EXISTS bounty_contracts(
                    contract_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    settlement_status TEXT NOT NULL,
                    payment_verification_status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_bounty_jobs_status_score
                ON bounty_jobs(status, score DESC);

                CREATE INDEX IF NOT EXISTS idx_bounty_earnings_currency
                ON bounty_earnings(currency, created_at);
                """
            )

    def history(self, category: str) -> tuple[int, int]:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT
                  COUNT(*) attempts,
                  COALESCE(SUM(CASE WHEN status IN ('accepted','paid','completed') THEN 1 ELSE 0 END),0) wins
                FROM bounty_attempts
                WHERE detail LIKE ?
                """,
                (f'%"category":"{category}"%',),
            ).fetchone()
        return int(row["attempts"]), int(row["wins"])

    def upsert_job(self, bounty: Bounty, decision: Decision) -> None:
        now = utcnow()
        status = "eligible" if decision.eligible else "rejected"
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO bounty_jobs(
                  source,external_id,title,description,reward_cents,currency,task_url,
                  execution_mode,match_score,decision,decision_reason,category,
                  estimated_minutes,success_probability,expected_profit_cents,
                  expected_hourly_cents,score,status,raw_json,first_seen_at,last_seen_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source,external_id) DO UPDATE SET
                  title=excluded.title,
                  description=excluded.description,
                  reward_cents=excluded.reward_cents,
                  currency=excluded.currency,
                  task_url=excluded.task_url,
                  execution_mode=excluded.execution_mode,
                  match_score=excluded.match_score,
                  decision=excluded.decision,
                  decision_reason=excluded.decision_reason,
                  category=excluded.category,
                  estimated_minutes=excluded.estimated_minutes,
                  success_probability=excluded.success_probability,
                  expected_profit_cents=excluded.expected_profit_cents,
                  expected_hourly_cents=excluded.expected_hourly_cents,
                  score=excluded.score,
                  status=CASE
                    WHEN bounty_jobs.status IN ('bid','working','submitted','paid') THEN bounty_jobs.status
                    ELSE excluded.status
                  END,
                  raw_json=excluded.raw_json,
                  last_seen_at=excluded.last_seen_at
                """,
                (
                    bounty.source,
                    bounty.external_id,
                    bounty.title,
                    bounty.description,
                    bounty.reward_cents,
                    bounty.currency,
                    bounty.task_url,
                    bounty.execution_mode,
                    bounty.match_score,
                    "accept" if decision.eligible else "reject",
                    decision.reason,
                    decision.category,
                    decision.estimated_minutes,
                    float(decision.success_probability),
                    decision.expected_profit_cents,
                    decision.expected_hourly_cents,
                    float(decision.score),
                    status,
                    json.dumps(bounty.raw, separators=(",", ":"), sort_keys=True)[:50_000],
                    now,
                    now,
                ),
            )

    def mark(self, bounty: Bounty, status: str, action: str, detail: dict[str, Any]) -> None:
        payload = dict(detail)
        payload.setdefault("category", classify(bounty)[0])
        with self.connect() as con:
            con.execute(
                "UPDATE bounty_jobs SET status=?, last_seen_at=? WHERE source=? AND external_id=?",
                (status, utcnow(), bounty.source, bounty.external_id),
            )
            con.execute(
                "INSERT INTO bounty_attempts(source,external_id,action,status,detail,created_at) VALUES(?,?,?,?,?,?)",
                (
                    bounty.source,
                    bounty.external_id,
                    action,
                    status,
                    json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)[:20_000],
                    utcnow(),
                ),
            )

    def count_active(self) -> int:
        with self.connect() as con:
            row = con.execute(
                "SELECT COUNT(*) n FROM bounty_jobs WHERE status IN ('bid','working','submitted')"
            ).fetchone()
        return int(row["n"])

    def bids_today(self) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        with self.connect() as con:
            row = con.execute(
                """
                SELECT COUNT(*) n FROM bounty_attempts
                WHERE action='bid' AND status='bid' AND substr(created_at,1,10)=?
                """,
                (today,),
            ).fetchone()
        return int(row["n"])

    def record_earning(
        self,
        *,
        source: str,
        external_id: str,
        settlement_ref: str,
        gross_cents: int,
        fees_cents: int,
        currency: str,
    ) -> bool:
        net = gross_cents - fees_cents
        with self.connect() as con:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO bounty_earnings(
                  source,external_id,settlement_ref,gross_cents,fees_cents,net_cents,currency,created_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    source,
                    external_id,
                    settlement_ref,
                    gross_cents,
                    fees_cents,
                    net,
                    currency.upper(),
                    utcnow(),
                ),
            )
            inserted = cur.rowcount > 0
            if inserted:
                con.execute(
                    "UPDATE bounty_jobs SET status='paid', last_seen_at=? WHERE source=? AND external_id=?",
                    (utcnow(), source, external_id),
                )
        return inserted

    def upsert_contract(self, contract: dict[str, Any]) -> None:
        contract_id = str(contract.get("id") or "")
        task_id = str((contract.get("task") or {}).get("id") or "")
        if not contract_id or not task_id:
            return
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO bounty_contracts(
                  contract_id,task_id,status,settlement_status,payment_verification_status,
                  source,updated_at,raw_json
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(contract_id) DO UPDATE SET
                  task_id=excluded.task_id,
                  status=excluded.status,
                  settlement_status=excluded.settlement_status,
                  payment_verification_status=excluded.payment_verification_status,
                  source=excluded.source,
                  updated_at=excluded.updated_at,
                  raw_json=excluded.raw_json
                """,
                (
                    contract_id,
                    task_id,
                    str(contract.get("status") or "unknown"),
                    str(contract.get("settlementStatus") or "unpaid"),
                    str(contract.get("paymentVerificationStatus") or "unpaid"),
                    str(contract.get("source") or "unknown"),
                    utcnow(),
                    json.dumps(contract, separators=(",", ":"), sort_keys=True)[:50000],
                ),
            )

    def mark_task_status(self, task_id: str, status: str) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE bounty_jobs SET status=?, last_seen_at=? WHERE source='opentask' AND external_id=?",
                (status, utcnow(), task_id),
            )

    def summary(self) -> dict[str, Any]:
        with self.connect() as con:
            statuses = {
                row["status"]: int(row["n"])
                for row in con.execute("SELECT status,COUNT(*) n FROM bounty_jobs GROUP BY status")
            }
            earnings = [
                dict(row)
                for row in con.execute(
                    """
                    SELECT currency,COUNT(*) settlements,
                           COALESCE(SUM(gross_cents),0) gross_cents,
                           COALESCE(SUM(fees_cents),0) fees_cents,
                           COALESCE(SUM(net_cents),0) net_cents
                    FROM bounty_earnings GROUP BY currency ORDER BY currency
                    """
                )
            ]
            top = [
                dict(row)
                for row in con.execute(
                    """
                    SELECT source,external_id,title,task_url,execution_mode,match_score,
                           decision_reason,category,estimated_minutes,
                           reward_cents,currency,success_probability,
                           expected_profit_cents,expected_hourly_cents,score,status,
                           substr(description,1,800) description_excerpt
                    FROM bounty_jobs
                    WHERE decision='accept'
                    ORDER BY score DESC LIMIT 10
                    """
                )
            ]
            rejected = [
                dict(row)
                for row in con.execute(
                    """
                    SELECT source,external_id,title,task_url,execution_mode,match_score,
                           decision_reason,category,estimated_minutes,
                           reward_cents,currency,success_probability,
                           expected_profit_cents,expected_hourly_cents,score,status,
                           substr(description,1,500) description_excerpt
                    FROM bounty_jobs
                    WHERE decision='reject'
                    ORDER BY match_score DESC,reward_cents DESC LIMIT 10
                    """
                )
            ]
            contracts = {
                row["status"]: int(row["n"])
                for row in con.execute(
                    "SELECT status,COUNT(*) n FROM bounty_contracts GROUP BY status"
                )
            }
        return {
            "statuses": statuses,
            "contract_statuses": contracts,
            "earnings": earnings,
            "top_candidates": top,
            "top_rejections": rejected,
        }


def classify(bounty: Bounty) -> tuple[str, int]:
    text = f"{bounty.title}\n{bounty.description}".lower()
    for category, words, minutes in CATEGORY_RULES:
        if any(word in text for word in words):
            return category, minutes
    return "general", 90


def estimated_minutes_for_bounty(bounty: Bounty, default_minutes: int) -> int:
    title = bounty.title
    description = bounty.description
    text = f"{title}\n{description}".lower()

    if safe_solver_payload(title, description) is not None:
        return 5
    if safe_repo_verification_spec(title, description) is not None:
        return 15
    if "csv" in text and "json" in text:
        return 20
    if any(term in text for term in ("jsonl", "ndjson", "base64", "sha256", "sha-256")):
        return 10
    if "csv" in text and any(term in text for term in ("deduplicate", "markdown table")):
        return 10
    return default_minutes


def historical_success(store: Store, category: str) -> Decimal:
    attempts, wins = store.history(category)
    return Decimal(wins + 2) / Decimal(attempts + 4)


def decide(bounty: Bounty, store: Store, config: Config) -> Decision:
    category, default_minutes = classify(bounty)
    minutes = estimated_minutes_for_bounty(bounty, default_minutes)
    text = f"{bounty.title}\n{bounty.description}".lower()

    if any(term in text for term in DISALLOWED_TERMS):
        return Decision(False, "disallowed-task-type", category, minutes, Decimal("0"), 0, 0, Decimal("0"))
    if bounty.currency.upper() not in config.allowed_currencies:
        return Decision(False, "unsupported-currency", category, minutes, Decimal("0"), 0, 0, Decimal("0"))
    if bounty.reward_cents < config.minimum_reward_cents:
        return Decision(False, "reward-below-minimum", category, minutes, Decimal("0"), 0, 0, Decimal("0"))
    if config.maximum_reward_cents and bounty.reward_cents > config.maximum_reward_cents:
        return Decision(False, "reward-above-autonomy-cap", category, minutes, Decimal("0"), 0, 0, Decimal("0"))

    hist = historical_success(store, category)
    match_probability = Decimal(max(0, min(100, bounty.match_score))) / Decimal(100)
    success = (match_probability * Decimal("0.65")) + (hist * Decimal("0.35"))
    success = max(Decimal("0.20"), min(Decimal("0.95"), success))

    # OpenTask currently advertises a 4.5% marketplace fee. Keep this
    # conservative and configurable later by recording actual settlement fees.
    expected_after_fee = (
        Decimal(bounty.reward_cents)
        * success
        * Decimal("0.955")
    )
    expected_profit = int(expected_after_fee) - config.compute_budget_cents
    hourly = 0 if minutes <= 0 else expected_profit * 60 // minutes
    exploration = Decimal("1") + (Decimal("20") / Decimal(max(20, bounty.match_score + 20)))
    score = Decimal(max(0, hourly)) * success * exploration

    if success < config.minimum_success_probability:
        reason = "success-probability-below-minimum"
        eligible = False
    elif expected_profit < config.minimum_expected_profit_cents:
        reason = "expected-profit-below-minimum"
        eligible = False
    elif hourly < config.minimum_hourly_cents:
        reason = "expected-hourly-below-minimum"
        eligible = False
    else:
        reason = "eligible"
        eligible = True

    return Decision(
        eligible,
        reason,
        category,
        minutes,
        success.quantize(Decimal("0.0001")),
        expected_profit,
        hourly,
        score.quantize(Decimal("0.01")),
    )



def _fenced_blocks(text: str) -> list[tuple[str, str]]:
    return [
        ((m.group(1) or "").strip().lower(), m.group(2).strip())
        for m in re.finditer(r"\`\`\`([A-Za-z0-9_-]*)[ \t]*\n(.*?)\`\`\`", text, re.DOTALL)
    ]


def safe_solver_payload(title: str, description: str) -> dict[str, Any] | None:
    """Return a deterministic, non-code-executing solver job for clear task types."""
    text = f"{title}\n{description}"
    lower = text.lower()
    blocks = _fenced_blocks(text)
    if not blocks:
        return None

    def first_block(*languages: str) -> str | None:
        allowed = set(languages)
        for language, body in blocks:
            if language in allowed:
                return body
        return blocks[0][1] if blocks else None

    if re.search(r"\b(csv\s*(?:to|->)\s*json|convert\b.*\bcsv\b.*\bjson\b)", lower, re.DOTALL):
        raw = first_block("csv", "text", "")
        return {"kind": "csv_to_json", "input_text": raw} if raw else None
    if re.search(r"\b(json\s*(?:to|->)\s*csv|convert\b.*\bjson\b.*\bcsv\b)", lower, re.DOTALL):
        raw = first_block("json", "text", "")
        return {"kind": "json_to_csv", "input_text": raw} if raw else None
    if re.search(r"\b(jsonl|ndjson)\s*(?:to|->)\s*json\b", lower):
        raw = first_block("jsonl", "ndjson", "text", "")
        return {"kind": "jsonl_to_json", "input_text": raw} if raw else None
    if re.search(r"\bjson\s*(?:to|->)\s*(?:jsonl|ndjson)\b", lower):
        raw = first_block("json", "text", "")
        return {"kind": "json_to_jsonl", "input_text": raw} if raw else None
    if ("deduplicate" in lower or "remove duplicate" in lower) and "csv" in lower:
        raw = first_block("csv", "text", "")
        key_match = re.search(r"(?:by|using)\s+(?:column|columns|keys?)\s*[:=]?\s*([A-Za-z0-9_, -]+)", text, re.IGNORECASE)
        payload = {"kind": "csv_deduplicate", "input_text": raw}
        if key_match:
            keys = [item.strip() for item in key_match.group(1).split(",") if item.strip()]
            if keys:
                payload["keys"] = keys
        return payload if raw else None
    if ("markdown table" in lower or "csv to markdown" in lower) and "csv" in lower:
        raw = first_block("csv", "text", "")
        return {"kind": "csv_to_markdown", "input_text": raw} if raw else None
    if ("sort" in lower and ("unique" in lower or "deduplicate" in lower)) and ("lines" in lower or "list" in lower):
        raw = first_block("text", "", "csv", "json")
        return {
            "kind": "lines_sort_unique",
            "input_text": raw,
            "case_sensitive": "case-insensitive" not in lower and "ignore case" not in lower,
        } if raw is not None else None
    if "base64" in lower and any(term in lower for term in ("encode", "to base64")):
        raw = first_block("text", "", "json", "csv")
        return {"kind": "base64_encode", "input_text": raw} if raw is not None else None
    if "base64" in lower and any(term in lower for term in ("decode", "from base64")):
        raw = first_block("text", "", "base64")
        return {"kind": "base64_decode", "input_text": raw} if raw is not None else None
    replace_match = re.search(
        r"(?:replace|change)\s+['\"]([^'\"]+)['\"]\s+(?:with|to)\s+['\"]([^'\"]*)['\"]",
        text,
        re.IGNORECASE,
    )
    if replace_match:
        raw = first_block("text", "", "md", "markdown")
        return {
            "kind": "text_replace",
            "input_text": raw,
            "old": replace_match.group(1),
            "new": replace_match.group(2),
        } if raw is not None else None
    if any(term in lower for term in ("pretty print json", "format json", "normalize json", "canonicalize json")):
        raw = first_block("json", "text", "")
        return {"kind": "json_format", "input_text": raw, "compact": "compact json" in lower} if raw else None
    if "sha256" in lower or "sha-256" in lower:
        raw = first_block("text", "", "json", "csv")
        return {"kind": "sha256", "input_text": raw} if raw is not None else None
    return None


def safe_repo_verification_spec(title: str, description: str) -> dict[str, Any] | None:
    text = f"{title}\n{description}"
    lower = text.lower()
    if not any(term in lower for term in ("verify", "run tests", "test this", "check this", "compile")):
        return None

    repo_match = re.search(
        r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        text,
        re.IGNORECASE,
    )
    sha_match = re.search(r"\b[0-9a-fA-F]{40}\b", text)
    if not repo_match or not sha_match:
        return None

    checks: list[str] = []
    if any(term in lower for term in ("python unittest", "unittest", "unit tests", "run tests")):
        checks.append("python_unittest")
    if any(term in lower for term in ("compileall", "compile all", "python compile", "syntax check")):
        checks.append("python_compileall")
    if not checks:
        return None

    deduped = []
    for check in checks:
        if check not in deduped:
            deduped.append(check)
    return {
        "repo_url": repo_match.group(0).rstrip("/").removesuffix(".git"),
        "commit_sha": sha_match.group(0).lower(),
        "checks": deduped[:3],
    }


def _queue_signature(secret: str, package: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in package.items() if key != "signature"}
    body = json.dumps(unsigned, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _safe_queue_job_id(source: str, task_id: str, contract_id: str | None = None) -> str:
    identity = f"{source}:{task_id}:{contract_id or 'entry'}"
    digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
    return f"{source}-{digest}"


def _settled_units(invoice: dict[str, Any], receipt_ids: set[str]) -> Iterable[dict[str, Any]]:
    settlement = invoice.get("settlement") or {}
    for unit in settlement.get("units") or []:
        receipt_id = str(unit.get("receiptId") or "")
        amount = unit.get("amount") or {}
        if (
            unit.get("status") == "paid"
            and receipt_id
            and receipt_id in receipt_ids
            and amount.get("sellerAmount") is not None
            and amount.get("currency")
        ):
            yield {
                "receipt_id": receipt_id,
                "seller_amount": str(amount["sellerAmount"]),
                "currency": str(amount["currency"]).upper(),
            }


class OpenTaskClient:
    def __init__(self, config: Config):
        self.base = config.opentask_base_url
        self.token = config.opentask_token

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        if not self.token:
            raise RuntimeError("OPENTASK_TOKEN is not configured")
        body = None if payload is None else json.dumps(payload).encode()
        request_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "BountyForge/1.0",
        }
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=body,
            method=method,
            headers=request_headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read()
                return {} if not data else json.loads(data)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"OpenTask HTTP {exc.code}: {raw[:1200]}") from exc

    def _public_request(self, path: str) -> Any:
        req = urllib.request.Request(
            f"{self.base}{path}",
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "BountyForge/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read()
                return {} if not data else json.loads(data)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"OpenTask public HTTP {exc.code}: {raw[:1200]}") from exc

    def public_tasks(self, *, skill: str, limit: int = 20) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(
            {
                "skill": skill,
                "sort": "new",
                "limit": max(1, min(limit, 50)),
            }
        )
        data = self._public_request(f"/tasks?{query}")
        return list(data.get("tasks") or [])

    def public_task_detail(self, task_id: str) -> dict[str, Any]:
        return self._public_request(f"/tasks/{urllib.parse.quote(task_id, safe='')}")

    def recommendations(self, limit: int = 25) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/agent/me/task-recommendations?limit={max(1, min(limit, 50))}&includeWeak=0",
        )
        return list(data.get("recommendations") or [])

    def task_detail(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/agent/tasks/{urllib.parse.quote(task_id, safe='')}")

    def contracts(self, role: str = "seller") -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(10):
            query = {"role": role, "limit": "100"}
            if cursor:
                query["cursor"] = cursor
            data = self._request("GET", "/agent/contracts?" + urllib.parse.urlencode(query))
            items.extend(list(data.get("contracts") or []))
            cursor = data.get("nextCursor")
            if not cursor:
                break
        return items

    def contract_receipts(self, contract_id: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/agent/contracts/{urllib.parse.quote(contract_id, safe='')}/receipts",
        )
        return list(data.get("receipts") or [])


    def contract_invoices(self, contract_id: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/agent/contracts/{urllib.parse.quote(contract_id, safe='')}/invoices",
        )
        return list(data.get("invoices") or [])

    def create_delivery_draft(
        self,
        contract_id: str,
        *,
        title: str,
        summary: str,
        verification_instructions: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/agent/contracts/{urllib.parse.quote(contract_id, safe='')}/deliveries",
            {
                "title": title[:200],
                "summary": summary[:20000],
                "verificationInstructions": verification_instructions[:20000],
            },
            {"Idempotency-Key": idempotency_key},
        )

    def create_delivery_upload_intent(
        self,
        contract_id: str,
        package_id: str,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/agent/contracts/{urllib.parse.quote(contract_id, safe='')}/deliveries/"
            f"{urllib.parse.quote(package_id, safe='')}/upload-intents",
            {
                "filename": filename,
                "contentType": content_type,
                "sizeBytes": size_bytes,
                "sha256": sha256,
            },
            {"Idempotency-Key": idempotency_key},
        )

    def complete_delivery_upload(
        self, contract_id: str, package_id: str, upload_intent_id: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/agent/contracts/{urllib.parse.quote(contract_id, safe='')}/deliveries/"
            f"{urllib.parse.quote(package_id, safe='')}/upload-intents/"
            f"{urllib.parse.quote(upload_intent_id, safe='')}/complete",
            {},
        )

    def delivery_upload_status(
        self, contract_id: str, package_id: str, upload_intent_id: str
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/agent/contracts/{urllib.parse.quote(contract_id, safe='')}/deliveries/"
            f"{urllib.parse.quote(package_id, safe='')}/upload-intents/"
            f"{urllib.parse.quote(upload_intent_id, safe='')}",
        )

    def submit_delivery(
        self,
        contract_id: str,
        package_id: str,
        *,
        expected_version: int,
        file_id: str,
        label: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/agent/contracts/{urllib.parse.quote(contract_id, safe='')}/deliveries/"
            f"{urllib.parse.quote(package_id, safe='')}/submit",
            {
                "expectedVersion": expected_version,
                "nativeArtifacts": [{"fileId": file_id, "label": label[:200]}],
                "confirmed": True,
            },
            {"Idempotency-Key": idempotency_key},
        )

    def create_task_entry_upload_intent(
        self,
        task_id: str,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/agent/tasks/{urllib.parse.quote(task_id, safe='')}/entry-attachments/upload-intents",
            {
                "filename": filename,
                "contentType": content_type,
                "sizeBytes": size_bytes,
                "sha256": sha256,
                "disclosure": "restricted",
            },
            {"Idempotency-Key": idempotency_key},
        )

    def upload_authorized(self, authorization: dict[str, Any], data: bytes) -> None:
        url = str(authorization.get("url") or "")
        if not url.startswith("https://"):
            raise RuntimeError("OpenTask upload authorization did not use HTTPS")
        headers = {str(k): str(v) for k, v in (authorization.get("callerHeaders") or {}).items()}
        req = urllib.request.Request(url, data=data, method="PUT", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"artifact upload failed with HTTP {response.status}")

    def complete_task_entry_upload(self, task_id: str, upload_intent_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/agent/tasks/{urllib.parse.quote(task_id, safe='')}/entry-attachments/upload-intents/"
            f"{urllib.parse.quote(upload_intent_id, safe='')}/complete",
            {},
        )

    def task_entry_upload_status(self, task_id: str, upload_intent_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/agent/tasks/{urllib.parse.quote(task_id, safe='')}/entry-attachments/upload-intents/"
            f"{urllib.parse.quote(upload_intent_id, safe='')}",
        )

    def submit_task_entry(
        self,
        task_id: str,
        *,
        expected_task_updated_at: str,
        artifact: dict[str, Any],
        notes: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/agent/tasks/{urllib.parse.quote(task_id, safe='')}/entries",
            {
                "expectedTaskUpdatedAt": expected_task_updated_at,
                "artifacts": [artifact],
                "notes": notes[:20000],
            },
            {"Idempotency-Key": idempotency_key},
        )

    def create_bid(
        self,
        bounty: Bounty,
        *,
        eta_days: int = 1,
        approach: str,
    ) -> dict[str, Any]:
        expected = bounty.updated_at
        payload = {
            "expectedTaskUpdatedAt": expected,
            "priceAmount": Decimal(bounty.reward_cents) / Decimal(100),
            "priceCurrency": bounty.currency,
            "etaDays": max(1, eta_days),
            "approach": approach[:4000],
        }
        # Decimal is not JSON serializable; preserve exact decimal as float here
        # because the platform schema accepts a JSON number and our amounts are cents.
        payload["priceAmount"] = float(payload["priceAmount"])
        return self._request(
            "POST",
            f"/agent/tasks/{urllib.parse.quote(bounty.external_id, safe='')}/bids",
            payload,
        )


def _task_work_text(task: dict[str, Any]) -> str:
    description = str(task.get("description") or "")
    criteria = task.get("acceptanceCriteria") or []
    if isinstance(criteria, list):
        criteria_text = "\n".join(f"- {item}" for item in criteria if isinstance(item, str))
    else:
        criteria_text = str(criteria or "")
    return description + (("\n\nAcceptance criteria:\n" + criteria_text) if criteria_text else "")


def looks_like_service_ad(task: dict[str, Any]) -> bool:
    title = str(task.get("title") or "").lower()
    description = _task_work_text(task).lower()
    text = f"{title}\n{description}"
    budget_text = str(task.get("budgetText") or "").lower()

    high_confidence = (
        "pitch me your task",
        "scope and price agreed before work starts",
        "fixed-scope engineering work delivered by",
        "services offered",
        "hire me for",
        "i offer ",
    )
    if any(signal in text for signal in high_confidence):
        return True
    if "delivered by an autonomous agent" in text and ("from " in text or "usdc" in text):
        return True
    if budget_text.startswith("from ") and any(
        signal in text
        for signal in ("typical delivery", "tested python", "data conversion", "openapi")
    ):
        return True
    if (
        description.lstrip().startswith("autonomous agent ")
        and "choose one deliverable" in description
        and "typical delivery" in description
    ):
        return True
    return False


def public_task_match_score(task: dict[str, Any]) -> int:
    if looks_like_service_ad(task):
        return 15
    title = str(task.get("title") or "")
    work_text = _task_work_text(task)
    text = f"{title}\n{work_text}".lower()

    if safe_solver_payload(title, work_text) is not None:
        return 98
    if safe_repo_verification_spec(title, work_text) is not None:
        return 96

    # Strong capability fit can exist before buyer inputs are supplied. This
    # affects scouting/bidding only; solving still requires an exact safe route.
    if "csv" in text and "json" in text:
        return 92
    if "jsonl" in text or "ndjson" in text:
        return 90
    if "base64" in text or "sha256" in text or "sha-256" in text:
        return 90
    if "csv" in text and any(term in text for term in ("deduplicate", "duplicate", "markdown table")):
        return 90
    if any(term in text for term in ("data conversion", "data cleanup", "normalize data")):
        return 84
    if "python" in text and any(term in text for term in ("unittest", "unit test", "compileall", "syntax check")):
        return 78
    return 50


def normalize_opentask(rec: dict[str, Any], detail: dict[str, Any] | None = None) -> Bounty | None:
    task = dict(rec.get("task") or {})
    detail_task = dict((detail or {}).get("task") or {})
    merged = {**task, **detail_task}
    task_id = str(merged.get("id") or "").strip()
    if not task_id:
        return None

    amount = merged.get("budgetAmount")
    currency = str(merged.get("budgetCurrency") or "").upper()
    reward_cents = 0
    if amount is not None and currency:
        try:
            reward_cents = to_minor(Decimal(str(amount)))
        except InvalidOperation:
            reward_cents = 0
    if not reward_cents:
        parsed = parse_budget(str(merged.get("budget") or ""))
        if parsed:
            reward_cents, currency = parsed
    if not reward_cents or not currency:
        return None

    updated_at = str(
        merged.get("updatedAt")
        or merged.get("createdAt")
        or datetime.now(timezone.utc).isoformat()
    )
    return Bounty(
        source="opentask",
        external_id=task_id,
        title=str(merged.get("title") or "Untitled task")[:500],
        description=_task_work_text(merged),
        reward_cents=reward_cents,
        currency=currency,
        task_url=f"https://opentask.ai/tasks/{task_id}",
        execution_mode=str(merged.get("executionMode") or "pitch"),
        match_score=int(rec.get("score") or 0),
        updated_at=updated_at,
        raw={"recommendation": rec, "detail": detail or {}},
    )


class BountyForge:
    def __init__(self, config: Config | None = None):
        self.config = config or Config.from_env()
        self.store = Store(self.config.database_path)
        self.store.init()
        self.opentask = OpenTaskClient(self.config)

    def discover(self) -> list[Bounty]:
        by_id: dict[str, Bounty] = {}

        # Authenticated recommendations remain the best signal when available.
        if self.config.opentask_token:
            try:
                recommendations = self.opentask.recommendations(limit=30)
            except RuntimeError as exc:
                print(json.dumps({"recommendation_error": str(exc)[:1000]}), flush=True)
                recommendations = []
            for rec in recommendations:
                task = rec.get("task") or {}
                task_id = str(task.get("id") or "")
                if not task_id:
                    continue
                try:
                    detail = self.opentask.task_detail(task_id)
                except RuntimeError:
                    detail = None
                bounty = normalize_opentask(rec, detail)
                if bounty:
                    by_id[bounty.external_id] = bounty

        # Public reads use OpenTask's documented /api/tasks surface and do not
        # require marketplace identity. Writes still require scoped auth.
        if self.config.public_scout:
            public_items: dict[str, dict[str, Any]] = {}
            for signal in self.config.public_skill_signals:
                try:
                    rows = self.opentask.public_tasks(
                        skill=signal,
                        limit=self.config.public_tasks_per_signal,
                    )
                except RuntimeError as exc:
                    print(
                        json.dumps(
                            {"public_scout_error": str(exc)[:1000], "skill": signal}
                        ),
                        flush=True,
                    )
                    continue
                for task in rows:
                    task_id = str(task.get("id") or "")
                    if task_id:
                        public_items[task_id] = task

            for task_id, task in public_items.items():
                try:
                    detail = self.opentask.public_task_detail(task_id)
                except RuntimeError:
                    detail = {"task": task}
                detail_task = dict(detail.get("task") or detail or {})
                merged = {**task, **detail_task}
                score = public_task_match_score(merged)
                rec = {"task": task, "score": score, "source": "public"}
                bounty = normalize_opentask(rec, {"task": merged})
                if not bounty:
                    continue
                existing = by_id.get(bounty.external_id)
                if existing is None or bounty.match_score > existing.match_score:
                    by_id[bounty.external_id] = bounty

        return sorted(
            by_id.values(),
            key=lambda bounty: (bounty.match_score, bounty.updated_at),
            reverse=True,
        )

    def _queue_root(self) -> Path:
        root = Path(self.config.queue_dir)
        for folder in ("inbox", "outbox", "ready", "consumed", "quarantine", "artifacts"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        return root

    def queue_solver_task(
        self,
        *,
        task_id: str,
        title: str,
        description: str,
        execution_mode: str,
        expected_task_updated_at: str,
        contract_id: str | None = None,
    ) -> bool:
        if not self.config.auto_solve or not self.config.queue_secret:
            return False
        payload = safe_solver_payload(title, description)
        if payload is None:
            return False

        root = self._queue_root()
        job_id = _safe_queue_job_id("opentask", task_id, contract_id)
        for folder in ("inbox", "outbox", "ready", "consumed"):
            if (root / folder / f"{job_id}.json").exists():
                return False

        package: dict[str, Any] = {
            "version": 1,
            "job_id": job_id,
            "source": "opentask",
            "task_id": task_id,
            "contract_id": contract_id,
            "execution_mode": execution_mode,
            "expected_task_updated_at": expected_task_updated_at,
            "title": title[:500],
            "payload": payload,
        }
        package["signature"] = _queue_signature(self.config.queue_secret, package)
        destination = root / "inbox" / f"{job_id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
        temporary.replace(destination)
        self.store.mark_task_status(task_id, "solving")
        return True

    def _repo_verify_root(self) -> Path:
        root = Path(self.config.repo_verify_dir)
        for folder in (
            "fetch-inbox",
            "fetch-outbox",
            "fetch-processed",
            "fetch-failed",
            "inbox",
            "outbox",
            "processed",
            "failed",
            "consumed",
            "quarantine",
            "staged",
        ):
            (root / folder).mkdir(parents=True, exist_ok=True)
        return root

    def queue_repo_verification(
        self,
        *,
        task_id: str,
        title: str,
        description: str,
        execution_mode: str,
        expected_task_updated_at: str,
        contract_id: str | None = None,
    ) -> bool:
        if not self.config.auto_repo_verify or not self.config.repo_verify_secret:
            return False
        spec = safe_repo_verification_spec(title, description)
        if spec is None:
            return False

        root = self._repo_verify_root()
        job_id = _safe_queue_job_id("opentask-repo", task_id, contract_id)
        for folder in (
            "fetch-inbox",
            "fetch-outbox",
            "fetch-processed",
            "fetch-failed",
            "inbox",
            "outbox",
            "consumed",
            "quarantine",
        ):
            if (root / folder / f"{job_id}.json").exists():
                return False

        package: dict[str, Any] = {
            "version": 1,
            "job_id": job_id,
            "source": "opentask",
            "task_id": task_id,
            "contract_id": contract_id,
            "execution_mode": execution_mode,
            "expected_task_updated_at": expected_task_updated_at,
            "title": title[:500],
            **spec,
        }
        package["signature"] = _queue_signature(self.config.repo_verify_secret, package)
        destination = root / "fetch-inbox" / f"{job_id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n")
        temporary.replace(destination)
        self.store.mark_task_status(task_id, "repo_staging")
        return True

    def collect_repo_verification_results(self) -> dict[str, int]:
        counts = {
            "verified": 0,
            "failed": 0,
            "translated": 0,
            "quarantined": 0,
        }
        if not self.config.repo_verify_secret or not self.config.queue_secret:
            return counts

        repo_root = self._repo_verify_root()
        queue_root = self._queue_root()
        for path in sorted((repo_root / "outbox").glob("*.json")):
            try:
                result = json.loads(path.read_text())
            except Exception:
                path.replace(repo_root / "quarantine" / path.name)
                counts["quarantined"] += 1
                continue

            supplied = str(result.get("signature") or "")
            expected = _queue_signature(self.config.repo_verify_secret, result)
            if not supplied or not hmac.compare_digest(supplied, expected):
                path.replace(repo_root / "quarantine" / path.name)
                counts["quarantined"] += 1
                continue

            job_id = str(result.get("job_id") or path.stem)
            task_id = str(result.get("task_id") or "")
            contract_id = str(result.get("contract_id") or "")
            passed = bool(result.get("passed"))

            if not passed:
                if task_id:
                    self.store.mark_task_status(task_id, "repo_verification_failed")
                path.replace(repo_root / "consumed" / path.name)
                counts["failed"] += 1
                continue

            counts["verified"] += 1
            artifact_dir = queue_root / "artifacts" / job_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = artifact_dir / "repository-verification.json"
            report = dict(result)
            artifact_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
            artifact_path.write_bytes(artifact_bytes)

            manifest: dict[str, Any] = {
                "version": 1,
                "job_id": job_id,
                "task_id": task_id or None,
                "contract_id": contract_id or None,
                "execution_mode": result.get("execution_mode"),
                "expected_task_updated_at": result.get("expected_task_updated_at"),
                "source": result.get("source") or "opentask",
                "ok": True,
                "handler": "repository_verification",
                "artifact": {
                    "relative_path": str(artifact_path.relative_to(queue_root)),
                    "filename": artifact_path.name,
                    "content_type": "application/json",
                    "size_bytes": len(artifact_bytes),
                    "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                },
                "verification": {
                    "passed": True,
                    "tree": result.get("tree"),
                    "checks": [
                        {
                            "check": item.get("check"),
                            "returncode": item.get("returncode"),
                            "duration_ms": item.get("duration_ms"),
                            "output_sha256": item.get("output_sha256"),
                            "output_truncated": item.get("output_truncated"),
                            "passed": item.get("passed"),
                        }
                        for item in (result.get("checks") or [])
                    ],
                },
                "error": None,
            }
            manifest["signature"] = _queue_signature(self.config.queue_secret, manifest)
            destination = queue_root / "outbox" / f"{job_id}.json"
            if not destination.exists():
                temporary = destination.with_suffix(".tmp")
                temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                temporary.replace(destination)
                counts["translated"] += 1
            if task_id:
                self.store.mark_task_status(task_id, "repo_verified")
            path.replace(repo_root / "consumed" / path.name)
        return counts

    def _verified_manifest_artifact(
        self, manifest: dict[str, Any]
    ) -> tuple[Path, dict[str, Any]] | None:
        if not self.config.queue_secret:
            return None
        supplied = str(manifest.get("signature") or "")
        expected = _queue_signature(self.config.queue_secret, manifest)
        if not supplied or not hmac.compare_digest(supplied, expected):
            return None
        artifact = manifest.get("artifact")
        if not isinstance(artifact, dict):
            return None
        relative = str(artifact.get("relative_path") or "")
        root = self._queue_root().resolve()
        path = (root / relative).resolve()
        if path == root or root not in path.parents or not path.is_file():
            return None
        data = path.read_bytes()
        expected_hash = str(artifact.get("sha256") or "")
        if not expected_hash or hashlib.sha256(data).hexdigest() != expected_hash:
            return None
        if int(artifact.get("size_bytes") or -1) != len(data):
            return None
        return path, artifact

    def deliver_solver_result(
        self,
        *,
        contract_id: str,
        task_id: str,
        manifest: dict[str, Any],
        artifact_path: Path,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        data = artifact_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        job_id = str(manifest.get("job_id") or "")
        draft_response = self.opentask.create_delivery_draft(
            contract_id,
            title="BountyForge verified delivery",
            summary=(
                "Deterministic offline solver output. The artifact was generated without "
                "network access and verified before submission."
            ),
            verification_instructions=json.dumps(
                manifest.get("verification") or {}, sort_keys=True, default=str
            )[:20000],
            idempotency_key=f"bf-draft-{job_id}",
        )
        delivery = dict(draft_response.get("delivery") or {})
        package_id = str(delivery.get("id") or "")
        version = int(delivery.get("version") or 0)
        if not package_id or version < 1:
            raise RuntimeError("OpenTask did not return a usable delivery draft")

        upload_response = self.opentask.create_delivery_upload_intent(
            contract_id,
            package_id,
            filename=str(artifact.get("filename") or artifact_path.name)[:200],
            content_type=str(artifact.get("content_type") or "application/octet-stream"),
            size_bytes=len(data),
            sha256=digest,
            idempotency_key=f"bf-upload-{job_id}",
        )
        intent = dict(upload_response.get("uploadIntent") or {})
        upload_intent_id = str(intent.get("id") or "")
        file_id = str(intent.get("fileId") or "")
        if not upload_intent_id or not file_id:
            raise RuntimeError("OpenTask did not return a usable upload intent")

        file_status = str(intent.get("fileStatus") or "")
        if file_status == "pending_upload":
            authorization = intent.get("upload")
            if not isinstance(authorization, dict):
                raise RuntimeError("OpenTask upload authorization is unavailable")
            self.opentask.upload_authorized(authorization, data)
            status_response = self.opentask.complete_delivery_upload(
                contract_id, package_id, upload_intent_id
            )
        else:
            status_response = {
                "file": {"id": file_id, "status": file_status},
                "pollAfterMs": upload_response.get("pollAfterMs"),
            }

        deadline = time.monotonic() + 120
        while True:
            file_info = dict(status_response.get("file") or {})
            status = str(file_info.get("status") or "")
            if status == "ready":
                file_id = str(file_info.get("id") or file_id)
                break
            if status in {"processing_failed", "quarantined", "deleted"}:
                raise RuntimeError(f"OpenTask rejected delivery artifact: {status}")
            if time.monotonic() >= deadline:
                raise RuntimeError("OpenTask delivery artifact processing timed out")
            poll_ms = status_response.get("pollAfterMs")
            try:
                pause = float(poll_ms) / 1000 if poll_ms is not None else 1.0
            except (TypeError, ValueError):
                pause = 1.0
            time.sleep(max(0.25, min(pause, 5.0)))
            status_response = self.opentask.delivery_upload_status(
                contract_id, package_id, upload_intent_id
            )

        response = self.opentask.submit_delivery(
            contract_id,
            package_id,
            expected_version=version,
            file_id=file_id,
            label=str(artifact.get("filename") or artifact_path.name),
            idempotency_key=f"bf-submit-{job_id}",
        )
        self.store.mark_task_status(task_id, "submitted")
        return response

    def collect_solver_results(self) -> dict[str, int]:
        root = self._queue_root()
        counts = {"verified": 0, "delivered": 0, "ready": 0, "failed": 0, "quarantined": 0}
        paths = list((root / "outbox").glob("*.json")) + list((root / "ready").glob("*.json"))
        for path in sorted(paths):
            try:
                manifest = json.loads(path.read_text())
            except Exception:
                path.replace(root / "quarantine" / path.name)
                counts["quarantined"] += 1
                continue

            supplied = str(manifest.get("signature") or "")
            expected = _queue_signature(self.config.queue_secret, manifest) if self.config.queue_secret else ""
            if not supplied or not expected or not hmac.compare_digest(supplied, expected):
                path.replace(root / "quarantine" / path.name)
                counts["quarantined"] += 1
                continue

            task_id = str(manifest.get("task_id") or "")
            contract_id = str(manifest.get("contract_id") or "")
            if not manifest.get("ok"):
                if task_id:
                    self.store.mark_task_status(task_id, "solver_failed")
                path.replace(root / "consumed" / path.name)
                counts["failed"] += 1
                continue

            verified = self._verified_manifest_artifact(manifest)
            if verified is None:
                path.replace(root / "quarantine" / path.name)
                counts["quarantined"] += 1
                continue
            artifact_path, artifact = verified
            counts["verified"] += 1

            if not contract_id:
                if task_id:
                    self.store.mark_task_status(task_id, "solved_entry_ready")
                if path.parent.name != "ready":
                    path.replace(root / "ready" / path.name)
                counts["ready"] += 1
                continue

            if not self.config.auto_deliver or not self.config.opentask_token:
                if task_id:
                    self.store.mark_task_status(task_id, "delivery_ready")
                if path.parent.name != "ready":
                    path.replace(root / "ready" / path.name)
                counts["ready"] += 1
                continue

            try:
                self.deliver_solver_result(
                    contract_id=contract_id,
                    task_id=task_id,
                    manifest=manifest,
                    artifact_path=artifact_path,
                    artifact=artifact,
                )
            except Exception as exc:
                if task_id:
                    self.store.mark_task_status(task_id, "delivery_error")
                print(
                    json.dumps(
                        {"delivery_error": str(exc)[:1000], "task_id": task_id, "contract_id": contract_id}
                    ),
                    flush=True,
                )
                if path.parent.name != "ready":
                    path.replace(root / "ready" / path.name)
                counts["ready"] += 1
                continue

            path.replace(root / "consumed" / path.name)
            counts["delivered"] += 1
        return counts

    def reconcile_contracts(self) -> dict[str, int]:
        result = {"contracts": 0, "queued": 0, "settlements": 0}
        if not self.config.opentask_token:
            return result

        contracts = self.opentask.contracts("seller")
        result["contracts"] = len(contracts)
        for contract in contracts:
            self.store.upsert_contract(contract)
            contract_id = str(contract.get("id") or "")
            task = contract.get("task") or {}
            task_id = str(task.get("id") or "")
            contract_status = str(contract.get("status") or "")
            if not contract_id or not task_id:
                continue

            if contract_status in {"submitted", "accepted", "rejected", "cancelled"}:
                self.store.mark_task_status(task_id, contract_status)

            if (self.config.auto_solve or self.config.auto_repo_verify) and contract_status == "in_progress":
                try:
                    detail = self.opentask.task_detail(task_id)
                    task_detail = dict(detail.get("task") or {})
                    title = str(task_detail.get("title") or task.get("title") or "OpenTask contract")
                    description = str(task_detail.get("description") or "")
                    execution_mode = str(task_detail.get("executionMode") or "pitch")
                    updated_at = str(task_detail.get("updatedAt") or task_detail.get("createdAt") or utcnow())
                    queued = self.queue_solver_task(
                        task_id=task_id,
                        title=title,
                        description=description,
                        execution_mode=execution_mode,
                        expected_task_updated_at=updated_at,
                        contract_id=contract_id,
                    )
                    if not queued and safe_solver_payload(title, description) is None:
                        queued = self.queue_repo_verification(
                            task_id=task_id,
                            title=title,
                            description=description,
                            execution_mode=execution_mode,
                            expected_task_updated_at=updated_at,
                            contract_id=contract_id,
                        )
                    if queued:
                        result["queued"] += 1
                except Exception as exc:
                    print(
                        json.dumps({"contract_queue_error": str(exc)[:1000], "contract_id": contract_id}),
                        flush=True,
                    )

            if not self.config.reconcile_payments:
                continue
            try:
                receipts = self.opentask.contract_receipts(contract_id)
                receipt_ids = {
                    str(receipt.get("id") or receipt.get("receiptId") or "")
                    for receipt in receipts
                    if receipt.get("id") or receipt.get("receiptId")
                }
                if not receipt_ids:
                    continue
                invoices = self.opentask.contract_invoices(contract_id)
                for invoice in invoices:
                    for unit in _settled_units(invoice, receipt_ids):
                        seller_cents = to_minor(Decimal(unit["seller_amount"]))
                        if seller_cents < 0:
                            continue
                        if self.store.record_earning(
                            source="opentask",
                            external_id=task_id,
                            settlement_ref=unit["receipt_id"],
                            gross_cents=seller_cents,
                            fees_cents=0,
                            currency=unit["currency"],
                        ):
                            result["settlements"] += 1
            except (RuntimeError, InvalidOperation, ValueError) as exc:
                print(
                    json.dumps({"reconcile_error": str(exc)[:1000], "contract_id": contract_id}),
                    flush=True,
                )
        return result

    def run_once(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {"enabled": False, "discovered": 0, "eligible": 0, "bids": 0}

        repo_results = (
            self.collect_repo_verification_results()
            if self.config.repo_verify_secret and self.config.queue_secret
            else {"verified": 0, "failed": 0, "translated": 0, "quarantined": 0}
        )
        solver_results = (
            self.collect_solver_results()
            if self.config.queue_secret
            else {"verified": 0, "delivered": 0, "ready": 0, "failed": 0, "quarantined": 0}
        )
        contracts = self.reconcile_contracts()

        discovered = self.discover()
        eligible: list[tuple[Bounty, Decision]] = []
        queued_entries = 0
        queued_repo_entries = 0
        for bounty in discovered:
            decision = decide(bounty, self.store, self.config)
            self.store.upsert_job(bounty, decision)
            if decision.eligible:
                eligible.append((bounty, decision))
                if bounty.execution_mode in {"bounty", "benchmark"}:
                    queued = self.queue_solver_task(
                        task_id=bounty.external_id,
                        title=bounty.title,
                        description=bounty.description,
                        execution_mode=bounty.execution_mode,
                        expected_task_updated_at=bounty.updated_at,
                    )
                    if queued:
                        queued_entries += 1
                    elif safe_solver_payload(bounty.title, bounty.description) is None and self.queue_repo_verification(
                        task_id=bounty.external_id,
                        title=bounty.title,
                        description=bounty.description,
                        execution_mode=bounty.execution_mode,
                        expected_task_updated_at=bounty.updated_at,
                    ):
                        queued_repo_entries += 1

        eligible.sort(key=lambda pair: pair[1].score, reverse=True)
        bids = 0
        if self.config.auto_bid and self.config.opentask_token:
            active = self.store.count_active()
            remaining_slots = max(0, self.config.maximum_active_jobs - active)
            remaining_daily = max(0, self.config.maximum_new_bids_per_day - self.store.bids_today())
            quota = min(remaining_slots, remaining_daily)
            for bounty, decision in eligible:
                if quota <= 0:
                    break
                if bounty.execution_mode != "pitch":
                    continue
                approach = (
                    f"BountyForge selected this task after automated fit and profitability checks. "
                    f"Plan: produce a minimal verified {decision.category} deliverable, run the task's "
                    f"acceptance checks, and submit evidence. Estimated effort: {decision.estimated_minutes} minutes."
                )
                try:
                    response = self.opentask.create_bid(bounty, eta_days=1, approach=approach)
                except Exception as exc:
                    self.store.mark(
                        bounty,
                        "eligible",
                        "bid-error",
                        {"error": str(exc)[:1200], "decision": asdict(decision)},
                    )
                    continue
                self.store.mark(
                    bounty,
                    "bid",
                    "bid",
                    {"response": response, "decision": asdict(decision)},
                )
                bids += 1
                quota -= 1

        return {
            "enabled": True,
            "auto_bid": self.config.auto_bid,
            "auto_solve": self.config.auto_solve,
            "auto_deliver": self.config.auto_deliver,
            "discovered": len(discovered),
            "eligible": len(eligible),
            "queued_entries": queued_entries,
            "queued_repo_entries": queued_repo_entries,
            "bids": bids,
            "contracts": contracts,
            "repo_verifier": repo_results,
            "solver": solver_results,
            "summary": self.store.summary(),
        }

    def worker(self) -> None:
        while True:
            try:
                result = self.run_once()
                print(json.dumps(result, default=str, sort_keys=True), flush=True)
            except Exception as exc:
                print(json.dumps({"error": str(exc), "at": utcnow()}), flush=True)
            time.sleep(self.config.scout_interval_seconds)


def cli() -> int:
    parser = argparse.ArgumentParser(description="BountyForge micro-bounty collector")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scout")
    sub.add_parser("worker")
    sub.add_parser("status")
    sub.add_parser("reconcile")
    sub.add_parser("collect")
    sub.add_parser("collect-repos")

    settle = sub.add_parser("settle")
    settle.add_argument("--source", required=True)
    settle.add_argument("--external-id", required=True)
    settle.add_argument("--settlement-ref", required=True)
    settle.add_argument("--gross-cents", required=True, type=int)
    settle.add_argument("--fees-cents", required=True, type=int)
    settle.add_argument("--currency", required=True)

    args = parser.parse_args()
    forge = BountyForge()

    if args.command == "scout":
        print(json.dumps(forge.run_once(), default=str, indent=2, sort_keys=True))
        return 0
    if args.command == "worker":
        forge.worker()
        return 0
    if args.command == "status":
        print(json.dumps(forge.store.summary(), indent=2, sort_keys=True))
        return 0
    if args.command == "reconcile":
        print(json.dumps(forge.reconcile_contracts(), indent=2, sort_keys=True))
        return 0
    if args.command == "collect":
        print(json.dumps(forge.collect_solver_results(), indent=2, sort_keys=True))
        return 0
    if args.command == "collect-repos":
        print(json.dumps(forge.collect_repo_verification_results(), indent=2, sort_keys=True))
        return 0
    if args.command == "settle":
        if args.gross_cents < 0 or args.fees_cents < 0 or args.fees_cents > args.gross_cents:
            parser.error("settlement amounts are invalid")
        inserted = forge.store.record_earning(
            source=args.source,
            external_id=args.external_id,
            settlement_ref=args.settlement_ref,
            gross_cents=args.gross_cents,
            fees_cents=args.fees_cents,
            currency=args.currency,
        )
        print(json.dumps({"recorded": inserted}))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())
