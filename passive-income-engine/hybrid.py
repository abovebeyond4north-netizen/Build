from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

import engine


AFFILIATE_DISCLOSURE = (
    "Some resource links may be affiliate links. If you buy through one, "
    "we may earn a commission at no extra cost to you."
)
STATIC_SITE_ORIGIN = os.getenv(
    "STATIC_SITE_ORIGIN",
    "https://abovebeyond4north-netizen.github.io",
).rstrip("/")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LeadRequest(BaseModel):
    email: str
    consent: bool
    source: str = "website"
    campaign: str = "evergreen"


def _load_affiliate_offers() -> dict[str, dict[str, str]]:
    raw = os.getenv("AFFILIATE_OFFERS_JSON", "[]")
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AFFILIATE_OFFERS_JSON must contain valid JSON") from exc
    if not isinstance(values, list):
        raise RuntimeError("AFFILIATE_OFFERS_JSON must be a JSON array")

    offers: dict[str, dict[str, str]] = {}
    for value in values:
        if not isinstance(value, dict):
            raise RuntimeError("Every affiliate offer must be an object")
        offer_id = str(value.get("id", "")).strip()
        name = str(value.get("name", "")).strip()
        description = str(value.get("description", "")).strip()
        category = str(value.get("category", "resource")).strip()
        url = str(value.get("url", "")).strip()
        parsed = urlparse(url)
        if (
            not offer_id
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", offer_id)
            or not name
            or not description
            or parsed.scheme != "https"
            or not parsed.netloc
        ):
            raise RuntimeError(f"Invalid affiliate offer: {offer_id or '<missing id>'}")
        offers[offer_id] = {
            "id": offer_id,
            "name": name[:120],
            "description": description[:500],
            "category": category[:80],
            "url": url,
        }
    return offers


AFFILIATE_OFFERS = _load_affiliate_offers()


def _init_growth_tables() -> None:
    with engine.db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS affiliate_clicks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id TEXT NOT NULL,
                visitor_hash TEXT NOT NULL,
                source TEXT NOT NULL,
                campaign TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_offer_created
                ON affiliate_clicks(offer_id, created_at);
            CREATE TABLE IF NOT EXISTS leads(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                consented_at TEXT NOT NULL,
                source TEXT NOT NULL,
                campaign TEXT NOT NULL,
                unsubscribe_hash TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
            """
        )


_init_growth_tables()

engine.app.add_middleware(
    CORSMiddleware,
    allow_origins=[STATIC_SITE_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


def _clean(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "", value)[:80]
    return cleaned or fallback


@engine.app.get("/resources", response_class=HTMLResponse)
def affiliate_resources() -> str:
    if AFFILIATE_OFFERS:
        cards = "".join(
            "<article class='card'>"
            f"<span class='badge'>{html.escape(offer['category'])}</span>"
            f"<h2>{html.escape(offer['name'])}</h2>"
            f"<p>{html.escape(offer['description'])}</p>"
            f"<a class='cta' rel='nofollow sponsored' href='/r/{html.escape(offer_id)}'>View resource</a>"
            "</article>"
            for offer_id, offer in AFFILIATE_OFFERS.items()
        )
    else:
        cards = "<p>Curated partner resources will appear here after verified offers are configured.</p>"
    body = (
        "<main><h1>Recommended resources</h1>"
        f"<p>{html.escape(AFFILIATE_DISCLOSURE)}</p>"
        f"<section class='grid'>{cards}</section></main>"
    )
    return engine.page_shell(
        f"Recommended resources | {engine.SITE_NAME}",
        "Curated tools and services for personal finance and small businesses.",
        f"{engine.PUBLIC_BASE_URL}/resources",
        body,
    )


@engine.app.get("/r/{offer_id}")
def affiliate_redirect(offer_id: str, request: Request):
    offer = AFFILIATE_OFFERS.get(offer_id)
    if not offer:
        raise HTTPException(404, "Affiliate offer not found")
    raw_visitor = request.cookies.get("bdt_visitor") or secrets.token_urlsafe(24)
    visitor = engine.visitor_hash(raw_visitor)
    source = _clean(request.query_params.get("source", ""), "direct")
    campaign = _clean(request.query_params.get("campaign", ""), "resource")
    with engine.db() as con:
        con.execute(
            "INSERT INTO affiliate_clicks(offer_id,visitor_hash,source,campaign,created_at) "
            "VALUES(?,?,?,?,?)",
            (offer_id, visitor, source, campaign, engine.utcnow()),
        )
    engine.audit(
        "affiliate.click",
        {"offer_id": offer_id, "source": source, "campaign": campaign},
    )
    response = RedirectResponse(offer["url"], status_code=302)
    response.set_cookie(
        "bdt_visitor",
        raw_visitor,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=engine.PUBLIC_BASE_URL.startswith("https://"),
    )
    return response


@engine.app.post("/api/leads")
def capture_lead(lead: LeadRequest):
    email = lead.email.strip().lower()
    if not lead.consent:
        raise HTTPException(400, "Consent is required")
    if len(email) > 254 or not _EMAIL.fullmatch(email):
        raise HTTPException(400, "A valid email address is required")

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = engine.utcnow()
    source = _clean(lead.source, "website")
    campaign = _clean(lead.campaign, "evergreen")
    with engine.db() as con:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute(
            "SELECT id FROM leads WHERE email=? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if existing:
            con.execute(
                "UPDATE leads SET consented_at=?,source=?,campaign=?,unsubscribe_hash=?,"
                "active=1,updated_at=? WHERE id=?",
                (now, source, campaign, token_hash, now, existing["id"]),
            )
        else:
            con.execute(
                "INSERT INTO leads(email,consented_at,source,campaign,unsubscribe_hash,active,updated_at) "
                "VALUES(?,?,?,?,?,1,?)",
                (email, now, source, campaign, token_hash, now),
            )
        con.execute("COMMIT")
    engine.audit("lead.captured", {"source": source, "campaign": campaign})
    return {
        "status": "subscribed",
        "resource_url": "/lead-magnet",
        "unsubscribe_url": f"/api/leads/unsubscribe/{token}",
    }


@engine.app.get("/api/leads/unsubscribe/{token}")
def unsubscribe_lead(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with engine.db() as con:
        cursor = con.execute(
            "UPDATE leads SET active=0,updated_at=? WHERE unsubscribe_hash=? AND active=1",
            (engine.utcnow(), token_hash),
        )
    if cursor.rowcount != 1:
        raise HTTPException(404, "Subscription not found")
    engine.audit("lead.unsubscribed", {})
    return {"status": "unsubscribed"}


@engine.app.get("/lead-magnet", response_class=HTMLResponse)
def lead_magnet() -> str:
    body = """<main><article><h1>Monthly Money Review Checklist</h1>
    <p>Use this ten-minute review at the end of every month.</p>
    <ol>
      <li>Record total income, fixed costs, variable costs, and debt payments.</li>
      <li>Calculate savings rate: savings divided by after-tax income.</li>
      <li>Compare actual spending with the prior month and planned budget.</li>
      <li>Confirm that emergency reserves cover essential expenses.</li>
      <li>Review subscriptions and cancel anything that no longer creates value.</li>
      <li>Set one measurable money goal for the next month.</li>
    </ol>
    <p><a class='cta' href='/products/compound-growth-calculator'>Model long-term growth</a></p>
    </article></main>"""
    return engine.page_shell(
        f"Monthly Money Review Checklist | {engine.SITE_NAME}",
        "A practical monthly checklist for reviewing income, spending, reserves, and goals.",
        f"{engine.PUBLIC_BASE_URL}/lead-magnet",
        body,
    )


@engine.app.get("/admin/growth")
def growth_status(request: Request):
    engine.require_admin(request)
    with engine.db() as con:
        clicks = con.execute(
            "SELECT offer_id,COUNT(*) clicks,COUNT(DISTINCT visitor_hash) visitors "
            "FROM affiliate_clicks GROUP BY offer_id ORDER BY clicks DESC"
        ).fetchall()
        lead_total = con.execute("SELECT COUNT(*) n FROM leads").fetchone()["n"]
        active_leads = con.execute(
            "SELECT COUNT(*) n FROM leads WHERE active=1"
        ).fetchone()["n"]
    treasury = engine.treasury()
    return {
        "affiliate_offers": len(AFFILIATE_OFFERS),
        "affiliate_clicks": [dict(row) for row in clicks],
        "leads": {"total": lead_total, "active": active_leads},
        "payout": {
            "ready_cents": treasury.payout_ready_cents,
            "currency": engine.CURRENCY,
            "execution": "PayPal automatic transfer settings",
        },
    }


@engine.app.get("/admin/leads")
def active_leads(request: Request):
    engine.require_admin(request)
    with engine.db() as con:
        rows = con.execute(
            "SELECT email,consented_at,source,campaign,updated_at "
            "FROM leads WHERE active=1 ORDER BY id DESC LIMIT 1000"
        ).fetchall()
    return {"leads": [dict(row) for row in rows]}
