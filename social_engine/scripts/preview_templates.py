"""Render all 3 post templates to PNG previews — Neural Command v3."""
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from pathlib import Path
import datetime

ROOT     = Path(__file__).resolve().parent.parent
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

pages = [
    ("slate.html", "_previews/slate_preview.png", {
        "eyebrow":        "TONIGHT'S PICKS",
        "title":          "Tonight's Platform Picks",
        "date_str":       today,
        "picks":          sample_picks,
        "cols":           2,
        "watermark_text": "SMART PICK PRO",
    }),
    ("results.html", "_previews/recap_preview.png", {
        "eyebrow":        "LAST NIGHT'S RESULTS",
        "title":          "4-1 Last Night",
        "subtitle":       "RECEIPTS ALWAYS ON FILE — ZERO HIDDEN LOSSES",
        "date_str":       today,
        "wins":           4,
        "losses":         1,
        "win_rate":       80.0,
        "roi_pct":        32.5,
        "picks":          sample_picks,
        "cols":           2,
        "watermark_text": "SMART PICK PRO",
    }),
    ("brand_cta.html", "_previews/brand_preview.png", {
        "headline":       "THE EDGE\nISN'T LUCK.\nIT'S MATH.",
        "subheadline":    "1,000 Monte Carlo simulations per pick. Zero black boxes. Free trial.",
        "button_text":    "\u2192 START FREE TRIAL",
        "tagline":        "Quantitative NBA Analytics",
        "watermark_text": "SMART PICK PRO",
    }),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for tpl, out_rel, ctx in pages:
        tmpl     = env.get_template(tpl)
        html     = tmpl.render(**ctx, base_css=base_css)
        page     = browser.new_page(viewport={"width": 1080, "height": 1080})
        page.set_content(html, wait_until="networkidle")
        out_path = ROOT / out_rel
        page.screenshot(path=str(out_path), full_page=False)
        print("Rendered:", out_path.name)
    browser.close()

print("Done — previews in social_engine/_previews/")
