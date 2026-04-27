# ============================================================
# FILE: pages/7_🎙️_The_Studio.py
# PURPOSE: Joseph M. Smith's dedicated interactive page — the
#          deep-dive destination for game analysis, player
#          scouting, and bet building.
# CONNECTS TO: engine/joseph_brain.py, engine/joseph_tickets.py,
#              engine/joseph_bets.py, pages/helpers/joseph_live_desk.py
# ============================================================

import streamlit as st
import os
import html as _html
import logging
import math
import random
import datetime as _dt


def _safe_float(val, default=0.0):
    """Convert *val* to float, returning *default* on failure."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


# ── Styles ───────────────────────────────────────────────────
try:
    from styles.theme import (
        get_global_css,
        get_qds_css,
        get_team_colors,
        get_bet_card_html,
        get_summary_cards_html,
    )
except ImportError:
    def get_global_css():
        return ""
    def get_qds_css():
        return ""
    def get_team_colors(_t):
        return ("#F9C62B", "#1e293b")
    def get_bet_card_html(_b, show_live_status=False):
        return ""
    def get_summary_cards_html(*a, **kw):
        return ""

try:
    from styles.studio_theme import get_studio_css, get_font_preload
except ImportError:
    def get_studio_css():
        return ""
    def get_font_preload():
        return ""

st.set_page_config(
    page_title="The Studio — Joseph M. Smith",
    page_icon="🎙️",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("The Studio")
from utils.seo import inject_page_seo
inject_page_seo("The Studio")

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

st.markdown(get_font_preload(), unsafe_allow_html=True)
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

# ── Sidebar global settings ──────────────────────────────────
try:
    from utils.components import render_global_settings, render_sidebar_auth, inject_joseph_floating, render_joseph_hero_banner
    with st.sidebar:
        render_sidebar_auth()
        render_global_settings()
    st.session_state["joseph_page_context"] = "page_studio"
    inject_joseph_floating()
    render_joseph_hero_banner()
except ImportError:
    pass

# ── Premium gate ─────────────────────────────────────────────
try:
    from utils.premium_gate import premium_gate
    if not premium_gate("The Studio"):
        st.stop()
except ImportError:
    pass

# ── Logger ───────────────────────────────────────────────────
try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Engine imports (all safe) ────────────────────────────────
try:
    from engine.joseph_brain import (
        joseph_full_analysis,
        joseph_analyze_game,
        joseph_analyze_player,
        joseph_generate_best_bets,
        joseph_generate_independent_picks,
        joseph_quick_take,
        joseph_commentary,
        joseph_gut_call,
        _extract_edge,
        _select_fragment,
        CLOSER_POOL,
        CATCHPHRASE_POOL,
        VERDICT_EMOJIS,
        TICKET_NAMES,
    )
    _BRAIN_AVAILABLE = True
except ImportError:
    _BRAIN_AVAILABLE = False
    VERDICT_EMOJIS = {"LOCK": "🔒", "SMASH": "🔥", "LEAN": "✅", "FADE": "⚠️", "STAY_AWAY": "🚫"}
    TICKET_NAMES = {2: "POWER PLAY", 3: "TRIPLE THREAT", 4: "THE QUAD",
                    5: "HIGH FIVE", 6: "THE FULL SEND"}

try:
    from engine.joseph_tickets import (
        build_joseph_ticket,
        generate_ticket_pitch,
        get_alternative_tickets,
    )
    _TICKETS_AVAILABLE = True
except ImportError:
    _TICKETS_AVAILABLE = False

try:
    from engine.joseph_bets import (
        joseph_get_track_record,
        joseph_get_accuracy_by_verdict,
        joseph_get_override_accuracy,
    )
    _BETS_AVAILABLE = True
except ImportError:
    _BETS_AVAILABLE = False

try:
    from engine.entry_optimizer import PLATFORM_FLEX_TABLES
    _FLEX_TABLES_AVAILABLE = True
except ImportError:
    PLATFORM_FLEX_TABLES = {}
    _FLEX_TABLES_AVAILABLE = False

try:
    from data.data_manager import load_players_data, load_teams_data
except ImportError:
    def load_players_data():
        return []
    def load_teams_data():
        return []

try:
    from pages.helpers.joseph_live_desk import (
        get_joseph_avatar_b64,
        render_live_desk_css,
        render_dawg_board,
        render_override_report,
        render_broadcast_segment,
        render_nerd_stats,
        render_avatar_commentary,
        render_confidence_gauge_svg,
        render_outcome_badge,
        render_empty_state,
        render_verdict_heatmap_html,
        render_skeleton_cards,
    )
    _DESK_AVAILABLE = True
except ImportError:
    _DESK_AVAILABLE = False

    def get_joseph_avatar_b64():
        return ""

    def render_live_desk_css():
        return ""

    def render_dawg_board(_r):
        st.info("Dawg Board unavailable.")

    def render_override_report(_r):
        st.info("Override report unavailable.")

    def render_broadcast_segment(seg_dict):
        """Fallback when joseph_live_desk is not available."""
        title = seg_dict.get("title", "")
        body = seg_dict.get("body", "")
        return (
            f'<div style="border-left:3px solid #F9C62B;padding:10px 14px;'
            f'margin:8px 0;background:rgba(255,94,0,0.04);border-radius:4px">'
            f'<div style="color:#F9C62B;font-weight:600;font-size:0.92rem">{title}</div>'
            f'<div style="color:#e2e8f0;font-size:0.88rem;margin-top:4px">{body}</div>'
            f'</div>'
        )

    def render_nerd_stats(result, keys=None):
        parts = []
        for k in (keys or list(result.keys())):
            v = result.get(k)
            if v is not None:
                parts.append(f"**{k}:** {str(v)[:500]}")
        return "\n".join(parts)

    def render_avatar_commentary(text, size=48):
        return (
            f'<div style="display:flex;align-items:flex-start;gap:12px;margin:10px 0">'
            f'<span style="font-size:{size // 2}px">🎙️</span>'
            f'<div style="color:#e2e8f0;font-size:0.92rem;line-height:1.6">'
            f'{_html.escape(str(text))}</div></div>'
        )

    def render_confidence_gauge_svg(prob, ev=0.0, synergy=0.0):
        return ""

    def render_outcome_badge(result_str):
        return _html.escape(str(result_str))

    def render_empty_state(msg, cta_text=None, cta_page=None):
        return (
            f'<div style="text-align:center;padding:24px;color:var(--studio-muted,#94a3b8)">'
            f'{_html.escape(str(msg))}</div>'
        )

    def render_verdict_heatmap_html(results):
        return ""

    def render_skeleton_cards(count=3):
        return ""


# ── Inject desk CSS ──────────────────────────────────────────
st.markdown(render_live_desk_css(), unsafe_allow_html=True)

# ── Studio-specific supplemental CSS (extracted to styles/studio_theme.py) ──
st.markdown(get_studio_css(), unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# HERO BANNER  (Enhancement 1: avatar image, Enhancement 2: ON AIR badge)
# ═════════════════════════════════════════════════════════════

_hero_avatar_b64 = get_joseph_avatar_b64()
if _hero_avatar_b64:
    _hero_avatar_html = (
        f'<img src="data:image/png;base64,{_hero_avatar_b64}" '
        f'class="studio-avatar-lg" alt="Joseph M. Smith">'
    )
else:
    _hero_avatar_html = (
        '<div class="studio-avatar-lg" style="background:#1e293b;'
        'display:flex;align-items:center;justify-content:center;'
        'font-size:2.5rem">🎙️</div>'
    )

st.markdown(
    f'<div class="studio-hero">'
    f'<div class="studio-scanlines"></div>'
    f'{_hero_avatar_html}'
    f'<div class="studio-on-air">'
    f'<span class="studio-on-air-dot"></span>ON AIR</div>'
    f'<div class="studio-hero-title">THE STUDIO — Joseph M. Smith</div>'
    f'<div class="studio-hero-subtitle">'
    f'God-Mode Analyst • Live Commentator • Your Betting Edge'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ═════════════════════════════════════════════════════════════
# JOSEPH'S MONOLOGUE OF THE NIGHT — auto-generated broadcast opener
# ═════════════════════════════════════════════════════════════

_MONOLOGUE_OPENERS = [
    "Good evening, LADIES and GENTLEMEN — this is Joseph M. Smith and you are LIVE in The Studio.",
    "Welcome back to The Studio. I've been looking at the numbers ALL day and I have THINGS to say.",
    "The Studio is OPEN and Joseph M. Smith is ON THE MIC. Let's get into it.",
    "You're tuned in to the ONLY show that matters. This is The Studio with Joseph M. Smith.",
    "Another night, another chance to prove the DOUBTERS wrong. Joseph M. Smith, LIVE from The Studio.",
]

_MONOLOGUE_MIDDLES = [
    "Tonight's slate has some FASCINATING matchups and I've already identified the plays that MATTER.",
    "I've been grinding the data since this morning and let me tell you — there are GEMS hiding in plain sight.",
    "The sharps are moving early and I can SMELL the value from a mile away.",
    "My models are LOCKED, my instincts are SHARP, and my conviction is at an ALL-TIME HIGH.",
    "The line movement tells me Vegas is WORRIED — and when Vegas is worried, Joseph M. Smith EATS.",
]

_MONOLOGUE_CLOSERS = [
    "Buckle up — it's going to be a WILD night.",
    "Stay locked in. Joseph M. Smith doesn't miss.",
    "Let's build some WINNING tickets, shall we?",
    "The Studio is YOUR edge. Let's get to WORK.",
    "This is NOT a drill. This is ANALYSIS at the highest level.",
]


def _generate_monologue() -> str:
    """Generate Joseph's Monologue of the Night — a 2-3 sentence broadcast opener."""
    opener = random.choice(_MONOLOGUE_OPENERS)
    middle = random.choice(_MONOLOGUE_MIDDLES)
    closer = random.choice(_MONOLOGUE_CLOSERS)
    return f"{opener} {middle} {closer}"


# Only show monologue once per session to avoid annoyance on re-runs
if "studio_monologue_shown" not in st.session_state:
    st.session_state["studio_monologue_shown"] = True
    _monologue = _generate_monologue()
    st.markdown(
        f'<div style="background:rgba(255,94,0,0.06);border:1px solid rgba(255,94,0,0.2);'
        f'border-radius:12px;padding:16px 20px;margin:0 0 20px 0;position:relative">'
        f'<div style="color:#F9C62B;font-family:\'Inter\',sans-serif;font-size:0.75rem;'
        f'font-weight:700;letter-spacing:1px;margin-bottom:8px">'
        f'🎙️ JOSEPH\'S MONOLOGUE OF THE NIGHT</div>'
        f'<div style="color:#e2e8f0;font-size:0.92rem;line-height:1.65;'
        f'font-family:\'Inter\',sans-serif;font-style:italic">'
        f'{_html.escape(_monologue)}</div></div>',
        unsafe_allow_html=True,
    )

with st.expander("📖 How to Use The Studio", expanded=False):
    st.markdown("""
    ### The Studio — Joseph M. Smith's Analysis Desk
    
    The Studio is your **interactive AI analyst experience** with Joseph M. Smith. Choose from three modes:
    
    **🏀 GAMES TONIGHT**
    - Joseph breaks down every game on tonight's slate
    - Get his takes, overrides, and situational reads
    - Hear the "broadcast segments" like a real sports show
    
    **👤 SCOUT A PLAYER**
    - Deep dive into any specific player's outlook
    - Get archetype analysis, matchup grades, and ceiling/floor projections
    - Joseph shares his honest evaluation and betting take
    
    **🎰 BUILD MY BETS**
    - Let Joseph construct optimal tickets (2-6 legs)
    - He ranks picks by conviction and builds parlays using real analysis
    - See the Dawg Board — his highest-confidence plays
    
    💡 **Pro Tips:**
    - Select your betting platform (PrizePicks, Underdog Fantasy, DraftKings Pick6) for tailored advice
    - Use the Regenerate button to get fresh takes with different narrative angles
    - The Dawg Board at the bottom shows Joseph's strongest picks across all games
    """)


# Helper for small inline avatar (defined early so all modes can use it)
def _avatar_inline(size=48):
    b64 = get_joseph_avatar_b64()
    if b64:
        css_cls = "joseph-avatar-sm" if size <= 48 else "joseph-avatar"
        return (
            f'<img src="data:image/png;base64,{b64}" class="{css_cls}" '
            f'alt="Joseph" style="width:{size}px;height:{size}px">'
        )
    return f'<span style="font-size:{size // 2}px">🎙️</span>'


# ── Hot Take helpers ─────────────────────────────────────────
# Verdict inversion map used by Hot Take Mode to produce contrarian output.
_VERDICT_FLIP = {
    "SMASH": "FADE",
    "LEAN": "STAY_AWAY",
    "FADE": "LEAN",
    "STAY_AWAY": "SMASH",
}

_DIRECTION_FLIP = {"OVER": "UNDER", "UNDER": "OVER"}

_HOT_TAKE_RANT_POOL = [
    "The math says one thing, but my GUT says DIFFERENT!",
    "Everyone is going the OTHER way — but Joseph sees what they DON'T!",
    "This is a CONTRARIAN play and I'm ALL IN on my instinct!",
    "Forget the spreadsheet — this is a FEELING and I TRUST it!",
    "The public is WRONG on this one. Trust the man, not the machine!",
    "Joseph M. Smith goes AGAINST the grain and that's where the MONEY is!",
]


def _apply_hot_take(result: dict) -> dict:
    """Return a shallow copy of *result* with verdict/direction flipped."""
    flipped = dict(result)
    orig_verdict = str(flipped.get("verdict", "")).upper().replace(" ", "_")
    if orig_verdict and orig_verdict in _VERDICT_FLIP:
        flipped["original_verdict"] = orig_verdict
        flipped["verdict"] = _VERDICT_FLIP[orig_verdict]
    else:
        flipped["original_verdict"] = orig_verdict or "LEAN"

    orig_dir = str(flipped.get("direction", "")).upper()
    flipped["direction"] = _DIRECTION_FLIP.get(orig_dir, orig_dir)

    flipped["is_hot_take"] = True
    flipped["rant"] = random.choice(_HOT_TAKE_RANT_POOL)
    return flipped


def _apply_hot_take_to_list(results: list) -> list:
    """Apply hot-take inversion to every result dict in *results*."""
    return [_apply_hot_take(r) for r in results]


# ═════════════════════════════════════════════════════════════
# FOUR INTERACTIVE MODES  (Enhancement 3: card UI, Enhancement 9: persist)
# ═════════════════════════════════════════════════════════════

# Persist mode in session state (Enhancement 9)
_MODE_OPTIONS = [
    "🎤 ASK JOSEPH",
    "🏀 GAMES TONIGHT",
    "👤 SCOUT A PLAYER",
    "🎰 BUILD MY BETS",
]
_MODE_META = {
    "🎤 ASK JOSEPH": ("🎤", "ASK JOSEPH", "Ask Joseph anything — voice or text"),
    "🏀 GAMES TONIGHT": ("🏀", "GAMES TONIGHT", "Full game breakdowns & takes"),
    "👤 SCOUT A PLAYER": ("👤", "SCOUT A PLAYER", "Deep dive into any player"),
    "🎰 BUILD MY BETS": ("🎰", "BUILD MY BETS", "Build optimal parlay tickets"),
}

if "studio_mode" not in st.session_state:
    st.session_state["studio_mode"] = _MODE_OPTIONS[0]

# Render styled mode cards as visual preview
_mode_cards_html = '<div class="studio-mode-cards">'
for _m in _MODE_OPTIONS:
    _icon, _title, _tag = _MODE_META[_m]
    _active = "active" if _m == st.session_state["studio_mode"] else ""
    _mode_cards_html += (
        f'<div class="studio-mode-card {_active}">'
        f'<div class="studio-mode-icon">{_icon}</div>'
        f'<div class="studio-mode-title">{_title}</div>'
        f'<div class="studio-mode-tag">{_tag}</div>'
        f'</div>'
    )
_mode_cards_html += '</div>'
st.markdown(_mode_cards_html, unsafe_allow_html=True)

mode = st.radio(
    "Choose your mode",
    _MODE_OPTIONS,
    index=_MODE_OPTIONS.index(st.session_state["studio_mode"]),
    horizontal=True,
    label_visibility="collapsed",
    key="studio_mode_radio",
)
st.session_state["studio_mode"] = mode

# ── Hot Take Mode Toggle ─────────────────────────────────────
# When enabled, Joseph gives a contrarian pick that goes AGAINST the model's math
if "joseph_hot_take_mode" not in st.session_state:
    st.session_state["joseph_hot_take_mode"] = False

_hot_take_cols = st.columns([3, 1])
with _hot_take_cols[1]:
    _hot_take_on = st.toggle(
        "🔥 Hot Take Mode",
        value=st.session_state["joseph_hot_take_mode"],
        key="studio_hot_take_toggle",
        help="When ON, Joseph gives a contrarian pick that goes against the model's math",
    )
    st.session_state["joseph_hot_take_mode"] = _hot_take_on

if st.session_state["joseph_hot_take_mode"]:
    _hot_take_lines = [
        "🔥 HOT TAKE MODE is ON! Joseph is going AGAINST the math tonight — pure INSTINCT!",
        "🔥 The model says one thing, but Joseph's GUT says ANOTHER. Trust the man, not the machine!",
        "🔥 HOT TAKE MODE ACTIVATED! When has the math EVER captured the HEART of the game?!",
    ]
    st.markdown(
        f'<div style="background:rgba(255,68,68,0.08);border:1px solid rgba(255,68,68,0.3);'
        f'border-radius:8px;padding:10px 14px;margin-bottom:12px;'
        f'color:#F24336;font-size:0.85rem;font-family:\'Inter\',sans-serif;font-weight:600">'
        f'{random.choice(_hot_take_lines)}</div>',
        unsafe_allow_html=True,
    )

# Quick navigation links (Enhancement 16)
st.markdown(
    '<div class="studio-quick-nav">'
    '<a href="#joseph-s-bets-tonight">🎯 Tonight\'s Bets</a>'
    '<a href="#the-dawg-board">🐕 Dawg Board</a>'
    '<a href="#joseph-s-track-record">📊 Track Record</a>'
    '<a href="#joseph-s-bet-history">📜 Bet History</a>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Joseph's Platform Preference ──────────────────────────────
# Joseph asks what betting platform the user is using.
# Persists in session state so it's remembered across interactions.
_PLATFORM_OPTIONS = ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"]
if "joseph_preferred_platform" not in st.session_state:
    st.session_state["joseph_preferred_platform"] = "PrizePicks"

_platform_fallback_icon = '<span style="font-size:16px">🎙️</span>'
avatar_b64 = get_joseph_avatar_b64()
_platform_avatar = _avatar_inline(32) if avatar_b64 else _platform_fallback_icon
st.markdown(
    f'<div style="display:flex;align-items:center;gap:10px;'
    f'margin:8px 0 16px 0;padding:10px 16px;'
    f'background:rgba(255,94,0,0.06);border-left:3px solid #F9C62B;'
    f'border-radius:6px">'
    f'{_platform_avatar}'
    f'<span style="color:#e2e8f0;font-size:0.88rem;font-family:Inter,sans-serif">'
    f'What betting app are you using tonight?</span></div>',
    unsafe_allow_html=True,
)
joseph_platform = st.radio(
    "Your betting platform",
    _PLATFORM_OPTIONS,
    index=_PLATFORM_OPTIONS.index(st.session_state["joseph_preferred_platform"]),
    horizontal=True,
    label_visibility="collapsed",
    key="joseph_platform_radio",
)
st.session_state["joseph_preferred_platform"] = joseph_platform

# Shared data
analysis_results = st.session_state.get("analysis_results", [])
teams_data_list = st.session_state.get("teams_data", None)
if teams_data_list is None:
    try:
        teams_data_list = load_teams_data()
    except Exception:
        teams_data_list = []

# Convert list to dict keyed by team abbreviation if needed
if isinstance(teams_data_list, list):
    _teams_dict = {}
    for t in teams_data_list:
        key = t.get("team", t.get("abbreviation", t.get("name", "")))
        if key:
            _teams_dict[key] = t
    teams_data = _teams_dict
elif isinstance(teams_data_list, dict):
    teams_data = teams_data_list
else:
    teams_data = {}


# ─────────────────────────────────────────────────────────────
# MODE 0: ASK JOSEPH (voice or text)
# ─────────────────────────────────────────────────────────────
if mode == "🎤 ASK JOSEPH":
    st.markdown(
        '<div class="studio-section-title">Ask Joseph a Question</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        render_avatar_commentary(
            "What's on your mind? Type your question below — or hit the mic "
            "button and just TALK to me. I'll give you the real answer, no fluff."
        ),
        unsafe_allow_html=True,
    )
    _voice_question = st.text_input(
        "Ask Joseph a question",
        placeholder="Type or use the mic button below to ask Joseph anything...",
        label_visibility="collapsed",
        key="studio_voice_question",
    )
    # Inject browser-native Web Speech API for voice input
    st.markdown(
        """<script>
        (function() {
            if (window.__josephVoiceInit) return;
            window.__josephVoiceInit = true;
            var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;
            var inputs = window.parent.document.querySelectorAll('input[aria-label="Ask Joseph a question"]');
            if (!inputs.length) return;
            var input = inputs[inputs.length - 1];
            var btn = document.createElement('button');
            btn.textContent = '🎤 Speak';
            btn.style.cssText = 'position:absolute;right:8px;top:50%;transform:translateY(-50%);'
                + 'background:#F9C62B;color:#fff;border:none;border-radius:6px;padding:4px 10px;'
                + 'font-size:0.75rem;cursor:pointer;font-family:Inter,sans-serif;z-index:10';
            btn.onclick = function(e) {
                e.preventDefault();
                var rec = new SpeechRecognition();
                rec.lang = 'en-US';
                rec.onresult = function(ev) {
                    var txt = ev.results[0][0].transcript;
                    var nativeSet = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    nativeSet.call(input, txt);
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                };
                rec.start();
                btn.textContent = '🔴 Listening...';
                rec.onend = function() { btn.textContent = '🎤 Speak'; };
            };
            if (input.parentElement) {
                input.parentElement.style.position = 'relative';
                input.parentElement.appendChild(btn);
            }
        })();
        </script>""",
        unsafe_allow_html=True,
    )

    # Handle voice/text question
    if _voice_question and _voice_question.strip():
        _q = _voice_question.strip()
        _q_safe = _html.escape(_q)
        _todays_games = st.session_state.get("todays_games", [])
        _is_hot_take = st.session_state.get("joseph_hot_take_mode", False)
        if _BRAIN_AVAILABLE:
            try:
                _voice_answer = joseph_quick_take(
                    analysis_results,
                    teams_data,
                    _todays_games,
                    context=f"user_question: {_q_safe}",
                )
                # When Hot Take Mode is on, prepend a contrarian spin
                if _is_hot_take:
                    _hot_take_prefix = random.choice([
                        "🔥 HOT TAKE — the math says one thing but Joseph says DIFFERENT! ",
                        "🔥 CONTRARIAN ALERT — I'm going AGAINST the consensus here! ",
                        "🔥 HOT TAKE MODE — everybody else is WRONG and here's WHY! ",
                    ])
                    _voice_answer = _hot_take_prefix + _voice_answer
            except Exception:
                _voice_answer = (
                    f"Joseph heard your question about '{_q_safe}' "
                    f"— give me a second to pull up the data!"
                )
        else:
            _voice_answer = (
                f"Joseph heard you ask about '{_q_safe}' "
                f"— the brain module is warming up!"
            )
        st.markdown(
            render_avatar_commentary(_voice_answer),
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────────────────────
# MODE 1: GAMES TONIGHT
# ─────────────────────────────────────────────────────────────
if mode == "🏀 GAMES TONIGHT":
    todays_games = st.session_state.get("todays_games", [])

    if not todays_games:
        st.markdown(
            render_empty_state(
                "No games loaded yet.",
                cta_text="Go to 📡 Live Games →",
                cta_page="/📡_Live_Games",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="studio-section-title">Tonight\'s Games</div>',
            unsafe_allow_html=True,
        )

        for g_idx, game in enumerate(todays_games):
            away = game.get("away_team", "AWAY")
            home = game.get("home_team", "HOME")
            spread = game.get("spread", "—")
            total = game.get("total", "—")
            game_time = game.get("time", game.get("commence_time", ""))

            # Team colors (Enhancement 4)
            try:
                h_pri, h_sec = get_team_colors(home)
            except Exception:
                h_pri, h_sec = "#F9C62B", "#1e293b"
            try:
                a_pri, a_sec = get_team_colors(away)
            except Exception:
                a_pri, a_sec = "#F9C62B", "#1e293b"

            # Render styled game card HTML (Enhancement 4 + 19)
            _time_str = f' • {_html.escape(str(game_time))}' if game_time else ''
            st.markdown(
                f'<div class="studio-game-card" style="border-left-color:{h_pri}">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<div>'
                f'<span class="team-badge" style="background:{a_pri};color:{a_sec}">'
                f'{_html.escape(away)}</span>'
                f' <span style="color:var(--studio-muted);font-size:0.85rem">@</span> '
                f'<span class="team-badge" style="background:{h_pri};color:{h_sec}">'
                f'{_html.escape(home)}</span>'
                f'</div>'
                f'<div style="color:var(--studio-muted);font-size:0.78rem;'
                f'font-family:\'JetBrains Mono\',monospace">'
                f'Spread: {_html.escape(str(spread))} | O/U: {_html.escape(str(total))}'
                f'{_time_str}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            if st.button(f"Analyze {away} @ {home}", key=f"studio_game_{g_idx}", use_container_width=True):
                if not _BRAIN_AVAILABLE:
                    st.warning("Joseph's brain module is not available.")
                else:
                    # ── Joseph Loading Screen — NBA fun facts ──
                    try:
                        from utils.joseph_loading import joseph_loading_placeholder
                        _joseph_studio_loader = joseph_loading_placeholder("Joseph is breaking down the game")
                    except Exception:
                        _joseph_studio_loader = None
                    with st.spinner("Joseph is analyzing this game..."):
                        try:
                            result = joseph_analyze_game(game, teams_data, analysis_results)
                        except Exception as exc:
                            _logger.warning("joseph_analyze_game failed: %s", exc)
                            result = {}
                    if _joseph_studio_loader is not None:
                        try:
                            _joseph_studio_loader.empty()
                        except Exception:
                            pass

                    # ── Persist result so it survives page navigation ──
                    if result:
                        # Hot Take Mode: flip verdicts on best_props
                        if st.session_state.get("joseph_hot_take_mode", False):
                            _raw_props = result.get("best_props", [])
                            result["best_props"] = _apply_hot_take_to_list(_raw_props)
                            result["_hot_take_applied"] = True
                        st.session_state.setdefault("studio_game_results", {})[g_idx] = result
                        st.rerun()
                    else:
                        st.session_state.setdefault("studio_game_results", {})[g_idx] = None

            # ── Display cached game analysis from session_state ──
            _cached_result = st.session_state.get("studio_game_results", {}).get(g_idx)
            if _cached_result:
                result = _cached_result
                if result.get("_hot_take_applied"):
                    st.markdown(
                        '<div style="background:rgba(255,68,68,0.08);'
                        'border:1px solid rgba(255,68,68,0.3);border-radius:8px;'
                        'padding:8px 14px;margin-bottom:10px;color:#F24336;'
                        'font-size:0.82rem;font-weight:600">'
                        '🔥 HOT TAKE — Joseph is going AGAINST the model on these picks!</div>',
                        unsafe_allow_html=True,
                    )

                # Avatar + commentary (Enhancement 18: use helper)
                try:
                    commentary = joseph_commentary(
                        [result], "analysis_results"
                    )
                except Exception:
                    commentary = ""

                if commentary:
                    st.markdown(
                        render_avatar_commentary(commentary),
                        unsafe_allow_html=True,
                    )

                # Game narrative
                narrative = result.get("game_narrative", "")
                if narrative:
                    st.markdown(
                        render_broadcast_segment({
                            "title": "📖 GAME NARRATIVE",
                            "body": _html.escape(narrative),
                        }),
                        unsafe_allow_html=True,
                    )

                # Pace take
                pace = result.get("pace_take", "")
                if pace:
                    st.markdown(
                        render_broadcast_segment({
                            "title": "⚡ PACE TAKE",
                            "body": _html.escape(pace),
                        }),
                        unsafe_allow_html=True,
                    )

                # Scheme analysis
                scheme = result.get("scheme_analysis", "")
                if scheme:
                    st.markdown(
                        render_broadcast_segment({
                            "title": "🛡️ SCHEME ANALYSIS",
                            "body": _html.escape(scheme),
                        }),
                        unsafe_allow_html=True,
                    )

                # Key matchup
                matchup = result.get("key_matchup", result.get("matchup", ""))
                if matchup:
                    st.markdown(
                        render_broadcast_segment({
                            "title": "🔑 KEY MATCHUP",
                            "body": _html.escape(str(matchup)),
                        }),
                        unsafe_allow_html=True,
                    )

                # Joseph's top 3 bets for this game
                best_props = result.get("best_props", [])[:3]
                if best_props:
                    st.markdown(
                        '<div class="joseph-segment-title">'
                        '🎯 Joseph\'s Top 3 Bets for this Game'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                    for bp in best_props:
                        v = bp.get("verdict", "LEAN")
                        emoji = VERDICT_EMOJIS.get(
                            v.upper().replace(" ", "_"), "✅"
                        )
                        bp_name = _html.escape(str(bp.get("player_name", bp.get("player", ""))))
                        bp_rant = _html.escape(str(bp.get("rant", "")))
                        st.markdown(
                            render_broadcast_segment({
                                "title": f"{bp_name}",
                                "body": bp_rant,
                                "verdict": v,
                            }),
                            unsafe_allow_html=True,
                        )

                # Game total and spread opinions
                total_opinion = result.get("total_opinion", result.get("joseph_game_total_take", ""))
                if total_opinion:
                    st.markdown(
                        render_broadcast_segment({
                            "title": "📊 TOTAL OPINION",
                            "body": _html.escape(total_opinion),
                        }),
                        unsafe_allow_html=True,
                    )

                spread_opinion = result.get("spread_opinion", result.get("joseph_spread_take", ""))
                if spread_opinion:
                    st.markdown(
                        render_broadcast_segment({
                            "title": "📏 SPREAD OPINION",
                            "body": _html.escape(spread_opinion),
                        }),
                        unsafe_allow_html=True,
                    )

                # Risk warning
                risk = result.get("blowout_risk", result.get("risk_warning", ""))
                if risk:
                    st.markdown(
                        f'<div style="color:#eab308;font-size:0.88rem;'
                        f'margin:10px 0;padding:10px 14px;'
                        f'border-left:3px solid #eab308;'
                        f'background:rgba(234,179,8,0.06);'
                        f'border-radius:4px">'
                        f'⚠️ <strong>Risk Warning:</strong> '
                        f'{_html.escape(str(risk))}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                # Nerd stats (Enhancement 20: consolidated helper)
                with st.expander("📊 Nerd Stats"):
                    _game_nerd_keys = [
                        "pace_take", "scheme_analysis", "blowout_risk",
                        "game_narrative", "total_opinion", "joseph_game_total_take",
                        "spread_opinion", "joseph_spread_take",
                        "betting_angle", "risk_warning",
                    ]
                    _nerd_html = render_nerd_stats(result, keys=_game_nerd_keys)
                    if _nerd_html:
                        st.markdown(_nerd_html, unsafe_allow_html=True)
            elif _cached_result is None and g_idx in st.session_state.get("studio_game_results", {}):
                st.markdown(
                    render_empty_state(
                        "Joseph couldn't analyze this game — data may be limited.",
                        cta_text="Run ⚡ Neural Analysis →",
                        cta_page="/⚡_Quantum_Analysis_Matrix",
                    ),
                    unsafe_allow_html=True,
                )


# ─────────────────────────────────────────────────────────────
# MODE 2: SCOUT A PLAYER
# ─────────────────────────────────────────────────────────────
elif mode == "👤 SCOUT A PLAYER":
    # Build player list from analysis results or loaded data
    player_options = []
    _seen = set()
    for ar in analysis_results:
        name = ar.get("player_name", ar.get("player", ar.get("name", "")))
        team = ar.get("team", "")
        label = f"{name} ({team})" if team else name
        if label and label not in _seen:
            _seen.add(label)
            player_options.append((label, ar))

    if not player_options:
        try:
            players_data = load_players_data()
            for pd in players_data:
                name = pd.get("name", pd.get("player", ""))
                team = pd.get("team", "")
                label = f"{name} ({team})" if team else name
                if label and label not in _seen:
                    _seen.add(label)
                    player_options.append((label, pd))
        except Exception:
            pass

    if not player_options:
        st.markdown(
            render_empty_state(
                "No players available yet.",
                cta_text="Run ⚡ Neural Analysis →",
                cta_page="/⚡_Quantum_Analysis_Matrix",
            ),
            unsafe_allow_html=True,
        )
    else:
        # Sort by team, then name (Enhancement 10: grouped by team)
        player_options.sort(key=lambda x: (
            x[1].get("team", "ZZZ"),  # group by team
            x[0],                     # then by name
        ))

        selected_label = st.selectbox(
            "Select a player to scout",
            [p[0] for p in player_options],
        )

        if selected_label:
            player_data = next(
                (p[1] for p in player_options if p[0] == selected_label), {}
            )

            if not _BRAIN_AVAILABLE:
                st.warning("Joseph's brain module is not available.")
            else:
                todays_games = st.session_state.get("todays_games", [])
                # ── Joseph Loading Screen — NBA fun facts ──
                try:
                    from utils.joseph_loading import joseph_loading_placeholder
                    _joseph_scout_loader = joseph_loading_placeholder("Joseph is scouting the player")
                except Exception:
                    _joseph_scout_loader = None
                with st.spinner("Joseph is scouting this player..."):
                    try:
                        result = joseph_analyze_player(
                            player_data, todays_games, teams_data, analysis_results
                        )
                    except Exception as exc:
                        _logger.warning("joseph_analyze_player failed: %s", exc)
                        result = {}
                if _joseph_scout_loader is not None:
                    try:
                        _joseph_scout_loader.empty()
                    except Exception:
                        pass

                if result:
                    # Hot Take Mode: flip best_prop and alt verdicts
                    if st.session_state.get("joseph_hot_take_mode", False):
                        bp = result.get("best_prop")
                        if isinstance(bp, dict) and bp:
                            result["best_prop"] = _apply_hot_take(bp)
                        _alts = result.get("alternative_props", result.get("alt_props", []))
                        if _alts:
                            key = "alternative_props" if "alternative_props" in result else "alt_props"
                            result[key] = _apply_hot_take_to_list(
                                [a for a in _alts if isinstance(a, dict)]
                            )
                        st.markdown(
                            '<div style="background:rgba(255,68,68,0.08);'
                            'border:1px solid rgba(255,68,68,0.3);border-radius:8px;'
                            'padding:8px 14px;margin-bottom:10px;color:#F24336;'
                            'font-size:0.82rem;font-weight:600">'
                            '🔥 HOT TAKE — Joseph is going AGAINST the model on this scouting report!</div>',
                            unsafe_allow_html=True,
                        )

                    # Avatar + scouting report (Enhancement 18: use helper)
                    report = result.get("scouting_report", "")
                    if report:
                        st.markdown(
                            render_avatar_commentary(report),
                            unsafe_allow_html=True,
                        )

                    # Archetype badge + letter grade
                    archetype = result.get("archetype", "")
                    grade = result.get("grade", "")
                    if archetype or grade:
                        badge_parts = []
                        if archetype:
                            badge_parts.append(
                                f'<span style="background:rgba(255,94,0,0.15);'
                                f'color:#F9C62B;padding:4px 12px;border-radius:6px;'
                                f'font-family:\'Inter\',sans-serif;font-size:0.8rem;'
                                f'font-weight:600">{_html.escape(str(archetype))}</span>'
                            )
                        if grade:
                            grade_color = "#22c55e" if grade in ("A+", "A", "A-") else (
                                "#eab308" if grade.startswith("B") else "var(--studio-muted,#94a3b8)"
                            )
                            badge_parts.append(
                                f'<span style="background:rgba(15,23,42,0.8);'
                                f'color:{grade_color};padding:4px 14px;'
                                f'border-radius:6px;font-family:\'Inter\',sans-serif;'
                                f'font-size:1rem;font-weight:700;'
                                f'border:1px solid {grade_color}">'
                                f'{_html.escape(str(grade))}</span>'
                            )
                        st.markdown(
                            f'<div style="display:flex;gap:10px;margin:12px 0">'
                            + "".join(badge_parts)
                            + "</div>",
                            unsafe_allow_html=True,
                        )

                    # Tonight's matchup take
                    matchup_take = result.get("matchup_take", result.get("tonight_matchup", ""))
                    if matchup_take:
                        st.markdown(
                            render_broadcast_segment({
                                "title": "🎯 TONIGHT'S MATCHUP",
                                "body": _html.escape(str(matchup_take)),
                            }),
                            unsafe_allow_html=True,
                        )

                    # Best prop with full rant
                    best_prop = result.get("best_prop", {})
                    if isinstance(best_prop, dict) and best_prop:
                        v = best_prop.get("verdict", "LEAN")
                        rant = best_prop.get("rant", "")
                        st.markdown(
                            render_broadcast_segment({
                                "title": "💰 BEST PROP",
                                "body": _html.escape(str(rant)),
                                "verdict": v,
                            }),
                            unsafe_allow_html=True,
                        )

                    # Alternative props
                    alt_props = result.get("alternative_props", result.get("alt_props", []))
                    if alt_props:
                        st.markdown(
                            '<div class="joseph-segment-title">'
                            '📋 Alternative Props</div>',
                            unsafe_allow_html=True,
                        )
                        for ap in alt_props[:3]:
                            if isinstance(ap, dict):
                                ap_text = ap.get("summary", ap.get("rant", ""))
                                if not ap_text:
                                    # Format key fields instead of dumping the raw dict
                                    _ap_player = ap.get("player_name", ap.get("player", ""))
                                    _ap_stat = ap.get("stat_type", ap.get("stat", ""))
                                    _ap_dir = ap.get("direction", "")
                                    _ap_line = ap.get("prop_line", ap.get("line", ""))
                                    _ap_verdict = ap.get("verdict", "")
                                    ap_text = " ".join(
                                        p for p in [_ap_player, _ap_stat, _ap_dir, str(_ap_line), _ap_verdict] if p
                                    ) or "Alternative prop"
                            else:
                                ap_text = str(ap)
                            st.markdown(
                                f'<div style="color:#e2e8f0;font-size:0.88rem;'
                                f'padding:6px 0;border-bottom:1px solid '
                                f'rgba(148,163,184,0.08)">'
                                f'{_html.escape(str(ap_text))}</div>',
                                unsafe_allow_html=True,
                            )

                    # Historical comp
                    comp = result.get("comp", result.get("historical_comp", {}))
                    if isinstance(comp, dict) and comp.get("name"):
                        st.markdown(
                            render_broadcast_segment({
                                "title": "📜 HISTORICAL COMP",
                                "body": _html.escape(str(comp.get("name", "")))
                                + (" — " + _html.escape(str(comp.get("narrative", "")))
                                   if comp.get("narrative") else ""),
                            }),
                            unsafe_allow_html=True,
                        )

                    # Fun fact
                    fun_fact = result.get("fun_fact", "")
                    if fun_fact:
                        st.markdown(
                            f'<div style="color:#ff9e00;font-size:0.88rem;'
                            f'margin:10px 0;padding:10px 14px;'
                            f'border-left:3px solid #ff9e00;'
                            f'background:rgba(255,158,0,0.06);'
                            f'border-radius:4px">🎲 '
                            f'{_html.escape(str(fun_fact))}</div>',
                            unsafe_allow_html=True,
                        )

                    # Risk factors
                    risks = result.get("risk_factors", result.get("risks", []))
                    if risks:
                        st.markdown(
                            '<div class="joseph-segment-title">⚠️ Risk Factors</div>',
                            unsafe_allow_html=True,
                        )
                        for rf in risks:
                            st.markdown(
                                f'<div style="color:#eab308;font-size:0.85rem;'
                                f'padding:4px 0">• {_html.escape(str(rf))}</div>',
                                unsafe_allow_html=True,
                            )

                    # Nerd Stats expander (Enhancement 20: consolidated helper)
                    with st.expander("📊 Nerd Stats"):
                        _scout_nerd_keys = [
                            "gravity", "trend", "grade", "archetype",
                            "scouting_report", "matchup_take",
                            "narrative_tags",
                        ]
                        _nerd_html = render_nerd_stats(result, keys=_scout_nerd_keys)
                        if _nerd_html:
                            st.markdown(_nerd_html, unsafe_allow_html=True)
                else:
                    st.markdown(
                        render_empty_state(
                            "Joseph couldn't scout this player — data may be limited.",
                            cta_text="Run ⚡ Neural Analysis →",
                            cta_page="/⚡_Quantum_Analysis_Matrix",
                        ),
                        unsafe_allow_html=True,
                    )


# ─────────────────────────────────────────────────────────────
# MODE 3: BUILD MY BETS
# ─────────────────────────────────────────────────────────────
elif mode == "🎰 BUILD MY BETS":
    if not _BRAIN_AVAILABLE:
        st.warning("Joseph's brain module is not available.")
    else:
        # Use analysis_results if available, otherwise try platform props
        _bets_data = analysis_results
        if not _bets_data:
            # Fallback: use platform props from session state
            _platform_props = st.session_state.get("platform_props", [])
            if _platform_props:
                _bets_data = _platform_props
                st.markdown(
                    render_broadcast_segment({
                        "title": "📡 LIVE PROPS LOADED",
                        "body": (
                            f"Using <strong>{len(_platform_props)}</strong> live props "
                            f"from betting platforms. For full analysis, run "
                            f"<strong>⚡ Neural Analysis</strong> first."
                        ),
                    }),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    render_empty_state(
                        "Load games and get live props, or run Neural Analysis to populate data for bet building!",
                        cta_text="Go to 📡 Live Games →",
                        cta_page="/📡_Live_Games",
                    ),
                    unsafe_allow_html=True,
                )

        if _bets_data:
            # Enhancement 17: Verdict heatmap before entry size selection
            _existing_joseph = st.session_state.get("joseph_results", [])
            if _existing_joseph:
                _heatmap_html = render_verdict_heatmap_html(_existing_joseph)
                if _heatmap_html:
                    st.markdown(_heatmap_html, unsafe_allow_html=True)

            st.markdown(
                '<div class="studio-section-title">Choose Your Entry Size</div>',
                unsafe_allow_html=True,
            )

            # 5 large columns with leg-count buttons
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                btn2 = st.button("2️⃣ POWER PLAY", use_container_width=True)
            with col2:
                btn3 = st.button("3️⃣ TRIPLE THREAT", use_container_width=True)
            with col3:
                btn4 = st.button("4️⃣ THE QUAD", use_container_width=True)
            with col4:
                btn5 = st.button("5️⃣ HIGH FIVE", use_container_width=True)
            with col5:
                btn6 = st.button("6️⃣ THE FULL SEND", use_container_width=True)

            # Use Joseph's platform preference (from top selector)
            platform = joseph_platform

            st.markdown(
                f'<div style="color:var(--studio-muted);font-size:0.82rem;margin:4px 0 8px 0">'
                f'Building bets for <strong style="color:var(--studio-accent)">{_html.escape(platform)}</strong></div>',
                unsafe_allow_html=True,
            )

            # Determine which button was pressed
            selected_legs = None
            if btn2:
                selected_legs = 2
            elif btn3:
                selected_legs = 3
            elif btn4:
                selected_legs = 4
            elif btn5:
                selected_legs = 5
            elif btn6:
                selected_legs = 6

            # Regenerate key
            if "studio_regen_seed" not in st.session_state:
                st.session_state["studio_regen_seed"] = 0

            if selected_legs:
                # Set random seed for regeneration variety
                random.seed(st.session_state["studio_regen_seed"] + (selected_legs * 1000))

                with st.spinner(
                    f"Joseph is building your {TICKET_NAMES.get(selected_legs, '')}..."
                ):
                    try:
                        ticket_result = joseph_generate_best_bets(
                            selected_legs, _bets_data, teams_data
                        )
                    except Exception as exc:
                        _logger.warning("joseph_generate_best_bets failed: %s", exc)
                        ticket_result = {}

                if ticket_result and ticket_result.get("legs"):
                    # Hot Take Mode: flip verdicts on ticket legs
                    if st.session_state.get("joseph_hot_take_mode", False):
                        ticket_result["legs"] = _apply_hot_take_to_list(
                            ticket_result.get("legs", [])
                        )
                        ticket_result["rant"] = (
                            "🔥 HOT TAKE TICKET — Joseph is going AGAINST "
                            "the model on EVERY leg! Pure instinct, no math!"
                        )
                        st.markdown(
                            '<div style="background:rgba(255,68,68,0.08);'
                            'border:1px solid rgba(255,68,68,0.3);border-radius:8px;'
                            'padding:8px 14px;margin-bottom:10px;color:#F24336;'
                            'font-size:0.82rem;font-weight:600">'
                            '🔥 HOT TAKE TICKET — All legs are CONTRARIAN picks!</div>',
                            unsafe_allow_html=True,
                        )

                    # Store ticket in session state for comparison (Enhancement 11)
                    if "studio_tickets" not in st.session_state:
                        st.session_state["studio_tickets"] = {}
                    st.session_state["studio_tickets"][selected_legs] = ticket_result

                    # Inline reaction (Enhancement 18: use helper)
                    try:
                        reaction = joseph_commentary([ticket_result], "ticket_generated")
                    except Exception:
                        reaction = ""

                    if reaction:
                        st.markdown(
                            render_avatar_commentary(reaction, size=40),
                            unsafe_allow_html=True,
                        )

                    # Ticket card
                    ticket_name = ticket_result.get(
                        "ticket_name", TICKET_NAMES.get(selected_legs, "TICKET")
                    )
                    pitch = ticket_result.get("rant", ticket_result.get("pitch", ""))

                    legs_html = ""
                    _clipboard_lines = []  # for copy-to-clipboard (Enhancement 12)
                    for leg in ticket_result.get("legs", []):
                        l_player = _html.escape(str(leg.get("player_name", leg.get("player", ""))))
                        l_dir = _html.escape(str(leg.get("direction", "")))
                        l_line = leg.get("prop_line", leg.get("line", ""))
                        l_stat = _html.escape(
                            str(leg.get("stat_type", leg.get("prop", "")))
                        )
                        l_verdict = leg.get("verdict", "LEAN")
                        l_emoji = VERDICT_EMOJIS.get(
                            l_verdict.upper().replace(" ", "_"), "✅"
                        )
                        l_oneliner = _html.escape(
                            str(leg.get("one_liner", leg.get("rant", "")[:80]))
                        )

                        legs_html += (
                            f'<div class="studio-ticket-leg">'
                            f'{_html.escape(l_emoji)} '
                            f'<strong>{l_player}</strong> '
                            f'{l_stat} {l_dir} {_html.escape(str(l_line))} '
                            f'<span style="color:var(--studio-muted);font-size:0.82rem">'
                            f'— {l_oneliner}</span>'
                            f'</div>'
                        )
                        _clipboard_lines.append(
                            f"{leg.get('player_name', leg.get('player', ''))} "
                            f"{leg.get('stat_type', leg.get('prop', ''))} "
                            f"{leg.get('direction', '')} {l_line}"
                        )

                    # Combined stats
                    combined_prob = ticket_result.get("combined_probability",
                                                      ticket_result.get("total_ev", 0))
                    ev = ticket_result.get("expected_value",
                                           ticket_result.get("total_ev", 0))
                    synergy = ticket_result.get("synergy_score",
                                                ticket_result.get("correlation_score", 0))

                    # Enhancement 5: Confidence gauge SVG
                    # Normalize metrics to 0-100 scale for the gauge:
                    # - prob: if <=1 treat as fraction (e.g. 0.65 → 65%), else use as-is
                    # - ev: EV typically ranges -5 to +5; shift by +5 then scale by 10
                    # - synergy: if <=1 treat as fraction, else use as-is
                    _prob_raw = _safe_float(combined_prob)
                    _prob_pct = _prob_raw * 100 if _prob_raw <= 1 else _prob_raw
                    _ev_raw = _safe_float(ev)
                    _ev_bar = max(0, min(100, (_ev_raw + 5) * 10))
                    _syn_raw = _safe_float(synergy)
                    _syn_bar = max(0, min(100, _syn_raw * 100 if _syn_raw <= 1 else _syn_raw))
                    _gauge_html = render_confidence_gauge_svg(_prob_pct, _ev_bar, _syn_bar)

                    st.markdown(
                        f'<div class="studio-ticket-card">'
                        f'<div class="studio-ticket-header">'
                        f'🎫 {_html.escape(str(ticket_name))}</div>'
                        f'<div style="color:var(--studio-muted);font-size:0.88rem;margin-bottom:14px">'
                        f'{_html.escape(str(pitch))}</div>'
                        f'{legs_html}'
                        f'<div style="display:flex;gap:20px;margin-top:14px;'
                        f'padding-top:12px;border-top:1px solid rgba(148,163,184,0.12);'
                        f'align-items:flex-start">'
                        f'<div style="flex:1">'
                        f'<div><span style="color:var(--studio-muted);font-size:0.78rem">'
                        f'Combined Prob</span><br>'
                        f'<span style="color:var(--studio-green);font-family:\'JetBrains Mono\','
                        f'monospace;font-weight:600">'
                        f'{combined_prob:.1%}</span></div>'
                        f'<div style="margin-top:8px"><span style="color:var(--studio-muted);font-size:0.78rem">EV</span><br>'
                        f'<span style="color:var(--studio-accent);font-family:\'JetBrains Mono\','
                        f'monospace;font-weight:600">'
                        f'{ev:+.2f}</span></div>'
                        f'<div style="margin-top:8px"><span style="color:var(--studio-muted);font-size:0.78rem">'
                        f'Synergy</span><br>'
                        f'<span style="color:var(--studio-cyan);font-family:\'JetBrains Mono\','
                        f'monospace;font-weight:600">'
                        f'{synergy:.2f}</span></div>'
                        f'</div>'
                        f'<div>{_gauge_html}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

                    # Enhancement 12: Copy ticket to clipboard
                    _clip_text = f"{ticket_name}\n" + "\n".join(_clipboard_lines)
                    st.code(_clip_text, language=None)
                    st.caption("📋 Copy the ticket above to share with your betting platform.")

                    # "Why These Connect:" narrative
                    why = ticket_result.get("why_these_legs",
                                            ticket_result.get("why_these_connect", ""))
                    if why:
                        st.markdown(
                            render_broadcast_segment({
                                "title": "🔗 Why These Connect",
                                "body": _html.escape(str(why)),
                            }),
                            unsafe_allow_html=True,
                        )

                    # Risk disclaimer
                    disclaimer = ticket_result.get(
                        "risk_disclaimer",
                        "All picks carry risk. Bet responsibly. Past performance does not guarantee future results.",
                    )
                    st.markdown(
                        f'<div style="color:var(--studio-muted);font-size:0.78rem;'
                        f'margin:10px 0;font-style:italic">'
                        f'⚠️ {_html.escape(str(disclaimer))}</div>',
                        unsafe_allow_html=True,
                    )

                    # Nerd Stats expander (Enhancement 20: consolidated helper)
                    nerd = ticket_result.get("nerd_stats", {})
                    with st.expander("📊 Nerd Stats"):
                        if isinstance(nerd, dict) and nerd:
                            _nerd_html = render_nerd_stats(nerd)
                            if _nerd_html:
                                st.markdown(_nerd_html, unsafe_allow_html=True)
                        else:
                            _ticket_nerd_keys = [
                                "combined_probability", "expected_value",
                                "synergy_score", "correlation_score",
                                "total_ev", "joseph_confidence",
                            ]
                            _nerd_html = render_nerd_stats(ticket_result, keys=_ticket_nerd_keys)
                            if _nerd_html:
                                st.markdown(_nerd_html, unsafe_allow_html=True)

                    # Regenerate button
                    if st.button("🔄 Regenerate", key="studio_regen"):
                        st.session_state["studio_regen_seed"] += 1
                        st.rerun()

                    # View All Options expander
                    if _TICKETS_AVAILABLE:
                        with st.expander("📋 View All Options — Top 3 Alternatives"):
                            joseph_results = st.session_state.get("joseph_results", [])
                            try:
                                alts = get_alternative_tickets(
                                    selected_legs, joseph_results, top_n=3
                                )
                            except Exception as exc:
                                _logger.warning("get_alternative_tickets failed: %s", exc)
                                alts = []

                            if alts:
                                for a_idx, alt in enumerate(alts, 1):
                                    alt_name = alt.get("ticket_name", f"Alt #{a_idx}")
                                    alt_pitch = alt.get("pitch", "")
                                    alt_edge = alt.get("total_edge", 0)
                                    st.markdown(
                                        f"**{a_idx}. {_html.escape(str(alt_name))}** "
                                        f"(Edge: {alt_edge:+.1f}%)"
                                    )
                                    if alt_pitch:
                                        st.markdown(
                                            f'<div style="color:var(--studio-muted,#94a3b8);font-size:0.85rem;'
                                            f'margin-bottom:8px">'
                                            f'{_html.escape(str(alt_pitch))}</div>',
                                            unsafe_allow_html=True,
                                        )
                                    alt_legs = alt.get("legs", [])
                                    for al in alt_legs:
                                        if isinstance(al, dict):
                                            al_name = _html.escape(
                                                str(al.get("player_name", al.get("player", "")))
                                            )
                                            al_stat = _html.escape(
                                                str(al.get("stat_type", al.get("prop", "")))
                                            )
                                            al_dir = _html.escape(
                                                str(al.get("direction", ""))
                                            )
                                            st.markdown(
                                                f"  • {al_name} {al_stat} {al_dir}"
                                            )
                                        else:
                                            # Alternative legs may be plain strings
                                            st.markdown(
                                                f"  • {_html.escape(str(al))}"
                                            )
                            else:
                                st.info("No alternative tickets available.")

                    # Payout table
                    if _FLEX_TABLES_AVAILABLE and platform in PLATFORM_FLEX_TABLES:
                        payout_table = PLATFORM_FLEX_TABLES[platform]
                        leg_payouts = payout_table.get(selected_legs, {})
                        if leg_payouts:
                            header_cells = "".join(
                                f"<th>{k} Correct</th>"
                                for k in sorted(leg_payouts.keys(), reverse=True)
                            )
                            data_cells = "".join(
                                f'<td class="{"highlight" if v > 0 else ""}">'
                                f'{v:.1f}x</td>'
                                for k, v in sorted(
                                    leg_payouts.items(), reverse=True
                                )
                            )
                            st.markdown(
                                f'<div style="margin-top:16px">'
                                f'<div style="color:#F9C62B;font-size:0.85rem;'
                                f'font-family:\'Inter\',sans-serif;margin-bottom:6px">'
                                f'{_html.escape(platform)} Payouts — '
                                f'{selected_legs}-Leg Entry</div>'
                                f'<table class="studio-payout-table">'
                                f'<thead><tr>{header_cells}</tr></thead>'
                                f'<tbody><tr>{data_cells}</tr></tbody>'
                                f'</table></div>',
                                unsafe_allow_html=True,
                            )
                else:
                    st.markdown(
                        render_empty_state(
                            "Joseph couldn't build a ticket — not enough qualifying picks.",
                            cta_text="Run ⚡ Neural Analysis →",
                            cta_page="/⚡_Quantum_Analysis_Matrix",
                        ),
                        unsafe_allow_html=True,
                    )

            # Enhancement 11: Side-by-side ticket comparison
            _stored_tickets = st.session_state.get("studio_tickets", {})
            if len(_stored_tickets) > 1:
                with st.expander("🔀 Compare Previous Tickets"):
                    _comp_cols = st.columns(len(_stored_tickets))
                    for _ci, (_legs, _tk) in enumerate(sorted(_stored_tickets.items())):
                        with _comp_cols[_ci]:
                            _tk_name = _tk.get("ticket_name", TICKET_NAMES.get(_legs, "TICKET"))
                            st.markdown(
                                f'<div style="font-family:\'Inter\',sans-serif;'
                                f'color:var(--studio-accent);font-size:0.85rem;'
                                f'font-weight:700;margin-bottom:6px">'
                                f'🎫 {_html.escape(str(_tk_name))}</div>',
                                unsafe_allow_html=True,
                            )
                            for _cl in _tk.get("legs", []):
                                _cl_name = _html.escape(str(_cl.get("player_name", _cl.get("player", ""))))
                                _cl_stat = _html.escape(str(_cl.get("stat_type", _cl.get("prop", ""))))
                                _cl_dir = _html.escape(str(_cl.get("direction", "")))
                                st.markdown(f"• {_cl_name} {_cl_stat} {_cl_dir}")


# ═════════════════════════════════════════════════════════════
# BELOW INTERACTIVE AREA
# ═════════════════════════════════════════════════════════════
st.divider()

# ── Dawg Board ───────────────────────────────────────────────
st.markdown(
    '<div id="the-dawg-board" class="studio-section-title">🐕 THE DAWG BOARD</div>',
    unsafe_allow_html=True,
)
joseph_results = st.session_state.get("joseph_results", [])

# Auto-generate Joseph's independent picks when none exist yet
if not joseph_results and _BRAIN_AVAILABLE:
    _gen_source = analysis_results
    _from_props = False
    if not _gen_source:
        _gen_source = st.session_state.get("platform_props", [])
        _from_props = True

    if _gen_source:
        # Show skeleton loader while Joseph scouts
        _skel_placeholder = st.empty()
        _skel_placeholder.markdown(render_skeleton_cards(3), unsafe_allow_html=True)
        # ── Joseph Loading Screen — NBA fun facts ──
        try:
            from utils.joseph_loading import joseph_loading_placeholder
            _joseph_board_loader = joseph_loading_placeholder("Joseph is scouting the board")
        except Exception:
            _joseph_board_loader = None
        with st.spinner("🎙️ Joseph is scouting the board..."):
            try:
                _players_raw = load_players_data()
                _p_lookup = {
                    str(p.get("name", p.get("player_name", ""))).lower().strip(): p
                    for p in _players_raw if p
                }
                _games = st.session_state.get("todays_games", [])

                if _from_props:
                    # All props including goblin/demon lines — Joseph sees everything
                    joseph_results = joseph_generate_independent_picks(
                        _gen_source, _p_lookup, _games, teams_data, max_picks=50,
                    )
                else:
                    # Sort by edge — no cap, Joseph analyzes the full slate
                    _sorted_ar = sorted(
                        _gen_source,
                        key=lambda r: abs(_extract_edge(r)),
                        reverse=True,
                    )
                    joseph_results = []
                    for _ar in _sorted_ar:
                        _pn = _ar.get(
                            "player_name",
                            _ar.get("player", _ar.get("name", "")),
                        )
                        _pd = _p_lookup.get(str(_pn).lower().strip(), {})
                        _gd = {}
                        _pt = _ar.get(
                            "team", _ar.get("player_team", _pd.get("team", "")),
                        )
                        for _g in _games:
                            if _pt in (
                                _g.get("home_team", ""),
                                _g.get("away_team", ""),
                            ):
                                _gd = _g
                                break
                        try:
                            _res = joseph_full_analysis(
                                _ar, _pd, _gd, teams_data,
                            )
                            _res["player"] = _pn
                            _res["prop"] = _ar.get("stat_type", "")
                            _res["line"] = _ar.get(
                                "line", _ar.get("prop_line", ""),
                            )
                            _res["direction"] = _ar.get("direction", "")
                            _res["team"] = _pt
                            _res["odds_type"] = _ar.get("odds_type", "standard")
                            joseph_results.append(_res)
                        except Exception:
                            pass

                    # ── Also run goblin/demon props through Joseph ────────
                    # The orchestrator filters them from analysis_results, so
                    # pull them separately from platform_props if available.
                    _alt_props = [
                        p for p in st.session_state.get("platform_props", [])
                        if str(p.get("odds_type", "standard")).lower() in ("goblin", "demon")
                    ]
                    if _alt_props:
                        try:
                            _alt_results = joseph_generate_independent_picks(
                                _alt_props, _p_lookup, _games, teams_data, max_picks=20,
                            )
                            joseph_results.extend(_alt_results)
                        except Exception:
                            pass

                if joseph_results:
                    st.session_state["joseph_results"] = joseph_results
                    # Auto-log Joseph's picks to bet tracker (once per session)
                    if not st.session_state.get("joseph_bets_logged"):
                        try:
                            from engine.joseph_bets import joseph_auto_log_bets as _jalab
                            _logged_count = _jalab(joseph_results)
                            st.session_state["joseph_bets_logged"] = True
                            if isinstance(_logged_count, int) and _logged_count > 0:
                                st.caption(f"📝 Joseph logged {_logged_count} pick(s) to your Bet Tracker")
                        except Exception:
                            pass
            except Exception as _dawg_err:
                _logger.warning(
                    "Auto-generation of Joseph's picks failed: %s", _dawg_err,
                )
        _skel_placeholder.empty()
        if _joseph_board_loader is not None:
            try:
                _joseph_board_loader.empty()
            except Exception:
                pass

if joseph_results:
    # ── Joseph's Best Bet of the Night hero card ──────────────────
    try:
        _best_candidates = [
            r for r in joseph_results
            if r.get("verdict") in ("LOCK", "SMASH")
        ]
        if not _best_candidates:
            _best_candidates = [r for r in joseph_results if r.get("verdict") == "LEAN"]
        if _best_candidates:
            _best = max(_best_candidates, key=lambda r: r.get("dawg_factor", 0))
            _b_player = _best.get("player", _best.get("player_name", ""))
            _b_verdict = _best.get("verdict", "")
            _b_emoji = _best.get("verdict_emoji", "🔒")
            _b_line = _best.get("line", "")
            _b_prop = _best.get("prop", _best.get("stat_type", ""))
            _b_dir = _best.get("direction", "")
            _b_edge = _best.get("edge", 0)
            _b_take = _best.get("top_pick_take") or _best.get("one_liner", "")
            st.markdown(
                f"""<div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                border:2px solid #e2b96a;border-radius:12px;padding:18px 22px;margin-bottom:18px">
                <div style="color:#e2b96a;font-size:13px;font-weight:700;letter-spacing:2px;
                text-transform:uppercase;margin-bottom:6px">🔒 Joseph's Best Bet Tonight</div>
                <div style="color:#fff;font-size:20px;font-weight:800">{_b_emoji} {_b_player}
                — {_b_dir} {_b_line} {_b_prop}</div>
                <div style="color:#aaa;font-size:13px;margin-top:6px">{_b_verdict} &bull;
                {_b_edge:.1f}% edge</div>
                <div style="color:#ccc;font-size:13px;margin-top:8px;font-style:italic">
                "{_b_take}"</div></div>""",
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    # ── Sort toggle ───────────────────────────────────────────────
    _sort_key = st.radio(
        "Sort Dawg Board by",
        options=["Dawg Factor", "Edge %", "Verdict", "Team"],
        index=0,
        horizontal=True,
        key="dawg_board_sort",
        label_visibility="collapsed",
    )
    try:
        _verdict_order = {"LOCK": 0, "SMASH": 1, "LEAN": 2, "FADE": 3, "STAY_AWAY": 4}
        if _sort_key == "Edge %":
            joseph_results = sorted(joseph_results, key=lambda r: abs(r.get("edge", 0)), reverse=True)
        elif _sort_key == "Verdict":
            joseph_results = sorted(joseph_results, key=lambda r: _verdict_order.get(r.get("verdict", "STAY_AWAY"), 5))
        elif _sort_key == "Team":
            joseph_results = sorted(joseph_results, key=lambda r: str(r.get("team", "")))
        else:  # Dawg Factor (default)
            joseph_results = sorted(joseph_results, key=lambda r: r.get("dawg_factor", 0), reverse=True)
    except Exception:
        pass

    render_dawg_board(joseph_results)

    # ── Joseph's Dark Horse Picks ────────────────────────────────
    try:
        from engine.joseph_brain._monolith import joseph_get_dark_horse_picks as _get_dh
        _dark_horses = _get_dh(joseph_results, 3)
        if _dark_horses:
            st.markdown(
                '<div class="studio-section-title" style="margin-top:28px">🏇 JOSEPH\'S DARK HORSE PICKS</div>',
                unsafe_allow_html=True,
            )
            st.caption("Sleepers, usage surges & alternate-line value the market hasn't caught up to yet.")
            _dh_cols = st.columns(len(_dark_horses))
            for _dhc, _dh in zip(_dh_cols, _dark_horses):
                with _dhc:
                    _dh_player = _dh.get("player", _dh.get("player_name", ""))
                    _dh_verdict = _dh.get("verdict", "LEAN")
                    _dh_emoji = _dh.get("verdict_emoji", "")
                    _dh_prop = _dh.get("prop", _dh.get("stat_type", ""))
                    _dh_line = _dh.get("line", "")
                    _dh_dir = _dh.get("direction", "")
                    _dh_edge = _dh.get("edge", 0)
                    _dh_tags = _dh.get("narrative_tags") or []
                    _dh_odds = str(_dh.get("odds_type", "standard")).lower()
                    _dh_tag_label = ""
                    if _dh_odds == "goblin":
                        _dh_tag_label = "🟢 GOBLIN LINE"
                    elif _dh_odds == "demon":
                        _dh_tag_label = "🔴 DEMON LINE"
                    elif "qeg_pick" in _dh_tags:
                        _dh_tag_label = "⚡ QEG"
                    elif "opportunity_boost" in _dh_tags:
                        _dh_tag_label = "🚀 USAGE SURGE"
                    elif "trending_up" in _dh_tags:
                        _dh_tag_label = "📈 HOT STREAK"
                    _dh_take = _dh.get("one_liner") or _dh.get("condensed_summary", "")
                    st.markdown(
                        f"""<div style="background:#1a1a2e;border:1px solid #4a3f7a;border-radius:10px;
                        padding:14px 16px;height:100%">
                        <div style="color:#b98ee4;font-size:11px;font-weight:700;letter-spacing:1px;
                        margin-bottom:4px">{_dh_tag_label}</div>
                        <div style="color:#fff;font-size:15px;font-weight:700">{_dh_emoji} {_dh_player}</div>
                        <div style="color:#aaa;font-size:12px;margin-top:3px">{_dh_dir} {_dh_line} {_dh_prop}</div>
                        <div style="color:#b98ee4;font-size:12px;margin-top:4px">{_dh_verdict} &bull;
                        {_dh_edge:.1f}% edge</div>
                        <div style="color:#888;font-size:11px;margin-top:6px;font-style:italic">
                        "{_dh_take}"</div></div>""",
                        unsafe_allow_html=True,
                    )
    except Exception:
        pass
else:
    st.markdown(
        render_empty_state(
            "Load games and get live props, or run Neural Analysis to populate Joseph's Dawg Board!",
            cta_text="Go to 📡 Live Games →",
            cta_page="/📡_Live_Games",
        ),
        unsafe_allow_html=True,
    )

# ── Joseph's Tonight's Bets ──────────────────────────────────
st.markdown(
    '<div id="joseph-s-bets-tonight" class="studio-section-title">🎯 JOSEPH\'S BETS TONIGHT</div>',
    unsafe_allow_html=True,
)

if joseph_results:
    # Filter to LOCK, SMASH, and LEAN verdicts — Joseph's actual bets
    _joseph_bets_tonight = [
        r for r in joseph_results
        if r.get("verdict") in ("LOCK", "SMASH", "LEAN")
    ]

    if _joseph_bets_tonight:
        _jbt_sorted = sorted(_joseph_bets_tonight, key=lambda x: abs(x.get("edge", 0)), reverse=True)

        # ── count line ─────────────────────────────────────────
        _n_locks  = sum(1 for r in _jbt_sorted if r.get("verdict") == "LOCK")
        _n_smash  = sum(1 for r in _jbt_sorted if r.get("verdict") == "SMASH")
        _n_lean   = sum(1 for r in _jbt_sorted if r.get("verdict") == "LEAN")
        _pill_html = ""
        for _lbl, _cnt, _clr in [("🔒 LOCK", _n_locks, "#a855f7"), ("🔥 SMASH", _n_smash, "#F24336"), ("✅ LEAN", _n_lean, "#00D559")]:
            if _cnt:
                _clr_rgb = ",".join(str(int(_clr.lstrip("#")[i:i+2], 16)) for i in (0, 2, 4))
                _pill_html += (
                    f'<span style="background:rgba({_clr_rgb},0.15);'
                    f'color:{_clr};border:1px solid {_clr};border-radius:20px;'
                    f'padding:3px 10px;font-size:0.72rem;font-weight:700;margin-right:6px">'
                    f'{_lbl} &times;{_cnt}</span>'
                )
        st.markdown(
            f'<div style="margin-bottom:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
            f'<span style="color:#6B7A9A;font-size:0.84rem">Joseph has '
            f'<strong style="color:#e2e8f0">{len(_jbt_sorted)}</strong> active bets tonight&nbsp;&mdash;&nbsp;</span>'
            f'{_pill_html}</div>',
            unsafe_allow_html=True,
        )

        # ── Premium bet cards ───────────────────────────────────
        _cards_html = '<div style="display:flex;flex-direction:column;gap:10px;margin-bottom:8px">'
        for _rank, _jb in enumerate(_jbt_sorted, 1):
            _jb_name    = _html.escape(str(_jb.get("player", _jb.get("name", "Unknown"))))
            _jb_prop    = _html.escape(str(_jb.get("prop", _jb.get("stat_type", ""))))
            _jb_dir     = _html.escape(str(_jb.get("direction", "")))
            _jb_line    = _jb.get("line", "")
            _jb_verdict = _jb.get("verdict", "")
            _jb_emoji   = _html.escape(str(_jb.get("verdict_emoji", "")))
            _jb_edge    = float(_jb.get("edge", 0) or 0)
            _jb_conf    = float(_jb.get("confidence", _jb.get("confidence_pct", 0)) or 0)
            _jb_team    = _html.escape(str(_jb.get("team", "")))
            _jb_liner   = _html.escape(str(_jb.get("one_liner", _jb.get("condensed_summary", "")) or "")[:110])
            _jb_df      = float(_jb.get("dawg_factor", 0) or 0)
            _jb_odds    = str(_jb.get("odds_type", "standard")).lower()

            # Verdict palette
            _vpal = {
                "LOCK":  {"border": "#a855f7", "bg": "rgba(168,85,247,0.08)", "badge_bg": "rgba(168,85,247,0.20)", "text": "#a855f7"},
                "SMASH": {"border": "#F24336", "bg": "rgba(242,67,54,0.08)",  "badge_bg": "rgba(242,67,54,0.20)",  "text": "#F24336"},
                "LEAN":  {"border": "#00D559", "bg": "rgba(0,213,89,0.08)",   "badge_bg": "rgba(0,213,89,0.20)",   "text": "#00D559"},
            }.get(_jb_verdict, {"border": "#334155", "bg": "rgba(51,65,85,0.08)", "badge_bg": "rgba(51,65,85,0.20)", "text": "#94a3b8"})

            _v_border = _vpal["border"]
            _v_bg     = _vpal["bg"]
            _v_badge  = _vpal["badge_bg"]
            _v_text   = _vpal["text"]

            # Edge bar (clamped 0-100%)
            _edge_bar_w = min(abs(_jb_edge) * 2.5, 100)
            _edge_clr   = "#00D559" if _jb_edge >= 0 else "#F24336"

            # Odds type tag
            _odds_tag = ""
            if _jb_odds == "goblin":
                _odds_tag = '<span style="background:rgba(34,197,94,0.18);color:#22c55e;border:1px solid #22c55e;border-radius:4px;padding:1px 7px;font-size:0.65rem;font-weight:700;margin-left:6px">GOBLIN</span>'
            elif _jb_odds == "demon":
                _odds_tag = '<span style="background:rgba(239,68,68,0.18);color:#ef4444;border:1px solid #ef4444;border-radius:4px;padding:1px 7px;font-size:0.65rem;font-weight:700;margin-left:6px">DEMON</span>'

            # Dawg factor bar (clamped 0-100% over scale of 10)
            _df_bar_w = min(_jb_df * 10, 100)
            _df_clr = "#F24336" if _jb_df >= 5 else "#a855f7" if _jb_df >= 3 else "#eab308" if _jb_df >= 1 else "#64748b"

            _cards_html += f"""
<div style="background:linear-gradient(135deg,#0f172a 0%,{_v_bg} 100%);
  border:1px solid {_v_border};border-left:4px solid {_v_border};
  border-radius:12px;padding:14px 18px;position:relative;overflow:hidden">

  <!-- glow accent -->
  <div style="position:absolute;top:-30px;right:-30px;width:120px;height:120px;
    background:radial-gradient(circle,{_v_border}22 0%,transparent 70%);pointer-events:none"></div>

  <!-- top row -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px">

    <div style="display:flex;align-items:center;gap:10px">
      <div style="background:#1e293b;color:#818cf8;border-radius:6px;
        padding:3px 8px;font-size:0.68rem;font-weight:800;min-width:28px;text-align:center">
        #{_rank}
      </div>
      <div>
        <div style="color:#f1f5f9;font-size:1.0rem;font-weight:800;line-height:1.1">
          {_jb_name}
        </div>
        <div style="color:#94a3b8;font-size:0.75rem;margin-top:2px">
          {_jb_team}
        </div>
      </div>
    </div>

    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <span style="background:{_v_badge};color:{_v_text};border:1px solid {_v_border};
        border-radius:20px;padding:4px 12px;font-size:0.78rem;font-weight:800;
        letter-spacing:0.5px">
        {_jb_emoji} {_html.escape(_jb_verdict)}
      </span>
      <span style="color:{_edge_clr};font-size:0.9rem;font-weight:800">
        {_jb_edge:+.1f}% edge
      </span>
    </div>

  </div>

  <!-- bet line -->
  <div style="margin-top:10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <span style="background:#1e293b;color:#e2e8f0;border-radius:8px;
      padding:5px 12px;font-size:0.88rem;font-weight:700;letter-spacing:0.3px">
      {_jb_dir} {_jb_line} {_jb_prop}
    </span>
    {_odds_tag}
  </div>

  <!-- one-liner -->
  {'<div style="margin-top:8px;color:#94a3b8;font-size:0.78rem;font-style:italic;line-height:1.4">&ldquo;' + _jb_liner + '&rdquo;</div>' if _jb_liner else ''}

  <!-- stat bars -->
  <div style="margin-top:12px;display:flex;gap:20px;flex-wrap:wrap">

    <div style="flex:1;min-width:110px">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px">
        <span style="color:#64748b;font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px">Edge</span>
        <span style="color:{_edge_clr};font-size:0.68rem;font-weight:700">{_jb_edge:+.1f}%</span>
      </div>
      <div style="height:4px;background:#1e293b;border-radius:2px;overflow:hidden">
        <div style="width:{_edge_bar_w:.0f}%;height:100%;background:{_edge_clr};border-radius:2px"></div>
      </div>
    </div>

    <div style="flex:1;min-width:110px">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px">
        <span style="color:#64748b;font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px">Confidence</span>
        <span style="color:#818cf8;font-size:0.68rem;font-weight:700">{_jb_conf:.0f}%</span>
      </div>
      <div style="height:4px;background:#1e293b;border-radius:2px;overflow:hidden">
        <div style="width:{min(_jb_conf,100):.0f}%;height:100%;background:#818cf8;border-radius:2px"></div>
      </div>
    </div>

    <div style="flex:1;min-width:110px">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px">
        <span style="color:#64748b;font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px">Dawg Factor</span>
        <span style="color:{_df_clr};font-size:0.68rem;font-weight:700">{_jb_df:.1f}</span>
      </div>
      <div style="height:4px;background:#1e293b;border-radius:2px;overflow:hidden">
        <div style="width:{_df_bar_w:.0f}%;height:100%;background:{_df_clr};border-radius:2px"></div>
      </div>
    </div>

  </div>

</div>"""

        _cards_html += '</div>'
        st.markdown(_cards_html, unsafe_allow_html=True)

        # Auto-save Joseph's bets to the bet tracker
        if _BETS_AVAILABLE:
            try:
                from tracking.database import insert_bet as _insert_joseph_bet
                import datetime as _dt_jb
                _saved_key = "joseph_bets_saved_today"
                if not st.session_state.get(_saved_key):
                    _saved_count = 0
                    _today_str = _dt_jb.date.today().strftime("%Y-%m-%d")
                    for _jb in _joseph_bets_tonight:
                        try:
                            _insert_joseph_bet({
                                "bet_date": _today_str,
                                "player_name": _jb.get("player", _jb.get("name", "")),
                                "team": _jb.get("team", ""),
                                "stat_type": _jb.get("prop", _jb.get("stat_type", "")),
                                "prop_line": _safe_float(_jb.get("line", 0)),
                                "direction": _jb.get("direction", "OVER"),
                                "platform": "Joseph M. Smith",
                                "confidence_score": _safe_float(_jb.get("confidence", 50)),
                                "edge_percentage": _safe_float(_jb.get("edge", 0)),
                                "tier": _jb.get("verdict", ""),
                                "notes": f"Joseph {_jb.get('verdict', '')} pick — edge {_safe_float(_jb.get('edge', 0)):+.1f}%",
                                "auto_logged": 1,
                            })
                            _saved_count += 1
                        except Exception:
                            pass
                    st.session_state[_saved_key] = True
                    if _saved_count > 0:
                        st.caption(f"📝 Auto-saved {_saved_count} bet(s) to the Bet Tracker.")
            except ImportError:
                pass
    else:
        st.markdown(
            render_empty_state("Joseph hasn't locked any SMASH or LEAN bets yet tonight."),
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        render_empty_state(
            "Run Neural Analysis to generate Joseph's bet picks.",
            cta_text="Run ⚡ Neural Analysis →",
            cta_page="/⚡_Quantum_Analysis_Matrix",
        ),
        unsafe_allow_html=True,
    )

# ── Override Report ──────────────────────────────────────────
st.markdown(
    '<div class="studio-section-title">⚡ OVERRIDE REPORT</div>',
    unsafe_allow_html=True,
)
if joseph_results:
    render_override_report(joseph_results)
else:
    st.markdown(
        render_empty_state("No overrides tonight — Joseph and the Quantum Matrix Engine agree across the board."),
        unsafe_allow_html=True,
    )

# ── Joseph's Track Record ───────────────────────────────────

@st.fragment
def _render_track_record_section():
    """Track Record fragment — only this section re-renders on filter change."""
    st.markdown(
        '<div id="joseph-s-track-record" class="studio-section-title">📊 JOSEPH\'S TRACK RECORD</div>',
        unsafe_allow_html=True,
    )
    if not _BETS_AVAILABLE:
        st.markdown(
            render_empty_state("Bet tracking module not available."),
            unsafe_allow_html=True,
        )
        return

    # Enhancement 14: Date range filter
    _tr_filter_col1, _tr_filter_col2 = st.columns([3, 1])
    with _tr_filter_col2:
        _tr_range = st.selectbox(
            "Time range",
            ["All Time", "Last 7 Days", "Last 30 Days", "This Season"],
            label_visibility="collapsed",
            key="studio_track_record_range",
        )

    # Build stats directly from bet rows so the selected time range applies.
    try:
        from tracking.database import load_all_bets as _load_all_bets
        _all_bets = _load_all_bets(limit=5000, exclude_linked=False)
    except Exception as exc:
        _logger.warning("Studio track record load failed: %s", exc)
        _all_bets = []

    def _is_joseph_bet_local(_bet: dict) -> bool:
        _notes = str(_bet.get("notes", ""))
        _platform = str(_bet.get("platform", ""))
        return "Joseph M. Smith" in _notes or _platform == "Joseph M. Smith"

    def _cutoff_for_range(_range_label: str):
        _today = _dt.date.today()
        if _range_label == "Last 7 Days":
            return _today - _dt.timedelta(days=6)
        if _range_label == "Last 30 Days":
            return _today - _dt.timedelta(days=29)
        if _range_label == "This Season":
            _season_year = _today.year if _today.month >= 10 else (_today.year - 1)
            return _dt.date(_season_year, 10, 1)
        return None

    _range_cutoff = _cutoff_for_range(_tr_range)
    _joseph_rows = []
    for _b in _all_bets:
        if not _is_joseph_bet_local(_b):
            continue
        if _range_cutoff is not None:
            _bd = str(_b.get("bet_date") or "")[:10]
            try:
                _bdate = _dt.date.fromisoformat(_bd)
            except ValueError:
                continue
            if _bdate < _range_cutoff:
                continue
        _joseph_rows.append(_b)

    total = len(_joseph_rows)
    wins = sum(1 for _b in _joseph_rows if str(_b.get("result", "")).upper() in ("WIN", "W"))
    losses = sum(1 for _b in _joseph_rows if str(_b.get("result", "")).upper() in ("LOSS", "L"))
    pending = total - wins - losses
    decided = wins + losses
    win_rate_pct = (wins / decided * 100.0) if decided > 0 else 0.0

    # Streak (most recent first)
    _sorted_rows = sorted(
        _joseph_rows,
        key=lambda _b: (str(_b.get("created_at", "")), int(_b.get("bet_id", 0))),
        reverse=True,
    )
    _results_seq = []
    for _b in _sorted_rows:
        _r = str(_b.get("result", "")).upper()
        if _r in ("WIN", "W"):
            _results_seq.append("W")
        elif _r in ("LOSS", "L"):
            _results_seq.append("L")
    streak = 0
    if _results_seq:
        _first = _results_seq[0]
        for _r in _results_seq:
            if _r == _first:
                streak += 1
            else:
                break
        if _first == "L":
            streak = -streak

    # Accuracy by verdict (decision-only denominator)
    def _verdict_pct(_verdict: str) -> float:
        _subset = [
            _b for _b in _joseph_rows
            if str(_b.get("tier", "")).upper() == _verdict
        ]
        _vw = sum(1 for _b in _subset if str(_b.get("result", "")).upper() in ("WIN", "W"))
        _vd = sum(1 for _b in _subset if str(_b.get("result", "")).upper() in ("WIN", "W", "LOSS", "L"))
        return (_vw / _vd * 100.0) if _vd > 0 else 0.0

    lock_pct = _verdict_pct("LOCK")
    smash_pct = _verdict_pct("SMASH")
    lean_pct = _verdict_pct("LEAN")

    # ── Premium Track Record Dashboard ─────────────────────────
    # Determine streak label and color
    if streak > 0:
        _streak_label = f"🔥 {streak}W Streak"
        _streak_clr = "#00D559"
    elif streak < 0:
        _streak_label = f"🧊 {abs(streak)}L Streak"
        _streak_clr = "#F24336"
    else:
        _streak_label = "— No streak"
        _streak_clr = "#64748b"

    _wr_clr = "#00D559" if win_rate_pct >= 60 else "#F9C62B" if win_rate_pct >= 50 else "#F24336"
    _wr_pct = max(0, min(100, win_rate_pct))

    # Verdict accuracy colors
    def _acc_clr(pct):
        return "#00D559" if pct >= 60 else "#F9C62B" if pct >= 50 else "#F24336" if pct > 0 else "#334155"

    # Top stat row — 4 big KPI tiles
    st.markdown(
        f'''<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">
  <div style="background:linear-gradient(135deg,#0f172a,#1a1f35);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:18px 16px;text-align:center;position:relative;overflow:hidden">
    <div style="position:absolute;top:-20px;left:-20px;width:80px;height:80px;background:radial-gradient(circle,rgba(129,140,248,0.15) 0%,transparent 70%)"></div>
    <div style="color:#818cf8;font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px">Total Bets</div>
    <div style="color:#f1f5f9;font-size:2rem;font-weight:900;line-height:1">{total}</div>
    <div style="color:#475569;font-size:0.65rem;margin-top:4px">{decided} resolved · {pending} pending</div>
  </div>
  <div style="background:linear-gradient(135deg,#0f172a,#0d2015);border:1px solid {_wr_clr}33;border-radius:14px;padding:18px 16px;text-align:center;position:relative;overflow:hidden">
    <div style="position:absolute;top:-20px;left:-20px;width:80px;height:80px;background:radial-gradient(circle,{_wr_clr}22 0%,transparent 70%)"></div>
    <div style="color:{_wr_clr};font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px">Win Rate</div>
    <div style="color:{_wr_clr};font-size:2rem;font-weight:900;line-height:1">{win_rate_pct:.1f}%</div>
    <div style="margin-top:8px;height:5px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden">
      <div style="width:{_wr_pct:.0f}%;height:100%;background:{_wr_clr};border-radius:3px;box-shadow:0 0 8px {_wr_clr}88"></div>
    </div>
    <div style="color:#475569;font-size:0.65rem;margin-top:4px">{wins}W · {losses}L</div>
  </div>
  <div style="background:linear-gradient(135deg,#0f172a,#1a1f35);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:18px 16px;text-align:center;position:relative;overflow:hidden">
    <div style="position:absolute;top:-20px;left:-20px;width:80px;height:80px;background:radial-gradient(circle,rgba(234,179,8,0.15) 0%,transparent 70%)"></div>
    <div style="color:#eab308;font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px">Pending</div>
    <div style="color:#f1f5f9;font-size:2rem;font-weight:900;line-height:1">{pending}</div>
    <div style="color:#475569;font-size:0.65rem;margin-top:4px">{total - pending} resolved</div>
  </div>
  <div style="background:linear-gradient(135deg,#0f172a,#1a1f35);border:1px solid {_streak_clr}33;border-radius:14px;padding:18px 16px;text-align:center;position:relative;overflow:hidden">
    <div style="position:absolute;top:-20px;left:-20px;width:80px;height:80px;background:radial-gradient(circle,{_streak_clr}22 0%,transparent 70%)"></div>
    <div style="color:{_streak_clr};font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px">Current Streak</div>
    <div style="color:{_streak_clr};font-size:1.3rem;font-weight:900;line-height:1">{_streak_label}</div>
  </div>
</div>''',
        unsafe_allow_html=True,
    )

    # Verdict accuracy row — 3 tiles (LOCK / SMASH / LEAN)
    _verdict_tiles_html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px">'
    for _vname, _vpct, _vclr, _vemoji in [
        ("LOCK",  lock_pct,  "#a855f7", "🔒"),
        ("SMASH", smash_pct, "#F24336", "🔥"),
        ("LEAN",  lean_pct,  "#00D559", "✅"),
    ]:
        _ac = _acc_clr(_vpct)
        _bar_w = min(_vpct, 100)
        _vclr_rgb = ",".join(str(int(_vclr.lstrip("#")[i:i+2], 16)) for i in (0, 2, 4))
        _verdict_tiles_html += (
            f'<div style="background:linear-gradient(135deg,#0f172a,rgba({_vclr_rgb},0.07));'
            f'border:1px solid {_vclr}33;border-radius:14px;padding:16px;text-align:center">'
            f'<div style="color:{_vclr};font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px">{_vemoji} {_vname} Accuracy</div>'
            f'<div style="color:{_ac};font-size:1.7rem;font-weight:900;line-height:1.1">{"—" if _vpct == 0 else f"{_vpct:.1f}%"}</div>'
            f'<div style="margin-top:8px;height:4px;background:rgba(255,255,255,0.06);border-radius:2px;overflow:hidden">'
            f'<div style="width:{_bar_w:.0f}%;height:100%;background:{_vclr};border-radius:2px;box-shadow:0 0 6px {_vclr}66"></div>'
            f'</div></div>'
        )
    _verdict_tiles_html += '</div>'
    st.markdown(_verdict_tiles_html, unsafe_allow_html=True)

    # SVG mini pie for LOCK vs SMASH vs LEAN (retained, placed inline below verdict row)
    _lock_pct_100 = max(0, min(100, lock_pct * 100)) if lock_pct <= 1 else lock_pct
    _smash_pct_100 = max(0, min(100, smash_pct * 100)) if smash_pct <= 1 else smash_pct
    _lean_pct_100 = max(0, min(100, lean_pct * 100)) if lean_pct <= 1 else lean_pct
    _pie_total = max(_lock_pct_100 + _smash_pct_100 + _lean_pct_100, 1)
    _pie_circ = 2 * math.pi * 28
    _lock_dash = _pie_circ * _lock_pct_100 / _pie_total
    _smash_dash = _pie_circ * _smash_pct_100 / _pie_total
    _lean_dash = _pie_circ * _lean_pct_100 / _pie_total
    _pie_svg = (
        f'<svg width="70" height="70" viewBox="0 0 70 70">'
        f'<circle cx="35" cy="35" r="28" fill="none" stroke="#1e293b" stroke-width="8"/>'
        f'<circle cx="35" cy="35" r="28" fill="none" stroke="#a855f7" stroke-width="8" '
        f'stroke-dasharray="{_lock_dash:.1f} {_pie_circ - _lock_dash:.1f}" '
        f'transform="rotate(-90 35 35)"/>'
        f'<circle cx="35" cy="35" r="28" fill="none" stroke="#F24336" stroke-width="8" '
        f'stroke-dasharray="{_smash_dash:.1f} {_pie_circ - _smash_dash:.1f}" '
        f'stroke-dashoffset="-{_lock_dash:.1f}" '
        f'transform="rotate(-90 35 35)"/>'
        f'<circle cx="35" cy="35" r="28" fill="none" stroke="#00D559" stroke-width="8" '
        f'stroke-dasharray="{_lean_dash:.1f} {_pie_circ - _lean_dash:.1f}" '
        f'stroke-dashoffset="-{_lock_dash + _smash_dash:.1f}" '
        f'transform="rotate(-90 35 35)"/>'
        f'</svg>'
    )
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#0f172a,#1a1f35);border:1px solid rgba(255,255,255,0.08);'
        f'border-radius:14px;padding:16px 20px;display:flex;align-items:center;gap:20px;flex-wrap:wrap">'
        f'<div style="flex-shrink:0">{_pie_svg}</div>'
        f'<div style="flex:1;min-width:160px">'
        f'<div style="color:#94a3b8;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Verdict Mix</div>'
        f'<div style="display:flex;flex-direction:column;gap:5px">'
        f'<div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:#a855f7;flex-shrink:0"></span><span style="color:#e2e8f0;font-size:0.8rem">LOCK</span><span style="color:#a855f7;font-size:0.8rem;font-weight:700;margin-left:auto">{_lock_pct_100:.0f}%</span></div>'
        f'<div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:#F24336;flex-shrink:0"></span><span style="color:#e2e8f0;font-size:0.8rem">SMASH</span><span style="color:#F24336;font-size:0.8rem;font-weight:700;margin-left:auto">{_smash_pct_100:.0f}%</span></div>'
        f'<div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:#00D559;flex-shrink:0"></span><span style="color:#e2e8f0;font-size:0.8rem">LEAN</span><span style="color:#00D559;font-size:0.8rem;font-weight:700;margin-left:auto">{_lean_pct_100:.0f}%</span></div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    # Override accuracy
    try:
        override_acc = joseph_get_override_accuracy()
        if isinstance(override_acc, dict) and override_acc.get("overrides_total", 0) > 0:
            _ov_acc = override_acc.get("override_accuracy", 0)
            _ov_ok = override_acc.get("overrides_correct", 0)
            _ov_total = override_acc.get("overrides_total", 0)
            _ov_clr = "#00D559" if _ov_acc >= 60 else "#F9C62B" if _ov_acc >= 50 else "#F24336"
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#0f172a,rgba(6,182,212,0.07));'
                f'border:1px solid rgba(6,182,212,0.25);border-radius:12px;padding:14px 18px;'
                f'display:flex;align-items:center;gap:14px;margin-top:12px">'
                f'<span style="font-size:1.4rem">🔄</span>'
                f'<div><div style="color:#06b6d4;font-size:0.68rem;font-weight:800;text-transform:uppercase;letter-spacing:1px">Override Accuracy</div>'
                f'<div style="color:{_ov_clr};font-size:1.3rem;font-weight:900">{_ov_acc:.1f}% '
                f'<span style="color:#64748b;font-size:0.75rem;font-weight:400">({_ov_ok}/{_ov_total} correct)</span></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    except Exception:
        pass


_render_track_record_section()

# ── Joseph's Bet History ─────────────────────────────────────
st.markdown(
    '<div id="joseph-s-bet-history" class="studio-section-title">📜 JOSEPH\'S BET HISTORY</div>',
    unsafe_allow_html=True,
)

_bets_loaded = False
if _BETS_AVAILABLE:
    try:
        from tracking.bet_tracker import load_all_bets as _load_all_bets
        all_bets = _load_all_bets()
        # Filter for Joseph's bets
        joseph_bets = [
            b for b in all_bets
            if b.get("source", "").lower() == "joseph"
            or "joseph" in b.get("notes", "").lower()
            or b.get("analyst", "").lower() == "joseph"
        ]
        _bets_loaded = True
    except ImportError:
        try:
            from tracking.database import load_all_bets as _load_all_bets
            all_bets = _load_all_bets()
            joseph_bets = [
                b for b in all_bets
                if b.get("source", "").lower() == "joseph"
                or "joseph" in b.get("notes", "").lower()
                or b.get("analyst", "").lower() == "joseph"
            ]
            _bets_loaded = True
        except ImportError:
            joseph_bets = []
    except Exception as exc:
        _logger.warning("Failed to load bet history: %s", exc)
        joseph_bets = []

if _bets_loaded and joseph_bets:
    for bet in joseph_bets[:100]:
        card_html = get_bet_card_html(bet)
        if card_html:
            # Enhancement 7: Append outcome badge to card
            _bet_result = str(bet.get("result", bet.get("outcome", "pending")))
            _badge_html = render_outcome_badge(_bet_result)
            st.markdown(card_html + f' {_badge_html}', unsafe_allow_html=True)
        else:
            player_name = _html.escape(str(bet.get("player", "Unknown")))
            stat = _html.escape(str(bet.get("stat_type", "")))
            direction = _html.escape(str(bet.get("direction", "")))
            result_val = str(bet.get("result", bet.get("outcome", "pending")))
            _badge_html = render_outcome_badge(result_val)
            st.markdown(
                f'<div class="joseph-segment">'
                f'<strong>{player_name}</strong> — {stat} {direction} '
                f'| {_badge_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
elif _bets_loaded:
    st.markdown(
        render_empty_state(
            "No bets logged by Joseph yet. Run analysis to start tracking!",
            cta_text="Run ⚡ Neural Analysis →",
            cta_page="/⚡_Quantum_Analysis_Matrix",
        ),
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        render_empty_state("Bet history module not available."),
        unsafe_allow_html=True,
    )


# ═════════════════════════════════════════════════════════════
# SIGN-OFF
# ═════════════════════════════════════════════════════════════
st.divider()
closer_text = "That's a WRAP, everybody."
catchphrase_text = ""
if _BRAIN_AVAILABLE:
    try:
        _used = set()
        c = _select_fragment(CLOSER_POOL, _used)
        closer_text = c.get("text", closer_text)
        cp = _select_fragment(CATCHPHRASE_POOL, _used)
        catchphrase_text = cp.get("text", "")
    except Exception:
        pass

signoff = _html.escape(closer_text)
if catchphrase_text:
    signoff += f' <em style="color:var(--studio-accent-secondary)">{_html.escape(catchphrase_text)}</em>'

st.markdown(
    f'<div style="text-align:center;margin:24px 0">'
    f'{_avatar_inline(64)}'
    f'<div style="color:var(--studio-accent);font-family:\'Inter\',sans-serif;'
    f'font-size:1rem;margin-top:12px">{signoff}</div>'
    f'<div style="color:var(--studio-muted);font-size:0.8rem;margin-top:4px">'
    f'— Joseph M. Smith, The Studio</div>'
    f'</div>',
    unsafe_allow_html=True,
)
