from __future__ import annotations

import html
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
_STATIC_DB = tempfile.TemporaryDirectory()
os.environ.setdefault("DATABASE_PATH", str(Path(_STATIC_DB.name) / "static-build.db"))
sys.path.insert(0, str(ROOT))

import engine  # noqa: E402
OUTPUT = ROOT / "site"
BACKEND = os.getenv("BACKEND_PUBLIC_URL", "").rstrip("/")
PAGES_BASE_PATH = os.getenv("PAGES_BASE_PATH", "/Build").rstrip("/")
SITE_URL = os.getenv(
    "STATIC_SITE_URL",
    "https://abovebeyond4north-netizen.github.io/Build",
).rstrip("/")

STYLE = """
:root{color-scheme:light;--ink:#11211b;--green:#176b4d;--mint:#dff5e9;--paper:#fbfdfb}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,sans-serif;color:var(--ink);background:var(--paper);line-height:1.6}
header,main,footer{max-width:1080px;margin:auto;padding:22px}header{display:flex;justify-content:space-between;align-items:center;gap:20px}
nav a{margin-left:16px}a{color:var(--green)}.hero{padding:64px 22px}.hero h1{font-size:clamp(2.2rem,6vw,4.8rem);line-height:1.03;max-width:850px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}.card{padding:22px;border:1px solid #cbd9d1;border-radius:16px;background:white}
.cta{display:inline-block;padding:11px 16px;border-radius:9px;background:var(--green);color:white;text-decoration:none;font-weight:700}
.badge{display:inline-block;padding:4px 9px;border-radius:999px;background:var(--mint);font-size:.82rem}form{display:grid;gap:12px;max-width:540px}
input{font:inherit;padding:11px;border:1px solid #9aac9f;border-radius:8px}button{font:inherit;border:0;cursor:pointer}.notice{padding:14px;border-radius:10px;background:var(--mint)}
footer{margin-top:48px;border-top:1px solid #dbe5df;font-size:.9rem}
"""

def path(relative: str = "") -> str:
    suffix = relative.lstrip("/")
    return f"{PAGES_BASE_PATH}/{suffix}" if suffix else f"{PAGES_BASE_PATH}/"


def shell(title: str, description: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(description, quote=True)}">
<link rel="canonical" href="{html.escape(SITE_URL, quote=True)}"><link rel="stylesheet" href="{path('assets/style.css')}">
</head><body><header><a href="{path()}"><strong>{html.escape(engine.SITE_NAME)}</strong></a>
<nav><a href="{path('products/')}">Tools</a><a href="{path('guides/')}">Guides</a><a href="{path('resources/')}">Resources</a></nav></header>
{body}<footer>Educational tools and scenario analysis. Results are not financial advice or guarantees.
<a href="{path('privacy/')}">Privacy</a> · <a href="{path('disclosure/')}">Affiliate disclosure</a></footer></body></html>"""


def write(relative: str, document: str) -> None:
    target = OUTPUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")


def backend_url(route: str) -> str:
    return f"{BACKEND}{route}" if BACKEND else ""


def build() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    (OUTPUT / "assets").mkdir(parents=True)
    (OUTPUT / "assets" / "style.css").write_text(STYLE, encoding="utf-8")
    (OUTPUT / ".nojekyll").write_text("", encoding="utf-8")

    product_cards = "".join(
        f"""<article class="card"><span class="badge">Offline digital tool</span>
<h2>{html.escape(product['name'])}</h2><p>{html.escape(product['description'])}</p>
<p><strong>{engine.cents(product['price_cents'])}</strong></p>
<a href="{path('products/' + quote(product_id) + '/') }">View tool</a></article>"""
        for product_id, product in engine.PRODUCTS.items()
    )
    lead_action = backend_url("/api/leads")
    lead_form = (
        f"""<form id="lead"><label>Email address<input required type="email" name="email" autocomplete="email"></label>
<label><input required type="checkbox" name="consent"> Send me the checklist and occasional relevant updates.</label>
<button class="cta" type="submit">Get the free checklist</button><p id="lead-status" role="status"></p></form>
<script>document.getElementById('lead').addEventListener('submit',async(e)=>{{e.preventDefault();const f=new FormData(e.target),s=document.getElementById('lead-status');s.textContent='Sending…';try{{const r=await fetch({json.dumps(lead_action)},{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:f.get('email'),consent:f.get('consent')==='on',source:'github-pages',campaign:'monthly-review'}})}});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Unable to subscribe');window.location.assign({json.dumps(BACKEND)}+d.resource_url)}}catch(x){{s.textContent=x.message}}}});</script>"""
        if lead_action
        else "<p class='notice'>The free checklist becomes available when the hosted service URL is connected.</p>"
    )
    home = shell(
        engine.SITE_NAME,
        "Practical digital tools, guides, and carefully selected resources.",
        f"""<main><section class="hero"><span class="badge">Practical tools that work offline</span>
<h1>Make clearer money and business decisions.</h1>
<p>Use focused calculators, plain-language guides, and selected resources built for independent operators.</p>
<a class="cta" href="{path('products/')}">Explore the tools</a></section>
<section><h2>Digital products</h2><div class="grid">{product_cards}</div></section>
<section class="hero"><h2>Free monthly money review</h2><p>Get a concise checklist for reviewing income, costs, reserves, and next-month goals.</p>{lead_form}</section></main>""",
    )
    write("index.html", home)

    write(
        "products/index.html",
        shell("Digital tools", "Offline planning tools.", f"<main><h1>Digital tools</h1><div class='grid'>{product_cards}</div></main>"),
    )
    for product_id, product in engine.PRODUCTS.items():
        checkout = backend_url(f"/products/{quote(product_id)}")
        action = (
            f"<a class='cta' href='{html.escape(checkout, quote=True)}'>Buy securely</a>"
            if checkout
            else "<p class='notice'>Checkout becomes available when the hosted payment service is connected.</p>"
        )
        write(
            f"products/{product_id}/index.html",
            shell(
                product["name"],
                product["description"],
                f"""<main><article><span class="badge">Instant digital download</span>
<h1>{html.escape(product['name'])}</h1><p>{html.escape(product['description'])}</p>
<p><strong>{engine.cents(product['price_cents'])}</strong></p>{action}
<h2>Designed for</h2><ul>{''.join(f"<li>{html.escape(k)}</li>" for k in product['keywords'])}</ul></article></main>""",
            ),
        )

    guide_cards = "".join(
        f"<article class='card'><h2><a href='{path('guides/' + slug + '/')}'>{html.escape(guide['title'])}</a></h2><p>{html.escape(guide['summary'])}</p></article>"
        for slug, guide in engine.GUIDES.items()
    )
    write("guides/index.html", shell("Guides", "Free practical guides.", f"<main><h1>Guides</h1><div class='grid'>{guide_cards}</div></main>"))
    for slug, guide in engine.GUIDES.items():
        paragraphs = "".join(f"<p>{html.escape(value)}</p>" for value in guide["body"])
        write(
            f"guides/{slug}/index.html",
            shell(guide["title"], guide["summary"], f"<main><article><h1>{html.escape(guide['title'])}</h1><p><strong>{html.escape(guide['summary'])}</strong></p>{paragraphs}<p><a class='cta' href='{path('products/' + guide['product_id'] + '/') }'>Use the related tool</a></p></article></main>"),
        )

    resources_link = backend_url("/resources")
    resources_body = (
        f"<p><a class='cta' href='{html.escape(resources_link, quote=True)}'>Browse verified partner resources</a></p>"
        if resources_link
        else "<p class='notice'>Verified partner offers appear after the hosted service is connected.</p>"
    )
    write("resources/index.html", shell("Recommended resources", "Curated partner resources.", f"<main><h1>Recommended resources</h1><p>Some links may earn us a commission at no extra cost to you.</p>{resources_body}</main>"))
    write("disclosure/index.html", shell("Affiliate disclosure", "Affiliate relationship disclosure.", "<main><h1>Affiliate disclosure</h1><p>Some resource links may be affiliate links. If you buy through one, we may earn a commission at no extra cost to you. Recommendations are selected for relevance and are not guarantees.</p></main>"))
    write("privacy/index.html", shell("Privacy", "Privacy information.", "<main><h1>Privacy</h1><p>The storefront records limited first-party activity needed for attribution, fulfillment, fraud prevention, and service improvement. Email addresses are stored only after explicit consent and can be unsubscribed using the link returned at signup. Payment credentials are handled by PayPal and are not stored by this site.</p></main>"))

    urls = ["", "products/", "guides/", "resources/", "privacy/", "disclosure/"]
    urls += [f"products/{key}/" for key in engine.PRODUCTS]
    urls += [f"guides/{key}/" for key in engine.GUIDES]
    sitemap = "<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>" + "".join(
        f"<url><loc>{html.escape(SITE_URL + '/' + value)}</loc></url>" for value in urls
    ) + "</urlset>"
    write("sitemap.xml", sitemap)
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")


if __name__ == "__main__":
    build()
