"""SmartPickPro — Brand Voice & Identity.

Single source of truth for all copy constants used across the social engine:
  - LLM system prompt / tone guidelines
  - CTA headline rotations (brand posts)
  - Tagline variants by tone
  - Compliance footer
  - Hashtag pools

Import this module wherever copy is generated or templates are rendered.
"""
from __future__ import annotations
import random

# ─────────────────────────────────────────────────────────────
# BRAND IDENTITY
# ─────────────────────────────────────────────────────────────

BRAND_NAME      = "SmartPickPro"
BRAND_URL       = "smartpickpro.app"
ENGINE_NAME     = "Quantum Matrix Engine™"
ENGINE_VERSION  = "5.6"
SCORE_NAME      = "SAFE Score™"

# ─────────────────────────────────────────────────────────────
# CORE BRAND VOICE GUIDELINES (injected into every LLM call)
# ─────────────────────────────────────────────────────────────

VOICE_GUIDELINES = """\
BRAND: SmartPickPro — proprietary quantitative NBA prop analytics platform.
ENGINE: Quantum Matrix Engine™ 5.6 (QME). All IP is owned exclusively by SmartPickPro.
SCORE: SAFE Score™ — 0-100 composite confidence rating, 8 weighted inputs, 4 penalty deductions.

VOICE PILLARS:
1. SHARP — Short sentences. No filler words. Every word earns its place.
2. INSTITUTIONAL — Data and math do the talking, not hype or personality.
3. TRANSPARENT — We post every win AND every loss. Receipts always on file. This is rare and we own it.
4. CONFIDENT, NOT ARROGANT — We state the edge, never guarantee outcomes.
5. OWNED IP — Say "Quantum simulations", "QME", "SAFE Score™". Never say "Monte Carlo".

TONE RULES:
- Never use: "lock", "guaranteed", "can't miss", "#1 pick", "trust me", "easy money"
- Never promise: wins, profit, positive ROI
- Always include: a transparency signal ("all picks shown", "receipts on file", "verify it yourself")
- Edge language: "the math flags", "QME flagged", "the engine says", "SAFE Score above X"
- Receipts language: "every win AND loss posted", "zero hidden losses", "receipts on file", "verify yourself"

POSITIONING:
- Against tipsters: "Not a tipster. A statistical engine."
- Against black boxes: "Zero black boxes. Full reasoning on every pick."
- Against cherry-pickers: "We post every win AND every loss. Always."
- Against gut-feel: "The edge isn't luck. It's math."

COMPLIANCE: Always include a responsible gambling signal. Never imply guaranteed returns.
"""

# ─────────────────────────────────────────────────────────────
# TAGLINES (rotate per post type)
# ─────────────────────────────────────────────────────────────

TAGLINES = {
    "primary":       "The edge isn't luck. It's math.",
    "transparency":  "Every win AND loss posted. Receipts always on file.",
    "engine":        "Quantum Matrix Engine™ — 1,000+ simulations per pick.",
    "positioning":   "Not a tipster. A statistical engine.",
    "authority":     "Zero black boxes. Full reasoning on every pick.",
    "cta":           "Free trial. Real edges. No black box.",
}

def random_tagline() -> str:
    return random.choice(list(TAGLINES.values()))

# ─────────────────────────────────────────────────────────────
# CTA HEADLINE ROTATIONS (3 per week — brand posts Mon/Wed/Fri)
# ─────────────────────────────────────────────────────────────
# Each entry: (headline_with_newlines, subheadline, button_text)
# headline supports \n for Bebas Neue line breaks in the template

CTA_ROTATIONS = [
    # Transparency / receipts angle
    (
        "EVERY WIN.\nEVERY LOSS.\nALWAYS.",
        "No cherry-picks. No hidden losses. Every result posted publicly — verify it yourself.",
        "→ SEE THE RECEIPTS",
    ),
    # Math / edge angle
    (
        "THE EDGE\nISN'T LUCK.\nIT'S MATH.",
        "1,000+ Quantum simulations per pick. Proprietary SAFE Score™. Zero black boxes.",
        "→ START FREE TRIAL",
    ),
    # Engine authority angle
    (
        "NOT A\nTIPSTER.\nAN ENGINE.",
        "Quantum Matrix Engine™ 5.6 — built to find statistical edges, not sell feelings.",
        "→ RUN YOUR FIRST ANALYSIS",
    ),
    # Positioning / competitive angle
    (
        "OTHERS\nGUESS.\nWE CALCULATE.",
        "8-factor SAFE Score™ on every NBA prop. Real data. Real edges. Full transparency.",
        "→ TRY IT FREE",
    ),
    # Transparency + authority combo
    (
        "ZERO\nBLACK\nBOXES.",
        "Full reasoning shown on every pick. Wins and losses posted publicly. Always verifiable.",
        "→ SEE HOW IT WORKS",
    ),
    # Receipts culture angle
    (
        "RECEIPTS\nALWAYS\nON FILE.",
        "We don't hide losses. Every pick result is posted — you can verify each one yourself.",
        "→ CHECK THE RECORD",
    ),
    # Free trial / conversion angle
    (
        "THE MATH\nIS FREE.\nFOR NOW.",
        "Full Quantum Matrix Engine™ access. No credit card. See the edges before you decide.",
        "→ START FOR FREE",
    ),
]

def pick_cta_rotation(index: int | None = None) -> tuple[str, str, str]:
    """Return a (headline, subheadline, button_text) tuple.
    Pass index for deterministic selection (e.g. day-of-week),
    or None for random.
    """
    if index is not None:
        return CTA_ROTATIONS[index % len(CTA_ROTATIONS)]
    return random.choice(CTA_ROTATIONS)

# ─────────────────────────────────────────────────────────────
# HASHTAG POOLS
# ─────────────────────────────────────────────────────────────

_ALWAYS = ["SmartPickPro", "NBA"]

HASHTAGS = {
    "slate": [
        *_ALWAYS,
        "NBAProps", "PrizePicks", "UnderdogFantasy", "DraftKings",
        "PropBets", "NBAEdge", "QuantumEdge", "DFS",
    ],
    "results": [
        *_ALWAYS,
        "NBARecap", "PropBets", "PrizePicks", "Receipts",
        "NBAResults", "DFS", "SportsBetting", "Transparency",
    ],
    "weekly": [
        *_ALWAYS,
        "WeeklyRecap", "NBAProps", "PropBets", "PrizePicks",
        "SportsBetting", "NBAEdge", "DFS", "Receipts",
    ],
    "brand": [
        *_ALWAYS,
        "NBAAnalytics", "PropBets", "QuantumEdge", "NBAProps",
        "SportsTech", "DFS", "DataDriven", "NBAEdge",
    ],
}

def get_hashtags(asset_type: str, n: int = 8) -> list[str]:
    pool = HASHTAGS.get(asset_type, HASHTAGS["brand"])
    # Always include the two brand anchors, fill rest from pool
    anchors = [t for t in pool if t in _ALWAYS]
    rest = [t for t in pool if t not in _ALWAYS]
    random.shuffle(rest)
    return anchors + rest[: max(0, n - len(anchors))]

# ─────────────────────────────────────────────────────────────
# COMPLIANCE FOOTER
# ─────────────────────────────────────────────────────────────

COMPLIANCE_FOOTER = (
    "For entertainment purposes only. Not financial or gambling advice. "
    "Must be 21+. Please play responsibly. Problem? Call 1-800-GAMBLER."
)
