from __future__ import annotations

import argparse
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
    scout_interval_seconds: int = 900
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

    @classmethod
    def from_env(cls) -> "Config":
        allowed = tuple(
            x.strip().upper()
            for x in os.getenv("BOUNTYFORGE_ALLOWED_CURRENCIES", "USD,USDC,USDT").split(",")
            if x.strip()
        )
        return cls(
            database_path=os.getenv("DATABASE_PATH", "/data/passive_income.db"),
            enabled=env_bool("BOUNTYFORGE_ENABLED", True),
            auto_bid=env_bool("BOUNTYFORGE_AUTO_BID", False),
            scout_interval_seconds=max(60, env_int("BOUNTYFORGE_SCOUT_INTERVAL_SECONDS", 900)),
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
                    SELECT source,external_id,title,reward_cents,currency,category,
                           success_probability,expected_profit_cents,expected_hourly_cents,score,status
                    FROM bounty_jobs
                    WHERE decision='accept'
                    ORDER BY score DESC LIMIT 10
                    """
                )
            ]
        return {"statuses": statuses, "earnings": earnings, "top_candidates": top}


def classify(bounty: Bounty) -> tuple[str, int]:
    text = f"{bounty.title}\n{bounty.description}".lower()
    for category, words, minutes in CATEGORY_RULES:
        if any(word in text for word in words):
            return category, minutes
    return "general", 90


def historical_success(store: Store, category: str) -> Decimal:
    attempts, wins = store.history(category)
    return Decimal(wins + 2) / Decimal(attempts + 4)


def decide(bounty: Bounty, store: Store, config: Config) -> Decision:
    category, minutes = classify(bounty)
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

    def recommendations(self, limit: int = 25) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/agent/me/task-recommendations?limit={max(1, min(limit, 50))}&includeWeak=0",
        )
        return list(data.get("recommendations") or [])

    def task_detail(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/agent/tasks/{urllib.parse.quote(task_id, safe='')}")

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
        description=str(merged.get("description") or ""),
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
        if not self.config.opentask_token:
            return []
        discovered: list[Bounty] = []
        for rec in self.opentask.recommendations(limit=30):
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
                discovered.append(bounty)
        return discovered

    def run_once(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {"enabled": False, "discovered": 0, "eligible": 0, "bids": 0}

        discovered = self.discover()
        eligible: list[tuple[Bounty, Decision]] = []
        for bounty in discovered:
            decision = decide(bounty, self.store, self.config)
            self.store.upsert_job(bounty, decision)
            if decision.eligible:
                eligible.append((bounty, decision))

        eligible.sort(key=lambda pair: pair[1].score, reverse=True)
        bids = 0
        if self.config.auto_bid and self.config.opentask_token:
            active = self.store.count_active()
            remaining_slots = max(0, self.config.maximum_active_jobs - active)
            remaining_daily = max(0, self.config.maximum_new_bids_per_day - self.store.bids_today())
            quota = min(remaining_slots, remaining_daily)
            for bounty, decision in eligible[:quota]:
                if bounty.execution_mode != "pitch":
                    # Bounty/benchmark tasks are completed-entry workflows. They
                    # need a solver + artifact verifier before safe submission.
                    self.store.mark(
                        bounty,
                        "queued",
                        "queue",
                        {
                            "reason": "completed-entry-workflow-needs-solver",
                            "decision": asdict(decision),
                        },
                    )
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

        return {
            "enabled": True,
            "auto_bid": self.config.auto_bid,
            "discovered": len(discovered),
            "eligible": len(eligible),
            "bids": bids,
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
