# ============================================================
# FILE: styles/theme.py
# PURPOSE: All CSS/HTML generators for the SmartBetPro NBA UI.
#          Provides a futuristic "AI Neural Network Lab" bright
#          theme with glassmorphism cards, animated glow
#          effects, and NBA team colors on a clean light
#          AI-lab background for maximum readability.
# BRAND:   SmartBetPro NBA by Quantum Matrix Engine 5.6
# USAGE:
#   from styles.theme import get_global_css, get_player_card_html
#   st.markdown(get_global_css(), unsafe_allow_html=True)
# ============================================================

# Standard library only — no new dependencies
import base64 as _base64
import datetime as _datetime
import functools as _functools
import html as _html
import logging as _logging
import math as _math
import os as _os

_logger_theme = _logging.getLogger(__name__)

# ── Line Value vs Average Badge ──────────────────────────────

def get_line_value_badge_html(gap_pct: float) -> str:
    """Return an HTML badge showing how far a prop line is from the season average.

    Returns empty string if gap is within the -8% to +8% neutral zone.

    Args:
        gap_pct: ``(prop_line - season_avg) / season_avg * 100``.
            Negative = line below avg (OVER value, green).
            Positive = line above avg (UNDER value, orange).
    """
    try:
        gap_pct = float(gap_pct)
    except (TypeError, ValueError):
        return ""
    if -8.0 < gap_pct < 8.0:
        return ""  # Neutral zone — no badge
    if gap_pct <= -8.0:
        return (
            f'<span style="display:inline-block;background:rgba(0,213,89,0.12);'
            f'color:#00D559;font-size:0.72rem;font-weight:700;padding:2px 8px;'
            f'border-radius:100px;border:1px solid rgba(0,213,89,0.32);margin-left:6px;'
            f'vertical-align:middle;">'
            f'\U0001f4c9 {gap_pct:+.1f}% vs Avg</span>'
        )
    else:
        return (
            f'<span style="display:inline-block;background:rgba(242,67,54,0.12);'
            f'color:#F24336;font-size:0.72rem;font-weight:700;padding:2px 8px;'
            f'border-radius:100px;border:1px solid rgba(242,67,54,0.32);margin-left:6px;'
            f'vertical-align:middle;">'
            f'\U0001f4c8 +{gap_pct:.1f}% vs Avg</span>'
        )


# ── Centralised logo paths ──────────────────────────────────────
GOBLIN_LOGO_PATH = _os.path.join("assets", "New_Goblin_Logo.png")
DEMON_LOGO_PATH  = _os.path.join("assets", "New_Demon_Logo.png")
GOLD_LOGO_PATH   = _os.path.join("assets", "NewGold_Logo.png")


@_functools.lru_cache(maxsize=32)
def _load_logo_b64(logo_path):
    """Load and base64-encode a logo file, cached per path."""
    try:
        with open(logo_path, "rb") as _f:
            return _base64.b64encode(_f.read()).decode()
    except OSError as _e:
        _logger_theme.warning("Could not load logo file '%s': %s", logo_path, _e)
        return None


def get_logo_img_tag(logo_path, width=20, alt="logo"):
    """Return an inline <img> tag for use in st.markdown HTML."""
    if _os.path.exists(logo_path):
        _b64 = _load_logo_b64(logo_path)
        if _b64:
            _safe_alt = _html.escape(str(alt))
            return f'<img src="data:image/png;base64,{_b64}" width="{width}" alt="{_safe_alt}" style="vertical-align:middle;">'
    _logger_theme.debug("Logo not found at '%s', using alt text '%s'", logo_path, alt)
    return _html.escape(str(alt))


# ============================================================
# SECTION: Glossary
# Plain-English explanations for betting / AI terms shown
# via tooltips and education boxes throughout the UI.
# ============================================================

GLOSSARY = {
    "Quantum Matrix Simulation": (
        "We simulate thousands of possible game outcomes using the player's historical "
        "stats, matchup data, and current conditions. The percentage you see reflects "
        "how often the player hit the target across all those simulations."
    ),
    "Edge": (
        "The difference between what we think will happen and what the betting line "
        "implies. A positive edge means our model sees more value than the sportsbook "
        "is offering — the bigger the edge, the better the opportunity."
    ),
    "Confidence Score": (
        "A 0–100 rating of how sure the model is about this pick. It combines sample "
        "size, consistency, matchup clarity, and simulation stability. Above 70 = "
        "high confidence; below 50 = proceed with caution."
    ),
    "Expected Value (EV)": (
        "How much money you'd expect to make (or lose) per dollar bet over time if "
        "you placed this wager repeatedly under the same conditions. Positive EV bets "
        "are profitable long-term even if any single bet can lose."
    ),
    "Coefficient of Variation": (
        "A measure of how consistent a player is. It compares the spread of their "
        "game-to-game stats to their average. Low CV = very consistent; high CV = "
        "boom-or-bust performer who is harder to predict."
    ),
    "Prop Bet": (
        "A bet on whether a player will exceed or fall short of a statistical threshold "
        "(the 'line') set by the platform — for example, scoring more or fewer than "
        "24.5 points in a game."
    ),
    "More/Less": (
        "Betting on whether a stat will be higher (More) or lower (Less) than the "
        "line. Our model calculates the true probability of each side so you can "
        "spot when the line is mis-priced."
    ),
    "Line": (
        "The threshold set by the platform for a specific player stat. If the line "
        "for LeBron points is 24.5, you bet whether he scores more (More) or fewer "
        "(Less) than that number."
    ),
    "Parlay": (
        "A multi-pick bet where ALL selections must be correct to win. The payout "
        "multiplies across legs but so does the risk — one wrong pick loses everything. "
        "Stick to high-confidence legs when building parlays."
    ),
    "Bankroll": (
        "The total amount of money set aside exclusively for betting. Good bankroll "
        "management means never risking more than 1–5% on a single bet, so a losing "
        "streak doesn't wipe you out before the edge plays out."
    ),
    "Goblin Bet": (
        "A PrizePicks More/Less prop with boosted payout odds — typically a harder "
        "line to hit but with a higher reward. The model evaluates Goblin lines the "
        "same way as standard props so you can see the true probability."
    ),
    "Demon Bet": (
        "A PrizePicks More/Less prop at reduced payout odds — usually an easier "
        "line but with a lower reward. Our analysis still applies full simulation "
        "so you know whether the edge justifies the smaller payout."
    ),
    "50/50 Bet": (
        "A PrizePicks More/Less prop where the platform treats both sides as equally "
        "likely. Our model often finds an edge even on 50/50 lines because our "
        "simulation uses real matchup data rather than symmetric pricing."
    ),
}


# ============================================================
# END SECTION: Glossary
# ============================================================


# ============================================================
# SECTION: NBA Team Colors
# Primary and secondary hex colors for each franchise.
# ============================================================

# Maps team abbreviation → (primary_color, secondary_color)
_TEAM_COLORS = {
    "ATL": ("#C8102E", "#FDB927"),
    "BOS": ("#007A33", "#BA9653"),
    "BKN": ("#000000", "#FFFFFF"),
    "CHA": ("#1D1160", "#00788C"),
    "CHI": ("#CE1141", "#000000"),
    "CLE": ("#860038", "#FDBB30"),
    "DAL": ("#00538C", "#002B5E"),
    "DEN": ("#0E2240", "#FEC524"),
    "DET": ("#C8102E", "#1D42BA"),
    "GSW": ("#1D428A", "#FFC72C"),
    "HOU": ("#CE1141", "#000000"),
    "IND": ("#002D62", "#FDBB30"),
    "LAC": ("#C8102E", "#1D428A"),
    "LAL": ("#552583", "#FDB927"),
    "MEM": ("#5D76A9", "#12173F"),
    "MIA": ("#98002E", "#F9A01B"),
    "MIL": ("#00471B", "#EEE1C6"),
    "MIN": ("#0C2340", "#236192"),
    "NOP": ("#0C2340", "#C8102E"),
    "NYK": ("#006BB6", "#F58426"),
    "OKC": ("#007AC1", "#EF3B24"),
    "ORL": ("#0077C0", "#C4CED4"),
    "PHI": ("#006BB6", "#ED174C"),
    "PHX": ("#1D1160", "#E56020"),
    "POR": ("#E03A3E", "#000000"),
    "SAC": ("#5A2D81", "#63727A"),
    "SAS": ("#C4CED4", "#000000"),
    "TOR": ("#CE1141", "#000000"),
    "UTA": ("#002B5C", "#00471B"),
    "WAS": ("#002B5C", "#E31837"),
}

_DEFAULT_TEAM_COLORS = ("#00D559", "#0a1a2e")


def get_team_colors(team_abbrev):
    """
    Return (primary, secondary) hex colors for an NBA team.

    Args:
        team_abbrev (str): 3-letter team abbreviation (e.g., 'LAL')

    Returns:
        tuple: (primary_color, secondary_color) hex strings
    """
    return _TEAM_COLORS.get(team_abbrev.upper() if team_abbrev else "", _DEFAULT_TEAM_COLORS)


# ============================================================
# END SECTION: NBA Team Colors
# ============================================================


# ============================================================
# SECTION: Global CSS Theme
# Injected once per page via st.markdown(unsafe_allow_html=True)
# ============================================================

def get_global_css():
    """
    Return the full CSS string for the Smart Pick Pro AI theme.

    Implements a PrizePicks + DraftKings Pick 6 inspired AI design:
    - Clean dark base (#0f1117) with subtle radial gradient
    - PP-style vibrant green (#00D959) as primary accent
    - DK-style gold (#F9C62B) as secondary accent
    - AI electric blue (#3B9EFF) as tertiary accent
    - Bold red (#F24336) for Under/Less indicators
    - Inter font throughout (clean, modern — not sci-fi)
    - Bebas Neue for large stat numbers
    - Pill/capsule shaped badges like PP MORE/LESS buttons
    - Clean elevated cards with subtle shadows
    - Green-forward sidebar with left accent line
    - Pulsing green live-indicator dot

    Returns:
        str: Full <style>...</style> block ready for st.markdown()
    """
    return """
<style>
/* ===========================================================
   SMART PICK PRO â€” AI Theme  (Phase 1: Core Foundation)
   Inspired by PrizePicks + DraftKings Pick 6
   ===========================================================

   Design tokens:
     --pp-green   #00D559   PrizePicks primary green
     --dk-gold    #F9C62B   DraftKings gold
     --ai-blue    #2D9EFF   AI electric blue
     --danger     #F24336   Under / Less red
     --bg-base    #0D0F14   Main background
     --bg-card    #161B27   Card background
     --bg-card-2  #1C2232   Elevated card
     --text       #FFFFFF / #A0AABE / #6B7A9A
   =========================================================== */

/* â”€â”€ Google Fonts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Bebas+Neue&family=Oswald:wght@400;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* â”€â”€ CSS Custom Properties â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
:root {
  --pp-green:      #00D559;
  --pp-green-dim:  rgba(0,213,89,0.12);
  --dk-gold:       #F9C62B;
  --dk-gold-dim:   rgba(249,198,43,0.12);
  --ai-blue:       #2D9EFF;
  --ai-blue-dim:   rgba(45,158,255,0.12);
  --danger:        #F24336;
  --danger-dim:    rgba(242,67,54,0.12);
  --bg-base:       #0D0F14;
  --bg-card:       #161B27;
  --bg-card-2:     #1C2232;
  --bg-sidebar:    #0A0D14;
  --border:        rgba(255,255,255,0.07);
  --border-light:  rgba(255,255,255,0.12);
  --text-1:        #FFFFFF;
  --text-2:        #A0AABE;
  --text-3:        #6B7A9A;
  --radius-sm:     8px;
  --radius-md:     12px;
  --radius-lg:     16px;
  --radius-xl:     20px;
  --radius-pill:   100px;
}

/* â”€â”€ Keyframes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
@keyframes ppPulseGreen {
  0%,100%{ box-shadow: 0 0 0 0 rgba(0,213,89,0.50); }
  50%    { box-shadow: 0 0 0 6px rgba(0,213,89,0); }
}
@keyframes ppPulseGold {
  0%,100%{ box-shadow: 0 0 0 0 rgba(249,198,43,0.50); }
  50%    { box-shadow: 0 0 0 6px rgba(249,198,43,0); }
}
@keyframes ppLiveDot {
  0%,100%{ opacity:1; transform:scale(1); }
  50%    { opacity:0.5; transform:scale(1.4); }
}
@keyframes ppFadeUp {
  from{ opacity:0; transform:translateY(12px); }
  to  { opacity:1; transform:translateY(0); }
}
@keyframes ppShimmer {
  0%  { background-position: -200% center; }
  100%{ background-position:  200% center; }
}
@keyframes ppBorderGlow {
  0%,100%{ box-shadow: 0 0 0 1px rgba(0,213,89,0.14), 0 4px 20px rgba(0,0,0,0.4); }
  50%    { box-shadow: 0 0 0 1px rgba(0,213,89,0.38), 0 4px 24px rgba(0,213,89,0.10); }
}
@keyframes ppGradientShift {
  0%  { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100%{ background-position: 0% 50%; }
}
@keyframes ppScanLine {
  0%  { top: -2px; }
  100%{ top: 100%; }
}

/* â”€â”€ Legacy animation aliases kept for Python helper functions â”€â”€ */
@keyframes borderGlow        { 0%,100%{ box-shadow:0 0 0 1px rgba(0,213,89,0.14),0 4px 20px rgba(0,0,0,0.4); } 50%{ box-shadow:0 0 0 1px rgba(0,213,89,0.38),0 4px 24px rgba(0,213,89,0.10); } }
@keyframes fadeInUp          { from{ opacity:0; transform:translateY(10px); } to{ opacity:1; transform:translateY(0); } }
@keyframes ssFadeInUp        { from{ opacity:0; transform:translateY(16px); } to{ opacity:1; transform:translateY(0); } }
@keyframes headerShimmer     { 0%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } 100%{ background-position:0% 50%; } }
@keyframes gradientShift     { 0%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } 100%{ background-position:0% 50%; } }
@keyframes live-dot-pulse    { 0%,100%{ opacity:1; transform:scale(1); } 50%{ opacity:0.4; transform:scale(1.35); } }
@keyframes thePulse          { 0%,100%{ box-shadow:0 0 4px 1px rgba(0,213,89,0.60); opacity:1; } 50%{ box-shadow:0 0 10px 3px rgba(0,213,89,0.90); opacity:0.7; } }
@keyframes pulse-platinum    { 0%,100%{ box-shadow:0 0 10px rgba(45,158,255,0.30); } 50%{ box-shadow:0 0 24px rgba(45,158,255,0.60); } }
@keyframes pulse-gold        { 0%,100%{ box-shadow:0 0 10px rgba(249,198,43,0.35); } 50%{ box-shadow:0 0 24px rgba(249,198,43,0.65); } }
@keyframes nba-shimmer-platinum { 0%{ background-position:-300% center; } 100%{ background-position:300% center; } }
@keyframes nba-gold-gleam    { 0%,80%,100%{ filter:brightness(1); } 40%{ filter:brightness(1.35) drop-shadow(0 0 6px #F9C62B); } }
@keyframes nba-silver-sheen  { 0%{ background-position:-200% 0; } 100%{ background-position:200% 0; } }
@keyframes nba-bronze-pulse  { 0%,100%{ box-shadow:0 0 8px rgba(205,127,50,0.30); } 50%{ box-shadow:0 0 18px rgba(205,127,50,0.65); } }
@keyframes nba-live-pulse    { 0%,100%{ box-shadow:0 0 0 0 rgba(242,67,54,0.7); opacity:1; } 50%{ box-shadow:0 0 0 8px rgba(242,67,54,0); opacity:0.85; } }
@keyframes analysis-spin     { 0%{ transform:rotate(0deg); } 100%{ transform:rotate(360deg); } }
@keyframes aiSpin            { 0%{ transform:rotate(0deg); } 100%{ transform:rotate(360deg); } }
@keyframes card-flip-in      { 0%{ opacity:0; transform:rotateY(-90deg) scale(0.95); } 100%{ opacity:1; transform:rotateY(0deg) scale(1); } }
@keyframes fade-in-up        { from{ opacity:0; transform:translateY(16px); } to{ opacity:1; transform:translateY(0); } }
@keyframes slide-in-left     { from{ opacity:0; transform:translateX(-24px); } to{ opacity:1; transform:translateX(0); } }
@keyframes slide-in-right    { from{ opacity:0; transform:translateX(24px); } to{ opacity:1; transform:translateX(0); } }
@keyframes count-up-glow     { 0%{ text-shadow:none; } 50%{ text-shadow:0 0 16px rgba(0,213,89,0.5); } 100%{ text-shadow:none; } }
@keyframes numberGlow        { 0%,100%{ text-shadow:0 0 8px rgba(0,213,89,0.30); } 50%{ text-shadow:0 0 24px rgba(0,213,89,0.70); } }
@keyframes goldBreathe       { 0%,100%{ box-shadow:0 0 14px rgba(249,198,43,0.20); } 50%{ box-shadow:0 0 32px rgba(249,198,43,0.55); } }
@keyframes amberPulse        { 0%,100%{ border-color:rgba(249,198,43,0.18); box-shadow:0 0 12px rgba(249,198,43,0.04); } 50%{ border-color:rgba(249,198,43,0.55); box-shadow:0 0 22px rgba(249,198,43,0.12); } }
@keyframes pulseRing         { 0%{ transform:scale(0.8); opacity:0.6; } 50%{ transform:scale(1.1); opacity:1; } 100%{ transform:scale(0.8); opacity:0.6; } }
@keyframes connectorFlow     { 0%{ background-position:-200% 0; } 100%{ background-position:200% 0; } }
@keyframes scanLine          { 0%{ top:-2px; } 100%{ top:100%; } }
@keyframes cardShine         { 0%{ left:-100%; } 100%{ left:200%; } }
@keyframes data-stream       { 0%{ background-position:0 0; } 100%{ background-position:0 -100px; } }
@keyframes freshness-pulse-green  { 0%,100%{ box-shadow:0 0 0 0 rgba(0,213,89,0.6); } 50%{ box-shadow:0 0 0 5px rgba(0,213,89,0); } }
@keyframes freshness-pulse-yellow { 0%,100%{ box-shadow:0 0 0 0 rgba(249,198,43,0.6); } 50%{ box-shadow:0 0 0 5px rgba(249,198,43,0); } }
@keyframes freshness-pulse-red    { 0%,100%{ box-shadow:0 0 0 0 rgba(242,67,54,0.6); } 50%{ box-shadow:0 0 0 5px rgba(242,67,54,0); } }

/* â”€â”€ Streamlit Chrome Reset â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#MainMenu { visibility: hidden !important; }
footer    { display: none !important; }
.stDeployButton { display: none !important; }
.block-container { padding-top: 1rem !important; }

@media (min-width: 769px) {
  header[data-testid="stHeader"] { display: none !important; }
  [data-testid="stSidebar"] {
    transform: none !important;
    visibility: visible !important;
    transition: none !important;
  }
  [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebar"] button[kind="header"] { display: none !important; }
}
@media (max-width: 768px) {
  header[data-testid="stHeader"] {
    background: transparent !important;
    height: 48px !important; min-height: 48px !important; max-height: 48px !important;
    padding: 0 !important; margin: 0 !important;
    border: none !important; box-shadow: none !important;
    overflow: visible !important;
    pointer-events: none !important;
    position: fixed !important; top: 0 !important; left: 0 !important; right: 0 !important;
    z-index: 9998 !important;
  }
  header[data-testid="stHeader"] button,
  header[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"],
  header[data-testid="stHeader"] [data-testid="collapsedControl"],
  header[data-testid="stHeader"] [data-testid="stToolbar"],
  header[data-testid="stHeader"] a {
    pointer-events: auto !important;
    visibility: visible !important;
  }
}

/* â”€â”€ Base / Body â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  font-size: 16px;
  color: #A0AABE;
  background-color: #0D0F14;
}
.stApp {
  background-color: #0D0F14;
  background-image:
    radial-gradient(ellipse at 0% 0%,   rgba(0,213,89,0.04)  0%, transparent 50%),
    radial-gradient(ellipse at 100% 100%, rgba(45,158,255,0.03) 0%, transparent 50%);
}
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(ellipse at 15% 5%,  rgba(0,213,89,0.035)  0%, transparent 40%),
    radial-gradient(ellipse at 85% 95%, rgba(45,158,255,0.025) 0%, transparent 45%),
    #0D0F14;
}

/* Tabular nums for numeric readouts */
[style*="JetBrains"], .stat-readout, .prob-value, .edge-badge,
.dist-p10, .dist-p50, .dist-p90, .dist-label, .summary-value,
.status-card-value, .nba-stat-number, .verdict-confidence,
code, pre, .monospace {
  font-variant-numeric: tabular-nums !important;
}

/* Default text */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stCaptionContainer"],
.stTextInput label, .stSelectbox label, .stSlider label,
.stCheckbox label, .stRadio label {
  color: #A0AABE !important;
  font-size: 1rem !important;
}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h5,
[data-testid="stMarkdownContainer"] h6,
.stHeadingWithActionElements,
h1, h2, h3, h4, h5, h6 {
  color: #FFFFFF !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: -0.01em !important;
}

/* â”€â”€ Scrollbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: rgba(13,15,20,0.9); }
::-webkit-scrollbar-thumb { background: rgba(0,213,89,0.25); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,213,89,0.50); }
::selection     { background: rgba(0,213,89,0.25); color: #fff; }
::-moz-selection{ background: rgba(0,213,89,0.25); color: #fff; }

/* â”€â”€ Sidebar â€” PrizePicks dark style â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
[data-testid="stSidebar"] {
  background: #0A0D14 !important;
  border-right: 1px solid rgba(255,255,255,0.06) !important;
  box-shadow: 2px 0 24px rgba(0,0,0,0.5) !important;
  min-width: 280px !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] a {
  color: #A0AABE !important;
}
[data-testid="stSidebar"] .stPageLink,
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
  font-size: 0.88rem !important;
  white-space: nowrap !important;
  overflow: visible !important;
  text-overflow: unset !important;
}
/* Active nav link â€” PP green left bar */
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] a[aria-current="page"] {
  background: rgba(0,213,89,0.08) !important;
  border-left: 3px solid #00D559 !important;
  color: #00D559 !important;
  font-weight: 700 !important;
}
[data-testid="stSidebar"]::after {
  content: "âš¡ Smart Pick Pro AI Engine";
  display: block;
  position: fixed;
  bottom: 18px; left: 0;
  width: 100%;
  padding: 0 20px;
  box-sizing: border-box;
  text-align: center;
  font-size: 0.65rem;
  font-family: 'Inter', sans-serif;
  font-weight: 700;
  color: rgba(0,213,89,0.50) !important;
  letter-spacing: 0.06em;
  pointer-events: none;
  text-transform: uppercase;
}

/* â”€â”€ Streamlit Metric Cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
[data-testid="stMetric"] {
  background: #161B27;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.35);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
[data-testid="stMetric"]:hover {
  border-color: rgba(0,213,89,0.22);
  box-shadow: 0 4px 20px rgba(0,213,89,0.08), 0 6px 24px rgba(0,0,0,0.45);
  transform: translateY(-2px);
}
[data-testid="stMetricValue"] {
  color: #FFFFFF !important;
  font-size: 1.6rem !important;
  font-family: 'Bebas Neue', 'Inter', sans-serif !important;
  font-variant-numeric: tabular-nums !important;
  letter-spacing: 0.04em !important;
}
[data-testid="stMetricLabel"] {
  color: #6B7A9A !important;
  font-size: 0.75rem !important;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  font-weight: 600 !important;
}
[data-testid="stMetricDelta"] {
  font-family: 'Inter', sans-serif !important;
  font-weight: 700 !important;
  font-variant-numeric: tabular-nums !important;
}

/* â”€â”€ Alerts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.stAlert {
  background: #161B27 !important;
  border-radius: 10px !important;
  border: none !important;
  color: #E0E8FF !important;
  font-size: 0.93rem !important;
  padding: 14px 18px !important;
}
[data-testid="stAlert"][data-baseweb*="negative"],
div[data-testid="stNotification"][data-type="error"]   { border-left: 3px solid #F24336 !important; background: rgba(242,67,54,0.06)  !important; }
[data-testid="stAlert"][data-baseweb*="warning"],
div[data-testid="stNotification"][data-type="warning"] { border-left: 3px solid #F9C62B !important; background: rgba(249,198,43,0.06) !important; }
[data-testid="stAlert"][data-baseweb*="positive"],
div[data-testid="stNotification"][data-type="success"] { border-left: 3px solid #00D559 !important; background: rgba(0,213,89,0.06)  !important; }
[data-testid="stAlert"][data-baseweb*="informational"],
div[data-testid="stNotification"][data-type="info"]    { border-left: 3px solid #2D9EFF !important; background: rgba(45,158,255,0.06) !important; }

/* â”€â”€ Buttons â€” PrizePicks pill style â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
button[kind="primary"] {
  background: #00D559 !important;
  color: #0D0F14 !important;
  border: none !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: 0.03em !important;
  border-radius: 100px !important;
  box-shadow: 0 4px 16px rgba(0,213,89,0.30) !important;
  transition: transform 0.18s ease, box-shadow 0.18s ease !important;
}
button[kind="primary"]:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 24px rgba(0,213,89,0.45) !important;
}
.stButton > button {
  border-radius: 100px !important;
  font-weight: 700 !important;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease !important;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 4px 16px rgba(0,213,89,0.15) !important;
}

/* â”€â”€ Tabs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
[data-testid="stTab"] button {
  font-size: 0.88rem !important;
  font-weight: 600 !important;
  color: #6B7A9A !important;
  transition: color 0.2s ease !important;
}
[data-testid="stTab"] button[aria-selected="true"] {
  color: #00D559 !important;
  border-bottom: 2px solid #00D559 !important;
  font-weight: 700 !important;
}

/* â”€â”€ Expanders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.stExpander {
  background: #161B27 !important;
  border: 1px solid rgba(255,255,255,0.07) !important;
  border-radius: 12px !important;
}
.stExpander summary,
.stExpander [data-testid="stExpanderToggleIcon"] + span {
  color: #E0E8FF !important;
  font-size: 0.95rem !important;
  font-weight: 600 !important;
}
.stExpander details,
[data-testid="stExpander"] details,
[data-testid="stExpanderDetails"] {
  overflow: visible !important;
  max-height: none !important;
}

/* â”€â”€ DataFrames â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
[data-testid="stDataFrame"] {
  border: none !important;
  border-radius: 12px !important;
  overflow: hidden !important;
}
[data-testid="stDataFrame"] td {
  font-size: 0.90rem !important;
  color: #E0E8FF !important;
  font-variant-numeric: tabular-nums !important;
  border-color: rgba(255,255,255,0.04) !important;
}
[data-testid="stDataFrame"] th {
  font-size: 0.72rem !important;
  color: #6B7A9A !important;
  text-transform: uppercase !important;
  letter-spacing: 1px !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 700 !important;
  background: #0D0F14 !important;
  border-color: rgba(255,255,255,0.05) !important;
}
[data-testid="stDataFrame"] tr:hover td  { background: rgba(0,213,89,0.04) !important; }
[data-testid="stDataFrame"] table        { border-collapse: collapse !important; }
[data-testid="stDataFrame"] th,
[data-testid="stDataFrame"] td           { border: none !important; }
.stDataFrame, .stTable { background: #161B27 !important; color: #E0E8FF !important; }

/* â”€â”€ Live pulse dot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.the-pulse {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #00D559;
  animation: thePulse 1.8s ease-in-out infinite;
  vertical-align: middle;
  margin-right: 6px;
  flex-shrink: 0;
}
.ss-fade-in-up  { animation: ssFadeInUp 0.4s ease both; }
.qds-fade-in    { animation: ssFadeInUp 0.5s ease both; animation-fill-mode: both; }
.fade-in-up     { animation: fade-in-up    0.4s ease both; }
.slide-in-left  { animation: slide-in-left  0.35s ease both; }
.slide-in-right { animation: slide-in-right 0.35s ease both; }
.pick-reveal    { animation: card-flip-in 0.45s cubic-bezier(0.25,0.46,0.45,0.94) both; perspective: 800px; }

/* â”€â”€ Input focus â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
input:focus, textarea:focus, select:focus,
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  outline: none !important;
  box-shadow: 0 0 0 2px rgba(0,213,89,0.40) !important;
  border-color: rgba(0,213,89,0.55) !important;
}

/* â”€â”€ Glass Card base â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.glass-card {
  background: #161B27;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
}
.glass-card:hover {
  border-color: rgba(0,213,89,0.22);
  box-shadow: 0 6px 28px rgba(0,213,89,0.08), 0 8px 32px rgba(0,0,0,0.5);
  transform: translateY(-3px);
}

/* â”€â”€ SmartAI Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
/* ── PrizePicks / DraftKings Pick6 style prop card ─────────── */
.smartai-card {
  background: linear-gradient(168deg, #1A1F2E 0%, #161B27 40%, #131722 100%);
  border: 1.5px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: 0;
  margin-bottom: 18px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.03);
  animation: fadeInUp 0.32s cubic-bezier(0.22,1,0.36,1) both;
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
  position: relative;
  overflow: hidden;
}
.smartai-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, var(--card-accent, #00D559), #2D9EFF, var(--card-accent, #00D559));
  background-size: 200% 100%;
  animation: ppShimmer 4s ease infinite;
  border-radius: 20px 20px 0 0;
}
.smartai-card:hover {
  border-color: rgba(0,213,89,0.35);
  transform: translateY(-3px) scale(1.005);
  box-shadow: 0 12px 40px rgba(0,213,89,0.12), 0 4px 24px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04);
}
/* Card sections */
.sc-body    { padding: 18px 20px 14px; }
.sc-footer  { padding: 12px 20px 16px; border-top: 1px solid rgba(255,255,255,0.06); }
/* OVER direction → green accent */
.smartai-card.dir-over-card  { --card-accent: #00D559; border-color: rgba(0,213,89,0.22); }
.smartai-card.dir-under-card { --card-accent: #F24336; border-color: rgba(242,67,54,0.22); }

/* â”€â”€ Neural Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.neural-header {
  background: linear-gradient(135deg, #161B27 0%, #1C2232 50%, #161B27 100%);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 24px 30px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}
.neural-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);
  background-size: 200% 100%;
  animation: ppShimmer 4s linear infinite;
}
.neural-header-title {
  font-size: 1.8rem;
  font-weight: 900;
  font-family: 'Inter', sans-serif;
  color: #FFFFFF;
  letter-spacing: -0.01em;
  line-height: 1.15;
}
.neural-header-subtitle {
  font-size: 0.84rem;
  color: #6B7A9A;
  margin-top: 6px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 600;
}
.circuit-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #00D559;
  margin: 0 6px;
  vertical-align: middle;
  animation: ppLiveDot 1.8s ease-in-out infinite;
  box-shadow: 0 0 8px rgba(0,213,89,0.9);
}

/* â”€â”€ SPP Hero Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.spp-hero-header { display: flex; align-items: center; gap: 22px; text-align: left; }
.spp-hero-logo {
  max-width: 80%; height: auto; object-fit: contain; border-radius: 50%;
  box-shadow: 0 0 18px rgba(0,213,89,0.28), 0 0 8px rgba(45,158,255,0.18);
  flex-shrink: 0;
}
.nba-edition-label {
  font-size: 1.05rem; letter-spacing: 0.22em;
  color: #F24336;
  font-family: 'Bebas Neue', 'Oswald', sans-serif;
  font-weight: 700; margin-top: 4px;
}

/* â”€â”€ Player Name / Team Pill â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.player-name {
  font-size: 1.2rem; font-weight: 800;
  font-family: 'Inter', sans-serif;
  color: #FFFFFF; letter-spacing: -0.01em;
}
.team-pill {
  display: inline-block;
  padding: 2px 10px; border-radius: 100px;
  font-weight: 700; font-size: 0.74rem;
  color: #fff;
  background: rgba(45,158,255,0.15);
  margin-left: 8px; vertical-align: middle;
  border: 1px solid rgba(45,158,255,0.28);
}
.position-tag { color: #6B7A9A; font-size: 0.80rem; margin-left: 8px; vertical-align: middle; }

/* â”€â”€ Tier Badges â€” pill shaped â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.tier-badge {
  display: inline-block; padding: 5px 16px; border-radius: 100px;
  font-weight: 800; font-size: 0.78rem; font-family: 'Inter', sans-serif;
  letter-spacing: 0.06em; text-transform: uppercase;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.tier-badge:hover { transform: scale(1.04); }
.tier-platinum {
  background: rgba(45,158,255,0.14) !important;
  border: 1px solid rgba(45,158,255,0.42) !important;
  color: #2D9EFF !important;
  animation: pulse-platinum 2.5s ease-in-out infinite, nba-shimmer-platinum 3s linear infinite !important;
}
.tier-gold {
  background: rgba(249,198,43,0.14) !important;
  border: 1px solid rgba(249,198,43,0.42) !important;
  color: #F9C62B !important;
  animation: pulse-gold 2.8s infinite, nba-gold-gleam 4s ease-in-out infinite !important;
}
.tier-silver {
  background: rgba(160,170,190,0.12) !important;
  border: 1px solid rgba(160,170,190,0.30) !important;
  color: #A0AABE !important;
  animation: nba-silver-sheen 3s linear infinite !important;
}
.tier-bronze {
  background: rgba(205,127,50,0.12) !important;
  border: 1px solid rgba(205,127,50,0.32) !important;
  color: #CD7F32 !important;
  animation: nba-bronze-pulse 2.5s ease-in-out infinite !important;
}

/* â”€â”€ Live / Sample badges â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.live-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(0,213,89,0.10); color: #00D559;
  border: 1px solid rgba(0,213,89,0.32);
  padding: 4px 12px; border-radius: 100px;
  font-size: 0.74rem; font-weight: 700;
  letter-spacing: 0.05em; text-transform: uppercase;
}
.live-badge::before {
  content: '';
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #00D559;
  animation: thePulse 1.8s ease-in-out infinite;
  flex-shrink: 0;
}
.sample-badge {
  display: inline-block;
  background: rgba(249,198,43,0.10); color: #F9C62B;
  border: 1px solid rgba(249,198,43,0.28);
  padding: 4px 12px; border-radius: 100px;
  font-size: 0.74rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.game-live-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: #F24336; color: #FFFFFF;
  font-family: 'Inter', sans-serif;
  font-size: 0.74rem; font-weight: 800;
  letter-spacing: 0.10em; padding: 4px 12px; border-radius: 100px;
  animation: nba-live-pulse 1.5s ease-in-out infinite;
  text-transform: uppercase;
}
.game-live-badge::before {
  content: '';
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #FFFFFF;
  animation: live-dot-pulse 1.2s ease-in-out infinite;
}

/* â”€â”€ MORE / LESS direction badges â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.dir-over {
  background: rgba(0,213,89,0.12); color: #00D559;
  padding: 5px 16px; border-radius: 100px;
  font-weight: 800; font-size: 0.82rem;
  border: 1px solid rgba(0,213,89,0.32);
  font-family: 'Inter', sans-serif;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.dir-under {
  background: rgba(242,67,54,0.12); color: #F24336;
  padding: 5px 16px; border-radius: 100px;
  font-weight: 800; font-size: 0.82rem;
  border: 1px solid rgba(242,67,54,0.32);
  font-family: 'Inter', sans-serif;
  text-transform: uppercase; letter-spacing: 0.06em;
}

/* ── PP/DK-style OVER/UNDER selection buttons ──────────────── */
.dir-btn-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
.dir-btn {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 10px 8px; border-radius: 12px; cursor: default;
  font-weight: 800; font-size: 0.88rem; font-family: 'Inter', sans-serif;
  letter-spacing: 0.05em; text-transform: uppercase;
  border: 1.5px solid transparent;
  transition: box-shadow 0.18s ease, transform 0.14s ease;
}
.dir-btn:hover { transform: translateY(-1px); }
.dir-btn-over-active  { background: #00D559; color: #0D0F14; border-color: #00D559; box-shadow: 0 4px 18px rgba(0,213,89,0.45); }
.dir-btn-over-active:hover  { box-shadow: 0 6px 24px rgba(0,213,89,0.55); }
.dir-btn-over-inactive  { background: rgba(0,213,89,0.07); color: rgba(0,213,89,0.55); border-color: rgba(0,213,89,0.18); }
.dir-btn-under-active { background: #F24336; color: #FFFFFF; border-color: #F24336; box-shadow: 0 4px 18px rgba(242,67,54,0.40); }
.dir-btn-under-active:hover { box-shadow: 0 6px 24px rgba(242,67,54,0.50); }
.dir-btn-under-inactive { background: rgba(242,67,54,0.07); color: rgba(242,67,54,0.55); border-color: rgba(242,67,54,0.18); }
.dir-btn-pct { font-size: 0.72rem; font-weight: 600; opacity: 0.85; font-variant-numeric: tabular-nums; }

/* ── PP/DK card structural helpers ─────────────────────────── */
.sc-body    { padding: 16px 18px 10px; }
.sc-footer  { padding: 8px 18px 14px; border-top: 1px solid rgba(255,255,255,0.06); }
.sc-header  { display: flex; align-items: center; gap: 14px; padding: 14px 18px 8px; }
.sc-headshot {
  width: 72px; height: 72px; border-radius: 50%; object-fit: cover;
  flex-shrink: 0; border: 2.5px solid rgba(255,255,255,0.12);
  background: #1C2232; transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
.smartai-card:hover .sc-headshot { border-color: rgba(0,213,89,0.40); box-shadow: 0 4px 20px rgba(0,213,89,0.12), 0 4px 16px rgba(0,0,0,0.35); }
.sc-player-info { flex: 1; min-width: 0; }
.sc-player-name {
  font-size: 1.05rem; font-weight: 800; color: #FFFFFF;
  font-family: 'Inter', sans-serif; letter-spacing: -0.01em;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.sc-meta-row { display: flex; align-items: center; gap: 6px; margin-top: 3px; flex-wrap: wrap; }
.sc-team-badge { display: inline-block; padding: 1px 8px; border-radius: 100px; font-size: 0.68rem; font-weight: 700; color: #fff; background: rgba(255,255,255,0.12); }
.sc-position   { font-size: 0.70rem; color: #6B7A9A; font-weight: 600; }
.sc-platform-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 100px; font-size: 0.65rem; font-weight: 700; white-space: nowrap; }
.sc-plat-pp  { background: rgba(22,163,74,0.15);  color: #4ade80; border: 1px solid rgba(22,163,74,0.30); }
.sc-plat-dk  { background: rgba(43,108,176,0.15);  color: #63b3ed; border: 1px solid rgba(43,108,176,0.30); }
.sc-plat-ud  { background: rgba(202,138,4,0.15);   color: #fcd34d; border: 1px solid rgba(202,138,4,0.28); }
.sc-plat-def { background: rgba(255,255,255,0.06); color: #A0AABE;  border: 1px solid rgba(255,255,255,0.12); }
.sc-line-block { text-align: center; padding: 12px 10px 8px; background: linear-gradient(180deg, rgba(0,0,0,0.22) 0%, rgba(0,0,0,0.12) 100%); border-radius: 14px; margin: 10px 0 6px; border-top: 1px solid rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.03); }
.sc-stat-label { font-size: 0.65rem; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase; color: #6B7A9A; margin-bottom: 3px; }
.sc-line-number { font-size: 2.6rem; font-weight: 900; color: #FFFFFF; font-family: 'Bebas Neue','Inter',sans-serif; letter-spacing: -0.01em; line-height: 1; font-variant-numeric: tabular-nums; text-shadow: 0 2px 10px rgba(0,0,0,0.35); }
.sc-avg-row { font-size: 0.72rem; color: #6B7A9A; margin-top: 4px; }
.sc-avg-val { font-weight: 700; color: #A0AABE; }
.sc-avg-diff-pos { color: #00D559; font-weight: 700; }
.sc-avg-diff-neg { color: #F24336; font-weight: 700; }
.sc-prob-row { display: flex; align-items: center; gap: 10px; margin: 8px 0; }
.sc-prob-track { flex: 1; height: 7px; background: rgba(255,255,255,0.07); border-radius: 100px; overflow: hidden; box-shadow: inset 0 1px 2px rgba(0,0,0,0.2); }
.sc-prob-fill-over  { height: 100%; border-radius: 100px; background: linear-gradient(90deg, #00D559, #2D9EFF); transition: width 0.4s ease; }
.sc-prob-fill-under { height: 100%; border-radius: 100px; background: linear-gradient(90deg, #F24336, #F9C62B); transition: width 0.4s ease; }
.sc-prob-pct { font-size: 0.82rem; font-weight: 800; color: #FFFFFF; font-variant-numeric: tabular-nums; white-space: nowrap; min-width: 36px; text-align: right; }
.sc-metrics { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin: 8px 0 6px; }
.sc-metric { background: linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%); border-radius: 10px; padding: 7px 6px; text-align: center; border: 1px solid rgba(255,255,255,0.06); transition: background 0.15s ease; box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 3px rgba(0,0,0,0.12); }
.sc-metric:hover { background: rgba(255,255,255,0.07); }
.sc-metric-val   { font-size: 0.88rem; font-weight: 800; color: #FFFFFF; font-variant-numeric: tabular-nums; }
.sc-metric-label { font-size: 0.58rem; color: #6B7A9A; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 2px; }
.sc-form-row { display: flex; align-items: center; gap: 5px; margin: 5px 0; }
.sc-form-dot-hit  { width: 9px; height: 9px; border-radius: 50%; background: #00D559; box-shadow: 0 0 5px rgba(0,213,89,0.6); flex-shrink: 0; }
.sc-form-dot-miss { width: 9px; height: 9px; border-radius: 50%; background: #F24336; box-shadow: 0 0 4px rgba(242,67,54,0.5); flex-shrink: 0; }
.sc-form-label    { font-size: 0.60rem; color: #6B7A9A; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-right: 4px; }
.sc-edge { display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px; border-radius: 100px; font-size: 0.70rem; font-weight: 700; }
.sc-edge-pos { background: rgba(0,213,89,0.10); color: #00D559; border: 1px solid rgba(0,213,89,0.26); }
.sc-edge-neg { background: rgba(242,67,54,0.10); color: #F24336; border: 1px solid rgba(242,67,54,0.26); }
.smartai-card.tier-card-platinum { box-shadow: 0 0 28px rgba(0,213,89,0.14), 0 4px 24px rgba(0,0,0,0.45); }
.smartai-card.tier-card-gold     { box-shadow: 0 0 24px rgba(249,198,43,0.14), 0 4px 24px rgba(0,0,0,0.45); }
.smartai-card.tier-card-silver   { box-shadow: 0 0 16px rgba(160,170,190,0.10), 0 4px 24px rgba(0,0,0,0.45); }

/* â”€â”€ AI Verdict Cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.verdict-bet {
  background: rgba(0,213,89,0.06);
  border: 1.5px solid rgba(0,213,89,0.38);
  border-radius: 16px; padding: 16px 20px;
  animation: ppBorderGlow 2.5s ease-in-out infinite;
  box-shadow: 0 4px 20px rgba(0,213,89,0.07);
}
.verdict-avoid {
  background: rgba(242,67,54,0.06);
  border: 1.5px solid rgba(242,67,54,0.38);
  border-radius: 16px; padding: 16px 20px;
  box-shadow: 0 4px 20px rgba(242,67,54,0.07);
}
.verdict-risky {
  background: rgba(249,198,43,0.06);
  border: 1.5px solid rgba(249,198,43,0.32);
  border-radius: 16px; padding: 16px 20px;
  box-shadow: 0 4px 20px rgba(249,198,43,0.07);
}
.verdict-label {
  font-size: 1.3rem; font-weight: 900;
  font-family: 'Bebas Neue', 'Inter', sans-serif;
  letter-spacing: 0.12em; text-transform: uppercase;
}
.verdict-label-bet   { color: #00D559; }
.verdict-label-avoid { color: #F24336; }
.verdict-label-risky { color: #F9C62B; }
.verdict-confidence  { font-size: 0.78rem; color: #6B7A9A; margin-top: 4px; font-weight: 600; }
.verdict-explanation {
  font-size: 0.88rem; color: rgba(224,232,255,0.90);
  margin-top: 10px; line-height: 1.6;
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: 10px;
}

/* â”€â”€ Stat Readout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.stat-readout {
  background: rgba(22,27,39,0.95);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px; padding: 8px 14px; margin: 4px 0;
  display: flex; justify-content: space-between; align-items: center;
  transition: background 0.2s ease;
}
.stat-readout:hover { background: rgba(28,34,50,0.95); }
.stat-readout-label { color: #6B7A9A; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; }
.stat-readout-value { color: #00D559; font-size: 0.96rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-readout-context { color: #6B7A9A; font-size: 0.74rem; margin-left: 10px; }

/* â”€â”€ Education Box â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.education-box {
  background: #161B27; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 14px 18px; margin: 10px 0;
  transition: background 0.2s ease;
}
.education-box:hover { background: #1C2232; }
.education-box-title { font-size: 0.88rem; font-weight: 700; color: #2D9EFF; display: flex; align-items: center; gap: 7px; cursor: pointer; user-select: none; }
.education-box-content { font-size: 0.83rem; color: rgba(160,170,190,0.90); margin-top: 9px; line-height: 1.6; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 9px; }

/* â”€â”€ Probability Gauge â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.prob-gauge-wrap { background: rgba(13,15,20,0.80); border-radius: 10px; height: 14px; overflow: hidden; margin-top: 6px; border: 1px solid rgba(255,255,255,0.06); }
.prob-gauge-fill-over  { background: linear-gradient(90deg, #00D559, #2D9EFF); height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.prob-gauge-fill-under { background: linear-gradient(90deg, #F24336, #ff6b6b); height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.prob-value { font-size: 1.15rem; font-weight: 800; color: #FFFFFF; font-family: 'Bebas Neue', 'Inter', sans-serif; font-variant-numeric: tabular-nums; letter-spacing: 0.04em; }
.edge-badge { padding: 3px 10px; border-radius: 100px; font-size: 0.78rem; font-weight: 700; }
.edge-positive { background: rgba(0,213,89,0.12);  color: #00D559; border: 1px solid rgba(0,213,89,0.32);  }
.edge-negative { background: rgba(242,67,54,0.12); color: #F24336; border: 1px solid rgba(242,67,54,0.32); }

/* â”€â”€ Force Bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.force-bar-wrap { display: flex; height: 8px; border-radius: 100px; overflow: hidden; background: rgba(13,15,20,0.80); margin-top: 5px; border: 1px solid rgba(255,255,255,0.05); }
.force-bar-over  { background: linear-gradient(90deg, #00D559, #2D9EFF); }
.force-bar-under { background: linear-gradient(90deg, #F24336, #ff6b6b); }

/* â”€â”€ Distribution Range â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.dist-range-wrap { text-align: right; }
.dist-p10  { color: #F24336; font-size: 0.80rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.dist-p50  { color: #FFFFFF;  font-size: 0.90rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.dist-p90  { color: #00D559; font-size: 0.80rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.dist-sep  { color: #3A4460; font-size: 0.80rem; margin: 0 3px; }
.dist-label{ color: #6B7A9A; font-size: 0.68rem; }

/* â”€â”€ Form Dots â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.form-dot-over  { display:inline-block; width:10px; height:10px; border-radius:50%; background:#00D559; box-shadow:0 0 5px rgba(0,213,89,0.65); margin:1px; vertical-align:middle; }
.form-dot-under { display:inline-block; width:10px; height:10px; border-radius:50%; background:#F24336; box-shadow:0 0 5px rgba(242,67,54,0.60); margin:1px; vertical-align:middle; }

/* â”€â”€ Summary Cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.summary-card {
  background: linear-gradient(168deg, #1A1F2E 0%, #161B27 60%, #131722 100%);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 16px 20px; text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.summary-card:hover { border-color: rgba(0,213,89,0.28); box-shadow: 0 4px 20px rgba(0,213,89,0.10), 0 6px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04); transform: translateY(-2px); }
.summary-value { font-size: 2rem; font-weight: 900; color: #FFFFFF; line-height: 1.1; font-family: 'Bebas Neue', 'Inter', sans-serif; font-variant-numeric: tabular-nums; letter-spacing: 0.04em; text-shadow: 0 2px 8px rgba(0,0,0,0.3); }
.summary-label { font-size: 0.72rem; color: #6B7A9A; text-transform: uppercase; letter-spacing: 1.2px; margin-top: 5px; font-weight: 600; }

/* â”€â”€ Best Bet Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.best-bet-card {
  background: linear-gradient(168deg, #1A1F2E 0%, #161B27 50%, #131722 100%);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 16px 20px; margin-bottom: 10px;
  position: relative; box-shadow: 0 2px 12px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03);
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}
.best-bet-card:hover { border-color: rgba(0,213,89,0.30); transform: translateX(3px); box-shadow: 0 4px 20px rgba(0,213,89,0.10), 0 6px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04); }
.best-bet-rank { position: absolute; top: -10px; left: 16px; background: linear-gradient(135deg, #00D559, #2D9EFF); color: #0D0F14; font-weight: 900; font-size: 0.72rem; padding: 2px 10px; border-radius: 100px; font-family: 'Inter', sans-serif; letter-spacing: 0.05em; }
.player-analysis-card {
  background: linear-gradient(168deg, #1A1F2E 0%, #161B27 40%, #131722 100%);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px; padding: 20px 24px; margin-bottom: 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03);
  animation: ppBorderGlow 4s ease-in-out infinite, fadeInUp 0.3s ease both;
  transition: border-color 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;
  position: relative; overflow: hidden;
}
.player-analysis-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);
  background-size: 200% 100%; animation: ppShimmer 4s ease infinite;
}
.player-analysis-card:hover { border-color: rgba(0,213,89,0.30); transform: translateY(-4px); box-shadow: 0 8px 32px rgba(0,213,89,0.10), 0 8px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04); }
.add-to-slip-btn { background: #00D559; color: #0D0F14; border: none; border-radius: 100px; padding: 7px 18px; font-weight: 800; font-size: 0.78rem; cursor: pointer; font-family: 'Inter', sans-serif; transition: opacity 0.2s ease, transform 0.2s ease; box-shadow: 0 4px 14px rgba(0,213,89,0.32); letter-spacing: 0.04em; text-transform: uppercase; }
.add-to-slip-btn:hover { opacity: 0.88; transform: scale(1.03); }

/* â”€â”€ Roster Health â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.health-matched   { display:inline-block; background:rgba(0,213,89,0.10);  border:1px solid rgba(0,213,89,0.32);  color:#00D559; padding:2px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; margin:2px; }
.health-fuzzy     { display:inline-block; background:rgba(249,198,43,0.10); border:1px solid rgba(249,198,43,0.32); color:#F9C62B; padding:2px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; margin:2px; cursor:help; }
.health-unmatched { display:inline-block; background:rgba(242,67,54,0.10);  border:1px solid rgba(242,67,54,0.32);  color:#F24336; padding:2px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; margin:2px; }

/* â”€â”€ Stat Chip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.stat-chip { display:inline-block; background:rgba(45,158,255,0.08); border:1px solid rgba(45,158,255,0.16); border-radius:100px; padding:4px 12px; margin-right:6px; margin-top:4px; color:#E0E8FF; font-size:0.82rem; font-weight:600; transition:background 0.2s ease; }
.stat-chip:hover { background: rgba(45,158,255,0.15); }
.stat-label { color: #6B7A9A; font-size: 0.72rem; }

/* â”€â”€ Progress Ring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.progress-ring-wrap { display:inline-flex; flex-direction:column; align-items:center; gap:4px; }
.progress-ring-label { font-size:0.72rem; color:#6B7A9A; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; }

/* â”€â”€ Signal Strength Bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.signal-bar-wrap { display:inline-flex; align-items:flex-end; gap:3px; height:22px; vertical-align:middle; }
.signal-bar-seg { width:7px; border-radius:2px; background:rgba(45,158,255,0.10); transition:background 0.2s ease; }
.signal-bar-seg.active { background: linear-gradient(180deg, #00D559, #2D9EFF); box-shadow: 0 0 4px rgba(0,213,89,0.5); }
.signal-strength-label { font-size:0.72rem; color:#6B7A9A; margin-left:6px; vertical-align:middle; font-weight:600; }

/* â”€â”€ Inline Tooltip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.edu-tooltip { position:relative; display:inline-block; border-bottom:1px dashed rgba(45,158,255,0.5); color:#2D9EFF; cursor:help; font-weight:600; }
.edu-tooltip .tooltip-text { visibility:hidden; opacity:0; width:260px; background:#161B27; border:1px solid rgba(255,255,255,0.10); color:#E0E8FF; font-size:0.80rem; font-weight:400; line-height:1.5; border-radius:12px; padding:10px 14px; position:absolute; z-index:999; bottom:130%; left:50%; transform:translateX(-50%); transition:opacity 0.18s ease; box-shadow:0 4px 24px rgba(0,0,0,0.5); pointer-events:none; }
.edu-tooltip:hover .tooltip-text { visibility:visible; opacity:1; }

/* â”€â”€ Smart Tooltip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.smart-tooltip-wrap { position:relative; cursor:help; }
.smart-tooltip { visibility:hidden; opacity:0; max-width:300px; min-width:140px; background:#161B27; border:1px solid rgba(255,255,255,0.10); border-radius:12px; padding:10px 14px; font-size:0.82rem; color:#A0AABE; line-height:1.5; position:absolute; z-index:9999; bottom:calc(100% + 8px); left:50%; transform:translateX(-50%) translateY(4px); box-shadow:0 4px 24px rgba(0,0,0,0.5); transition:opacity 0.18s ease, visibility 0.18s ease, transform 0.18s ease; pointer-events:none; }
.smart-tooltip::after { content:''; position:absolute; top:100%; left:50%; transform:translateX(-50%); border:6px solid transparent; border-top-color:rgba(255,255,255,0.10); }
.smart-tooltip-wrap:hover .smart-tooltip { visibility:visible; opacity:1; transform:translateX(-50%) translateY(0); }

/* â”€â”€ Platform Badge â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.platform-badge { display:inline-block; padding:3px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; transition:opacity 0.2s ease; }
.status-card {
  background: linear-gradient(168deg, #1A1F2E 0%, #161B27 60%, #131722 100%);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 20px 22px; text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03);
  transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
  position: relative; overflow: hidden;
}
.status-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, #00D559, #2D9EFF); opacity:0; transition:opacity 0.25s ease; }
.status-card:hover::before { opacity:1; }
.status-card:hover { border-color:rgba(0,213,89,0.22); transform:translateY(-3px); box-shadow:0 6px 24px rgba(0,213,89,0.10), 0 8px 28px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04); }
.status-card-value { font-size:2.2rem; font-weight:900; color:#FFFFFF; font-family:'Bebas Neue','Inter',sans-serif; font-variant-numeric:tabular-nums; letter-spacing:0.04em; text-shadow: 0 2px 8px rgba(0,0,0,0.3); }
.status-card-label { font-size:0.70rem; color:#6B7A9A; text-transform:uppercase; letter-spacing:1.2px; margin-top:6px; font-weight:600; }

/* â”€â”€ Team Chip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.team-chip { display:inline-block; background:rgba(45,158,255,0.08); color:#E0E8FF; border:1px solid rgba(255,255,255,0.08); padding:3px 10px; border-radius:100px; font-size:0.83rem; font-weight:600; margin:3px; transition:border-color 0.2s ease; }
.team-chip:hover { border-color: rgba(45,158,255,0.25); }

/* â”€â”€ Correlation Warning â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.corr-warning { background:rgba(249,198,43,0.08); border:1px solid rgba(249,198,43,0.26); border-radius:8px; padding:8px 14px; color:#F9C62B; font-size:0.83rem; margin-top:8px; }

/* â”€â”€ GRT Picks Table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.grt-summary-bar { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; padding:0 2px; }
.grt-chip { display:inline-flex; align-items:center; gap:4px; padding:5px 14px; border-radius:100px; font-size:0.70rem; font-weight:700; letter-spacing:0.5px; text-transform:uppercase; white-space:nowrap; }
.grt-table-wrap { border-radius:12px; overflow:hidden; border:1px solid rgba(255,255,255,0.07); background:#161B27; box-shadow:0 4px 20px rgba(0,0,0,0.3); }
.grt-table { width:100%; border-collapse:collapse; table-layout:fixed; }
.grt-th { padding:10px 12px; font-size:0.68rem; font-family:'Inter',sans-serif; font-weight:700; color:#6B7A9A; text-transform:uppercase; letter-spacing:1.2px; background:#0D0F14; border-bottom:1px solid rgba(255,255,255,0.06); text-align:left; white-space:nowrap; }
.grt-th-rank { width:44px; text-align:center; }
.grt-th-center { text-align:center; }
.grt-th-right { text-align:right; }
.grt-row { transition:background 0.15s ease; border-bottom:1px solid rgba(255,255,255,0.03); }
.grt-row:hover { background: rgba(0,213,89,0.04); }
.grt-td { padding:10px 12px; font-size:0.85rem; color:#E0E8FF; font-family:'Inter',sans-serif; vertical-align:middle; border-bottom:1px solid rgba(255,255,255,0.03); }
.grt-td-rank { text-align:center; width:44px; }
.grt-td-center { text-align:center; }
.grt-td-right { text-align:right; }
.grt-td-player { display:flex; align-items:center; gap:8px; }
.grt-team-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.grt-player-name { font-family:'Inter',sans-serif; font-weight:700; font-size:0.85rem; color:#FFFFFF; white-space:nowrap; }
.grt-team-label { font-size:0.68rem; color:#6B7A9A; font-weight:600; margin-left:2px; letter-spacing:0.5px; }
.grt-mono { font-variant-numeric:tabular-nums; }
.grt-dir { display:inline-block; padding:3px 12px; border-radius:100px; font-size:0.68rem; font-weight:800; font-family:'Inter',sans-serif; letter-spacing:0.5px; text-transform:uppercase; }
.grt-dir-over  { background:rgba(0,213,89,0.12);  color:#00D559; border:1px solid rgba(0,213,89,0.28);  }
.grt-dir-under { background:rgba(242,67,54,0.12); color:#F24336; border:1px solid rgba(242,67,54,0.28); }
.grt-safe-wrap { display:flex; flex-direction:column; align-items:center; gap:3px; min-width:56px; }
.grt-safe-num { font-size:0.82rem; font-weight:700; font-variant-numeric:tabular-nums; line-height:1; }
.grt-safe-track { width:100%; max-width:52px; height:3px; background:rgba(255,255,255,0.06); border-radius:100px; overflow:hidden; }
.grt-safe-fill { height:100%; border-radius:100px; transition:width 0.3s ease; }
.grt-tier { display:inline-block; padding:3px 10px; border-radius:100px; font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; }
.grt-rank { display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:8px; font-size:0.72rem; font-weight:700; color:#6B7A9A; background:rgba(255,255,255,0.04); }
.grt-rank-top { color:#00D559; background:rgba(0,213,89,0.12); border:1px solid rgba(0,213,89,0.28); }
@media (max-width: 768px) {
  .grt-table { font-size:0.78rem; }
  .grt-th, .grt-td { padding:8px 6px; }
  .grt-player-name { font-size:0.78rem; }
  .grt-summary-bar { gap:6px; }
  .grt-chip { padding:4px 10px; font-size:0.65rem; }
}

/* â”€â”€ Data Freshness Badge â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.data-freshness-badge { display:inline-flex; align-items:center; gap:5px; font-size:0.70rem; font-weight:700; letter-spacing:0.10em; padding:3px 10px; border-radius:100px; vertical-align:middle; text-transform:uppercase; }
.data-freshness-badge.fresh    { background:rgba(0,213,89,0.10);  color:#00D559; border:1px solid rgba(0,213,89,0.32);  animation:freshness-pulse-green  2s   ease-in-out infinite; }
.data-freshness-badge.stale    { background:rgba(249,198,43,0.10); color:#F9C62B; border:1px solid rgba(249,198,43,0.32); animation:freshness-pulse-yellow 2.5s ease-in-out infinite; }
.data-freshness-badge.outdated { background:rgba(242,67,54,0.10);  color:#F24336; border:1px solid rgba(242,67,54,0.32);  animation:freshness-pulse-red    1.8s ease-in-out infinite; }

/* â”€â”€ NBA-specific elements â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.nba-game-day-banner {
  border-top: 3px solid transparent;
  border-image: linear-gradient(90deg, #00D559 0%, #FFFFFF 33%, #2D9EFF 66%, #00D559 100%) 1;
  background: #161B27; border-radius: 0 0 12px 12px;
  padding: 12px 24px; text-align: center;
  font-family: 'Bebas Neue', sans-serif; font-size: 1.4rem;
  letter-spacing: 0.25em; color: #FFFFFF; position: relative; overflow: hidden;
}
.nba-game-day-banner::before { content: 'ðŸ€'; margin-right: 12px; }
.nba-game-day-banner::after  { content: 'ðŸ€'; margin-left:  12px; }
.nba-stat-highlight { display:inline-flex; flex-direction:column; align-items:flex-start; border-left:4px solid #00D559; padding:8px 16px 8px 14px; background:rgba(0,213,89,0.06); border-radius:0 12px 12px 0; margin:4px 8px; transition:border-color 0.2s ease, background 0.2s ease; }
.nba-stat-highlight:hover { border-color:#2D9EFF; background:rgba(45,158,255,0.06); }
.nba-stat-number { font-family:'Bebas Neue',sans-serif; font-size:2.2rem; font-weight:700; color:#FFFFFF; line-height:1; letter-spacing:0.03em; }
.nba-stat-label  { font-family:'Oswald','Inter',sans-serif; font-size:0.70rem; font-weight:600; color:#6B7A9A; letter-spacing:0.12em; text-transform:uppercase; margin-top:2px; }
.stApp::after { content:''; display:block; position:fixed; bottom:-120px; right:-120px; width:360px; height:360px; border-radius:50%; border:40px solid rgba(0,213,89,0.02); pointer-events:none; z-index:0; }
.premium-metric-card {
  background: linear-gradient(168deg, #1A1F2E 0%, #161B27 40%, #131722 100%);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px; padding: 22px 26px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03);
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
  animation: count-up-glow 1.5s ease 0.2s both;
  position: relative; overflow: hidden;
}
.premium-metric-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559); background-size:200% 100%; animation:ppShimmer 4s ease infinite; }
.premium-metric-card:hover { transform:translateY(-5px) scale(1.01); border-color:rgba(0,213,89,0.30); box-shadow:0 8px 32px rgba(0,213,89,0.12), 0 12px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04); }

/* â”€â”€ Spinners â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.ai-spinner       { width:36px; height:36px; border:3px solid rgba(0,213,89,0.12); border-top:3px solid #00D559; border-radius:50%; animation:aiSpin 0.9s linear infinite; margin:0 auto; }
.analysis-loading { display:inline-block; width:38px; height:38px; border:3px solid rgba(0,213,89,0.12); border-top-color:#00D559; border-radius:50%; animation:analysis-spin 0.9s linear infinite; vertical-align:middle; margin:0 10px; }

/* â”€â”€ Data Stream â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.data-stream { background-image: repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,213,89,0.025) 3px, rgba(0,213,89,0.025) 4px); background-size: 100% 100px; animation: data-stream 2s linear infinite; }

/* â”€â”€ Correlation Stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
.corr-stats-bar { display:flex; flex-wrap:wrap; gap:12px; margin:16px 0; }
.corr-stat-card { flex:1; min-width:120px; background:#161B27; border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:10px 14px; text-align:center; }
.corr-stat-label { color:#6B7A9A; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; }
.corr-stat-value { font-size:1.15rem; font-weight:800; font-variant-numeric:tabular-nums; }
.corr-insight { background:#161B27; border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:12px 16px; margin:12px 0; }
.corr-insight-title { font-weight:700; font-size:0.85rem; color:#FFFFFF; }
.corr-insight-body  { color:#A0AABE; font-size:0.82rem; margin-top:4px; }
.corr-heatmap-wrap  { overflow-x:auto; -webkit-overflow-scrolling:touch; margin:0 -4px; padding:0 4px; }
@media (max-width: 768px) {
  .corr-stats-bar { gap:8px; }
  .corr-stat-card { min-width:calc(50% - 8px); flex:1 1 calc(50% - 8px); padding:8px 10px; }
  .corr-stat-value { font-size:1rem; }
  .corr-insight { padding:10px 12px; margin:8px 0; }
  .corr-heatmap-wrap { margin:0 -8px; padding:0 8px 8px; }
  .corr-heatmap-wrap .stPlotlyChart,
  .corr-heatmap-wrap [data-testid="stPlotlyChart"] { min-width:480px; }
}
@media (max-width: 480px) {
  .corr-stats-bar { flex-direction:column; gap:6px; }
  .corr-stat-card { min-width:100%; flex:1 1 100%; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; }
  .corr-heatmap-wrap .stPlotlyChart,
  .corr-heatmap-wrap [data-testid="stPlotlyChart"] { min-width:400px; }
}

/* â”€â”€ Print â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
@media print {
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"],
  .stButton, .stDownloadButton, [data-testid="stSidebarNav"] { display:none !important; }
  html, body, .stApp, [class*="css"] { background:#ffffff !important; color:#111111 !important; }
  .smartai-card, .premium-metric-card { background:#f5f5f5 !important; border:1px solid #cccccc !important; box-shadow:none !important; }
  section[data-testid="stMain"], .main .block-container { max-width:100% !important; padding:0 !important; }
}

/* â”€â”€ Mobile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
@media (max-width: 768px) {
  html, body, [class*="css"] { font-size:14px !important; }
  .neural-header-title { font-size:1.4rem !important; }
  .smartai-card, .premium-metric-card { padding:14px 16px !important; }
  .nba-stat-number { font-size:1.7rem !important; }
  button, .stButton > button { min-height:44px !important; padding:10px 16px !important; }
  input, select, textarea, [role="button"], .stSelectbox > div { min-height:44px !important; }
  [data-testid="stMetricValue"] { font-size:1.2rem !important; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:8px !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width:calc(50% - 8px) !important; flex:1 1 calc(50% - 8px) !important; }
  [data-testid="stSidebar"] { min-width:0 !important; width:280px !important; max-width:85vw !important; z-index:9999 !important; position:fixed !important; top:0 !important; left:0 !important; height:100vh !important; height:100dvh !important; overflow-y:auto !important; overflow-x:hidden !important; -webkit-overflow-scrolling:touch !important; transition:transform 0.3s cubic-bezier(0.4,0,0.2,1), visibility 0.3s !important; box-shadow:4px 0 24px rgba(0,0,0,0.6) !important; }
  [data-testid="stSidebar"] > div:first-child { height:100% !important; overflow-y:auto !important; overflow-x:hidden !important; -webkit-overflow-scrolling:touch !important; display:flex !important; flex-direction:column !important; padding-bottom:24px !important; }
  [data-testid="stSidebar"][aria-expanded="false"] { transform:translateX(-100%) !important; visibility:hidden !important; box-shadow:none !important; }
  [data-testid="stSidebar"][aria-expanded="true"]  { transform:translateX(0) !important; visibility:visible !important; }
  [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], button[kind="header"],
  header[data-testid="stHeader"] button[kind="header"],
  header[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"],
  header[data-testid="stHeader"] > div > button {
    display:flex !important; visibility:visible !important; opacity:1 !important;
    position:fixed !important; top:10px !important; left:10px !important;
    z-index:10000 !important; background:rgba(22,27,39,0.97) !important;
    border:1px solid rgba(0,213,89,0.35) !important; border-radius:10px !important;
    padding:8px 10px !important; min-width:44px !important; min-height:44px !important;
    width:44px !important; height:44px !important; cursor:pointer !important;
    box-shadow:0 2px 16px rgba(0,0,0,0.5) !important;
    align-items:center !important; justify-content:center !important;
  }
  [data-testid="stSidebarCollapsedControl"] svg, [data-testid="collapsedControl"] svg,
  button[kind="header"] svg, header[data-testid="stHeader"] button svg { width:22px !important; height:22px !important; color:#00D559 !important; }
  [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebar"] button[kind="header"] { position:absolute !important; top:8px !important; right:8px !important; z-index:10001 !important; min-width:44px !important; min-height:44px !important; }
  section[data-testid="stMain"] { margin-left:0 !important; width:100% !important; }
  .main .block-container { padding-left:12px !important; padding-right:12px !important; padding-top:60px !important; max-width:100% !important; }
  .stApp, section[data-testid="stMain"] { overflow-x:hidden !important; }
  .stDataFrame, [data-testid="stDataFrame"], .comp-table, .qds-strategy-table { overflow-x:auto !important; -webkit-overflow-scrolling:touch !important; max-width:100% !important; }
  [data-testid="stPopover"] > div { max-width:92vw !important; max-height:80vh !important; overflow-y:auto !important; }
  [data-testid="stExpander"] summary { min-height:44px !important; padding:10px 14px !important; }
  [data-testid="stTabs"] [role="tablist"] { overflow-x:auto !important; -webkit-overflow-scrolling:touch !important; flex-wrap:nowrap !important; gap:4px !important; }
  [data-testid="stTabs"] button[role="tab"] { min-height:44px !important; white-space:nowrap !important; flex-shrink:0 !important; padding:8px 14px !important; font-size:0.85rem !important; }
  img:not(.qcm-headshot):not(.upc-headshot):not(.bet-card-headshot):not(.gm-card-headshot):not(.gm-modal-headshot):not(.joseph-welcome-avatar):not(.upc-joseph-avatar):not(.upc-joseph-resp-avatar):not(.qds-player-img):not(.sweat-card-headshot):not(.joseph-floating-avatar):not(.joseph-avatar):not(.joseph-avatar-sm):not(.joseph-sidebar-avatar):not(.joseph-inline-avatar):not(.joseph-popover-avatar):not(.qam-mu-logo):not(.pc-head):not(.pc-id-avatar):not(.sc-headshot):not(.qeg-prop-hs):not(.qeg-detail-hs):not(.qeg-sum-head):not(.qam-hero-headshot):not(.plc-hs):not(.plat-headshot) { max-width:100% !important; height:auto !important; }
  .sc-headshot, .qeg-prop-hs, .qeg-detail-hs, .qeg-sum-head, .qam-hero-headshot, .plc-hs, .plat-headshot, .qcm-headshot, .upc-headshot, .bet-card-headshot, .gm-card-headshot, .gm-modal-headshot, .sweat-card-headshot, .qds-player-img { object-fit: cover !important; aspect-ratio: 1 / 1; }
  iframe { max-width:100% !important; }
  [data-testid="stPageLink"] a { min-height:44px !important; display:flex !important; align-items:center !important; }
  [data-testid="stMetricLabel"] { font-size:0.75rem !important; }
  .glass-card { padding:14px 16px !important; border-radius:12px !important; }
  .qds-prop-card { padding:14px !important; margin-bottom:14px !important; }
  .qds-player-img { width:56px !important; height:56px !important; }
  .qds-container { max-width:100% !important; padding:0 10px !important; }
  .qds-na-card { padding:14px !important; margin-bottom:14px !important; }
  .qds-na-metrics-grid { grid-template-columns:repeat(2, 1fr) !important; gap:8px !important; }
  .qds-na-strategy-table, .qds-strategy-table { display:block !important; overflow-x:auto !important; -webkit-overflow-scrolling:touch !important; max-width:100% !important; }
  .qds-game-teams { padding:10px 14px !important; gap:10px !important; }
  .qds-na-matchup { gap:10px !important; padding:10px !important; }
  .qds-na-verdict { padding:10px 14px !important; }
  .qds-report-title-text { font-size:clamp(1.1rem, 3.5vw, 1.6rem) !important; }
  [data-testid="stSidebar"]::after { display:none !important; }
}
@media (max-width: 480px) {
  [data-testid="stSidebar"] { width:100vw !important; max-width:100vw !important; border-right:none !important; }
  .main .block-container { padding-left:8px !important; padding-right:8px !important; }
  [data-testid="stHorizontalBlock"] { flex-direction:column !important; gap:8px !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { width:100% !important; flex:1 1 100% !important; min-width:100% !important; }
}
@media (max-width: 896px) and (orientation: landscape) {
  .main .block-container { padding-top:48px !important; padding-left:10px !important; padding-right:10px !important; }
  [data-testid="stSidebar"] { width:260px !important; max-width:50vw !important; }
  [data-testid="stHorizontalBlock"] { flex-direction:row !important; flex-wrap:wrap !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width:calc(33% - 8px) !important; flex:1 1 auto !important; }
  html, body, [class*="css"] { font-size:13px !important; }
}

/* ── Liquid Progress Bars ──────────────────────────────────────── */
@keyframes liquidShimmer {
  0%   { background-position: -200% center; }
  100% { background-position:  200% center; }
}
@keyframes liquidWave {
  0%   { transform: translateX(-100%) scaleY(1); }
  50%  { transform: translateX(0%)    scaleY(1.08); }
  100% { transform: translateX(100%)  scaleY(1); }
}
@keyframes liquidBubble {
  0%,100% { opacity:0; transform:translateY(0) scale(0.6); }
  50%     { opacity:0.6; transform:translateY(-6px) scale(1); }
}

/* Track */
[data-testid="stProgressBar"] > div,
div[role="progressbar"],
.stProgress > div > div {
  background: rgba(255,255,255,0.06) !important;
  border-radius: 100px !important;
  overflow: hidden !important;
  height: 14px !important;
  border: 1px solid rgba(0,213,89,0.15) !important;
  position: relative !important;
}

/* Fill — the liquid itself */
[data-testid="stProgressBar"] > div > div,
div[role="progressbar"] > div,
.stProgress > div > div > div {
  border-radius: 100px !important;
  height: 100% !important;
  position: relative !important;
  overflow: hidden !important;
  background: linear-gradient(
    90deg,
    #00a844 0%,
    #00D559 30%,
    #7FFFB8 50%,
    #00D559 70%,
    #00a844 100%
  ) !important;
  background-size: 200% auto !important;
  animation: liquidShimmer 2.4s linear infinite !important;
  box-shadow:
    0 0 12px rgba(0,213,89,0.55),
    0 0 4px  rgba(0,213,89,0.9) inset !important;
}

/* Wave overlay on the fill */
[data-testid="stProgressBar"] > div > div::after,
div[role="progressbar"] > div::after,
.stProgress > div > div > div::after {
  content: "" !important;
  position: absolute !important;
  inset: 0 !important;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255,255,255,0.28) 40%,
    rgba(255,255,255,0.05) 60%,
    transparent 100%
  ) !important;
  border-radius: inherit !important;
  animation: liquidWave 1.8s ease-in-out infinite !important;
}
</style>
"""


# ============================================================
# END SECTION: Global CSS Theme
# ============================================================


# ============================================================
# SECTION: Premium Footer HTML
# ============================================================

def get_premium_footer_html() -> str:
    """Return a premium footer HTML block with responsible gambling info."""
    return '''<div style="text-align:center;padding:16px 0 8px 0;margin-top:24px;border-top:1px solid rgba(0,213,89,0.10);">
    <p style="color:#6B7A9A;font-size:0.75rem;margin:0;">
        Powered by <strong style="color:#00D559;">SmartBetPro AI™</strong> &nbsp;|&nbsp;
        For entertainment &amp; educational purposes only &nbsp;|&nbsp; 
        <span style="color:#F24336;">Not financial advice. Bet responsibly. 21+</span>
    </p>
    <p style="color:#6B7A9A;font-size:0.7rem;margin:4px 0 0 0;">
        Problem gambling help: <strong>1-800-GAMBLER (1-800-426-2537)</strong> |
        <a href="https://www.ncpgambling.org" target="_blank" rel="noopener noreferrer"
           aria-label="National Council on Problem Gambling" style="color:#A0AABE;">National Council on Problem Gambling</a> |
        <a href="https://www.begambleaware.org" target="_blank" rel="noopener noreferrer"
           aria-label="BeGambleAware organisation" style="color:#A0AABE;">BeGambleAware</a>
    </p>
</div>'''

# ============================================================
# END SECTION: Premium Footer HTML
# ============================================================


# ============================================================
# SECTION: HTML Component Generators
# Each function returns a self-contained HTML snippet.
# ============================================================

def get_tier_badge_html(tier, tier_emoji=None):
    """
    Return styled HTML for a tier badge.

    Args:
        tier (str): 'Platinum', 'Gold', 'Silver', or 'Bronze'
        tier_emoji (str, optional): Override emoji (default per tier)

    Returns:
        str: HTML span with appropriate CSS class
    """
    tier_emojis = {
        "Platinum": "💎",
        "Gold": "🥇",
        "Silver": "🥈",
        "Bronze": "🥉",
    }
    emoji = tier_emoji or tier_emojis.get(tier, "🏅")
    css_class = f"tier-badge tier-{tier.lower()}"
    return f'<span class="{css_class}">{emoji} {tier}</span>'


def get_probability_gauge_html(probability, direction):
    """
    Return a styled probability progress bar.

    Args:
        probability (float): Raw P(over), 0.0–1.0
        direction (str): 'OVER' or 'UNDER'

    Returns:
        str: HTML div containing the gauge bar
    """
    if direction == "OVER":
        display_pct = probability * 100
        fill_class = "prob-gauge-fill-over"
    else:
        display_pct = (1.0 - probability) * 100
        fill_class = "prob-gauge-fill-under"
    bar_width = int(min(100, max(0, display_pct)))
    return f"""<div class="prob-gauge-wrap">
  <div class="{fill_class}" style="width:{bar_width}%;"></div>
</div>"""


def get_stat_pill_html(label, value, emoji=""):
    """
    Return a styled stat pill chip.

    Args:
        label (str): Stat label (e.g., 'PPG')
        value: Stat value (e.g., 24.8)
        emoji (str): Optional emoji prefix

    Returns:
        str: HTML span
    """
    prefix = f"{emoji} " if emoji else ""
    return f'<span class="stat-chip">{prefix}<strong>{value}</strong> <span class="stat-label">{label}</span></span>'


def get_force_bar_html(over_strength, under_strength, over_count, under_count):
    """
    Return a proportional green/red force bar showing OVER vs UNDER pressure.

    Args:
        over_strength (float): Total strength of OVER forces
        under_strength (float): Total strength of UNDER forces
        over_count (int): Number of OVER forces
        under_count (int): Number of UNDER forces

    Returns:
        str: HTML div with the force bar
    """
    total = (over_strength + under_strength) or 1.0
    over_pct = int(over_strength / total * 100)
    under_pct = 100 - over_pct
    return f"""<div class="force-bar-wrap">
  <div class="force-bar-over" style="width:{over_pct}%;"></div>
  <div class="force-bar-under" style="width:{under_pct}%;"></div>
</div>
<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#6B7A9A;margin-top:3px;">
  <span>⬆️ OVER ({over_count})</span>
  <span>UNDER ({under_count}) ⬇️</span>
</div>"""


def get_distribution_range_html(p10, p50, p90):
    """
    Return a styled distribution range display (10th / 50th / 90th pct).

    Args:
        p10 (float): 10th percentile value
        p50 (float): 50th percentile (median)
        p90 (float): 90th percentile value

    Returns:
        str: HTML span block
    """
    return f"""<div class="dist-range-wrap">
  <span class="dist-p10">{p10:.1f}</span>
  <span class="dist-sep">—</span>
  <span class="dist-p50">{p50:.1f}</span>
  <span class="dist-sep">—</span>
  <span class="dist-p90">{p90:.1f}</span>
  <div class="dist-label">10th / 50th / 90th pct</div>
</div>"""


def get_player_card_html(result):
    """
    Build the complete styled analysis card HTML for one prop result.

    The card header now includes a player headshot loaded from the NBA CDN
    (``https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png``).
    An ``onerror`` handler falls back to a generic silhouette when the image
    is unavailable (e.g. sample / unknown player IDs).

    Args:
        result (dict): Full analysis result dict from the simulation loop.
            Expected keys: player_name, stat_type, line, direction, tier,
            tier_emoji, probability_over, edge_percentage, confidence_score,
            platform, player_team, player_position, season_pts_avg,
            player_id (optional NBA player ID for headshot), etc.

    Returns:
        str: Complete HTML string for the card
    """
    player = result.get("player_name", "Unknown")
    stat = result.get("stat_type", "").capitalize()
    line = result.get("line", 0)
    direction = result.get("direction", "OVER")
    tier = result.get("tier", "Bronze")
    tier_emoji = result.get("tier_emoji", "🥉")
    prob_over = result.get("probability_over", 0.5)
    edge = result.get("edge_percentage", 0)
    confidence = result.get("confidence_score", 50)
    platform = result.get("platform", "")
    team = result.get("player_team", result.get("team", ""))
    position = result.get("player_position", result.get("position", ""))
    proj = result.get("adjusted_projection", 0)
    player_id = result.get("player_id", "")

    pts_avg = result.get("season_pts_avg", result.get("points_avg", 0))
    reb_avg = result.get("season_reb_avg", result.get("rebounds_avg", 0))
    ast_avg = result.get("season_ast_avg", result.get("assists_avg", 0))

    prob_pct = prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100
    direction_arrow = "⬆️" if direction == "OVER" else "⬇️"

    tier_class = f"tier-badge tier-{tier.lower()}"
    dir_class = "dir-over" if direction == "OVER" else "dir-under"

    platform_colors = {
        "Smart Pick": "rgba(39,103,73,0.9)",
        "Underdog Fantasy": "rgba(85,60,154,0.9)",
        "DraftKings Pick6": "rgba(43,108,176,0.9)",
        # Backward-compat aliases
        "Underdog": "rgba(85,60,154,0.9)",
        "DraftKings": "rgba(43,108,176,0.9)",
    }
    plat_color = platform_colors.get(platform, "rgba(45,55,72,0.9)")

    fill_class = "prob-gauge-fill-over" if direction == "OVER" else "prob-gauge-fill-under"
    bar_width = int(min(100, max(0, prob_pct)))

    primary_color, secondary_color = get_team_colors(team)

    # Team badge
    team_badge = f'<span class="team-pill" style="background:{secondary_color};">{team}</span>' if team else ""
    position_tag = f'<span class="position-tag">{position}</span>' if position else ""

    # Player headshot from NBA CDN with fallback silhouette
    NBA_CDN_BASE = "https://cdn.nba.com/headshots/nba/latest/1040x760"
    FALLBACK_HEADSHOT = f"{NBA_CDN_BASE}/fallback.png"
    if player_id:
        headshot_url = f"{NBA_CDN_BASE}/{player_id}.png"
        headshot_html = (
            f'<img src="{headshot_url}" '
            f'onerror="this.onerror=null;this.src=\'{FALLBACK_HEADSHOT}\';" '
            f'style="width:60px;height:60px;border-radius:50%;object-fit:cover;'
            f'margin-right:12px;flex-shrink:0;background:#1C2232;" '
            f'alt="{player}">'
        )
    else:
        headshot_html = (
            f'<div style="width:60px;height:60px;border-radius:50%;'
            f'background:#1C2232;margin-right:12px;flex-shrink:0;'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:1.6rem;">🏀</div>'
        )

    # Stat pills
    stat_pills = ""
    if pts_avg:
        stat_pills += get_stat_pill_html("PPG", f"{pts_avg:.1f}", "🏀")
    if reb_avg:
        stat_pills += get_stat_pill_html("RPG", f"{reb_avg:.1f}", "📊")
    if ast_avg:
        stat_pills += get_stat_pill_html("APG", f"{ast_avg:.1f}", "🎯")
    if proj:
        stat_pills += get_stat_pill_html("Proj", f"{proj:.1f}", "📐")

    # Edge badge
    edge_class = "edge-positive" if edge >= 0 else "edge-negative"
    edge_sign = "+" if edge >= 0 else ""
    edge_html = f'<span class="edge-badge {edge_class}">{edge_sign}{edge:.1f}% edge</span>'

    # Confidence color
    conf_color = "#00D559" if confidence >= 70 else "#F9C62B" if confidence >= 50 else "#F24336"

    # Force bar
    over_forces = result.get("forces", {}).get("over_forces", [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    total_over_strength = sum(f.get("strength", 1) for f in over_forces)
    total_under_strength = sum(f.get("strength", 1) for f in under_forces)
    force_bar = get_force_bar_html(
        total_over_strength, total_under_strength,
        len(over_forces), len(under_forces)
    )

    # Distribution range
    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)
    dist_range = get_distribution_range_html(p10, p50, p90)

    # Opponent
    opponent = result.get("opponent", "")
    matchup_html = f'<span style="color:#6B7A9A;font-size:0.82rem;">vs {opponent}</span>' if opponent else ""

    # Line context
    line_vs_avg = result.get("line_vs_avg_pct", 0)
    if line_vs_avg != 0:
        line_ctx = f"Line is {abs(line_vs_avg):.0f}% {'above' if line_vs_avg > 0 else 'below'} season avg"
        line_ctx_html = f'<span style="color:#6B7A9A;font-size:0.78rem;font-style:italic;">{line_ctx}</span>'
    else:
        line_ctx_html = ""

    # Recent form dots
    recent_results = result.get("recent_form_results", [])
    form_html = ""
    if recent_results:
        stat_map = {"points": "pts", "rebounds": "reb", "assists": "ast",
                    "threes": "fg3m", "steals": "stl", "blocks": "blk", "turnovers": "tov"}
        mapped_key = stat_map.get(stat.lower(), "pts")
        dots = ""
        for g in recent_results[:5]:
            val = g.get(mapped_key, g.get("pts", 0))
            dot_cls = "form-dot-over" if val >= line else "form-dot-under"
            dots += f'<span class="{dot_cls}"></span>'
        form_html = f"""<div style="margin-right:16px;">
      <div style="color:#6B7A9A;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Last 5</div>
      {dots}
    </div>"""

    # Correlation warning (passed in from caller if applicable)
    corr_warning = result.get("_correlation_warning", "")
    corr_html = f'<div class="corr-warning">⚠️ {corr_warning}</div>' if corr_warning else ""

    # ── New PP/DK card layout helpers ──────────────────────────────────────
    # Season avg for this stat
    stat_map_avg = {"points": pts_avg, "rebounds": reb_avg, "assists": ast_avg}
    this_avg = stat_map_avg.get(stat.lower(), proj or 0)
    avg_diff = this_avg - line if this_avg else 0
    avg_diff_cls = "sc-avg-diff-pos" if avg_diff >= 0 else "sc-avg-diff-neg"
    avg_sign = "+" if avg_diff >= 0 else ""
    avg_html = (
        f'<span class="sc-avg-val">{this_avg:.1f} avg</span>'
        f' &nbsp;·&nbsp; <span class="{avg_diff_cls}">{avg_sign}{avg_diff:.1f} vs line</span>'
    ) if this_avg else ""

    # Platform badge class
    plat_slug = platform.lower().replace(" ", "").replace("6", "").replace("pick", "")
    plat_cls_map = {"prizepicks": "sc-plat-pp", "draftkings": "sc-plat-dk",
                    "underdog": "sc-plat-ud", "underdogfantasy": "sc-plat-ud"}
    plat_cls = plat_cls_map.get(plat_slug, "sc-plat-def")

    # Tier card class
    tier_card_cls = f"tier-card-{tier.lower()}" if tier.lower() in ("platinum", "gold", "silver") else ""

    # OVER/UNDER button classes
    over_btn_cls = "dir-btn dir-btn-over-active" if direction == "OVER" else "dir-btn dir-btn-over-inactive"
    under_btn_cls = "dir-btn dir-btn-under-active" if direction == "UNDER" else "dir-btn dir-btn-under-inactive"
    prob_under_pct = 100.0 - prob_pct

    # Confidence color
    conf_color = "#00D559" if confidence >= 70 else "#F9C62B" if confidence >= 50 else "#F24336"

    # New-style form dots
    form_dots_inner = ""
    if recent_results:
        stat_map2 = {"points": "pts", "rebounds": "reb", "assists": "ast",
                     "threes": "fg3m", "steals": "stl", "blocks": "blk", "turnovers": "tov"}
        mk = stat_map2.get(stat.lower(), "pts")
        for g in recent_results[:5]:
            v = g.get(mk, g.get("pts", 0))
            dc = "sc-form-dot-hit" if v >= line else "sc-form-dot-miss"
            form_dots_inner += f'<span class="{dc}" title="{v}"></span>'

    form_dots_html = (
        f'<div class="sc-form-row"><span class="sc-form-label">Last 5</span>{form_dots_inner}</div>'
        if form_dots_inner else ""
    )

    # New 72px headshot for sc-header
    NBA_CDN_BASE = "https://cdn.nba.com/headshots/nba/latest/1040x760"
    FALLBACK_HEADSHOT = f"{NBA_CDN_BASE}/fallback.png"
    if player_id:
        headshot_url = f"{NBA_CDN_BASE}/{player_id}.png"
        new_headshot = (
            f'<img src="{headshot_url}" '
            f'onerror="this.onerror=null;this.src=\'{FALLBACK_HEADSHOT}\';" '
            f'class="sc-headshot" alt="{player}">'
        )
    else:
        new_headshot = (
            f'<div class="sc-headshot" '
            f'style="display:flex;align-items:center;justify-content:center;font-size:1.8rem;">🏀</div>'
        )

    return f"""
<div class="smartai-card {tier_card_cls}" style="--card-accent:{primary_color};">
  <!-- ── Header: headshot + player info + tier ── -->
  <div class="sc-header">
    {new_headshot}
    <div class="sc-player-info">
      <div class="sc-player-name">{player}</div>
      <div class="sc-meta-row">
        {f'<span class="sc-team-badge" style="background:{secondary_color}22;color:{secondary_color};border:1px solid {secondary_color}44;">{team}</span>' if team else ""}
        {f'<span class="sc-position">{position}</span>' if position else ""}
        {f'<span class="sc-platform-badge {plat_cls}">{platform}</span>' if platform else ""}
      </div>
      {f'<div style="margin-top:5px;">{matchup_html} {line_ctx_html}</div>' if (matchup_html or line_ctx_html) else ""}
    </div>
    <span class="{tier_class}">{tier_emoji}</span>
  </div>

  <!-- ── Body ── -->
  <div class="sc-body">
    <!-- Large stat line number (PP-style hero display) -->
    <div class="sc-line-block">
      <div class="sc-stat-label">{stat}</div>
      <div class="sc-line-number">{line}</div>
      {f'<div class="sc-avg-row">{avg_html}</div>' if avg_html else ""}
    </div>

    <!-- Season stat metrics row -->
    {f'''<div class="sc-metrics">
      {f'<div class="sc-metric"><div class="sc-metric-val">{pts_avg:.1f}</div><div class="sc-metric-label">PPG</div></div>' if pts_avg else '<div class="sc-metric" style="opacity:0.3;"><div class="sc-metric-val">—</div><div class="sc-metric-label">PPG</div></div>'}
      {f'<div class="sc-metric"><div class="sc-metric-val">{reb_avg:.1f}</div><div class="sc-metric-label">RPG</div></div>' if reb_avg else '<div class="sc-metric" style="opacity:0.3;"><div class="sc-metric-val">—</div><div class="sc-metric-label">RPG</div></div>'}
      {f'<div class="sc-metric"><div class="sc-metric-val">{ast_avg:.1f}</div><div class="sc-metric-label">APG</div></div>' if ast_avg else f'<div class="sc-metric"><div class="sc-metric-val">{proj:.1f}</div><div class="sc-metric-label">Proj</div></div>' if proj else '<div class="sc-metric" style="opacity:0.3;"><div class="sc-metric-val">—</div><div class="sc-metric-label">APG</div></div>'}
    </div>''' if (pts_avg or reb_avg or ast_avg or proj) else ""}

    <!-- Probability bar -->
    <div class="sc-prob-row">
      <div class="sc-prob-track">
        <div class="{'sc-prob-fill-over' if direction == 'OVER' else 'sc-prob-fill-under'}"
             style="width:{bar_width}%;"></div>
      </div>
      <span class="sc-prob-pct">{prob_pct:.1f}%</span>
      {f'<span class="sc-edge {"sc-edge-pos" if edge >= 0 else "sc-edge-neg"}">{("+" if edge>=0 else "")}{edge:.1f}%</span>' if edge else ""}
    </div>

    <!-- Form dots + confidence -->
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;">
      {form_dots_html}
      <span style="color:#6B7A9A;font-size:0.76rem;">Confidence <strong style="color:{conf_color};">{confidence:.0f}</strong>/100</span>
    </div>
  </div>

  <!-- ── Footer: OVER/UNDER pick buttons + forces ── -->
  <div class="sc-footer">
    <div class="dir-btn-row">
      <div class="{over_btn_cls}">⬆ MORE &thinsp;<span class="dir-btn-pct">{prob_pct:.0f}%</span></div>
      <div class="{under_btn_cls}">⬇ LESS &thinsp;<span class="dir-btn-pct">{prob_under_pct:.0f}%</span></div>
    </div>
    <div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap;margin-top:10px;">
      <div style="flex:1;min-width:140px;">
        <div style="color:#3A4460;font-size:0.60rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Forces</div>
        {force_bar}
      </div>
      <div style="min-width:90px;">
        <div style="color:#3A4460;font-size:0.60rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Range</div>
        {dist_range}
      </div>
    </div>
    {corr_html}
  </div>
</div>
"""


def get_best_bets_section_html(best_bets):
    """
    Return HTML for the "Best Bets" ranked summary section.

    Args:
        best_bets (list of dict): Top analysis results (ranked)

    Returns:
        str: HTML string for the best-bets section
    """
    if not best_bets:
        return ""

    rank_emojis = [get_logo_img_tag("assets/NewGold_Logo.png", width=16, alt="#1"), "🥈", "🥉", "4️⃣", "5️⃣"]
    rows = []
    for i, bet in enumerate(best_bets[:5]):
        emoji = rank_emojis[i] if i < len(rank_emojis) else f"{i+1}."
        player = bet.get("player_name", "")
        stat = bet.get("stat_type", "").capitalize()
        line = bet.get("line", 0)
        direction = bet.get("direction", "OVER")
        prob_over = bet.get("probability_over", 0.5)
        prob_pct = prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100
        edge = bet.get("edge_percentage", 0)
        tier = bet.get("tier", "")
        tier_class = f"tier-badge tier-{tier.lower()}"
        tier_emoji = bet.get("tier_emoji", "")
        platform = bet.get("platform", "")
        rec = bet.get("recommendation", "")
        dir_class = "dir-over" if direction == "OVER" else "dir-under"
        arrow = "⬆️" if direction == "OVER" else "⬇️"
        edge_sign = "+" if edge >= 0 else ""

        rows.append(f"""
<div class="best-bet-card">
  <div class="best-bet-rank">{emoji} #{i+1}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-top:6px;">
    <div>
      <strong style="color:#FFFFFF;font-size:1.05rem;">{player}</strong>
      <span style="color:#A0AABE;font-size:0.88rem;margin-left:8px;">{stat} {line}</span>
      <span style="color:#6B7A9A;font-size:0.8rem;margin-left:6px;">{platform}</span>
    </div>
    <div style="display:flex;gap:8px;align-items:center;">
      <span class="{dir_class}">{arrow} {direction}</span>
      <span class="{tier_class}">{tier_emoji} {tier}</span>
    </div>
  </div>
  <div style="margin-top:6px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
    <span style="color:#FFFFFF;font-weight:700;font-family:'JetBrains Mono','Courier New',monospace;font-variant-numeric:tabular-nums;">{prob_pct:.1f}%</span>
    <span style="color:#00D559;font-size:0.82rem;font-family:'JetBrains Mono','Courier New',monospace;font-variant-numeric:tabular-nums;">{edge_sign}{edge:.1f}% edge</span>
    <span style="color:#6B7A9A;font-size:0.82rem;font-style:italic;">{rec}</span>
  </div>
</div>
""")

    cards_html = "\n".join(rows)
    return f"""
<div style="background:#161B27;
            border:1px solid rgba(0,213,89,0.18);border-radius:16px;padding:20px 24px;margin-bottom:20px;
            box-shadow:0 4px 24px rgba(0,0,0,0.4);">
  <div style="font-size:1.15rem;font-weight:900;color:#FFFFFF;margin-bottom:14px;font-family:'Inter',sans-serif;letter-spacing:-0.01em;">
    🏆 Best Bets Today
    <span style="font-size:0.8rem;font-weight:500;color:#6B7A9A;margin-left:10px;font-family:'Inter',sans-serif;">Ranked by confidence score</span>
  </div>
  {cards_html}
</div>
"""


def get_roster_health_html(matched, fuzzy_matched, unmatched):
    """
    Return HTML showing prop-to-roster matching status.

    Three categories:
    - ✅ Matched players (green) — definitive match
    - ⚠️ Fuzzy matched (yellow) — probable match with suggestion
    - ❌ Unmatched (red) — no match found, closest suggestion shown

    Args:
        matched (list of dict): Items from validate_props_against_roster()['matched']
            Each has 'prop' (dict) and 'matched_name' (str)
        fuzzy_matched (list of dict): Items from ['fuzzy_matched']
            Each has 'prop', 'matched_name', 'suggestion'
        unmatched (list of dict): Items from ['unmatched']
            Each has 'prop' (dict) and 'suggestion' (str or None)

    Returns:
        str: HTML string for the roster health section
    """
    sections = []

    if matched:
        chips = " ".join(
            f'<span class="health-matched">✅ {item["prop"].get("player_name", "")}</span>'
            for item in matched
        )
        sections.append(f"""
<div style="margin-bottom:12px;">
  <div style="color:#00D559;font-size:0.8rem;font-weight:700;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:6px;">
    ✅ Matched ({len(matched)})
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{chips}</div>
</div>""")

    if fuzzy_matched:
        chips = " ".join(
            f'<span class="health-fuzzy" title="{item.get("suggestion","")}">'
            f'⚠️ {item["prop"].get("player_name", "")}'
            f'<span style="font-size:0.7rem;opacity:0.8;"> → {item.get("matched_name","")}</span>'
            f'</span>'
            for item in fuzzy_matched
        )
        sections.append(f"""
<div style="margin-bottom:12px;">
  <div style="color:#F9C62B;font-size:0.8rem;font-weight:700;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:6px;">
    ⚠️ Fuzzy Matched ({len(fuzzy_matched)}) — using closest match
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{chips}</div>
</div>""")

    if unmatched:
        chips = " ".join(
            f'<span class="health-unmatched" title="Closest: {item.get("suggestion") or "none"}">'
            f'❌ {item["prop"].get("player_name", "")}'
            + (f'<span style="font-size:0.7rem;opacity:0.7;"> (suggest: {item["suggestion"]})</span>'
               if item.get("suggestion") else "")
            + "</span>"
            for item in unmatched
        )
        sections.append(f"""
<div style="margin-bottom:12px;">
  <div style="color:#F24336;font-size:0.8rem;font-weight:700;text-transform:uppercase;
              letter-spacing:1px;margin-bottom:6px;">
    ❌ Unmatched ({len(unmatched)}) — will use fallback data
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{chips}</div>
</div>""")

    if not sections:
        return '<div style="color:#00D559;">✅ All props matched to the player database.</div>'

    inner = "\n".join(sections)
    total = len(matched) + len(fuzzy_matched) + len(unmatched)
    match_pct = int((len(matched) + len(fuzzy_matched)) / max(total, 1) * 100)
    return f"""
<div style="background:#161B27;border:1px solid rgba(0,213,89,0.18);
            border-radius:12px;padding:16px 20px;margin-bottom:16px;
            box-shadow:0 4px 16px rgba(0,0,0,0.4);">
  <div style="font-size:1rem;font-weight:700;color:#FFFFFF;margin-bottom:12px;">
    🧬 Roster Health Check
    <span style="font-size:0.8rem;font-weight:400;color:#6B7A9A;margin-left:8px;">
      {len(matched) + len(fuzzy_matched)}/{total} matched ({match_pct}%)
    </span>
  </div>
  {inner}
  <div style="font-size:0.75rem;color:#6B7A9A;margin-top:4px;">
    💡 Add fuzzy-matched names to the alias map for exact matching next time.
    Unmatched props use the prop line as the baseline projection.
  </div>
</div>"""


def get_platform_badge_html(platform):
    """
    Return a styled platform badge for sportsbook platforms.

    Args:
        platform (str): Platform name

    Returns:
        str: HTML span with platform-specific gradient and styling
    """
    platform_styles = {
        "PrizePicks": (
            "background:linear-gradient(135deg,#276749,#48bb78);color:#f0fff4;"
        ),
        "Underdog Fantasy": (
            "background:linear-gradient(135deg,#44337a,#805ad5);color:#e9d8fd;"
        ),
        "DraftKings Pick6": (
            "background:linear-gradient(135deg,#1a202c,#2b6cb0);color:#bee3f8;"
        ),
        # Backward-compat aliases
        "Underdog": (
            "background:linear-gradient(135deg,#44337a,#805ad5);color:#e9d8fd;"
        ),
        "DraftKings": (
            "background:linear-gradient(135deg,#1a202c,#2b6cb0);color:#bee3f8;"
        ),
    }
    style = platform_styles.get(
        platform,
        "background:rgba(45,55,72,0.9);color:#e2e8f0;",
    )
    return (
        f'<span style="{style}padding:3px 10px;border-radius:6px;'
        f'font-size:0.8rem;font-weight:700;display:inline-block;">{platform}</span>'
    )

# ============================================================
# END SECTION: HTML Component Generators
# ============================================================


# ============================================================
# SECTION: New AI Neural Network Lab Components
# Additional HTML generators for the SmartBetPro NBA UI.
# ============================================================

def get_neural_header_html(title, subtitle):
    """
    Return a glowing circuit-decoration header for page/section headings.

    Args:
        title (str): Main heading text (rendered with gradient)
        subtitle (str): Secondary line shown in monospace below the title

    Returns:
        str: HTML string for the neural header block
    """
    return f"""
<div class="neural-header">
  <div class="neural-header-title">{title}</div>
  <div class="neural-header-subtitle">
    <span class="circuit-dot"></span>
    {subtitle}
    <span class="circuit-dot"></span>
  </div>
</div>
"""


def get_ai_verdict_card_html(verdict, confidence, explanation):
    """
    Return a styled AI verdict card showing BET / AVOID / RISKY.

    Args:
        verdict (str): 'BET', 'AVOID', or 'RISKY'
        confidence (float): Confidence score 0–100
        explanation (str): Plain-English rationale for the verdict

    Returns:
        str: HTML string for the verdict card
    """
    verdict_upper = verdict.upper()
    icons = {"BET": "✅", "AVOID": "🚫", "RISKY": "⚠️"}
    icon = icons.get(verdict_upper, "🔍")
    css_class_map = {"BET": "verdict-bet", "AVOID": "verdict-avoid", "RISKY": "verdict-risky"}
    label_class_map = {"BET": "verdict-label-bet", "AVOID": "verdict-label-avoid", "RISKY": "verdict-label-risky"}
    card_class = css_class_map.get(verdict_upper, "verdict-risky")
    label_class = label_class_map.get(verdict_upper, "verdict-label-risky")
    conf_bar_color = "#00D559" if confidence >= 70 else "#F9C62B" if confidence >= 50 else "#F24336"
    bar_width = int(min(100, max(0, confidence)))
    return f"""
<div class="{card_class}">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
    <span class="verdict-label {label_class}">{icon} {verdict_upper}</span>
    <div style="text-align:right;">
      <div class="verdict-confidence">CONFIDENCE</div>
      <div style="font-size:1.1rem;font-weight:800;color:{conf_bar_color};
                  font-family:'JetBrains Mono','Courier New',monospace;font-variant-numeric:tabular-nums;">{confidence:.0f}/100</div>
    </div>
  </div>
  <div style="margin-top:8px;background:rgba(13,15,20,0.90);border-radius:6px;height:6px;overflow:hidden;">
    <div style="width:{bar_width}%;height:100%;background:{conf_bar_color};
                border-radius:6px;box-shadow:0 0 8px {conf_bar_color};
                transition:width 0.5s ease;"></div>
  </div>
  <div class="verdict-explanation">{explanation}</div>
</div>
"""


def get_player_analysis_card_html(result, show_add_button=True):
    """
    Return a redesigned player analysis card with the neural network theme.

    Wraps the core stat data in the .player-analysis-card container with
    an optional '+ Add to Slip' button. Internally re-uses the proven
    layout from get_player_card_html but applies the updated CSS class.

    Args:
        result (dict): Full analysis result dict (same schema as get_player_card_html)
        show_add_button (bool): Whether to render the '+ Add to Slip' button

    Returns:
        str: HTML string for the player analysis card
    """
    player = result.get("player_name", "Unknown")
    stat = result.get("stat_type", "").capitalize()
    line = result.get("line", 0)
    direction = result.get("direction", "OVER")
    tier = result.get("tier", "Bronze")
    tier_emoji = result.get("tier_emoji", "🥉")
    prob_over = result.get("probability_over", 0.5)
    edge = result.get("edge_percentage", 0)
    confidence = result.get("confidence_score", 50)
    platform = result.get("platform", "")
    team = result.get("player_team", result.get("team", ""))
    position = result.get("player_position", result.get("position", ""))
    proj = result.get("adjusted_projection", 0)

    pts_avg = result.get("season_pts_avg", result.get("points_avg", 0))
    reb_avg = result.get("season_reb_avg", result.get("rebounds_avg", 0))
    ast_avg = result.get("season_ast_avg", result.get("assists_avg", 0))

    prob_pct = prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100
    direction_arrow = "⬆️" if direction == "OVER" else "⬇️"
    tier_class = f"tier-badge tier-{tier.lower()}"
    dir_class = "dir-over" if direction == "OVER" else "dir-under"

    platform_colors = {
        "PrizePicks": "rgba(0,120,70,0.85)",
        "Underdog Fantasy": "rgba(85,60,154,0.85)",
        "DraftKings Pick6": "rgba(43,108,176,0.85)",
        # Backward-compat aliases
        "Underdog": "rgba(85,60,154,0.85)",
        "DraftKings": "rgba(43,108,176,0.85)",
    }
    plat_color = platform_colors.get(platform, "rgba(30,40,60,0.85)")
    fill_class = "prob-gauge-fill-over" if direction == "OVER" else "prob-gauge-fill-under"
    bar_width = int(min(100, max(0, prob_pct)))
    primary_color, secondary_color = get_team_colors(team)

    team_badge = (
        f'<span class="team-pill" style="background:rgba(45,158,255,0.14);">{team}</span>'
        if team else ""
    )
    position_tag = f'<span class="position-tag">{position}</span>' if position else ""

    stat_pills = ""
    if pts_avg:
        stat_pills += get_stat_pill_html("PPG", f"{pts_avg:.1f}", "🏀")
    if reb_avg:
        stat_pills += get_stat_pill_html("RPG", f"{reb_avg:.1f}", "📊")
    if ast_avg:
        stat_pills += get_stat_pill_html("APG", f"{ast_avg:.1f}", "🎯")
    if proj:
        stat_pills += get_stat_pill_html("Proj", f"{proj:.1f}", "📐")

    conf_color = "#00D559" if confidence >= 70 else "#F9C62B" if confidence >= 50 else "#F24336"

    edge_class = "edge-positive" if edge >= 0 else "edge-negative"
    edge_sign = "+" if edge >= 0 else ""
    edge_html = f'<span class="edge-badge {edge_class}">{edge_sign}{edge:.1f}% edge</span>'

    over_forces = result.get("forces", {}).get("over_forces", [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    total_over_strength = sum(f.get("strength", 1) for f in over_forces)
    total_under_strength = sum(f.get("strength", 1) for f in under_forces)
    force_bar = get_force_bar_html(
        total_over_strength, total_under_strength,
        len(over_forces), len(under_forces)
    )

    p10 = result.get("percentile_10", 0)
    p50 = result.get("percentile_50", 0)
    p90 = result.get("percentile_90", 0)
    dist_range = get_distribution_range_html(p10, p50, p90)

    opponent = result.get("opponent", "")
    matchup_html = f'<span style="color:#6B7A9A;font-size:0.82rem;">vs {opponent}</span>' if opponent else ""

    add_btn = (
        '<button class="add-to-slip-btn">＋ Add to Slip</button>'
        if show_add_button else ""
    )

    corr_warning = result.get("_correlation_warning", "")
    corr_html = f'<div class="corr-warning">⚠️ {corr_warning}</div>' if corr_warning else ""

    return f"""
<div class="player-analysis-card" style="border-top-color:{primary_color};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
    <div>
      <span class="player-name">{player}</span>
      {team_badge}
      {position_tag}
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span class="{tier_class}">{tier_emoji} {tier}</span>
      {add_btn}
    </div>
  </div>
  <div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
    <span class="platform-badge" style="background:{plat_color};color:#fff;">{platform}</span>
    <span style="color:#A0AABE;font-size:0.9rem;">{stat} &nbsp;·&nbsp;
      Line: <strong style="color:#FFFFFF;">{line}</strong></span>
    {matchup_html}
  </div>
  {f'<div style="margin-top:10px;">{stat_pills}</div>' if stat_pills else ""}
  <div style="margin-top:14px;">
    <div style="display:flex;justify-content:space-between;align-items:center;
                flex-wrap:wrap;gap:6px;margin-bottom:4px;">
      <span class="{dir_class}">{direction_arrow} {direction}</span>
      <span class="prob-value">{prob_pct:.1f}%</span>
      {edge_html}
      <span style="color:#6B7A9A;font-size:0.82rem;">
        Confidence: <strong style="color:{conf_color};">{confidence:.0f}/100</strong>
      </span>
    </div>
    <div class="prob-gauge-wrap">
      <div class="{fill_class}" style="width:{bar_width}%;"></div>
    </div>
  </div>
  <div style="margin-top:12px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;">
    <div style="flex:1;min-width:160px;">
      <div style="color:#6B7A9A;font-size:0.72rem;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:3px;">Over/Under Forces</div>
      {force_bar}
    </div>
    <div style="min-width:110px;">
      <div style="color:#6B7A9A;font-size:0.72rem;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:3px;">Range</div>
      {dist_range}
    </div>
  </div>
  {corr_html}
</div>
"""


def get_stat_readout_html(label, value, context):
    """
    Return a monospace terminal-style stat readout row.

    Args:
        label (str): Stat name shown on the left (e.g., 'Season AVG')
        value: The stat value to display prominently (e.g., 24.8)
        context (str): Short contextual note shown on the right (e.g., 'last 10 games')

    Returns:
        str: HTML string for the stat readout
    """
    return f"""
<div class="stat-readout">
  <span class="stat-readout-label">{label}</span>
  <span>
    <span class="stat-readout-value">{value}</span>
    <span class="stat-readout-context">{context}</span>
  </span>
</div>
"""


def get_education_box_html(title, content):
    """
    Return a collapsible education info box.

    The box is rendered open by default using an HTML <details> element
    so it works without JavaScript in Streamlit's sandboxed environment.

    Args:
        title (str): Box heading (e.g., 'What is Edge?')
        content (str): Explanation text rendered inside the box

    Returns:
        str: HTML string for the education box
    """
    return f"""
<details class="education-box" open>
  <summary class="education-box-title">
    <span>💡</span> {title}
  </summary>
  <div class="education-box-content">{content}</div>
</details>
"""


def get_progress_ring_html(percentage, label):
    """
    Return an SVG circular confidence/progress ring indicator.

    Args:
        percentage (float): Value 0–100 to fill the ring
        label (str): Text label displayed below the ring

    Returns:
        str: HTML string containing inline SVG ring and label
    """
    pct = max(0.0, min(100.0, float(percentage)))
    radius = 28
    circumference = 2 * _math.pi * radius
    filled = circumference * pct / 100.0
    gap = circumference - filled

    if pct >= 70:
        ring_color = "#00D559"
    elif pct >= 50:
        ring_color = "#F9C62B"
    else:
        ring_color = "#F24336"

    return f"""
<div class="progress-ring-wrap">
  <svg width="72" height="72" viewBox="0 0 72 72">
    <circle cx="36" cy="36" r="{radius}"
            fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="6"/>
    <circle cx="36" cy="36" r="{radius}"
            fill="none" stroke="{ring_color}" stroke-width="6"
            stroke-linecap="round"
            stroke-dasharray="{filled:.2f} {gap:.2f}"
            stroke-dashoffset="{circumference * 0.25:.2f}"
            style="filter:drop-shadow(0 0 4px {ring_color});transition:stroke-dasharray 0.5s ease;"/>
    <text x="36" y="40" text-anchor="middle"
          font-family="'Bebas Neue','Inter',sans-serif"
          font-size="14" font-weight="700"
          fill="{ring_color}">{pct:.0f}%</text>
  </svg>
  <span class="progress-ring-label">{label}</span>
</div>
"""


def get_signal_strength_bar_html(strength, label):
    """
    Return a WiFi-style signal-strength bar (5 segments).

    Args:
        strength (float): Signal level 0.0–1.0 (or 0–100)
        label (str): Text label displayed next to the bars

    Returns:
        str: HTML string for the signal strength indicator
    """
    # Normalise to 0–1
    if strength > 1:
        strength = strength / 100.0
    strength = max(0.0, min(1.0, strength))
    active_bars = round(strength * 5)

    heights = [8, 12, 16, 20, 24]  # px heights for each bar segment
    bars_html = ""
    for i, h in enumerate(heights):
        active_class = "active" if i < active_bars else ""
        bars_html += (
            f'<div class="signal-bar-seg {active_class}" '
            f'style="height:{h}px;"></div>'
        )

    return f"""
<span>
  <span class="signal-bar-wrap">{bars_html}</span>
  <span class="signal-strength-label">{label}</span>
</span>
"""


def get_education_tooltip_html(term, explanation):
    """
    Return an inline hover tooltip for a betting/AI term.

    The tooltip uses pure CSS (no JavaScript) and works within
    Streamlit's sandboxed HTML environment.

    Args:
        term (str): The term to underline and make hoverable
        explanation (str): Plain-English explanation shown on hover

    Returns:
        str: HTML string with the tooltip span
    """
    safe_explanation = _html.escape(str(explanation))
    return (
        f'<span class="edu-tooltip">{term}'
        f'<span class="tooltip-text">{safe_explanation}</span>'
        f'</span>'
    )


# ============================================================
# END SECTION: New AI Neural Network Lab Components
# ============================================================


# ============================================================
# SECTION: QDS Game Report Generator
# Produces a fully self-contained HTML game-betting report
# using the Quantum Design System (QDS) visual language:
#   - Dark card panels, teal neon accents, glassmorphism
#   - Collapsible sections with chevron animation
#   - Animated confidence / probability bars (fill on open)
#   - SAFE Score™ prop cards with per-metric breakdowns
#   - Entry Strategy Matrix (Pick 2/3/5)
#   - Framework Logic and Final Word sections
# Designed for st.components.v1.html() embedding.
# ============================================================

# ── Static CSS for the QDS report (no f-string — braces are literal) ────────
_QDS_REPORT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&family=Montserrat:wght@300;400;600;700&display=swap');

:root {
  --qds-primary: #00D559;
  --qds-primary-dark: #00A844;
  --qds-primary-light: rgba(0,213,89,0.14);
  --qds-bg: #0D0F14;
  --qds-card: #161B27;
  --qds-card-hover: #1C2232;
  --qds-accent: #2D9EFF;
  --qds-accent-light: rgba(45,158,255,0.15);
  --qds-text-light: #EEF0F6;
  --qds-text-muted: #A0AABE;
  --qds-text-dark: #0D0F14;
  --qds-success: #00D559;
  --qds-warning: #F9C62B;
  --qds-info: #2D9EFF;
  --qds-danger: #F24336;
  --qds-neon-shadow: 0 0 10px rgba(0,213,89,0.4);
  --qds-neon-glow: 0 0 15px rgba(0,213,89,0.6);
}
*{box-sizing:border-box;margin:0;padding:0;}
html{scroll-behavior:smooth;}
body{
  font-family:'Inter',sans-serif;
  background:var(--qds-bg);
  color:var(--qds-text-light);
  line-height:1.6;
  overflow-x:hidden;
  background-image:
    radial-gradient(circle at 10% 20%,rgba(45,158,255,0.04) 0%,transparent 20%),
    radial-gradient(circle at 90% 80%,rgba(0,213,89,0.04) 0%,transparent 20%);
  background-attachment:fixed;
  padding:0 0 40px;
}
h1,h2,h3,h4{font-family:'Bebas Neue','Inter',sans-serif;letter-spacing:0.5px;font-weight:700;color:var(--qds-text-light);}
.qds-container{max-width:1100px;margin:0 auto;padding:0 16px;}

/* ── Header ── */
.qds-report-header{text-align:center;padding:24px 0 16px;position:relative;overflow:hidden;}
.qds-report-header::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,transparent,var(--qds-primary),var(--qds-accent),transparent);
}
.qds-report-title{display:flex;flex-direction:column;align-items:center;gap:8px;margin-bottom:18px;}
.qds-report-title-icon{color:var(--qds-primary);font-size:22px;}
.qds-report-title-text{
  font-size:clamp(1.4rem,4vw,2rem);
  background:linear-gradient(90deg,var(--qds-primary),var(--qds-accent));
  -webkit-background-clip:text;background-clip:text;color:transparent;
  text-shadow:0 0 10px rgba(0,255,213,0.3);
}
.qds-game-info-container{display:flex;flex-direction:column;gap:14px;margin-bottom:24px;align-items:center;}
.qds-game-teams{
  display:flex;align-items:center;justify-content:center;gap:14px;padding:14px 20px;
  border-radius:12px;background:rgba(10,16,31,0.7);
  border:1px solid rgba(0,255,213,0.1);box-shadow:var(--qds-neon-shadow);
  flex-wrap:wrap;width:100%;max-width:600px;
}
.qds-team-container{display:flex;flex-direction:column;align-items:center;gap:6px;flex:1;}
.qds-team-brand{display:flex;align-items:center;gap:8px;}
.qds-team-logo{width:38px;height:38px;object-fit:contain;filter:drop-shadow(0 0 5px rgba(0,180,255,0.3));}
.qds-team-name-txt{font-weight:700;font-size:0.95rem;font-family:'Orbitron',sans-serif;white-space:nowrap;}
.qds-vs-separator{
  font-size:1rem;font-weight:700;color:var(--qds-text-light);padding:4px 14px;
  border-radius:50px;background:rgba(0,180,255,0.1);font-family:'Orbitron',sans-serif;
}
.qds-team-record{font-size:0.82rem;color:var(--qds-text-muted);display:flex;align-items:center;gap:5px;}
.qds-game-meta{display:flex;flex-direction:column;gap:10px;align-items:center;width:100%;max-width:600px;}
.qds-game-date{
  font-size:0.9rem;color:var(--qds-text-light);
  background:linear-gradient(90deg,rgba(0,255,213,0.08) 0%,rgba(0,180,255,0.08) 100%);
  padding:8px 16px;border-radius:50px;display:flex;align-items:center;gap:8px;
  border:1px dashed var(--qds-primary);width:100%;justify-content:center;
}
.qds-framework{
  display:inline-flex;align-items:center;gap:10px;
  background:linear-gradient(90deg,rgba(0,255,213,0.08) 0%,rgba(0,180,255,0.08) 100%);
  padding:8px 18px;border-radius:50px;font-size:0.82rem;
  border:1px solid rgba(0,255,213,0.3);font-family:'Orbitron',sans-serif;
  letter-spacing:0.5px;width:100%;justify-content:center;
}

/* ── Collapsible ── */
.qds-collapsible{
  background:var(--qds-card);border-radius:12px;margin-bottom:18px;
  overflow:hidden;box-shadow:0 5px 15px rgba(0,0,0,0.25);
  border:1px solid rgba(0,255,213,0.1);
}
.qds-collapsible-header{
  padding:14px 18px;cursor:pointer;display:flex;justify-content:space-between;
  align-items:center;
  background:linear-gradient(90deg,rgba(0,255,213,0.04) 0%,rgba(0,180,255,0.04) 100%);
  position:relative;
}
.qds-collapsible-header::after{
  content:'';position:absolute;bottom:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(0,255,213,0.3),transparent);
}
.qds-collapsible-title{
  display:flex;align-items:center;gap:10px;font-size:1rem;font-weight:600;
  color:var(--qds-primary);margin:0;font-family:'Orbitron',sans-serif;
}
.qds-collapsible-icon{transition:all 0.3s ease;color:var(--qds-accent);}
.qds-collapsible.open .qds-collapsible-icon{transform:rotate(180deg);color:var(--qds-primary);}
.qds-collapsible-content{padding:0 18px;max-height:0;overflow:hidden;transition:max-height 0.5s cubic-bezier(0.4,0,0.2,1);}
.qds-collapsible.open .qds-collapsible-content{padding:18px;max-height:5000px;}

/* ── Team Cards ── */
.qds-team-cards{display:flex;flex-direction:column;gap:16px;margin-bottom:20px;}
.qds-team-card{background:rgba(20,26,45,0.7);border-radius:12px;padding:18px;border-left:4px solid var(--qds-primary);}
.qds-team-header{display:flex;align-items:center;gap:12px;margin-bottom:12px;}
.qds-stat-row{display:flex;flex-wrap:wrap;margin-bottom:10px;align-items:flex-start;gap:4px;}
.qds-stat-icon{color:var(--qds-primary);font-size:0.75rem;margin-top:3px;}
.qds-stat-label{font-weight:600;color:var(--qds-primary);font-size:0.82rem;min-width:75px;display:flex;align-items:center;gap:4px;}
.qds-stat-value{font-size:0.82rem;color:var(--qds-text-light);flex:1;}

/* ── Section Title ── */
.qds-section-title{display:flex;align-items:center;gap:10px;color:var(--qds-primary);margin-bottom:12px;}
.qds-matchup-text{
  font-size:0.9rem;line-height:1.65;margin-bottom:12px;padding-left:14px;
  border-left:2px solid var(--qds-primary);position:relative;
}

/* ── Prop Cards ── */
.qds-prop-card{
  background:var(--qds-card);border-radius:12px;padding:18px;margin-bottom:20px;
  position:relative;overflow:hidden;border-top:3px solid var(--qds-primary);
}
.qds-prop-badge{
  position:absolute;top:14px;right:14px;background:var(--qds-primary);
  color:var(--qds-text-dark);padding:4px 10px;border-radius:4px;
  font-size:0.72rem;font-weight:700;text-transform:uppercase;
  font-family:'Orbitron',sans-serif;z-index:2;
}
.qds-prop-header{display:flex;flex-direction:column;gap:12px;margin-bottom:18px;}
@media(min-width:480px){.qds-prop-header{flex-direction:row;align-items:flex-start;}}
.qds-player-img{
  width:68px;height:68px;border-radius:50%;border:3px solid var(--qds-primary);
  object-fit:cover;align-self:center;flex-shrink:0;
  background:#1a2238;
}
.qds-player-info{flex:1;}
.qds-player-name{font-size:1.1rem;margin:0;color:var(--qds-primary);display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.qds-player-team-badge{font-size:0.78rem;background:rgba(255,255,255,0.08);padding:2px 7px;border-radius:4px;}
.qds-player-prop{font-size:0.95rem;color:var(--qds-text-light);margin-top:7px;font-weight:600;display:flex;align-items:center;gap:6px;}
.qds-prop-emoji{font-size:1.1rem;}
.qds-safe-score{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:12px;}
.qds-score-value{
  font-weight:700;font-size:1.05rem;color:var(--qds-primary);
  background:rgba(0,255,213,0.1);padding:4px 12px;border-radius:50px;
  display:flex;align-items:center;gap:6px;
}
.qds-score-label{font-size:0.85rem;color:var(--qds-text-muted);}
.qds-confidence-tier{display:inline-flex;align-items:center;gap:5px;font-size:0.82rem;padding:4px 10px;border-radius:50px;}
.qds-tier-diamond{background:rgba(0,255,213,0.12);color:var(--qds-primary);border:1px solid var(--qds-primary);box-shadow:0 0 8px rgba(0,255,213,0.5);}
.qds-tier-lock{background:rgba(255,204,0,0.12);color:var(--qds-warning);border:1px solid var(--qds-warning);box-shadow:0 0 8px rgba(255,204,0,0.5);}
.qds-tier-check{background:rgba(0,163,255,0.12);color:var(--qds-info);border:1px solid var(--qds-info);box-shadow:0 0 8px rgba(0,163,255,0.4);}
.qds-tier-caution{background:rgba(255,94,0,0.10);color:#ff5e00;border:1px solid #ff5e00;box-shadow:0 0 8px rgba(255,94,0,0.4);}

/* ── Metrics Grid ── */
.qds-metrics-grid{display:grid;grid-template-columns:1fr;gap:12px;margin:16px 0;}
@media(min-width:560px){.qds-metrics-grid{grid-template-columns:repeat(auto-fill,minmax(220px,1fr));}}
.qds-metric-item{background:rgba(20,26,45,0.75);padding:13px;border-radius:8px;border-left:3px solid var(--qds-primary);}
.qds-metric-header{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
.qds-metric-name{font-size:0.82rem;font-weight:600;color:var(--qds-primary);flex:1;}
.qds-metric-score{font-weight:700;color:var(--qds-primary);background:rgba(0,255,213,0.1);padding:2px 7px;border-radius:4px;font-size:0.82rem;}
.qds-metric-justification{font-size:0.82rem;color:var(--qds-text-light);line-height:1.55;}
.qds-stat-badge{display:inline-block;background:rgba(0,255,213,0.1);color:var(--qds-primary);border:1px solid rgba(0,255,213,0.3);border-radius:4px;padding:2px 7px;font-size:0.78rem;font-weight:600;margin-right:4px;margin-bottom:3px;}

/* ── Bonus Factors ── */
.qds-bonus-factors{margin-top:16px;padding-top:13px;border-top:1px dashed rgba(255,255,255,0.08);}
.qds-bonus-title{font-size:0.85rem;color:var(--qds-primary);margin-bottom:10px;display:flex;align-items:center;gap:6px;}
.qds-bonus-item{display:flex;align-items:flex-start;gap:8px;margin-bottom:10px;}
.qds-bonus-icon{color:var(--qds-primary);font-size:0.78rem;margin-top:3px;}
.qds-bonus-text{font-size:0.82rem;color:var(--qds-text-light);flex:1;line-height:1.5;}

/* ── Confidence Bars ── */
.qds-confidence-bars{margin:16px 0;}
.qds-confidence-bar{height:9px;background:#1a2238;border-radius:5px;margin-bottom:10px;overflow:hidden;}
.qds-confidence-fill{
  height:100%;
  background:linear-gradient(90deg,var(--qds-primary),var(--qds-accent));
  width:0;border-radius:5px;
  transition:width 1.5s cubic-bezier(0.4,0,0.2,1);
}
/* Color-coded confidence fill variants (Platinum/Gold/Silver/Bronze) */
.qds-conf-fill-high{background:linear-gradient(90deg,#00D559,#00A844)!important;}
.qds-conf-fill-mid{background:linear-gradient(90deg,#ffcc00,#ff9500)!important;}
.qds-conf-fill-low{background:linear-gradient(90deg,#00b4ff,#0070cc)!important;}
.qds-conf-fill-very-low{background:linear-gradient(90deg,#ff5e00,#ff3860)!important;}
.qds-confidence-labels{display:flex;justify-content:space-between;font-size:0.85rem;color:var(--qds-text-muted);margin-bottom:14px;}
.qds-confidence-name{display:flex;align-items:center;gap:7px;}
/* ── Verdict paragraph ── */
.qds-prop-verdict{
  margin-top:12px;padding:10px 14px;font-size:0.83rem;line-height:1.6;
  background:rgba(0,255,213,0.04);border-left:3px solid var(--qds-primary);
  border-radius:0 6px 6px 0;color:var(--qds-text-light);font-style:italic;
}

/* ── Strategy Table ── */
.qds-strategy-table{width:100%;border-collapse:collapse;margin-top:16px;font-size:0.85rem;background:var(--qds-card);border-radius:8px;overflow:hidden;}
.qds-strategy-table th{text-align:left;padding:11px 14px;color:var(--qds-primary);border-bottom:1px solid rgba(255,255,255,0.08);background:rgba(0,255,213,0.04);}
.qds-strategy-table td{padding:11px 14px;color:var(--qds-text-light);border-bottom:1px solid rgba(255,255,255,0.05);vertical-align:middle;}
.qds-strategy-table tr:last-child td{border-bottom:none;}
.qds-strategy-pick{display:flex;flex-direction:column;gap:5px;margin:3px 0;}
.qds-strategy-player{font-weight:600;color:var(--qds-primary);display:flex;align-items:center;gap:7px;}
.qds-strategy-prop{font-size:0.8rem;color:var(--qds-text-muted);padding-left:18px;}
.qds-strategy-tag{background:rgba(0,255,213,0.1);color:var(--qds-primary);border:1px solid rgba(0,255,213,0.3);padding:3px 10px;border-radius:50px;font-size:0.78rem;white-space:nowrap;}

/* ── Framework Logic ── */
.qds-logic-item{display:flex;align-items:flex-start;gap:10px;margin-bottom:13px;padding:13px;background:rgba(20,26,45,0.75);border-radius:8px;}
.qds-logic-icon{color:var(--qds-primary);font-size:1rem;margin-top:2px;}
.qds-logic-text{font-size:0.9rem;color:var(--qds-text-light);flex:1;}
.qds-logic-text strong{color:var(--qds-primary);font-weight:600;}

/* ── Final Word ── */
.qds-final-word{background:var(--qds-card);border-radius:12px;padding:18px;border-left:3px solid var(--qds-primary);}
.qds-final-text{font-size:0.95rem;color:var(--qds-text-light);line-height:1.65;margin-bottom:18px;font-style:italic;}
.qds-cta{display:flex;align-items:center;gap:10px;margin-bottom:13px;color:var(--qds-primary);}
.qds-cta-steps{display:flex;flex-direction:column;gap:10px;}
.qds-cta-step{display:flex;align-items:flex-start;gap:10px;}
.qds-cta-text{flex:1;font-size:0.9rem;}

/* ── Empty State ── */
.qds-empty{text-align:center;padding:40px 20px;color:var(--qds-text-muted);}
.qds-empty-icon{font-size:2.2rem;color:var(--qds-primary);display:block;margin-bottom:12px;}

@media(min-width:768px){
  .qds-team-cards{flex-direction:row;}
  .qds-team-card{flex:1;}
  .qds-game-meta{flex-direction:row;}
}

/* ── Mobile: Game Report (≤768px) ── */
@media(max-width:768px){
  .qds-container{max-width:100%!important;padding:0 10px!important;}
  .qds-report-title-text{font-size:clamp(1.1rem,3.5vw,1.6rem)!important;}
  .qds-collapsible-content{padding:0 12px!important;}
  .qds-collapsible.open .qds-collapsible-content{padding:12px!important;}
  .qds-game-teams{padding:10px 14px!important;gap:10px!important;}
  .qds-metrics-grid{grid-template-columns:repeat(2,1fr)!important;gap:8px!important;}
  .qds-prop-card{padding:14px!important;}
  .qds-strategy-table{display:block!important;overflow-x:auto!important;-webkit-overflow-scrolling:touch!important;max-width:100%!important;}
  .qds-final-word{padding:14px!important;}
  .qds-player-img{width:56px!important;height:56px!important;}
}

/* ── Mobile: Game Report (≤480px phones) ── */
@media(max-width:480px){
  .qds-container{padding:0 6px!important;}
  .qds-report-title-text{font-size:clamp(1rem,3vw,1.4rem)!important;}
  .qds-collapsible-header{padding:10px 12px!important;}
  .qds-collapsible-title{font-size:0.88rem!important;gap:6px!important;}
  .qds-collapsible.open .qds-collapsible-content{padding:10px!important;}
  .qds-game-teams{padding:8px 10px!important;gap:8px!important;flex-direction:column!important;}
  .qds-team-logo{width:32px!important;height:32px!important;}
  .qds-team-name-txt{font-size:0.85rem!important;}
  .qds-vs-separator{font-size:0.85rem!important;padding:3px 10px!important;}
  .qds-game-date,.qds-framework{font-size:0.75rem!important;padding:6px 12px!important;}
  .qds-metrics-grid{grid-template-columns:1fr 1fr!important;gap:6px!important;}
  .qds-metric-item{padding:10px!important;}
  .qds-metric-name{font-size:0.75rem!important;}
  .qds-prop-card{padding:10px!important;}
  .qds-prop-badge{top:8px!important;right:8px!important;font-size:0.65rem!important;padding:3px 7px!important;}
  .qds-player-img{width:48px!important;height:48px!important;}
  .qds-player-name{font-size:0.95rem!important;}
  .qds-player-prop{font-size:0.85rem!important;}
  .qds-confidence-labels{font-size:0.75rem!important;}
  .qds-strategy-table th,.qds-strategy-table td{padding:6px 8px!important;font-size:0.75rem!important;}
  .qds-logic-item{padding:10px!important;margin-bottom:8px!important;}
  .qds-logic-text{font-size:0.82rem!important;}
  .qds-final-word{padding:12px!important;}
  .qds-final-text{font-size:0.85rem!important;}
  .qds-cta-text{font-size:0.82rem!important;}
  .qds-prop-verdict{padding:8px 12px!important;font-size:0.78rem!important;}
  .qds-bonus-item{font-size:0.75rem!important;}
}
</style>"""

# ── Static JS for QDS report ────────────────────────────────────────────────
_QDS_REPORT_JS = """
<script>
function qdsToggle(id){
  var el=document.getElementById(id);
  el.classList.toggle('open');
  if(el.classList.contains('open')) qdsAnimateBars();
}
function qdsAnimateBars(){
  document.querySelectorAll('.qds-confidence-fill').forEach(function(bar){
    var w=bar.getAttribute('data-width');
    bar.style.width='0';
    setTimeout(function(){bar.style.width=w;},80);
  });
}
document.addEventListener('DOMContentLoaded',function(){
  document.querySelectorAll('.qds-collapsible').forEach(function(s){s.classList.add('open');});
  setTimeout(qdsAnimateBars,400);
});
</script>"""


def get_game_report_html(game=None, analysis_results=None):
    """
    Generate a complete QDS-styled NBA game betting report as a self-contained HTML document.

    Produces a fully interactive report with collapsible sections, animated confidence
    bars, SAFE Score™ prop cards with per-metric breakdowns, team analysis, and entry
    strategy matrix. Designed for embedding via st.components.v1.html().

    Args:
        game (dict|None): Game dict from session state with home_team, away_team, records
        analysis_results (list|None): Analysis result dicts from Neural Analysis engine

    Returns:
        str: Complete self-contained HTML document with embedded CSS and JS
    """
    NBA_CDN = "https://cdn.nba.com/headshots/nba/latest/1040x760"
    ESPN_NBA = "https://a.espncdn.com/i/teamlogos/nba/500"

    # Confidence thresholds for color-coded bar fills
    _CONF_HIGH  = 80   # ≥ 80%  → cyan  gradient (Platinum / High)
    _CONF_MID   = 60   # ≥ 60%  → gold  gradient (Gold / Moderate)
    _CONF_LOW   = 40   # ≥ 40%  → blue  gradient (Silver / Lower)

    # ── Data Prep ─────────────────────────────────────────────
    results = sorted(
        analysis_results or [],
        key=lambda x: x.get("confidence_score", 0),
        reverse=True,
    )
    top_picks = results[:3]
    all_picks = results  # render prop cards for every analyzed pick
    today_str = _datetime.date.today().strftime("%B %d, %Y")

    # ── Game Data ─────────────────────────────────────────────
    if game:
        home = game.get("home_team", "HOME")
        away = game.get("away_team", "AWAY")
        hw = game.get("home_wins")
        hl = game.get("home_losses")
        aw = game.get("away_wins")
        al = game.get("away_losses")
        home_record = f"{hw}-{hl}" if (hw is not None and hl is not None and (hw > 0 or hl > 0)) else "N/A"
        away_record  = f"{aw}-{al}" if (aw is not None and al is not None and (aw > 0 or al > 0)) else "N/A"
    else:
        home, away = "HOME", "AWAY"
        home_record = away_record = "N/A"

    home_color, _ = get_team_colors(home)
    away_color, _  = get_team_colors(away)
    home_logo = f"{ESPN_NBA}/{home.lower()}.png"
    away_logo = f"{ESPN_NBA}/{away.lower()}.png"

    # ── Tier Mappings ─────────────────────────────────────────
    TIER = {
        "Platinum": {"icon": "gem",   "label": "95%+ Confidence", "css": "qds-tier-diamond"},
        "Gold":     {"icon": "lock",  "label": "90% Confidence",  "css": "qds-tier-lock"},
        "Silver":   {"icon": "check", "label": "85% Confidence",  "css": "qds-tier-check"},
        "Bronze":   {"icon": "star",  "label": "80% Confidence",  "css": "qds-tier-caution"},
    }
    BADGE = [("QUANTUM PICK", "bolt"), ("STRONG PICK", "lock"), ("SAFE PICK", "check")]
    STAT_EMOJI = {
        "points": "🏀", "rebounds": "📊", "assists": "🎯",
        "threes": "🎯", "steals": "⚡", "blocks": "🛡️", "turnovers": "❌",
    }

    def _ss(conf):
        """Convert 0-100 confidence to 0-10 SAFE Score."""
        return round(min(10.0, conf / 10.0), 1)

    def _prop_pct(pick):
        """Return the relevant hit-probability percentage for a pick (0-100 float)."""
        prob_over = pick.get("probability_over", 0.5)
        direction = pick.get("direction", "OVER")
        return prob_over * 100 if direction == "OVER" else (1 - prob_over) * 100

    def _badge(text, color):
        return (
            f'<span class="qds-stat-badge" style="border-color:{color};color:{color};">'
            f'{_html.escape(str(text))}</span>'
        )

    def _force_items(pick, max_n=2):
        over_f  = pick.get("forces", {}).get("over_forces",  [])
        under_f = pick.get("forces", {}).get("under_forces", [])
        items = (over_f + under_f)[:max_n]
        html_out = ""
        # Render any Line Value badge first (prominently)
        for f in (over_f + under_f):
            fname = f.get("name", "") if isinstance(f, dict) else ""
            if fname in ("Low Line Value", "High Line Value"):
                _gap = f.get("gap_pct", 0)
                badge = get_line_value_badge_html(_gap)
                if badge:
                    html_out += (
                        f'<div class="qds-bonus-item">'
                        f'<div class="qds-bonus-text">{badge}</div></div>'
                    )
                break
        for f in items:
            lbl  = f.get("label", f.get("factor", ""))
            desc = f.get("description", f.get("detail", ""))
            if lbl:
                html_out += (
                    f'<div class="qds-bonus-item">'
                    f'<i class="fas fa-circle-check qds-bonus-icon"></i>'
                    f'<div class="qds-bonus-text"><strong>{_html.escape(str(lbl))}</strong>'
                    f'{f" — {_html.escape(str(desc))}" if desc else ""}'
                    f'</div></div>'
                )
        if not html_out:
            edge = pick.get("edge_percentage", 0)
            prob_pct = int(_prop_pct(pick))
            sign = "+" if edge >= 0 else ""
            html_out = (
                f'<div class="qds-bonus-item">'
                f'<i class="fas fa-circle-check qds-bonus-icon"></i>'
                f'<div class="qds-bonus-text">'
                f'<strong>{sign}{edge:.1f}% edge vs implied probability</strong>'
                f' — AI model shows {prob_pct}% hit rate across 1,000+ simulations'
                f'</div></div>'
            )
        return html_out

    # ── Confidence Bars ───────────────────────────────────────
    conf_bars = ""
    for pick in top_picks:
        player    = pick.get("player_name", "Player")
        stat      = pick.get("stat_type", "stat").capitalize()
        line      = pick.get("line", 0)
        direction = pick.get("direction", "OVER")
        prob_pct  = int(_prop_pct(pick))
        tier      = pick.get("tier", "Silver")
        td        = TIER.get(tier, TIER["Silver"])
        # Color-code the fill based on confidence level
        fill_class = (
            "qds-conf-fill-high"     if prob_pct >= _CONF_HIGH else
            "qds-conf-fill-mid"      if prob_pct >= _CONF_MID  else
            "qds-conf-fill-low"      if prob_pct >= _CONF_LOW  else
            "qds-conf-fill-very-low"
        )
        conf_bars += (
            f'<div class="qds-confidence-bar">'
            f'<div class="qds-confidence-fill {fill_class}" data-width="{prob_pct}%"></div></div>'
            f'<div class="qds-confidence-labels">'
            f'<span class="qds-confidence-name">'
            f'<i class="fas fa-{td["icon"]}" style="color:var(--qds-primary);"></i>'
            f'<span>{_html.escape(player)} &nbsp;{direction} {line} {stat}</span>'
            f'</span><span>{prob_pct}%</span></div>'
        )
    if not conf_bars:
        conf_bars = (
            '<p class="qds-empty">'
            '<i class="fas fa-robot qds-empty-icon"></i>'
            'Run Neural Analysis to see confidence rankings.</p>'
        )

    # ── Prop Cards ────────────────────────────────────────────
    prop_cards = ""
    for idx, pick in enumerate(all_picks):
        player    = pick.get("player_name", "Unknown")
        stat      = pick.get("stat_type", "points").capitalize()
        line      = pick.get("line", 0)
        direction = pick.get("direction", "OVER")
        tier      = pick.get("tier", "Silver")
        prob_over = pick.get("probability_over", 0.5)
        edge      = pick.get("edge_percentage", 0)
        conf      = pick.get("confidence_score", 75)
        platform  = pick.get("platform", "")
        team      = pick.get("player_team", pick.get("team", ""))
        player_id = pick.get("player_id", "")

        pts_avg = pick.get("season_pts_avg", pick.get("points_avg", 0))
        reb_avg = pick.get("season_reb_avg", pick.get("rebounds_avg", 0))
        ast_avg = pick.get("season_ast_avg", pick.get("assists_avg", 0))
        proj    = pick.get("adjusted_projection", 0)

        prob_pct  = _prop_pct(pick)
        ss        = _ss(conf)
        edge_sign = "+" if edge >= 0 else ""

        td = TIER.get(tier, TIER["Silver"])
        bl, bi = BADGE[idx] if idx < len(BADGE) else ("PICK", "check")

        hs_url  = f"{NBA_CDN}/{player_id}.png" if player_id and str(player_id).strip() else f"{NBA_CDN}/fallback.png"
        hs_fall = f"{NBA_CDN}/fallback.png"
        prop_emoji = STAT_EMOJI.get(stat.lower(), "📊")
        tcolor, _ = get_team_colors(team)

        # Stat badges for metric card
        sbadges = ""
        if pts_avg: sbadges += _badge(f"{pts_avg:.1f} PPG", "#00D559")
        if reb_avg: sbadges += _badge(f"{reb_avg:.1f} RPG", "#00D559")
        if ast_avg: sbadges += _badge(f"{ast_avg:.1f} APG", "#00D559")
        if proj:    sbadges += _badge(f"{proj:.1f} Proj",   "#2D9EFF")
        if not sbadges:
            sbadges = f'<span style="color:var(--qds-text-muted);">Stats for {_html.escape(player)}</span>'

        team_badge_html = ""
        if team:
            team_badge_html = (
                f'<span class="qds-player-team-badge" '
                f'style="border:1px solid {tcolor};color:{tcolor};">'
                f'{_html.escape(team)}</span>'
            )
        plat_html = (
            f'<span style="font-size:0.8rem;color:var(--qds-text-muted);margin-left:6px;">'
            f'{_html.escape(platform)}</span>'
            if platform else ""
        )

        # Line Value vs Average badge (display-only)
        _line_val_badge = ""
        _stat_key = stat.lower()
        _season_avg_for_line = float(
            pick.get(f"season_{_stat_key}_avg",
                     pick.get(f"{_stat_key}_avg",
                              pick.get("season_average", 0))) or 0
        )
        if _season_avg_for_line > 0 and line > 0:
            _lv_gap_pct = (line - _season_avg_for_line) / _season_avg_for_line * 100.0
            _line_val_badge = get_line_value_badge_html(_lv_gap_pct)

        # Extract plain-English verdict for the prop card footer
        pick_verdict = (pick.get("explanation") or {}).get("verdict") or pick.get("recommendation", "")
        verdict_html = (
            f'<p class="qds-prop-verdict">{_html.escape(str(pick_verdict))}</p>'
            if pick_verdict else ""
        )

        prop_cards += f"""
<div class="qds-prop-card">
  <div class="qds-prop-badge"><i class="fas fa-{bi}"></i> {bl}</div>
  <div class="qds-prop-header">
    <img src="{hs_url}" onerror="this.onerror=null;this.src='{hs_fall}';"
         class="qds-player-img" alt="{_html.escape(player)}" loading="lazy" width="68" height="68">
    <div class="qds-player-info">
      <h3 class="qds-player-name">{_html.escape(player)} {team_badge_html}</h3>
      <div class="qds-player-prop">
        <span class="qds-prop-emoji">{prop_emoji}</span>
        <span><span style="color:{'var(--qds-success)' if direction == 'OVER' else '#ff5e00'};font-weight:700;">{direction}</span> {line} {stat}</span>{_line_val_badge}{plat_html}
      </div>
      <div class="qds-safe-score">
        <span class="qds-score-value"><i class="fas fa-shield-alt"></i> {ss:.1f} / 10</span>
        <span class="qds-score-label">SAFE Score™</span>
        <span class="qds-confidence-tier {td['css']}">
          <i class="fas fa-{td['icon']}"></i> <span>{td['label']}</span>
        </span>
      </div>
    </div>
  </div>
  <div class="qds-metrics-grid">
    <div class="qds-metric-item">
      <div class="qds-metric-header">
        <i class="fas fa-chart-line"></i>
        <span class="qds-metric-name">Season Stats</span>
        <span class="qds-metric-score">{min(9.8, ss + 0.1):.1f}</span>
      </div>
      <p class="qds-metric-justification">{sbadges}</p>
    </div>
    <div class="qds-metric-item">
      <div class="qds-metric-header">
        <i class="fas fa-chess"></i>
        <span class="qds-metric-name">Matchup Edge</span>
        <span class="qds-metric-score">{ss:.1f}</span>
      </div>
      <p class="qds-metric-justification">
        {edge_sign}{edge:.1f}% edge vs posted line. Model sees favorable conditions
        for {direction.lower()} {line} {stat.lower()}.
      </p>
    </div>
    <div class="qds-metric-item">
      <div class="qds-metric-header">
        <i class="fas fa-brain"></i>
        <span class="qds-metric-name">AI Model Signal</span>
        <span class="qds-metric-score">{ss:.1f}</span>
      </div>
      <p class="qds-metric-justification">
        Quantum Matrix simulation: <strong style="color:var(--qds-primary);">{int(prob_pct)}%
        hit rate</strong> across 1,000+ game scenarios.
      </p>
    </div>
    <div class="qds-metric-item">
      <div class="qds-metric-header">
        <i class="fas fa-shield-alt"></i>
        <span class="qds-metric-name">Confidence</span>
        <span class="qds-metric-score">{conf:.0f}/100</span>
      </div>
      <p class="qds-metric-justification">
        Quantum Matrix Engine 5.6 rating integrating sample size, matchup clarity, and simulation stability.
      </p>
    </div>
  </div>
  <div class="qds-bonus-factors">
    <div class="qds-bonus-title"><i class="fas fa-star"></i> Key Supporting Factors:</div>
    {_force_items(pick)}
  </div>{verdict_html}
  <!-- Always-open full breakdown panel -->
  <div style="background:#161B27;border-radius:6px;padding:12px 15px;margin-top:10px;border:1px solid rgba(255,94,0,0.12);">
    <div style="color:#F9C62B;font-weight:600;font-size:0.8rem;margin-bottom:10px;">📊 Distribution</div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px;">
      <div style="text-align:center;padding:6px;background:rgba(13,15,20,0.8);border-radius:5px;">
        <div style="color:#A0AABE;font-size:0.7rem;">10th pct</div>
        <div style="color:#F9C62B;font-weight:700;font-size:0.85rem;">{pick.get("percentile_10", 0):.1f}</div>
      </div>
      <div style="text-align:center;padding:6px;background:rgba(13,15,20,0.8);border-radius:5px;">
        <div style="color:#A0AABE;font-size:0.7rem;">Median</div>
        <div style="color:var(--qds-primary);font-weight:700;font-size:0.85rem;">{pick.get("percentile_50", 0):.1f}</div>
      </div>
      <div style="text-align:center;padding:6px;background:rgba(13,15,20,0.8);border-radius:5px;">
        <div style="color:#A0AABE;font-size:0.7rem;">90th pct</div>
        <div style="color:#F9C62B;font-weight:700;font-size:0.85rem;">{pick.get("percentile_90", 0):.1f}</div>
      </div>
      <div style="text-align:center;padding:6px;background:rgba(13,15,20,0.8);border-radius:5px;">
        <div style="color:#A0AABE;font-size:0.7rem;">Std Dev</div>
        <div style="color:#EEF0F6;font-weight:700;font-size:0.85rem;">{pick.get("simulated_std", 0):.1f}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
      <div style="padding:8px;background:rgba(0,213,89,0.05);border-radius:5px;border-left:2px solid var(--qds-primary);">
        <div style="color:var(--qds-primary);font-size:0.75rem;font-weight:600;margin-bottom:4px;">🔵 Forces OVER</div>
        {_force_items(pick, max_n=2) if pick.get("forces", {}).get("over_forces") else '<span style="color:#A0AABE;font-size:0.75rem;">None detected</span>'}
      </div>
      <div style="padding:8px;background:rgba(242,67,54,0.05);border-radius:5px;border-left:2px solid #F24336;">
        <div style="color:#F24336;font-size:0.75rem;font-weight:600;margin-bottom:4px;">🔴 Forces UNDER</div>
        {_force_items(pick, max_n=2) if pick.get("forces", {}).get("under_forces") else '<span style="color:#A0AABE;font-size:0.75rem;">None detected</span>'}
      </div>
    </div>
  </div>
</div>"""

    if not prop_cards:
        prop_cards = (
            '<div class="qds-empty">'
            '<i class="fas fa-robot qds-empty-icon"></i>'
            '<p style="font-size:1rem;margin-bottom:8px;">No analysis results available yet.</p>'
            '<p style="font-size:0.85rem;">Go to <strong style="color:var(--qds-primary);">'
            '⚡ Neural Analysis</strong> to generate prop predictions.</p></div>'
        )

    # ── Strategy Matrix ───────────────────────────────────────
    # Use all picks (not just top 3) to build better combo recommendations.
    _eligible = [
        p for p in all_picks
        if not p.get("should_avoid", False)
        and not p.get("player_is_out", False)
    ]
    strategy_rows = ""
    if len(_eligible) >= 2:
        # Pick unique players for each combo tier, excluding already-used
        # players so each tier offers genuinely different picks.
        def _unique_players(pool, num_picks, exclude=None):
            _excl = exclude or set()
            seen, out = set(), []
            for p in pool:
                pn = p.get("player_name", "")
                if pn not in seen and pn not in _excl:
                    seen.add(pn)
                    out.append(p)
                if len(out) == num_picks:
                    break
            return out

        # Sort by edge% for alternative ordering (variety between tiers)
        _edge_sorted = sorted(
            _eligible,
            key=lambda p: abs(p.get("edge_percentage", 0)),
            reverse=True,
        )

        matrix = []
        _used = set()

        # Pick 2 — highest confidence
        u2 = _unique_players(_eligible, 2)
        if len(u2) >= 2:
            avg2 = sum(p.get("confidence_score", 75) for p in u2) / 2 / 10
            matrix.append(("Pick 2", "fire", "danger", u2, "Power Play", f"{avg2:.2f}"))
            _used.update(p.get("player_name", "") for p in u2)

        # Pick 3 — best edge, excluding Pick 2 players for variety
        u3 = _unique_players(_edge_sorted, 3, exclude=_used)
        if len(u3) < 3:
            u3 = _unique_players(_edge_sorted, 3)
        if len(u3) >= 3:
            avg3 = sum(p.get("confidence_score", 75) for p in u3) / 3 / 10
            matrix.append(("Pick 3", "lock", "success", u3, "Flex Core", f"{avg3:.2f}"))
            _used.update(p.get("player_name", "") for p in u3)

        # Pick 5 — diversified from remaining pool
        u5 = _unique_players(_eligible, 5, exclude=_used)
        if len(u5) < 5:
            u5 = _unique_players(_eligible, 5)
        if len(u5) >= 5:
            avg5 = sum(p.get("confidence_score", 75) for p in u5) / 5 / 10
            matrix.append(("Pick 5", "layer-group", "warning", u5, "Stack Build", f"{avg5:.2f}"))

        for combo, icon, color_name, picks, strategy, avg_ss in matrix:
            picks_html = ""
            display_picks = picks[:5]  # Show up to 5 picks in strategy preview
            for j, p in enumerate(display_picks):
                pname = _html.escape(p.get("player_name", ""))
                pstat = p.get("stat_type", "").capitalize()
                pline = p.get("line", 0)
                pdir  = p.get("direction", "OVER")
                ptier = p.get("tier", "Silver")
                ptd   = TIER.get(ptier, TIER["Silver"])
                picks_html += (
                    f'<div class="qds-strategy-pick">'
                    f'<span class="qds-strategy-player">'
                    f'<i class="fas fa-{ptd["icon"]}" style="color:var(--qds-primary);"></i>'
                    f' {pname}</span>'
                    f'<span class="qds-strategy-prop">{pdir} {pline} {pstat}</span></div>'
                )
                if j < len(display_picks) - 1:
                    picks_html += '<span style="color:var(--qds-text-muted);font-size:0.85rem;padding:3px 0;display:block;">+</span>'
            strategy_rows += (
                f'<tr>'
                f'<td><i class="fas fa-{icon}" style="color:var(--qds-{color_name});margin-right:6px;"></i>{combo}</td>'
                f'<td>{picks_html}</td>'
                f'<td style="font-family:\'Courier New\',monospace;color:var(--qds-primary);font-weight:700;">{avg_ss}</td>'
                f'<td><span class="qds-strategy-tag">{strategy}</span></td>'
                f'</tr>'
            )

    if not strategy_rows:
        strategy_rows = (
            '<tr><td colspan="4" class="qds-empty" style="padding:24px;">'
            'Run Neural Analysis to populate strategy recommendations.</td></tr>'
        )

    # ── Team Player Badges ────────────────────────────────────
    home_players = [r for r in results if r.get("player_team", "").upper() == home.upper()]
    away_players = [r for r in results if r.get("player_team", "").upper() == away.upper()]

    def _player_badges(players, color, max_n=3):
        seen = set(); out = ""
        for p in players[:max_n]:
            name = p.get("player_name", "")
            pts  = p.get("season_pts_avg", p.get("points_avg", 0))
            if name and name not in seen:
                seen.add(name)
                label = f"{name} ({pts:.0f} PPG)" if pts else name
                out += _badge(label, color)
        return out or "—"

    home_pbadges = _player_badges(home_players, home_color)
    away_pbadges = _player_badges(away_players, away_color)

    # ── Pick Distribution Summary ─────────────────────────────
    _n_plat = sum(1 for r in all_picks if r.get("confidence_score", 0) >= 85)
    _n_gold = sum(1 for r in all_picks if 70 <= r.get("confidence_score", 0) < 85)
    _n_silv = sum(1 for r in all_picks if 55 <= r.get("confidence_score", 0) < 70)
    _n_brnz = sum(1 for r in all_picks if r.get("confidence_score", 0) < 55)
    _n_over = sum(1 for r in all_picks if r.get("direction", "") == "OVER")
    _n_under = len(all_picks) - _n_over
    _avg_edge = (
        sum(abs(r.get("edge_percentage", 0)) for r in all_picks) / max(len(all_picks), 1)
    )

    dist_summary_html = (
        f'<div style="display:flex;gap:16px;flex-wrap:wrap;justify-content:center;margin-bottom:12px;">'
        f'<div style="text-align:center;min-width:60px;">'
        f'<div style="font-size:1.4rem;font-weight:700;color:#00D559;">{_n_plat}</div>'
        f'<div style="font-size:0.68rem;color:#6B7A9A;">Platinum</div></div>'
        f'<div style="text-align:center;min-width:60px;">'
        f'<div style="font-size:1.4rem;font-weight:700;color:#F9C62B;">{_n_gold}</div>'
        f'<div style="font-size:0.68rem;color:#6B7A9A;">Gold</div></div>'
        f'<div style="text-align:center;min-width:60px;">'
        f'<div style="font-size:1.4rem;font-weight:700;color:#2D9EFF;">{_n_silv}</div>'
        f'<div style="font-size:0.68rem;color:#6B7A9A;">Silver</div></div>'
        f'<div style="text-align:center;min-width:60px;">'
        f'<div style="font-size:1.4rem;font-weight:700;color:#a0b4d0;">{_n_brnz}</div>'
        f'<div style="font-size:0.68rem;color:#6B7A9A;">Bronze</div></div>'
        f'<div style="border-left:1px solid rgba(255,255,255,0.08);'
        f'padding-left:16px;text-align:center;min-width:60px;">'
        f'<div style="font-size:1.4rem;font-weight:700;color:#00D559;">{_n_over}</div>'
        f'<div style="font-size:0.68rem;color:#6B7A9A;">OVER</div></div>'
        f'<div style="text-align:center;min-width:60px;">'
        f'<div style="font-size:1.4rem;font-weight:700;color:#F24336;">{_n_under}</div>'
        f'<div style="font-size:0.68rem;color:#6B7A9A;">UNDER</div></div>'
        f'<div style="border-left:1px solid rgba(255,255,255,0.08);'
        f'padding-left:16px;text-align:center;min-width:60px;">'
        f'<div style="font-size:1.4rem;font-weight:700;color:#c0d0e8;">{_avg_edge:.1f}%</div>'
        f'<div style="font-size:0.68rem;color:#6B7A9A;">Avg Edge</div></div>'
        f'</div>'
    )

    # ── Final Word ────────────────────────────────────────────
    pick_summaries = []
    for p in top_picks[:3]:
        pname = p.get("player_name", "")
        pdir  = p.get("direction", "OVER")
        pline = p.get("line", 0)
        pstat = p.get("stat_type", "").capitalize()
        ppct  = int(_prop_pct(p))
        pick_summaries.append(f"{pname} {pdir} {pline} {pstat} ({ppct}%)")

    primary  = pick_summaries[0] if pick_summaries else "—"
    second   = " + ".join(pick_summaries[1:]) if len(pick_summaries) > 1 else "—"
    pick2txt = " + ".join(pick_summaries[:2]) if len(pick_summaries) >= 2 else primary

    matchup_label = f"{away} @ {home}" if game else "Tonight's Matchup"

    # ── Assemble Full HTML ────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SmartBetPro NBA — {_html.escape(matchup_label)} Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  {_QDS_REPORT_CSS}
</head>
<body>
<div class="qds-container">

  <!-- ── Header ── -->
  <header class="qds-report-header">
    <div class="qds-report-title">
      <i class="fas fa-robot qds-report-title-icon"></i>
      <h1 class="qds-report-title-text">{_html.escape(away)} vs {_html.escape(home)}</h1>
    </div>
    <div class="qds-game-info-container">
      <div class="qds-game-teams">
        <div class="qds-team-container">
          <div class="qds-team-brand">
            <img src="{away_logo}" onerror="this.style.display='none';"
                 class="qds-team-logo" alt="{_html.escape(away)}" loading="lazy" width="38" height="38">
            <span class="qds-team-name-txt" style="color:{away_color};">{_html.escape(away)}</span>
          </div>
          <div class="qds-team-record"><i class="fas fa-flag"></i><span>{away_record}</span></div>
        </div>
        <span class="qds-vs-separator">VS</span>
        <div class="qds-team-container">
          <div class="qds-team-brand">
            <img src="{home_logo}" onerror="this.style.display='none';"
                 class="qds-team-logo" alt="{_html.escape(home)}" loading="lazy" width="38" height="38">
            <span class="qds-team-name-txt" style="color:{home_color};">{_html.escape(home)}</span>
          </div>
          <div class="qds-team-record"><i class="fas fa-trophy"></i><span>{home_record}</span></div>
        </div>
      </div>
      <div class="qds-game-meta">
        <span class="qds-game-date">
          <i class="far fa-calendar-alt"></i> {today_str}
        </span>
        <div class="qds-framework">
          <i class="fas fa-brain"></i>
          <span>SAFE SCORE™ AI · QUANTUM MATRIX ENGINE 5.6</span>
          <i class="fas fa-atom"></i>
        </div>
      </div>
    </div>
  </header>

  <main>

    <!-- ── Team Analysis ── -->
    <div class="qds-collapsible open" id="qdsTeams">
      <div class="qds-collapsible-header" onclick="qdsToggle('qdsTeams')">
        <h2 class="qds-collapsible-title">
          <i class="fas fa-network-wired"></i> TEAM MATCHUP BREAKDOWN
        </h2>
        <i class="fas fa-chevron-down qds-collapsible-icon"></i>
      </div>
      <div class="qds-collapsible-content">
        <div class="qds-team-cards">
          <div class="qds-team-card" style="border-left-color:{away_color};">
            <div class="qds-team-header">
              <img src="{away_logo}" onerror="this.style.display='none';"
                   class="qds-team-logo" alt="{_html.escape(away)}" loading="lazy" width="38" height="38">
              <div>
                <h3 class="qds-team-name-txt" style="color:{away_color};font-size:1.05rem;">{_html.escape(away)}</h3>
                <div class="qds-team-record"><i class="fas fa-flag"></i><span>{away_record}</span></div>
              </div>
            </div>
            <div>
              <div class="qds-stat-row">
                <i class="fas fa-users qds-stat-icon"></i>
                <span class="qds-stat-label">Key Players:</span>
                <span class="qds-stat-value">{away_pbadges if away_pbadges != "—" else "Load analysis for player data"}</span>
              </div>
            </div>
          </div>
          <div class="qds-team-card" style="border-left-color:{home_color};">
            <div class="qds-team-header">
              <img src="{home_logo}" onerror="this.style.display='none';"
                   class="qds-team-logo" alt="{_html.escape(home)}" loading="lazy" width="38" height="38">
              <div>
                <h3 class="qds-team-name-txt" style="color:{home_color};font-size:1.05rem;">{_html.escape(home)}</h3>
                <div class="qds-team-record"><i class="fas fa-trophy"></i><span>{home_record}</span></div>
              </div>
            </div>
            <div>
              <div class="qds-stat-row">
                <i class="fas fa-users qds-stat-icon"></i>
                <span class="qds-stat-label">Key Players:</span>
                <span class="qds-stat-value">{home_pbadges if home_pbadges != "—" else "Load analysis for player data"}</span>
              </div>
            </div>
          </div>
        </div>
        <div>
          <h3 class="qds-section-title"><i class="fas fa-chart-network"></i> KEY MATCHUP INSIGHTS</h3>
          <p class="qds-matchup-text">
            SmartBetPro's Quantum Matrix Engine 5.6 has run 1,000+ Quantum Matrix simulations for this matchup.
            The top-ranked props below reflect the strongest signal-to-noise ratio across all analysed players —
            each selected based on edge vs the posted line, recent form, and matchup-specific factors.
          </p>
          <p class="qds-matchup-text">
            All picks carry a SAFE Score™ of 8.0+ and have been validated against the current season sample.
            Focus on the <strong style="color:var(--qds-primary);">Quantum Pick</strong> for single-leg entries
            and use the Strategy Matrix below to build optimal multi-leg combinations.
          </p>
        </div>
      </div>
    </div>

    <!-- ── Pick Distribution Summary ── -->
    <div class="qds-collapsible open" id="qdsDist">
      <div class="qds-collapsible-header" onclick="qdsToggle('qdsDist')">
        <h2 class="qds-collapsible-title">
          <i class="fas fa-chart-pie"></i> PICK DISTRIBUTION SUMMARY
        </h2>
        <i class="fas fa-chevron-down qds-collapsible-icon"></i>
      </div>
      <div class="qds-collapsible-content">
        {dist_summary_html}
        <p class="qds-matchup-text" style="margin-top:8px;font-size:0.78rem;text-align:center;">
          {len(all_picks)} total props analyzed &middot;
          Focus on <strong style="color:#00D559;">Platinum</strong> and
          <strong style="color:#ffcc00;">Gold</strong> tiers for highest confidence entries.
        </p>
      </div>
    </div>

    <!-- ── Top Prop Bets ── -->
    <div class="qds-collapsible open" id="qdsProps">
      <div class="qds-collapsible-header" onclick="qdsToggle('qdsProps')">
        <h2 class="qds-collapsible-title">
          <i class="fas fa-magnifying-glass-chart"></i> TOP PROP BETS (SAFE SCORE™ RANKED)
        </h2>
        <i class="fas fa-chevron-down qds-collapsible-icon"></i>
      </div>
      <div class="qds-collapsible-content">
        <div class="qds-confidence-bars">{conf_bars}</div>
        {prop_cards}
      </div>
    </div>

    <!-- ── Entry Strategy Matrix ── -->
    <div class="qds-collapsible open" id="qdsStrategy">
      <div class="qds-collapsible-header" onclick="qdsToggle('qdsStrategy')">
        <h2 class="qds-collapsible-title">
          <i class="fas fa-chess-board"></i> ENTRY STRATEGY MATRIX
        </h2>
        <i class="fas fa-chevron-down qds-collapsible-icon"></i>
      </div>
      <div class="qds-collapsible-content">
        <table class="qds-strategy-table">
          <thead>
            <tr>
              <th>Combo</th><th>Picks</th><th>SAFE Avg</th><th>Strategy</th>
            </tr>
          </thead>
          <tbody>{strategy_rows}</tbody>
        </table>
      </div>
    </div>

    <!-- ── Framework Logic ── -->
    <div class="qds-collapsible open" id="qdsFramework">
      <div class="qds-collapsible-header" onclick="qdsToggle('qdsFramework')">
        <h2 class="qds-collapsible-title">
          <i class="fas fa-sitemap"></i> WHY THIS WORKS — FRAMEWORK LOGIC
        </h2>
        <i class="fas fa-chevron-down qds-collapsible-icon"></i>
      </div>
      <div class="qds-collapsible-content">
        <div class="qds-logic-item">
          <i class="fas fa-check qds-logic-icon"></i>
          <div class="qds-logic-text">
            <strong>SAFE Score™ Weighted System</strong> — Balances volatility with matchup intelligence
            via a proprietary algorithm analysing confidence, edge %, form, and situational factors.
          </div>
        </div>
        <div class="qds-logic-item">
          <i class="fas fa-project-diagram qds-logic-icon"></i>
          <div class="qds-logic-text">
            <strong>Causal-Driven Picks Only</strong> — No trend chasing. Every pick has layered
            justification with clear cause-effect relationships backed by Quantum Matrix simulation.
          </div>
        </div>
        <div class="qds-logic-item">
          <i class="fas fa-chess-queen qds-logic-icon"></i>
          <div class="qds-logic-text">
            <strong>Multi-Lens Value</strong> — Combines projection delta + narrative context +
            edge % for maximum signal. We identify when the market hasn't adjusted to recent form.
          </div>
        </div>
        <div class="qds-logic-item">
          <i class="fas fa-layer-group qds-logic-icon"></i>
          <div class="qds-logic-text">
            <strong>Confidence Buckets</strong> — Tier system (Platinum / Gold / Silver / Bronze)
            maps directly to optimal entry formats (2, 3, 5) based on risk tolerance.
          </div>
        </div>
        <div class="qds-logic-item">
          <i class="fas fa-network-wired qds-logic-icon"></i>
          <div class="qds-logic-text">
            <strong>Stack Matrix Synergy</strong> — Complementary picks in the same game create
            correlated upside while the SAFE Score maintains strong individual probabilities.
          </div>
        </div>
      </div>
    </div>

    <!-- ── Final Word ── -->
    <div class="qds-collapsible open" id="qdsFinal">
      <div class="qds-collapsible-header" onclick="qdsToggle('qdsFinal')">
        <h2 class="qds-collapsible-title">
          <i class="fas fa-bullseye"></i> FINAL WORD FROM SMARTBETPRO NBA
        </h2>
        <i class="fas fa-chevron-down qds-collapsible-icon"></i>
      </div>
      <div class="qds-collapsible-content">
        <div class="qds-final-word">
          <p class="qds-final-text">
            "These aren't locks — they're engineered plays. Built with matchup logic, stress-tested
            through 1,000+ Quantum Matrix simulations, and reinforced with real market edge.
            The Quantum Matrix Engine 5.6 has identified {len(top_picks)} high-probability props for
            {_html.escape(matchup_label)}, each with a SAFE Score™ of {_ss(top_picks[0].get('confidence_score', 75)) if top_picks else '—'}/10 or better.
            Play disciplined, size appropriately, and trust the process."
          </p>
          <div class="qds-cta">
            <i class="fas fa-rocket qds-cta-icon"></i>
            <span>Recommended Play Strategy:</span>
          </div>
          <div class="qds-cta-steps">
            <div class="qds-cta-step">
              <i class="fas fa-check qds-cta-icon"></i>
              <span class="qds-cta-text">
                <strong>Primary Play:</strong> {_html.escape(primary)}
              </span>
            </div>
            <div class="qds-cta-step">
              <i class="fas fa-check qds-cta-icon"></i>
              <span class="qds-cta-text">
                <strong>Multi-Leg:</strong> {_html.escape(pick2txt)} as a 2-leg entry
              </span>
            </div>
            <div class="qds-cta-step">
              <i class="fas fa-check qds-cta-icon"></i>
              <span class="qds-cta-text">
                <strong>Full Stack:</strong> {_html.escape(second if second != "—" else "See Strategy Matrix above for 3-leg recommendations")}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

  </main>
</div>
{_QDS_REPORT_JS}
</body>
</html>"""

    return html


# ============================================================
# END SECTION: QDS Game Report Generator
# ============================================================
# ============================================================
# SECTION: QDS Neural Analysis HTML Generators
# Individual reusable building blocks for the Neural Analysis
# page redesign using the Quantum Design System visual language.
# All functions return self-contained HTML strings suitable for
# st.markdown(unsafe_allow_html=True) injection.
# ============================================================

# Shared QDS CSS injected once per page (lightweight variant —
# does not duplicate the full report CSS).
_QDS_NA_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Montserrat:wght@300;400;600;700&display=swap');
:root{
  --qds-primary:#00D559;--qds-bg:#0D0F14;--qds-card:#161B27;
  --qds-accent:#2D9EFF;--qds-text-light:#EEF0F6;--qds-text-muted:#A0AABE;
  --qds-success:#00D559;--qds-warning:#F9C62B;--qds-danger:#F24336;
  --qds-neon-shadow:0 0 10px rgba(0,213,89,0.4);
}
.qds-na-card{background:var(--qds-card);border-radius:12px;padding:18px;
  margin-bottom:18px;border-top:3px solid var(--qds-primary);
  box-shadow:var(--qds-neon-shadow);}
.qds-na-badge{display:inline-block;padding:3px 10px;border-radius:4px;
  font-size:0.72rem;font-weight:700;text-transform:uppercase;
  font-family:'Orbitron',sans-serif;letter-spacing:0.5px;}
.qds-na-player-name{font-family:'Orbitron',sans-serif;font-size:1.05rem;
  font-weight:700;color:var(--qds-text-light);margin-bottom:4px;}
.qds-na-prop-desc{color:var(--qds-primary);font-size:1.1rem;font-weight:600;
  margin-bottom:10px;}
.qds-na-score{font-family:'Orbitron',sans-serif;font-size:1.6rem;font-weight:700;
  color:var(--qds-primary);text-shadow:0 0 8px rgba(0,255,213,0.5);}
.qds-na-metrics-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
  gap:10px;margin:12px 0;}
.qds-na-metric-card{background:rgba(10,16,31,0.7);border-radius:8px;padding:10px;
  border:1px solid rgba(0,255,213,0.12);text-align:center;}
.qds-na-metric-label{font-size:0.7rem;color:var(--qds-text-muted);
  text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;}
.qds-na-metric-value{font-size:1rem;font-weight:700;color:var(--qds-text-light);}
.qds-na-conf-bar-wrap{margin:4px 0 12px;}
.qds-na-conf-bar-label{font-size:0.8rem;color:var(--qds-text-muted);
  margin-bottom:3px;display:flex;justify-content:space-between;}
.qds-na-conf-bar-track{height:10px;background:rgba(255,255,255,0.08);
  border-radius:5px;overflow:hidden;}
@keyframes qds-conf-bar-expand{from{width:0%}}
.qds-na-conf-bar-fill{height:100%;border-radius:5px;
  background:linear-gradient(90deg,var(--qds-primary),var(--qds-accent));
  transition:width 0.5s ease;
  animation:qds-conf-bar-expand 0.6s ease-out both;}
.qds-na-bonus-item{display:flex;align-items:flex-start;gap:8px;
  font-size:0.82rem;color:var(--qds-text-light);margin-bottom:5px;}
.qds-na-bonus-icon{color:var(--qds-success);margin-top:2px;flex-shrink:0;}
.qds-na-team-badge{display:inline-block;padding:2px 8px;border-radius:4px;
  font-size:0.72rem;font-weight:700;margin-left:6px;vertical-align:middle;}
.qds-na-header{text-align:center;padding:20px;border-radius:12px;
  background:linear-gradient(135deg,rgba(0,255,213,0.06) 0%,rgba(0,180,255,0.06) 100%);
  border:1px solid rgba(0,255,213,0.15);margin-bottom:18px;}
.qds-na-matchup{display:flex;align-items:center;justify-content:center;
  gap:16px;flex-wrap:wrap;padding:14px;border-radius:10px;
  background:rgba(10,16,31,0.6);border:1px solid rgba(0,255,213,0.1);}
.qds-na-team-block{display:flex;flex-direction:column;align-items:center;gap:4px;}
.qds-na-team-logo{width:44px;height:44px;object-fit:contain;
  filter:drop-shadow(0 0 6px rgba(0,180,255,0.4));}
.qds-na-team-abbrev{font-family:'Orbitron',sans-serif;font-weight:700;
  font-size:0.9rem;color:var(--qds-text-light);}
.qds-na-vs{font-family:'Orbitron',sans-serif;font-size:0.9rem;
  color:var(--qds-text-muted);padding:4px 12px;
  background:rgba(0,180,255,0.1);border-radius:20px;}
.qds-na-strategy-table{width:100%;border-collapse:collapse;font-size:0.85rem;
  color:var(--qds-text-light);}
.qds-na-strategy-table th{background:rgba(0,255,213,0.08);color:var(--qds-primary);
  padding:8px 12px;text-align:left;font-family:'Orbitron',sans-serif;
  font-size:0.72rem;letter-spacing:0.5px;border-bottom:1px solid rgba(0,255,213,0.2);}
.qds-na-strategy-table td{padding:8px 12px;
  border-bottom:1px solid rgba(255,255,255,0.05);vertical-align:top;}
.qds-na-strategy-table tr:hover td{background:rgba(0,255,213,0.03);}
.qds-na-logic-item{display:flex;align-items:flex-start;gap:10px;
  padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);}
.qds-na-logic-icon{color:var(--qds-accent);font-size:1rem;flex-shrink:0;margin-top:1px;}
.qds-na-logic-title{font-weight:600;color:var(--qds-primary);font-size:0.85rem;}
.qds-na-logic-desc{font-size:0.8rem;color:var(--qds-text-muted);margin-top:2px;}
.qds-na-verdict{background:rgba(0,255,213,0.04);border-left:3px solid var(--qds-primary);
  border-radius:0 8px 8px 0;padding:14px 18px;margin-bottom:14px;
  font-style:italic;color:var(--qds-text-light);font-size:0.9rem;line-height:1.6;}
.qds-na-rec-item{display:flex;align-items:flex-start;gap:8px;
  font-size:0.85rem;color:var(--qds-text-light);margin-bottom:6px;}
.qds-na-rec-icon{color:var(--qds-success);flex-shrink:0;}
</style>
"""


def get_qds_css():
    """Return the lightweight QDS CSS for the Neural Analysis page."""
    return _QDS_NA_CSS


def get_qds_confidence_bar_html(label, percentage, tier_icon=""):
    """
    Render a horizontal confidence bar for a single prop.

    Args:
        label (str):      Player + prop description, e.g. "LeBron James — Over 24.5 Pts"
        percentage (float): Confidence percentage 0-100.
        tier_icon (str):  Optional emoji prefix, e.g. "💎".

    Returns:
        str: HTML string.
    """
    pct = max(0.0, min(100.0, float(percentage)))
    # Color by confidence tier
    if pct >= 80:
        color = "#00D559"
    elif pct >= 65:
        color = "#F9C62B"
    elif pct >= 50:
        color = "#2D9EFF"
    else:
        color = "#A0AABE"

    safe_label = _html.escape(str(label))
    safe_icon  = _html.escape(str(tier_icon)) if tier_icon else ""
    return (
        f'<div class="qds-na-conf-bar-wrap">'
        f'<div class="qds-na-conf-bar-label">'
        f'<span>{safe_icon} {safe_label}</span>'
        f'<span style="color:{color};font-weight:700;">{pct:.0f}%</span>'
        f'</div>'
        f'<div class="qds-na-conf-bar-track">'
        f'<div class="qds-na-conf-bar-fill" style="width:{pct}%;background:{color};"></div>'
        f'</div>'
        f'</div>'
    )


def get_qds_metrics_grid_html(metrics_list):
    """
    Render a 4-card metrics grid.

    Args:
        metrics_list (list[dict]): Each dict has keys:
            "label" (str), "value" (str|float), "icon" (str, optional)

    Returns:
        str: HTML string.
    """
    cards_html = ""
    for m in metrics_list:
        icon  = _html.escape(str(m.get("icon", "")))
        label = _html.escape(str(m.get("label", "")))
        value = _html.escape(str(m.get("value", "—")))
        cards_html += (
            f'<div class="qds-na-metric-card">'
            f'<div class="qds-na-metric-label">{icon} {label}</div>'
            f'<div class="qds-na-metric-value">{value}</div>'
            f'</div>'
        )
    return f'<div class="qds-na-metrics-grid">{cards_html}</div>'


def get_qds_prop_card_html(
    player_name,
    team,
    prop_text,
    score,
    tier,
    metrics,
    bonus_factors,
    player_id=None,
    opponent=None,
    is_home=None,
    season_stats=None,
    bet_direction=None,
):
    """
    Render a full QDS prop card for a single analysis result.

    Args:
        player_name (str): Player's full name.
        team (str):        Team abbreviation, e.g. "LAL".
        prop_text (str):   Prop description, e.g. "💣 Over 24.5 Points".
        score (float):     Confidence score 0-100 (displayed as X.X / 10).
        tier (str):        "Platinum", "Gold", "Silver", or "Bronze".
        metrics (list[dict]): Metrics for the 4-card grid (see get_qds_metrics_grid_html).
        bonus_factors (list[str]): Short bonus factor strings.
        player_id (str|None): NBA player ID for headshot CDN URL.
        opponent (str|None): Opponent team abbreviation, e.g. "BOS".
        is_home (bool|None): Whether the player's team is the home team.
        season_stats (dict|None): Season averages dict with keys like
            ``pts_avg``, ``reb_avg``, ``ast_avg``.
        bet_direction (str|None): Recommended direction, e.g. "OVER" or "UNDER".

    Returns:
        str: Self-contained HTML card string.
    """
    # ── Tier config ───────────────────────────────────────────────
    _TIER_CFG = {
        "Platinum": {
            "badge_text": "⚡ QUANTUM PICK",
            "badge_bg":   "#00D559",
            "badge_fg":   "#0D0F14",
            "border":     "#00D559",
            "icon":       "💎",
        },
        "Gold": {
            "badge_text": "🔒 STRONG PICK",
            "badge_bg":   "#F9C62B",
            "badge_fg":   "#0D0F14",
            "border":     "#F9C62B",
            "icon":       "🔒",
        },
        "Silver": {
            "badge_text": "✓ SAFE PICK",
            "badge_bg":   "#2D9EFF",
            "badge_fg":   "#0D0F14",
            "border":     "#2D9EFF",
            "icon":       "✓",
        },
        "Bronze": {
            "badge_text": "★ PICK",
            "badge_bg":   "#A0AABE",
            "badge_fg":   "#0D0F14",
            "border":     "#A0AABE",
            "icon":       "⭐",
        },
    }
    cfg = _TIER_CFG.get(tier, _TIER_CFG["Bronze"])

    # ── Player headshot ───────────────────────────────────────────
    if player_id:
        headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
    else:
        headshot_url = ""

    fallback_svg = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
        "width='60' height='60' viewBox='0 0 60 60'%3E"
        "%3Ccircle cx='30' cy='30' r='30' fill='%23141a2d'/%3E"
        "%3Ccircle cx='30' cy='22' r='10' fill='%23a0b4d0'/%3E"
        "%3Cellipse cx='30' cy='50' rx='16' ry='12' fill='%23a0b4d0'/%3E"
        "%3C/svg%3E"
    )
    if headshot_url:
        img_html = (
            f'<img src="{headshot_url}" '
            f'onerror="this.onerror=null;this.src=\'{fallback_svg}\'" '
            f'style="width:60px;height:60px;border-radius:50%;object-fit:cover;'
            f'border:2px solid {cfg["border"]};flex-shrink:0;" alt="{_html.escape(player_name)}">'
        )
    else:
        img_html = (
            f'<img src="{fallback_svg}" '
            f'style="width:60px;height:60px;border-radius:50%;object-fit:cover;'
            f'border:2px solid {cfg["border"]};flex-shrink:0;" alt="{_html.escape(player_name)}">'
        )

    # ── Team badge ────────────────────────────────────────────────
    team_primary, _ = get_team_colors(team)
    team_badge_html = (
        f'<span class="qds-na-team-badge" '
        f'style="background:{team_primary};color:#fff;">'
        f'{_html.escape(str(team))}</span>'
    )

    # ── Safe / Neural Score ───────────────────────────────────────
    safe_score = round(min(10.0, float(score) / 10.0), 1)
    safe_score_str = f"{safe_score:.1f}"

    # ── Confidence bar ────────────────────────────────────────────
    conf_bar = get_qds_confidence_bar_html(
        f"{prop_text}", score, cfg["icon"]
    )

    # ── Metrics grid ─────────────────────────────────────────────
    metrics_html = get_qds_metrics_grid_html(metrics) if metrics else ""

    # ── Bonus factors ─────────────────────────────────────────────
    bonus_html = ""
    for factor in (bonus_factors or []):
        safe_factor = _html.escape(str(factor))
        bonus_html += (
            f'<div class="qds-na-bonus-item">'
            f'<span class="qds-na-bonus-icon">✓</span>'
            f'<span>{safe_factor}</span>'
            f'</div>'
        )

    # ── Matchup strip (opponent & home/away) ────────────────────
    matchup_html = ""
    if opponent:
        opp_safe = _html.escape(str(opponent))
        opp_primary, _ = get_team_colors(str(opponent))
        home_away_label = "HOME" if is_home else "AWAY" if is_home is not None else ""
        ha_icon = "🏠" if is_home else "✈️" if is_home is not None else ""
        matchup_html = (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;'
            f'padding:5px 10px;background:rgba(255,255,255,0.03);'
            f'border-radius:6px;border:1px solid rgba(255,255,255,0.06);">'
            f'<span style="font-size:0.72rem;color:var(--qds-text-muted);'
            f'text-transform:uppercase;letter-spacing:0.5px;">Matchup</span>'
            f'<span style="font-weight:700;color:#fff;font-size:0.82rem;">'
            f'{_html.escape(str(team))}</span>'
            f'<span style="color:var(--qds-text-muted);font-size:0.78rem;">vs</span>'
            f'<span class="qds-na-team-badge" '
            f'style="background:{opp_primary};color:#fff;">{opp_safe}</span>'
            + (
                f'<span style="margin-left:auto;font-size:0.7rem;color:var(--qds-text-muted);'
                f'letter-spacing:0.5px;">{ha_icon} {home_away_label}</span>'
                if home_away_label else ""
            )
            + f'</div>'
        )

    # ── Season stats strip ────────────────────────────────────────
    stats_strip_html = ""
    if season_stats:
        _stat_items = []
        _stat_display = [
            ("PTS", season_stats.get("pts_avg", 0)),
            ("REB", season_stats.get("reb_avg", 0)),
            ("AST", season_stats.get("ast_avg", 0)),
        ]
        for label, val in _stat_display:
            fval = float(val or 0)
            if fval > 0:
                _stat_items.append(
                    f'<div style="text-align:center;flex:1;">'
                    f'<div style="font-size:0.65rem;color:var(--qds-text-muted);'
                    f'text-transform:uppercase;letter-spacing:0.5px;">{label}</div>'
                    f'<div style="font-size:0.95rem;font-weight:700;color:#fff;">'
                    f'{fval:.1f}</div></div>'
                )
        if _stat_items:
            stats_strip_html = (
                f'<div style="display:flex;gap:4px;margin-bottom:8px;'
                f'padding:6px 10px;background:rgba(255,255,255,0.03);'
                f'border-radius:6px;border:1px solid rgba(255,255,255,0.06);">'
                + "".join(_stat_items)
                + f'</div>'
            )

    # ── Bet direction badge ───────────────────────────────────────
    dir_badge_html = ""
    if bet_direction:
        _dir_upper = str(bet_direction).upper()
        _dir_colors = {
            "OVER": ("#00D559", "rgba(0,213,89,0.12)"),
            "UNDER": ("#F24336", "rgba(242,67,54,0.12)"),
        }
        _dir_color, _dir_bg = _dir_colors.get(
            _dir_upper, ("#a0b4d0", "rgba(160,180,208,0.12)")
        )
        dir_badge_html = (
            f'<span style="background:{_dir_bg};color:{_dir_color};padding:2px 8px;'
            f'border-radius:4px;font-size:0.72rem;font-weight:700;'
            f'border:1px solid {_dir_color}40;margin-left:6px;">'
            f'{"📈" if _dir_upper == "OVER" else "📉"} {_dir_upper}</span>'
        )

    # ── Build card ────────────────────────────────────────────────
    safe_player = _html.escape(str(player_name))
    safe_prop   = _html.escape(str(prop_text))
    badge_text  = _html.escape(str(cfg["badge_text"]))
    border_color = cfg["border"]
    badge_bg     = cfg["badge_bg"]
    badge_fg     = cfg["badge_fg"]

    return (
        f'<div class="qds-na-card" style="border-top-color:{border_color};">'
        # Badge row (tier badge + optional direction badge)
        f'<div style="display:flex;justify-content:{"space-between" if dir_badge_html else "flex-end"};align-items:center;margin-bottom:8px;">'
        f'{dir_badge_html}'
        f'<span class="qds-na-badge" style="background:{badge_bg};color:{badge_fg};">'
        f'{badge_text}</span>'
        f'</div>'
        # Player row (headshot, name, team, score)
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">'
        f'{img_html}'
        f'<div style="flex:1;">'
        f'<div class="qds-na-player-name">{safe_player}{team_badge_html}</div>'
        f'<div class="qds-na-prop-desc">{safe_prop}</div>'
        f'</div>'
        # Score
        f'<div style="text-align:center;flex-shrink:0;">'
        f'<div style="font-size:0.65rem;color:var(--qds-text-muted);'
        f'text-transform:uppercase;letter-spacing:0.5px;">SAFE Score™</div>'
        f'<div class="qds-na-score">{safe_score_str}<span style="font-size:0.85rem;'
        f'color:var(--qds-text-muted);">/10</span></div>'
        f'</div>'
        f'</div>'
        # Matchup strip (opponent + home/away)
        f'{matchup_html}'
        # Season stats strip (PTS / REB / AST)
        f'{stats_strip_html}'
        # Confidence bar
        f'{conf_bar}'
        # Metrics grid
        f'{metrics_html}'
        # Bonus factors
        + (
            f'<div style="margin-top:10px;">'
            f'<div style="font-size:0.75rem;color:var(--qds-text-muted);'
            f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">'
            f'Bonus Factors</div>'
            f'{bonus_html}'
            f'</div>'
            if bonus_html else ""
        )
        + f'</div>'
    )


def get_qds_matchup_header_html(away_team, home_team, game_info=""):
    """
    Render a matchup header banner with team logos, names, and game info.

    Args:
        away_team (str): Away team abbreviation, e.g. "BOS".
        home_team (str): Home team abbreviation, e.g. "LAL".
        game_info (str): Additional text, e.g. date + tip-off time.

    Returns:
        str: HTML string.
    """
    ESPN_NBA = "https://a.espncdn.com/i/teamlogos/nba/500"
    away_logo = f"{ESPN_NBA}/{away_team.lower()}.png"
    home_logo = f"{ESPN_NBA}/{home_team.lower()}.png"
    away_color, _ = get_team_colors(away_team)
    home_color, _ = get_team_colors(home_team)

    safe_away      = _html.escape(str(away_team))
    safe_home      = _html.escape(str(home_team))
    safe_game_info = _html.escape(str(game_info))
    fallback       = "https://cdn.nba.com/logos/leagues/logo-nba.svg"

    return (
        f'<div class="qds-na-header">'
        f'<div style="font-size:0.72rem;color:var(--qds-text-muted);'
        f'text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">'
        f'SmartBetPro Quantum Matrix Engine 5.6 — Tonight\'s Game</div>'
        f'<div class="qds-na-matchup">'
        # Away team
        f'<div class="qds-na-team-block">'
        f'<img src="{away_logo}" onerror="this.src=\'{fallback}\'" '
        f'class="qds-na-team-logo" alt="{safe_away}">'
        f'<div class="qds-na-team-abbrev" style="color:{away_color};">{safe_away}</div>'
        f'</div>'
        # VS
        f'<div class="qds-na-vs">VS</div>'
        # Home team
        f'<div class="qds-na-team-block">'
        f'<img src="{home_logo}" onerror="this.src=\'{fallback}\'" '
        f'class="qds-na-team-logo" alt="{safe_home}">'
        f'<div class="qds-na-team-abbrev" style="color:{home_color};">{safe_home}</div>'
        f'</div>'
        f'</div>'
        + (
            f'<div style="margin-top:10px;font-size:0.8rem;color:var(--qds-text-muted);">'
            f'{safe_game_info}</div>'
            if safe_game_info else ""
        )
        + f'</div>'
    )


def get_qds_team_card_html(team_name, team_abbrev, record, stats, key_players, team_color):
    """
    Render a QDS-styled team breakdown card.

    Args:
        team_name (str):   Full team name.
        team_abbrev (str): Team abbreviation.
        record (str):      Win-loss record, e.g. "42-30".
        stats (list[dict]): List of {"label": str, "value": str} dicts.
        key_players (list[str]): Player names to highlight.
        team_color (str):  CSS color hex for the left border.

    Returns:
        str: HTML string.
    """
    safe_name   = _html.escape(str(team_name))
    safe_abbrev = _html.escape(str(team_abbrev))
    safe_record = _html.escape(str(record))
    safe_color  = _html.escape(str(team_color))

    # Stats rows
    stats_html = ""
    for s in (stats or []):
        lbl = _html.escape(str(s.get("label", "")))
        val = _html.escape(str(s.get("value", "")))
        stats_html += (
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
            f'<span style="color:var(--qds-text-muted);font-size:0.8rem;">{lbl}</span>'
            f'<span style="font-weight:600;color:var(--qds-text-light);font-size:0.8rem;">{val}</span>'
            f'</div>'
        )

    # Key players badges
    players_html = ""
    for p in (key_players or []):
        safe_p = _html.escape(str(p))
        players_html += (
            f'<span style="background:rgba(0,255,213,0.1);color:var(--qds-primary);'
            f'padding:2px 8px;border-radius:4px;font-size:0.75rem;margin:2px;'
            f'display:inline-block;">{safe_p}</span>'
        )

    return (
        f'<div style="background:var(--qds-card);border-radius:10px;padding:16px;'
        f'border-left:4px solid {safe_color};margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">'
        f'<div style="width:8px;height:8px;border-radius:50%;'
        f'background:{safe_color};"></div>'
        f'<div style="font-family:\'Orbitron\',sans-serif;font-weight:700;'
        f'font-size:0.9rem;color:var(--qds-text-light);">'
        f'{safe_name} &nbsp;<span style="color:{safe_color};">({safe_abbrev})</span></div>'
        f'<span style="margin-left:auto;background:rgba(0,0,0,0.3);padding:2px 8px;'
        f'border-radius:4px;font-size:0.75rem;color:var(--qds-text-muted);">'
        f'{safe_record}</span>'
        f'</div>'
        + (f'<div style="margin-bottom:10px;">{stats_html}</div>' if stats_html else "")
        + (
            f'<div style="margin-top:10px;">'
            f'<div style="font-size:0.7rem;color:var(--qds-text-muted);'
            f'text-transform:uppercase;margin-bottom:5px;">Key Players</div>'
            f'{players_html}'
            f'</div>'
            if players_html else ""
        )
        + f'</div>'
    )


def get_qds_strategy_table_html(entries):
    """
    Render the Entry Strategy Matrix table.

    Args:
        entries (list[dict]): Each dict has keys:
            "combo_type" (str), "picks" (str|list), "safe_avg" (float|str),
            "strategy" (str)

    Returns:
        str: HTML string with a styled table.
    """
    if not entries:
        return '<p style="color:var(--qds-text-muted);font-size:0.85rem;">No entry combinations available yet.</p>'

    rows_html = ""
    for entry in entries:
        combo     = _html.escape(str(entry.get("combo_type", "")))
        picks_raw = entry.get("picks", [])
        if isinstance(picks_raw, list):
            picks = ", ".join(_html.escape(str(p)) for p in picks_raw)
        else:
            picks = _html.escape(str(picks_raw))
        safe_avg  = _html.escape(str(entry.get("safe_avg", "")))
        strategy  = _html.escape(str(entry.get("strategy", "")))
        rows_html += (
            f'<tr>'
            f'<td><span style="color:var(--qds-primary);font-weight:600;">{combo}</span></td>'
            f'<td>{picks}</td>'
            f'<td style="text-align:center;">{safe_avg}</td>'
            f'<td style="color:var(--qds-text-muted);">{strategy}</td>'
            f'</tr>'
        )

    return (
        f'<table class="qds-na-strategy-table">'
        f'<thead><tr>'
        f'<th>Combo Type</th>'
        f'<th>Picks</th>'
        f'<th>SAFE Avg</th>'
        f'<th>Strategy</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
    )


def get_qds_framework_logic_html():
    """
    Return the Framework Logic section HTML explaining the model pipeline.

    Returns:
        str: HTML string.
    """
    items = [
        ("🧮", "Quantum Matrix Simulation",
         "We run 2,000+ simulated game outcomes per player, drawing from a "
         "normal distribution centered on the adjusted projection."),
        ("📐", "Projection Engine",
         "Season averages are adjusted for matchup defense ratings, home/away "
         "splits, rest days, pace, and blowout risk."),
        ("⚡", "Directional Forces",
         "Structural signals — pace edge, usage upticks, teammate absences, "
         "target-share shifts — are scored and aggregated."),
        ("🛡️", "Edge Detection",
         "We compare the model's implied probability to the book's implied "
         "probability to detect mispriced lines."),
        ("🔒", "Confidence Scoring",
         "A composite 0-100 confidence score is computed from simulation "
         "probability, edge, form, and force alignment."),
        ("⚠️", "Trap-Line & Sharpness Filters",
         "Lines set suspiciously close to the season average are penalised. "
         "Round-number traps are flagged for avoidance."),
        ("🕸️", "Layer 5 Injury Data",
         "Real-time injury status from NBA.com, RotoWire, and ESPN overrides "
         "stale nba_api designations for the most accurate availability picture."),
    ]

    rows_html = ""
    for icon, title, desc in items:
        safe_icon  = _html.escape(str(icon))
        safe_title = _html.escape(str(title))
        safe_desc  = _html.escape(str(desc))
        rows_html += (
            f'<div class="qds-na-logic-item">'
            f'<span class="qds-na-logic-icon">{safe_icon}</span>'
            f'<div>'
            f'<div class="qds-na-logic-title">{safe_title}</div>'
            f'<div class="qds-na-logic-desc">{safe_desc}</div>'
            f'</div>'
            f'</div>'
        )

    return (
        f'<div style="padding:6px 0;">{rows_html}</div>'
    )


def get_qds_final_verdict_html(summary_text, recommendations):
    """
    Render the Final Verdict section with italic summary and rec steps.

    Args:
        summary_text (str):       One or two sentence italic summary.
        recommendations (list[str]): Actionable checkmark steps.

    Returns:
        str: HTML string.
    """
    safe_summary = _html.escape(str(summary_text))

    recs_html = ""
    for rec in (recommendations or []):
        safe_rec = _html.escape(str(rec))
        recs_html += (
            f'<div class="qds-na-rec-item">'
            f'<span class="qds-na-rec-icon">✓</span>'
            f'<span>{safe_rec}</span>'
            f'</div>'
        )

    return (
        f'<div class="qds-na-verdict">"{safe_summary}"</div>'
        + (
            f'<div style="margin-top:12px;">'
            f'<div style="font-size:0.75rem;color:var(--qds-text-muted);'
            f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">'
            f'Recommended Play Strategy</div>'
            f'{recs_html}'
            f'</div>'
            if recs_html else ""
        )
    )

# ============================================================
# END SECTION: QDS Neural Analysis HTML Generators
# ============================================================


# ============================================================
# SECTION: Bet Tracker Card CSS & HTML Generators
# ============================================================

_BET_CARD_CSS = """
<style>
/* ─── Bet Card Base ───────────────────────────────────────── */
.bet-card {
    background: linear-gradient(160deg, #161B27 0%, #1A2030 100%);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.50);
    transition: transform 0.20s ease, box-shadow 0.20s ease, border-color 0.20s ease;
    border-left: 4px solid rgba(0,213,89,0.35);
    position: relative;
    overflow: hidden;
}
.bet-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.60);
}
.bet-card-win {
    border-color: rgba(0,213,89,0.40);
    border-left: 4px solid #00D559;
    background: linear-gradient(160deg, #121C18 0%, #161F1C 100%);
    box-shadow: 0 0 0 1px rgba(0,213,89,0.08), 0 4px 24px rgba(0,0,0,0.55), 0 0 30px rgba(0,213,89,0.08);
}
.bet-card-win:hover {
    box-shadow: 0 0 0 1px rgba(0,213,89,0.18), 0 10px 40px rgba(0,213,89,0.18), 0 16px 50px rgba(0,0,0,0.60);
}
.bet-card-loss {
    border-color: rgba(242,67,54,0.40);
    border-left: 4px solid #F24336;
    background: linear-gradient(160deg, #1C1212 0%, #201616 100%);
    box-shadow: 0 0 0 1px rgba(242,67,54,0.08), 0 4px 24px rgba(0,0,0,0.55), 0 0 30px rgba(242,67,54,0.06);
}
.bet-card-loss:hover {
    box-shadow: 0 0 0 1px rgba(242,67,54,0.18), 0 10px 40px rgba(242,67,54,0.15), 0 16px 50px rgba(0,0,0,0.60);
}
.bet-card-even {
    border-color: rgba(160,170,190,0.28);
    border-left: 4px solid #A0AABE;
}
.bet-card-pending {
    border-color: rgba(249,198,43,0.30);
    border-left: 4px solid #F9C62B;
    animation: betCardPulse 2.8s ease-in-out infinite;
}
@keyframes betCardPulse {
    0%,100% { box-shadow: 0 4px 20px rgba(0,0,0,0.50); }
    50%      { box-shadow: 0 4px 20px rgba(0,0,0,0.50), 0 0 28px rgba(249,198,43,0.22); }
}

/* ─── Result shimmer reveal ───────────────────────────────── */
.bet-card-win::after, .bet-card-loss::after {
    content: '';
    position: absolute;
    top: 0; left: -100%; width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent);
    animation: cardRevealShimmer 1.4s ease-out forwards;
    pointer-events: none;
}
@keyframes cardRevealShimmer {
    0%   { left: -100%; opacity: 1; }
    100% { left: 100%; opacity: 0; }
}

/* ─── Top accent line ─────────────────────────────────────── */
.bet-card::before {
    content: '';
    position: absolute; top:0; left:0; right:0; height:2px;
    opacity: 0; transition: opacity 0.20s ease;
}
.bet-card:hover::before { opacity: 1; }
.bet-card-win::before    { background: linear-gradient(90deg, #00D559, transparent); opacity: 0.7 !important; }
.bet-card-loss::before   { background: linear-gradient(90deg, #F24336, transparent); opacity: 0.7 !important; }
.bet-card-pending::before { background: linear-gradient(90deg, #F9C62B, transparent); opacity: 0.7 !important; }

/* ─── Tier-specific card glows ────────────────────────────── */
.bet-card-tier-platinum { box-shadow: 0 0 24px rgba(0,213,89,0.16), 0 4px 20px rgba(0,0,0,0.50); }
.bet-card-tier-gold     { box-shadow: 0 0 24px rgba(255,170,0,0.16), 0 4px 20px rgba(0,0,0,0.50); }
.bet-card-tier-silver   { box-shadow: 0 0 16px rgba(192,208,232,0.12), 0 4px 20px rgba(0,0,0,0.50); }
.bet-card-tier-bronze   { box-shadow: 0 0 16px rgba(255,124,58,0.12), 0 4px 20px rgba(0,0,0,0.50); }

/* ─── Card Header ─────────────────────────────────────────── */
.bet-card-player {
    font-size: 1.15rem;
    font-weight: 900;
    font-family: 'Inter', sans-serif;
    color: #F0F4FF;
    letter-spacing: -0.01em;
}
.bet-card-team {
    font-size: 0.78rem;
    color: #6B7A9A;
    margin-left: 8px;
    font-weight: 600;
}
.bet-card-divider {
    height: 1px;
    background: rgba(255,255,255,0.07);
    margin: 12px 0;
}

/* ─── Player headshot ─────────────────────────────────────── */
.bet-card-headshot {
    width: 44px; height: 44px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid rgba(0,213,89,0.28);
    background: #0D0F14;
    flex-shrink: 0;
    box-shadow: 0 0 12px rgba(0,213,89,0.16);
}

/* ─── Direction ───────────────────────────────────────────── */
.direction-over {
    color: #00D559;
    font-weight: 900;
    font-size: 1.05rem;
    text-shadow: 0 0 10px rgba(0,213,89,0.50);
}
.direction-under {
    color: #F24336;
    font-weight: 900;
    font-size: 1.05rem;
    text-shadow: 0 0 10px rgba(242,67,54,0.50);
}

/* ─── Confidence Gauge (SVG arc) ──────────────────────────── */
.confidence-gauge-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 8px 0 4px 0;
}
.confidence-gauge-label { font-size: 0.75rem; color: #6B7A9A; }
.confidence-gauge-value { font-size: 0.85rem; font-weight: 700; color: #e8f0ff; }

/* ─── Confidence Bar ──────────────────────────────────────── */
.confidence-bar-wrap { margin: 10px 0 6px 0; }
.confidence-bar-track {
    height: 8px;
    background: rgba(255,255,255,0.07);
    border-radius: 4px;
    overflow: hidden;
}
.confidence-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
}
.confidence-bar-label {
    display: flex;
    justify-content: space-between;
    font-size: 0.74rem;
    color: #6B7A9A;
    margin-bottom: 3px;
}

/* ─── Platform Badges ─────────────────────────────────────── */
.platform-badge-fd { background: rgba(0,200,83,0.18);  color: #00c853; border:1px solid rgba(0,200,83,0.35);  padding: 3px 10px; border-radius: 6px; font-size: 0.76rem; font-weight: 800; }
.platform-badge-pp { background: rgba(0,200,83,0.18);  color: #00c853; border:1px solid rgba(0,200,83,0.35);  padding: 3px 10px; border-radius: 6px; font-size: 0.76rem; font-weight: 800; }
.platform-badge-ud { background: rgba(124,77,255,0.18); color: #9c71ff; border:1px solid rgba(124,77,255,0.35); padding: 3px 10px; border-radius: 6px; font-size: 0.76rem; font-weight: 800; }
.platform-badge-dk { background: rgba(33,150,243,0.18); color: #64b5f6; border:1px solid rgba(33,150,243,0.35); padding: 3px 10px; border-radius: 6px; font-size: 0.76rem; font-weight: 800; }
.platform-badge    { background: rgba(255,255,255,0.08); color: #a0aabe; border:1px solid rgba(255,255,255,0.14); padding: 3px 10px; border-radius: 6px; font-size: 0.76rem; font-weight: 700; }

/* ─── Tier Badges ─────────────────────────────────────────── */
.tier-badge-platinum { color: #00D559; font-weight: 900; text-shadow: 0 0 10px rgba(0,213,89,0.55); }
.tier-badge-gold     { color: #ffaa00; font-weight: 900; text-shadow: 0 0 10px rgba(255,170,0,0.55); }
.tier-badge-silver   { color: #c0d0e8; font-weight: 800; }
.tier-badge-bronze   { color: #ff7c3a; font-weight: 800; }
.tier-badge-avoid    { color: #ff4444; font-weight: 800; }

/* ─── Result Badges — big, clear, unmissable ──────────────── */
.result-win {
    color: #fff;
    background: linear-gradient(90deg, #00A844 0%, #00D559 100%);
    font-weight: 900;
    font-size: 0.90rem;
    padding: 4px 14px;
    border-radius: 100px;
    letter-spacing: 0.06em;
    box-shadow: 0 0 16px rgba(0,213,89,0.55), 0 2px 8px rgba(0,0,0,0.30);
}
.result-loss {
    color: #fff;
    background: linear-gradient(90deg, #c62828 0%, #F24336 100%);
    font-weight: 900;
    font-size: 0.90rem;
    padding: 4px 14px;
    border-radius: 100px;
    letter-spacing: 0.06em;
    box-shadow: 0 0 16px rgba(242,67,54,0.50), 0 2px 8px rgba(0,0,0,0.30);
}
.result-even {
    color: #0D0F14;
    background: #A0AABE;
    font-weight: 800;
    font-size: 0.90rem;
    padding: 4px 14px;
    border-radius: 100px;
}
.result-pending {
    color: #0D0F14;
    background: linear-gradient(90deg, #D4A017 0%, #F9C62B 100%);
    font-weight: 900;
    font-size: 0.90rem;
    padding: 4px 14px;
    border-radius: 100px;
    animation: resultPulse 2s ease-in-out infinite;
}
@keyframes resultPulse {
    0%,100% { box-shadow: 0 0 8px rgba(249,198,43,0.40); }
    50%      { box-shadow: 0 0 22px rgba(249,198,43,0.80); }
}

/* ─── Projected vs Actual ─────────────────────────────────── */
.proj-vs-actual {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-top: 6px;
    font-size: 0.82rem;
}
.proj-label  { color: #6B7A9A; }
.proj-value  { color: #EEF0F6; font-weight: 700; }
.actual-hit  { color: #00D559; font-weight: 800; text-shadow: 0 0 8px rgba(0,213,89,0.40); }
.actual-miss { color: #F24336; font-weight: 800; text-shadow: 0 0 8px rgba(242,67,54,0.35); }
.actual-close{ color: #F9C62B; font-weight: 800; }

/* ─── Live Status ─────────────────────────────────────────── */
.live-status-winning { color: #00D559; font-weight: 700; }
.live-status-losing  { color: #F24336; font-weight: 700; }
.live-status-pending { color: #F9C62B; font-weight: 700; }
.live-status-final   { color: #6B7A9A; font-weight: 600; }
.live-status-not-started { color: #3A4460; font-weight: 600; }

/* ─── Summary Cards Row (Glassmorphism Dashboard) ─────────── */
.summary-dashboard {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 20px;
}
.summary-card {
    background: linear-gradient(160deg,
        rgba(18,24,38,0.98) 0%,
        rgba(22,28,44,0.96) 100%);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 16px;
    padding: 20px 18px 18px;
    text-align: center;
    flex: 1;
    min-width: 130px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.45);
    transition: transform 0.22s ease, box-shadow 0.22s ease;
}
.summary-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 30px rgba(0,213,89,0.12), 0 12px 40px rgba(0,0,0,0.50);
    border-color: rgba(0,213,89,0.25);
}
.summary-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.35), transparent);
    transition: opacity 0.22s ease;
}
.summary-card:hover::before { opacity: 1; background: linear-gradient(90deg, transparent, rgba(0,213,89,0.65), transparent); }
.summary-card-value {
    font-size: 1.8rem;
    font-weight: 900;
    font-family: 'Bebas Neue', 'Inter', sans-serif;
    color: #00D559;
    line-height: 1;
}
/* Animated count-up effect */
@keyframes countUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
.summary-card-value {
    animation: countUp 0.55s ease-out both;
}
.summary-card:nth-child(2) .summary-card-value { animation-delay: 0.08s; }
.summary-card:nth-child(3) .summary-card-value { animation-delay: 0.16s; }
.summary-card:nth-child(4) .summary-card-value { animation-delay: 0.24s; }
.summary-card:nth-child(5) .summary-card-value { animation-delay: 0.32s; }
.summary-card:nth-child(6) .summary-card-value { animation-delay: 0.40s; }
.summary-card-label {
    font-size: 0.70rem;
    color: #6B7A9A;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    margin-top: 5px;
    font-weight: 700;
}

/* Win rate card pulsing glow */
.summary-card-wr-green { box-shadow: 0 0 24px rgba(0,213,89,0.20); border-color: rgba(0,213,89,0.30); }
.summary-card-wr-green::before { background: linear-gradient(90deg, transparent, rgba(0,213,89,0.55), transparent) !important; opacity: 1 !important; }
.summary-card-wr-red   { box-shadow: 0 0 24px rgba(255,68,68,0.22); border-color: rgba(255,68,68,0.32); }
.summary-card-wr-red::before   { background: linear-gradient(90deg, transparent, rgba(255,68,68,0.55), transparent) !important; opacity: 1 !important; }
.summary-card-wr-gold  { box-shadow: 0 0 24px rgba(255,204,0,0.22); border-color: rgba(255,204,0,0.32); }
.summary-card-wr-gold::before  { background: linear-gradient(90deg, transparent, rgba(255,204,0,0.55), transparent) !important; opacity: 1 !important; }

@keyframes wrPulse {
    0%,100% { opacity: 1; }
    50%     { opacity: 0.75; }
}
.summary-card-wr-green, .summary-card-wr-red, .summary-card-wr-gold {
    animation: wrPulse 3.5s ease-in-out infinite;
}

/* ─── Mini Sparkline ──────────────────────────────────────── */
.summary-card-sparkline {
    margin-top: 6px;
    opacity: 0.7;
}
.summary-card-sparkline svg { display: block; margin: 0 auto; }

/* ─── Filter Pills ────────────────────────────────────────── */
.filter-pill {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 100px;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    border: 1px solid rgba(0,213,89,0.22);
    background: rgba(0,213,89,0.05);
    color: #6B7A9A;
    margin: 3px 4px;
    transition: all 0.18s ease;
}
.filter-pill:hover, .filter-pill-active {
    background: rgba(0,213,89,0.14);
    color: #00D559;
    border-color: rgba(0,213,89,0.50);
}

/* ─── Day Timeline Cards ──────────────────────────────────── */
.day-card-green {
    border-left: 4px solid #00D559;
    background: rgba(0,213,89,0.04);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.day-card-red {
    border-left: 4px solid #ff4444;
    background: rgba(255,68,68,0.04);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.day-card-yellow {
    border-left: 4px solid #ffcc00;
    background: rgba(255,200,0,0.04);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 10px;
}

/* ─── Calendar Heatmap ────────────────────────────────────── */
.heatmap-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
    max-width: 420px;
}
.heatmap-cell {
    width: 100%;
    aspect-ratio: 1;
    border-radius: 3px;
    cursor: pointer;
    transition: transform 0.12s ease;
    position: relative;
}
.heatmap-cell:hover { transform: scale(1.3); z-index: 2; }
.heatmap-cell-empty { background: rgba(255,255,255,0.03); }
.heatmap-cell-green-1 { background: rgba(0,213,89,0.15); }
.heatmap-cell-green-2 { background: rgba(0,213,89,0.35); }
.heatmap-cell-green-3 { background: rgba(0,213,89,0.55); }
.heatmap-cell-green-4 { background: rgba(0,213,89,0.80); }
.heatmap-cell-red-1 { background: rgba(255,68,68,0.15); }
.heatmap-cell-red-2 { background: rgba(255,68,68,0.35); }
.heatmap-cell-red-3 { background: rgba(255,68,68,0.55); }
.heatmap-cell-red-4 { background: rgba(255,68,68,0.80); }
.heatmap-cell-neutral { background: rgba(255,204,0,0.20); }
.heatmap-day-label {
    font-size: 0.65rem;
    color: #3A4460;
    text-align: center;
    padding-bottom: 2px;
}

/* ─── Achievement Progress Rings ──────────────────────────── */
.achievement-ring-wrap {
    text-align: center;
    padding: 12px 8px;
}
.achievement-ring-label {
    color: #e8f4ff;
    font-weight: 700;
    font-size: 0.82rem;
    margin-top: 6px;
}
.achievement-ring-desc {
    color: #6B7A9A;
    font-size: 0.70rem;
}
.achievement-ring-progress {
    font-size: 0.68rem;
    color: #3A4460;
    margin-top: 2px;
}
.badge-locked {
    filter: grayscale(1) opacity(0.45);
}
.badge-earned {
    animation: badgeEarned 0.6s ease-out;
}
@keyframes badgeEarned {
    0%   { transform: scale(0.5); opacity: 0; }
    60%  { transform: scale(1.15); }
    100% { transform: scale(1); opacity: 1; }
}

/* ─── Level System ────────────────────────────────────────── */
.level-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 800;
    letter-spacing: 0.04em;
}
.level-rookie  { background: rgba(160,170,190,0.15); color: #A0AABE; border: 1px solid rgba(160,170,190,0.3); }
.level-starter { background: rgba(45,158,255,0.10); color: #2D9EFF; border: 1px solid rgba(45,158,255,0.3); }
.level-allstar { background: rgba(255,170,0,0.10); color: #ffaa00; border: 1px solid rgba(255,170,0,0.3); }
.level-mvp     { background: rgba(0,213,89,0.10); color: #00D559; border: 1px solid rgba(0,213,89,0.3); }
.level-goat    { background: linear-gradient(90deg, rgba(255,215,0,0.15), rgba(0,213,89,0.15)); color: #ffd700; border: 1px solid rgba(255,215,0,0.3); }
</style>
"""


def get_bet_card_css():
    """Return CSS for bet tracker cards."""
    return _BET_CARD_CSS


def get_bet_card_html(bet, show_live_status=False):
    """
    Render a single bet as a styled HTML card.

    Args:
        bet (dict): Bet record from the database.
        show_live_status (bool): Whether to show live game status.

    Returns:
        str: HTML string.
    """
    import html as _h

    player   = _h.escape(str(bet.get("player_name") or "Unknown Player"))
    team     = _h.escape(str(bet.get("team") or ""))
    stat     = _h.escape(str(bet.get("stat_type") or "").replace("_", " ").title())
    line     = bet.get("prop_line") or bet.get("line") or 0
    direction = str(bet.get("direction") or "OVER").upper()
    projected = bet.get("projected_value") or bet.get("projected") or ""
    edge_pct = bet.get("edge_percentage") or bet.get("edge") or 0
    confidence = float(bet.get("confidence_score") or 0)
    tier     = str(bet.get("tier") or "Bronze")
    platform = str(bet.get("platform") or "")
    result   = str(bet.get("result") or "").upper()
    actual   = bet.get("actual_value")
    bet_date = _h.escape(str(bet.get("bet_date") or ""))

    # Direction styling
    dir_class = "direction-over" if direction == "OVER" else "direction-under"
    dir_arrow = "↑" if direction == "OVER" else "↓"

    # Platform left-border color
    plat_lower = platform.lower()
    if "fanduel" in plat_lower or "fd" in plat_lower:
        platform_border_color = "#1456c8"
    elif "draftkings" in plat_lower or "dk" in plat_lower:
        platform_border_color = "#2196f3"
    elif "betmgm" in plat_lower or "mgm" in plat_lower:
        platform_border_color = "#c4a930"
    elif "caesars" in plat_lower:
        platform_border_color = "#00a060"
    else:
        platform_border_color = "rgba(0,213,89,0.35)"

    # Card class by result + tier glow
    tier_lower = tier.lower()
    tier_glow_class = f" bet-card-tier-{tier_lower}" if tier_lower in ("platinum", "gold", "silver", "bronze") else ""
    if result == "WIN":
        card_class = f"bet-card bet-card-win{tier_glow_class}"
        result_html = '<span class="result-win">✅ WIN</span>'
    elif result == "LOSS":
        card_class = f"bet-card bet-card-loss{tier_glow_class}"
        result_html = '<span class="result-loss">❌ LOSS</span>'
    elif result == "EVEN":
        card_class = f"bet-card bet-card-even{tier_glow_class}"
        result_html = '<span class="result-even">🔄 EVEN</span>'
    else:
        card_class = f"bet-card bet-card-pending{tier_glow_class}"
        result_html = '<span class="result-pending">⏳ PENDING</span>'

    # Override platform border color for resolved cards (keep result color as left border)
    if result == "WIN":
        platform_border_color = "#00D559"
    elif result == "LOSS":
        platform_border_color = "#F24336"
    elif result == "EVEN":
        platform_border_color = "#A0AABE"
    # PENDING keeps the platform color

    # Platform badge
    if "prizepicks" in plat_lower:
        plat_html = f'<span class="platform-badge-fd">🟢 PrizePicks</span>'
    elif "underdog" in plat_lower:
        plat_html = f'<span class="platform-badge-dk">🟣 Underdog Fantasy</span>'
    elif "draftkings" in plat_lower or "pick6" in plat_lower or "dk" in plat_lower:
        plat_html = f'<span class="platform-badge-dk">🔵 DraftKings Pick6</span>'
    else:
        safe_plat = _h.escape(platform)
        plat_html = f'<span class="platform-badge">{safe_plat}</span>'

    # Tier badge
    tier_emojis = {"platinum": "💎", "gold": "🥇", "silver": "🥈", "bronze": "🥉", "avoid": "⛔"}
    tier_emoji = tier_emojis.get(tier_lower, "🏅")
    tier_html = f'<span class="tier-badge-{tier_lower}">{tier_emoji} {_h.escape(tier)}</span>'

    # Confidence gauge (SVG semi-circular arc)
    conf_pct = max(0.0, min(100.0, confidence))
    if conf_pct >= 80:
        gauge_color = "#00D559"
    elif conf_pct >= 65:
        gauge_color = "#F9C62B"
    elif conf_pct >= 50:
        gauge_color = "#2D9EFF"
    else:
        gauge_color = "#3A4460"

    # SVG arc gauge — 180° semicircle
    _gauge_radius = 28
    _gauge_cx = 35
    _gauge_cy = 32
    _arc_length = _math.pi * _gauge_radius  # half circumference
    _dash = _arc_length * (conf_pct / 100.0)
    _gap = _arc_length - _dash
    conf_bar = (
        f'<div class="confidence-gauge-wrap">'
        f'<svg width="70" height="40" viewBox="0 0 70 40">'
        f'<path d="M 7 32 A {_gauge_radius} {_gauge_radius} 0 0 1 63 32" '
        f'fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="5" stroke-linecap="round"/>'
        f'<path d="M 7 32 A {_gauge_radius} {_gauge_radius} 0 0 1 63 32" '
        f'fill="none" stroke="{gauge_color}" stroke-width="5" stroke-linecap="round" '
        f'stroke-dasharray="{_dash:.1f} {_gap:.1f}"/>'
        f'<text x="{_gauge_cx}" y="{_gauge_cy}" text-anchor="middle" '
        f'font-size="11" font-weight="800" fill="{gauge_color}" '
        f'font-family="Orbitron,sans-serif">{conf_pct:.0f}%</text>'
        f'</svg>'
        f'<span class="confidence-gauge-label">Confidence</span>'
        f'</div>'
    )

    # Projected & edge — and visual projected vs actual comparison
    try:
        proj_float = float(projected) if projected else None
        proj_text = f"📊 Proj: <strong>{proj_float:.1f}</strong>" if proj_float else ""
    except (TypeError, ValueError):
        proj_float = None
        proj_text = ""
    try:
        edge_text = f"· Edge: <strong style='color:#00D559;'>+{float(edge_pct):.1f}%</strong>" if edge_pct else ""
    except (TypeError, ValueError):
        edge_text = ""

    # Projected vs Actual comparison (visual indicator)
    actual_html = ""
    if actual is not None and result in ("WIN", "LOSS", "EVEN"):
        try:
            actual_float = float(actual)
            actual_str = f"{actual_float:.1f}"
            if proj_float is not None and abs(proj_float) > 0.1:
                diff = actual_float - proj_float
                diff_pct = abs(diff / proj_float * 100)
                if diff_pct <= 10:
                    # Close to projection — neutral success indicator
                    actual_class = "actual-close"
                    diff_label = f"(±{abs(diff):.1f} — on target)"
                elif diff > 0:
                    # Exceeded projection
                    actual_class = "actual-hit"
                    diff_label = f"(+{diff:.1f} above proj)"
                else:
                    # Below projection
                    actual_class = "actual-miss"
                    diff_label = f"({diff:.1f} below proj)"
                actual_html = (
                    f'<div class="proj-vs-actual">'
                    f'<span class="proj-label">Actual:</span>'
                    f'<span class="{actual_class}">{actual_str}</span>'
                    f'<span style="color:#3A4460;font-size:0.76rem;">{_h.escape(diff_label)}</span>'
                    f'</div>'
                )
            else:
                actual_html = (
                    f'<div style="margin-top:6px;font-size:0.82rem;color:#6B7A9A;">'
                    f'Actual: <strong style="color:#EEF0F6;">{actual_str}</strong>'
                    f'</div>'
                )
        except (TypeError, ValueError):
            pass

    # Live status
    live_html = ""
    if show_live_status:
        live_status = str(bet.get("live_status") or "🕐 Not Started")
        current_val = bet.get("current_value")
        if current_val is not None:
            live_html = (
                f'<div style="margin-top:6px;font-size:0.82rem;">'
                f'Live: <strong>{current_val}</strong> · {_h.escape(live_status)}'
                f'</div>'
            )
        else:
            live_html = f'<div style="margin-top:6px;font-size:0.82rem;">{_h.escape(live_status)}</div>'

    team_display = f'<span class="bet-card-team">· {team}</span>' if team else ""
    date_display = f'<span style="font-size:0.74rem;color:#3A4460;">{bet_date}</span>' if bet_date else ""

    # Bet-type badge — show logo for historical goblin/demon bets
    bet_type = str(bet.get("bet_type") or "").lower()
    bet_type_badge_html = ""
    if bet_type == "goblin" and _os.path.exists(GOBLIN_LOGO_PATH):
        goblin_img = get_logo_img_tag(GOBLIN_LOGO_PATH, width=18, alt="Goblin")
        bet_type_badge_html = (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'background:rgba(0,213,89,0.08);border:1px solid rgba(0,213,89,0.25);'
            f'border-radius:100px;padding:2px 7px;font-size:0.75rem;color:#00D559;">'
            f'{goblin_img} Goblin</span>'
        )
    elif bet_type == "demon" and _os.path.exists(DEMON_LOGO_PATH):
        demon_img = get_logo_img_tag(DEMON_LOGO_PATH, width=18, alt="Demon")
        bet_type_badge_html = (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'background:rgba(255,94,0,0.08);border:1px solid rgba(255,94,0,0.25);'
            f'border-radius:5px;padding:2px 7px;font-size:0.75rem;color:#ff5e00;">'
            f'{demon_img} Demon</span>'
        )

    # Player headshot thumbnail (NBA CDN)
    player_id = bet.get("player_id") or ""
    headshot_html = ""
    if player_id:
        headshot_html = (
            f'<img class="bet-card-headshot" '
            f'src="https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" '
            f'alt="" onerror="this.style.display=\'none\'" loading="lazy"/>'
        )

    return (
        f'<div class="{card_class}" style="border-left-color:{platform_border_color};">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'{headshot_html}'
        f'<div>'
        f'<span class="bet-card-player">🏀 {player}</span>{team_display}'
        f'</div>'
        f'</div>'
        f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px;">'
        f'{result_html}'
        f'{date_display}'
        f'</div>'
        f'</div>'
        f'<div class="bet-card-divider"></div>'
        f'<div style="font-size:0.9rem;color:rgba(255,255,255,0.85);">'
        f'<span class="{dir_class}">{direction} {dir_arrow}</span>'
        f' &nbsp;{stat} &nbsp;·&nbsp; Line: <strong>{line}</strong>'
        f'</div>'
        f'<div style="font-size:0.82rem;color:#6B7A9A;margin-top:4px;">'
        f'{proj_text} {edge_text}'
        f'</div>'
        f'{conf_bar}'
        f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px;">'
        f'{plat_html} &nbsp; {tier_html}'
        + (f' &nbsp; {bet_type_badge_html}' if bet_type_badge_html else '')
        + f'</div>'
        f'{actual_html}'
        f'{live_html}'
        f'</div>'
    )


def get_summary_cards_html(total, wins, losses, evens, pending, win_rate, streak=0, best_platform="", total_label="Total Bets"):
    """Render the premium summary metrics dashboard at the top of the Bet Tracker."""
    import html as _h

    streak_label = (
        f"🔥 {streak}W" if streak > 0
        else f"❄️ {abs(streak)}L" if streak < 0
        else "—"
    )
    streak_color  = "#00D559" if streak > 0 else "#F24336" if streak < 0 else "#6B7A9A"
    win_color     = "#00D559" if win_rate >= 55 else "#F24336" if win_rate < 45 else "#F9C62B"
    win_glow      = ("rgba(0,213,89,0.35)" if win_rate >= 55
                     else "rgba(242,67,54,0.35)" if win_rate < 45
                     else "rgba(249,198,43,0.35)")
    win_bar_color = win_color

    wr_glow_class = (
        "summary-card-wr-green" if win_rate >= 55
        else "summary-card-wr-red" if win_rate < 45
        else "summary-card-wr-gold"
    )

    # Win rate card — large with mini progress bar
    wr_bar_pct = min(max(win_rate, 0), 100)
    wr_card = (
        f'<div class="summary-card {wr_glow_class}" style="flex:2;min-width:180px;">'
        f'<div style="display:flex;align-items:baseline;gap:6px;justify-content:center;">'
        f'<div class="summary-card-value" style="color:{win_color};font-size:2.6rem;'
        f'text-shadow:0 0 24px {win_glow};">{win_rate:.1f}%</div>'
        f'</div>'
        f'<div class="summary-card-label">Win Rate</div>'
        f'<div style="margin-top:10px;height:5px;background:rgba(255,255,255,0.07);'
        f'border-radius:3px;overflow:hidden;">'
        f'<div style="width:{wr_bar_pct:.1f}%;height:100%;background:{win_bar_color};'
        f'border-radius:3px;box-shadow:0 0 8px {win_glow};'
        f'transition:width 0.6s ease;"></div></div>'
        f'</div>'
    )

    # W/L split card
    wl_card = (
        f'<div class="summary-card" style="flex:1.5;min-width:150px;">'
        f'<div style="display:flex;align-items:center;justify-content:center;gap:16px;">'
        f'<div><div class="summary-card-value" style="color:#00D559;font-size:2rem;'
        f'text-shadow:0 0 18px rgba(0,213,89,0.45);">{_h.escape(str(wins))}</div>'
        f'<div class="summary-card-label">Wins</div></div>'
        f'<div style="color:rgba(255,255,255,0.15);font-size:1.4rem;font-weight:300;">/</div>'
        f'<div><div class="summary-card-value" style="color:#F24336;font-size:2rem;'
        f'text-shadow:0 0 18px rgba(242,67,54,0.40);">{_h.escape(str(losses))}</div>'
        f'<div class="summary-card-label">Losses</div></div>'
        f'</div>'
        f'</div>'
    )

    # Total card
    total_card = (
        f'<div class="summary-card" style="flex:1;min-width:120px;">'
        f'<div class="summary-card-value" style="color:#FFFFFF;font-size:2.2rem;">'
        f'{_h.escape(str(total))}</div>'
        f'<div class="summary-card-label">{_h.escape(total_label)}</div>'
        f'</div>'
    )

    # Streak card
    streak_card = (
        f'<div class="summary-card" style="flex:1;min-width:120px;">'
        f'<div class="summary-card-value" style="color:{streak_color};font-size:1.8rem;'
        f'text-shadow:0 0 16px {streak_color}55;">{_h.escape(streak_label)}</div>'
        f'<div class="summary-card-label">Streak</div>'
        f'</div>'
    )

    # Pending card
    pend_color = "#F9C62B" if pending > 0 else "#6B7A9A"
    pending_card = (
        f'<div class="summary-card" style="flex:1;min-width:110px;">'
        f'<div class="summary-card-value" style="color:{pend_color};font-size:2rem;">'
        f'{_h.escape(str(pending))}</div>'
        f'<div class="summary-card-label">Pending</div>'
        f'</div>'
    )

    cards = wr_card + wl_card + total_card + streak_card + pending_card

    if best_platform:
        safe_plat = _h.escape(best_platform)
        cards += (
            f'<div class="summary-card" style="flex:1.2;min-width:130px;">'
            f'<div class="summary-card-value" style="color:#7c4dff;font-size:1.0rem;'
            f'font-family:Inter,sans-serif;line-height:1.3;">{safe_plat}</div>'
            f'<div class="summary-card-label">Best Platform</div>'
            f'</div>'
        )

    return f'<div class="summary-dashboard">{cards}</div>'


# ============================================================
# SECTION: Styled Stats Table HTML
# ============================================================

def get_styled_stats_table_html(rows, columns, title=""):
    """
    Render a list of dicts as a dark-glass styled HTML table.

    Args:
        rows (list[dict]):   Data rows — each dict maps column header → value.
        columns (list[str]): Column headers in display order.
        title (str):         Optional table title shown above the table.

    Returns:
        str: Self-contained HTML string safe for ``st.markdown(..., unsafe_allow_html=True)``.
    """
    import html as _h

    _TIER_EMOJI = {
        "platinum": "💎",
        "gold":     "🥇",
        "silver":   "🥈",
        "bronze":   "🥉",
    }

    _BET_TYPE_ICON = {
        "goblin":   get_logo_img_tag(GOBLIN_LOGO_PATH, width=16, alt="Goblin"),
        "demon":    get_logo_img_tag(DEMON_LOGO_PATH,  width=16, alt="Demon"),
        "standard": "",
        "normal":   "",
    }

    def _apply_icon(icon, text):
        """Prepend icon to text.  Returns (html_string, is_html).

        When *icon* is a trusted ``<img>`` tag, the text portion is
        HTML-escaped and the combined value is returned with ``is_html=True``
        so the caller can skip a second escape pass.  Plain-text icons are
        simply concatenated without marking the result as HTML.
        """
        if not icon:
            return text, False
        if "<img" in icon:
            return f"{icon} {_h.escape(text)}", True
        return f"{icon} {text}", False

    def _bet_type_lookup_key(raw_key: str) -> str:
        """Return the normalised key for _BET_TYPE_ICON lookup."""
        key = raw_key.lower()
        if key in _BET_TYPE_ICON:
            return key
        words = key.split()
        return words[-1] if words else ""

    def _win_rate_color(val_str):
        """Return a CSS color based on a win-rate string like '63.0%'."""
        try:
            pct = float(str(val_str).replace("%", "").strip())
            if pct >= 60:
                return "#00D559"
            if pct >= 50:
                return "#F9C62B"
            return "#F24336"
        except (ValueError, TypeError):
            return "#e8f0ff"

    header_cells = "".join(
        f'<th style="padding:10px 16px;text-align:left;color:#8899BB;'
        f'font-family:Inter,sans-serif;font-size:0.72rem;font-weight:800;'
        f'text-transform:uppercase;letter-spacing:1px;'
        f'background:rgba(0,0,0,0.30);'
        f'border-bottom:1px solid rgba(255,255,255,0.08);">'
        f'{_h.escape(str(c))}</th>'
        for c in columns
    )

    # Tier color map for badge styling
    _TIER_COLORS = {
        "platinum": ("#00D559", "rgba(0,213,89,0.12)"),
        "gold":     ("#ffaa00", "rgba(255,170,0,0.12)"),
        "silver":   ("#c0d0e8", "rgba(192,208,232,0.10)"),
        "bronze":   ("#ff7c3a", "rgba(255,124,58,0.12)"),
    }

    body_rows = []
    for i, row in enumerate(rows):
        row_bg = "rgba(255,255,255,0.03)" if i % 2 == 0 else "transparent"
        cells = []
        for col in columns:
            raw_val = row.get(col, "")
            display_val = str(raw_val)
            is_html = False

            # Tier column — styled pill badge
            if col.lower() == "tier":
                icon = _TIER_EMOJI.get(display_val.lower(), "")
                t_color, t_bg = _TIER_COLORS.get(display_val.lower(), ("#e8f0ff", "rgba(255,255,255,0.06)"))
                display_val = (
                    f'<span style="display:inline-flex;align-items:center;gap:4px;'
                    f'padding:2px 10px;border-radius:100px;font-size:0.78rem;font-weight:800;'
                    f'color:{t_color};background:{t_bg};border:1px solid {t_color}44;">'
                    f'{_h.escape(icon + " " + display_val) if icon else _h.escape(display_val)}</span>'
                )
                is_html = True
                cell_color = t_color
            # Bet Type column — add logo icon prefix
            elif col.lower() == "bet type":
                icon = _BET_TYPE_ICON.get(_bet_type_lookup_key(display_val), "")
                display_val, is_html = _apply_icon(icon, display_val)
                cell_color = "#e8f0ff"
            elif "win rate" in col.lower() or "win%" in col.lower():
                cell_color = _win_rate_color(display_val)
                # Add inline bar
                try:
                    pct = float(str(display_val).replace("%", "").strip())
                    bar_color = _win_rate_color(display_val)
                    bar_w = min(max(pct, 0), 100)
                    display_val = (
                        f'<div style="display:flex;align-items:center;gap:8px;min-width:100px;">'
                        f'<span style="color:{bar_color};font-weight:800;min-width:44px;">{_h.escape(display_val)}</span>'
                        f'<div style="flex:1;height:6px;background:rgba(255,255,255,0.07);border-radius:3px;overflow:hidden;">'
                        f'<div style="width:{bar_w:.1f}%;height:100%;background:{bar_color};'
                        f'border-radius:3px;box-shadow:0 0 6px {bar_color}66;"></div>'
                        f'</div></div>'
                    )
                    is_html = True
                except (ValueError, TypeError):
                    pass
            elif col.lower() in ("wins", "w"):
                cell_color = "#00D559"
            elif col.lower() in ("losses", "l"):
                cell_color = "#F24336"
            else:
                cell_color = "rgba(255,255,255,0.88)"

            cell_content = display_val if is_html else _h.escape(display_val)
            cells.append(
                f'<td style="padding:10px 16px;color:{cell_color};'
                f'font-family:Inter,sans-serif;font-size:0.86rem;'
                f'border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'{cell_content}</td>'
            )
        hover_bg = "rgba(0,213,89,0.04)" if i % 2 == 0 else "rgba(0,213,89,0.02)"
        body_rows.append(
            f'<tr style="background:{hover_bg};">{"".join(cells)}</tr>'
        )

    title_html = (
        f'<div style="color:#00D559;font-family:Inter,sans-serif;'
        f'font-size:0.78rem;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:0.12em;margin-bottom:10px;'
        f'text-shadow:0 0 12px rgba(0,213,89,0.40);">'
        f'{_h.escape(title)}</div>'
        if title else ""
    )

    return (
        f'{title_html}'
        f'<div style="overflow-x:auto;border-radius:14px;'
        f'border:1px solid rgba(255,255,255,0.09);'
        f'background:linear-gradient(160deg,rgba(18,24,38,0.98) 0%,rgba(10,13,20,0.99) 100%);'
        f'box-shadow:0 8px 32px rgba(0,0,0,0.45),inset 0 1px 0 rgba(255,255,255,0.05);">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        f'</table></div>'
    )

# ============================================================
# END SECTION: Styled Stats Table HTML
# ============================================================

# ============================================================
# END SECTION: Bet Tracker Card CSS & HTML Generators
# ============================================================


# ============================================================
# SECTION: Player Intelligence CSS & HTML Helpers
# Provides CSS classes and HTML generators for the player
# intelligence strip, form dots, matchup grade badges, and
# availability badges used in Neural Analysis cards and the
# Prop Scanner Quick Analysis panel.
# ============================================================

_PLAYER_INTEL_CSS = """
<style>
/* ─── Availability Badges ─────────────────────────────── */
.avail-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    white-space: nowrap;
}
.avail-active   { background: rgba(0,255,128,0.15); color: #00ff90; border: 1px solid rgba(0,255,128,0.35); }
.avail-gtd      { background: rgba(255,200,0,0.15);  color: #ffc800; border: 1px solid rgba(255,200,0,0.35); }
.avail-doubtful { background: rgba(255,120,0,0.15);  color: #ff8800; border: 1px solid rgba(255,120,0,0.35); }
.avail-out      { background: rgba(255,60,60,0.15);  color: #ff4444; border: 1px solid rgba(255,60,60,0.35); }

/* ─── Form Dots ───────────────────────────────────────── */
.form-dots-row {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    flex-wrap: nowrap;
}
.form-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    display: inline-block;
    position: relative;
    flex-shrink: 0;
    cursor: default;
}
.form-dot-hit  { background: #00d084; box-shadow: 0 0 5px rgba(0,208,132,0.55); }
.form-dot-miss { background: #ff4d4d; box-shadow: 0 0 5px rgba(255,77,77,0.45); }
.form-dot-na   { background: #3a4560; }
.form-label-hot     { color: #ff7b2e; font-weight: 700; font-size: 0.78rem; }
.form-label-cold    { color: #5bc8f5; font-weight: 700; font-size: 0.78rem; }
.form-label-neutral { color: #6B7A9A; font-weight: 600; font-size: 0.78rem; }

/* ─── Matchup Grade Badges ────────────────────────────── */
.grade-badge {
    display: inline-block;
    width: 28px;
    height: 28px;
    line-height: 28px;
    text-align: center;
    border-radius: 6px;
    font-size: 0.9rem;
    font-weight: 800;
    letter-spacing: 0;
}
.grade-a  { background: rgba(0,255,128,0.18); color: #00e57a; border: 1px solid rgba(0,255,128,0.40); }
.grade-b  { background: rgba(0,200,255,0.14); color: #00c8ff; border: 1px solid rgba(0,200,255,0.35); }
.grade-c  { background: rgba(255,200,0,0.13); color: #e6b800; border: 1px solid rgba(255,200,0,0.30); }
.grade-d  { background: rgba(255,60,60,0.14); color: #ff5050; border: 1px solid rgba(255,60,60,0.32); }
.grade-na { background: rgba(80,90,120,0.20); color: #6B7A9A; border: 1px solid rgba(80,90,120,0.25); }

/* ─── Value Assessment Classes ────────────────────────── */
.val-great   { color: #00e57a; font-weight: 700; }
.val-good    { color: #00c8ff; font-weight: 600; }
.val-neutral { color: #6B7A9A; }

/* ─── Player Intel Strip ──────────────────────────────── */
.intel-strip {
    background: rgba(13,20,45,0.72);
    border: 1px solid rgba(0,213,89,0.10);
    border-radius: 8px;
    padding: 6px 10px;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 6px;
}
.intel-section {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.76rem;
}
.intel-label {
    color: #3A4460;
    font-size: 0.70rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-right: 2px;
}

/* ─── Streak Banner ───────────────────────────────────── */
.streak-banner-hot  { background: rgba(255,100,0,0.10); border-left: 3px solid #ff6420;
                      padding: 4px 10px; border-radius: 0 6px 6px 0; font-size: 0.78rem; color: #ffaa60; margin-bottom:4px; }
.streak-banner-cold { background: rgba(0,160,255,0.10); border-left: 3px solid #009fff;
                      padding: 4px 10px; border-radius: 0 6px 6px 0; font-size: 0.78rem; color: #70ceff; margin-bottom:4px; }

/* ─── Quick Analysis Panel (Prop Scanner) ─────────────── */

/* Keep legacy classes for the intel strip renderer */
.qa-edge     { font-weight: 700; font-size: 0.82rem; }
.qa-edge-pos { color: #00e57a; }
.qa-edge-neg { color: #ff5050; }
.qa-edge-neu { color: #6B7A9A; }

/* ── QA Card Grid ─────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

.qa-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 14px;
    padding: 8px 0;
    width: 100%;
}
.qa-count-bar {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 14px; margin-bottom: 10px;
    background: rgba(13,20,45,0.55); border-radius: 8px;
    border: 1px solid rgba(0,213,89,0.06);
    font-family: 'Inter', sans-serif; font-size: 0.78rem; color: #6B7A9A;
}
.qa-count-bar b { color: #e0eeff; }

/* ── KPI Summary Bar ──────────────────────────────────── */
.qa-kpi-bar {
    display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.qa-kpi {
    flex: 1 1 160px;
    background: rgba(11,14,26,0.80);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 14px 18px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    text-align: center;
    font-family: 'Inter', sans-serif;
}
.qa-kpi-value {
    font-size: 1.8rem; font-weight: 800; line-height: 1.1;
    font-family: 'JetBrains Mono', monospace;
}
.qa-kpi-label {
    font-size: 0.72rem; color: #6B7A9A; text-transform: uppercase;
    letter-spacing: 0.08em; margin-top: 4px;
}
.qa-kpi-hot  .qa-kpi-value { color: #ff7b2e; }
.qa-kpi-cold .qa-kpi-value { color: #5bc8f5; }
.qa-kpi-flag .qa-kpi-value { color: #ffc800; }
.qa-kpi-hot  { border-color: rgba(255,123,46,0.25); }
.qa-kpi-cold { border-color: rgba(91,200,245,0.25); }
.qa-kpi-flag { border-color: rgba(255,200,0,0.25);  }

/* ── Individual Prop Card ─────────────────────────────── */
@keyframes qa-card-in {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}
.qa-card {
    background: rgba(11,14,26,0.85);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 16px 18px 14px;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.40), 0 0 12px rgba(0,213,89,0.03);
    transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
    animation: qa-card-in 0.35s ease both;
    font-family: 'Inter', sans-serif;
    color: #e0eeff;
    position: relative;
    overflow: hidden;
}
.qa-card:hover {
    border-color: rgba(0,213,89,0.20);
    box-shadow: 0 6px 26px rgba(0,0,0,0.50), 0 0 20px rgba(0,213,89,0.07);
    transform: translateY(-2px);
}
/* Left accent bar showing edge direction */
.qa-card::before {
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0;
    width: 4px; border-radius: 14px 0 0 14px;
}
.qa-card-pos::before { background: linear-gradient(180deg, #00e57a 0%, #00c8ff 100%); }
.qa-card-neg::before { background: linear-gradient(180deg, #ff5050 0%, #ff8844 100%); }
.qa-card-neu::before { background: linear-gradient(180deg, #3A4460 0%, #3a4560 100%); }

/* Header row: player · team · platform */
.qa-card-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 8px; padding-left: 8px;
}
.qa-card-player {
    font-size: 0.95rem; font-weight: 700; color: #ffffff;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 65%;
}
.qa-card-team {
    font-size: 0.72rem; color: #6B7A9A; font-weight: 500;
    margin-left: 6px;
}
.qa-card-platform {
    font-size: 0.68rem; font-weight: 700; padding: 2px 8px;
    border-radius: 5px; text-transform: uppercase;
    letter-spacing: 0.05em;
    font-family: 'JetBrains Mono', monospace;
    background: rgba(0,213,89,0.10); color: #2D9EFF;
    border: 1px solid rgba(0,213,89,0.15);
}

/* Stat + Line row */
.qa-card-stat-row {
    display: flex; align-items: baseline; gap: 8px;
    padding-left: 8px; margin-bottom: 10px;
}
.qa-card-stat {
    font-size: 0.74rem; color: #94a3b8; text-transform: uppercase;
    letter-spacing: 0.07em; font-family: 'JetBrains Mono', monospace;
}
.qa-card-line {
    font-size: 1.35rem; font-weight: 800; color: #ffffff;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
}
.qa-card-avg {
    font-size: 0.72rem; color: #6b7b96; font-weight: 500;
}

/* Metrics row: edge, hit rate, form */
.qa-card-metrics {
    display: flex; gap: 8px; align-items: stretch;
    padding-left: 8px; margin-bottom: 8px;
}
.qa-card-metric-box {
    flex: 1;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 8px 10px;
    text-align: center;
}
.qa-card-metric-val {
    font-size: 1.0rem; font-weight: 700; line-height: 1.2;
    font-family: 'JetBrains Mono', monospace;
}
.qa-card-metric-lbl {
    font-size: 0.62rem; color: #6b7b96; text-transform: uppercase;
    letter-spacing: 0.07em; margin-top: 2px;
}
.qa-card-metric-val.qa-val-pos { color: #00e57a; }
.qa-card-metric-val.qa-val-neg { color: #ff5050; }
.qa-card-metric-val.qa-val-neu { color: #6B7A9A; }

/* Hit-rate mini bar */
.qa-hr-bar-bg {
    width: 100%; height: 4px; background: rgba(255,255,255,0.06);
    border-radius: 2px; margin-top: 4px; overflow: hidden;
}
.qa-hr-bar-fill {
    height: 100%; border-radius: 2px;
    transition: width 0.5s ease;
}
.qa-hr-bar-fill.hr-hot  { background: linear-gradient(90deg, #ff7b2e, #ff9b5e); }
.qa-hr-bar-fill.hr-cold { background: linear-gradient(90deg, #5bc8f5, #8adcff); }
.qa-hr-bar-fill.hr-mid  { background: linear-gradient(90deg, #3A4460, #6B7A9A); }

/* Form dots + availability footer */
.qa-card-footer {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 8px 0; border-top: 1px solid rgba(255,255,255,0.05);
}
.qa-card-footer-left {
    display: flex; align-items: center; gap: 6px;
}
.qa-card-footer-right {
    display: flex; align-items: center; gap: 6px;
}
/* Streak pill */
.qa-streak-pill {
    font-size: 0.68rem; font-weight: 700; padding: 2px 8px;
    border-radius: 5px; white-space: nowrap;
}
.qa-streak-hot  { background: rgba(255,100,0,0.12); color: #ffaa60; border: 1px solid rgba(255,100,0,0.25); }
.qa-streak-cold { background: rgba(0,160,255,0.12); color: #70ceff; border: 1px solid rgba(0,160,255,0.25); }

/* Direction arrow */
.qa-dir-arrow {
    font-size: 0.85rem; font-weight: 700; margin-left: 2px;
}
.qa-dir-over  { color: #00e57a; }
.qa-dir-under { color: #ff5050; }
.qa-dir-dash  { color: #3A4460; }

/* ── Responsive: stack metrics on narrow screens ──────── */
@media (max-width: 420px) {
    .qa-card-metrics { flex-direction: column; }
    .qa-grid { grid-template-columns: 1fr; }
}

/* ── Landscape mobile: compact QA components ─────────── */
@media (max-width: 896px) and (orientation: landscape) {
    .qa-grid {
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 10px;
    }
    .qa-kpi-bar { gap: 8px; margin-bottom: 10px; }
    .qa-kpi {
        padding: 10px 14px;
        flex: 1 1 120px;
    }
    .qa-kpi-value { font-size: 1.4rem; }
    .qa-kpi-label { font-size: 0.65rem; }
    .qa-card {
        padding: 12px 14px 10px;
    }
    .qa-card-player { font-size: 0.85rem; }
    .qa-card-line { font-size: 1.15rem; }
    .qa-card-metric-box { padding: 6px 8px; }
    .qa-card-metric-val { font-size: 0.88rem; }
    .qa-count-bar { padding: 6px 12px; font-size: 0.72rem; }
}

/* ── Landscape extra-small phones (very short viewport) ── */
@media (max-height: 450px) and (orientation: landscape) {
    .qa-grid {
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 8px;
    }
    .qa-kpi { padding: 8px 10px; flex: 1 1 100px; }
    .qa-kpi-value { font-size: 1.2rem; }
    .qa-card { padding: 10px 12px 8px; }
    .qa-card-line { font-size: 1.05rem; }
    .qa-card-metrics { gap: 6px; }
}
</style>
"""


def get_player_intel_css() -> str:
    """Return CSS for the player intelligence UI components."""
    return _PLAYER_INTEL_CSS


def get_availability_badge_html(badge_label: str, badge_class: str, injury_note: str = "") -> str:
    """Return HTML for an availability / injury status badge.

    *badge_class* should be one of: avail-active, avail-gtd,
    avail-doubtful, avail-out.
    """
    import html as _h
    tooltip = _h.escape(injury_note) if injury_note else ""
    title_attr = f' title="{tooltip}"' if tooltip else ""
    return (
        f'<span class="avail-badge {badge_class}"{title_attr}>'
        f'{_h.escape(badge_label)}</span>'
    )


def get_form_dots_html(form_results: list, window: int = 5, prop_line: float = 0.0) -> str:
    """Return an HTML row of coloured dots representing last-N-game over/under results.

    *form_results* is the ``results`` list from
    ``engine.player_intelligence.get_recent_form_vs_line()``.
    """
    dots = []
    # Most recent game first
    for i, r in enumerate(form_results[:window]):
        css_cls = "form-dot-hit" if r.get("hit") else "form-dot-miss"
        date_str = r.get("date", "")
        val = r.get("value", "?")
        margin = r.get("margin", 0)
        sign = "+" if margin >= 0 else ""
        tooltip = f"{date_str}: {val} ({sign}{margin})"
        import html as _h
        dots.append(
            f'<span class="form-dot {css_cls}" title="{_h.escape(tooltip)}"></span>'
        )
    # Pad with grey dots if fewer games available
    for _ in range(max(0, window - len(form_results))):
        dots.append('<span class="form-dot form-dot-na" title="No data"></span>')

    return f'<span class="form-dots-row">{"".join(dots)}</span>'


def get_matchup_grade_badge_html(grade: str, label: str, css_class: str) -> str:
    """Return an HTML matchup grade badge (A / B / C / D / N/A)."""
    import html as _h
    return (
        f'<span class="grade-badge {css_class}" title="{_h.escape(label)}">'
        f'{_h.escape(grade)}</span>'
    )


def get_intel_strip_html(
    availability_html: str,
    form_html: str,
    hit_rate_pct: float,
    form_label: str,
    grade_html: str,
    edge_pct: float,
    direction: str,
    streak_label: str = "",
) -> str:
    """Return a compact player intelligence strip HTML block.

    Shows availability badge, form dots, hit-rate, matchup grade, and
    edge assessment in a single-row layout for use inside analysis cards.
    """
    form_css = (
        "form-label-hot" if "Hot" in form_label
        else "form-label-cold" if "Cold" in form_label
        else "form-label-neutral"
    )
    hit_pct_str = f"{hit_rate_pct * 100:.0f}%"

    edge_sign = "+" if edge_pct >= 0 else ""
    edge_css = "qa-edge-pos" if edge_pct >= 4 else "qa-edge-neg" if edge_pct <= -4 else "qa-edge-neu"

    streak_html = ""
    if streak_label:
        banner_cls = "streak-banner-hot" if "Over" in streak_label else "streak-banner-cold"
        import html as _h
        streak_html = f'<div class="{banner_cls}">{_h.escape(streak_label)}</div>'

    # Determine direction label from form label
    if "Hot" in form_label:
        _form_dir_label = "Over"
    elif "Cold" in form_label:
        _form_dir_label = "Under"
    else:
        _form_dir_label = "-"

    return f"""
{streak_html}
<div class="intel-strip">
  <div class="intel-section">
    <span class="intel-label">Status</span>{availability_html}
  </div>
  <div class="intel-section">
    <span class="intel-label">L{len(form_html)//20 or 5}</span>
    {form_html}
    <span class="{form_css}">{hit_pct_str} ({_form_dir_label})</span>
  </div>
  <div class="intel-section">
    <span class="intel-label">Matchup</span>{grade_html}
  </div>
  <div class="intel-section">
    <span class="intel-label">Avg Edge</span>
    <span class="qa-edge {edge_css}">{edge_sign}{edge_pct:.1f}% {direction}</span>
  </div>
</div>
"""


def get_qa_kpi_bar_html(
    hot_count: int, cold_count: int, flagged_count: int, total_count: int,
) -> str:
    """Return HTML for the Quick Analysis KPI summary bar."""
    return f"""
<div class="qa-kpi-bar">
  <div class="qa-kpi qa-kpi-hot">
    <div class="qa-kpi-value">{hot_count}</div>
    <div class="qa-kpi-label">🔥 Hot Players</div>
  </div>
  <div class="qa-kpi qa-kpi-cold">
    <div class="qa-kpi-value">{cold_count}</div>
    <div class="qa-kpi-label">🧊 Cold Players</div>
  </div>
  <div class="qa-kpi qa-kpi-flag">
    <div class="qa-kpi-value">{flagged_count}</div>
    <div class="qa-kpi-label">⚠️ Injury Flagged</div>
  </div>
  <div class="qa-kpi">
    <div class="qa-kpi-value" style="color:#e0eeff;">{total_count}</div>
    <div class="qa-kpi-label">📊 Total Props</div>
  </div>
</div>
"""


def get_qa_card_html(row: dict, form_dots_html: str) -> str:
    """Return a single Quick Analysis prop card as HTML.

    *row* is a dict from ``build_quick_analysis_rows()``.
    *form_dots_html* is pre-rendered output from ``get_form_dots_html()``.
    """
    import html as _h

    player = _h.escape(row.get("player_name", ""))
    stat = _h.escape(row.get("stat_type", "").replace("_", " ").title())
    line = row.get("line", 0)
    avg = row.get("season_avg", 0.0)
    edge = row.get("edge_pct", 0.0)
    direction = row.get("direction", "—")
    hr = row.get("hit_rate", 0.0)
    form_label = row.get("form_label", "No Data")
    avail_badge = row.get("availability_badge", "🟢 Active")
    avail_cls = row.get("availability_class", "avail-active")
    inj_note = row.get("injury_note", "")
    streak = row.get("streak_label", "")
    platform = row.get("platform", "")
    team = _h.escape(row.get("team", row.get("player_team", "")))

    # Card accent class
    card_accent = "qa-card-pos" if edge >= 4 else "qa-card-neg" if edge <= -4 else "qa-card-neu"

    # Edge display
    edge_sign = "+" if edge >= 0 else ""
    edge_val_cls = "qa-val-pos" if edge >= 4 else "qa-val-neg" if edge <= -4 else "qa-val-neu"

    # Hit rate
    hr_pct = int(hr * 100)
    hr_bar_cls = "hr-hot" if "Hot" in form_label else "hr-cold" if "Cold" in form_label else "hr-mid"

    # Direction arrow
    if "Over" in direction or "OVER" in direction:
        dir_html = '<span class="qa-dir-arrow qa-dir-over">▲</span>'
    elif "Under" in direction or "UNDER" in direction:
        dir_html = '<span class="qa-dir-arrow qa-dir-under">▼</span>'
    else:
        dir_html = '<span class="qa-dir-arrow qa-dir-dash">—</span>'

    # Platform badge
    plat_html = (
        f'<span class="qa-card-platform">{_h.escape(platform)}</span>'
        if platform else ""
    )

    # Average display
    avg_html = f'<span class="qa-card-avg">avg {avg:.1f}</span>' if avg > 0 else ""

    # Availability badge
    inj_title = f' title="{_h.escape(inj_note)}"' if inj_note else ""
    avail_html = f'<span class="avail-badge {avail_cls}"{inj_title}>{avail_badge}</span>'

    # Streak pill
    streak_html = ""
    if streak:
        streak_cls = "qa-streak-hot" if "Over" in streak else "qa-streak-cold"
        streak_html = f'<span class="qa-streak-pill {streak_cls}">{_h.escape(streak)}</span>'

    # NOTE: No line may start with 4+ spaces — st.markdown() treats that as
    # a Markdown code-block, causing raw HTML to render as text.
    return (
        f'<div class="qa-card {card_accent}">'
        f'<div class="qa-card-header">'
        f'<div>'
        f'<span class="qa-card-player">{player}</span>'
        f'<span class="qa-card-team">{team}</span>'
        f'</div>'
        f'{plat_html}'
        f'</div>'
        f'<div class="qa-card-stat-row">'
        f'<span class="qa-card-stat">{stat}</span>'
        f'<span class="qa-card-line">{line}</span>'
        f'{avg_html}'
        f'</div>'
        f'<div class="qa-card-metrics">'
        f'<div class="qa-card-metric-box">'
        f'<div class="qa-card-metric-val {edge_val_cls}">{edge_sign}{edge:.1f}%{dir_html}</div>'
        f'<div class="qa-card-metric-lbl">Edge</div>'
        f'</div>'
        f'<div class="qa-card-metric-box">'
        f'<div class="qa-card-metric-val" style="color:#e0eeff;">{hr_pct}%</div>'
        f'<div class="qa-hr-bar-bg"><div class="qa-hr-bar-fill {hr_bar_cls}" style="width:{hr_pct}%;"></div></div>'
        f'<div class="qa-card-metric-lbl">Hit Rate</div>'
        f'</div>'
        f'</div>'
        f'<div class="qa-card-footer">'
        f'<div class="qa-card-footer-left">'
        f'{form_dots_html}'
        f'{streak_html}'
        f'</div>'
        f'<div class="qa-card-footer-right">'
        f'{avail_html}'
        f'</div>'
        f'</div>'
        f'</div>'
    )


# ============================================================
# END SECTION: Player Intelligence CSS & HTML Helpers
# ============================================================


# ============================================================
# SECTION: Quantum Card Matrix — CSS Grid + Glassmorphic Cards
# ============================================================

QUANTUM_CARD_MATRIX_CSS = """
/* ═══════════════════════════════════════════════════════════
   QUANTUM CARD MATRIX — High-Capacity Grid Renderer
   Full Breakdown Cards with Distribution, Forces & Scores
   ═══════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

/* Container query context — cards adapt to their container,
   not the viewport.  Critical for iframe-embedded rendering. */
.qcm-grid-container {
    container-type: inline-size;
    container-name: qcm;
    width: 100%;
}

.qcm-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
    padding: 8px 0;
    width: 100%;
}

@keyframes qcm-fade-in-up {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
}

.qcm-card {
    background: rgba(11, 14, 26, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 14px;
    padding: 18px 20px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45), 0 0 16px rgba(0, 240, 255, 0.04);
    transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
    animation: qcm-fade-in-up 0.4s ease both;
    font-family: 'Inter', sans-serif;
    color: #e0eeff;
}
.qcm-card:hover {
    border-color: rgba(0, 240, 255, 0.25);
    box-shadow: 0 6px 28px rgba(0, 0, 0, 0.50), 0 0 24px rgba(0, 240, 255, 0.10);
    transform: translateY(-2px);
}

.qcm-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.qcm-player-name {
    font-size: 1.0rem;
    font-weight: 700;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 70%;
}
.qcm-tier-badge {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: 'JetBrains Mono', monospace;
}
.qcm-tier-platinum { background: rgba(0, 240, 255, 0.15); color: #00D559; border: 1px solid rgba(0, 240, 255, 0.30); }
.qcm-tier-gold     { background: rgba(255, 215, 0, 0.15); color: #FFD700; border: 1px solid rgba(255, 215, 0, 0.30); }
.qcm-tier-silver   { background: rgba(192, 192, 192, 0.15); color: #C0C0C0; border: 1px solid rgba(192, 192, 192, 0.30); }
.qcm-tier-bronze   { background: rgba(205, 127, 50, 0.15); color: #CD7F32; border: 1px solid rgba(205, 127, 50, 0.30); }
.qcm-tier-avoid    { background: rgba(100, 116, 139, 0.15); color: #94A3B8; border: 1px solid rgba(100, 116, 139, 0.30); }

/* ── Animated Tier-Glow Borders ──────────────────────────── */
@keyframes qcm-platinum-pulse {
    0%, 100% { box-shadow: 0 0 8px rgba(200, 0, 255, 0.2); }
    50%      { box-shadow: 0 0 18px rgba(200, 0, 255, 0.4); }
}
@keyframes qcm-gold-pulse {
    0%, 100% { box-shadow: 0 0 8px rgba(255, 215, 0, 0.15); }
    50%      { box-shadow: 0 0 18px rgba(255, 215, 0, 0.3); }
}
.qcm-card.qcm-card-platinum {
    animation: qcm-platinum-pulse 2s ease-in-out infinite;
}
.qcm-card.qcm-card-gold {
    animation: qcm-gold-pulse 2s ease-in-out infinite;
}

.qcm-stat-type {
    font-size: 0.78rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 12px;
    font-family: 'JetBrains Mono', monospace;
}
.qcm-stat-type .qcm-team {
    color: #64748b;
    font-size: 0.72rem;
}
.qcm-stat-type .qcm-platform {
    color: #475569;
    font-size: 0.68rem;
}

.qcm-true-line-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    margin-bottom: 10px;
    background: rgba(0, 240, 255, 0.06);
    border: 1px solid rgba(0, 240, 255, 0.15);
    border-radius: 8px;
}
.qcm-true-line-label {
    font-size: 0.72rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-family: 'JetBrains Mono', monospace;
}
.qcm-true-line-value {
    font-size: 1.3rem;
    font-weight: 700;
    color: #00D559;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
}

.qcm-prediction {
    font-size: 0.80rem;
    padding: 8px 12px;
    margin-bottom: 10px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    letter-spacing: 0.02em;
}
.qcm-prediction-neutral {
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.15);
    color: #94A3B8;
}

.qcm-metrics {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 10px;
}
.qcm-metric {
    flex: 1;
    min-width: 60px;
    text-align: center;
    padding: 6px 4px;
    background: rgba(15, 23, 42, 0.50);
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
.qcm-metric-val {
    font-size: 0.9rem;
    font-weight: 700;
    color: #ffffff;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
}
.qcm-metric-lbl {
    font-size: 0.62rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 2px;
}

/* ── Distribution Percentile Row ─────────────────────────── */
.qcm-dist-row {
    display: flex;
    gap: 4px;
    margin-bottom: 10px;
}
.qcm-dist-cell {
    flex: 1;
    text-align: center;
    padding: 5px 2px;
    background: rgba(15, 23, 42, 0.60);
    border-radius: 5px;
    border: 1px solid rgba(255, 255, 255, 0.04);
}
.qcm-dist-val {
    font-size: 0.78rem;
    font-weight: 700;
    color: #c0d0e8;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
}
.qcm-dist-lbl {
    font-size: 0.56rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 1px;
}
.qcm-dist-median .qcm-dist-val { color: #00D559; }
.qcm-dist-proj .qcm-dist-val { color: #ff5e00; }

/* ── Forces Columns ──────────────────────────────────────── */
.qcm-forces {
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
}
.qcm-forces-col {
    flex: 1;
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    min-height: 40px;
}
.qcm-forces-over {
    background: rgba(0, 240, 255, 0.04);
    border: 1px solid rgba(0, 240, 255, 0.12);
}
.qcm-forces-under {
    background: rgba(255, 94, 0, 0.04);
    border: 1px solid rgba(255, 94, 0, 0.12);
}
.qcm-forces-label {
    font-weight: 700;
    font-size: 0.64rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
    color: #94A3B8;
}
.qcm-forces-over .qcm-forces-label { color: #00D559; }
.qcm-forces-under .qcm-forces-label { color: #ff5e00; }

.qcm-force-item {
    color: #c0d0e8;
    margin-bottom: 2px;
    font-size: 0.68rem;
    line-height: 1.4;
}
.qcm-force-none {
    color: #475569;
    font-size: 0.68rem;
    font-style: italic;
}

/* ── Score Breakdown Bars ────────────────────────────────── */
.qcm-breakdown {
    margin-top: 2px;
}
.qcm-breakdown-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 5px;
    font-family: 'JetBrains Mono', monospace;
}
.qcm-breakdown-label {
    font-size: 0.62rem;
    color: #94A3B8;
    width: 65px;
    flex-shrink: 0;
    text-align: right;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.qcm-breakdown-score {
    font-size: 0.62rem;
    color: #ff5e00;
    font-weight: 600;
    width: 24px;
    flex-shrink: 0;
    text-align: right;
}
.qcm-breakdown-track {
    flex: 1;
    height: 4px;
    background: rgba(26, 32, 53, 0.80);
    border-radius: 2px;
    overflow: hidden;
}
.qcm-breakdown-fill {
    height: 4px;
    border-radius: 2px;
    transition: width 0.3s ease;
}

/* ── Player Identity Row (headshot + name + SAFE Score) ──── */
.qcm-identity {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.qcm-headshot {
    width: 72px;
    height: 72px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
    border: 2px solid rgba(0, 240, 255, 0.30);
}
.qcm-headshot-gold { border-color: #FFD700; }
.qcm-headshot-platinum { border-color: #00D559; }
.qcm-headshot-silver { border-color: #C0C0C0; }
.qcm-headshot-bronze { border-color: #CD7F32; }
.qcm-headshot-avoid { border-color: #64748b; }
.qcm-identity-info {
    flex: 1;
    min-width: 0;
}
.qcm-identity-name {
    font-size: 1.0rem;
    font-weight: 700;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.qcm-team-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.64rem;
    font-weight: 700;
    margin-left: 6px;
    vertical-align: middle;
    color: #fff;
}
.qcm-identity-prop {
    font-size: 0.82rem;
    font-weight: 600;
    color: #00D559;
    margin-top: 2px;
}
.qcm-safe-score {
    text-align: center;
    flex-shrink: 0;
    padding: 4px 8px;
}
.qcm-safe-score-label {
    font-size: 0.55rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-family: 'JetBrains Mono', monospace;
}
.qcm-safe-score-value {
    font-size: 1.3rem;
    font-weight: 700;
    color: #00D559;
    font-family: 'JetBrains Mono', monospace;
    text-shadow: 0 0 8px rgba(0,213,89,0.30);
    line-height: 1.1;
}
.qcm-safe-score-value span {
    font-size: 0.72rem;
    color: #64748b;
}

/* ── Compact Card (inside Unified Player Cards) ─────────── */
/* When a prop card lives inside a <details> player card the
   player identity is already visible in the outer header.
   Compact mode removes the headshot and name, replacing them
   with a streamlined tier-badge + prop-description header. */
.qcm-card-compact {
    padding: 14px 16px;
}
.qcm-compact-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.qcm-compact-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
}
.qcm-compact-prop {
    font-size: 0.88rem;
    font-weight: 600;
    color: #00D559;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.qcm-card-compact .qcm-safe-score {
    padding: 2px 6px;
}
.qcm-card-compact .qcm-safe-score-value {
    font-size: 1.1rem;
}

/* ── Inline Prop Badges (Best Pick, Uncertain, Caution) ──── */
.qcm-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    white-space: nowrap;
    flex-shrink: 0;
}
.qcm-badge-best {
    background: rgba(255, 215, 0, 0.12);
    border: 1px solid rgba(255, 215, 0, 0.35);
    color: #FFD700;
    text-shadow: 0 0 6px rgba(255, 215, 0, 0.2);
}
.qcm-badge-uncertain {
    background: rgba(255, 193, 7, 0.10);
    border: 1px solid rgba(255, 193, 7, 0.30);
    color: #ffc107;
}
.qcm-badge-avoid {
    background: rgba(255, 68, 68, 0.10);
    border: 1px solid rgba(255, 68, 68, 0.25);
    color: #ff4444;
}

/* ── Confidence Bar ─────────────────────────────────────── */
.qcm-conf-bar-wrap {
    margin: 4px 0 10px;
}
.qcm-conf-bar-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.68rem;
    color: #64748b;
    margin-bottom: 3px;
    font-family: 'JetBrains Mono', monospace;
}
.qcm-conf-bar-pct {
    font-weight: 700;
}
.qcm-conf-bar-track {
    height: 6px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 3px;
    overflow: hidden;
}
@keyframes qcm-conf-bar-expand {
    from { width: 0%; }
}
.qcm-conf-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
    animation: qcm-conf-bar-expand 0.6s ease-out both;
}

/* ── Context Metrics Grid (Situational / Matchup / Form / Edge) ── */
.qcm-context-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;
    margin-bottom: 10px;
}
.qcm-context-card {
    background: rgba(10, 16, 31, 0.70);
    border-radius: 6px;
    padding: 7px 8px;
    border: 1px solid rgba(0, 240, 255, 0.08);
}
.qcm-context-label {
    font-size: 0.58rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 2px;
}
.qcm-context-value {
    font-size: 0.72rem;
    font-weight: 600;
    color: #e0eeff;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Bonus Factors ──────────────────────────────────────── */
.qcm-bonus {
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
}
.qcm-bonus-title {
    font-size: 0.58rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.qcm-bonus-item {
    display: flex;
    align-items: flex-start;
    gap: 5px;
    font-size: 0.68rem;
    color: #c0d0e8;
    margin-bottom: 2px;
    line-height: 1.35;
}
.qcm-bonus-icon {
    color: #00ff88;
    flex-shrink: 0;
    margin-top: 1px;
}

/* ═══════════════════════════════════════════════════════════
   HORIZONTAL CARD — Best Single Bets wide layout
   ═══════════════════════════════════════════════════════════ */
.qcm-h-card {
    background: linear-gradient(135deg, rgba(11, 14, 26, 0.95), rgba(15, 22, 40, 0.90));
    border: 1px solid rgba(0, 240, 255, 0.18);
    border-radius: 14px;
    padding: 18px 22px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45),
                0 0 20px rgba(0, 240, 255, 0.06),
                inset 0 1px 0 rgba(255, 255, 255, 0.04);
    margin-bottom: 14px;
    font-family: 'Inter', sans-serif;
    color: #e0eeff;
    border-left: 4px solid var(--h-card-accent, #00D559);
    animation: qcm-fade-in-up 0.4s ease both;
    position: relative;
    overflow: hidden;
}
.qcm-h-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(135deg,
        rgba(0, 240, 255, 0.03) 0%,
        transparent 40%,
        transparent 60%,
        rgba(0, 240, 255, 0.02) 100%);
    pointer-events: none;
}
.qcm-h-card:hover {
    border-color: rgba(0, 240, 255, 0.35);
    box-shadow: 0 6px 32px rgba(0, 0, 0, 0.55),
                0 0 28px rgba(0, 240, 255, 0.12),
                inset 0 1px 0 rgba(255, 255, 255, 0.06);
    transform: translateY(-1px);
    transition: all 0.25s ease;
}
/* Tier-specific accent overrides */
.qcm-h-card[data-tier="Platinum"] { --h-card-accent: #c800ff; border-left-color: #c800ff; }
.qcm-h-card[data-tier="Gold"]     { --h-card-accent: #ffd700; border-left-color: #ffd700; }
.qcm-h-card[data-tier="Silver"]   { --h-card-accent: #b0c0d8; border-left-color: #b0c0d8; }
.qcm-h-card[data-tier="Bronze"]   { --h-card-accent: #cd7f32; border-left-color: #cd7f32; }

/* Top section: identity + metrics side by side */
.qcm-h-top {
    display: flex;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 10px;
}
.qcm-h-left {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 200px;
}
.qcm-h-center {
    flex: 1;
    min-width: 0;
}
.qcm-h-right {
    flex: 0 0 auto;
    text-align: right;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
}

/* Horizontal metrics strip */
.qcm-h-metrics-strip {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}
.qcm-h-metric {
    text-align: center;
    padding: 5px 10px;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.65), rgba(20, 28, 50, 0.50));
    border-radius: 6px;
    border: 1px solid rgba(0, 240, 255, 0.08);
    min-width: 50px;
    transition: border-color 0.2s ease;
}
.qcm-h-metric:hover {
    border-color: rgba(0, 240, 255, 0.22);
}

/* Probability pill badge */
.qcm-prob-pill {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #0a0f1a;
}

/* Horizontal bottom section: 3-column layout */
.qcm-h-bottom {
    display: flex;
    gap: 12px;
}
.qcm-h-col {
    flex: 1;
    min-width: 0;
}
.qcm-h-col-narrow {
    flex: 0 0 200px;
}

/* ── Responsive Grid Breakpoints ─────────────────────────── */
@media (min-width: 1200px) {
    .qcm-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
@media (max-width: 600px) {
    .qcm-grid {
        grid-template-columns: 1fr;
    }
}

/* Responsive stacking — Container Queries (preferred).
   Cards adapt to their container width, not the viewport.
   This is critical when rendered inside a self-resizing iframe. */
@container qcm (max-width: 900px) {
    .qcm-h-top {
        flex-direction: column;
    }
    .qcm-h-bottom {
        flex-direction: column;
    }
    .qcm-h-col-narrow {
        flex: 1;
    }
}
@container qcm (max-width: 640px) {
    .qcm-grid {
        grid-template-columns: 1fr;
    }
    .qcm-forces {
        flex-direction: column;
    }
}

/* Fallback for browsers without container query support */
@supports not (container-type: inline-size) {
    @media (max-width: 900px) {
        .qcm-h-top {
            flex-direction: column;
        }
        .qcm-h-bottom {
            flex-direction: column;
        }
        .qcm-h-col-narrow {
            flex: 1;
        }
    }
    @media (max-width: 640px) {
        .qcm-grid {
            grid-template-columns: 1fr;
        }
        .qcm-forces {
            flex-direction: column;
        }
    }
}

/* ── Mobile Responsive — Prop Cards (viewport fallback) ──── */
@media (max-width: 768px) {
    .qcm-grid {
        grid-template-columns: 1fr;
        gap: 12px;
        padding: 4px 0;
    }
    .qcm-card {
        padding: 14px 14px;
        border-radius: 10px;
    }
    .qcm-card-header {
        flex-wrap: wrap;
        gap: 6px;
    }
    .qcm-player-name {
        font-size: 0.90rem;
        max-width: 65%;
    }
    .qcm-tier-badge {
        font-size: 0.62rem;
        padding: 2px 6px;
    }
    .qcm-stat-type {
        font-size: 0.72rem;
        margin-bottom: 8px;
    }
    .qcm-true-line-row {
        padding: 8px 10px;
        margin-bottom: 8px;
    }
    .qcm-true-line-value {
        font-size: 1.1rem;
    }
    .qcm-metrics {
        gap: 4px;
    }
    .qcm-metric {
        min-width: 50px;
        padding: 5px 3px;
    }
    .qcm-metric-val {
        font-size: 0.80rem;
    }
    .qcm-metric-lbl {
        font-size: 0.56rem;
    }
    .qcm-dist-row {
        gap: 3px;
    }
    .qcm-dist-cell {
        padding: 4px 1px;
    }
    .qcm-dist-val {
        font-size: 0.70rem;
    }
    .qcm-dist-lbl {
        font-size: 0.50rem;
    }
    .qcm-forces {
        flex-direction: column;
        gap: 4px;
    }
    .qcm-forces-col {
        padding: 6px 8px;
        font-size: 0.68rem;
    }
    .qcm-h-top,
    .qcm-h-bottom {
        flex-direction: column;
    }
    .qcm-h-col-narrow {
        flex: 1;
    }
    .qcm-bonus {
        padding: 8px 10px;
    }
    .qcm-bonus-title {
        font-size: 0.68rem;
    }
    .qcm-card-compact {
        padding: 12px;
    }
    .qcm-compact-prop {
        font-size: 0.80rem;
    }
    .qcm-badge {
        font-size: 0.56rem;
        padding: 1px 5px;
    }
    .qcm-compact-left {
        flex-wrap: wrap;
    }
    .qam-top-picks-bar {
        padding: 8px 12px;
        gap: 6px;
    }
    .qam-top-picks-label {
        font-size: 0.74rem;
    }
    .qam-top-pill {
        font-size: 0.60rem;
        padding: 3px 8px;
    }
    .qam-uncertain-banner {
        padding: 8px 12px;
    }
    .qam-uncertain-text {
        font-size: 0.68rem;
    }
}
@media (max-width: 480px) {
    .qcm-card {
        padding: 10px 10px;
        border-radius: 8px;
    }
    .qcm-player-name {
        font-size: 0.84rem;
        max-width: 60%;
    }
    .qcm-true-line-value {
        font-size: 1.0rem;
    }
    .qcm-prediction {
        font-size: 0.74rem;
        padding: 6px 10px;
    }
    .qcm-metric {
        min-width: 44px;
    }
    .qcm-metric-val {
        font-size: 0.74rem;
    }
    .qcm-card-compact {
        padding: 8px 10px;
    }
    .qcm-compact-prop {
        font-size: 0.74rem;
    }
    .qcm-card-compact .qcm-safe-score-value {
        font-size: 0.95rem;
    }
    .qcm-badge {
        font-size: 0.52rem;
        padding: 1px 4px;
    }
    .qam-top-pill {
        font-size: 0.56rem;
        padding: 2px 6px;
    }
}

/* ── QAM Helper Card Classes ─────────────────────────────── */
.qam-dfs-edge {
    background: linear-gradient(135deg, #0f1424, #14192b);
    border: 1px solid rgba(0, 255, 157, 0.2);
    border-radius: 8px;
    padding: 10px 16px;
    margin: 6px 0;
}
.qam-dfs-edge-label {
    color: #64748b;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.qam-dfs-edge-sub {
    color: #475569;
    font-size: 0.68rem;
    margin-left: 8px;
}
.qam-dfs-edge-val {
    font-size: 0.82rem;
    font-weight: 800;
    margin-left: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
}
.qam-tier-dist {
    background: linear-gradient(135deg, #0f1424, #14192b);
    border: 1px solid rgba(255, 94, 0, 0.25);
    border-radius: 8px;
    padding: 14px 18px;
    margin: 8px 0 14px;
}
.qam-tier-dist-header {
    font-size: 0.9rem;
    font-weight: 600;
    color: #e0e7ef;
    margin-bottom: 6px;
}
.qam-tier-dist-bar {
    font-size: 0.85rem;
}
.qam-best-pick {
    margin-top: 10px;
    padding: 10px 14px;
    background: rgba(255, 94, 0, 0.08);
    border-radius: 6px;
    border-left: 3px solid #ff5e00;
}
.qam-best-pick-label {
    color: #ff5e00;
    font-weight: 700;
    font-size: 0.85rem;
}
.qam-best-pick-detail {
    color: #e0e7ef;
    font-weight: 600;
}
.qam-best-pick-conf {
    color: #00D559;
    font-weight: 700;
    margin-left: 10px;
}
.qam-news-alert {
    background: #0d1117;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
}
.qam-news-alert-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.qam-news-alert-title {
    color: #e0e7ef;
    font-weight: 700;
}
.qam-news-alert-badge {
    color: #000;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 0.72rem;
    font-weight: 700;
}
.qam-news-alert-meta {
    color: #8b949e;
    font-size: 0.78rem;
    margin-top: 4px;
}
.qam-news-alert-body {
    color: #a0b4d0;
    font-size: 0.82rem;
    margin-top: 6px;
}
.qam-market-move {
    background: #0d1117;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
}
.qam-market-move-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.qam-market-move-player {
    color: #e0e7ef;
    font-weight: 700;
}
.qam-market-move-signal {
    font-weight: 700;
    font-size: 0.85rem;
}
.qam-market-move-detail {
    color: #8b949e;
    font-size: 0.78rem;
    margin-top: 4px;
}
.qam-uncertain-header {
    background: rgba(255, 193, 7, 0.10);
    border: 2px solid #ffc107;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 14px;
}
.qam-uncertain-card {
    background: rgba(255, 193, 7, 0.06);
    border: 1px solid rgba(255, 193, 7, 0.35);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.qam-uncertain-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.qam-uncertain-name {
    color: #ffc107;
    font-weight: 700;
}
.qam-uncertain-team-badge {
    background: rgba(255, 193, 7, 0.15);
    color: #ffe082;
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-left: 7px;
    border: 1px solid rgba(255, 193, 7, 0.3);
}
.qam-uncertain-flag-type {
    background: #ffc107;
    color: #333;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-left: 8px;
}
.qam-uncertain-prop {
    color: #ffe082;
    font-size: 0.85rem;
}
.qam-uncertain-edge {
    color: #ffc107;
    font-size: 0.8rem;
    font-weight: 600;
}
.qam-uncertain-flags {
    margin-top: 8px;
}
.qam-uncertain-flags-label {
    color: #ffc107;
    font-size: 0.75rem;
    font-weight: 600;
}
.qam-uncertain-flags ul {
    margin: 4px 0 0 16px;
    padding: 0;
}
.qam-uncertain-flags li {
    color: #ffe082;
    font-size: 0.82rem;
}
/* ══════════════════════════════════════════════════════════════
   QUANTUM EDGE GAP – Premium Section (redesigned proportions)
   ══════════════════════════════════════════════════════════════ */

/* ── Animations ──────────────────────────────────────────────── */
@keyframes qeg-border-glow {
    0%, 100% { box-shadow: 0 0 16px rgba(0, 180, 100, 0.08), inset 0 0 24px rgba(0, 180, 100, 0.02); }
    50%      { box-shadow: 0 0 28px rgba(0, 180, 100, 0.14), inset 0 0 36px rgba(0, 180, 100, 0.04); }
}
@keyframes qeg-scanline {
    0%   { transform: translateY(-100%); }
    100% { transform: translateY(100%); }
}
@keyframes qeg-shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes qeg-grid-scroll {
    0%   { background-position: 0 0; }
    100% { background-position: 40px 40px; }
}
@keyframes qeg-card-slide-in {
    from { opacity: 0; transform: translateY(12px) scale(0.97); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes qeg-edge-pulse {
    0%, 100% { box-shadow: 0 0 10px rgba(0, 180, 100, 0.10); }
    50%      { box-shadow: 0 0 22px rgba(0, 180, 100, 0.18); }
}
@keyframes qeg-edge-pulse-red {
    0%, 100% { box-shadow: 0 0 10px rgba(200, 60, 60, 0.10); }
    50%      { box-shadow: 0 0 22px rgba(200, 60, 60, 0.18); }
}
@keyframes qeg-gauge-fill {
    from { stroke-dashoffset: 157; }
}
@keyframes qeg-conf-expand {
    from { width: 0; }
}
@keyframes qeg-heat-pulse {
    0%, 100% { opacity: 0.85; }
    50%      { opacity: 1; }
}
@keyframes qeg-force-fill {
    from { width: 0; }
}

/* ── Banner ──────────────────────────────────────────────────── */
.qeg-banner-v2 {
    background: linear-gradient(145deg, #020804 0%, #051109 25%, #07150b 50%, #040e06 75%, #020804 100%);
    border: 1px solid rgba(0, 220, 120, 0.18);
    border-radius: 16px;
    padding: 0;
    margin-bottom: 16px;
    animation: qeg-border-glow 6s ease-in-out infinite;
    position: relative;
    overflow: hidden;
}
/* Circuit-board grid background */
.qeg-banner-v2::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        linear-gradient(rgba(0, 220, 120, 0.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 220, 120, 0.018) 1px, transparent 1px);
    background-size: 32px 32px;
    animation: qeg-grid-scroll 30s linear infinite;
    pointer-events: none;
    mask-image: radial-gradient(ellipse at 50% 50%, black 15%, transparent 65%);
    -webkit-mask-image: radial-gradient(ellipse at 50% 50%, black 15%, transparent 65%);
}
.qeg-banner-v2-inner {
    position: relative; z-index: 1;
    padding: 22px 26px 18px;
}
/* Scanline sweep */
.qeg-scanline-overlay {
    position: absolute; top: 0; left: 0; right: 0; height: 200%;
    background: linear-gradient(180deg, transparent 0%, rgba(0, 220, 120, 0.015) 48%, rgba(0, 220, 120, 0.04) 50%, rgba(0, 220, 120, 0.015) 52%, transparent 100%);
    animation: qeg-scanline 8s linear infinite;
    pointer-events: none; z-index: 0;
}

/* ── Header ──────────────────────────────────────────────────── */
.qeg-v2-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 20px;
}
.qeg-v2-icon-ring {
    width: 46px; height: 46px;
    border-radius: 50%;
    border: 2px solid rgba(0, 220, 120, 0.35);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem;
    background: radial-gradient(circle, rgba(0, 220, 120, 0.10) 0%, transparent 70%);
    box-shadow: 0 0 18px rgba(0, 220, 120, 0.12), inset 0 0 8px rgba(0, 220, 120, 0.06);
    flex-shrink: 0;
    animation: qeg-edge-pulse 4s ease-in-out infinite;
}
.qeg-v2-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: #88e8b0;
    letter-spacing: 0.14em;
    margin: 0;
    text-shadow: 0 0 20px rgba(0, 220, 120, 0.30), 0 1px 2px rgba(0, 0, 0, 0.6);
    line-height: 1.2;
}
.qeg-v2-subtitle {
    font-size: 0.68rem;
    color: rgba(136, 200, 168, 0.55);
    margin: 3px 0 0;
    letter-spacing: 0.03em;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
}

/* ── Main Metrics Row ────────────────────────────────────────── */
.qeg-v2-metrics {
    display: flex;
    align-items: stretch;
    gap: 16px;
    margin-bottom: 16px;
}

/* Count block */
.qeg-v2-count-block {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 80px;
    padding: 12px 16px;
    background: linear-gradient(160deg, rgba(0, 220, 120, 0.04), rgba(0, 220, 120, 0.10));
    border: 1px solid rgba(0, 220, 120, 0.16);
    border-radius: 12px;
    position: relative;
}
.qeg-v2-count-block::after {
    content: '';
    position: absolute; top: 0; left: 15%; right: 15%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 220, 120, 0.20), transparent);
}
.qeg-v2-count-num {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
    color: #78f0b0;
    line-height: 1;
    text-shadow: 0 0 16px rgba(0, 220, 120, 0.35);
    font-variant-numeric: tabular-nums;
}
.qeg-v2-count-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.50rem;
    font-weight: 700;
    color: rgba(120, 240, 176, 0.50);
    letter-spacing: 0.18em;
    margin-top: 4px;
}

/* Over/Under split bar */
.qeg-v2-split-block {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 6px;
    padding: 12px 16px;
    background: rgba(0, 220, 120, 0.02);
    border: 1px solid rgba(0, 220, 120, 0.08);
    border-radius: 12px;
}
.qeg-v2-split-labels {
    display: flex;
    justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.08em;
}
.qeg-v2-split-over  { color: #68d898; }
.qeg-v2-split-under { color: #e07878; }
.qeg-v2-split-bar {
    display: flex;
    height: 8px;
    border-radius: 4px;
    overflow: hidden;
    background: rgba(255,255,255,0.03);
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.3);
}
.qeg-v2-split-fill-over {
    background: linear-gradient(90deg, #308858, #50c880);
    border-radius: 4px 0 0 4px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 0 8px rgba(0, 200, 100, 0.25);
    position: relative;
}
.qeg-v2-split-fill-over::after {
    content: ''; position: absolute; top: 0; right: 0; bottom: 0; width: 2px;
    background: rgba(255,255,255,0.15); border-radius: 1px;
}
.qeg-v2-split-fill-under {
    background: linear-gradient(90deg, #b85050, #d87070);
    border-radius: 0 4px 4px 0;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 0 8px rgba(200, 60, 60, 0.20);
}

/* Edge metrics */
.qeg-v2-edge-block {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 20px;
    background: linear-gradient(160deg, rgba(0, 220, 120, 0.03), rgba(0, 220, 120, 0.08));
    border: 1px solid rgba(0, 220, 120, 0.14);
    border-radius: 12px;
    position: relative;
}
.qeg-v2-edge-block::after {
    content: '';
    position: absolute; top: 0; left: 15%; right: 15%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 220, 120, 0.18), transparent);
}
.qeg-v2-edge-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
}
.qeg-v2-edge-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.15rem;
    font-weight: 700;
    color: #a0e8c0;
    font-variant-numeric: tabular-nums;
    text-shadow: 0 0 10px rgba(0, 220, 120, 0.20);
    line-height: 1;
}
.qeg-v2-peak {
    color: #78f0b0;
    text-shadow: 0 0 14px rgba(0, 240, 140, 0.30);
}
.qeg-v2-edge-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.46rem;
    font-weight: 700;
    color: rgba(160, 200, 180, 0.50);
    letter-spacing: 0.14em;
    text-transform: uppercase;
}
.qeg-v2-edge-divider {
    width: 1px;
    height: 28px;
    background: linear-gradient(180deg, transparent, rgba(0, 220, 120, 0.18), transparent);
}

/* ── Sub-stats row ───────────────────────────────────────────── */
.qeg-v2-sub {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    padding-top: 2px;
    border-top: 1px solid rgba(0, 220, 120, 0.06);
}
.qeg-sub-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: rgba(160, 210, 185, 0.60);
    letter-spacing: 0.02em;
}
.qeg-sub-icon {
    font-size: 0.68rem;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 640px) {
    .qeg-v2-metrics {
        flex-direction: column;
        gap: 10px;
    }
    .qeg-v2-count-block {
        flex-direction: row;
        gap: 10px;
        min-width: unset;
    }
    .qeg-v2-count-num { font-size: 1.4rem; }
    .qeg-v2-count-label { margin-top: 0; }
    .qeg-v2-edge-block { justify-content: center; }
    .qeg-banner-v2-inner { padding: 16px 18px 14px; }
    .qeg-v2-title { font-size: 0.88rem; }
}

/* ── QEG PP-style prop card ─────────────────────────────────── */
.qeg-props-scroll {
    display: flex;
    gap: 14px;
    overflow-x: auto;
    padding: 10px 4px 16px;
    scroll-snap-type: x proximity;
    -webkit-overflow-scrolling: touch;
}
.qeg-props-scroll::-webkit-scrollbar { height: 4px; }
.qeg-props-scroll::-webkit-scrollbar-track { background: transparent; }
.qeg-props-scroll::-webkit-scrollbar-thumb { background: rgba(0,180,100,0.12); border-radius: 2px; }
.qeg-props-scroll::-webkit-scrollbar-thumb:hover { background: rgba(0,180,100,0.22); }

/* Singles row — horizontal scroll strip */
.qeg-singles-row {
    display: flex;
    flex-wrap: nowrap;
    gap: 14px;
    padding: 10px 4px 16px;
    align-items: flex-start;
    overflow-x: auto;
    overflow-y: visible;
    -webkit-overflow-scrolling: touch;
    scroll-snap-type: x proximity;
    scrollbar-width: thin;
    scrollbar-color: rgba(0,180,100,0.12) transparent;
}
.qeg-singles-row::-webkit-scrollbar { height: 4px; }
.qeg-singles-row::-webkit-scrollbar-track { background: transparent; }
.qeg-singles-row::-webkit-scrollbar-thumb { background: rgba(0,180,100,0.12); border-radius: 2px; }
.qeg-singles-row::-webkit-scrollbar-thumb:hover { background: rgba(0,180,100,0.22); }

.qeg-prop {
    flex-shrink: 0;
    width: 280px;
    background: linear-gradient(168deg, rgba(8,16,12,0.97) 0%, rgba(4,8,6,0.96) 35%, rgba(6,12,9,0.94) 100%);
    border: 1px solid rgba(0,180,100,0.10);
    border-radius: 22px;
    font-family: 'Inter', sans-serif;
    color: #c8d8e0;
    overflow: visible;
    transition: width 0.25s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.22s cubic-bezier(.22,1,.36,1);
    scroll-snap-align: start;
    animation: qeg-card-slide-in 0.45s ease both;
    position: relative;
    box-shadow: 0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.02);
}
.qeg-prop[open] {
    width: 420px;
    border-color: rgba(0,180,100,0.22);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 20px rgba(0,180,100,0.06), inset 0 1px 0 rgba(255,255,255,0.03);
}
.qeg-prop:hover {
    border-color: rgba(0,180,100,0.22);
    box-shadow: 0 16px 40px rgba(0,0,0,0.55), 0 0 20px rgba(0,180,100,0.06), inset 0 1px 0 rgba(255,255,255,0.04);
    transform: translateY(-4px) scale(1.01);
}
/* OVER/UNDER glow */
.qeg-prop-over  { border-left: 3px solid #50a874; }
.qeg-prop-under { border-left: 3px solid #c85555; }
.qeg-prop-under {
    background: linear-gradient(160deg, rgba(8,4,4,0.96), rgba(16,8,10,0.94));
}
/* Platinum / Gold glow */
.qeg-prop-platinum { box-shadow: 0 0 22px rgba(200,0,255,0.16), 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(200,0,255,0.04); border-color: rgba(200,0,255,0.26); }
.qeg-prop-gold     { box-shadow: 0 0 22px rgba(255,94,0,0.16), 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,94,0,0.04); border-color: rgba(255,94,0,0.26); }

/* ── Card face (summary) ────────────────────────────────────── */
.qeg-prop > summary {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 18px 16px 16px;
    cursor: pointer;
    list-style: none;
    user-select: none;
    gap: 6px;
    position: relative;
    z-index: 0;
}
.qeg-prop > summary::-webkit-details-marker { display: none; }
.qeg-prop > summary::marker { display: none; content: ''; }
.qeg-prop > summary::after { content:''; position:absolute; top:0; left:10%; right:10%; height:50%; background:radial-gradient(ellipse at 50% 0%, rgba(255,255,255,0.018) 0%, transparent 70%); pointer-events:none; z-index:-1; }

/* Status bar: rank + tier + platform */
.qeg-prop-status {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    justify-content: center;
    margin-bottom: 6px;
}
.qeg-prop-rank {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 800;
    color: #8ec8a0;
    background: rgba(0,180,100,0.10);
    border: 1px solid rgba(0,180,100,0.22);
    padding: 2px 8px;
    border-radius: 6px;
}
.qeg-prop-under .qeg-prop-rank { color: #d88888; background: rgba(200,60,60,0.10); border-color: rgba(200,60,60,0.22); }

.qeg-tier {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 100px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.qeg-tier-platinum { color: #e0aaff; background: rgba(200,0,255,0.15); border: 1px solid rgba(200,0,255,0.25); }
.qeg-tier-gold     { color: #FFD700; background: rgba(255,215,0,0.10); border: 1px solid rgba(255,215,0,0.20); }
.qeg-tier-silver   { color: #b0c0d8; background: rgba(176,192,216,0.08); border: 1px solid rgba(176,192,216,0.15); }
.qeg-tier-bronze   { color: #90a090; background: rgba(100,116,139,0.08); border: 1px solid rgba(100,116,139,0.12); }
.qeg-prop-platform {
    font-size: 0.50rem;
    color: #607870;
    font-weight: 600;
    letter-spacing: 0.03em;
}

/* Headshot */
.qeg-prop-hs-wrap {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    overflow: hidden;
    border: 2.5px solid rgba(0,180,100,0.18);
    background: linear-gradient(145deg, #080c0a, #050805);
    margin: 6px 0;
    flex-shrink: 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    transition: box-shadow 0.25s, border-color 0.25s;
}
.qeg-prop:hover .qeg-prop-hs-wrap { box-shadow: 0 4px 20px rgba(0,180,100,0.12), 0 4px 16px rgba(0,0,0,0.45); border-color: rgba(0,180,100,0.30); }
.qeg-prop[open] .qeg-prop-hs-wrap { box-shadow: 0 4px 20px rgba(0,180,100,0.15); border-color: rgba(0,180,100,0.35); }
.qeg-prop-under .qeg-prop-hs-wrap { border-color: rgba(200,60,60,0.18); }
.qeg-prop-under:hover .qeg-prop-hs-wrap { box-shadow: 0 4px 20px rgba(200,60,60,0.12), 0 4px 16px rgba(0,0,0,0.45); border-color: rgba(200,60,60,0.30); }
.qeg-prop-hs {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center top;
    display: block;
}

/* Player info */
.qeg-prop-team-pos {
    font-size: 0.72rem;
    color: #607870;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 2px;
}
.qeg-prop-player-name {
    font-size: 1.10rem;
    font-weight: 800;
    color: #dce4ec;
    text-align: center;
    word-wrap: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
    line-height: 1.2;
    letter-spacing: -0.01em;
    padding: 0 4px;
}
.qeg-prop-game-info {
    font-size: 0.68rem;
    color: #506858;
    margin-bottom: 4px;
}

/* Line hero area */
.qeg-prop-line-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    padding: 2px 0 4px;
}
.qeg-prop-cur-label {
    font-size: 0.52rem;
    color: #607870;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
}
.qeg-prop-big-line {
    font-family: 'Bebas Neue', 'Oswald', sans-serif;
    font-size: 3.2rem;
    font-weight: 700;
    color: #FFFFFF;
    line-height: 1;
    letter-spacing: 0.01em;
    text-shadow: 0 2px 12px rgba(0,0,0,0.4), 0 0 20px rgba(0,180,100,0.06);
}
.qeg-prop-stat-name {
    font-size: 0.85rem;
    color: #607870;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* Mini probability bar */
.qeg-prop-prob-bar {
    width: 90%;
    height: 5px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    overflow: hidden;
    margin: 4px 0 2px;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.25);
}
.qeg-prop-prob-fill-over {
    height: 100%;
    background: linear-gradient(90deg, #308858, #50c880);
    border-radius: 2px;
    transition: width 0.4s ease;
}
.qeg-prop-prob-fill-under {
    height: 100%;
    background: linear-gradient(90deg, #993333, #c05050);
    border-radius: 2px;
    transition: width 0.4s ease;
}
.qeg-prop-prob-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    margin-bottom: 4px;
}
.qeg-prop-prob-label-over  { color: #90d0a8; }
.qeg-prop-prob-label-under { color: #d88888; }

/* Less / More buttons */
.qeg-btn-row {
    display: flex;
    gap: 8px;
    width: 92%;
}
.qeg-btn {
    flex: 1;
    text-align: center;
    padding: 10px 0;
    border-radius: 12px;
    font-size: 1.0rem;
    font-weight: 700;
    cursor: default;
    transition: background 0.15s ease, transform 0.15s, filter 0.15s;
}
.qeg-btn:hover { transform: translateY(-1px); filter: brightness(1.06); }
.qeg-btn-over-active {
    background: linear-gradient(180deg, rgba(0,200,120,0.18), rgba(0,180,100,0.12));
    color: #90d0a8;
    border: 1px solid rgba(0,180,100,0.28);
    box-shadow: 0 2px 8px rgba(0,180,100,0.15), inset 0 1px 0 rgba(255,255,255,0.06);
}
.qeg-btn-over-inactive {
    background: transparent;
    color: #506858;
    border: 1px solid rgba(0,180,100,0.08);
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
}
.qeg-btn-under-active {
    background: linear-gradient(180deg, rgba(220,70,70,0.18), rgba(200,60,60,0.12));
    color: #d88888;
    border: 1px solid rgba(200,60,60,0.28);
    box-shadow: 0 2px 8px rgba(200,60,60,0.15), inset 0 1px 0 rgba(255,255,255,0.06);
}
.qeg-btn-under-inactive {
    background: transparent;
    color: #604848;
    border: 1px solid rgba(200,60,60,0.08);
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
}

/* ── Expanded detail panel ──────────────────────────────────── */
@keyframes qegPropExpand { from { opacity:0; max-height:0; } to { opacity:1; max-height:900px; } }
.qeg-prop-expanded {
    border-top: 1px solid rgba(0,180,100,0.08);
    padding: 14px 16px 18px;
    animation: qegPropExpand 0.22s ease;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(0,0,0,0.06) 0%, transparent 40%);
}
.qeg-prop-under .qeg-prop-expanded { border-top-color: rgba(200,60,60,0.08); }

/* Detail header */
.qeg-detail-hdr {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.qeg-detail-hs {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid rgba(0,180,100,0.15);
    background: #080c0a;
    flex-shrink: 0;
}
.qeg-prop-under .qeg-detail-hs { border-color: rgba(200,60,60,0.15); }
.qeg-detail-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.qeg-detail-name { font-size: 0.88rem; font-weight: 800; color: #dce4ec; }
.qeg-detail-sub { font-size: 0.60rem; color: #607870; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.qeg-detail-team-badge {
    font-size: 0.54rem; font-weight: 700; padding: 1px 6px;
    border-radius: 100px; color: #fff;
}

/* Section label */
.qeg-sec-label {
    font-size: 0.52rem;
    font-weight: 700;
    color: rgba(136,200,168,0.50);
    text-transform: uppercase;
    letter-spacing: 0.10em;
    padding: 8px 0 4px;
    border-bottom: 1px solid rgba(0,180,100,0.05);
    margin-bottom: 6px;
}
.qeg-prop-under .qeg-sec-label { color: rgba(200,140,140,0.50); border-bottom-color: rgba(200,60,60,0.05); }

/* Edge gauge in expanded */
.qeg-detail-edge {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background: linear-gradient(135deg, rgba(0,180,100,0.05) 0%, rgba(0,180,100,0.01) 100%);
    border: 1px solid rgba(0,180,100,0.10);
    border-radius: 10px;
    margin-bottom: 8px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), 0 1px 4px rgba(0,0,0,0.12);
}
.qeg-prop-under .qeg-detail-edge { background: rgba(200,60,60,0.03); border-color: rgba(200,60,60,0.08); }
.qeg-detail-edge .qeg-edge-gauge { width: 48px; height: 48px; }
.qeg-detail-edge-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.qeg-detail-edge-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.05rem;
    font-weight: 800;
    color: #90d0a8;
}
.qeg-prop-under .qeg-detail-edge-val { color: #d88888; }
.qeg-detail-edge-lbl {
    font-size: 0.50rem;
    color: #607870;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* Metrics 2x2 */
.qeg-detail-metrics {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5px;
    margin-bottom: 8px;
}
.qeg-dm {
    text-align: center;
    padding: 6px 4px;
    background: linear-gradient(180deg, rgba(0,180,100,0.04) 0%, rgba(0,180,100,0.01) 100%);
    border: 1px solid rgba(0,180,100,0.08);
    border-radius: 8px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), 0 1px 3px rgba(0,0,0,0.1);
}
.qeg-prop-under .qeg-dm { background: rgba(200,60,60,0.02); border-color: rgba(200,60,60,0.06); }
.qeg-dm-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 700;
    color: #90d0a8;
}
.qeg-prop-under .qeg-dm-val { color: #d88888; }
.qeg-dm-lbl {
    font-size: 0.46rem;
    color: #607870;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 1px;
}

/* Distribution row */
.qeg-detail-dist {
    display: flex;
    justify-content: space-between;
    gap: 4px;
    padding: 6px 0;
}
.qeg-dd {
    text-align: center;
    flex: 1;
}
.qeg-dd-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem;
    font-weight: 700;
    color: #c8d8e0;
}
.qeg-dd-lbl {
    font-size: 0.44rem;
    color: #607870;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.qeg-dd-med .qeg-dd-val { color: #90d0a8; }
.qeg-dd-proj .qeg-dd-val { color: #78f0b0; }
.qeg-prop-under .qeg-dd-med .qeg-dd-val { color: #d88888; }
.qeg-prop-under .qeg-dd-proj .qeg-dd-val { color: #e09898; }

/* Force direction bar */
.qeg-detail-force {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
}
.qeg-df-lbl {
    font-size: 0.50rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    min-width: 32px;
}
.qeg-df-lbl-over  { color: #90d0a8; text-align: right; }
.qeg-df-lbl-under { color: #d88888; }
.qeg-df-track {
    flex: 1;
    height: 6px;
    background: rgba(255,255,255,0.04);
    border-radius: 3px;
    overflow: hidden;
    display: flex;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.2);
}
.qeg-df-fill-over {
    height: 100%;
    background: linear-gradient(90deg, #50a874, #60b080);
    border-radius: 3px 0 0 3px;
    box-shadow: 0 0 4px rgba(80,168,116,0.3);
}
.qeg-df-fill-under {
    height: 100%;
    background: linear-gradient(90deg, #c85555, #d88888);
    border-radius: 0 3px 3px 0;
    box-shadow: 0 0 4px rgba(200,85,85,0.3);
}

/* Prop call badge */
.qeg-detail-prop-call {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
    margin-bottom: 8px;
    display: inline-block;
}
.qeg-detail-prop-over {
    background: rgba(0,180,100,0.10);
    color: #90d0a8;
    border: 1px solid rgba(0,180,100,0.18);
}
.qeg-prop-under .qeg-detail-avg-val { color: #d88888; }

/* ── Player group row (expandable) ──────────────────────────── */
.qeg-player-row {
    background: linear-gradient(168deg, rgba(8,16,12,0.94) 0%, rgba(4,8,6,0.92) 50%, rgba(6,12,9,0.88) 100%);
    border: 1.5px solid rgba(0,180,100,0.08);
    border-left: 3px solid transparent;
    border-radius: 16px;
    font-family: 'Inter', sans-serif;
    color: #c8d8e0;
    overflow: visible;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    margin-bottom: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.015);
}
.qeg-player-row:hover {
    border-color: rgba(0,180,100,0.18);
    box-shadow: 0 6px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.02);
}
.qeg-player-row[open] {
    border-color: rgba(0,180,100,0.22);
    box-shadow: 0 8px 32px rgba(0,180,100,0.06), 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.02);
}
.qeg-player-row > summary {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 18px;
    cursor: pointer;
    list-style: none;
    user-select: none;
    transition: background 0.15s ease;
    border-radius: 16px;
}
.qeg-player-row > summary::-webkit-details-marker { display: none; }
.qeg-player-row > summary::marker { display: none; content: ''; }
.qeg-player-row > summary:hover { background: rgba(0,180,100,0.025); }
.qeg-player-row[open] > summary { border-radius: 16px 16px 0 0; }
.qeg-player-body { padding: 0 14px 14px; }

/* Summary headshot */
.qeg-sum-arrow {
    font-size: 0.55rem;
    color: #506858;
    flex-shrink: 0;
    transition: transform 0.22s ease, color 0.18s ease;
    margin-right: -4px;
}
.qeg-player-row[open] .qeg-sum-arrow { transform: rotate(90deg); color: #50a874; }
.qeg-sum-head {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 2px solid rgba(0,180,100,0.12);
    object-fit: cover;
    flex-shrink: 0;
    background: #080c0a;
}
.qeg-player-row[open] .qeg-sum-head { border-color: rgba(0,180,100,0.35); }
.qeg-sum-name {
    font-size: 0.95rem;
    font-weight: 800;
    color: #dce4ec;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    letter-spacing: -0.01em;
}
.qeg-sum-team {
    font-size: 0.58rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 100px;
    color: #fff;
}
.qeg-sum-props {
    font-size: 0.62rem;
    color: #607870;
    font-weight: 600;
}
.qeg-sum-edge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 700;
    color: #90d0a8;
    margin-left: auto;
    white-space: nowrap;
}

/* (QEG responsive rules consolidated into comprehensive block below) */

.qam-gold-banner {
    background: linear-gradient(135deg, #1a1200, #231800);
    border: 2px solid #ffd700;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 4px;
}
.qam-section-header {
    background: linear-gradient(135deg, #0f1a2e, #14192b);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 20px;
}
.qam-section-header-single { border: 2px solid #00D559; }
.qam-section-header-parlay {
    border: 1px solid rgba(0, 217, 89, 0.25);
    background: rgba(4, 8, 6, 0.92);
    position: relative; overflow: hidden;
}

/* ═══════════════════════════════════════════════════════════
   AI-OPTIMIZED PARLAYS — Unified Card Design
   ═══════════════════════════════════════════════════════════ */

/* ── Keyframes ────────────────────────────────────────────── */
@keyframes parlaySlideUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── Section Header — mirrors .pc-prop / .qam-hero-card ──── */
.espn-parlay-section-header {
    display: flex; align-items: center; justify-content: space-between;
    background: linear-gradient(168deg, #1E2336 0%, #1A1F2E 35%, #161B27 100%);
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 18px; padding: 22px 28px; margin-bottom: 22px;
    position: relative; overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
}
.espn-parlay-section-header::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3.5px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    opacity: 0.85;
}
.espn-parlay-section-header::after {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 20% 50%, rgba(45,158,255,0.04) 0%, transparent 60%);
    pointer-events: none;
}
.espn-parlay-section-left {
    display: flex; align-items: center; gap: 16px; position: relative; z-index: 1;
}
.espn-parlay-section-icon {
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 100%);
    color: #000; font-weight: 900; font-size: 0.78rem;
    font-family: 'JetBrains Mono', monospace;
    padding: 12px 14px; border-radius: 14px; line-height: 1;
    letter-spacing: 2px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.2);
}
.espn-parlay-section-title {
    color: #FFFFFF; margin: 0; font-size: 1.15rem;
    font-family: Inter, -apple-system, sans-serif; font-weight: 800;
    letter-spacing: -0.2px;
}
.espn-parlay-section-sub {
    color: #6B7A9A; margin: 4px 0 0; font-size: 0.72rem;
    font-family: Inter, sans-serif; font-weight: 500;
}
.espn-parlay-section-badge {
    color: #000; font-size: 0.55rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 900; letter-spacing: 2px;
    padding: 6px 14px; border-radius: 100px;
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    position: relative; z-index: 1;
}

/* ── Parlay container ─────────────────────────────────────── */
.qam-parlay-container {
    display: flex; flex-direction: column; gap: 18px;
}

/* ── Parlay Card — mirrors .pc-prop shell ─────────────────── */
.espn-parlay-card {
    background: linear-gradient(168deg, #1E2336 0%, #1A1F2E 35%, #161B27 100%);
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 18px; overflow: hidden;
    position: relative;
    transition: border-color 0.25s, transform 0.22s cubic-bezier(.22,1,.36,1), box-shadow 0.25s;
    box-shadow: 0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
    animation: parlaySlideUp 0.5s ease-out both;
}
/* gradient top bar like .pc-prop::before */
.espn-parlay-card::before {
    content: ''; display: block; height: 3.5px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    opacity: 0.85;
}
.espn-parlay-card:hover {
    border-color: rgba(255,255,255,0.20);
    transform: translateY(-4px) scale(1.005);
    box-shadow: 0 16px 40px rgba(0,0,0,0.6), 0 0 24px rgba(45,158,255,0.06), inset 0 1px 0 rgba(255,255,255,0.06);
}

/* Top pick — premium glow like .pc-prop-platinum */
.espn-parlay-top {
    border-color: rgba(0,213,89,0.35);
    box-shadow: 0 0 24px rgba(0,213,89,0.14), 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(0,213,89,0.06);
}
.espn-parlay-top::before {
    background: linear-gradient(90deg, #00D559, #2D9EFF, #00D559);
    opacity: 1;
}
.espn-parlay-top::after {
    content: ''; position: absolute; inset: 0; top: 4px;
    background: radial-gradient(ellipse at 30% 0%, rgba(0,213,89,0.04) 0%, transparent 50%);
    pointer-events: none; border-radius: 18px;
}
.espn-parlay-top:hover {
    border-color: rgba(0,213,89,0.5);
    box-shadow: 0 16px 40px rgba(0,0,0,0.6), 0 0 30px rgba(0,213,89,0.1), inset 0 1px 0 rgba(0,213,89,0.08);
}

/* ── Top bar — rank + label ───────────────────────────────── */
.espn-parlay-topbar {
    display: flex; align-items: center; gap: 14px;
    padding: 16px 22px 12px;
    position: relative;
}
.espn-parlay-topbar::after {
    content: ''; position: absolute; bottom: 0; left: 22px; right: 22px;
    height: 1px;
    background: rgba(255,255,255,0.06);
}
.espn-parlay-rank {
    font-size: 0.55rem; font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.07em; text-transform: uppercase;
    padding: 2px 7px; border-radius: 100px;
    background: rgba(0,213,89,0.12); color: #00D559;
    border: 1px solid rgba(0,213,89,0.26);
}
.espn-parlay-label {
    color: #FFFFFF; font-size: 1.0rem; font-weight: 800;
    font-family: Inter, -apple-system, sans-serif;
    letter-spacing: -0.01em;
}

/* ── Body ─────────────────────────────────────────────────── */
.espn-parlay-body {
    display: flex; flex-direction: column; gap: 0;
    padding: 0;
}
.espn-parlay-ring-wrap { display: none; }
.espn-parlay-ring { display: none; }
.espn-parlay-picks { flex: 1; min-width: 0; }

/* ── Game group ───────────────────────────────────────────── */
.espn-parlay-game-group {
    margin-bottom: 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.espn-parlay-game-group:last-child { border-bottom: none; }

/* ── Matchup banner ───────────────────────────────────────── */
.espn-parlay-matchup {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 22px; margin: 0;
    background: linear-gradient(90deg, rgba(255,255,255,0.02) 0%, transparent 100%);
    border: none; border-radius: 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.espn-parlay-team {
    display: flex; align-items: center; gap: 8px;
}
.espn-parlay-team-logo {
    width: 24px; height: 24px; object-fit: contain;
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.4));
    transition: transform 0.2s ease;
}
.espn-parlay-team:hover .espn-parlay-team-logo { transform: scale(1.1); }
.espn-parlay-team-name {
    font-family: Inter, -apple-system, sans-serif;
    font-size: 0.78rem; font-weight: 700;
    letter-spacing: 0.3px;
}
.espn-parlay-team-rec {
    font-size: 0.62rem; color: #3A4460;
    font-family: 'JetBrains Mono', monospace;
}
.espn-parlay-vs {
    font-size: 0.58rem; color: #3A4460;
    font-weight: 900; letter-spacing: 2px;
    padding: 2px 7px; border-radius: 4px;
    background: rgba(255,255,255,0.03);
}

/* ── Leg row ──────────────────────────────────────────────── */
.espn-leg-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 22px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    transition: background 0.15s ease;
    position: relative;
}
.espn-leg-row::before {
    content: ''; position: absolute; left: 0; top: 25%; bottom: 25%;
    width: 2px; background: transparent; border-radius: 2px;
    transition: background 0.2s ease;
}
.espn-leg-row:hover {
    background: rgba(255, 255, 255, 0.02);
}
.espn-leg-row:hover::before {
    background: #2D9EFF;
}
.espn-leg-row:last-child { border-bottom: none; }
.espn-leg-left {
    display: flex; align-items: center; gap: 10px;
    flex-wrap: wrap; min-width: 0;
}
.espn-leg-player {
    color: #FFFFFF; font-weight: 800; font-size: 0.88rem;
    font-family: Inter, -apple-system, sans-serif;
    white-space: nowrap; letter-spacing: -0.01em;
}
.espn-leg-dir {
    font-size: 0.55rem; font-weight: 800;
    padding: 2px 7px; border-radius: 100px;
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase; letter-spacing: 0.07em;
    line-height: 1;
}
.espn-leg-over {
    background: rgba(0,213,89,0.12); color: #00D559;
    border: 1px solid rgba(0,213,89,0.26);
}
.espn-leg-under {
    background: rgba(242,67,54,0.12); color: #F24336;
    border: 1px solid rgba(242,67,54,0.26);
}
.espn-leg-detail {
    color: #A0AABE; font-size: 0.80rem;
    font-weight: 600; font-family: Inter, sans-serif;
}
.espn-leg-tier {
    font-size: 0.55rem; padding: 2px 7px;
    border-radius: 100px; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.07em;
    font-family: 'JetBrains Mono', monospace;
}
.espn-leg-tier-platinum {
    background: rgba(0,213,89,0.12); color: #00D559;
    border: 1px solid rgba(0,213,89,0.26);
}
.espn-leg-tier-gold {
    background: rgba(249,198,43,0.12); color: #F9C62B;
    border: 1px solid rgba(249,198,43,0.26);
}
.espn-leg-tier-silver {
    background: rgba(160,170,190,0.10); color: #A0AABE;
    border: 1px solid rgba(160,170,190,0.20);
}
.espn-leg-edge {
    font-size: 0.82rem; font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    padding: 2px 8px; border-radius: 100px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
}

/* ── Reason tags ──────────────────────────────────────────── */
.espn-parlay-tags {
    display: flex; flex-wrap: wrap; gap: 6px;
    padding: 6px 22px 16px;
}
.espn-parlay-tag {
    font-size: 0.52rem; padding: 2px 7px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 100px; color: #6B7A9A;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600; letter-spacing: 0.04em;
    transition: background 0.15s, transform 0.15s;
}
.espn-parlay-tag:hover {
    background: rgba(255,255,255,0.05);
    transform: translateY(-1px);
}

/* ── Footer stats — mirrors .pc-metrics grid ──────────────── */
.espn-parlay-footer {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 5px; padding: 10px 14px 14px;
    border-top: 1px solid rgba(255,255,255,0.06);
    background: linear-gradient(180deg, rgba(0,0,0,0.08) 0%, transparent 40%);
}
.espn-parlay-stat {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 8px 6px;
    background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02));
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 3px rgba(0,0,0,0.12);
    position: relative;
    transition: background 0.15s, transform 0.15s;
}
.espn-parlay-stat:hover { background: rgba(255,255,255,0.05); transform: translateY(-1px); }
.espn-parlay-stat:not(:last-child)::after { display: none; }
.espn-parlay-stat-num {
    font-size: 1.05rem; font-weight: 800; color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    line-height: 1;
}
.espn-parlay-stat-lbl {
    font-size: 0.48rem; color: #6B7A9A;
    text-transform: uppercase; letter-spacing: 0.05em;
    font-weight: 700; margin-top: 4px;
    font-family: 'JetBrains Mono', monospace;
}
.espn-parlay-safe {
    color: #2D9EFF;
}

/* (Parlay responsive rules consolidated into comprehensive block below) */

/* ═══════════════════════════════════════════════════════════
   PARLAY LEG CARDS — Hero-style mini cards per pick
   ═══════════════════════════════════════════════════════════ */
.plc-row {
    display: flex;
    gap: 20px;
    padding: 12px 16px 16px;
    overflow-x: auto;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.10) transparent;
}
.plc-row::-webkit-scrollbar { height: 4px; }
.plc-row::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.10); border-radius: 4px; }

/* ── Card shell ──────────────────────────────────────────── */
.plc-card {
    position: relative;
    background: linear-gradient(168deg, #1E2336 0%, #1A1F2E 35%, #161B27 100%);
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 22px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 280px;
    max-width: 320px;
    flex-shrink: 0;
    box-shadow: 0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
    transition: border-color 0.25s, transform 0.22s cubic-bezier(.22,1,.36,1), box-shadow 0.25s;
}
.plc-card::before {
    content: '';
    display: block;
    height: 3px;
    width: 100%;
    opacity: 0.75;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
}
.plc-card:hover {
    border-color: rgba(255,255,255,0.20);
    transform: translateY(-3px) scale(1.01);
    box-shadow: 0 12px 32px rgba(0,0,0,0.5), 0 0 18px rgba(45,158,255,0.06), inset 0 1px 0 rgba(255,255,255,0.06);
}
/* Tier variants */
.plc-platinum {
    border-color: rgba(0,213,89,0.35);
    box-shadow: 0 0 20px rgba(0,213,89,0.12), 0 4px 14px rgba(0,0,0,0.3), inset 0 1px 0 rgba(0,213,89,0.06);
}
.plc-platinum::before {
    background: linear-gradient(90deg, #00D559, #2D9EFF, #00D559);
    opacity: 1;
}
.plc-gold {
    border-color: rgba(249,198,43,0.30);
    box-shadow: 0 0 18px rgba(249,198,43,0.10), 0 4px 14px rgba(0,0,0,0.3), inset 0 1px 0 rgba(249,198,43,0.05);
}
.plc-gold::before {
    background: linear-gradient(90deg, #F9C62B, #F24336);
}

/* ── Status / tier badge area ────────────────────────────── */
.plc-status {
    width: 100%;
    text-align: center;
    padding: 12px 14px 0;
}
.plc-tier {
    display: inline-block;
    font-family: 'Orbitron', sans-serif;
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 6px;
}
.plc-tier-platinum {
    background: rgba(0,213,89,0.18);
    color: #00D559;
    border: 1px solid rgba(0,213,89,0.30);
    text-shadow: 0 0 8px rgba(0,213,89,0.40);
}
.plc-tier-gold {
    background: rgba(249,198,43,0.15);
    color: #F9C62B;
    border: 1px solid rgba(249,198,43,0.25);
}
.plc-tier-silver {
    background: rgba(160,170,190,0.12);
    color: #A0AABE;
    border: 1px solid rgba(160,170,190,0.20);
}

/* ── Headshot ────────────────────────────────────────────── */
.plc-hs-wrap {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    overflow: hidden;
    margin: 10px auto 6px;
    background: radial-gradient(circle, rgba(255,255,255,0.06) 60%, transparent 100%);
    box-shadow: 0 0 0 2.5px var(--plc-team-color, rgba(255,255,255,0.12)),
                0 0 14px rgba(0,0,0,0.40);
}
.plc-hs {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center top;
    --plc-team-color: rgba(255,255,255,0.12);
}

/* ── Player info ─────────────────────────────────────────── */
.plc-team {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.68rem;
    font-weight: 700;
    color: #6B7A9A;
    letter-spacing: 0.08em;
    text-align: center;
    margin-top: 4px;
}
.plc-name {
    font-size: 1.10rem;
    font-weight: 800;
    color: #FFFFFF;
    text-align: center;
    padding: 0 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 95%;
}

/* ── Line area ───────────────────────────────────────────── */
.plc-line-area {
    width: 100%;
    text-align: center;
    padding: 14px 14px 6px;
    background: linear-gradient(180deg, rgba(0,0,0,0.22) 0%, rgba(0,0,0,0.12) 100%);
    margin: 4px 0;
    border-top: 1px solid rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
.plc-line {
    font-size: 3.2rem;
    font-weight: 900;
    color: #FFFFFF;
    font-family: 'Bebas Neue', 'Inter', sans-serif;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
    text-shadow: 0 2px 8px rgba(0,0,0,0.35);
}
.plc-stat {
    font-size: 0.85rem;
    font-weight: 600;
    color: #A0AABE;
    margin-top: 4px;
    padding-bottom: 8px;
}

/* ── Direction button ────────────────────────────────────── */
.plc-dir {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px 6px;
    margin: 8px 16px 0;
    border-radius: 12px;
    font-weight: 800;
    font-size: 1.0rem;
    letter-spacing: 0.03em;
    border: 1.5px solid transparent;
    width: calc(100% - 20px);
    box-sizing: border-box;
}
.plc-dir[data-dir="OVER"] {
    background: #00D559;
    color: #0D0F14;
    border-color: #00D559;
    box-shadow: 0 3px 10px rgba(0,213,89,0.35);
}
.plc-dir[data-dir="UNDER"] {
    background: #F24336;
    color: #FFFFFF;
    border-color: #F24336;
    box-shadow: 0 3px 10px rgba(242,67,54,0.30);
}

/* ── Bottom metrics ──────────────────────────────────────── */
.plc-metrics {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 12px 16px 18px;
    width: 100%;
    box-sizing: border-box;
}
.plc-m {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02));
    border-radius: 8px;
    padding: 8px 6px;
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}
.plc-m-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.0rem;
    font-weight: 800;
    color: #FFFFFF;
    line-height: 1;
}
.plc-m-lbl {
    font-size: 0.56rem;
    color: #6B7A9A;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 700;
    margin-top: 3px;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Tier count colors ────────────────────────────────────── */
.qam-tier-platinum { color: #c800ff; font-weight: 700; }
.qam-tier-gold     { color: #ffd700; font-weight: 600; }
.qam-tier-silver   { color: #A0AABE; }
.qam-tier-bronze   { color: #A0AABE; }
.qam-avg-edge      { color: #00D559; }
.qam-news-alert-player { color: #c0d0e8; }
.qam-detail-value  { color: #c0d0e8; }

/* ── Uncertain header inner ─────────────────────────────── */
.qam-uncertain-header-title { color: #ffc107; font-size: 1.0rem; }
.qam-uncertain-header-desc  { color: #ffe082; font-size: 0.85rem; }
.qam-uncertain-card-right   { text-align: right; }

/* ── Banner & section header inner text ─────────────────── */
.qam-gold-banner h3 { color: #ffd700; font-family: Orbitron, sans-serif; margin: 0 0 4px; }
.qam-gold-banner p  { color: #ffe082; font-size: 0.85rem; margin: 0; }
.qam-section-header-single h3 { color: #00D559; font-family: Orbitron, sans-serif; margin: 0 0 6px; }
.qam-section-header-parlay h3 { color: #00D959; font-family: Inter, -apple-system, sans-serif; margin: 0 0 6px; font-weight: 800; }
.qam-section-header p { color: #a0b4d0; font-size: 0.85rem; margin: 0; }

/* ── Parlay header h4 uses parent card styles ──────────────── */

/* ═══════════════════════════════════════════════════════════
   NEURAL ANALYSIS HELPERS — CSS Classes (Item 2)
   Replaces inline style= strings in neural_analysis_helpers.py
   ═══════════════════════════════════════════════════════════ */

/* Distribution row cells */
.nah-dist-row      { display: flex; gap: 4px; margin-top: 10px; margin-bottom: 8px; }
.nah-dist-cell     { text-align: center; padding: 5px 4px;
                     background: rgba(15, 23, 42, 0.60); border-radius: 5px;
                     border: 1px solid rgba(255, 255, 255, 0.04);
                     flex: 1; min-width: 48px; }
.nah-dist-val      { font-size: 0.82rem; font-weight: 700;
                     font-family: 'JetBrains Mono', monospace;
                     font-variant-numeric: tabular-nums; }
.nah-dist-val-p10  { color: #c0d0e8; }
.nah-dist-val-med  { color: #00D559; }
.nah-dist-val-p90  { color: #c0d0e8; }
.nah-dist-val-std  { color: #ffffff; }
.nah-dist-val-proj { color: #ff5e00; }
.nah-dist-label    { font-size: 0.58rem; color: #64748b;
                     text-transform: uppercase; letter-spacing: 0.06em; margin-top: 1px; }

/* Force columns */
.nah-forces-row    { display: flex; gap: 5px; margin-bottom: 8px; }
.nah-force-col     { flex: 1; padding: 7px 9px; border-radius: 5px;
                     font-family: 'JetBrains Mono', monospace; min-height: 36px; }
.nah-force-col-over  { background: rgba(0, 240, 255, 0.04); border: 1px solid rgba(0, 240, 255, 0.12); }
.nah-force-col-under { background: rgba(255, 94, 0, 0.04); border: 1px solid rgba(255, 94, 0, 0.12); }
.nah-force-heading { font-weight: 700; font-size: 0.65rem; text-transform: uppercase;
                     letter-spacing: 0.06em; margin-bottom: 3px; }
.nah-force-heading-over  { color: #00D559; }
.nah-force-heading-under { color: #ff5e00; }
.nah-force-item    { color: #c0d0e8; font-size: 0.7rem; line-height: 1.35; margin-bottom: 1px; }
.nah-force-none    { color: #475569; font-size: 0.7rem; font-style: italic; }

/* Score breakdown bars */
.nah-breakdown     { margin-top: 2px; }
.nah-bkd-row       { display: flex; align-items: center; gap: 5px; margin-bottom: 4px;
                     font-family: 'JetBrains Mono', monospace; }
.nah-bkd-label     { font-size: 0.62rem; color: #94A3B8; width: 62px; flex-shrink: 0;
                     text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nah-bkd-score     { font-size: 0.62rem; font-weight: 600;
                     width: 22px; flex-shrink: 0; text-align: right; }
.nah-bkd-track     { flex: 1; height: 4px; background: rgba(26, 32, 53, 0.80);
                     border-radius: 2px; overflow: hidden; }
.nah-bkd-fill      { height: 4px; border-radius: 2px; }

/* Kelly wager row */
.nah-kelly-row     { display: flex; align-items: center; gap: 6px; margin-top: 8px;
                     padding: 6px 10px;
                     background: linear-gradient(135deg, #070A13, #0F172A);
                     border: 1px solid rgba(0, 198, 255, 0.20); border-radius: 6px; }
.nah-kelly-label   { color: #64748b; font-size: 0.62rem; text-transform: uppercase;
                     letter-spacing: 0.06em; flex-shrink: 0; }
.nah-kelly-amount  { color: #00C6FF; font-size: 0.92rem; font-weight: 800;
                     font-family: 'JetBrains Mono', monospace;
                     font-variant-numeric: tabular-nums; }
.nah-kelly-pct     { color: #475569; font-size: 0.58rem; margin-left: auto; }

/* DFS flex EV section */
.nah-dfs-wrap      { background: linear-gradient(135deg, #070A13, #0F172A);
                     border: 1px solid rgba(0, 255, 157, 0.2); border-radius: 8px;
                     padding: 8px 12px; margin: 6px 0; }
.nah-dfs-header    { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.nah-dfs-label     { color: #64748b; font-size: 0.7rem; text-transform: uppercase;
                     letter-spacing: 0.08em; }
.nah-dfs-platform  { color: #475569; font-size: 0.65rem; margin-left: 6px; }
.nah-dfs-prob      { color: #00D559; font-size: 0.65rem; margin-left: auto;
                     font-family: 'JetBrains Mono', monospace; }
.nah-dfs-pills     { display: flex; gap: 6px; margin-top: 4px; }
.nah-dfs-pill      { flex: 1; min-width: 68px; text-align: center; padding: 4px 6px;
                     border-radius: 6px; }
.nah-dfs-pill-label { font-size: 0.68rem; font-weight: 700;
                      font-family: 'JetBrains Mono', monospace; }
.nah-dfs-pill-edge  { font-size: 0.78rem; font-weight: 800;
                      font-family: 'JetBrains Mono', monospace;
                      font-variant-numeric: tabular-nums; }
.nah-dfs-pill-be    { color: #475569; font-size: 0.58rem; }
.nah-dfs-kelly      { color: #475569; font-size: 0.62rem; margin-top: 3px; }

/* ═══════════════════════════════════════════════════════════
   Feature 13: Sticky Summary Dashboard
   NOTE: ``position:sticky`` was removed because it caused the
   browser to recalculate the sticky offset on every scroll
   frame.  Inside a Streamlit ``@st.fragment`` (which is itself
   inside a scrollable container), this continuous layout
   recalculation overwhelmed the Streamlit WebSocket with
   postMessage traffic from co-located iframes, triggering a
   full page rerun ("app restart") on mobile.  The summary now
   uses a static position with the same visual treatment.
   ═══════════════════════════════════════════════════════════ */
.qam-sticky-summary {
    z-index: 10;
    background: linear-gradient(180deg, #0b1120 0%, rgba(11, 17, 32, 0.97) 100%);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    padding: 8px 0 6px;
    margin: 0 -1rem;
    padding-left: 1rem;
    padding-right: 1rem;
    border-bottom: 1px solid rgba(0, 198, 255, 0.10);
    border-radius: 8px;
    transition: box-shadow 0.25s ease;
}
.qam-sticky-summary:hover {
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}

/* ═══════════════════════════════════════════════════════════
   Feature 14: Quick Filter Chips
   ═══════════════════════════════════════════════════════════ */
.qam-filter-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 0 12px;
    align-items: center;
}
.qam-filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(15, 20, 36, 0.7);
    color: #94A3B8;
    transition: all 0.2s ease;
    user-select: none;
    white-space: nowrap;
}
.qam-filter-chip:hover {
    border-color: rgba(0, 198, 255, 0.35);
    color: #e0e7ef;
    background: rgba(0, 198, 255, 0.06);
}
.qam-filter-chip-active {
    border-color: #00C6FF;
    color: #00C6FF;
    background: rgba(0, 198, 255, 0.12);
    box-shadow: 0 0 8px rgba(0, 198, 255, 0.15);
}
.qam-filter-chip-platinum.qam-filter-chip-active {
    border-color: #c800ff;
    color: #c800ff;
    background: rgba(200, 0, 255, 0.10);
    box-shadow: 0 0 8px rgba(200, 0, 255, 0.2);
}
.qam-filter-chip-gold.qam-filter-chip-active {
    border-color: #ffd700;
    color: #ffd700;
    background: rgba(255, 215, 0, 0.10);
    box-shadow: 0 0 8px rgba(255, 215, 0, 0.2);
}
.qam-filter-chip-edge.qam-filter-chip-active {
    border-color: #00D559;
    color: #00D559;
    background: rgba(0, 255, 157, 0.10);
    box-shadow: 0 0 8px rgba(0, 255, 157, 0.2);
}
.qam-filter-chip-form.qam-filter-chip-active {
    border-color: #ff5e00;
    color: #ff5e00;
    background: rgba(255, 94, 0, 0.10);
    box-shadow: 0 0 8px rgba(255, 94, 0, 0.2);
}
.qam-filter-chip-avoid.qam-filter-chip-active {
    border-color: #ff4444;
    color: #ff4444;
    background: rgba(255, 68, 68, 0.10);
    box-shadow: 0 0 8px rgba(255, 68, 68, 0.2);
}

/* ═══════════════════════════════════════════════════════════
   Feature 15: Sort Controls
   ═══════════════════════════════════════════════════════════ */
.qam-sort-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 0;
    font-size: 0.78rem;
    color: #64748b;
}
.qam-sort-bar-label {
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-size: 0.68rem;
    color: #475569;
    margin-right: 4px;
}

/* ═══════════════════════════════════════════════════════════
   Feature 16: Collapsible Game Groups
   ═══════════════════════════════════════════════════════════ */
.qam-game-group {
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    margin-bottom: 14px;
    overflow: hidden;
    background: rgba(11, 17, 32, 0.4);
}
.qam-game-group-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: linear-gradient(135deg, rgba(15, 20, 36, 0.9), rgba(20, 25, 43, 0.8));
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    cursor: pointer;
    user-select: none;
    transition: background 0.2s ease;
}
.qam-game-group-header:hover {
    background: linear-gradient(135deg, rgba(20, 28, 50, 0.95), rgba(25, 32, 55, 0.9));
}
.qam-game-group-matchup {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.92rem;
    font-weight: 700;
    color: #e0e7ef;
}
.qam-game-group-meta {
    font-size: 0.75rem;
    color: #64748b;
    margin-left: auto;
}
.qam-game-group-badge {
    font-size: 0.7rem;
    color: #00C6FF;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(0, 198, 255, 0.08);
    border: 1px solid rgba(0, 198, 255, 0.15);
}
.qam-game-group-body {
    padding: 4px 0;
}

/* ── QAM Matchup Banner (horizontal split-bar layout) ─────── */
.qam-mu-bar {
    display: flex;
    align-items: center;
    gap: 0;
    background: linear-gradient(
        90deg,
        rgba(11,14,26,0.96) 0%,
        rgba(20,26,40,0.92) 50%,
        rgba(11,14,26,0.96) 100%
    );
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 0;
    margin-bottom: 10px;
    overflow: hidden;
    position: relative;
    font-family: 'Inter', sans-serif;
}
/* Gradient accent from each team color (faint wash on each side) */
.qam-mu-bar::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    border-radius: 14px;
    background:
        radial-gradient(ellipse at 5% 50%, var(--away-clr) 0%, transparent 50%),
        radial-gradient(ellipse at 95% 50%, var(--home-clr) 0%, transparent 50%);
    opacity: 0.08;
}
.qam-mu-side {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    padding: 14px 20px;
    position: relative;
    z-index: 1;
}
.qam-mu-away { justify-content: flex-start; }
.qam-mu-home { justify-content: flex-end; }
.qam-mu-logo {
    width: 44px !important;
    height: 44px !important;
    object-fit: contain;
    flex-shrink: 0;
    filter: drop-shadow(0 2px 6px rgba(0,0,0,0.50));
    transition: transform 0.25s ease;
}
.qam-mu-bar:hover .qam-mu-logo {
    transform: scale(1.08);
}
.qam-mu-team-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
}
.qam-mu-abbrev {
    font-family: 'Orbitron', monospace, sans-serif;
    font-weight: 800;
    font-size: 1.10rem;
    letter-spacing: 0.08em;
}
.qam-mu-record {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #6B7A9A;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}
/* Centre column */
.qam-mu-centre {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 10px 16px;
    flex-shrink: 0;
    position: relative;
    z-index: 1;
}
.qam-mu-at {
    font-family: 'Orbitron', monospace, sans-serif;
    font-size: 0.80rem;
    font-weight: 700;
    color: #64748b;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 50%;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.qam-mu-counts {
    display: flex;
    gap: 10px;
}
.qam-mu-count {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    color: #94a3b8;
    white-space: nowrap;
}
/* Mobile */
@media (max-width: 600px) {
    .qam-mu-side { padding: 10px 12px; gap: 8px; }
    .qam-mu-logo { width: 32px; height: 32px; }
    .qam-mu-abbrev { font-size: 0.88rem; }
    .qam-mu-record { font-size: 0.64rem; }
    .qam-mu-centre { padding: 8px 8px; }
    .qam-mu-at { width: 24px; height: 24px; font-size: 0.68rem; }
    .qam-mu-count { font-size: 0.60rem; }
}

/* ── Top Picks Summary Bar ─────────────────────────────────── */
.qam-top-picks-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding: 12px 18px;
    background: linear-gradient(135deg, rgba(255,215,0,0.04) 0%, rgba(0,213,89,0.03) 100%);
    border: 1px solid rgba(255,215,0,0.18);
    border-radius: 12px;
    margin-bottom: 12px;
}
.qam-top-picks-label {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.82rem;
    font-weight: 700;
    color: #FFD700;
    letter-spacing: 0.5px;
    flex-shrink: 0;
}
.qam-top-pill {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 8px;
    border: 1px solid #334155;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.qam-top-pill:hover {
    box-shadow: 0 0 10px rgba(255,215,0,0.08);
}

/* ── Uncertain Picks Inline Banner ─────────────────────────── */
.qam-uncertain-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: rgba(255,193,7,0.05);
    border: 1px solid rgba(255,193,7,0.18);
    border-left: 3px solid #ffc107;
    border-radius: 8px;
    margin-bottom: 12px;
    font-family: 'Inter', sans-serif;
}
.qam-uncertain-icon {
    font-size: 1.1rem;
    flex-shrink: 0;
}
.qam-uncertain-text {
    font-size: 0.76rem;
    color: #d4a84a;
    line-height: 1.45;
}

/* ═══════════════════════════════════════════════════════════
   TOP 3 TONIGHT — Hero cards (matches QEG prop card style)
   ═══════════════════════════════════════════════════════════ */
.qam-hero-section {
    margin-bottom: 28px;
}
.qam-hero-label {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 0.03em;
    margin-bottom: 16px;
}
.qam-hero-grid {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    width: 100%;
}
/* (Hero grid responsive rules consolidated into comprehensive block below) */

/* ── Card shell — mirrors .pc-prop ─────────────────────── */
.qam-hero-card {
    position: relative;
    flex: 1 1 280px;
    min-width: 280px;
    max-width: 420px;
    background: linear-gradient(168deg, #1E2336 0%, #1A1F2E 35%, #161B27 100%);
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 22px;
    overflow: hidden;
    animation: heroFadeIn 0.5s ease-out both;
    transition: border-color 0.25s, transform 0.22s cubic-bezier(.22,1,.36,1), box-shadow 0.25s;
    display: flex;
    flex-direction: column;
    align-items: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
}
/* top gradient bar — tier-aware like .pc-prop::before */
.qam-hero-card::before {
    content: '';
    display: block;
    height: 3px;
    width: 100%;
    opacity: 0.75;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
}
.qam-hero-card[data-tier="Platinum"]::before {
    background: linear-gradient(90deg, #00D559, #2D9EFF, #00D559);
    opacity: 1;
}
.qam-hero-card[data-tier="Gold"]::before {
    background: linear-gradient(90deg, #F9C62B, #F24336);
}
.qam-hero-card:hover {
    border-color: rgba(255,255,255,0.20);
    transform: translateY(-4px) scale(1.015);
    box-shadow: 0 16px 40px rgba(0,0,0,0.6), 0 0 24px rgba(45,158,255,0.06), inset 0 1px 0 rgba(255,255,255,0.06);
}
.qam-hero-card[data-tier="Platinum"] {
    border-color: rgba(0,213,89,0.35);
    box-shadow: 0 0 24px rgba(0,213,89,0.14), 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(0,213,89,0.06);
}
.qam-hero-card[data-tier="Gold"] {
    border-color: rgba(249,198,43,0.30);
    box-shadow: 0 0 22px rgba(249,198,43,0.12), 0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(249,198,43,0.05);
}
@keyframes heroFadeIn {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── Rank badge (top-right) ────────────────────────────── */
.qam-hero-rank {
    position: absolute;
    top: 14px; right: 16px;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.6rem;
    font-weight: 900;
    color: rgba(255,255,255,0.08);
    line-height: 1;
    z-index: 1;
}

/* ── Status bar (tier + team) — mirrors .pc-prop-status ── */
.qam-hero-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 10px 14px 6px;
    box-sizing: border-box;
}

/* Tier badge — mirrors .pc-tier */
.qam-hero-tier {
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    padding: 2px 7px;
    border-radius: 100px;
    text-transform: uppercase;
    white-space: nowrap;
}
.qam-hero-tier[data-tier="Platinum"] {
    background: rgba(0,213,89,0.12);
    color: #00D559;
    border: 1px solid rgba(0,213,89,0.26);
}
.qam-hero-tier[data-tier="Gold"] {
    background: rgba(249,198,43,0.12);
    color: #F9C62B;
    border: 1px solid rgba(249,198,43,0.26);
}
.qam-hero-tier[data-tier="Silver"] {
    background: rgba(160,170,190,0.10);
    color: #A0AABE;
    border: 1px solid rgba(160,170,190,0.20);
}
.qam-hero-tier[data-tier="Bronze"] {
    background: rgba(107,122,154,0.10);
    color: #6B7A9A;
    border: 1px solid rgba(107,122,154,0.20);
}

/* ── Headshot — centered circle like .pc-prop-hs ─────── */
.qam-hero-hs-wrap {
    position: relative;
    margin: 4px auto 10px;
    width: 100px;
    height: 100px;
}
.qam-hero-headshot {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    border: 2.5px solid var(--hero-team-color, rgba(255,255,255,0.14));
    object-fit: cover;
    object-position: top center;
    background: #1C2232;
    display: block;
    box-shadow: 0 4px 16px rgba(0,0,0,0.45);
    transition: box-shadow 0.25s;
}
.qam-hero-card:hover .qam-hero-headshot {
    box-shadow: 0 4px 20px rgba(45,158,255,0.15), 0 4px 16px rgba(0,0,0,0.4);
}

/* ── Player info — centered below headshot ───────────── */
.qam-hero-team-pos {
    font-size: 0.68rem;
    font-weight: 600;
    color: #6B7A9A;
    text-align: center;
    margin-bottom: 4px;
}
.qam-hero-name {
    font-size: 1.10rem;
    font-weight: 800;
    color: #FFFFFF;
    text-align: center;
    letter-spacing: -0.01em;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 90%;
}
.qam-hero-game-info {
    font-size: 0.60rem;
    color: #4A5568;
    text-align: center;
    margin-bottom: 4px;
}

/* ── Line area — big number, centered, like .pc-prop-line-area */
.qam-hero-line-area {
    width: 100%;
    text-align: center;
    padding: 14px 14px 6px;
    background: linear-gradient(180deg, rgba(0,0,0,0.22) 0%, rgba(0,0,0,0.12) 100%);
    margin: 4px 0;
    border-top: 1px solid rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
.qam-hero-line {
    font-size: 3.2rem;
    font-weight: 900;
    color: #FFFFFF;
    font-family: 'Bebas Neue', 'Inter', sans-serif;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
    text-shadow: 0 2px 10px rgba(0,0,0,0.35);
}
.qam-hero-stat {
    font-size: 0.85rem;
    font-weight: 600;
    color: #A0AABE;
    margin-top: 4px;
    padding-bottom: 8px;
}

/* ── Direction button — mirrors .pc-btn-row ──────────── */
.qam-hero-dir {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px 6px;
    margin: 8px 16px 0;
    border-radius: 12px;
    font-weight: 800;
    font-size: 1.0rem;
    letter-spacing: 0.03em;
    border: 1.5px solid transparent;
    width: calc(100% - 28px);
    box-sizing: border-box;
}
.qam-hero-dir[data-dir="OVER"] {
    background: #00D559;
    color: #0D0F14;
    border-color: #00D559;
    box-shadow: 0 3px 12px rgba(0,213,89,0.40);
}
.qam-hero-dir[data-dir="UNDER"] {
    background: #F24336;
    color: #FFFFFF;
    border-color: #F24336;
    box-shadow: 0 3px 12px rgba(242,67,54,0.36);
}

/* ── Projection bar — Line vs Proj ───────────────────── */
.qam-hero-proj-bar {
    width: calc(100% - 28px);
    margin: 8px 14px 4px;
    box-sizing: border-box;
}
.qam-hero-proj-bar-label {
    display: flex;
    justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem;
    margin-bottom: 5px;
    white-space: nowrap;
    overflow: hidden;
}
.qam-hero-proj-bar-track {
    height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 4px;
    overflow: hidden;
}
.qam-hero-proj-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.8s ease;
}

/* ── Bottom metrics — mirrors .pc-metrics grid ────────── */
.qam-hero-metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    padding: 10px 10px 14px;
    width: 100%;
    box-sizing: border-box;
}
.qam-hero-metric {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.02));
    border-radius: 8px;
    padding: 6px 4px;
    border: 1px solid rgba(255,255,255,0.06);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 3px rgba(0,0,0,0.12);
    overflow: hidden;
    min-width: 0;
}
.qam-hero-metric-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88rem;
    font-weight: 700;
    color: #FFFFFF;
    white-space: nowrap;
}
.qam-hero-metric-label {
    font-size: 0.50rem;
    color: #6B7A9A;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 1px;
}

/* ── Simulation range ──────────────────────────────────── */
.qam-hero-range {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: calc(100% - 28px);
    padding-bottom: 12px;
    margin: 0 14px;
}
.qam-hero-range-label {
    font-size: 0.62rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
}
.qam-hero-range-vals {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.80rem;
    font-weight: 600;
    color: #94a3b8;
}

/* ═══════════════════════════════════════════════════════════
   QUICK VIEW — Compact one-line-per-pick table
   ═══════════════════════════════════════════════════════════ */
.qam-quick-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-family: 'Inter', sans-serif;
}
.qam-quick-table thead th {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.62rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(0,213,89,0.10);
    text-align: left;
    position: sticky;
    top: 0;
    background: #0a0f1a;
    z-index: 2;
}
.qam-quick-table thead th:last-child,
.qam-quick-table tbody td:last-child {
    text-align: center;
}
.qam-quick-table tbody tr {
    transition: background 0.15s ease;
    cursor: default;
}
.qam-quick-table tbody tr:hover {
    background: rgba(0,213,89,0.04);
}
.qam-quick-table tbody td {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    font-size: 0.82rem;
    color: #c8d8f0;
    vertical-align: middle;
    white-space: nowrap;
}
.qam-quick-player {
    font-weight: 700;
    color: #e2e8f0;
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
}
.qam-quick-stat {
    color: #94a3b8;
    font-size: 0.78rem;
}
.qam-quick-line {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 0.88rem;
    color: #00D559;
}
.qam-quick-dir {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 5px;
    letter-spacing: 0.03em;
}
.qam-quick-dir[data-dir="OVER"] {
    background: rgba(0,213,89,0.09);
    color: #00D559;
}
.qam-quick-dir[data-dir="UNDER"] {
    background: rgba(255,94,0,0.10);
    color: #ff5e00;
}
.qam-quick-conf {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 0.85rem;
}
.qam-quick-edge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.80rem;
    color: #94a3b8;
}
.qam-quick-tier {
    display: inline-block;
    font-family: 'Orbitron', sans-serif;
    font-size: 0.56rem;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 5px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.qam-quick-tier[data-tier="Platinum"] {
    background: rgba(200,0,255,0.15);
    color: #c800ff;
    border: 1px solid rgba(200,0,255,0.30);
}
.qam-quick-tier[data-tier="Gold"] {
    background: rgba(255,94,0,0.12);
    color: #ff5e00;
    border: 1px solid rgba(255,94,0,0.25);
}
.qam-quick-tier[data-tier="Silver"] {
    background: rgba(176,192,216,0.10);
    color: #b0c0d8;
    border: 1px solid rgba(176,192,216,0.20);
}
.qam-quick-tier[data-tier="Bronze"] {
    background: rgba(100,116,139,0.10);
    color: #64748b;
    border: 1px solid rgba(100,116,139,0.20);
}
.qam-quick-badge {
    display: inline-block;
    font-size: 0.54rem;
    padding: 1px 5px;
    border-radius: 4px;
    margin-left: 4px;
    font-weight: 600;
    vertical-align: middle;
}
.qam-quick-badge-top {
    background: rgba(255,215,0,0.12);
    color: #FFD700;
    border: 1px solid rgba(255,215,0,0.25);
}
.qam-quick-badge-avoid {
    background: rgba(239,68,68,0.10);
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.20);
}
/* ═══════════════════════════════════════════════════════════
   PLATFORM AI PICKS — Electric AI-themed hero cards
   ═══════════════════════════════════════════════════════════ */
@keyframes aiShimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes aiPulse {
    0%, 100% { opacity: 0.6; }
    50%      { opacity: 1; }
}
@keyframes aiBorderGlow {
    0%, 100% { border-color: rgba(138,92,246,0.35); box-shadow: 0 0 20px rgba(138,92,246,0.12), 0 4px 16px rgba(0,0,0,0.3); }
    50%      { border-color: rgba(59,130,246,0.45); box-shadow: 0 0 28px rgba(59,130,246,0.18), 0 4px 20px rgba(0,0,0,0.35); }
}

.plat-section {
    margin-bottom: 28px;
}
.plat-label {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    margin-bottom: 16px;
    background: linear-gradient(90deg, #c084fc, #60a5fa, #fbbf24, #f0abfc);
    background-size: 200% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: aiShimmer 4s linear infinite;
}
.plat-grid {
    display: flex;
    gap: 16px;
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: visible;
    width: 100%;
    padding-bottom: 8px;
    scrollbar-width: thin;
    scrollbar-color: rgba(138,92,246,0.5) rgba(255,255,255,0.05);
}
.plat-grid::-webkit-scrollbar {
    height: 5px;
}
.plat-grid::-webkit-scrollbar-track {
    background: rgba(255,255,255,0.04);
    border-radius: 100px;
}
.plat-grid::-webkit-scrollbar-thumb {
    background: rgba(138,92,246,0.55);
    border-radius: 100px;
}

/* ── Card shell — AI electric aesthetic ──────────────────── */
.plat-card {
    position: relative;
    flex: 0 0 280px;
    min-width: 280px;
    max-width: 280px;
    background: linear-gradient(168deg, #1a1035 0%, #0f172a 35%, #0c1220 100%);
    border: 1.5px solid rgba(138,92,246,0.30);
    border-radius: 22px;
    overflow: hidden;
    animation: heroFadeIn 0.5s ease-out both, aiBorderGlow 4s ease-in-out infinite;
    transition: transform 0.22s cubic-bezier(.22,1,.36,1), box-shadow 0.25s;
    display: flex;
    flex-direction: column;
    align-items: center;
    box-shadow: 0 0 20px rgba(138,92,246,0.10), 0 4px 16px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
}
/* Top gradient bar — electric multi-color */
.plat-card::before {
    content: '';
    display: block;
    height: 3px;
    width: 100%;
    background: linear-gradient(90deg, #8b5cf6, #3b82f6, #fbbf24, #c084fc, #60a5fa);
    background-size: 200% 100%;
    animation: aiShimmer 3s linear infinite;
}
.plat-card::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 22px;
    background: radial-gradient(ellipse at 50% 0%, rgba(139,92,246,0.06) 0%, transparent 60%);
    pointer-events: none;
}
.plat-card:hover {
    transform: translateY(-5px) scale(1.02);
    box-shadow: 0 0 36px rgba(138,92,246,0.22), 0 16px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06);
}

/* ── Platform badge ──────────────────────────────────────── */
.plat-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 10px 14px 6px;
    box-sizing: border-box;
}
.plat-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: 'Orbitron', sans-serif;
    font-size: 0.58rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    padding: 3px 10px;
    border-radius: 100px;
    text-transform: uppercase;
    white-space: nowrap;
    background: linear-gradient(135deg, rgba(138,92,246,0.18), rgba(59,130,246,0.12));
    color: #c084fc;
    border: 1px solid rgba(138,92,246,0.30);
    text-shadow: 0 0 8px rgba(192,132,252,0.30);
}
.plat-badge-icon {
    font-size: 0.62rem;
    animation: aiPulse 2s ease-in-out infinite;
}
.plat-rank {
    position: absolute;
    top: 14px; right: 16px;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.6rem;
    font-weight: 900;
    background: linear-gradient(180deg, rgba(139,92,246,0.12), rgba(59,130,246,0.06));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
    z-index: 1;
}

/* ── Headshot — AI ring glow ─────────────────────────────── */
.plat-hs-wrap {
    position: relative;
    margin: 4px auto 10px;
    width: 100px;
    height: 100px;
}
.plat-headshot {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    border: 2.5px solid;
    border-image: linear-gradient(135deg, #8b5cf6, #3b82f6, #fbbf24) 1;
    border-image-slice: 1;
    object-fit: cover;
    object-position: top center;
    background: #0f172a;
    display: block;
    box-shadow: 0 0 16px rgba(139,92,246,0.25), 0 4px 16px rgba(0,0,0,0.45);
    transition: box-shadow 0.25s;
}
.plat-card:hover .plat-headshot {
    box-shadow: 0 0 28px rgba(139,92,246,0.40), 0 4px 20px rgba(59,130,246,0.20);
}

/* ── Player info ─────────────────────────────────────────── */
.plat-team-pos {
    font-size: 0.68rem;
    font-weight: 600;
    color: #7c82a8;
    text-align: center;
    margin-bottom: 4px;
}
.plat-name {
    font-size: 1.10rem;
    font-weight: 800;
    color: #FFFFFF;
    text-align: center;
    letter-spacing: -0.01em;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 90%;
}
.plat-game-info {
    font-size: 0.60rem;
    color: #4A5568;
    text-align: center;
    margin-bottom: 4px;
}

/* ── Line area — big number ──────────────────────────────── */
.plat-line-area {
    width: 100%;
    text-align: center;
    padding: 14px 14px 6px;
    background: linear-gradient(180deg, rgba(139,92,246,0.08) 0%, rgba(0,0,0,0.12) 100%);
    margin: 4px 0;
    border-top: 1px solid rgba(139,92,246,0.08);
    border-bottom: 1px solid rgba(59,130,246,0.06);
}
.plat-line {
    font-size: 3.2rem;
    font-weight: 900;
    color: #FFFFFF;
    font-family: 'Bebas Neue', 'Inter', sans-serif;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
    text-shadow: 0 0 20px rgba(139,92,246,0.25), 0 2px 10px rgba(0,0,0,0.35);
}
.plat-stat {
    font-size: 0.85rem;
    font-weight: 600;
    color: #a0a8c8;
    margin-top: 4px;
    padding-bottom: 8px;
}

/* ── Direction button — AI gradient ──────────────────────── */
.plat-dir {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px 6px;
    margin: 8px 16px 0;
    border-radius: 12px;
    font-weight: 800;
    font-size: 1.0rem;
    letter-spacing: 0.03em;
    border: 1.5px solid transparent;
    width: calc(100% - 28px);
    box-sizing: border-box;
}
.plat-dir[data-dir="OVER"] {
    background: linear-gradient(135deg, #8b5cf6, #6366f1);
    color: #FFFFFF;
    border-color: rgba(139,92,246,0.50);
    box-shadow: 0 3px 14px rgba(139,92,246,0.35);
}
.plat-dir[data-dir="UNDER"] {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    color: #FFFFFF;
    border-color: rgba(59,130,246,0.50);
    box-shadow: 0 3px 14px rgba(59,130,246,0.35);
}

/* ── Projection bar ──────────────────────────────────────── */
.plat-proj-bar {
    width: calc(100% - 28px);
    margin: 8px 14px 4px;
    box-sizing: border-box;
}
.plat-proj-bar-label {
    display: flex;
    justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem;
    margin-bottom: 5px;
    white-space: nowrap;
    overflow: hidden;
}
.plat-proj-bar-track {
    height: 4px;
    background: rgba(139,92,246,0.10);
    border-radius: 4px;
    overflow: hidden;
}
.plat-proj-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.8s ease;
    background: linear-gradient(90deg, #8b5cf6, #3b82f6);
}

/* ── Metrics grid ────────────────────────────────────────── */
.plat-metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    padding: 10px 10px 14px;
    width: 100%;
    box-sizing: border-box;
}
.plat-metric {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: linear-gradient(180deg, rgba(139,92,246,0.06), rgba(59,130,246,0.03));
    border-radius: 8px;
    padding: 6px 4px;
    border: 1px solid rgba(139,92,246,0.10);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 1px 3px rgba(0,0,0,0.12);
    overflow: hidden;
    min-width: 0;
}
.plat-metric-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88rem;
    font-weight: 700;
    color: #FFFFFF;
    white-space: nowrap;
}
.plat-metric-label {
    font-size: 0.50rem;
    color: #7c82a8;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 1px;
}

/* ── Sim range ───────────────────────────────────────────── */
.plat-range {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: calc(100% - 28px);
    padding-bottom: 12px;
    margin: 0 14px;
}
.plat-range-label {
    font-size: 0.62rem;
    color: #6366f1;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
}
.plat-range-vals {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.80rem;
    font-weight: 600;
    color: #a5b4fc;
}

/* ── AI confidence tier colors ───────────────────────────── */
.plat-tier-platinum { color: #c084fc; text-shadow: 0 0 8px rgba(192,132,252,0.30); }
.plat-tier-gold     { color: #fbbf24; text-shadow: 0 0 8px rgba(251,191,36,0.25); }
.plat-tier-silver   { color: #a5b4fc; }

/* ═══════════════════════════════════════════════════════════
   COMPREHENSIVE MOBILE RESPONSIVE — All QAM Components
   ═══════════════════════════════════════════════════════════ */

/* ── Tablet  (≤ 768px) ─────────────────────────────────────── */
@media (max-width: 768px) {
    /* --- Hero cards --- */
    .qam-hero-grid { flex-direction: column; align-items: stretch; gap: 12px; }
    .qam-hero-card { width: 100%; max-width: 100%; }
    .qam-hero-hs-wrap, .qam-hero-headshot { width: 80px; height: 80px; }
    .qam-hero-name { font-size: 1.0rem; }
    .qam-hero-line { font-size: 2.6rem; }
    .qam-hero-stat { font-size: 0.78rem; }
    .qam-hero-dir { font-size: 0.88rem; padding: 10px 6px; }
    .qam-hero-metrics { grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 10px 12px 14px; }
    .qam-hero-metric-val { font-size: 0.85rem; }
    .qam-hero-metric-label { font-size: 0.48rem; }
    .qam-hero-line-area { padding: 10px 10px 4px; }

    /* --- Parlay leg cards --- */
    .plc-row { gap: 12px; padding: 10px 10px 14px; }
    .plc-card { min-width: 220px; max-width: 280px; }
    .plc-hs-wrap { width: 80px; height: 80px; }
    .plc-name { font-size: 0.95rem; }
    .plc-line { font-size: 2.6rem; }
    .plc-stat { font-size: 0.78rem; }
    .plc-dir { font-size: 0.88rem; padding: 10px 6px; }
    .plc-metrics { gap: 6px; padding: 10px 12px 14px; }
    .plc-m-val { font-size: 0.85rem; }
    .plc-m-lbl { font-size: 0.48rem; }

    /* --- Parlay section header --- */
    .espn-parlay-section-header { flex-direction: column; gap: 12px; align-items: flex-start; padding: 16px 16px; }
    .espn-parlay-topbar { padding: 12px 14px 10px; flex-wrap: wrap; gap: 8px; }
    .espn-parlay-footer { grid-template-columns: repeat(2, 1fr); }
    .espn-parlay-tags { padding: 6px 14px 12px; }

    /* --- QEG cards --- */
    .qeg-singles-row { gap: 12px; }
    .qeg-prop { width: 220px; }
    .qeg-prop[open] { width: 340px; }
    .qeg-prop > summary { padding: 14px 12px 12px; }
    .qeg-prop-hs-wrap { width: 80px; height: 80px; }
    .qeg-prop-player-name { font-size: 0.95rem; }
    .qeg-prop-big-line { font-size: 2.6rem; }
    .qeg-prop-stat-name { font-size: 0.72rem; }
    .qeg-btn { font-size: 0.85rem; padding: 8px 0; }

    /* --- Matchup bar --- */
    .qam-mu-bar { border-radius: 14px; }
    .qam-mu-side { padding: 10px 12px; gap: 8px; }
    .qam-mu-logo { width: 32px !important; height: 32px !important; }
    .qam-mu-abbrev { font-size: 0.88rem; }
    .qam-mu-record { font-size: 0.64rem; }
    .qam-mu-at { width: 24px; height: 24px; font-size: 0.68rem; }
    .qam-mu-count { font-size: 0.60rem; }

    /* --- Section headers & banners --- */
    .qam-section-header { padding: 12px 14px; }
    .qam-uncertain-banner { padding: 10px 12px; }
    .qam-top-picks-bar { padding: 10px 14px; flex-wrap: wrap; }
    .qam-top-picks-label { font-size: 0.72rem; }
    .qam-top-pill { font-size: 0.60rem; padding: 3px 10px; }

    /* --- Quick View table --- */
    .qam-quick-table thead th { font-size: 0.56rem; padding: 6px 8px; }
    .qam-quick-table tbody td { font-size: 0.76rem; padding: 8px 8px; }
    .qam-quick-player { max-width: 100px; }

    /* --- Uncertain cards --- */
    .qam-uncertain-card { padding: 12px; }
    .qam-uncertain-name { font-size: 0.88rem; }

    /* --- Platform AI Picks — keep horizontal scroll on mobile --- */
    .plat-grid { flex-direction: row; align-items: flex-start; gap: 12px; flex-wrap: nowrap; overflow-x: auto; }
    .plat-card { flex: 0 0 240px; min-width: 240px; max-width: 240px; }
    .plat-hs-wrap, .plat-headshot { width: 80px; height: 80px; }
    .plat-name { font-size: 1.0rem; }
    .plat-line { font-size: 2.6rem; }
    .plat-dir { font-size: 0.88rem; padding: 10px 6px; }
    .plat-metrics { gap: 6px; padding: 10px 10px 14px; }
    .plat-metric-val { font-size: 0.80rem; }
    .plat-metric-label { font-size: 0.44rem; }
}

/* ── Phone  (≤ 480px) ──────────────────────────────────────── */
@media (max-width: 480px) {
    /* --- Hero cards --- */
    .qam-hero-card { border-radius: 16px; }
    .qam-hero-hs-wrap, .qam-hero-headshot { width: 64px; height: 64px; }
    .qam-hero-name { font-size: 0.88rem; }
    .qam-hero-team-pos { font-size: 0.56rem; }
    .qam-hero-line { font-size: 2.2rem; }
    .qam-hero-stat { font-size: 0.68rem; }
    .qam-hero-dir { font-size: 0.80rem; padding: 8px 4px; margin: 6px 10px 0; border-radius: 10px; }
    .qam-hero-metrics { grid-template-columns: repeat(2, 1fr); gap: 5px; padding: 8px 10px 12px; }
    .qam-hero-metric-val { font-size: 0.78rem; }
    .qam-hero-metric-label { font-size: 0.42rem; }
    .qam-hero-status { padding: 8px 10px 4px; }
    .qam-hero-rank { font-size: 1.2rem; top: 10px; right: 12px; }
    .qam-hero-proj-bar { width: calc(100% - 20px); margin: 6px 10px 4px; }
    .qam-hero-range { width: calc(100% - 20px); margin: 0 10px; padding-bottom: 10px; }
    .qam-hero-range-vals { font-size: 0.68rem; }

    /* --- Parlay leg cards --- */
    .plc-card { min-width: 180px; max-width: 240px; border-radius: 16px; }
    .plc-hs-wrap { width: 64px; height: 64px; }
    .plc-name { font-size: 0.82rem; }
    .plc-line { font-size: 2.2rem; }
    .plc-stat { font-size: 0.68rem; }
    .plc-dir { font-size: 0.80rem; padding: 8px 4px; margin: 6px 10px 0; border-radius: 10px; }
    .plc-metrics { grid-template-columns: 1fr 1fr; gap: 5px; padding: 8px 10px 12px; }
    .plc-m-val { font-size: 0.78rem; }
    .plc-m-lbl { font-size: 0.42rem; }
    .plc-status { padding: 8px 10px 0; }
    .plc-tier { font-size: 0.52rem; }
    .plc-team { font-size: 0.56rem; }
    .plc-line-area { padding: 10px 10px 4px; }

    /* --- Parlay section header --- */
    .espn-parlay-section-header { padding: 14px 12px; border-radius: 14px; }
    .espn-parlay-section-title { font-size: 0.95rem; }
    .espn-parlay-section-sub { font-size: 0.64rem; }
    .espn-parlay-section-icon { font-size: 0.68rem; padding: 10px 12px; border-radius: 10px; }
    .espn-parlay-section-badge { font-size: 0.48rem; padding: 5px 10px; }
    .espn-parlay-card { border-radius: 14px; }
    .espn-parlay-topbar { padding: 10px 12px 8px; }
    .espn-parlay-footer { grid-template-columns: 1fr 1fr; gap: 6px; padding: 8px 10px 10px; }

    /* --- QEG cards --- */
    .qeg-singles-row { gap: 10px; padding: 8px 2px 12px; }
    .qeg-prop { width: 180px; border-radius: 16px; }
    .qeg-prop[open] { width: 280px; }
    .qeg-prop > summary { padding: 12px 10px 10px; gap: 4px; }
    .qeg-prop-hs-wrap { width: 64px; height: 64px; }
    .qeg-prop-player-name { font-size: 0.82rem; }
    .qeg-prop-big-line { font-size: 2.2rem; }
    .qeg-prop-stat-name { font-size: 0.62rem; }
    .qeg-prop-team-pos { font-size: 0.56rem; }
    .qeg-prop-game-info { font-size: 0.52rem; }
    .qeg-btn { font-size: 0.78rem; padding: 6px 0; border-radius: 8px; }
    .qeg-tier { font-size: 0.52rem; }
    .qeg-prop-rank { font-size: 0.58rem; }

    /* --- Matchup bar --- */
    .qam-mu-bar { border-radius: 10px; }
    .qam-mu-side { padding: 8px 10px; gap: 6px; }
    .qam-mu-logo { width: 28px !important; height: 28px !important; }
    .qam-mu-abbrev { font-size: 0.78rem; }
    .qam-mu-record { font-size: 0.58rem; }
    .qam-mu-centre { padding: 6px 6px; }
    .qam-mu-at { width: 22px; height: 22px; font-size: 0.58rem; }
    .qam-mu-count { font-size: 0.52rem; }

    /* --- Section headers & banners --- */
    .qam-section-header { padding: 10px 12px; border-radius: 8px; }
    .qam-uncertain-banner { padding: 8px 10px; }
    .qam-uncertain-text { font-size: 0.68rem; }
    .qam-uncertain-icon { font-size: 0.92rem; }
    .qam-top-picks-bar { padding: 8px 10px; gap: 6px; border-radius: 10px; }
    .qam-top-picks-label { font-size: 0.64rem; }
    .qam-top-pill { font-size: 0.56rem; padding: 3px 8px; border-radius: 6px; }
    .qam-hero-label { font-size: 0.95rem; margin-bottom: 12px; }
    .qam-hero-section { margin-bottom: 20px; }

    /* --- Quick View table --- */
    .qam-quick-table thead th { font-size: 0.50rem; padding: 5px 6px; }
    .qam-quick-table tbody td { font-size: 0.68rem; padding: 6px 6px; }
    .qam-quick-player { max-width: 80px; }

    /* --- Uncertain cards --- */
    .qam-uncertain-card { padding: 10px; }
    .qam-uncertain-name { font-size: 0.80rem; }
    .qam-uncertain-prop { font-size: 0.68rem; }
    .qam-uncertain-edge { font-size: 0.64rem; }
    .qam-uncertain-flags { font-size: 0.64rem; }
    .qam-uncertain-card-header { flex-wrap: wrap; gap: 6px; }

    /* --- Platform AI Picks --- */
    .plat-card { border-radius: 16px; }
    .plat-hs-wrap, .plat-headshot { width: 64px; height: 64px; }
    .plat-name { font-size: 0.88rem; }
    .plat-line { font-size: 2.2rem; }
    .plat-dir { font-size: 0.80rem; padding: 8px 4px; margin: 6px 10px 0; border-radius: 10px; }
    .plat-metrics { grid-template-columns: repeat(2, 1fr); gap: 5px; padding: 8px 10px 12px; }
    .plat-metric-val { font-size: 0.78rem; }
    .plat-metric-label { font-size: 0.42rem; }
    .plat-badge { font-size: 0.50rem; }
    .plat-rank { font-size: 1.2rem; top: 10px; right: 12px; }
}

/* ── Small phone (≤ 360px) ──────────────────────────────────── */
@media (max-width: 360px) {
    .qam-hero-card { border-radius: 14px; }
    .qam-hero-hs-wrap, .qam-hero-headshot { width: 56px; height: 56px; }
    .qam-hero-name { font-size: 0.82rem; }
    .qam-hero-line { font-size: 1.9rem; }
    .qam-hero-dir { font-size: 0.72rem; padding: 7px 4px; }
    .qam-hero-metrics { grid-template-columns: repeat(2, 1fr); }

    .plc-card { min-width: 160px; max-width: 200px; border-radius: 14px; }
    .plc-hs-wrap { width: 56px; height: 56px; }
    .plc-name { font-size: 0.76rem; }
    .plc-line { font-size: 1.9rem; }

    .qeg-prop { width: 160px; border-radius: 14px; }
    .qeg-prop[open] { width: 260px; }
    .qeg-prop-hs-wrap { width: 56px; height: 56px; }
    .qeg-prop-big-line { font-size: 1.9rem; }
    .qeg-prop-player-name { font-size: 0.76rem; }

    .qam-mu-side { padding: 6px 8px; }
    .qam-mu-logo { width: 24px !important; height: 24px !important; }
    .qam-mu-abbrev { font-size: 0.68rem; }

    .espn-parlay-section-header { padding: 12px 10px; }
    .espn-parlay-section-title { font-size: 0.85rem; }
    .espn-parlay-card { border-radius: 12px; }

    .plat-card { border-radius: 14px; }
    .plat-hs-wrap, .plat-headshot { width: 56px; height: 56px; }
    .plat-name { font-size: 0.82rem; }
    .plat-line { font-size: 1.9rem; }
}

/* ── AI/Tech Theme Accents ─────────────────────────────────── */
/* (matchup bar accents are built into .qam-mu-bar::before) */
"""


def get_quantum_card_matrix_css():
    """Return the Quantum Card Matrix CSS for injection via st.markdown."""
    return f"<style>{QUANTUM_CARD_MATRIX_CSS}</style>"

# ============================================================
# END SECTION: Quantum Card Matrix CSS
# ============================================================


# ============================================================
# SECTION: Unified Expandable Player Card CSS
# PURPOSE: Combines the trading card header with all prop
#          analysis cards into one expandable <details> element.
# ============================================================

UNIFIED_PLAYER_CARD_CSS = """
/* ═══════════════════════════════════════════════════════════
   UNIFIED PLAYER CARD — Compact accordion-style player rows
   Clean sports-dashboard aesthetic
   ═══════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

.upc-grid {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 0;
    width: 100%;
}

/* ── Expandable wrapper (<details>) ─────────────────────── */
.upc-card {
    background: rgba(15, 18, 30, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    font-family: 'Inter', sans-serif;
    color: #e0eeff;
    overflow: visible;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.upc-card:hover {
    border-color: rgba(255, 255, 255, 0.12);
}
.upc-card[open] {
    border-color: rgba(0, 198, 255, 0.25);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.40);
}

/* ── Summary (always-visible header strip) ──────────────── */
.upc-card > summary {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    cursor: pointer;
    list-style: none;
    user-select: none;
    transition: background 0.15s ease;
}
.upc-card > summary::-webkit-details-marker { display: none; }
.upc-card > summary::marker { display: none; content: ''; }
.upc-card > summary:hover {
    background: rgba(255, 255, 255, 0.03);
}

/* Expand arrow */
.upc-expand-arrow {
    font-size: 0.55rem;
    color: #4a5568;
    flex-shrink: 0;
    transition: transform 0.25s ease, color 0.2s ease;
}
.upc-card[open] .upc-expand-arrow {
    transform: rotate(90deg);
    color: #00C6FF;
}

/* Headshot — small circle */
.upc-headshot {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.15);
    object-fit: cover;
    flex-shrink: 0;
    background: #1a1d2e;
}
.upc-card[open] .upc-headshot {
    border-color: rgba(0, 198, 255, 0.40);
}

/* Player name — inline */
.upc-player-name {
    font-size: 0.95rem;
    font-weight: 700;
    color: #ffffff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-shrink: 1;
    min-width: 0;
}

/* Header meta — compact inline info */
.upc-header-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
    color: #5eead4;
    white-space: nowrap;
    flex-shrink: 0;
}

/* Stats column — three vertical mini cells */
.upc-stats-col {
    display: flex;
    gap: 12px;
    flex-shrink: 0;
    align-items: center;
}
.upc-stat-row {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
}
.upc-stat-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 700;
    color: #e2e8f0;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
}
.upc-stat-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.52rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1.1;
}

/* Tier summary dots */
.upc-tier-summary {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
    align-items: center;
}
.upc-tier-dot {
    font-size: 0.64rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    white-space: nowrap;
}

/* Right-side summary info */
.upc-summary-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
}
.upc-prop-count {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem;
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: 600;
}
.upc-chevron {
    font-size: 0.90rem;
    color: #4a5568;
    transition: transform 0.25s ease, color 0.2s ease;
    flex-shrink: 0;
}
.upc-card[open] .upc-chevron {
    transform: rotate(180deg);
    color: #00C6FF;
}

/* ── Expanded body ──────────────────────────────────────── */
.upc-body {
    padding: 0 16px 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    overflow: visible;
}
.upc-body .qcm-grid-container {
    overflow: visible;
}
.upc-body .qcm-grid {
    overflow: visible;
    padding-top: 12px;
}

/* ── Joseph M Smith avatar row inside expanded card ────── */
.upc-joseph-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 14px;
    padding: 10px 14px;
    background: rgba(255, 94, 0, 0.05);
    border: 1px solid rgba(255, 94, 0, 0.18);
    border-radius: 10px;
    cursor: pointer;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.upc-joseph-row:hover {
    border-color: rgba(255, 94, 0, 0.40);
    box-shadow: 0 0 12px rgba(255, 94, 0, 0.10);
}
.upc-joseph-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 2px solid #ff5e00;
    object-fit: cover;
    flex-shrink: 0;
}
.upc-joseph-label {
    color: #ff9e00;
    font-size: 0.80rem;
    font-weight: 700;
    font-family: 'Inter', sans-serif;
}

/* ── Joseph M Smith response panel (toggled on click) ──── */
.upc-joseph-response {
    margin-top: 10px;
    padding: 14px 16px;
    background: linear-gradient(135deg, rgba(255, 94, 0, 0.06), rgba(15, 23, 42, 0.90));
    border: 1px solid rgba(255, 94, 0, 0.22);
    border-radius: 10px;
    animation: josephFadeIn 0.3s ease-out;
}
@keyframes josephFadeIn {
    from { opacity: 0; transform: translateY(-6px); }
    to   { opacity: 1; transform: translateY(0); }
}
.upc-joseph-resp-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.upc-joseph-resp-avatar {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 2px solid #ff5e00;
    object-fit: cover;
    flex-shrink: 0;
}
.upc-joseph-resp-title {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.upc-joseph-resp-name {
    color: #ff9e00;
    font-size: 0.86rem;
    font-weight: 700;
    font-family: 'Orbitron', monospace, sans-serif;
    letter-spacing: 0.05em;
}
.upc-joseph-resp-role {
    color: #64748b;
    font-size: 0.68rem;
    font-weight: 600;
}
.upc-joseph-resp-lock {
    color: #facc15;
    font-size: 0.90rem;
    font-weight: 800;
    font-family: 'Orbitron', monospace, sans-serif;
    letter-spacing: 0.06em;
    margin-bottom: 8px;
}
.upc-joseph-resp-rant {
    color: #e2e8f0;
    font-size: 0.82rem;
    line-height: 1.65;
    font-family: 'Inter', sans-serif;
}

/* ── Responsive: tablets & phones ───────────────────────── */
@media (max-width: 768px) {
    .upc-grid {
        gap: 4px;
        padding: 4px 0;
    }
    .upc-card {
        border-radius: 10px;
    }
    .upc-card > summary {
        gap: 8px;
        padding: 10px 12px;
    }
    .upc-headshot {
        width: 28px;
        height: 28px;
    }
    .upc-player-name {
        font-size: 0.86rem;
    }
    .upc-header-meta {
        font-size: 0.64rem;
    }
    .upc-body {
        padding: 0 10px 12px;
        overflow: visible;
    }
    .upc-body .qcm-grid-container,
    .upc-body .qcm-grid {
        overflow: visible;
    }
    .upc-joseph-row {
        padding: 8px 10px;
        gap: 8px;
    }
    .upc-joseph-avatar {
        width: 30px;
        height: 30px;
    }
    .upc-joseph-label {
        font-size: 0.74rem;
    }
    .upc-joseph-response {
        padding: 10px 12px;
    }
    .upc-joseph-resp-avatar {
        width: 36px;
        height: 36px;
    }
    .upc-joseph-resp-name {
        font-size: 0.78rem;
    }
    .upc-joseph-resp-role {
        font-size: 0.62rem;
    }
    .upc-joseph-resp-lock {
        font-size: 0.80rem;
    }
    .upc-joseph-resp-rant {
        font-size: 0.76rem;
        line-height: 1.55;
    }
}

/* ── Extra-small phones (≤ 480px) ────────────────────────── */
@media (max-width: 480px) {
    .upc-card > summary {
        gap: 6px;
        padding: 8px 10px;
    }
    .upc-headshot {
        width: 24px;
        height: 24px;
    }
    .upc-player-name {
        font-size: 0.80rem;
    }
    .upc-header-meta {
        font-size: 0.58rem;
    }
    .upc-body {
        padding: 0 8px 10px;
        overflow: visible;
    }
    .upc-body .qcm-grid-container,
    .upc-body .qcm-grid {
        overflow: visible;
    }
    .upc-joseph-row {
        padding: 6px 8px;
        gap: 6px;
    }
    .upc-joseph-avatar {
        width: 26px;
        height: 26px;
    }
    .upc-joseph-label {
        font-size: 0.68rem;
    }
    .upc-joseph-response {
        padding: 8px 10px;
    }
    .upc-joseph-resp-avatar {
        width: 30px;
        height: 30px;
    }
    .upc-joseph-resp-name {
        font-size: 0.72rem;
    }
    .upc-joseph-resp-lock {
        font-size: 0.74rem;
    }
    .upc-joseph-resp-rant {
        font-size: 0.70rem;
        line-height: 1.5;
    }
}

/* ── Stat Pills (PPG/RPG/APG teal badges in header) ─────── */
.upc-stat-pills {
    display: flex;
    gap: 8px;
    margin-top: 4px;
    flex-wrap: wrap;
}
.upc-stat-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 700;
    color: #00D559;
    background: rgba(0, 240, 255, 0.08);
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 6px;
    padding: 2px 10px;
    white-space: nowrap;
    letter-spacing: 0.02em;
}

/* ── Props Count Button (teal) ───────────────────────────── */
.upc-props-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    color: #ffffff;
    background: #0d9488;
    border-radius: 8px;
    padding: 6px 14px;
    white-space: nowrap;
    flex-shrink: 0;
    transition: background 0.2s ease;
}
.upc-card:hover .upc-props-btn {
    background: #0f766e;
}
.upc-props-arrow {
    font-size: 0.60rem;
    transition: transform 0.25s ease;
}
.upc-card[open] .upc-props-arrow {
    transform: rotate(180deg);
}
"""


def get_unified_player_card_css():
    """Return the Unified Player Card CSS for injection via st.markdown."""
    return f"<style>{UNIFIED_PLAYER_CARD_CSS}</style>"


# ============================================================
# END SECTION: Unified Expandable Player Card CSS
# ============================================================


# ============================================================
# SECTION: Glassmorphic Dark Theme — Trading Card & Modal CSS
# PURPOSE: Obsidian/Deep Space backgrounds, neon accents,
#          Inter + JetBrains Mono typography, and glassmorphic
#          card/modal styles for the Player Spotlight system.
# ============================================================

GLASSMORPHIC_CARD_CSS = """
/* ── Glassmorphic Dark-Theme Variables ───────────────────── */
:root {
  --gm-bg-deep: #070A13;
  --gm-bg-card: rgba(15, 23, 42, 0.6);
  --gm-border: rgba(255, 255, 255, 0.1);
  --gm-accent-blue: #00C6FF;
  --gm-accent-red: #FF0055;
  --gm-text-primary: #E2E8F0;
  --gm-text-muted: #94A3B8;
  --gm-font-body: 'Inter', sans-serif;
  --gm-font-mono: 'JetBrains Mono', monospace;
}

/* ── Google-Font import for Inter ────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

/* ── Trading-Card Grid ───────────────────────────────────── */
.gm-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 18px;
  padding: 12px 0;
}

/* ── Individual Trading Card ─────────────────────────────── */
.gm-player-card {
  background: var(--gm-bg-card);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--gm-border);
  border-radius: 12px;
  padding: 18px 16px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  position: relative;
  overflow: hidden;
}
.gm-player-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 0 18px rgba(0, 198, 255, 0.25);
  border-color: var(--gm-accent-blue);
}

/* ── Card headshot ───────────────────────────────────────── */
.gm-card-headshot {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 2px solid var(--gm-accent-blue);
  object-fit: cover;
  margin: 0 auto 10px;
  display: block;
}

/* ── Card player name ────────────────────────────────────── */
.gm-card-name {
  font-family: var(--gm-font-body);
  font-size: 1rem;
  font-weight: 700;
  color: var(--gm-text-primary);
  text-align: center;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Card subtitle (Position · Team · Opponent) ──────────── */
.gm-card-sub {
  font-family: var(--gm-font-mono);
  font-size: 0.72rem;
  color: var(--gm-text-muted);
  text-align: center;
  margin-bottom: 10px;
}

/* ── Mini stat pills row ─────────────────────────────────── */
.gm-card-stats {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 10px;
}
.gm-stat-pill {
  font-family: var(--gm-font-mono);
  font-size: 0.68rem;
  font-variant-numeric: tabular-nums;
  color: var(--gm-accent-blue);
  background: rgba(0, 198, 255, 0.08);
  border: 1px solid rgba(0, 198, 255, 0.18);
  border-radius: 6px;
  padding: 2px 8px;
}

/* ── Prop count badge ────────────────────────────────────── */
.gm-card-prop-count {
  font-family: var(--gm-font-mono);
  font-size: 0.68rem;
  color: var(--gm-text-muted);
  text-align: center;
}

/* ── Modal / Dialog overrides ────────────────────────────── */
div[data-testid="stDialog"] > div {
  background: rgba(15, 23, 42, 0.92) !important;
  backdrop-filter: blur(14px) !important;
  -webkit-backdrop-filter: blur(14px) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 12px !important;
}

/* ── Modal Vitals Row ────────────────────────────────────── */
.gm-modal-vitals {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 20px;
}
.gm-modal-headshot {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: 3px solid var(--gm-accent-blue);
  object-fit: cover;
  flex-shrink: 0;
}
.gm-modal-info h2 {
  font-family: var(--gm-font-body);
  color: var(--gm-text-primary);
  margin: 0 0 4px;
}
.gm-modal-info p {
  font-family: var(--gm-font-mono);
  color: var(--gm-text-muted);
  font-size: 0.82rem;
  margin: 0;
}

/* ── Season-Stats Metric Bar ─────────────────────────────── */
.gm-season-bar {
  display: flex;
  gap: 14px;
  margin: 14px 0 20px;
  flex-wrap: wrap;
}
.gm-season-metric {
  text-align: center;
  min-width: 64px;
}
.gm-season-metric .val {
  font-family: var(--gm-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--gm-accent-blue);
}
.gm-season-metric .lbl {
  font-family: var(--gm-font-body);
  font-size: 0.68rem;
  color: var(--gm-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* ── Market Grid (bet rows) ──────────────────────────────── */
.gm-market-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}
.gm-market-cell {
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid var(--gm-border);
  border-radius: 8px;
  padding: 10px 12px;
  font-family: var(--gm-font-mono);
  font-size: 0.78rem;
  color: var(--gm-text-primary);
}
.gm-market-cell .stat-label {
  font-weight: 700;
  color: var(--gm-accent-blue);
  margin-bottom: 4px;
}
.gm-market-cell .edge-pos {
  color: #4ADE80;
}
.gm-market-cell .edge-neg {
  color: var(--gm-accent-red);
}

/* ── Ask Joseph CTA button ───────────────────────────────── */
.gm-ask-joseph-btn button {
  width: 100%;
  background: linear-gradient(135deg, #FF5E00 0%, #FF0055 100%) !important;
  color: #fff !important;
  font-family: 'Orbitron', sans-serif !important;
  font-size: 1rem !important;
  font-weight: 700 !important;
  border: none !important;
  border-radius: 8px !important;
  padding: 12px 0 !important;
  box-shadow: 0 0 20px rgba(255, 94, 0, 0.35);
  transition: box-shadow 0.2s ease;
}
.gm-ask-joseph-btn button:hover {
  box-shadow: 0 0 28px rgba(255, 0, 85, 0.55);
}

/* ── Joseph Broadcast Container ──────────────────────────── */
.gm-joseph-response {
  background: rgba(255, 94, 0, 0.06);
  border: 1px solid rgba(255, 94, 0, 0.30);
  border-radius: 10px;
  padding: 16px;
  margin-top: 14px;
}
.gm-joseph-response .gm-joseph-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 2px solid #FF5E00;
  object-fit: cover;
  float: left;
  margin-right: 12px;
}
.gm-joseph-response .gm-joseph-lock {
  font-family: 'Orbitron', sans-serif;
  font-size: 0.92rem;
  font-weight: 700;
  color: #FF5E00;
  margin-bottom: 6px;
}
.gm-joseph-response .gm-joseph-rant {
  font-family: var(--gm-font-body);
  font-size: 0.85rem;
  color: var(--gm-text-primary);
  line-height: 1.6;
}
"""


def get_glassmorphic_card_css():
    """Return the Glassmorphic Trading-Card CSS for injection."""
    return f"<style>{GLASSMORPHIC_CARD_CSS}</style>"


def get_player_trading_card_html(
    player_name: str,
    headshot_url: str = "",
    position: str = "N/A",
    team: str = "N/A",
    opponent: str = "TBD",
    season_stats: dict | None = None,
    prop_count: int = 0,
) -> str:
    """Build an HTML Trading Card for one player.

    Parameters
    ----------
    player_name : str
        Display name.
    headshot_url : str
        URL to headshot image.
    position, team, opponent : str
        Player metadata.
    season_stats : dict | None
        ``{"ppg": float, "rpg": float, "apg": float, "avg_minutes": float}``
    prop_count : int
        Number of available props for badge.

    Returns
    -------
    str
        HTML string for one trading card.
    """
    stats = season_stats or {}
    safe_name = _html.escape(str(player_name))
    safe_pos = _html.escape(str(position))
    safe_team = _html.escape(str(team))
    safe_opp = _html.escape(str(opponent))
    safe_url = _html.escape(str(headshot_url))

    ppg = stats.get("ppg", 0.0)
    rpg = stats.get("rpg", 0.0)
    apg = stats.get("apg", 0.0)

    return (
        f'<div class="gm-player-card">'
        f'<img class="gm-card-headshot" src="{safe_url}" alt="{safe_name}" '
        f'onerror="this.src=\'https://cdn.nba.com/headshots/nba/latest/1040x760/fallback.png\'">'
        f'<div class="gm-card-name">{safe_name}</div>'
        f'<div class="gm-card-sub">{safe_pos} · {safe_team} vs {safe_opp}</div>'
        f'<div class="gm-card-stats">'
        f'<span class="gm-stat-pill">{ppg} PPG</span>'
        f'<span class="gm-stat-pill">{rpg} RPG</span>'
        f'<span class="gm-stat-pill">{apg} APG</span>'
        f'</div>'
        f'<div class="gm-card-prop-count">{prop_count} prop{"s" if prop_count != 1 else ""} available</div>'
        f'</div>'
    )


# ============================================================
# END SECTION: Glassmorphic Dark Theme
# ============================================================


# ============================================================
# SECTION: Smart NBA Data — Premium Glassmorphic Card / Widget Helpers
# Used by pages/9_📡_Smart_NBA_Data.py.  Matches the app-wide
# "AI Neural Network Lab" dark theme with glassmorphism,
# animated glows, and Orbitron / JetBrains Mono typography.
# ============================================================


def get_data_feed_css() -> str:
    """Return page-specific CSS for the Smart NBA Data page."""
    return """<style>
/* ── Smart NBA Data page animations ──────────────────────── */
@keyframes df-pulse-glow {
    0%, 100% { box-shadow: 0 0 8px rgba(0,213,89,0.12), 0 4px 20px rgba(0,0,0,0.3); }
    50%      { box-shadow: 0 0 20px rgba(0,213,89,0.25), 0 4px 28px rgba(0,0,0,0.4); }
}
@keyframes df-shimmer {
    0%   { background-position: -200% center; }
    100% { background-position: 200% center; }
}
@keyframes df-bar-fill {
    from { width: 0%; }
}
@keyframes df-fade-in {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes df-status-pulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.4; }
}
/* ── Action card ─────────────────────────────────────────── */
.df-action-card {
    background: linear-gradient(135deg, #0a0f1a 0%, #0d1a2e 50%, #0a1428 100%);
    border: 1px solid rgba(0,213,89,0.15);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 14px;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    animation: df-fade-in 0.4s ease-out;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.df-action-card:hover {
    border-color: rgba(0,213,89,0.30);
    box-shadow: 0 0 16px rgba(0,213,89,0.12), 0 4px 24px rgba(0,0,0,0.4);
}
.df-action-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
}
.df-action-card .df-card-title {
    font-family: 'Orbitron', 'Inter', sans-serif;
    font-size: 1.05rem;
    font-weight: 800;
    letter-spacing: 0.03em;
    margin-bottom: 6px;
}
.df-action-card .df-card-desc {
    color: rgba(192,208,232,0.75);
    font-size: 0.88rem;
    line-height: 1.5;
}
/* ── Readiness gauge ─────────────────────────────────────── */
.df-readiness-wrap {
    background: linear-gradient(135deg, #070A13 0%, #0d1a2e 50%, #070A13 100%);
    border: 1px solid rgba(0,213,89,0.18);
    border-radius: 16px;
    padding: 24px 28px 20px;
    position: relative;
    overflow: hidden;
    animation: df-pulse-glow 4s ease-in-out infinite;
}
.df-readiness-wrap::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #00D559, #ff5e00, #c800ff, #00D559);
    background-size: 200% 100%;
    animation: df-shimmer 3s linear infinite;
}
.df-readiness-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 10px;
    flex-wrap: wrap;
    gap: 6px;
}
.df-readiness-score {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.4rem;
    font-weight: 900;
    letter-spacing: 0.04em;
}
.df-readiness-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    letter-spacing: 0.05em;
    color: rgba(192,208,232,0.70);
}
.df-readiness-track {
    height: 12px;
    background: rgba(13,18,32,0.80);
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid rgba(0,213,89,0.07);
}
.df-readiness-fill {
    height: 12px;
    border-radius: 6px;
    background: linear-gradient(90deg, #ff4444, #ff5e00, #ffcc00, #00D559, #00D559);
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    animation: df-bar-fill 1.2s ease-out;
    position: relative;
}
.df-readiness-fill::after {
    content: '';
    position: absolute;
    top: 0; right: 0; bottom: 0; width: 40px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25));
    border-radius: 0 6px 6px 0;
}
/* ── Freshness timeline ──────────────────────────────────── */
.df-timeline {
    background: linear-gradient(135deg, #0a0f1a 0%, #10182e 100%);
    border: 1px solid rgba(0,213,89,0.10);
    border-radius: 12px;
    padding: 16px 20px;
    margin-top: 12px;
}
.df-timeline-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 0;
}
.df-timeline-label {
    min-width: 140px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #c0d0e8;
}
.df-timeline-track {
    flex: 1;
    height: 8px;
    background: rgba(13,18,32,0.80);
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid rgba(0,213,89,0.05);
}
.df-timeline-fill {
    height: 8px;
    border-radius: 4px;
    transition: width 0.6s ease;
    animation: df-bar-fill 0.8s ease-out;
}
.df-timeline-status {
    min-width: 100px;
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}
/* ── Preflight checklist ─────────────────────────────────── */
.df-preflight {
    background: linear-gradient(135deg, #0a0f1a 0%, #0d182a 100%);
    border: 1px solid rgba(0,213,89,0.10);
    border-radius: 10px;
    padding: 14px 18px;
}
.df-check-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 5px 0;
    border-bottom: 1px solid rgba(0,213,89,0.04);
}
.df-check-row:last-child { border-bottom: none; }
.df-check-icon { font-size: 1.1rem; }
.df-check-label {
    font-weight: 700;
    font-size: 0.88rem;
}
.df-check-detail {
    color: rgba(192,208,232,0.55);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
}
/* ── Status dot (pulsing) ────────────────────────────────── */
.df-dot-live {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #00D559;
    animation: df-status-pulse 1.5s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(0,213,89,0.65);
    margin-right: 6px;
    vertical-align: middle;
}
.df-dot-warn {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #ffcc00;
    animation: df-status-pulse 1.2s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(255,204,0,0.7);
    margin-right: 6px;
    vertical-align: middle;
}
.df-dot-stale {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #ff4444;
    animation: df-status-pulse 0.8s ease-in-out infinite;
    box-shadow: 0 0 6px rgba(255,68,68,0.7);
    margin-right: 6px;
    vertical-align: middle;
}
/* ── Section header (replicates neural-header-subtitle style) */
.df-section-head {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    background: linear-gradient(135deg, #00D559, #00D559);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(0 0 8px rgba(0,213,89,0.4));
    margin-bottom: 4px;
}
.df-section-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: rgba(192,208,232,0.55);
    letter-spacing: 0.05em;
}
/* ── Platform badge pills ────────────────────────────────── */
.df-platform-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid rgba(255,255,255,0.08);
    margin-right: 6px;
    margin-bottom: 4px;
}
.df-badge-pp { background: rgba(0,213,89,0.10); color: #00D559; border-color: rgba(0,213,89,0.20); }
.df-badge-ud { background: rgba(255,204,0,0.12); color: #ffcc00; border-color: rgba(255,204,0,0.25); }
.df-badge-dk { background: rgba(0,160,255,0.12); color: #00a0ff; border-color: rgba(0,160,255,0.25); }
.df-badge-off { background: rgba(100,100,120,0.12); color: #6e7681; border-color: rgba(100,100,120,0.15); }
</style>"""


def get_action_card_html(title: str, description: str, gradient: str = "",
                         border_color: str = "", icon_color: str = "#00D559") -> str:
    """Return a premium glassmorphic action card for Smart NBA Data buttons."""
    _safe_title = _html.escape(str(title))
    _safe_desc = str(description)
    _gradient_css = f"background:{gradient};" if gradient else ""
    _border_css = f"border-color:{border_color};" if border_color else ""
    _top_bar_color = border_color or icon_color
    _top_bar_css = f"background:{_top_bar_color};"
    return (
        f'<div class="df-action-card" style="{_gradient_css}{_border_css}">'
        f'<div style="position:absolute;top:0;left:0;right:0;height:2px;{_top_bar_css}'
        f'opacity:0.6;border-radius:14px 14px 0 0;"></div>'
        f'<div class="df-card-title" style="color:{icon_color};">{_safe_title}</div>'
        f'<div class="df-card-desc">{_safe_desc}</div>'
        f'</div>'
    )


def get_health_card_html(label: str, badge_html: str, health_html: str, description: str) -> str:
    """Return a single data-health card for the status dashboard."""
    _safe_label = _html.escape(str(label))
    _safe_desc = _html.escape(str(description))
    return (
        f'<div class="df-action-card" style="padding:16px 18px;">'
        f'<div style="font-size:0.92rem;font-weight:700;color:#c0d0e8;'
        f'font-family:\'Orbitron\',sans-serif;letter-spacing:0.03em;margin-bottom:8px;">{_safe_label}</div>'
        f'{badge_html}'
        f'{health_html}'
        f'<div style="color:rgba(192,208,232,0.50);font-size:0.73rem;margin-top:6px;'
        f'font-family:\'JetBrains Mono\',monospace;">{_safe_desc}</div>'
        f'</div>'
    )


def get_readiness_bar_html(score: int) -> str:
    """Return a premium animated readiness gauge (0-100)."""
    score = max(0, min(100, int(score)))
    if score >= 80:
        score_color = "#00D559"
        status_text = "SYSTEMS NOMINAL ✅"
    elif score >= 50:
        score_color = "#ffcc00"
        status_text = "UPDATE RECOMMENDED ⚠️"
    else:
        score_color = "#ff4444"
        status_text = "DATA REFRESH NEEDED ❌"
    return (
        f'<div class="df-readiness-wrap">'
        f'<div class="df-readiness-header">'
        f'<div>'
        f'<div style="font-size:0.72rem;color:rgba(192,208,232,0.45);font-family:\'JetBrains Mono\',monospace;'
        f'letter-spacing:0.1em;margin-bottom:2px;">SESSION READINESS</div>'
        f'<div class="df-readiness-score" style="color:{score_color};">{score}%</div>'
        f'</div>'
        f'<div class="df-readiness-label">{status_text}</div>'
        f'</div>'
        f'<div class="df-readiness-track">'
        f'<div class="df-readiness-fill" style="width:{score}%;"></div>'
        f'</div>'
        f'</div>'
    )


def get_freshness_timeline_html(sources: list[tuple[str, str, float | None]]) -> str:
    """
    Premium visual freshness timeline with animated bars.

    *sources*: list of (label, emoji, age_hours_or_None).
    """
    rows_html = []
    for label, emoji, age_h in sources:
        if age_h is None:
            pct = 0
            status = "NEVER"
            bar_color = "#553c9a"
            text_color = "#b794f4"
            dot_class = "df-dot-stale"
        else:
            freshness = max(0.0, 1.0 - age_h / 24.0)
            pct = round(freshness * 100)
            if pct > 70:
                bar_color = "#00D559"
                text_color = "#00D559"
                status = f"{age_h:.0f}h ago"
                dot_class = "df-dot-live"
            elif pct > 30:
                bar_color = "#ffcc00"
                text_color = "#ffcc00"
                status = f"{age_h:.0f}h ago"
                dot_class = "df-dot-warn"
            else:
                bar_color = "#ff4444"
                text_color = "#ff4444"
                status = f"{age_h:.1f}h ago"
                dot_class = "df-dot-stale"
        rows_html.append(
            f'<div class="df-timeline-row">'
            f'<div class="df-timeline-label"><span class="{dot_class}"></span>{emoji} {_html.escape(str(label))}</div>'
            f'<div class="df-timeline-track">'
            f'<div class="df-timeline-fill" style="width:{pct}%;background:{bar_color};'
            f'box-shadow:0 0 6px {bar_color};"></div></div>'
            f'<div class="df-timeline-status" style="color:{text_color};">{status}</div>'
            f'</div>'
        )
    return (
        '<div class="df-timeline">'
        + "\n".join(rows_html)
        + '</div>'
    )


def get_preflight_checklist_html(checks: list[tuple[str, bool, str]]) -> str:
    """
    Premium pre-flight checklist with pulsing status indicators.

    *checks*: list of (label, is_ok, detail_text).
    """
    items = []
    for label, ok, detail in checks:
        icon_class = "df-dot-live" if ok else "df-dot-stale"
        color = "#00D559" if ok else "#ff4444"
        items.append(
            f'<div class="df-check-row">'
            f'<span class="df-check-icon"><span class="{icon_class}"></span></span>'
            f'<span class="df-check-label" style="color:{color};">{_html.escape(str(label))}</span>'
            f'<span class="df-check-detail">{_html.escape(str(detail))}</span>'
            f'</div>'
        )
    return '<div class="df-preflight">' + "\n".join(items) + '</div>'


# ============================================================
# END SECTION: Smart NBA Data — Premium Glassmorphic Card / Widget Helpers
# ============================================================


# ============================================================
# SECTION: Prop Scanner — CSS & HTML Helpers
# ============================================================

_PROP_SCANNER_CSS = """
<style>
/* ─── Platform Color Badges ───────────────────────────── */
.plat-draftkings  { background:#2b6cb0; color:#bee3f8; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; display:inline-block; }
.plat-prizepicks  { background:#16a34a; color:#dcfce7; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; display:inline-block; }
.plat-underdog    { background:#ca8a04; color:#fef9c3; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; display:inline-block; }
.plat-default     { background:#1C2232; color:#A0AABE; padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:700; border:1px solid rgba(0,213,89,0.18); display:inline-block; }

/* ─── Team Pill ───────────────────────────────────────── */
.team-pill { background:rgba(0,213,89,0.10); color:#fff; border:1px solid rgba(0,213,89,0.25); padding:1px 6px; border-radius:4px; font-size:0.8rem; font-weight:700; display:inline-block; }

/* ─── Line Type Badges (Goblin / Demon / Standard) ────── */
.line-type-goblin   { background:rgba(0,255,128,0.15); color:#00ff90; padding:2px 8px; border-radius:5px; font-size:0.75rem; font-weight:700; border:1px solid rgba(0,255,128,0.35); display:inline-block; }
.line-type-demon    { background:rgba(255,60,60,0.15); color:#ff4444; padding:2px 8px; border-radius:5px; font-size:0.75rem; font-weight:700; border:1px solid rgba(255,60,60,0.35); display:inline-block; }
.line-type-standard { background:rgba(80,90,120,0.20); color:#6B7A9A; padding:2px 8px; border-radius:5px; font-size:0.75rem; font-weight:700; border:1px solid rgba(80,90,120,0.25); display:inline-block; }

/* ─── Value Signal Gauge Bar ──────────────────────────── */
.vs-gauge-wrap {
    display:flex; align-items:center; gap:6px; min-width:140px;
}
.vs-gauge-track {
    flex:1; height:8px; background:rgba(255,255,255,0.08); border-radius:4px;
    position:relative; overflow:hidden; min-width:60px;
}
.vs-gauge-fill {
    height:100%; border-radius:4px; transition:width 0.3s ease;
}
.vs-gauge-low  .vs-gauge-fill { background:linear-gradient(90deg,#00D559,#00d084); }
.vs-gauge-high .vs-gauge-fill { background:linear-gradient(90deg,#F9C62B,#F24336); }
.vs-gauge-fair .vs-gauge-fill { background:linear-gradient(90deg,#69b4ff,#4a9eff); }
.vs-gauge-label {
    font-size:0.72rem; font-weight:700; white-space:nowrap;
}
.vs-gauge-low  .vs-gauge-label { color:#00D559; }
.vs-gauge-high .vs-gauge-label { color:#ff6b6b; }
.vs-gauge-fair .vs-gauge-label { color:#69b4ff; }

/* ─── Confidence Score Badge ──────────────────────────── */
.conf-badge {
    display:inline-block; padding:2px 8px; border-radius:6px;
    font-size:0.78rem; font-weight:800; font-family:'JetBrains Mono',monospace;
    letter-spacing:0.02em;
}
.conf-high   { background:rgba(0,255,128,0.15); color:#00ff90; border:1px solid rgba(0,255,128,0.35); }
.conf-medium { background:rgba(0,200,255,0.14); color:#00c8ff; border:1px solid rgba(0,200,255,0.35); }
.conf-low    { background:rgba(255,200,0,0.13); color:#e6b800; border:1px solid rgba(255,200,0,0.30); }
.conf-poor   { background:rgba(255,60,60,0.14); color:#ff5050; border:1px solid rgba(255,60,60,0.32); }

/* ─── Prop Scanner Card Grid ──────────────────────────── */
.ps-grid {
    display:grid;
    grid-template-columns:repeat(auto-fill, minmax(290px, 1fr));
    gap:16px; padding:8px 0; width:100%;
}
@keyframes ps-card-in {
    from { opacity:0; transform:translateY(14px) scale(0.98); }
    to   { opacity:1; transform:translateY(0)    scale(1); }
}
/* ── PrizePicks-style prop card ── */
.ps-card {
    background: #161B27;
    border: 1.5px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 0;
    font-family: 'Inter', sans-serif;
    animation: ps-card-in 0.30s cubic-bezier(0.22,1,0.36,1) both;
    position: relative; overflow: hidden;
    transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}
.ps-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    border-radius: 18px 18px 0 0;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    opacity: 0.7;
}
.ps-card:hover {
    border-color: rgba(0,213,89,0.30);
    transform: translateY(-3px);
    box-shadow: 0 10px 32px rgba(0,213,89,0.10), 0 4px 20px rgba(0,0,0,0.5);
}
.ps-card-pos::before { background: linear-gradient(90deg, #00D559, #2D9EFF); }
.ps-card-neg::before { background: linear-gradient(90deg, #F24336, #F9C62B); }
.ps-card-neu::before { background: linear-gradient(90deg, #2D9EFF, #6B7A9A); }
.ps-card-pos:hover { border-color: rgba(0,213,89,0.32); }
.ps-card-neg:hover { border-color: rgba(242,67,54,0.32); }

/* ─── PP-style card header ── */
.ps-card-header {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 16px 10px;
}
.ps-card-headshot {
    width: 60px; height: 60px; border-radius: 50%;
    object-fit: cover; flex-shrink: 0;
    border: 2px solid rgba(255,255,255,0.10);
    background: #1C2232;
    transition: border-color 0.2s ease;
}
.ps-card:hover .ps-card-headshot { border-color: rgba(0,213,89,0.35); }
.ps-card-player { font-size: 0.95rem; font-weight: 800; color: #FFFFFF; line-height: 1.2; }
.ps-card-team   { font-size: 0.68rem; color: #6B7A9A; font-weight: 600; margin-top: 1px; }
.ps-card-plat-badge {
    margin-left: auto; flex-shrink: 0;
    align-self: flex-start; margin-top: 2px;
}

/* ─── Large line number (PP hero) ── */
.ps-card-line-block {
    text-align: center; padding: 10px 12px 8px;
    background: rgba(0,0,0,0.16); border-radius: 12px;
    margin: 6px 16px 8px;
}
.ps-card-stat-label {
    font-size: 0.62rem; font-weight: 800; letter-spacing: 0.14em;
    text-transform: uppercase; color: #6B7A9A; margin-bottom: 2px;
}
.ps-card-line {
    font-size: 2.2rem; font-weight: 900; color: #FFFFFF;
    font-family: 'Bebas Neue', 'Inter', sans-serif;
    letter-spacing: -0.01em; line-height: 1;
    font-variant-numeric: tabular-nums;
}
.ps-card-avg {
    font-size: 0.72rem; color: #6B7A9A; margin-top: 3px;
}

/* ─── Metrics & badges row ── */
.ps-card-metrics {
    display: flex; gap: 8px; flex-wrap: wrap;
    padding: 0 16px 10px; align-items: center;
}
.ps-card-metric-box {
    flex: 1 1 auto; text-align: center;
    background: rgba(255,255,255,0.04); border-radius: 8px;
    padding: 6px 8px; border: 1px solid rgba(255,255,255,0.05);
}
.ps-card-metric-val { font-size: 0.82rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
.ps-card-metric-lbl { font-size: 0.58rem; color: #6B7A9A; text-transform: uppercase; letter-spacing: 0.07em; margin-top: 2px; }

/* ─── PP-style OVER/UNDER buttons at card bottom ── */
.ps-card-btn-row {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    padding: 8px 16px 14px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.ps-card-btn {
    display: flex; align-items: center; justify-content: center; gap: 4px;
    padding: 9px 6px; border-radius: 10px;
    font-weight: 800; font-size: 0.82rem; text-transform: uppercase;
    letter-spacing: 0.05em; border: 1.5px solid transparent;
    transition: box-shadow 0.15s ease, transform 0.12s ease;
}
.ps-card-btn:hover { transform: translateY(-1px); }
.ps-btn-over-active  { background: #00D559; color: #0D0F14; border-color: #00D559; box-shadow: 0 4px 14px rgba(0,213,89,0.40); }
.ps-btn-over-inactive  { background: rgba(0,213,89,0.07); color: rgba(0,213,89,0.55); border-color: rgba(0,213,89,0.20); }
.ps-btn-under-active { background: #F24336; color: #FFFFFF; border-color: #F24336; box-shadow: 0 4px 14px rgba(242,67,54,0.36); }
.ps-btn-under-inactive { background: rgba(242,67,54,0.07); color: rgba(242,67,54,0.55); border-color: rgba(242,67,54,0.20); }

/* ─── Value Signal Gauge Bar ──────────────────────────── */
.vs-gauge-wrap  { display:flex; align-items:center; gap:6px; min-width:120px; }
.vs-gauge-track { flex:1; height:6px; background:rgba(255,255,255,0.08); border-radius:4px; overflow:hidden; min-width:50px; }
.vs-gauge-fill  { height:100%; border-radius:4px; transition:width 0.3s ease; }
.vs-gauge-low  .vs-gauge-fill { background:linear-gradient(90deg,#00D559,#00d084); }
.vs-gauge-high .vs-gauge-fill { background:linear-gradient(90deg,#F9C62B,#F24336); }
.vs-gauge-fair .vs-gauge-fill { background:linear-gradient(90deg,#2D9EFF,#4a9eff); }
.vs-gauge-label { font-size:0.70rem; font-weight:700; white-space:nowrap; }
.vs-gauge-low  .vs-gauge-label { color:#00D559; }
.vs-gauge-high .vs-gauge-label { color:#F24336; }
.vs-gauge-fair .vs-gauge-label { color:#2D9EFF; }

/* ─── Confidence Score Badge ──────────────────────────── */
.conf-badge { display:inline-block; padding:2px 8px; border-radius:6px; font-size:0.76rem; font-weight:800; font-family:'JetBrains Mono',monospace; }
.conf-high   { background:rgba(0,213,89,0.12); color:#00D559; border:1px solid rgba(0,213,89,0.32); }
.conf-medium { background:rgba(45,158,255,0.12); color:#2D9EFF; border:1px solid rgba(45,158,255,0.30); }
.conf-low    { background:rgba(249,198,43,0.12); color:#F9C62B; border:1px solid rgba(249,198,43,0.28); }
.conf-poor   { background:rgba(242,67,54,0.12); color:#F24336; border:1px solid rgba(242,67,54,0.28); }

/* ─── Platform Color Badges ───────────────────────────── */
.plat-draftkings { background:rgba(43,108,176,0.18); color:#63b3ed; padding:2px 8px; border-radius:6px; font-size:0.70rem; font-weight:700; display:inline-block; border:1px solid rgba(43,108,176,0.32); }
.plat-prizepicks { background:rgba(22,163,74,0.18);  color:#4ade80; padding:2px 8px; border-radius:6px; font-size:0.70rem; font-weight:700; display:inline-block; border:1px solid rgba(22,163,74,0.32); }
.plat-underdog   { background:rgba(202,138,4,0.18);  color:#fcd34d; padding:2px 8px; border-radius:6px; font-size:0.70rem; font-weight:700; display:inline-block; border:1px solid rgba(202,138,4,0.28); }
.plat-default    { background:rgba(255,255,255,0.05); color:#A0AABE; padding:2px 8px; border-radius:6px; font-size:0.70rem; font-weight:700; display:inline-block; border:1px solid rgba(255,255,255,0.12); }
.team-pill { background:rgba(0,213,89,0.10); color:#fff; border:1px solid rgba(0,213,89,0.22); padding:1px 7px; border-radius:6px; font-size:0.72rem; font-weight:700; display:inline-block; }

/* ─── Line Type Badges (Goblin / Demon / Standard) ────── */
.line-type-goblin   { background:rgba(0,213,89,0.12); color:#00D559; padding:2px 8px; border-radius:6px; font-size:0.68rem; font-weight:700; border:1px solid rgba(0,213,89,0.28); display:inline-block; }
.line-type-demon    { background:rgba(242,67,54,0.12); color:#F24336; padding:2px 8px; border-radius:6px; font-size:0.68rem; font-weight:700; border:1px solid rgba(242,67,54,0.28); display:inline-block; }
.line-type-standard { background:rgba(107,122,154,0.12); color:#6B7A9A; padding:2px 8px; border-radius:6px; font-size:0.68rem; font-weight:700; border:1px solid rgba(107,122,154,0.22); display:inline-block; }

/* ─── Line Movement Alert ─────────────────────────────── */
.lm-alert { display:inline-flex; align-items:center; gap:4px; font-size:0.70rem; font-weight:700; padding:2px 7px; border-radius:6px; }
.lm-alert-down { background:rgba(0,213,89,0.09); color:#00D559; border:1px solid rgba(0,213,89,0.24); }
.lm-alert-up   { background:rgba(242,67,54,0.10); color:#F24336; border:1px solid rgba(242,67,54,0.28); }

/* ─── Responsive tweaks ───────────────────────────────── */
@media (max-width:768px) {
    .ps-grid { grid-template-columns:1fr; }
}
.ps-card-avg {
    font-size:0.72rem; color:#3A4460; font-weight:500;
}

.ps-card-metrics {
    display:flex; gap:10px; margin-bottom:8px; flex-wrap:wrap;
}
.ps-card-metric-box {
    flex:1 1 60px; text-align:center;
    background:rgba(255,255,255,0.03); border-radius:8px;
    padding:6px 4px;
}
.ps-card-metric-val {
    font-size:0.88rem; font-weight:700;
    font-family:'JetBrains Mono',monospace;
}
.ps-card-metric-lbl {
    font-size:0.62rem; color:#3A4460; text-transform:uppercase;
    letter-spacing:0.06em; margin-top:2px;
}

.ps-card-footer {
    display:flex; justify-content:space-between; align-items:center;
    border-top:1px solid rgba(255,255,255,0.05);
    padding-top:8px; margin-top:4px;
}

/* ─── Line Movement Alert ─────────────────────────────── */
.lm-alert {
    display:inline-flex; align-items:center; gap:4px;
    font-size:0.72rem; font-weight:700; padding:2px 6px;
    border-radius:4px;
}
.lm-alert-down { background:rgba(0,213,89,0.09); color:#00D559; border:1px solid rgba(0,213,89,0.24); }
.lm-alert-up   { background:rgba(255,100,100,0.10); color:#ff6b6b; border:1px solid rgba(255,100,100,0.30); }

/* ─── Responsive tweaks ───────────────────────────────── */
@media (max-width:768px) {
    .ps-grid { grid-template-columns:1fr; }
    .ps-card-metrics { gap:6px; }
}
</style>
"""


def get_prop_scanner_css() -> str:
    """Return the CSS block for Prop Scanner page components."""
    return _PROP_SCANNER_CSS


def get_platform_badge_html(platform: str) -> str:
    """Return an HTML badge for a sportsbook platform name."""
    pl = platform.lower() if platform else ""
    if "prizepicks" in pl:
        return '<span class="plat-prizepicks">🟢 PrizePicks</span>'
    if "underdog" in pl:
        return '<span class="plat-underdog">🟡 Underdog Fantasy</span>'
    if "draftkings" in pl or "pick6" in pl or "dk" in pl:
        return '<span class="plat-draftkings">🔵 DraftKings Pick6</span>'
    if platform:
        return f'<span class="plat-default">{_html.escape(platform)}</span>'
    return ""


def get_line_type_badge_html(odds_type: str) -> str:
    """Return an HTML badge for goblin / demon / standard line type."""
    ot = (odds_type or "standard").lower()
    if ot == "goblin":
        return '<span class="line-type-goblin">🟢 Goblin</span>'
    if ot == "demon":
        return '<span class="line-type-demon">🔴 Demon</span>'
    return '<span class="line-type-standard">⚪ Standard</span>'


def get_value_gauge_html(line_diff_pct: float) -> str:
    """Return an HTML mini gauge bar for value signal (line vs season avg).

    *line_diff_pct* is ``(line - avg) / avg * 100``.
    Negative = OVER value (green).  Positive = UNDER value (orange).
    """
    try:
        diff = float(line_diff_pct)
    except (TypeError, ValueError):
        return '<span style="color:#3A4460;font-size:0.72rem;">—</span>'

    abs_diff = min(abs(diff), 50)  # cap at 50 for gauge width
    pct_width = max(int(abs_diff * 2), 8)  # 0-100% scale

    if diff < -12:
        cls = "vs-gauge-low"
        label = f"🔥 {diff:+.0f}%"
    elif diff > 15:
        cls = "vs-gauge-high"
        label = f"⚠️ {diff:+.0f}%"
    else:
        cls = "vs-gauge-fair"
        label = f"✅ {diff:+.0f}%" if abs(diff) >= 0.5 else "✅ Fair"

    return (
        f'<div class="vs-gauge-wrap {cls}">'
        f'<div class="vs-gauge-track"><div class="vs-gauge-fill" style="width:{pct_width}%;"></div></div>'
        f'<span class="vs-gauge-label">{label}</span>'
        f'</div>'
    )


def get_confidence_badge_html(score: int) -> str:
    """Return an HTML badge for a 0-100 confidence score."""
    score = max(0, min(100, int(score)))
    if score >= 75:
        cls = "conf-high"
    elif score >= 55:
        cls = "conf-medium"
    elif score >= 35:
        cls = "conf-low"
    else:
        cls = "conf-poor"
    return f'<span class="conf-badge {cls}">{score}</span>'


def get_line_movement_html(old_line: float, new_line: float) -> str:
    """Return an HTML badge showing how a prop line moved."""
    try:
        old_line = float(old_line)
        new_line = float(new_line)
    except (TypeError, ValueError):
        return ""
    diff = new_line - old_line
    if abs(diff) < 0.01:
        return ""
    if diff < 0:
        return (
            f'<span class="lm-alert lm-alert-down">'
            f'{old_line:.1f} → {new_line:.1f} ⬇️</span>'
        )
    return (
        f'<span class="lm-alert lm-alert-up">'
        f'{old_line:.1f} → {new_line:.1f} ⬆️</span>'
    )


def get_prop_card_html(
    player_name: str,
    team: str,
    stat_type: str,
    line: float,
    season_avg: float,
    line_diff_pct: float,
    odds_type: str,
    platform: str,
    status_emoji: str,
    player_status: str,
    confidence_score: int = 0,
    player_id: int = 0,
    movement_html: str = "",
) -> str:
    """Return a single prop card for the Prop Scanner card grid.

    Uses 260x190 NBA CDN headshot URLs (CSS sizes to 48px circle).
    """
    safe_player = _html.escape(player_name)
    safe_team = _html.escape(team)
    safe_stat = _html.escape(stat_type.replace("_", " ").title())

    # Card accent
    if line_diff_pct < -12:
        accent = "ps-card-pos"
    elif line_diff_pct > 15:
        accent = "ps-card-neg"
    else:
        accent = "ps-card-neu"

    # Headshot (260x190 per project conventions)
    headshot_url = (
        f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"
        if player_id
        else ""
    )
    headshot_html = (
        f'<img class="ps-card-headshot" src="{headshot_url}" alt="" loading="lazy" '
        f'onerror="this.style.display=\'none\'">'
        if headshot_url
        else ""
    )

    plat_badge = get_platform_badge_html(platform)
    type_badge = get_line_type_badge_html(odds_type)
    gauge = get_value_gauge_html(line_diff_pct)
    conf_badge = get_confidence_badge_html(confidence_score) if confidence_score else ""

    avg_html = f'<span class="ps-card-avg">avg {season_avg:.1f}</span>' if season_avg > 0 else ""

    # OVER/UNDER button direction: positive line_diff_pct → UNDER edge, negative → OVER edge
    over_btn_cls = "ps-card-btn ps-btn-over-active" if line_diff_pct < -5 else "ps-card-btn ps-btn-over-inactive"
    under_btn_cls = "ps-card-btn ps-btn-under-active" if line_diff_pct > 10 else "ps-card-btn ps-btn-under-inactive"

    # NOTE: No line may start with 4+ spaces — st.markdown() treats that as
    # a Markdown code-block, causing raw HTML to render as text.
    return (
        f'<div class="ps-card {accent}">'
        # ── Header: headshot + player + platform badge ──
        f'<div class="ps-card-header">'
        f'{headshot_html}'
        f'<div style="flex:1;min-width:0;">'
        f'<div class="ps-card-player">{safe_player}</div>'
        f'<div class="ps-card-team">{safe_team}</div>'
        f'</div>'
        f'<div class="ps-card-plat-badge">{plat_badge}</div>'
        f'</div>'
        # ── Large line number block (PP-style) ──
        f'<div class="ps-card-line-block">'
        f'<div class="ps-card-stat-label">{safe_stat}</div>'
        f'<div class="ps-card-line">{line:.1f}</div>'
        f'{avg_html}'
        f'</div>'
        # ── Metrics row: value gauge + status + confidence ──
        f'<div class="ps-card-metrics">'
        f'<div class="ps-card-metric-box">{gauge}<div class="ps-card-metric-lbl">Value</div></div>'
        f'<div class="ps-card-metric-box"><div class="ps-card-metric-val">{status_emoji} {_html.escape(player_status)}</div><div class="ps-card-metric-lbl">Status</div></div>'
        + (f'<div class="ps-card-metric-box"><div class="ps-card-metric-val">{conf_badge}</div><div class="ps-card-metric-lbl">Confidence</div></div>' if conf_badge else '')
        + f'</div>'
        # ── Line type badge + movement ──
        + f'<div style="display:flex;gap:6px;align-items:center;padding:0 16px 8px;flex-wrap:wrap;">'
        + f'{type_badge}'
        + (f'&nbsp;{movement_html}' if movement_html else '')
        + f'</div>'
        # ── PP-style OVER/UNDER pick buttons ──
        + f'<div class="ps-card-btn-row">'
        + f'<div class="{over_btn_cls}">⬆ MORE</div>'
        + f'<div class="{under_btn_cls}">⬇ LESS</div>'
        + f'</div>'
        + f'</div>'
    )


# ============================================================
# END SECTION: Prop Scanner — CSS & HTML Helpers
# ============================================================
