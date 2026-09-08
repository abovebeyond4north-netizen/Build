from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/passive_income.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CURRENCY = os.getenv("CURRENCY", "CAD").upper()
PROFIT_FLOOR_CENTS = env_int("PROFIT_FLOOR_CENTS", 50_000)
MIN_SWEEP_CENTS = env_int("MIN_SWEEP_CENTS", 5_000)
MAX_SWEEP_CENTS = env_int("MAX_SWEEP_CENTS", 100_000)
TAX_RESERVE_BPS = env_int("TAX_RESERVE_BPS", 2_500)
REFUND_RESERVE_BPS = env_int("REFUND_RESERVE_BPS", 500)
OPERATING_RESERVE_CENTS = env_int("OPERATING_RESERVE_CENTS", 10_000)

PRODUCTS = {
    "compound-growth-calculator": {
        "name": "Compound Growth Calculator",
        "price_cents": 900,
        "filename": "compound-growth-calculator.html",
        "content": """<!doctype html><meta charset='utf-8'><title>Compound Growth Calculator</title><h1>Compound Growth Calculator</h1><label>Principal <input id='p' type='number' value='10000'></label><label> Monthly <input id='m' type='number' value='250'></label><label> Annual return % <input id='r' type='number' value='6'></label><label> Years <input id='y' type='number' value='20'></label><button onclick='c()'>Calculate</button><h2 id='o'></h2><script>function c(){let p=+pEl.value,m=+mEl.value,r=+rEl.value/1200,n=+yEl.value*12;for(let i=0;i<n;i++)p=p*(1+r)+m;o.textContent=p.toLocaleString(undefined,{style:'currency',currency:'CAD'})}const pEl=document.getElementById('p'),mEl=document.getElementById('m'),rEl=document.getElementById('r'),yEl=document.getElementById('y'),o=document.getElementById('o');c()</script>""",
    },
    "microbusiness-kpi-dashboard": {
        "name": "Microbusiness KPI Dashboard",
        "price_cents": 1900,
        "filename": "microbusiness-kpi-dashboard.html",
        "content": """<!doctype html><meta charset='utf-8'><title>Microbusiness KPI Dashboard</title><h1>Microbusiness KPI Dashboard</h1><p>Paste CSV: date,revenue,costs</p><textarea id='x' rows='8' cols='60'>date,revenue,costs\n2026-01-01,1250,700\n2026-02-01,1500,760</textarea><br><button onclick='r()'>Calculate</button><pre id='o'></pre><script>function r(){let a=x.value.trim().split(/\\r?\\n/).slice(1),R=0,C=0;for(const s of a){let z=s.split(',');R+=+z[1];C+=+z[2]}let P=R-C;o.textContent=`Revenue: ${R.toFixed(2)}\nCosts: ${C.toFixed(2)}\nProfit: ${P.toFixed(2)}\nMargin: ${R?(P/R*100).toFixed(1):0}%`}r()</script>""",
    },
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATABASE_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
    finally:
        con.close()


def init_db() -> None:
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS sales(id TEXT PRIMARY KEY, product_id TEXT NOT NULL, net_cents INTEGER NOT NULL, currency TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS refunds(id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries(token_hash TEXT PRIMARY KEY, sale_id TEXT NOT NULL UNIQUE, product_id TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        """)


@dataclass(frozen=True)
class Treasury:
    sales_cents: int
    refunds_cents: int
    expenses_cents: int
    tax_reserve_cents: int
    refund_reserve_cents: int
    operating_reserve_cents: int
    profit_floor_cents: int
    payout_ready_cents: int


def treasury() -> Treasury:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    with db() as con:
        sales = con.execute("SELECT COALESCE(SUM(net_cents),0) v FROM sales WHERE currency=?", (CURRENCY,)).fetchone()["v"]
        refunds = con.execute("SELECT COALESCE(SUM(amount_cents),0) v FROM refunds WHERE currency=?", (CURRENCY,)).fetchone()["v"]
        expenses = con.execute("SELECT COALESCE(SUM(amount_cents),0) v FROM expenses WHERE currency=?", (CURRENCY,)).fetchone()["v"]
        recent = con.execute("SELECT COALESCE(SUM(net_cents),0) v FROM sales WHERE currency=? AND created_at>=?", (CURRENCY, cutoff)).fetchone()["v"]
    taxable = max(0, sales - refunds - expenses)
    tax = taxable * TAX_RESERVE_BPS // 10_000
    refund_reserve = recent * REFUND_RESERVE_BPS // 10_000
    available = sales - refunds - expenses - tax - refund_reserve - OPERATING_RESERVE_CENTS - PROFIT_FLOOR_CENTS
    payout_ready = max(0, available)
    if payout_ready < MIN_SWEEP_CENTS:
        payout_ready = 0
    elif MAX_SWEEP_CENTS > 0:
        payout_ready = min(payout_ready, MAX_SWEEP_CENTS)
    return Treasury(sales, refunds, expenses, tax, refund_reserve, OPERATING_RESERVE_CENTS, PROFIT_FLOOR_CENTS, payout_ready)


def verify_signature(body: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


app = FastAPI(title="Passive Income Engine", version="1.0.0")
init_db()


class Expense(BaseModel):
    category: str
    amount_cents: int
    note: str = ""


def require_admin(request: Request) -> None:
    expected = f"Bearer {ADMIN_TOKEN}"
    if not ADMIN_TOKEN or not hmac.compare_digest(request.headers.get("authorization", ""), expected):
        raise HTTPException(401, "Unauthorized")


@app.get("/", response_class=HTMLResponse)
def storefront():
    cards = "".join(f"<article><h2>{p['name']}</h2><strong>${p['price_cents']/100:.2f} {CURRENCY}</strong><p>Connect this product ID to your approved checkout provider: <code>{pid}</code>.</p></article>" for pid,p in PRODUCTS.items())
    return f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Beyond Digital Tools</title><style>body{{font-family:system-ui;max-width:900px;margin:auto;padding:28px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}article{{border:1px solid #ddd;border-radius:14px;padding:20px}}</style><h1>Beyond Digital Tools</h1><main>{cards}</main>"


@app.post("/webhooks/payment")
async def payment_webhook(request: Request):
    body = await request.body()
    if not verify_signature(body, request.headers.get("x-signature", "")):
        raise HTTPException(401, "Invalid webhook signature")
    event = json.loads(body)
    event_id = str(event["id"])
    try:
        with db() as con:
            con.execute("INSERT INTO events VALUES(?,?)", (event_id, utcnow()))
    except sqlite3.IntegrityError:
        return {"status": "duplicate"}

    kind = event.get("type")
    if kind == "sale.completed":
        product_id = event["product_id"]
        if product_id not in PRODUCTS:
            raise HTTPException(400, "Unknown product")
        expected = PRODUCTS[product_id]["price_cents"]
        if int(event["gross_cents"]) != expected or event.get("currency") != CURRENCY:
            raise HTTPException(409, "Price or currency mismatch")
        sale_id = str(event["sale_id"])
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        with db() as con:
            con.execute("INSERT OR IGNORE INTO sales VALUES(?,?,?,?,?)", (sale_id, product_id, int(event["net_cents"]), CURRENCY, utcnow()))
            con.execute("DELETE FROM deliveries WHERE sale_id=?", (sale_id,))
            con.execute("INSERT INTO deliveries VALUES(?,?,?,?)", (token_hash, sale_id, product_id, expires))
        return {"status": "fulfilled", "download_url": f"/download/{token}"}

    if kind == "sale.refunded":
        with db() as con:
            con.execute("INSERT OR IGNORE INTO refunds VALUES(?,?,?,?)", (str(event["refund_id"]), int(event["amount_cents"]), CURRENCY, utcnow()))
        return {"status": "recorded"}

    return {"status": "ignored"}


@app.get("/download/{token}")
def download(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db() as con:
        row = con.execute("SELECT * FROM deliveries WHERE token_hash=?", (token_hash,)).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(404, "Invalid or expired link")
    product = PRODUCTS[row["product_id"]]
    return Response(product["content"], media_type="text/html", headers={"Content-Disposition": f"attachment; filename={product['filename']}"})


@app.get("/admin/treasury")
def treasury_status(request: Request):
    require_admin(request)
    return treasury().__dict__


@app.post("/admin/expenses")
def add_expense(request: Request, expense: Expense):
    require_admin(request)
    if expense.amount_cents <= 0:
        raise HTTPException(400, "amount_cents must be positive")
    with db() as con:
        con.execute("INSERT INTO expenses(category,amount_cents,currency,note,created_at) VALUES(?,?,?,?,?)", (expense.category[:80], expense.amount_cents, CURRENCY, expense.note[:500], utcnow()))
    return {"status": "recorded"}


@app.get("/health")
def health():
    return {"status": "ok", "currency": CURRENCY}
