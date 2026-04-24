"""Render all 5 skins x 3 templates = 15 PNG previews — Neural Command v4."""
import datetime, sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.variants import SKINS

env      = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
base_css = (ROOT / "templates" / "_base.css").read_text(encoding="utf-8")
out_dir  = ROOT / "_previews"
out_dir.mkdir(exist_ok=True)

today = datetime.date.today().strftime("%b %d, %Y").upper()

sample_picks = [
    {"player_name": "LeBron James",  "stat_type": "Points",   "prop_line": 25.5, "direction": "OVER",  "platform": "PrizePicks", "confidence_score": 87, "edge_pct": 12.4, "result": "WIN", "team": "LAL", "opponent": "GSW"},
    {"player_name": "Stephen Curry", "stat_type": "Assists",  "prop_line": 6.5,  "direction": "OVER",  "platform": "Underdog",   "confidence_score": 82, "edge_pct":  9.1, "result": "WIN", "team": "GSW", "opponent": "LAL"},
    {"player_name": "Jayson Tatum",  "stat_type": "Rebounds", "prop_line": 8.5,  "direction": "UNDER", "platform": "PrizePicks", "confidence_score": 78, "edge_pct":  7.3, "result": "WIN", "team": "BOS", "opponent": "MIA"},
    {"player_name": "Kevin Durant",  "stat_type": "Points",   "prop_line": 28.5, "direction": "OVER",  "platform": "DK Pick6",   "confidence_score": 75, "edge_pct":  8.8, "result": "WIN", "team": "PHX", "opponent": "DEN"},
]

TEMPLATES = {
    "slate.html": {
        "slug": "slate",
        "ctx": {
            "eyebrow": "TONIGHT'S PICKS", "title": "Tonight's Platform Picks",
            "date_str": today, "picks": sample_picks, "cols": 2,
            "watermark_text": "SMART PICK PRO",
        },
    },
    "results.html": {
        "slug": "recap",
        "ctx": {
            "eyebrow": "LAST NIGHT'S RESULTS", "title": "4-1 Last Night",
            "subtitle": "RECEIPTS ALWAYS ON FILE", "date_str": today,
            "wins": 4, "losses": 1, "win_rate": 80.0, "roi_pct": 32.5,
            "picks": sample_picks, "cols": 2, "watermark_text": "SMART PICK PRO",
        },
    },
    "brand_cta.html": {
        "slug": "brand",
        "ctx": {
            "headline": "THE EDGE\nISN'T LUCK.\nIT'S MATH.",
            "subheadline": "1,000 Monte Carlo simulations per pick. Zero black boxes. Free trial.",
            "button_text": "\u2192 START FREE TRIAL",
            "tagline": "Quantitative NBA Analytics",
            "watermark_text": "SMART PICK PRO",
        },
    },
}

# Platform sizes (square=IG/FB, landscape=Twitter, portrait=Stories/TikTok)
SIZES = {
    "square":    (1080, 1080),
    "landscape": (1200, 675),
    "portrait":  (1080, 1920),
}

with sync_playwright() as p:
    browser = p.chromium.launch()

    # ── Pass 1: all 5 skins at square (skin comparison) ───────────────────────
    print("Pass 1 — Skin comparison (square 1080×1080):")
    for skin in SKINS:
        for tpl_name, tpl in TEMPLATES.items():
            tmpl = env.get_template(tpl_name)
            html = tmpl.render(**tpl["ctx"], base_css=base_css, skin_class=skin["class"])
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            page.set_content(html, wait_until="networkidle")
            fname = f"{tpl['slug']}_{skin['id']}.png"
            page.screenshot(path=str(out_dir / fname), full_page=False)
            print(f"  [{skin['label']:18}] {tpl['slug']:7} → {fname}")
            page.close()

    # ── Pass 2: all 3 platform sizes using neural skin (layout check) ─────────
    print("\nPass 2 — Platform size layouts (neural skin):")
    neural_skin = next(s for s in SKINS if s["id"] == "neural")
    for size_key, (w, h) in SIZES.items():
        for tpl_name, tpl in TEMPLATES.items():
            tmpl = env.get_template(tpl_name)
            html = tmpl.render(**tpl["ctx"], base_css=base_css, skin_class=neural_skin["class"])
            page = browser.new_page(viewport={"width": w, "height": h})
            page.set_content(html, wait_until="networkidle")
            fname = f"{tpl['slug']}_neural_{size_key}_{w}x{h}.png"
            page.screenshot(path=str(out_dir / fname), full_page=False)
            print(f"  [{size_key:9} {w}×{h}] {tpl['slug']:7} → {fname}")
            page.close()

    browser.close()

total_skins = len(SKINS) * len(TEMPLATES)
total_sizes = len(SIZES) * len(TEMPLATES)
print(f"\nDone — {total_skins} skin + {total_sizes} layout previews in social_engine/_previews/")
