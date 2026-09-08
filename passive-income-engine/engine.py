from __future__ import annotations

import hashlib
import hmac
import html
import json
import math
import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/passive_income.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CURRENCY = os.getenv("CURRENCY", "CAD").upper()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
SITE_NAME = os.getenv("SITE_NAME", "Beyond Digital Tools")
PROFIT_FLOOR_CENTS = env_int("PROFIT_FLOOR_CENTS", 50_000)
MIN_SWEEP_CENTS = env_int("MIN_SWEEP_CENTS", 5_000)
MAX_SWEEP_CENTS = env_int("MAX_SWEEP_CENTS", 100_000)
TAX_RESERVE_BPS = env_int("TAX_RESERVE_BPS", 2_500)
REFUND_RESERVE_BPS = env_int("REFUND_RESERVE_BPS", 500)
OPERATING_RESERVE_CENTS = env_int("OPERATING_RESERVE_CENTS", 10_000)
DOWNLOAD_TTL_HOURS = env_int("DOWNLOAD_TTL_HOURS", 168)
MAX_DOWNLOADS = env_int("MAX_DOWNLOADS", 8)

PRODUCTS = {
    "compound-growth-calculator": {
        "name": "Compound Growth Calculator",
        "price_cents": 900,
        "description": "Offline browser calculator for lump-sum and recurring investment growth scenarios.",
        "filename": "compound-growth-calculator.html",
        "keywords": ["compound interest", "investment calculator", "monthly contributions"],
        "content": """<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Compound Growth Calculator</title><style>body{font-family:system-ui;max-width:760px;margin:40px auto;padding:20px}label{display:block;margin:12px 0}input{padding:8px;width:180px}button{padding:10px 16px}#o{font-size:1.4rem;font-weight:700}</style><h1>Compound Growth Calculator</h1><label>Principal <input id='p' type='number' value='10000' step='0.01'></label><label>Monthly contribution <input id='m' type='number' value='250' step='0.01'></label><label>Annual return % <input id='r' type='number' value='6' step='0.01'></label><label>Years <input id='y' type='number' value='20' step='1'></label><button onclick='c()'>Calculate</button><h2 id='o'></h2><script>function c(){let P=+p.value,M=+m.value,R=+r.value/1200,N=Math.max(0,Math.round(+y.value*12));for(let i=0;i<N;i++)P=P*(1+R)+M;o.textContent=P.toLocaleString(undefined,{style:'currency',currency:'CAD'})}c()</script>""",
    },
    "microbusiness-kpi-dashboard": {
        "name": "Microbusiness KPI Dashboard",
        "price_cents": 1900,
        "description": "Offline dashboard for revenue, costs, profit margin, and annualized run-rate calculations.",
        "filename": "microbusiness-kpi-dashboard.html",
        "keywords": ["small business dashboard", "profit margin", "cash flow KPI"],
        "content": """<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Microbusiness KPI Dashboard</title><style>body{font-family:system-ui;max-width:900px;margin:30px auto;padding:20px}textarea{width:100%;height:180px}.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.card{border:1px solid #ddd;border-radius:12px;padding:16px}button{padding:10px 16px}</style><h1>Microbusiness KPI Dashboard</h1><p>Paste CSV with columns date,revenue,costs.</p><textarea id='x'>date,revenue,costs\n2026-01-01,1250,700\n2026-02-01,1500,760\n2026-03-01,1800,820</textarea><br><button onclick='r()'>Calculate KPIs</button><div id='o' class='k'></div><script>function m(v){return Number(v).toLocaleString(undefined,{style:'currency',currency:'CAD'})}function r(){let a=x.value.trim().split(/\\r?\\n/).slice(1),R=0,C=0,n=0;for(const s of a){let z=s.split(',');if(z.length<3)continue;R+=+z[1];C+=+z[2];n++}let P=R-C,M=R?P/R*100:0,A=n?P/n*12:0;let v=[['Revenue',m(R)],['Costs',m(C)],['Profit',m(P)],['Margin',M.toFixed(1)+'%'],['Annualized run rate',m(A)]];o.innerHTML=v.map(q=>`<div class='card'><b>${q[0]}</b><div>${q[1]}</div></div>`).join('')}r()</script>""",
    },
    "cashflow-forecast-template": {
        "name": "Cashflow Forecast Template",
        "price_cents": 1500,
        "description": "Offline monthly cash-flow forecaster with scenario controls for revenue and cost growth.",
        "filename": "cashflow-forecast-template.html",
        "keywords": ["cash flow forecast", "small business forecast", "monthly budget"],
        "content": """<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cashflow Forecast Template</title><style>body{font-family:system-ui;max-width:820px;margin:35px auto;padding:20px}label{display:block;margin:10px 0}input{padding:7px}table{border-collapse:collapse;width:100%;margin-top:20px}td,th{border:1px solid #ddd;padding:8px;text-align:right}td:first-child,th:first-child{text-align:left}</style><h1>Cashflow Forecast Template</h1><label>Starting monthly revenue <input id='rev' type='number' value='3000'></label><label>Starting monthly costs <input id='cost' type='number' value='1800'></label><label>Monthly revenue growth % <input id='rg' type='number' value='2'></label><label>Monthly cost growth % <input id='cg' type='number' value='1'></label><button onclick='run()'>Forecast 12 months</button><div id='out'></div><script>function run(){let R=+rev.value,C=+cost.value,RG=+rg.value/100,CG=+cg.value/100,cash=0,s='<table><tr><th>Month</th><th>Revenue</th><th>Costs</th><th>Profit</th><th>Cumulative</th></tr>';for(let i=1;i<=12;i++){let p=R-C;cash+=p;s+=`<tr><td>${i}</td><td>${R.toFixed(2)}</td><td>${C.toFixed(2)}</td><td>${p.toFixed(2)}</td><td>${cash.toFixed(2)}</td></tr>`;R*=1+RG;C*=1+CG}out.innerHTML=s+'</table>'}run()</script>""",
    },
}

GUIDES = {
    "compound-growth-basics": {
        "title": "How Compound Growth Works With Monthly Contributions",
        "summary": "A practical explanation of compounding, contribution timing, and scenario testing.",
        "product_id": "compound-growth-calculator",
        "body": [
            "Compound growth combines the return earned on the original principal with returns earned on prior gains. Adding recurring contributions changes the path because each contribution gets a different amount of time to compound.",
            "A useful forecast separates assumptions from facts. Test several annual return assumptions, contribution amounts, and time horizons instead of treating one projection as guaranteed.",
            "Monthly models commonly approximate the periodic rate as the annual rate divided by 12. Real investments can vary substantially from that simplified path, so the calculator is best used for scenario analysis rather than prediction.",
        ],
    },
    "small-business-kpis": {
        "title": "Five Small-Business KPIs Worth Tracking Every Month",
        "summary": "Revenue, costs, operating profit, margin, and run rate in one compact workflow.",
        "product_id": "microbusiness-kpi-dashboard",
        "body": [
            "A small business does not need dozens of metrics to understand whether its economics are improving. Revenue, costs, operating profit, profit margin, and a normalized run rate provide a useful first layer.",
            "The strongest trend signal is often direction rather than a single month's result. Comparing several periods helps distinguish durable improvement from a temporary spike.",
            "A lightweight dashboard is useful when it makes the monthly review repeatable. Keep the source data simple, preserve the historical rows, and reconcile the figures to the underlying payment and expense records.",
        ],
    },
    "cashflow-forecasting": {
        "title": "A Simple 12-Month Cash-Flow Forecasting Method",
        "summary": "Build a scenario model from starting revenue, costs, and monthly growth assumptions.",
        "product_id": "cashflow-forecast-template",
        "body": [
            "Cash-flow forecasting becomes easier when the model is explicit about its assumptions. Start with current monthly revenue and costs, then apply conservative growth rates to each independently.",
            "Revenue growth and cost growth rarely move at the same rate. Separating them makes margin expansion or compression visible before it becomes a surprise.",
            "Run multiple scenarios: conservative, expected, and optimistic. The purpose is not to predict the future perfectly; it is to identify which assumptions matter most and how much operating cushion may be needed.",
        ],
    },
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def cents(value: int) -> str:
    return f"${value / 100:,.2f} {CURRENCY}"


@contextmanager
def db():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATABASE_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
    finally:
        con.close()


def has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in con.execute(f"PRAGMA table_info({table})"))


def init_db() -> None:
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS sales(id TEXT PRIMARY KEY, product_id TEXT NOT NULL, net_cents INTEGER NOT NULL, currency TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS refunds(id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries(token_hash TEXT PRIMARY KEY, sale_id TEXT NOT NULL UNIQUE, product_id TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS product_views(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            visitor_hash TEXT NOT NULL,
            day TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(product_id, visitor_hash, day)
        );
        CREATE TABLE IF NOT EXISTS visitor_sessions(
            visitor_hash TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            medium TEXT NOT NULL,
            campaign TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sale_attribution(
            sale_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            medium TEXT NOT NULL,
            campaign TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        if not has_column(con, "deliveries", "downloads"):
            con.execute("ALTER TABLE deliveries ADD COLUMN downloads INTEGER NOT NULL DEFAULT 0")
        if not has_column(con, "refunds", "sale_id"):
            con.execute("ALTER TABLE refunds ADD COLUMN sale_id TEXT")
        if not has_column(con, "refunds", "product_id"):
            con.execute("ALTER TABLE refunds ADD COLUMN product_id TEXT")


def audit(kind: str, detail: dict | str) -> None:
    payload = detail if isinstance(detail, str) else json.dumps(detail, separators=(",", ":"), sort_keys=True)
    with db() as con:
        con.execute("INSERT INTO audit_log(kind,detail,created_at) VALUES(?,?,?)", (kind[:80], payload[:4000], utcnow()))


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


def visitor_hash(visitor_id: str) -> str:
    key = WEBHOOK_SECRET or ADMIN_TOKEN or "local-development-key"
    return hmac.new(key.encode(), visitor_id.encode(), hashlib.sha256).hexdigest()


def clean_tag(value: str | None, default: str) -> str:
    if not value:
        return default
    safe = "".join(ch for ch in value.strip() if ch.isalnum() or ch in "-_. ")[:80]
    return safe or default


def ensure_visitor(request: Request, response: Response) -> str:
    raw = request.cookies.get("bdt_visitor")
    if not raw or len(raw) > 128:
        raw = secrets.token_urlsafe(24)
        response.set_cookie("bdt_visitor", raw, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax", secure=PUBLIC_BASE_URL.startswith("https://"))
    return raw


def record_session(request: Request, response: Response) -> str:
    raw = ensure_visitor(request, response)
    vh = visitor_hash(raw)
    source = clean_tag(request.query_params.get("utm_source"), "direct")
    medium = clean_tag(request.query_params.get("utm_medium"), "none")
    campaign = clean_tag(request.query_params.get("utm_campaign"), "none")
    now = utcnow()
    with db() as con:
        con.execute(
            "INSERT INTO visitor_sessions(visitor_hash,source,medium,campaign,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(visitor_hash) DO UPDATE SET last_seen_at=excluded.last_seen_at",
            (vh, source, medium, campaign, now, now),
        )
    return vh


def record_product_view(product_id: str, vh: str) -> None:
    day = datetime.now(timezone.utc).date().isoformat()
    with db() as con:
        con.execute(
            "INSERT OR IGNORE INTO product_views(product_id,visitor_hash,day,created_at) VALUES(?,?,?,?)",
            (product_id, vh, day, utcnow()),
        )


@dataclass(frozen=True)
class ProductPerformance:
    product_id: str
    name: str
    views: int
    sales: int
    net_revenue_cents: int
    refunds: int
    refund_cents: int
    bayesian_conversion_rate: float
    refund_rate: float
    expected_net_value_per_view_cents: float
    exploration_score: float
    recommendation: str


def product_performance(days: int = 90) -> list[ProductPerformance]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()
    with db() as con:
        total_views = con.execute("SELECT COUNT(*) v FROM product_views WHERE created_at>=?", (cutoff,)).fetchone()["v"]
        rows = []
        for product_id, product in PRODUCTS.items():
            views = con.execute("SELECT COUNT(*) v FROM product_views WHERE product_id=? AND created_at>=?", (product_id, cutoff)).fetchone()["v"]
            sale_row = con.execute("SELECT COUNT(*) n, COALESCE(SUM(net_cents),0) total FROM sales WHERE product_id=? AND created_at>=?", (product_id, cutoff)).fetchone()
            refund_row = con.execute("SELECT COUNT(*) n, COALESCE(SUM(amount_cents),0) total FROM refunds WHERE product_id=? AND created_at>=?", (product_id, cutoff)).fetchone()
            sales = sale_row["n"]
            net_revenue = sale_row["total"]
            refunds = refund_row["n"]
            refund_cents = refund_row["total"]
            bayes_conversion = (sales + 1.0) / (views + 50.0)
            refund_rate = refunds / sales if sales else 0.0
            avg_net = net_revenue / sales if sales else product["price_cents"] * 0.95
            expected_value = bayes_conversion * avg_net * max(0.0, 1.0 - refund_rate)
            exploration = bayes_conversion + 0.20 * math.sqrt(math.log(total_views + 2.0) / (views + 1.0))
            if views < 25:
                recommendation = "explore"
            elif sales >= 5 and refund_rate >= 0.20:
                recommendation = "review-refunds"
            elif views >= 100 and bayes_conversion < 0.015:
                recommendation = "revise-offer"
            elif bayes_conversion >= 0.035 and refund_rate < 0.10:
                recommendation = "promote"
            else:
                recommendation = "maintain"
            rows.append(ProductPerformance(product_id, product["name"], views, sales, net_revenue, refunds, refund_cents, round(bayes_conversion, 6), round(refund_rate, 6), round(expected_value, 3), round(exploration, 6), recommendation))
    return sorted(rows, key=lambda x: (x.exploration_score, x.expected_net_value_per_view_cents), reverse=True)


def featured_product_id() -> str:
    ranked = product_performance()
    return ranked[0].product_id if ranked else next(iter(PRODUCTS))


def page_shell(title: str, description: str, canonical: str, body: str, json_ld: dict | None = None) -> str:
    schema = ""
    if json_ld:
        schema = f"<script type='application/ld+json'>{html.escape(json.dumps(json_ld, separators=(',', ':')))}</script>"
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><meta name='description' content='{html.escape(description, quote=True)}'><link rel='canonical' href='{html.escape(canonical, quote=True)}'>{schema}<style>body{{font-family:system-ui,-apple-system,sans-serif;max-width:1050px;margin:auto;padding:28px;color:#171717;background:#fafafa}}a{{color:#174ea6}}header{{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-bottom:30px}}nav a{{margin-left:14px}}main{{background:white;padding:26px;border:1px solid #e5e5e5;border-radius:16px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:18px}}.card{{border:1px solid #ddd;border-radius:14px;padding:20px;background:white}}.badge{{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef3ff;font-size:.8rem}}.price{{font-size:1.25rem;font-weight:700}}.cta{{display:inline-block;padding:10px 14px;border-radius:9px;background:#171717;color:white;text-decoration:none}}footer{{margin-top:30px;color:#666;font-size:.9rem}}code{{overflow-wrap:anywhere}}</style></head><body><header><a href='/'><strong>{html.escape(SITE_NAME)}</strong></a><nav><a href='/guides'>Guides</a><a href='/feed.xml'>Feed</a></nav></header>{body}<footer>Digital tools are delivered after confirmed payment. Forecasting tools provide scenario analysis, not guaranteed outcomes.</footer></body></html>"""


app = FastAPI(title="Passive Income Engine", version="2.0.0")
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
def storefront(request: Request):
    response = HTMLResponse("")
    record_session(request, response)
    featured = featured_product_id()
    cards = []
    for pid, p in PRODUCTS.items():
        badge = "<span class='badge'>Featured by performance engine</span>" if pid == featured else ""
        cards.append(f"<article class='card'>{badge}<h2>{html.escape(p['name'])}</h2><p>{html.escape(p['description'])}</p><p class='price'>{cents(p['price_cents'])}</p><a class='cta' href='/products/{quote(pid)}'>View product</a></article>")
    body = f"<main><h1>Practical offline tools for personal finance and small-business planning</h1><p>Instant-download utilities designed to run locally in a browser.</p><section class='grid'>{''.join(cards)}</section></main>"
    response.body = page_shell(SITE_NAME, "Offline financial and small-business planning tools.", f"{PUBLIC_BASE_URL}/", body).encode()
    response.headers["content-length"] = str(len(response.body))
    return response


@app.get("/products/{product_id}", response_class=HTMLResponse)
def product_page(product_id: str, request: Request):
    product = PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    response = HTMLResponse("")
    vh = record_session(request, response)
    record_product_view(product_id, vh)
    body = f"<main><span class='badge'>Instant digital download</span><h1>{html.escape(product['name'])}</h1><p>{html.escape(product['description'])}</p><p class='price'>{cents(product['price_cents'])}</p><p>Checkout integration should submit the server-owned product ID <code>{html.escape(product_id)}</code> to your approved payment adapter. Fulfillment occurs only after a signed completed-sale webhook.</p><h2>Designed for</h2><ul>{''.join(f'<li>{html.escape(k)}</li>' for k in product['keywords'])}</ul><p><a href='/guides'>Read the free guides</a></p></main>"
    schema = {"@context": "https://schema.org", "@type": "Product", "name": product["name"], "description": product["description"], "offers": {"@type": "Offer", "priceCurrency": CURRENCY, "price": f"{product['price_cents']/100:.2f}", "availability": "https://schema.org/InStock", "url": f"{PUBLIC_BASE_URL}/products/{product_id}"}}
    response.body = page_shell(product["name"], product["description"], f"{PUBLIC_BASE_URL}/products/{product_id}", body, schema).encode()
    response.headers["content-length"] = str(len(response.body))
    return response


@app.get("/guides", response_class=HTMLResponse)
def guide_index():
    cards = "".join(f"<article class='card'><h2><a href='/guides/{quote(slug)}'>{html.escape(g['title'])}</a></h2><p>{html.escape(g['summary'])}</p></article>" for slug, g in GUIDES.items())
    body = f"<main><h1>Free planning guides</h1><p>Evergreen educational content that complements the downloadable tools.</p><section class='grid'>{cards}</section></main>"
    return page_shell("Guides | " + SITE_NAME, "Free guides for compound growth, KPIs, and cash-flow forecasting.", f"{PUBLIC_BASE_URL}/guides", body)


@app.get("/guides/{slug}", response_class=HTMLResponse)
def guide_page(slug: str):
    guide = GUIDES.get(slug)
    if not guide:
        raise HTTPException(404, "Guide not found")
    product = PRODUCTS[guide["product_id"]]
    paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in guide["body"])
    body = f"<main><article><h1>{html.escape(guide['title'])}</h1><p><strong>{html.escape(guide['summary'])}</strong></p>{paragraphs}<hr><h2>Related tool</h2><p>{html.escape(product['description'])}</p><p><a class='cta' href='/products/{quote(guide['product_id'])}'>View {html.escape(product['name'])}</a></p></article></main>"
    schema = {"@context": "https://schema.org", "@type": "Article", "headline": guide["title"], "description": guide["summary"], "mainEntityOfPage": f"{PUBLIC_BASE_URL}/guides/{slug}"}
    return page_shell(guide["title"], guide["summary"], f"{PUBLIC_BASE_URL}/guides/{slug}", body, schema)


@app.get("/sitemap.xml")
def sitemap():
    urls = [f"{PUBLIC_BASE_URL}/", f"{PUBLIC_BASE_URL}/guides"] + [f"{PUBLIC_BASE_URL}/products/{pid}" for pid in PRODUCTS] + [f"{PUBLIC_BASE_URL}/guides/{slug}" for slug in GUIDES]
    xml = "<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>" + "".join(f"<url><loc>{xml_escape(url)}</loc></url>" for url in urls) + "</urlset>"
    return Response(xml, media_type="application/xml")


@app.get("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /webhooks/\nSitemap: {PUBLIC_BASE_URL}/sitemap.xml\n", media_type="text/plain")


@app.get("/feed.xml")
def feed():
    items = "".join(f"<item><title>{xml_escape(g['title'])}</title><link>{xml_escape(PUBLIC_BASE_URL + '/guides/' + slug)}</link><description>{xml_escape(g['summary'])}</description><guid>{xml_escape(PUBLIC_BASE_URL + '/guides/' + slug)}</guid></item>" for slug, g in GUIDES.items())
    xml = f"<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>{xml_escape(SITE_NAME)}</title><link>{xml_escape(PUBLIC_BASE_URL)}</link><description>Planning guides and digital tools</description>{items}</channel></rss>"
    return Response(xml, media_type="application/rss+xml")


@app.get("/go/{product_id}")
def campaign_redirect(product_id: str, request: Request):
    if product_id not in PRODUCTS:
        raise HTTPException(404, "Product not found")
    params = []
    for key in ("utm_source", "utm_medium", "utm_campaign"):
        value = request.query_params.get(key)
        if value:
            params.append(f"{key}={quote(clean_tag(value, 'none'))}")
    suffix = ("?" + "&".join(params)) if params else ""
    return RedirectResponse(f"/products/{quote(product_id)}{suffix}", status_code=302)


@app.post("/webhooks/payment")
async def payment_webhook(request: Request):
    body = await request.body()
    if not verify_signature(body, request.headers.get("x-signature", "")):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    event_id = str(event.get("id", ""))
    if not event_id:
        raise HTTPException(400, "Missing event id")
    try:
        with db() as con:
            con.execute("INSERT INTO events VALUES(?,?)", (event_id, utcnow()))
    except sqlite3.IntegrityError:
        return {"status": "duplicate"}
    kind = event.get("type")
    if kind == "sale.completed":
        product_id = str(event.get("product_id", ""))
        if product_id not in PRODUCTS:
            raise HTTPException(400, "Unknown product")
        expected = PRODUCTS[product_id]["price_cents"]
        gross = int(event.get("gross_cents", -1))
        net = int(event.get("net_cents", -1))
        if gross != expected or event.get("currency") != CURRENCY:
            raise HTTPException(409, "Price or currency mismatch")
        if net < 0 or net > gross:
            raise HTTPException(409, "Invalid net amount")
        sale_id = str(event.get("sale_id", ""))
        if not sale_id:
            raise HTTPException(400, "Missing sale id")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(hours=DOWNLOAD_TTL_HOURS)).isoformat()
        now = utcnow()
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("INSERT OR IGNORE INTO sales VALUES(?,?,?,?,?)", (sale_id, product_id, net, CURRENCY, now))
            con.execute("DELETE FROM deliveries WHERE sale_id=?", (sale_id,))
            con.execute("INSERT INTO deliveries(token_hash,sale_id,product_id,expires_at,downloads) VALUES(?,?,?,?,0)", (token_hash, sale_id, product_id, expires))
            visitor_id = event.get("visitor_id")
            if visitor_id:
                vh = visitor_hash(str(visitor_id))
                session = con.execute("SELECT source,medium,campaign FROM visitor_sessions WHERE visitor_hash=?", (vh,)).fetchone()
                if session:
                    con.execute("INSERT OR REPLACE INTO sale_attribution(sale_id,source,medium,campaign,created_at) VALUES(?,?,?,?,?)", (sale_id, session["source"], session["medium"], session["campaign"], now))
            con.execute("COMMIT")
        audit("sale.completed", {"sale_id": sale_id, "product_id": product_id, "net_cents": net})
        return {"status": "fulfilled", "download_url": f"/download/{token}"}
    if kind == "sale.refunded":
        refund_id = str(event.get("refund_id", ""))
        amount = int(event.get("amount_cents", -1))
        sale_id = str(event.get("sale_id", "")) or None
        if not refund_id or amount <= 0 or event.get("currency") != CURRENCY:
            raise HTTPException(400, "Invalid refund")
        product_id = None
        with db() as con:
            if sale_id:
                sale = con.execute("SELECT product_id FROM sales WHERE id=?", (sale_id,)).fetchone()
                product_id = sale["product_id"] if sale else None
            con.execute("INSERT OR IGNORE INTO refunds(id,amount_cents,currency,created_at,sale_id,product_id) VALUES(?,?,?,?,?,?)", (refund_id, amount, CURRENCY, utcnow(), sale_id, product_id))
        audit("sale.refunded", {"refund_id": refund_id, "sale_id": sale_id, "amount_cents": amount})
        return {"status": "recorded"}
    return {"status": "ignored"}


@app.get("/download/{token}")
def download(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM deliveries WHERE token_hash=?", (token_hash,)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc) or row["downloads"] >= MAX_DOWNLOADS:
            con.execute("ROLLBACK")
            raise HTTPException(404, "Invalid, expired, or exhausted download link")
        con.execute("UPDATE deliveries SET downloads=downloads+1 WHERE token_hash=?", (token_hash,))
        con.execute("COMMIT")
    product = PRODUCTS[row["product_id"]]
    return Response(product["content"], media_type="text/html", headers={"Content-Disposition": f"attachment; filename={product['filename']}"})


@app.get("/admin/treasury")
def treasury_status(request: Request):
    require_admin(request)
    return asdict(treasury())


@app.get("/admin/optimizer")
def optimizer_status(request: Request, days: int = 90):
    require_admin(request)
    days = max(1, min(days, 365))
    ranked = product_performance(days)
    return {"window_days": days, "featured_product_id": ranked[0].product_id if ranked else None, "products": [asdict(item) for item in ranked], "policy": {"automatic_action": "rotate featured placement only", "price_changes": "recommendation-only", "external_marketing": "not automated"}}


@app.get("/admin/attribution")
def attribution_status(request: Request):
    require_admin(request)
    with db() as con:
        rows = con.execute("SELECT source,medium,campaign,COUNT(*) sales FROM sale_attribution GROUP BY source,medium,campaign ORDER BY sales DESC LIMIT 100").fetchall()
    return {"attribution": [dict(r) for r in rows]}


@app.get("/admin/audit")
def audit_status(request: Request, limit: int = 100):
    require_admin(request)
    limit = max(1, min(limit, 500))
    with db() as con:
        rows = con.execute("SELECT id,kind,detail,created_at FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"events": [dict(r) for r in rows]}


@app.post("/admin/expenses")
def add_expense(request: Request, expense: Expense):
    require_admin(request)
    if expense.amount_cents <= 0:
        raise HTTPException(400, "amount_cents must be positive")
    with db() as con:
        con.execute("INSERT INTO expenses(category,amount_cents,currency,note,created_at) VALUES(?,?,?,?,?)", (expense.category[:80], expense.amount_cents, CURRENCY, expense.note[:500], utcnow()))
    audit("expense.recorded", {"category": expense.category[:80], "amount_cents": expense.amount_cents})
    return {"status": "recorded"}


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0", "currency": CURRENCY, "products": len(PRODUCTS), "guides": len(GUIDES)}
