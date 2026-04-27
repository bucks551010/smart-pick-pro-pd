"""
card_templates.py — Standalone hardcoded card HTML generators.

Each function returns raw HTML for a specific design variant.
Logo is embedded as a base64 data URI so templates work offline/headless.

Platform safe zones (no bleed):
  square   1080×1080  — Instagram, Twitter, Facebook (60px inner margin)
  portrait 1080×1350  — Instagram portrait / Reels cover (60px inner margin)
  landscape 1200×628  — Twitter/X card, Facebook link preview (50px inner margin)
  story    1080×1920  — Instagram/Facebook Stories (80px inner margin)
"""
from __future__ import annotations
import base64
from pathlib import Path

# ── Logo loader ────────────────────────────────────────────────────────
_ASSETS = Path(__file__).resolve().parent / "assets"

def _b64(filename: str) -> str | None:
    p = _ASSETS / filename
    if not p.exists():
        # fallback to parent assets/
        p = _ASSETS.parent.parent / "assets" / filename
    if p.exists():
        ext = p.suffix.lstrip(".")
        mime = "svg+xml" if ext == "svg" else ext
        return f"data:image/{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return None

_LOGO       = _b64("Smart_Pick_Pro_Logo.png")
_LOGO_GOLD  = _b64("NewGold_Logo.png")

_LOGO_TAG   = f'<img class="logo" src="{_LOGO}" alt="SmartPickPro">' if _LOGO else '<div class="logo-text">SP</div>'
_LOGO_GOLD_TAG = f'<img class="logo" src="{_LOGO_GOLD}" alt="SmartPickPro">' if _LOGO_GOLD else '<div class="logo-text">SP</div>'

_FONTS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800;900&family=Bebas+Neue&family=Inter:wght@400;600;700;900&family=JetBrains+Mono:wght@600;700&display=swap" rel="stylesheet">
"""

# ══════════════════════════════════════════════════════════════════════
# TEMPLATE 1 — "SCOREBOARD HERO"  (cyan glow)
# Best for: square (Instagram feed, Twitter)
# ══════════════════════════════════════════════════════════════════════
def scoreboard_hero(wins: int, losses: int, win_rate: float,
                    width: int = 1080, height: int = 1080) -> str:
    pad = max(60, int(width * 0.056))
    logo_h = max(48, int(height * 0.05))
    big_fs  = int(min(width, height) * 0.20)
    dash_fs = int(big_fs * 0.72)
    hl_fs   = int(min(width, height) * 0.058)
    sub_fs  = int(min(width, height) * 0.020)
    wr_fs   = int(min(width, height) * 0.046)
    pill_py = int(height * 0.013)
    pill_px = int(width  * 0.040)

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{background:#04060E;font-family:'Inter',sans-serif}}
.bg{{position:absolute;inset:0;
  background:
    radial-gradient(ellipse 60% 50% at 50% 18%, rgba(0,240,255,.13) 0%,transparent 70%),
    radial-gradient(ellipse 40% 30% at 50% 88%, rgba(0,213,89,.08) 0%,transparent 60%),
    radial-gradient(circle,rgba(0,240,255,.06) 1px,transparent 1px) 0 0/52px 52px;
}}
.border-top,.border-bot{{position:absolute;left:0;right:0;height:3px;background:linear-gradient(90deg,#00D559,#00F0FF,#00D559)}}
.border-top{{top:0}}.border-bot{{bottom:0}}
.inner{{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100%;padding:{pad}px;gap:0}}
/* logo */
.logo{{height:{logo_h}px;object-fit:contain;margin-bottom:{int(height*.04)}px;filter:brightness(1.1)}}
.logo-text{{height:{logo_h}px;display:flex;align-items:center;font-family:'Bebas Neue',sans-serif;font-size:{logo_h}px;color:#00F0FF}}
/* eyebrow */
.eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{sub_fs*1.1:.0f}px;letter-spacing:6px;
  color:#00F0FF;text-transform:uppercase;opacity:.85;margin-bottom:{int(height*.014)}px}}
/* main record */
.record{{font-family:'Bebas Neue',sans-serif;font-size:{big_fs}px;line-height:1;letter-spacing:-2px;
  color:#00D559;text-shadow:0 0 40px rgba(0,213,89,.9),0 0 80px rgba(0,213,89,.5),0 0 160px rgba(0,213,89,.2)}}
.record .dash{{color:#00F0FF;font-size:{dash_fs}px}}
.record .lss{{color:#FF4757}}
/* headline */
.headline{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{hl_fs}px;letter-spacing:4px;
  text-transform:uppercase;color:#fff;margin-top:{int(height*.006)}px}}
.headline span{{color:#00D559}}
/* sub */
.sub{{font-family:'Barlow Condensed',sans-serif;font-weight:500;font-size:{sub_fs}px;letter-spacing:5px;
  color:rgba(255,255,255,.4);margin-top:{int(height*.018)}px;text-transform:uppercase}}
/* pill stats */
.pill{{display:flex;align-items:center;gap:{int(width*.022)}px;margin-top:{int(height*.040)}px;
  border:1.5px solid rgba(0,240,255,.2);border-radius:60px;
  padding:{pill_py}px {pill_px}px;background:rgba(0,240,255,.04)}}
.ps{{text-align:center}}
.ps-val{{font-family:'Bebas Neue',sans-serif;font-size:{wr_fs}px;color:#00F0FF;letter-spacing:2px}}
.ps-val.g{{color:#00D559}}.ps-val.r{{color:#FF4757}}
.ps-lbl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(sub_fs*.9)}px;
  letter-spacing:3px;color:rgba(255,255,255,.45);text-transform:uppercase;margin-top:2px}}
.divv{{width:1px;height:{int(wr_fs*.9)}px;background:rgba(255,255,255,.12)}}
/* brand footer */
.brand-foot{{position:absolute;bottom:{int(height*.032)}px;display:flex;align-items:center;gap:8px}}
.bd{{width:7px;height:7px;border-radius:50%;background:#00D559;box-shadow:0 0 8px #00D559}}
.bt{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(sub_fs*.95)}px;
  letter-spacing:4px;color:rgba(255,255,255,.35);text-transform:uppercase}}
.date-tag{{position:absolute;top:{int(height*.032)}px;right:{pad}px;font-family:'JetBrains Mono',monospace;
  font-size:{int(sub_fs*.95)}px;color:rgba(0,240,255,.5);letter-spacing:2px}}
</style></head><body>
<div class="bg"></div>
<div class="border-top"></div><div class="border-bot"></div>
<div class="inner">
  {_LOGO_TAG}
  <div class="eyebrow">April 26, 2026 · Final Results</div>
  <div class="record"><span>{wins}</span><span class="dash"> – </span><span class="lss">{losses}</span></div>
  <div class="headline">WIN <span>RATE</span> {win_rate}%</div>
  <div class="sub">{wins} documented wins · all results on file</div>
  <div class="pill">
    <div class="ps"><div class="ps-val g">{wins}</div><div class="ps-lbl">Wins</div></div>
    <div class="divv"></div>
    <div class="ps"><div class="ps-val r">{losses}</div><div class="ps-lbl">Losses</div></div>
    <div class="divv"></div>
    <div class="ps"><div class="ps-val">{win_rate}%</div><div class="ps-lbl">Win Rate</div></div>
    <div class="divv"></div>
    <div class="ps"><div class="ps-val">{wins+losses}</div><div class="ps-lbl">Settled</div></div>
  </div>
</div>
<div class="brand-foot"><div class="bd"></div><div class="bt">smartpickpro.ai</div></div>
<div class="date-tag">APR 26 · 2026</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# TEMPLATE 2 — "RECEIPTS GOLD"  (split layout, player list)
# Best for: square (Instagram feed), portrait
# ══════════════════════════════════════════════════════════════════════
def receipts_gold(wins: int, losses: int, win_rate: float,
                  picks: list[dict],
                  width: int = 1080, height: int = 1080) -> str:
    pad = int(width * 0.056)
    logo_h = int(height * 0.048)
    left_w = int(width * 0.30)

    def rows_html() -> str:
        out = ""
        for p in picks[:7]:
            name   = p.get("player_name", "")
            stat   = p.get("stat_type", "")[:12]
            line   = p.get("prop_line", "")
            direct = p.get("direction", "OVER")
            actual = p.get("actual_value", "")
            av_str = f"{int(actual) if actual and float(actual)==int(float(actual)) else actual}" if actual not in (None,"") else "✓"
            stat_short = stat.replace("points","PTS").replace("rebounds","REB").replace("assists","AST").replace("_","+")
            out += f"""<div class="row">
              <div class="chk">✓</div>
              <div class="pi"><div class="pn">{name}</div>
                <div class="pl">{stat_short} · {direct} {line}</div></div>
              <div class="av">{av_str}</div>
            </div>"""
        return out

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{background:#080604;font-family:'Inter',sans-serif}}
.bg{{position:absolute;inset:0;
  background:
    radial-gradient(ellipse 70% 40% at 80% 0%,rgba(249,198,43,.14) 0%,transparent 60%),
    radial-gradient(ellipse 50% 50% at 10% 100%,rgba(255,100,20,.07) 0%,transparent 60%),
    repeating-linear-gradient(135deg,rgba(249,198,43,.03) 0,rgba(249,198,43,.03) 1px,transparent 1px,transparent 60px);
}}
.border-top{{position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#F9C62B,#FF9D42,#F9C62B)}}
.wrap{{position:relative;z-index:2;display:grid;grid-template-columns:{left_w}px 1fr;height:100%}}
/* LEFT */
.left{{display:flex;flex-direction:column;justify-content:center;padding:{pad}px {int(pad*.75)}px {pad}px {pad}px;border-right:1px solid rgba(249,198,43,.11)}}
.logo{{height:{logo_h}px;object-fit:contain;object-position:left;margin-bottom:{int(height*.03)}px;filter:brightness(1.1)}}
.logo-text{{height:{logo_h}px;font-family:'Bebas Neue',sans-serif;font-size:{logo_h}px;color:#F9C62B;margin-bottom:{int(height*.03)}px}}
.big{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.13)}px;line-height:1;color:#F9C62B;
  text-shadow:0 0 30px rgba(249,198,43,.8),0 0 70px rgba(249,198,43,.35)}}
.wl{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{int(height*.034)}px;
  letter-spacing:2px;text-transform:uppercase;color:#fff;margin-top:-4px}}
.wl span{{color:#F9C62B}}
.meta{{font-family:'Barlow Condensed',sans-serif;font-weight:500;font-size:{int(height*.014)}px;
  letter-spacing:4px;color:rgba(255,255,255,.32);margin-top:{int(height*.015)}px;text-transform:uppercase;line-height:1.9}}
.wr-box{{margin-top:{int(height*.025)}px;background:rgba(249,198,43,.08);border:1px solid rgba(249,198,43,.22);
  border-radius:{int(height*.011)}px;padding:{int(height*.016)}px {int(width*.02)}px}}
.wr-v{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.042)}px;color:#F9C62B;letter-spacing:2px}}
.wr-s{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.012)}px;
  letter-spacing:3px;color:rgba(255,255,255,.38);text-transform:uppercase}}
/* RIGHT */
.right{{display:flex;flex-direction:column;padding:{int(pad*.9)}px {pad}px {int(pad*.9)}px {int(pad*.75)}px}}
.sec-eye{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.013)}px;
  letter-spacing:5px;color:rgba(249,198,43,.6);text-transform:uppercase;margin-bottom:{int(height*.007)}px}}
.sec-title{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.052)}px;letter-spacing:2px;color:#fff;line-height:1;margin-bottom:{int(height*.025)}px}}
.sec-title span{{color:#F9C62B}}
.row{{display:flex;align-items:center;gap:{int(width*.015)}px;padding:{int(height*.015)}px 0;border-bottom:1px solid rgba(255,255,255,.055)}}
.row:last-child{{border-bottom:none}}
.chk{{width:{int(height*.034)}px;height:{int(height*.034)}px;border-radius:50%;
  background:rgba(249,198,43,.12);border:1.5px solid rgba(249,198,43,.38);
  display:flex;align-items:center;justify-content:center;font-size:{int(height*.016)}px;color:#F9C62B;flex-shrink:0}}
.pi{{flex:1;min-width:0}}
.pn{{font-family:'Inter',sans-serif;font-weight:700;font-size:{int(height*.019)}px;color:#fff;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pl{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.011)}px;color:rgba(255,255,255,.38);margin-top:2px;letter-spacing:.5px}}
.av{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.034)}px;color:#F9C62B;
  text-shadow:0 0 18px rgba(249,198,43,.5);flex-shrink:0;text-align:right;min-width:{int(width*.06)}px}}
.foot{{margin-top:auto;padding-top:{int(height*.016)}px;border-top:1px solid rgba(249,198,43,.1);
  display:flex;justify-content:space-between;align-items:center}}
.fl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.012)}px;
  letter-spacing:3px;color:rgba(255,255,255,.28);text-transform:uppercase}}
.fr{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.012)}px;
  letter-spacing:3px;color:rgba(249,198,43,.5);text-transform:uppercase}}
</style></head><body>
<div class="bg"></div><div class="border-top"></div>
<div class="wrap">
  <div class="left">
    {_LOGO_GOLD_TAG}
    <div class="big">{wins}</div>
    <div class="wl">WINS<br><span>&amp; COUNTING</span></div>
    <div class="meta">APR 26, 2026<br>ALL RESULTS ON FILE</div>
    <div class="wr-box">
      <div class="wr-v">{win_rate}%</div>
      <div class="wr-s">Win Rate · {wins}W / {losses}L</div>
    </div>
  </div>
  <div class="right">
    <div class="sec-eye">🏆 High-Edge Wins · Apr 26</div>
    <div class="sec-title">THE <span>RECEIPTS</span></div>
    {rows_html()}
    <div class="foot">
      <div class="fl">smartpickpro.ai · Quantum Matrix Engine™</div>
      <div class="fr">Follow for daily picks →</div>
    </div>
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# TEMPLATE 3 — "NEON GRID"  (crimson/purple, 3×3 pick cards)
# Best for: square, landscape
# ══════════════════════════════════════════════════════════════════════
def neon_grid(wins: int, losses: int, win_rate: float,
              picks: list[dict],
              width: int = 1080, height: int = 1080) -> str:
    pad  = int(width * 0.050)
    lw   = int(width * 0.35)

    def cards_html() -> str:
        out = ""
        for p in picks[:9]:
            name   = p.get("player_name","").split()[-1]  # last name only — fits cards
            stat   = p.get("stat_type","").replace("points","PTS").replace("rebounds","REB").replace("assists","AST").replace("_","+")
            line   = p.get("prop_line","")
            actual = p.get("actual_value","")
            av_str = f"{int(float(actual)) if actual not in (None,'') else ''}"
            out += f"""<div class="card">
              <div class="card-chk">✓</div>
              <div class="card-name">{name}</div>
              <div class="card-line">{stat[:10]} OVER {line}</div>
              <div class="card-result">{av_str}</div>
            </div>"""
        return out

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{background:#08060F;font-family:'Inter',sans-serif}}
.bg{{position:absolute;inset:0;
  background:
    radial-gradient(ellipse 60% 60% at 0% 50%,rgba(180,0,255,.11) 0%,transparent 60%),
    radial-gradient(ellipse 40% 40% at 100% 20%,rgba(255,60,80,.09) 0%,transparent 50%),
    radial-gradient(circle,rgba(140,0,255,.04) 1px,transparent 1px) 0 0/48px 48px;
}}
.stripe{{position:absolute;left:0;top:0;bottom:0;width:{lw}px;
  background:linear-gradient(160deg,rgba(200,0,255,.15) 0%,rgba(255,40,100,.07) 100%);
  border-right:1px solid rgba(200,0,255,.18)}}
.bar-top{{position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#C800FF,#FF2866,#C800FF)}}
.wrap{{position:relative;z-index:2;display:grid;grid-template-columns:{lw}px 1fr;height:100%}}
/* LEFT */
.left{{display:flex;flex-direction:column;justify-content:center;padding:{pad}px {int(pad*.8)}px {pad}px {pad}px}}
.logo{{height:{int(height*.05)}px;object-fit:contain;object-position:left;margin-bottom:{int(height*.03)}px;filter:brightness(1.2) saturate(0.7)}}
.logo-text{{height:{int(height*.05)}px;font-family:'Bebas Neue',sans-serif;font-size:{int(height*.05)}px;color:#C800FF;margin-bottom:{int(height*.03)}px}}
.date-tag{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.012)}px;letter-spacing:3px;
  color:rgba(200,0,255,.7);text-transform:uppercase;margin-bottom:{int(height*.022)}px}}
.hero-n{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.15)}px;line-height:.9;color:#FF2866;
  text-shadow:0 0 40px rgba(255,40,102,.9),0 0 100px rgba(255,40,102,.4)}}
.hero-s{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.046)}px;color:#C800FF;letter-spacing:3px;margin-top:6px;
  text-shadow:0 0 20px rgba(200,0,255,.7)}}
.hero-s2{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.017)}px;letter-spacing:3px;
  color:rgba(255,255,255,.55);text-transform:uppercase;margin-top:10px}}
.divv{{width:100%;height:1px;background:linear-gradient(90deg,rgba(200,0,255,.38),transparent);margin:{int(height*.025)}px 0}}
.stats{{display:flex;flex-direction:column;gap:{int(height*.012)}px}}
.si{{display:flex;justify-content:space-between;align-items:baseline;gap:12px}}
.sv{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.036)}px;color:#fff;letter-spacing:1px}}
.sv.g{{color:#00D559}}.sv.r{{color:#FF2866}}
.sl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.012)}px;letter-spacing:3px;color:rgba(255,255,255,.38);text-transform:uppercase}}
.brand-l{{margin-top:auto;font-family:'Barlow Condensed',sans-serif;font-weight:700;
  font-size:{int(height*.012)}px;letter-spacing:3px;color:rgba(200,0,255,.48);text-transform:uppercase}}
/* RIGHT */
.right{{padding:{pad}px {pad}px {pad}px {int(pad*.75)}px;display:flex;flex-direction:column;gap:{int(height*.008)}px}}
.rt-hdr{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.026)}px;letter-spacing:4px;
  color:rgba(255,255,255,.32);text-transform:uppercase;margin-bottom:{int(height*.01)}px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:{int(width*.009)}px;flex:1}}
.card{{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.065);border-radius:{int(height*.01)}px;
  padding:{int(height*.014)}px {int(width*.014)}px;display:flex;flex-direction:column;gap:4px;position:relative;overflow:hidden}}
.card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#C800FF,#FF2866)}}
.card-chk{{font-size:{int(height*.012)}px;color:#00D559;font-weight:700;letter-spacing:1px}}
.card-name{{font-family:'Inter',sans-serif;font-weight:700;font-size:{int(height*.017)}px;color:#fff;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.card-line{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.010)}px;color:rgba(255,255,255,.34);letter-spacing:.4px}}
.card-result{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.030)}px;color:#FF2866;letter-spacing:1px;margin-top:2px;
  text-shadow:0 0 15px rgba(255,40,102,.5)}}
.rt-foot{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.012)}px;
  letter-spacing:3px;color:rgba(255,255,255,.22);text-transform:uppercase;text-align:right}}
</style></head><body>
<div class="bg"></div><div class="stripe"></div><div class="bar-top"></div>
<div class="wrap">
  <div class="left">
    {_LOGO_TAG}
    <div class="date-tag">April 26, 2026</div>
    <div class="hero-n">{wins}</div>
    <div class="hero-s">WINS</div>
    <div class="hero-s2">Out of {wins+losses} settled</div>
    <div class="divv"></div>
    <div class="stats">
      <div class="si"><span class="sv g">{wins}</span><span class="sl">Wins</span></div>
      <div class="si"><span class="sv r">{losses}</span><span class="sl">Losses</span></div>
      <div class="si"><span class="sv">{win_rate}%</span><span class="sl">Win Rate</span></div>
    </div>
    <div class="brand-l">@smartpickproai</div>
  </div>
  <div class="right">
    <div class="rt-hdr">⚡ Top Wins — Actual Results</div>
    <div class="grid">{cards_html()}</div>
    <div class="rt-foot">smartpickpro.ai · All results on file</div>
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# TEMPLATE 4 — "ICE COMMAND"  (blue steel, full pick list)
# Best for: portrait (1080×1350)  ← Instagram best performing format
# ══════════════════════════════════════════════════════════════════════
def ice_command(wins: int, losses: int, win_rate: float,
                picks: list[dict],
                width: int = 1080, height: int = 1350) -> str:
    pad  = int(width * 0.074)
    logo_h = int(height * 0.042)

    def rows_html() -> str:
        out = ""
        for i, p in enumerate(picks[:8], 1):
            name   = p.get("player_name","")
            stat   = p.get("stat_type","").replace("points","PTS").replace("rebounds","REB").replace("assists","AST").replace("_","+")[:12]
            line   = p.get("prop_line","")
            direct = p.get("direction","OVER")
            actual = p.get("actual_value","")
            av_str = f"{int(float(actual)) if actual not in (None,'') else '✓'}"
            idx    = f"0{i}" if i < 10 else str(i)
            out += f"""<div class="row">
              <div class="idx">{idx}</div>
              <div class="info"><div class="pn">{name}</div>
                <div class="pl">{stat} &nbsp; {direct} {line}</div></div>
              <div class="rv">{av_str}</div>
            </div>"""
        return out

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{background:#050810;font-family:'Inter',sans-serif}}
.bg{{position:absolute;inset:0;
  background:
    radial-gradient(ellipse 80% 35% at 50% 0%,rgba(45,158,255,.13) 0%,transparent 55%),
    radial-gradient(ellipse 60% 30% at 50% 100%,rgba(0,213,89,.06) 0%,transparent 50%),
    radial-gradient(circle,rgba(45,158,255,.07) 1px,transparent 1px) 0 0/44px 44px;
}}
.bar{{position:absolute;left:0;right:0;height:3px;background:linear-gradient(90deg,#2D9EFF,#00D559,#2D9EFF)}}
.bar.t{{top:0}}.bar.b{{bottom:0}}
.inner{{position:relative;z-index:2;display:flex;flex-direction:column;padding:{pad}px;height:100%}}
/* header row */
.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:{int(height*.04)}px}}
.brand-row{{display:flex;align-items:center;gap:{int(width*.012)}px}}
.logo{{height:{logo_h}px;object-fit:contain;filter:brightness(1.1)}}
.logo-text{{font-family:'Bebas Neue',sans-serif;font-size:{logo_h}px;color:#2D9EFF}}
.brand-info{{display:flex;flex-direction:column}}
.bn{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:{int(height*.018)}px;letter-spacing:2px;color:#fff;text-transform:uppercase}}
.bs{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.010)}px;color:rgba(255,255,255,.38);letter-spacing:1px}}
.date-t{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.013)}px;color:rgba(45,158,255,.7);letter-spacing:2px}}
/* hero */
.hero{{text-align:center;margin-bottom:{int(height*.036)}px}}
.hero-eye{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.014)}px;
  letter-spacing:6px;color:rgba(45,158,255,.7);text-transform:uppercase;margin-bottom:6px}}
.hero-rec{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.115)}px;line-height:1;color:#2D9EFF;
  text-shadow:0 0 40px rgba(45,158,255,.8),0 0 100px rgba(45,158,255,.3)}}
.hero-rec .d{{color:rgba(255,255,255,.28)}}
.hero-rec .l{{color:#FF4757}}
.hero-tag{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{int(height*.040)}px;
  letter-spacing:6px;text-transform:uppercase;color:#fff;margin-top:4px}}
.hero-tag span{{color:#00D559}}
.stats-row{{display:flex;justify-content:center;gap:{int(width*.033)}px;margin-top:{int(height*.018)}px}}
.sb{{text-align:center;padding:{int(height*.013)}px {int(width*.024)}px;
  border:1px solid rgba(45,158,255,.2);border-radius:{int(height*.010)}px;background:rgba(45,158,255,.04)}}
.sbv{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.036)}px;color:#2D9EFF;letter-spacing:1px}}
.sbv.g{{color:#00D559}}.sbv.r{{color:#FF4757}}
.sbl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.011)}px;
  letter-spacing:3px;color:rgba(255,255,255,.38);text-transform:uppercase;margin-top:2px}}
/* picks */
.picks-lbl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.013)}px;
  letter-spacing:5px;color:rgba(45,158,255,.6);text-transform:uppercase;margin-bottom:{int(height*.013)}px}}
.row{{display:flex;align-items:center;gap:{int(width*.016)}px;
  padding:{int(height*.012)}px 0;border-bottom:1px solid rgba(255,255,255,.05)}}
.row:last-child{{border-bottom:none}}
.idx{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.012)}px;color:rgba(45,158,255,.4);width:24px;flex-shrink:0}}
.info{{flex:1;min-width:0}}
.pn{{font-family:'Inter',sans-serif;font-weight:700;font-size:{int(height*.017)}px;color:#fff}}
.pl{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.010)}px;color:rgba(255,255,255,.34);margin-top:2px;letter-spacing:.5px}}
.rv{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.030)}px;color:#2D9EFF;
  text-shadow:0 0 16px rgba(45,158,255,.6);flex-shrink:0}}
/* footer */
.foot{{margin-top:auto;display:flex;justify-content:space-between;align-items:center;
  padding-top:{int(height*.016)}px;border-top:1px solid rgba(45,158,255,.1)}}
.fl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.013)}px;
  letter-spacing:3px;color:rgba(255,255,255,.28);text-transform:uppercase}}
.fr{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.013)}px;
  letter-spacing:3px;color:rgba(45,158,255,.5);text-transform:uppercase}}
</style></head><body>
<div class="bg"></div><div class="bar t"></div><div class="bar b"></div>
<div class="inner">
  <div class="hdr">
    <div class="brand-row">
      <div class="logo-wrap">{_LOGO_TAG}</div>
      <div class="brand-info">
        <div class="bn">SmartPickPro</div>
        <div class="bs">Quantum Matrix Engine™ 5.6</div>
      </div>
    </div>
    <div class="date-t">APR 26 · 2026</div>
  </div>
  <div class="hero">
    <div class="hero-eye">Yesterday's Final Results</div>
    <div class="hero-rec"><span>{wins}</span><span class="d"> – </span><span class="l">{losses}</span></div>
    <div class="hero-tag"><span>{win_rate}%</span> Win Rate</div>
    <div class="stats-row">
      <div class="sb"><div class="sbv g">{wins}</div><div class="sbl">Wins</div></div>
      <div class="sb"><div class="sbv r">{losses}</div><div class="sbl">Losses</div></div>
      <div class="sb"><div class="sbv">{win_rate}%</div><div class="sbl">Win Rate</div></div>
      <div class="sb"><div class="sbv">{wins+losses}</div><div class="sbl">Settled</div></div>
    </div>
  </div>
  <div class="picks-lbl">⚡ Top Wins — Actual Scores</div>
  {rows_html()}
  <div class="foot">
    <div class="fl">All results documented &amp; on file</div>
    <div class="fr">@smartpickproai</div>
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# TEMPLATE 5 — "VOLT MINIMAL"  (electric green, big number)
# Best for: square, story (1080×1920), Twitter landscape
# ══════════════════════════════════════════════════════════════════════
def volt_minimal(wins: int, losses: int, win_rate: float,
                 width: int = 1080, height: int = 1080) -> str:
    pad  = int(width * 0.074)
    big  = int(min(width, height) * 0.245)
    logo_h = int(height * 0.050)

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{background:#030A05;font-family:'Inter',sans-serif}}
.bg{{position:absolute;inset:0;
  background:
    radial-gradient(ellipse 50% 50% at 50% 50%,rgba(0,255,90,.09) 0%,transparent 65%),
    repeating-linear-gradient(0deg,rgba(0,255,90,.022) 0,rgba(0,255,90,.022) 1px,transparent 1px,transparent 80px),
    repeating-linear-gradient(90deg,rgba(0,255,90,.022) 0,rgba(0,255,90,.022) 1px,transparent 1px,transparent 80px);
}}
.corner{{position:absolute;width:{int(width*.074)}px;height:{int(height*.074)}px;border-color:#00FF5A;border-style:solid}}
.tl{{top:{int(height*.028)}px;left:{int(width*.028)}px;border-width:3px 0 0 3px}}
.tr{{top:{int(height*.028)}px;right:{int(width*.028)}px;border-width:3px 3px 0 0}}
.bl{{bottom:{int(height*.028)}px;left:{int(width*.028)}px;border-width:0 0 3px 3px}}
.br{{bottom:{int(height*.028)}px;right:{int(width*.028)}px;border-width:0 3px 3px 0}}
.inner{{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;
  justify-content:space-between;height:100%;padding:{pad}px}}
.top-row{{display:flex;justify-content:space-between;align-items:center;width:100%}}
.logo{{height:{logo_h}px;object-fit:contain;filter:brightness(1.2) saturate(0.5) sepia(1) hue-rotate(90deg) saturate(2)}}
.logo-text{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(logo_h*.7)}px;
  letter-spacing:5px;color:rgba(0,255,90,.5);text-transform:uppercase}}
.date-t{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.013)}px;color:rgba(255,255,255,.28);letter-spacing:2px}}
.hero{{text-align:center;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}}
.big{{font-family:'Bebas Neue',sans-serif;font-size:{big}px;line-height:.85;color:#00FF5A;
  text-shadow:0 0 60px rgba(0,255,90,1),0 0 120px rgba(0,255,90,.6),0 0 240px rgba(0,255,90,.2)}}
.wl{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.067)}px;letter-spacing:10px;color:rgba(255,255,255,.9);margin-top:10px}}
.wl span{{color:#00FF5A}}
.tagline{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.017)}px;
  letter-spacing:6px;color:rgba(255,255,255,.28);text-transform:uppercase;margin-top:{int(height*.018)}px}}
.bot-bar{{width:100%;display:flex;justify-content:space-around;
  padding:{int(height*.025)}px 0;border-top:1px solid rgba(0,255,90,.12)}}
.stat{{text-align:center}}
.sv{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.040)}px;color:#00FF5A;letter-spacing:2px}}
.sv.r{{color:#FF4757}}.sv.w{{color:#fff}}
.sl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{int(height*.012)}px;
  letter-spacing:4px;color:rgba(255,255,255,.32);text-transform:uppercase;margin-top:2px}}
.dv{{width:1px;background:rgba(0,255,90,.14);align-self:stretch}}
</style></head><body>
<div class="bg"></div>
<div class="corner tl"></div><div class="corner tr"></div>
<div class="corner bl"></div><div class="corner br"></div>
<div class="inner">
  <div class="top-row">
    <div class="logo-text">SmartPickPro</div>
    <div class="date-t">APR 26 · 2026</div>
  </div>
  <div class="hero">
    <div class="big">{wins}</div>
    <div class="wl"><span>W</span>INS &amp; COUNTING</div>
    <div class="tagline">All results documented · zero hidden losses</div>
  </div>
  <div class="bot-bar">
    <div class="stat"><div class="sv">{wins}</div><div class="sl">Wins</div></div>
    <div class="dv"></div>
    <div class="stat"><div class="sv r">{losses}</div><div class="sl">Losses</div></div>
    <div class="dv"></div>
    <div class="stat"><div class="sv w">{win_rate}%</div><div class="sl">Win Rate</div></div>
    <div class="dv"></div>
    <div class="stat"><div class="sv">{wins+losses}</div><div class="sl">Settled</div></div>
  </div>
</div>
</body></html>"""



# ══════════════════════════════════════════════════════════════════════
# TEMPLATE 6 — "REELS FIRE"  (cinematic dark-red, 9:16)
# Best for: Instagram Reels cover, Facebook Story
# ══════════════════════════════════════════════════════════════════════
def reels_fire(wins: int, losses: int, win_rate: float,
               picks: list[dict] | None = None,
               width: int = 1080, height: int = 1920) -> str:
    picks = picks or []
    pad   = max(72, int(width * 0.067))
    lh    = max(56, int(height * 0.034))    # logo height
    big   = int(height * 0.17)              # record font
    dash  = int(big  * 0.60)
    eyef  = int(height * 0.016)
    tagf  = int(height * 0.028)
    pf    = int(height * 0.022)             # pick row font
    ctaf  = int(height * 0.026)

    picks_html = ""
    for i, p in enumerate(picks[:7]):
        name  = p.get("player_name", "")
        st    = p.get("stat_type",   "").replace("_", "+").upper()
        line  = p.get("prop_line",   "")
        act   = p.get("actual_value","")
        res   = p.get("result","WIN").upper()
        color = "#FF6B35" if res == "WIN" else "#FF4757"
        badge = "✓ WIN" if res == "WIN" else "✗ LOSS"
        delta = ""
        if act and line:
            try:
                diff = float(act) - float(line)
                delta = f"+{diff:.1f}" if diff >= 0 else f"{diff:.1f}"
            except Exception:
                pass
        picks_html += f"""
        <div class="pick-row" style="animation-delay:{i*0.06:.2f}s">
          <div class="pick-left">
            <div class="pname">{name}</div>
            <div class="pstat">{st} &nbsp;·&nbsp; LINE {line}</div>
          </div>
          <div class="pick-right">
            <div class="actual" style="color:{color}">{act}{f" ({delta})" if delta else ""}</div>
            <div class="badge" style="color:{color}">{badge}</div>
          </div>
        </div>"""

    logo_tag = f'<img class="logo" src="{_LOGO}" alt="SmartPickPro">' if _LOGO else '<span class="logo-txt">SmartPickPro</span>'

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{
  background:#0A0608;
  font-family:'Inter',sans-serif;
  position:relative;
}}
/* layered background */
.bg-layer{{
  position:absolute;inset:0;
  background:
    radial-gradient(ellipse 80% 40% at 50% 0%,   rgba(200,30,30,0.28)  0%, transparent 55%),
    radial-gradient(ellipse 60% 30% at 20% 80%,   rgba(255,107,53,0.12) 0%, transparent 50%),
    radial-gradient(ellipse 50% 25% at 80% 100%,  rgba(200,30,30,0.15)  0%, transparent 50%),
    radial-gradient(circle, rgba(255,60,30,0.04) 1px, transparent 1px) 0 0/48px 48px;
}}
/* animated flame pulse */
@keyframes pulse{{0%,100%{{opacity:.7}}50%{{opacity:1}}}}
.flame{{position:absolute;top:0;left:0;right:0;height:{int(height*.38)}px;
  background:radial-gradient(ellipse 70% 60% at 50% -10%,rgba(220,50,20,0.45) 0%,transparent 65%);
  animation:pulse 3s ease-in-out infinite;pointer-events:none}}
/* top accent bar */
.bar-top{{position:absolute;top:0;left:0;right:0;height:6px;
  background:linear-gradient(90deg,#C81E1E,#FF6B35,#FF4757,#FF6B35,#C81E1E)}}
/* bottom accent */
.bar-bot{{position:absolute;bottom:0;left:0;right:0;height:6px;
  background:linear-gradient(90deg,#C81E1E,#FF6B35,#C81E1E)}}
/* side glow lines */
.glow-l{{position:absolute;left:0;top:0;bottom:0;width:3px;
  background:linear-gradient(to bottom,transparent,rgba(255,107,53,.6),transparent)}}
.glow-r{{position:absolute;right:0;top:0;bottom:0;width:3px;
  background:linear-gradient(to bottom,transparent,rgba(255,107,53,.6),transparent)}}
/* inner layout */
.inner{{
  position:relative;z-index:2;
  display:flex;flex-direction:column;
  height:100%;padding:{pad}px {pad}px {int(pad*.85)}px;
}}
/* header */
.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:{int(height*.022)}px}}
.logo{{height:{lh}px;object-fit:contain;filter:drop-shadow(0 0 8px rgba(255,107,53,.5))}}
.logo-txt{{font-family:'Bebas Neue',sans-serif;font-size:{lh}px;color:#FF6B35}}
.date-tag{{
  font-family:'JetBrains Mono',monospace;font-size:{int(height*.013)}px;
  color:rgba(255,107,53,.75);letter-spacing:2px;text-transform:uppercase
}}
/* eyebrow */
.eyebrow{{
  font-family:'Barlow Condensed',sans-serif;font-weight:700;
  font-size:{eyef}px;letter-spacing:8px;color:rgba(255,107,53,.65);
  text-transform:uppercase;text-align:center;margin-bottom:{int(height*.006)}px
}}
/* hero record */
.record{{
  display:flex;align-items:baseline;justify-content:center;
  gap:{int(width*.015)}px;margin-bottom:{int(height*.008)}px;
  line-height:1
}}
.rec-w{{
  font-family:'Bebas Neue',sans-serif;font-size:{big}px;color:#FF6B35;
  text-shadow:0 0 40px rgba(255,107,53,.9),0 0 100px rgba(255,107,53,.4),
              0 4px 24px rgba(0,0,0,.8)
}}
.rec-dash{{font-family:'Bebas Neue',sans-serif;font-size:{dash}px;color:rgba(255,255,255,.18)}}
.rec-l{{
  font-family:'Bebas Neue',sans-serif;font-size:{big}px;color:#FF4757;
  text-shadow:0 0 30px rgba(255,71,87,.7),0 4px 20px rgba(0,0,0,.8)
}}
.tagline{{
  text-align:center;
  font-family:'Barlow Condensed',sans-serif;font-weight:900;
  font-size:{tagf}px;letter-spacing:5px;color:#fff;
  text-transform:uppercase;margin-bottom:{int(height*.012)}px
}}
.wr-pill{{
  display:flex;align-items:center;justify-content:center;gap:{int(width*.02)}px;
  margin-bottom:{int(height*.032)}px
}}
.wr-chip{{
  background:rgba(255,107,53,.15);
  border:1px solid rgba(255,107,53,.4);
  border-radius:999px;
  padding:{int(height*.008)}px {int(width*.04)}px;
  font-family:'Barlow Condensed',sans-serif;font-weight:800;
  font-size:{int(height*.028)}px;color:#FF6B35;letter-spacing:2px
}}
/* divider */
.divider{{height:1px;background:linear-gradient(90deg,transparent,rgba(255,107,53,.4),transparent);margin-bottom:{int(height*.024)}px}}
/* picks section */
.picks-label{{
  font-family:'Barlow Condensed',sans-serif;font-weight:700;
  font-size:{int(height*.014)}px;letter-spacing:5px;color:rgba(255,255,255,.35);
  text-transform:uppercase;margin-bottom:{int(height*.014)}px
}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}}
.pick-row{{
  display:flex;justify-content:space-between;align-items:center;
  padding:{int(height*.013)}px {int(width*.024)}px;
  background:rgba(255,255,255,.04);
  border:1px solid rgba(255,107,53,.12);
  border-radius:{int(width*.016)}px;
  margin-bottom:{int(height*.010)}px;
  animation:fadeUp .4s ease both;
}}
.pick-left{{flex:1;min-width:0}}
.pname{{
  font-family:'Barlow Condensed',sans-serif;font-weight:800;
  font-size:{pf}px;color:#fff;letter-spacing:.5px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis
}}
.pstat{{
  font-family:'JetBrains Mono',monospace;font-size:{int(pf*.6)}px;
  color:rgba(255,255,255,.35);letter-spacing:1px;margin-top:2px
}}
.pick-right{{text-align:right;flex-shrink:0;margin-left:{int(width*.02)}px}}
.actual{{font-family:'Bebas Neue',sans-serif;font-size:{int(pf*1.15)}px;letter-spacing:1px}}
.badge{{font-family:'JetBrains Mono',monospace;font-size:{int(pf*.55)}px;letter-spacing:2px;margin-top:1px}}
/* spacer */
.spacer{{flex:1}}
/* CTA */
.cta-block{{text-align:center}}
.cta-line{{
  font-family:'Barlow Condensed',sans-serif;font-weight:700;
  font-size:{ctaf}px;letter-spacing:5px;color:rgba(255,255,255,.45);
  text-transform:uppercase
}}
.cta-arrow{{
  font-size:{int(ctaf*1.6)}px;color:rgba(255,107,53,.55);margin-top:{int(height*.006)}px;
  animation:pulse 1.5s ease-in-out infinite
}}
.brand-url{{
  font-family:'JetBrains Mono',monospace;font-size:{int(height*.014)}px;
  color:rgba(255,107,53,.5);letter-spacing:2px;margin-top:{int(height*.010)}px
}}
</style></head><body>
<div class="bg-layer"></div>
<div class="flame"></div>
<div class="bar-top"></div>
<div class="bar-bot"></div>
<div class="glow-l"></div>
<div class="glow-r"></div>
<div class="inner">
  <div class="hdr">
    {logo_tag}
    <div class="date-tag">APR 26 · 2026</div>
  </div>
  <div class="eyebrow">Last Night's Results</div>
  <div class="record">
    <div class="rec-w">{wins}</div>
    <div class="rec-dash">-</div>
    <div class="rec-l">{losses}</div>
  </div>
  <div class="tagline">Documented. On the record.</div>
  <div class="wr-pill">
    <div class="wr-chip">{win_rate}% WIN RATE</div>
    <div class="wr-chip">{wins+losses} SETTLED</div>
  </div>
  <div class="divider"></div>
  {"<div class='picks-label'>Top Hits</div>" if picks_html else ""}
  {picks_html}
  <div class="spacer"></div>
  <div class="cta-block">
    <div class="cta-line">Swipe for full receipts</div>
    <div class="cta-arrow">↓</div>
    <div class="brand-url">smartpickpro.ai</div>
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# TEMPLATE 7 — "REELS MINIMAL"  (electric-green volt, 9:16)
# Best for: Instagram Reels, TikTok cover, Facebook Story
# ══════════════════════════════════════════════════════════════════════
def reels_minimal(wins: int, losses: int, win_rate: float,
                  width: int = 1080, height: int = 1920) -> str:
    pad    = max(80, int(width  * 0.074))
    lh     = max(52, int(height * 0.032))
    big    = int(height * 0.225)
    sublf  = int(height * 0.024)
    statf  = int(height * 0.030)
    lblf   = int(height * 0.014)
    ctaf   = int(height * 0.022)

    logo_tag = f'<img class="logo" src="{_LOGO}" alt="SmartPickPro">' if _LOGO else '<span class="logo-txt">SmartPickPro</span>'

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{
  background:#020E06;
  font-family:'Inter',sans-serif;
  position:relative;
}}
/* grid bg */
.grid{{
  position:absolute;inset:0;
  background:
    linear-gradient(rgba(0,255,90,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,255,90,.04) 1px, transparent 1px);
  background-size:60px 60px;
}}
/* radial glow */
.glow{{
  position:absolute;inset:0;
  background:
    radial-gradient(ellipse 70% 55% at 50% 52%, rgba(0,255,90,.14) 0%, transparent 65%),
    radial-gradient(ellipse 40% 20% at 50% 100%, rgba(0,255,90,.10) 0%, transparent 55%);
}}
/* corner accents */
.ca{{position:absolute;width:{int(width*.10)}px;height:{int(width*.10)}px}}
.ca.tl{{top:{int(pad*.5)}px;left:{int(pad*.5)}px;border-top:3px solid rgba(0,255,90,.5);border-left:3px solid rgba(0,255,90,.5)}}
.ca.tr{{top:{int(pad*.5)}px;right:{int(pad*.5)}px;border-top:3px solid rgba(0,255,90,.5);border-right:3px solid rgba(0,255,90,.5)}}
.ca.bl{{bottom:{int(pad*.5)}px;left:{int(pad*.5)}px;border-bottom:3px solid rgba(0,255,90,.5);border-left:3px solid rgba(0,255,90,.5)}}
.ca.br{{bottom:{int(pad*.5)}px;right:{int(pad*.5)}px;border-bottom:3px solid rgba(0,255,90,.5);border-right:3px solid rgba(0,255,90,.5)}}
/* bars */
.bar{{position:absolute;left:0;right:0;height:5px;
  background:linear-gradient(90deg,#00FF5A,#00D559,#00FF5A)}}
.bar.t{{top:0}}.bar.b{{bottom:0}}
/* inner */
.inner{{
  position:relative;z-index:2;height:100%;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:{pad}px;text-align:center;gap:{int(height*.018)}px
}}
/* logo */
.logo-wrap{{margin-bottom:{int(height*.01)}px}}
.logo{{height:{lh}px;object-fit:contain;filter:drop-shadow(0 0 10px rgba(0,255,90,.6))}}
.logo-txt{{font-family:'Bebas Neue',sans-serif;font-size:{lh}px;color:#00FF5A}}
/* date */
.date-lbl{{
  font-family:'JetBrains Mono',monospace;font-size:{int(height*.013)}px;
  color:rgba(0,255,90,.5);letter-spacing:3px;text-transform:uppercase
}}
/* divider thin */
.div-line{{width:{int(width*.3)}px;height:1px;background:rgba(0,255,90,.3)}}
/* main number */
.big-num{{
  font-family:'Bebas Neue',sans-serif;font-size:{big}px;line-height:1;
  color:#00FF5A;
  text-shadow:0 0 60px rgba(0,255,90,1),0 0 120px rgba(0,255,90,.5),
              0 0 200px rgba(0,255,90,.2);
  letter-spacing:-4px
}}
.big-label{{
  font-family:'Barlow Condensed',sans-serif;font-weight:900;
  font-size:{sublf}px;letter-spacing:8px;color:#fff;text-transform:uppercase;
  margin-top:-{int(height*.008)}px
}}
/* stats row */
.stats-row{{
  display:flex;gap:{int(width*.06)}px;margin-top:{int(height*.01)}px
}}
.stat-box{{text-align:center}}
.sv{{
  font-family:'Bebas Neue',sans-serif;font-size:{statf}px;letter-spacing:1px
}}
.sl{{
  font-family:'Barlow Condensed',sans-serif;font-weight:700;
  font-size:{lblf}px;letter-spacing:4px;color:rgba(255,255,255,.35);
  text-transform:uppercase;margin-top:2px
}}
.div-v{{width:1px;background:rgba(0,255,90,.2);align-self:stretch}}
/* brand */
.brand-url{{
  font-family:'JetBrains Mono',monospace;font-size:{int(height*.014)}px;
  color:rgba(0,255,90,.4);letter-spacing:3px
}}
/* cta */
.cta{{
  font-family:'Barlow Condensed',sans-serif;font-weight:700;
  font-size:{ctaf}px;letter-spacing:5px;color:rgba(255,255,255,.38);
  text-transform:uppercase
}}
</style></head><body>
<div class="grid"></div>
<div class="glow"></div>
<div class="ca tl"></div><div class="ca tr"></div>
<div class="ca bl"></div><div class="ca br"></div>
<div class="bar t"></div><div class="bar b"></div>
<div class="inner">
  <div class="logo-wrap">{logo_tag}</div>
  <div class="date-lbl">APR 26 · 2026</div>
  <div class="div-line"></div>
  <div class="big-num">{wins}</div>
  <div class="big-label">Wins Last Night</div>
  <div class="stats-row">
    <div class="stat-box"><div class="sv" style="color:#FF4757">{losses}</div><div class="sl">Losses</div></div>
    <div class="div-v"></div>
    <div class="stat-box"><div class="sv" style="color:#00FF5A">{win_rate}%</div><div class="sl">Win Rate</div></div>
    <div class="div-v"></div>
    <div class="stat-box"><div class="sv" style="color:rgba(255,255,255,.7)">{wins+losses}</div><div class="sl">Settled</div></div>
  </div>
  <div class="div-line"></div>
  <div class="brand-url">smartpickpro.ai</div>
  <div class="cta">All Receipts Documented</div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════
# CAROUSEL SYSTEM — 3 slide types + render_carousel() helper
# Each slide is a self-contained HTML page rendered to 1080×1080 PNG.
#
# Slide order:
#   [0]  carousel_cover      — hook: record + date + "swipe →"
#   [1…N] carousel_pick_slide — one slide per pick (player details)
#   [N+1] carousel_cta       — closing brand / follow CTA
# ══════════════════════════════════════════════════════════════════════

def _carousel_base_css(width: int, height: int, bg: str, accent: str, accent2: str) -> str:
    pad   = max(64, int(width * 0.059))
    return f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{width}px;height:{height}px;overflow:hidden;background:{bg};font-family:'Inter',sans-serif}}
.bar{{position:absolute;left:0;right:0;height:5px;background:linear-gradient(90deg,{accent},{accent2},{accent})}}
.bar.t{{top:0}}.bar.b{{bottom:0}}
.inner{{position:relative;z-index:2;display:flex;flex-direction:column;padding:{pad}px;height:100%}}
.logo{{height:{max(44,int(height*.045))}px;object-fit:contain;filter:drop-shadow(0 0 6px rgba(255,255,255,.25))}}
.logo-txt{{font-family:'Bebas Neue',sans-serif;font-size:{max(44,int(height*.045))}px;color:{accent}}}
"""


# ── Slide 1: Cover ────────────────────────────────────────────────────
def carousel_cover(wins: int, losses: int, win_rate: float,
                   date_str: str = "APR 26 · 2026",
                   width: int = 1080, height: int = 1080) -> str:
    pad   = max(64, int(width * 0.059))
    bigf  = int(height * 0.19)
    dashf = int(bigf  * 0.62)
    eyef  = int(height * 0.016)
    tagf  = int(height * 0.034)
    pillf = int(height * 0.024)
    ctaf  = int(height * 0.022)
    lh    = max(44, int(height * 0.052))

    logo_tag = f'<img class="logo" src="{_LOGO}" alt="SmartPickPro">' if _LOGO else '<span class="logo-txt">SmartPickPro</span>'

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
{_carousel_base_css(width, height, '#040810', '#F7C948', '#FFD966')}
body{{
  background:
    radial-gradient(ellipse 70% 50% at 50% 30%, rgba(247,201,72,.10) 0%, transparent 60%),
    radial-gradient(ellipse 50% 35% at 50% 90%, rgba(247,201,72,.06) 0%, transparent 55%),
    radial-gradient(circle, rgba(247,201,72,.04) 1px, transparent 1px) 0 0/54px 54px,
    #040810;
}}
.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:{int(height*.03)}px}}
.date-tag{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.013)}px;color:rgba(247,201,72,.6);letter-spacing:2px}}
.eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{eyef}px;letter-spacing:8px;
  color:rgba(247,201,72,.55);text-transform:uppercase;text-align:center;margin-bottom:{int(height*.005)}px}}
.record{{display:flex;align-items:baseline;justify-content:center;gap:{int(width*.018)}px;line-height:1;margin-bottom:{int(height*.008)}px}}
.rw{{font-family:'Bebas Neue',sans-serif;font-size:{bigf}px;color:#F7C948;
  text-shadow:0 0 40px rgba(247,201,72,.8),0 0 80px rgba(247,201,72,.3),0 4px 24px rgba(0,0,0,.9)}}
.rd{{font-family:'Bebas Neue',sans-serif;font-size:{dashf}px;color:rgba(255,255,255,.18)}}
.rl{{font-family:'Bebas Neue',sans-serif;font-size:{bigf}px;color:#FF6B35;
  text-shadow:0 0 30px rgba(255,107,53,.7),0 4px 20px rgba(0,0,0,.8)}}
.tagline{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{tagf}px;
  letter-spacing:5px;color:#fff;text-transform:uppercase;text-align:center;margin-bottom:{int(height*.028)}px}}
.pills{{display:flex;justify-content:center;gap:{int(width*.016)}px;margin-bottom:{int(height*.032)}px}}
.pill{{background:rgba(247,201,72,.12);border:1px solid rgba(247,201,72,.35);border-radius:999px;
  padding:{int(height*.009)}px {int(width*.036)}px;
  font-family:'Barlow Condensed',sans-serif;font-weight:800;
  font-size:{pillf}px;color:#F7C948;letter-spacing:2px}}
.spacer{{flex:1}}
.cta-row{{display:flex;justify-content:space-between;align-items:center}}
.cta-txt{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{ctaf}px;
  letter-spacing:5px;color:rgba(255,255,255,.38);text-transform:uppercase}}
.cta-arrow{{font-family:'Bebas Neue',sans-serif;font-size:{int(ctaf*1.8)}px;color:rgba(247,201,72,.55);letter-spacing:2px}}
.slide-num{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.012)}px;
  color:rgba(255,255,255,.2);letter-spacing:2px}}
</style></head><body>
<div class="bar t"></div>
<div class="bar b"></div>
<div class="inner">
  <div class="hdr">
    {logo_tag}
    <div class="date-tag">{date_str}</div>
  </div>
  <div class="eyebrow">Last Night's Results</div>
  <div class="record">
    <div class="rw">{wins}</div><div class="rd">-</div><div class="rl">{losses}</div>
  </div>
  <div class="tagline">Documented. On the record.</div>
  <div class="pills">
    <div class="pill">{win_rate}% WIN RATE</div>
    <div class="pill">{wins + losses} SETTLED</div>
  </div>
  <div class="spacer"></div>
  <div class="cta-row">
    <div class="cta-txt">Swipe for receipts</div>
    <div class="cta-arrow">→</div>
    <div class="slide-num">1 / ?</div>
  </div>
</div>
</body></html>"""


# ── Slide N: Per-pick receipt ─────────────────────────────────────────
def carousel_pick_slide(pick: dict, slide_num: int, total_slides: int,
                        width: int = 1080, height: int = 1080) -> str:
    pad    = max(64, int(width  * 0.059))
    namef  = int(height * 0.072)
    statf  = int(height * 0.022)
    linef  = int(height * 0.018)
    actf   = int(height * 0.115)
    lblf   = int(height * 0.017)
    ctaf   = int(height * 0.020)
    lh     = max(40, int(height * 0.046))

    name   = pick.get("player_name",  "Player")
    st     = pick.get("stat_type",    "").replace("_", " ").upper()
    line   = pick.get("prop_line",    "")
    act    = pick.get("actual_value", "")
    res    = pick.get("result",       "WIN").upper()
    dirn   = pick.get("direction",    "OVER").upper()
    plat   = pick.get("platform",     "")

    is_win  = res == "WIN"
    accent  = "#00D559" if is_win else "#FF4757"
    accent2 = "#00FF5A" if is_win else "#FF6B73"
    badge   = "✓  WIN" if is_win else "✗  LOSS"

    delta = ""
    if act != "" and line != "":
        try:
            d = float(act) - float(line)
            delta = f"+{d:.1f}" if d >= 0 else f"{d:.1f}"
        except Exception:
            pass

    logo_tag = f'<img class="logo" src="{_LOGO}" alt="SmartPickPro">' if _LOGO else '<span class="logo-txt">SmartPickPro</span>'

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
{_carousel_base_css(width, height, '#04090F', accent, accent2)}
body{{
  background:
    radial-gradient(ellipse 80% 55% at 50% 15%, {accent}1A 0%, transparent 55%),
    radial-gradient(circle, {accent}08 1px, transparent 1px) 0 0/52px 52px,
    #04090F;
}}
.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:{int(height*.04)}px}}
.slide-tag{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.013)}px;
  color:rgba(255,255,255,.22);letter-spacing:2px}}
.pick-badge{{
  font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{int(height*.017)}px;
  letter-spacing:4px;color:{accent};text-transform:uppercase;
  padding:{int(height*.006)}px {int(width*.020)}px;
  background:{accent}1A;border:1px solid {accent}55;border-radius:999px
}}
/* player name */
.player{{
  font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{namef}px;
  line-height:1;color:#fff;letter-spacing:1px;
  text-shadow:0 2px 20px rgba(0,0,0,.8);
  margin-bottom:{int(height*.012)}px;
  word-break:break-word
}}
.stat-line{{
  font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{statf}px;
  color:rgba(255,255,255,.55);letter-spacing:3px;text-transform:uppercase;
  margin-bottom:{int(height*.008)}px
}}
.prop-row{{
  display:flex;align-items:center;gap:{int(width*.024)}px;
  margin-bottom:{int(height*.032)}px
}}
.prop-chip{{
  font-family:'JetBrains Mono',monospace;font-size:{linef}px;
  color:rgba(255,255,255,.4);letter-spacing:1px;
  padding:{int(height*.006)}px {int(width*.020)}px;
  background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:8px
}}
.dir-chip{{
  font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:{int(linef*1.1)}px;
  color:{accent};letter-spacing:3px;
  padding:{int(height*.006)}px {int(width*.020)}px;
  background:{accent}15;border:1px solid {accent}40;border-radius:8px
}}
/* big actual number */
.act-block{{text-align:center;margin-bottom:{int(height*.032)}px}}
.act-val{{
  font-family:'Bebas Neue',sans-serif;font-size:{actf}px;line-height:1;
  color:{accent};
  text-shadow:0 0 50px {accent}CC,0 0 100px {accent}66,0 4px 30px rgba(0,0,0,.9);
  letter-spacing:-2px
}}
.act-lbl{{
  font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{lblf}px;
  letter-spacing:5px;color:rgba(255,255,255,.35);text-transform:uppercase;margin-top:4px
}}
.act-delta{{
  font-family:'JetBrains Mono',monospace;font-size:{int(lblf*.9)}px;
  color:{accent}AA;letter-spacing:2px;margin-top:2px
}}
/* result banner */
.result-banner{{
  display:flex;align-items:center;justify-content:center;
  padding:{int(height*.014)}px;
  background:{accent}18;
  border:2px solid {accent}50;
  border-radius:{int(width*.016)}px;
  font-family:'Bebas Neue',sans-serif;font-size:{int(height*.044)}px;
  letter-spacing:6px;color:{accent};
  text-shadow:0 0 20px {accent}AA
}}
.spacer{{flex:1}}
.nav-row{{display:flex;justify-content:space-between;align-items:center}}
.nav-num{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.013)}px;color:rgba(255,255,255,.22);letter-spacing:2px}}
.nav-arr{{font-family:'Bebas Neue',sans-serif;font-size:{int(height*.026)}px;color:rgba(255,255,255,.18);letter-spacing:2px}}
</style></head><body>
<div class="bar t"></div>
<div class="bar b"></div>
<div class="inner">
  <div class="hdr">
    {logo_tag}
    <div class="pick-badge">{badge}</div>
    <div class="slide-tag">{slide_num} / {total_slides}</div>
  </div>
  <div class="player">{name}</div>
  <div class="stat-line">{st}</div>
  <div class="prop-row">
    <div class="prop-chip">LINE  {line}</div>
    <div class="dir-chip">{dirn}</div>
    {f'<div class="prop-chip">{plat}</div>' if plat else ''}
  </div>
  <div class="act-block">
    <div class="act-val">{act}</div>
    <div class="act-lbl">Actual Result</div>
    {f'<div class="act-delta">({delta} vs line)</div>' if delta else ''}
  </div>
  <div class="result-banner">{badge}</div>
  <div class="spacer"></div>
  <div class="nav-row">
    <div class="nav-arr">←</div>
    <div class="nav-num">{slide_num} of {total_slides}</div>
    <div class="nav-arr">→</div>
  </div>
</div>
</body></html>"""


# ── Final slide: CTA ─────────────────────────────────────────────────
def carousel_cta(wins: int, losses: int, win_rate: float,
                 slide_num: int = 0, total_slides: int = 0,
                 width: int = 1080, height: int = 1080) -> str:
    pad    = max(64, int(width * 0.059))
    lh     = max(56, int(height * 0.060))
    headf  = int(height * 0.052)
    subf   = int(height * 0.026)
    urlf   = int(height * 0.020)
    statf  = int(height * 0.036)
    lblf   = int(height * 0.014)

    logo_tag = f'<img class="logo-big" src="{_LOGO}" alt="SmartPickPro">' if _LOGO else '<span class="logo-txt-big">SmartPickPro</span>'

    return f"""<!doctype html><html><head><meta charset="utf-8">{_FONTS}<style>
{_carousel_base_css(width, height, '#030608', '#00F0FF', '#F7C948')}
body{{
  background:
    radial-gradient(ellipse 65% 55% at 50% 50%, rgba(0,240,255,.09) 0%, transparent 60%),
    radial-gradient(ellipse 40% 25% at 50% 95%, rgba(247,201,72,.07) 0%, transparent 50%),
    radial-gradient(circle, rgba(0,240,255,.04) 1px, transparent 1px) 0 0/52px 52px,
    #030608;
}}
.inner{{align-items:center;justify-content:center;text-align:center;gap:{int(height*.022)}px}}
.logo-big{{height:{lh}px;object-fit:contain;filter:drop-shadow(0 0 14px rgba(0,240,255,.5))}}
.logo-txt-big{{font-family:'Bebas Neue',sans-serif;font-size:{lh}px;color:#00F0FF}}
.divider{{width:{int(width*.25)}px;height:1px;background:linear-gradient(90deg,transparent,rgba(0,240,255,.4),transparent)}}
.headline{{
  font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{headf}px;
  letter-spacing:4px;color:#fff;text-transform:uppercase;line-height:1.1
}}
.sub{{
  font-family:'Inter',sans-serif;font-weight:600;font-size:{subf}px;
  color:rgba(255,255,255,.45);line-height:1.4;max-width:{int(width*.75)}px
}}
.stats-row{{display:flex;gap:{int(width*.05)}px}}
.stat-box{{text-align:center}}
.sv{{font-family:'Bebas Neue',sans-serif;font-size:{statf}px;letter-spacing:1px}}
.sl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:{lblf}px;
  letter-spacing:4px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-top:2px}}
.div-v{{width:1px;background:rgba(255,255,255,.12);align-self:stretch}}
.cta-pill{{
  background:linear-gradient(135deg,rgba(0,240,255,.18),rgba(247,201,72,.12));
  border:1px solid rgba(0,240,255,.3);border-radius:999px;
  padding:{int(height*.014)}px {int(width*.06)}px;
  font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:{int(subf*1.05)}px;
  letter-spacing:3px;color:#00F0FF;text-transform:uppercase
}}
.url{{
  font-family:'JetBrains Mono',monospace;font-size:{urlf}px;
  color:rgba(0,240,255,.4);letter-spacing:3px
}}
.slide-num{{font-family:'JetBrains Mono',monospace;font-size:{int(height*.011)}px;
  color:rgba(255,255,255,.18);letter-spacing:2px;margin-top:{int(height*.015)}px}}
</style></head><body>
<div class="bar t"></div>
<div class="bar b"></div>
<div class="inner">
  {logo_tag}
  <div class="divider"></div>
  <div class="headline">Free Daily<br>NBA Edge Picks</div>
  <div class="sub">1,000 quantum simulations per pick.<br>Every result documented. Zero hidden losses.</div>
  <div class="stats-row">
    <div class="stat-box"><div class="sv" style="color:#00FF5A">{wins}</div><div class="sl">Wins</div></div>
    <div class="div-v"></div>
    <div class="stat-box"><div class="sv" style="color:#FF4757">{losses}</div><div class="sl">Losses</div></div>
    <div class="div-v"></div>
    <div class="stat-box"><div class="sv" style="color:#F7C948">{win_rate}%</div><div class="sl">Win Rate</div></div>
  </div>
  <div class="cta-pill">Follow for Daily Picks →</div>
  <div class="url">smartpickpro.ai</div>
  {f'<div class="slide-num">{slide_num} of {total_slides}</div>' if slide_num else ''}
</div>
</body></html>"""


# ── Composer: render_carousel() ──────────────────────────────────────
def render_carousel(
    wins: int,
    losses: int,
    win_rate: float,
    picks: list[dict],
    width: int = 1080,
    height: int = 1080,
    date_str: str = "APR 26 · 2026",
    max_picks: int = 9,
) -> list[str]:
    """Return a list of HTML strings: [cover, pick_1, …, pick_N, cta].

    Pass each item to render_png_bytes() to get a PNG byte string.
    """
    picks = picks[:max_picks]
    total = 1 + len(picks) + 1          # cover + picks + cta

    slides: list[str] = []
    slides.append(carousel_cover(wins, losses, win_rate, date_str, width, height))
    for i, p in enumerate(picks, start=1):
        slides.append(carousel_pick_slide(p, i + 1, total, width, height))
    slides.append(carousel_cta(wins, losses, win_rate, total, total, width, height))
    return slides

# ══════════════════════════════════════════════════════════════════════
# Registry — used by app.py template picker
# ══════════════════════════════════════════════════════════════════════

# Posting-destination categories (ordered for display)
CATEGORIES: dict[str, str] = {
    "instagram_feed":     "📸 Instagram Feed",
    "instagram_reels":    "🎬 Instagram Reels",
    "instagram_carousel": "🎠 Instagram Carousel",
    "twitter_x":          "🐦 Twitter / X",
    "facebook":           "📘 Facebook",
}

# Each template carries:
#   categories  — list of CATEGORIES keys this template is suited for
#   sizes       — {label: (w, h)} mapping; only platform-appropriate sizes listed
#   needs_picks — template fn accepts a `picks` argument
#   needs_carousel — render via render_carousel() rather than a single fn call
TEMPLATES: dict[str, dict] = {
    "scoreboard_hero": {
        "label":       "Scoreboard Hero",
        "description": "Massive record front & center, cyan glow. Clean, bold result card.",
        "fn":          scoreboard_hero,
        "categories":  ["instagram_feed", "twitter_x", "facebook"],
        "sizes": {
            "Instagram Square (1080×1080)": (1080, 1080),
            "Twitter/X Card (1200×628)":    (1200, 628),
            "Facebook Post (1200×628)":     (1200, 628),
        },
    },
    "receipts_gold": {
        "label":       "Receipts Gold",
        "description": "Split layout: big win count left, full player list with actual scores right.",
        "fn":          receipts_gold,
        "categories":  ["instagram_feed"],
        "sizes": {
            "Instagram Square (1080×1080)":   (1080, 1080),
            "Instagram Portrait (1080×1350)": (1080, 1350),
        },
        "needs_picks": True,
    },
    "neon_grid": {
        "label":       "Neon Grid",
        "description": "3×3 win cards on dark crimson/purple. Great for square feed or landscape.",
        "fn":          neon_grid,
        "categories":  ["instagram_feed", "twitter_x", "facebook"],
        "sizes": {
            "Instagram Square (1080×1080)": (1080, 1080),
            "Twitter/X Card (1200×628)":    (1200, 628),
            "Facebook Post (1200×628)":     (1200, 628),
        },
        "needs_picks": True,
    },
    "ice_command": {
        "label":       "Ice Command",
        "description": "Blue steel portrait, full pick list with actual scores. Tall feed card.",
        "fn":          ice_command,
        "categories":  ["instagram_feed"],
        "sizes": {
            "Instagram Portrait (1080×1350)": (1080, 1350),
            "Instagram Square (1080×1080)":   (1080, 1080),
        },
        "needs_picks": True,
    },
    "volt_minimal": {
        "label":       "Volt Minimal",
        "description": "Electric green, giant number, bold & clean. Works on any platform.",
        "fn":          volt_minimal,
        "categories":  ["instagram_feed", "twitter_x", "facebook"],
        "sizes": {
            "Instagram Square (1080×1080)":   (1080, 1080),
            "Twitter/X Card (1200×628)":      (1200, 628),
            "Facebook Post (1200×628)":       (1200, 628),
        },
    },
    "reels_fire": {
        "label":       "Reels Fire",
        "description": "Cinematic dark-red 9:16, pick rows, animated swipe CTA. Built for Reels.",
        "fn":          reels_fire,
        "categories":  ["instagram_reels"],
        "sizes": {
            "Instagram Reel / Story (1080×1920)": (1080, 1920),
        },
        "needs_picks": True,
    },
    "reels_minimal": {
        "label":       "Reels Minimal",
        "description": "Electric-green volt adapted for 9:16. Clean, bold, hypnotic.",
        "fn":          reels_minimal,
        "categories":  ["instagram_reels"],
        "sizes": {
            "Instagram Reel / Story (1080×1920)": (1080, 1920),
        },
    },
    "carousel": {
        "label":       "Carousel (Multi-Slide)",
        "description": "Cover + one receipt per pick + CTA. Instagram swipe carousel.",
        "fn":          carousel_cover,       # cover preview only — render_carousel() for full set
        "categories":  ["instagram_carousel"],
        "sizes": {
            "Instagram Square (1080×1080)":   (1080, 1080),
            "Instagram Portrait (1080×1350)": (1080, 1350),
        },
        "needs_picks":    True,
        "needs_carousel": True,
    },
}
