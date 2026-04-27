# ============================================================
# FILE: pages/0_💦_Live_Sweat.py
# PURPOSE: Live Sweat in-game dashboard.  Tracks locked pre-game
#          bets against real-time NBA box scores with auto-refresh,
#          glassmorphic cards, neon progress bars, and Joseph M.
#          Smith's live vibe-check reactions.
# DESIGN:  API Firewall (120 s cache) + streamlit-autorefresh
# ============================================================

import streamlit as st
import datetime
import html as _html_mod
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Page Configuration (MUST be first Streamlit call) ─────────

st.set_page_config(
    page_title="Live Sweat — SmartBetPro NBA",
    page_icon="💦",
    layout="wide",
)

# ── Global CSS ────────────────────────────────────────────────

from styles.theme import get_global_css
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Live Sweat CSS (glassmorphic cards + neon progress) ───────

from styles.live_theme import get_live_sweat_css
st.markdown(get_live_sweat_css(), unsafe_allow_html=True)

# ── Live Mode Avatar CSS (pulsing orange glow) ────────────────
try:
    from styles.live_theme import get_live_mode_avatar_css
    st.markdown(get_live_mode_avatar_css(), unsafe_allow_html=True)
except ImportError:
    pass

# ── Joseph M. Smith Floating Widget ──────────────────────────

try:
    from utils.components import inject_joseph_floating, render_joseph_hero_banner
    render_joseph_hero_banner()
    st.session_state["joseph_page_context"] = "page_live_sweat"
    inject_joseph_floating()
except ImportError:
    pass

# ── Auto-Refresh (silent 120 s reload) ───────────────────────

try:
    from streamlit_autorefresh import st_autorefresh
    _tick = st_autorefresh(interval=120_000, key="live_sweat_refresh")
except ImportError:
    _tick = 0

# ============================================================
# SECTION: Imports — Pacing Engine, Tracker, Persona
# ============================================================

from data.live_game_tracker import (
    get_live_boxscores,
    get_all_live_players,
    get_game_for_player,
    match_live_player,
)
from engine.live_math import calculate_live_pace, pace_color_tier, calculate_sweat_score
from styles.live_theme import (
    render_sweat_card, render_waiting_card,
    render_confetti_html, render_victory_lap,
    render_sweat_score_gauge, render_joseph_ticker_bar,
    render_danger_zone, render_sparkline_svg,
    render_quarter_breakdown, render_parlay_health,
    get_sound_alerts_js, get_keyboard_shortcuts_js,
)
from agent.live_persona import get_joseph_live_reaction, stream_joseph_text

# ── Pillar 4 Panic Room imports ──────────────────────────────

from agent.payload_builder import build_live_vibe_payload, get_grudge_buffer
from agent.response_parser import parse_vibe_response, generate_vibe_css_class, get_vibe_emoji
from styles.live_theme import get_panic_room_css, render_panic_room_card

# ── Resolve imports (same pipeline as Bet Tracker) ───────────
import threading as _threading

from tracking.bet_tracker import (
    load_all_bets as _ls_load_all_bets,
    resolve_todays_bets as _ls_resolve_todays,
    resolve_all_pending_bets as _ls_resolve_all_pending,
    auto_resolve_bet_results as _ls_auto_resolve,
)

# Inject Panic Room CSS
st.markdown(get_panic_room_css(), unsafe_allow_html=True)

# ── Keyboard Shortcuts (always active) ───────────────────────
st.markdown(get_keyboard_shortcuts_js(), unsafe_allow_html=True)

# ── Background Auto-Resolve on Page Load ─────────────────────
# Mirrors the Bet Tracker's _background_auto_resolve(): runs once per
# browser session in a daemon thread so the page renders immediately.

def _ls_background_auto_resolve():
    """Resolve past & finished-today bets in a background thread."""
    _msgs: list[str] = []
    try:
        _today_str = datetime.date.today().isoformat()
        _all_bets = _ls_load_all_bets(exclude_linked=False)

        # Resolve past pending bets (yesterday and older)
        _pending_old = [
            b for b in _all_bets
            if not b.get("result") and b.get("bet_date", "") < _today_str
        ]
        if _pending_old:
            _dates = sorted({b.get("bet_date", "") for b in _pending_old if b.get("bet_date")})
            _total = 0
            for _d in _dates:
                try:
                    _cnt, _ = _ls_auto_resolve(date_str=_d)
                    _total += _cnt
                except Exception:
                    pass
            if _total > 0:
                _msgs.append(f"🤖 Auto-resolved {_total} past bet(s).")

        # Resolve today's bets where games are Final
        try:
            _today_result = _ls_resolve_todays()
            if _today_result.get("resolved", 0) > 0:
                _msgs.append(
                    f"⚡ Auto-resolved {_today_result['resolved']} of today's bet(s) "
                    f"({_today_result['wins']}W / {_today_result['losses']}L)."
                )
        except Exception:
            pass
    except Exception:
        pass

    st.session_state["_ls_auto_resolve_messages"] = _msgs
    st.session_state["_ls_auto_resolve_done"] = True

if not st.session_state.get("_bet_tracker_auto_resolved", False) and not st.session_state.get("_ls_auto_resolved", False):
    st.session_state["_ls_auto_resolved"] = True
    st.session_state["_ls_auto_resolve_done"] = False
    _threading.Thread(target=_ls_background_auto_resolve, daemon=True).start()
    st.toast("🤖 Auto-resolving pending bets in the background…")

# Show deferred toast messages from background thread
if st.session_state.get("_ls_auto_resolve_done"):
    _ls_msgs = st.session_state.pop("_ls_auto_resolve_messages", [])
    if _ls_msgs:
        for _t in _ls_msgs:
            if _t.strip():
                st.toast(_t.strip())
    st.session_state.pop("_ls_auto_resolve_done", None)

# ============================================================
# SECTION: Header
# ============================================================

st.title("💦 Live Sweat Dashboard")
st.markdown(
    f"**{datetime.date.today().strftime('%A, %B %d, %Y')}** — "
    "Tracking your locked bets against real-time box scores.  "
    "Auto-refreshes every **2 minutes**."
)

with st.expander("📖 How to Use the Live Sweat Dashboard", expanded=False):
    st.markdown("""
### What This Page Does
The Live Sweat Dashboard monitors your **locked player prop bets** against
real-time NBA box-score data.  It calculates whether each player is
**on pace** to hit their line (OVER or UNDER) and surfaces Joseph M. Smith's
live vibe-check reactions so you know the emotional temperature of every bet.

### Selecting Your Bets
All your bets from every source are loaded automatically.  Use the
**Select Bets to Sweat** multiselect to pick exactly which bets you want
to track — you don't have to sweat them all at once.

### How Bets Get Here
Your bets are pulled automatically from **three sources** (all merged):
1. **Manual Locks** — props you locked on the Neural Analysis or Prop Scanner pages.
2. **Analysis Results** — the last Neural Analysis run stored in your session.
3. **Bet Tracker Database** — bets recorded through the 📈 Bet Tracker page.

If no bets appear, head to **📡 Live Games → ⚡ Quantum Analysis Matrix** and
lock some props first, or record a bet in the **📈 Bet Tracker**.

### Today's Scoreboard
The scoreboard at the top shows **live scores for all NBA games** today —
including games that haven't tipped off yet and games that are already final.

### Reading the Sweat Cards
| Element | Meaning |
|---------|---------|
| **Pace Bar** | Green = on pace to cash, Red = falling behind |
| **Projected Total** | Current stat total + pace × remaining minutes |
| **OVER / UNDER Badge** | Which direction you bet |
| **🔥 / 😰 Emoji** | Joseph's real-time vibe on this bet |
| **Awaiting Tip-Off** | Game hasn't started yet — card is greyed out |
| **OT Badge** | Game is in overtime — pace recalculated accordingly |

### Tips
- 💡 The dashboard **auto-refreshes every 2 minutes** — no need to manually reload.
- 💡 Pace projections are most reliable after the **first quarter** of play.
- 💡 UNDER bets flip the pace bar — green means the player is staying low.
- 💡 Use this page alongside the **📈 Bet Tracker** to log final results once games finish.
""")

st.divider()

# ============================================================
# SECTION: Resolve Active Bets
# We check three sources in priority order:
#   1. st.session_state["active_bets"] (manual locks)
#   2. st.session_state["analysis_results"] (Neural Analysis)
#   3. Database via load_all_bets (Bet Tracker)
# ============================================================

_STAT_MAP = {
    # ── Internal canonical keys ────────────────────────────────
    "points":               "pts",
    "rebounds":             "reb",
    "assists":              "ast",
    "steals":               "stl",
    "blocks":               "blk",
    "turnovers":            "tov",
    "threes":               "fg3m",
    "three_pointers":       "fg3m",
    "minutes":              "minutes",
    # ── Direct box-score keys ─────────────────────────────────
    "pts":                  "pts",
    "reb":                  "reb",
    "ast":                  "ast",
    "stl":                  "stl",
    "blk":                  "blk",
    "tov":                  "tov",
    "fg3m":                 "fg3m",
    "fg3a":                 "fg3a",
    "fgm":                  "fgm",
    "fga":                  "fga",
    "ftm":                  "ftm",
    "fta":                  "fta",
    "oreb":                 "oreb",
    "dreb":                 "dreb",
    "pf":                   "pf",
    "min":                  "minutes",
    # ── Platform name aliases ─────────────────────────────────
    "three pointers":       "fg3m",
    "3-pointers":           "fg3m",
    "3-point made":         "fg3m",
    "3-pointers made":      "fg3m",
    "three pointers made":  "fg3m",
    "3pm":                  "fg3m",
    "three_point":          "fg3m",
    "3-pt made":            "fg3m",
    "3-pt attempted":       "fg3a",
    "3pt attempted":        "fg3a",
    "three pointers attempted": "fg3a",
    "three_pointers_attempted": "fg3a",
    "3-pointers attempted": "fg3a",
    "free throws made":     "ftm",
    "fg attempted":         "fga",
    "field goals attempted": "fga",
    "fg made":              "fgm",
    "field goals made":     "fgm",
    "ft attempted":         "fta",
    "free throws attempted": "fta",
    "personal_fouls":       "pf",
    "personal fouls":       "pf",
    "offensive_rebounds":   "oreb",
    "offensive rebounds":   "oreb",
    "defensive_rebounds":   "dreb",
    "defensive rebounds":   "dreb",
    "blocked shots":        "blk",
    # ── Shorthand aliases ─────────────────────────────────────
    "rebs":                 "reb",
    "asts":                 "ast",
    "blks":                 "blk",
    "stls":                 "stl",
    "tovs":                 "tov",
}

_COMBO_STATS = {
    "points_rebounds":          ("pts", "reb"),
    "points_assists":           ("pts", "ast"),
    "rebounds_assists":         ("reb", "ast"),
    "points_rebounds_assists":  ("pts", "reb", "ast"),
    "blocks_steals":            ("blk", "stl"),
}

# Fantasy scoring formulas (mirroring data/platform_mappings.py)
_FANTASY_SCORING = {
    "fantasy_score_pp": {
        "pts": 1.0, "reb": 1.2, "ast": 1.5,
        "stl": 3.0, "blk": 3.0, "tov": -1.0,
    },
    "fantasy_score_dk": {
        "pts": 1.0, "reb": 1.25, "ast": 1.5,
        "stl": 2.0, "blk": 2.0, "tov": -0.5, "fg3m": 0.5,
    },
    "fantasy_score_ud": {
        "pts": 1.0, "reb": 1.2, "ast": 1.5,
        "stl": 3.0, "blk": 3.0, "tov": -1.0,
    },
}


def _resolve_current_stat(player_stats: dict, stat_type: str) -> float | None:
    """Extract the correct stat value from a player's live stats dict."""
    st_lower = str(stat_type).lower().strip()
    # Combo stats (PRA, P+R, etc.)
    if st_lower in _COMBO_STATS:
        return sum(player_stats.get(k, 0) for k in _COMBO_STATS[st_lower])
    # Fantasy score stats
    if st_lower in _FANTASY_SCORING:
        formula = _FANTASY_SCORING[st_lower]
        return round(
            sum(float(player_stats.get(k, 0)) * w for k, w in formula.items()),
            2,
        )
    # Simple stat lookup
    box_key = _STAT_MAP.get(st_lower)
    if box_key:
        return float(player_stats.get(box_key, 0))
    # Fallback: try normalize_stat_type from platform_mappings
    try:
        from data.platform_mappings import normalize_stat_type as _norm
        normalized = _norm(st_lower)
        if normalized and normalized != st_lower:
            # Non-recursive: look up directly in our maps to avoid cycles
            if normalized in _COMBO_STATS:
                return sum(player_stats.get(k, 0) for k in _COMBO_STATS[normalized])
            if normalized in _FANTASY_SCORING:
                formula = _FANTASY_SCORING[normalized]
                return round(
                    sum(float(player_stats.get(k, 0)) * w for k, w in formula.items()),
                    2,
                )
            box_key = _STAT_MAP.get(normalized)
            if box_key:
                return float(player_stats.get(box_key, 0))
    except ImportError:
        pass
    return None


def _get_active_bets() -> list[dict]:
    """
    Collect the user's active bets from **all** available sources.

    Merges bets from manual locks, Neural Analysis results, and the
    Bet Tracker database so the user can see every bet in one place
    and pick which ones to sweat.

    Each returned dict has at least:
        player_name, stat_type, line (float), direction, source
    """
    seen: set[tuple] = set()
    bets: list[dict] = []

    def _add(player: str, stat: str, line: float, direction: str,
             tier: str, source: str, team: str = "") -> None:
        key = (player.lower().strip(), stat.lower().strip(), line, direction.upper())
        if key in seen or not player:
            return
        seen.add(key)
        bets.append({
            "player_name": player,
            "stat_type":   stat,
            "line":        line,
            "direction":   direction,
            "tier":        tier,
            "source":      source,
            "team":        team.upper().strip(),
        })

    # Source 1: explicit active_bets in session state (manual locks)
    for b in st.session_state.get("active_bets", []):
        _add(
            b.get("player_name", ""), b.get("stat_type", ""),
            float(b.get("line", 0) or 0),
            str(b.get("direction", "OVER")),
            b.get("tier", ""), "Lock",
            b.get("player_team", b.get("team", "")),
        )

    # Source 2: analysis_results from Neural Analysis
    for r in st.session_state.get("analysis_results", []):
        if r.get("should_avoid"):
            continue
        _add(
            r.get("player_name", ""), r.get("stat_type", ""),
            float(r.get("line", 0) or 0),
            str(r.get("direction", "OVER")),
            r.get("tier", ""), "Analysis",
            r.get("player_team", r.get("team", "")),
        )

    # Source 3: database (today's pending bets)
    try:
        from tracking.bet_tracker import load_all_bets
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        all_db = load_all_bets(limit=200, exclude_linked=False)
        today_bets = [
            b for b in all_db
            if str(b.get("bet_date", "")).startswith(today_str)
            and str(b.get("result", "")).upper() not in ("WIN", "LOSS", "EVEN")
        ]
        for b in today_bets:
            _add(
                b.get("player_name", ""), b.get("stat_type", ""),
                float(b.get("prop_line", 0) or 0),
                str(b.get("direction", "OVER")),
                b.get("tier", ""), "Tracker",
                b.get("player_team", b.get("team", "")),
            )
    except Exception:
        pass

    return bets


# ============================================================
# SECTION: Load Live Data & Render Cards
# ============================================================

all_available_bets = _get_active_bets()

if not all_available_bets:
    st.info(
        "📌 **No active bets to track yet.**\n\n"
        "Run **⚡ Neural Analysis** to generate picks, or lock bets "
        "in the **📈 Bet Tracker**, then come back here to monitor them live."
    )
    st.stop()

# ── Bet Selector ──────────────────────────────────────────────
def _bet_label(b: dict) -> str:
    name = b.get("player_name", "Unknown")
    stat = str(b.get("stat_type", "")).replace("_", " ").title()
    line = b.get("line", 0)
    direction = str(b.get("direction", "OVER")).upper()
    source = b.get("source", "")
    source_tag = f" [{source}]" if source else ""
    return f"{name} — {stat} {direction} {line}{source_tag}"


# Build team → "AWAY @ HOME" matchup label from todays_games session state
def _build_team_game_map() -> dict[str, str]:
    result: dict[str, str] = {}
    for g in st.session_state.get("todays_games", []):
        away = str(g.get("away_team", g.get("away", g.get("visitor_team", "")))).upper().strip()
        home = str(g.get("home_team", g.get("home", ""))).upper().strip()
        if home and away:
            label = f"{away} @ {home}"
            result[home] = label
            result[away] = label
    return result

_team_game_map = _build_team_game_map()

def _bet_game_label(b: dict) -> str:
    team = str(b.get("team", "")).upper().strip()
    if not team:
        return ""
    return _team_game_map.get(team, team)

_bet_labels = [_bet_label(b) for b in all_available_bets]
_label_to_bet = dict(zip(_bet_labels, all_available_bets))
_all_game_labels = sorted({_bet_game_label(b) for b in all_available_bets if _bet_game_label(b)})

_ss_full = "sweat_full_selection"   # full selection across all games
_ss_view  = "sweat_bet_selector"    # multiselect view (game-scoped)

# Initialise full selection once (all bets active by default)
if _ss_full not in st.session_state:
    st.session_state[_ss_full] = set(_bet_labels)

# ── Compact filter row ────────────────────────────────────────
_gf_col, _cnt_col = st.columns([3, 2])
with _gf_col:
    _sel_game = st.selectbox(
        "Filter by game",
        options=["🏀 All Games"] + _all_game_labels,
        label_visibility="collapsed",
        key="sweat_game_filter",
    )
with _cnt_col:
    st.caption(f"🎯 **{len(st.session_state[_ss_full])} bets** active")

# Determine which labels are visible in the current game view
if _sel_game == "🏀 All Games" or not _all_game_labels:
    _visible_labels = _bet_labels
else:
    _visible_labels = [_bet_label(b) for b in all_available_bets if _bet_game_label(b) == _sel_game]

# ── Customise expander (collapsed by default) ─────────────────
_exp_title = (
    f"⚙️ Customize · {len(_visible_labels)} bets · {_sel_game}"
    if _sel_game != "🏀 All Games"
    else f"⚙️ Customize · {len(_bet_labels)} bets · all games"
)
with st.expander(_exp_title, expanded=False):
    _sa_col, _ca_col = st.columns(2)
    if _sa_col.button("✅ Select All", key="sweat_sel_all", use_container_width=True):
        st.session_state[_ss_full] |= set(_visible_labels)
        st.rerun()
    if _ca_col.button("❌ Clear All", key="sweat_clr_all", use_container_width=True):
        st.session_state[_ss_full] -= set(_visible_labels)
        st.rerun()

    # Set the multiselect value to current game's selection before rendering
    _default_view = [l for l in _visible_labels if l in st.session_state[_ss_full]]
    st.session_state[_ss_view] = _default_view

    _sel_view = st.multiselect(
        f"Showing {len(_visible_labels)} bets — type to search:",
        options=_visible_labels,
        key=_ss_view,
        placeholder="Type a player name to search...",
    )
    # Sync view selection back into the full selection set
    st.session_state[_ss_full] = (
        st.session_state[_ss_full] - set(_visible_labels)
    ) | set(_sel_view)

# Active labels = full selection (preserves choices across game filter switches)
selected_labels = [l for l in _bet_labels if l in st.session_state[_ss_full]]

active_bets = [_label_to_bet[lbl] for lbl in selected_labels if lbl in _label_to_bet]

if not active_bets:
    st.warning("⬆ Select at least one bet above to start sweating!")
    st.stop()

# Load live box scores (API-firewalled: cached 120 s)
try:
    live_games = get_live_boxscores()
    all_live_players = get_all_live_players(live_games)
except Exception as _live_fetch_err:
    _logger.error("Live Sweat: failed to fetch live box scores: %s", _live_fetch_err)
    st.error(
        "⚠️ Could not load live game data right now. "
        "This usually resolves itself within a minute — try refreshing."
    )
    live_games = []
    all_live_players = []

# ============================================================
# SECTION: Live Scoreboard — ESPN-Style Ticker with Leaders
# ============================================================

# Build a lookup from game_id → live game data (for leaders)
_live_game_map: dict[str, dict] = {}
for _lg in (live_games or []):
    _lgid = _lg.get("game_id", "")
    if _lgid:
        _live_game_map[_lgid] = _lg


def _get_all_todays_games() -> list[dict]:
    """Return all of today's games (live + scheduled + final).

    Uses the live box-scores already fetched and supplements with the
    ScoreboardV3 endpoint so that pre-tipoff and final games also
    appear.  Includes per-game leaders when box-score data is available.
    """
    seen_ids: set[str] = set()
    games: list[dict] = []

    # Include live games we already have
    for g in (live_games or []):
        gid = g.get("game_id", "")
        if gid:
            seen_ids.add(gid)
        games.append({
            "game_id":      gid,
            "home_team":    g.get("home_team", ""),
            "away_team":    g.get("away_team", ""),
            "home_score":   int(g.get("home_score", 0) or 0),
            "away_score":   int(g.get("away_score", 0) or 0),
            "status":       g.get("status", ""),
            "period":       g.get("period", ""),
            "home_players": g.get("home_players", []),
            "away_players": g.get("away_players", []),
        })

    # Supplement with ScoreboardV3 for pre-tipoff / final games
    try:
        from data.nba_data_service import get_todays_scoreboard
        sb = get_todays_scoreboard()
        if sb:
            game_headers = sb.get("game_header", [])
            line_scores = sb.get("line_score", [])
            score_map: dict[tuple, int] = {}
            for ls in line_scores:
                gid = ls.get("GAME_ID", "")
                abbr = ls.get("TEAM_ABBREVIATION", "")
                pts = ls.get("PTS")
                if gid and abbr:
                    score_map[(gid, abbr)] = int(pts) if pts is not None else 0

            for gh in game_headers:
                gid = gh.get("GAME_ID", "")
                if gid in seen_ids:
                    continue
                home_abbr = gh.get("HOME_TEAM_ABBREVIATION", "")
                away_abbr = gh.get("VISITOR_TEAM_ABBREVIATION", "")
                if not home_abbr or not away_abbr:
                    home_tid = gh.get("HOME_TEAM_ID", "")
                    vis_tid = gh.get("VISITOR_TEAM_ID", "")
                    for ls in line_scores:
                        if ls.get("GAME_ID") == gid:
                            if str(ls.get("TEAM_ID")) == str(home_tid):
                                home_abbr = ls.get("TEAM_ABBREVIATION", home_abbr)
                            elif str(ls.get("TEAM_ID")) == str(vis_tid):
                                away_abbr = ls.get("TEAM_ABBREVIATION", away_abbr)
                games.append({
                    "game_id":      gid,
                    "home_team":    home_abbr,
                    "away_team":    away_abbr,
                    "home_score":   score_map.get((gid, home_abbr), 0),
                    "away_score":   score_map.get((gid, away_abbr), 0),
                    "status":       str(gh.get("GAME_STATUS_TEXT", "")).strip(),
                    "period":       "",
                    "home_players": [],
                    "away_players": [],
                })
    except Exception:
        pass

    # Fallback: session state todays_games
    if not games:
        for g in st.session_state.get("todays_games", []):
            games.append({
                "game_id":      g.get("game_id", ""),
                "home_team":    g.get("home_team", ""),
                "away_team":    g.get("away_team", ""),
                "home_score":   0,
                "away_score":   0,
                "status":       g.get("game_time_et", "Scheduled"),
                "period":       "",
                "home_players": [],
                "away_players": [],
            })

    return games


def _game_leaders(players: list[dict]) -> dict:
    """Extract top scorer from a player list.

    Returns dict with keys: name, pts, reb, ast.
    """
    if not players:
        return {}
    top = max(players, key=lambda p: float(p.get("pts", 0) or 0))
    name = str(top.get("name", ""))
    # Use last name only for compact display
    parts = name.split()
    short = parts[-1] if parts else name
    first_initial = parts[0][0] + "." if len(parts) > 1 and parts[0] else ""
    return {
        "name": f"{first_initial} {short}".strip(),
        "pts":  int(float(top.get("pts", 0) or 0)),
        "reb":  int(float(top.get("reb", 0) or 0)),
        "ast":  int(float(top.get("ast", 0) or 0)),
    }


def _status_class_and_label(status_text: str) -> tuple[str, str]:
    """Return (css_class, label) for a game status string."""
    s = str(status_text).upper().strip()
    if "FINAL" in s:
        return "espn-status-final", "FINAL"
    if any(kw in s for kw in ("QTR", "HALF", "OT", "Q1", "Q2", "Q3", "Q4")):
        return "espn-status-live", status_text.strip()
    # Check for time patterns like "7:00 PM ET"
    if ":" in s and ("PM" in s or "AM" in s or "ET" in s):
        return "espn-status-sched", status_text.strip()
    if s:
        return "espn-status-sched", status_text.strip()
    return "espn-status-sched", "SCHEDULED"


scoreboard_games = _get_all_todays_games()

if scoreboard_games:
    _game_cards: list[str] = []
    _has_live = False

    for _tg in scoreboard_games:
        _t_away = _html_mod.escape(str(_tg.get("away_team", "?")))
        _t_home = _html_mod.escape(str(_tg.get("home_team", "?")))
        _t_a_pts = int(_tg.get("away_score", 0) or 0)
        _t_h_pts = int(_tg.get("home_score", 0) or 0)

        _status_cls, _status_lbl = _status_class_and_label(_tg.get("status", ""))
        if "live" in _status_cls:
            _has_live = True

        _a_cls = "espn-team-winning" if _t_a_pts > _t_h_pts else ("espn-team-losing" if _t_a_pts < _t_h_pts else "espn-team-winning")
        _h_cls = "espn-team-winning" if _t_h_pts > _t_a_pts else ("espn-team-losing" if _t_h_pts < _t_a_pts else "espn-team-winning")

        # Status line with live dot for active games
        _live_dot = '<span class="espn-ticker-live-dot"></span>' if "live" in _status_cls else ""
        _status_html = (
            f'<div class="espn-game-status {_status_cls}">'
            f'{_live_dot}{_html_mod.escape(_status_lbl)}</div>'
        )

        # Team rows
        _teams_html = (
            f'<div class="espn-team-row">'
            f'<span class="espn-team-abbr">{_t_away}</span>'
            f'<span class="espn-team-score {_a_cls}">{_t_a_pts}</span></div>'
            f'<div class="espn-team-row">'
            f'<span class="espn-team-abbr">{_t_home}</span>'
            f'<span class="espn-team-score {_h_cls}">{_t_h_pts}</span></div>'
        )

        # Leaders (from live box-score data)
        _leaders_html = ""
        _home_players = _tg.get("home_players", [])
        _away_players = _tg.get("away_players", [])
        _all_players = (_home_players or []) + (_away_players or [])
        _leader = _game_leaders(_all_players)
        if _leader:
            _l_name = _html_mod.escape(_leader["name"])
            _leaders_html = (
                f'<div class="espn-leaders">'
                f'<div class="espn-leader-row">'
                f'<span class="espn-leader-name">🏆 {_l_name}</span>'
                f'<span class="espn-leader-stat">'
                f'{_leader["pts"]} PTS  {_leader["reb"]} REB  {_leader["ast"]} AST</span>'
                f'</div></div>'
            )

        _game_cards.append(
            f'<div class="espn-game-card">'
            f'{_status_html}{_teams_html}{_leaders_html}</div>'
        )

    # Duplicate cards for seamless infinite scroll when there are
    # enough games to fill the viewport.
    _cards_html = ''.join(_game_cards)
    _n_games = len(scoreboard_games)
    _scroll_duration = max(15, _n_games * 5)  # 5s per game, min 15s

    # Only auto-scroll when there are 3+ games (otherwise static)
    if _n_games >= 3:
        _inner = (
            f'<div class="espn-ticker-scroll" '
            f'style="--scroll-duration:{_scroll_duration}s;">'
            f'{_cards_html}{_cards_html}</div>'  # duplicated for infinite loop
        )
    else:
        _inner = f'<div class="espn-ticker-track">{_cards_html}</div>'

    _header_text = "🔴 LIVE SCORES" if _has_live else "🏀 TODAY'S GAMES"
    _ticker_html = (
        f'<div class="espn-ticker-container">'
        f'<div class="espn-ticker-header">'
        f'{_header_text} — {datetime.date.today().strftime("%b %d, %Y")}</div>'
        f'<div class="espn-ticker-track">{_inner}</div>'
        f'</div>'
    )

    st.markdown(_ticker_html, unsafe_allow_html=True)
    st.divider()

# ── Live Heartbeat Indicator & Last Refresh ───────────────────

_now = datetime.datetime.now()
_refresh_col, _btn_col, _settings_col = st.columns([2, 1, 3])
with _refresh_col:
    st.markdown(
        f'<div class="live-heartbeat">'
        f'<span class="live-heartbeat-dot"></span>'
        f'<span style="font-size:0.82rem;color:rgba(255,255,255,0.55);">'
        f'LIVE · {_now.strftime("%I:%M:%S %p")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
with _btn_col:
    if st.button("🔄 Refresh Now", key="manual_refresh"):
        st.rerun()
with _settings_col:
    _sound_enabled = st.toggle("🔔 Sound Alerts", value=False, key="sweat_sound_toggle")

# Inject sound JS if enabled
st.markdown(get_sound_alerts_js(_sound_enabled), unsafe_allow_html=True)

if not live_games:
    st.warning(
        "📡 No live games in progress right now.  "
        "Cards will populate once tonight's games tip off."
    )

# ── Metrics Row ───────────────────────────────────────────────

cashed_count = 0
tracking_count = 0
risk_count = 0
waiting_count = 0

cards_html_parts: list[str] = []
waiting_html = ""
vibe_checks: list[tuple[str, dict]] = []  # (player_name, pace_result)
all_pace_results: list[dict] = []  # for sweat score
parlay_legs: list[dict] = []  # for parlay health

# ── Drama escalation tracking ────────────────────────────────
if "sweat_drama_counts" not in st.session_state:
    st.session_state["sweat_drama_counts"] = {}

# ── Emoji reactions state ────────────────────────────────────
if "sweat_reactions" not in st.session_state:
    st.session_state["sweat_reactions"] = {}

# ── Removed / locked-out bets ────────────────────────────────
if "sweat_removed_bets" not in st.session_state:
    st.session_state["sweat_removed_bets"] = set()

for bet in active_bets:
    player_name = bet.get("player_name", "")
    stat_type = bet.get("stat_type", "")
    target = float(bet.get("line", 0) or 0)
    direction = str(bet.get("direction", "OVER")).upper()

    if not player_name or target <= 0:
        continue

    # Check if bet was removed from session
    bet_key = f"{player_name}|{stat_type}|{target}|{direction}"
    if bet_key in st.session_state.get("sweat_removed_bets", set()):
        continue

    # Fuzzy-match the player in the live box score
    matched = match_live_player(player_name, all_live_players)
    if matched is None:
        # Player not found in live data — show awaiting card
        waiting_count += 1
        waiting_html += render_waiting_card(
            player_name=player_name,
            stat_type=stat_type,
            target_stat=target,
            direction=direction,
        )
        continue

    tracking_count += 1

    # Get the game context for blowout detection
    game = get_game_for_player(player_name, live_games)
    score_diff = 0.0
    period = ""
    if game:
        score_diff = abs(game.get("home_score", 0) - game.get("away_score", 0))
        period = game.get("period", "")

    current_stat_val = _resolve_current_stat(matched, stat_type)
    if current_stat_val is None:
        continue

    # Run the pacing engine
    pace = calculate_live_pace(
        current_stat=current_stat_val,
        minutes_played=matched.get("minutes", 0),
        target_stat=target,
        live_score_diff=score_diff,
        current_fouls=matched.get("fouls", 0),
        period=period,
        direction=direction,
    )

    color = pace_color_tier(pace["pct_of_target"], direction)
    all_pace_results.append(pace)

    if pace["cashed"]:
        cashed_count += 1
    if pace["blowout_risk"] or pace["foul_trouble"]:
        risk_count += 1

    # ── Drama escalation tracking ────────────────────────────
    drama_key = f"{player_name}_{stat_type}"
    drama_counts = st.session_state.get("sweat_drama_counts", {})
    pct = pace.get("pct_of_target", 0)
    if 85 <= pct <= 99 and not pace["cashed"]:
        drama_counts[drama_key] = drama_counts.get(drama_key, 0) + 1
    else:
        drama_counts[drama_key] = 0
    st.session_state["sweat_drama_counts"] = drama_counts
    drama_level = drama_counts.get(drama_key, 0)

    # ── Quarter values for sparkline (simulated from pace) ───
    period_num = pace.get("period_num", 0)
    quarter_values: list[float] = []
    if period_num >= 1 and pace["current_stat"] > 0:
        per_q = pace["current_stat"] / max(1, min(period_num, 4))
        quarter_values = [round(per_q * (i + 1), 1) for i in range(min(period_num, 4))]

    # ── Projected Q4 stat ────────────────────────────────────
    projected_q4 = 0.0
    if period_num < 4 and pace["pace_per_minute"] > 0:
        projected_q4 = pace["pace_per_minute"] * 12  # 12 min quarter

    # Parlay tracking
    parlay_legs.append({
        "player_name": player_name,
        "stat_type": stat_type,
        "pct_of_target": pace["pct_of_target"],
        "on_pace": pace["on_pace"],
        "cashed": pace["cashed"],
    })

    # Render card
    cards_html_parts.append(render_sweat_card(
        player_name=player_name,
        stat_type=stat_type,
        current_stat=pace["current_stat"],
        target_stat=pace["target_stat"],
        projected_final=pace["projected_final"],
        pct_of_target=pace["pct_of_target"],
        color_tier=color,
        blowout_risk=pace["blowout_risk"],
        foul_trouble=pace["foul_trouble"],
        cashed=pace["cashed"],
        minutes_played=pace["minutes_played"],
        direction=direction,
        minutes_remaining=pace["minutes_remaining"],
        is_overtime=pace["is_overtime"],
        quarter_values=quarter_values if quarter_values else None,
        est_total_minutes=pace.get("est_total_minutes", 0),
        drama_level=drama_level,
    ))

    vibe_checks.append((player_name, pace))

cards_html = "".join(cards_html_parts)

# ── Sticky Top-Level Metrics ──────────────────────────────────

st.markdown('<div class="sticky-metrics-bar">', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🎯 Active Bets", len(active_bets))
c2.metric("📡 Tracking Live", tracking_count)
c3.metric("✅ Cashed", cashed_count)
c4.metric("🚨 At Risk", risk_count)
c5.metric("🕐 Awaiting", waiting_count)
st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# ── Sweat Score Gauge ─────────────────────────────────────────

if all_pace_results:
    sweat_score = calculate_sweat_score(all_pace_results)
    st.markdown(render_sweat_score_gauge(sweat_score), unsafe_allow_html=True)

# ── Confetti + Victory Lap for cashed bets ────────────────────

if cashed_count > 0:
    # Gold confetti cannon replaces st.balloons()
    st.markdown(render_confetti_html(), unsafe_allow_html=True)
    # Play cash sound if sound alerts are enabled
    if _sound_enabled:
        st.markdown(
            '<script>if(window._cashSound) window._cashSound();</script>',
            unsafe_allow_html=True,
        )
    # Victory lap for first cash (show once per session per count)
    _prev_cashed = st.session_state.get("_prev_cashed_count", 0)
    if cashed_count > _prev_cashed:
        from agent.live_persona import _CASHED_BRAGS
        import random as _rnd_victory
        victory_quote = _rnd_victory.choice(_CASHED_BRAGS)
        st.markdown(render_victory_lap(victory_quote), unsafe_allow_html=True)
    st.session_state["_prev_cashed_count"] = cashed_count

# ── Render all sweat cards (Grid Layout) ──────────────────────

if cards_html:
    st.markdown(f'<div class="sweat-cards-grid">{cards_html}</div>', unsafe_allow_html=True)

    # Build lookup for bet details by player name (O(1) access)
    _bet_by_player: dict[str, dict] = {}
    for b in active_bets:
        _bet_by_player.setdefault(b.get("player_name", ""), b)

    # ── Tap-to-Expand Card Details + Emoji Reactions ──────────
    for i, (player_name, pace) in enumerate(vibe_checks):
        bet_key = f"{player_name}|{pace.get('target_stat', 0)}"
        col_card, col_remove = st.columns([10, 1])
        with col_remove:
            if st.button("❌", key=f"remove_{i}", help="Remove from sweat"):
                bet_info = _bet_by_player.get(player_name, {})
                stat_t = bet_info.get("stat_type", "")
                rm_key = f"{player_name}|{stat_t}|{pace.get('target_stat', 0)}|{pace.get('direction', 'OVER')}"
                st.session_state.setdefault("sweat_removed_bets", set()).add(rm_key)
                st.rerun()
        with col_card:
            with st.expander(f"📊 {player_name} — Details", expanded=pace.get("cashed", False)):
                # Per-quarter pace breakdown
                period_num = pace.get("period_num", 0)
                if period_num >= 1 and pace["current_stat"] > 0:
                    per_q = pace["current_stat"] / max(1, min(period_num, 4))
                    q_vals = [round(per_q * (i + 1), 1) for i in range(min(period_num, 4))]
                    proj_q4 = pace["pace_per_minute"] * 12 if period_num < 4 else 0
                    st.markdown(render_quarter_breakdown(q_vals, proj_q4), unsafe_allow_html=True)

                # Minutes share
                est_min = pace.get("est_total_minutes", 0)
                if est_min > 0:
                    st.caption(
                        f"⏱️ Minutes: {pace['minutes_played']:.0f} played / "
                        f"{est_min:.0f} projected total"
                    )

                # Danger zone timeline (within 10% of target)
                dist = pace.get("distance", 0)
                target_val = pace.get("target_stat", 1)
                if 0 < dist <= target_val * 0.10 and not pace["cashed"]:
                    bet_info = _bet_by_player.get(player_name, {})
                    stat_t = bet_info.get("stat_type", "")
                    st.markdown(
                        render_danger_zone(dist, pace["minutes_remaining"], stat_t),
                        unsafe_allow_html=True,
                    )

                # Pace details
                st.caption(
                    f"Pace: **{pace['pace_per_minute']:.2f}** per min · "
                    f"Projected: **{pace['projected_final']:.1f}** · "
                    f"Target: **{pace['target_stat']:.1f}**"
                )

        # Emoji reactions
        rxn_key = f"rxn_{player_name}"
        current_rxns = st.session_state.get("sweat_reactions", {}).get(rxn_key, {})
        rxn_cols = st.columns(8)
        for j, emoji in enumerate(["🔥", "😰", "💀", "🙏", "💰", "😤", "🎯", "👑"]):
            count = current_rxns.get(emoji, 0)
            with rxn_cols[j]:
                if st.button(
                    f"{emoji} {count}" if count else emoji,
                    key=f"rxn_{i}_{j}",
                ):
                    rxns = st.session_state.setdefault("sweat_reactions", {})
                    rxns.setdefault(rxn_key, {})[emoji] = count + 1

elif live_games:
    st.info(
        "📊 No matching box-score data found for your active bets yet. "
        "Stats appear once games tip off and players check in."
    )

# ── "Lock More" Quick Link ────────────────────────────────────

st.markdown(
    '<div style="text-align:center;margin:12px 0;">'
    '<a href="/Prop_Scanner" target="_self" '
    'style="color:#00f0ff;text-decoration:none;font-weight:700;">'
    '🔒 Lock More Bets → Prop Scanner</a>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Resolve All Bets ──────────────────────────────────────────
# Same pipeline the Bet Tracker uses — lets users resolve without
# navigating away from Live Sweat.

st.divider()
_ls_r1, _ls_r2 = st.columns([1, 1])
with _ls_r1:
    _ls_resolve_today_btn = st.button(
        "⚡ Resolve Today's Bets",
        help="Check final scores and resolve today's finished bets.",
        key="ls_resolve_today",
    )
with _ls_r2:
    _ls_resolve_all_btn = st.button(
        "🔄 Resolve All Pending Bets",
        type="primary",
        help="Resolve every unresolved bet from any date.",
        key="ls_resolve_all",
    )

if _ls_resolve_today_btn:
    with st.spinner("Resolving today's bets…"):
        try:
            _ls_tr = _ls_resolve_todays()
            _ls_resolved = _ls_tr.get("resolved", 0)
            if _ls_resolved > 0:
                st.success(
                    f"✅ Resolved **{_ls_resolved}** bet(s) — "
                    f"{_ls_tr.get('wins', 0)}W / {_ls_tr.get('losses', 0)}L / "
                    f"{_ls_tr.get('pushes', 0)} Push"
                )
                st.rerun()
            else:
                _ls_pend = _ls_tr.get("pending", 0)
                if _ls_pend > 0:
                    st.info(f"No games final yet — **{_ls_pend}** bet(s) still pending.")
                else:
                    st.info("No pending bets found for today.")
            if _ls_tr.get("errors"):
                with st.expander(f"⚠️ {len(_ls_tr['errors'])} error(s)"):
                    for _e in _ls_tr["errors"]:
                        st.markdown(f"- {_e}")
        except Exception as _exc:
            st.error(f"Resolve failed: {_exc}")

if _ls_resolve_all_btn:
    with st.spinner("Resolving all pending bets — this may take a moment…"):
        try:
            _ls_ar = _ls_resolve_all_pending()
            _ls_ar_resolved = _ls_ar.get("resolved", 0)
            if _ls_ar_resolved > 0:
                st.success(
                    f"✅ Resolved **{_ls_ar_resolved}** bet(s) — "
                    f"{_ls_ar.get('wins', 0)}W / {_ls_ar.get('losses', 0)}L / "
                    f"{_ls_ar.get('pushes', 0)} Push"
                )
                _ls_by_date = _ls_ar.get("by_date", {})
                if _ls_by_date:
                    for _d, _cnt in sorted(_ls_by_date.items()):
                        st.markdown(f"  • **{_d}**: {_cnt} resolved")
                st.rerun()
            else:
                st.info("No pending bets found to resolve, or all bets are already resolved.")
            if _ls_ar.get("errors"):
                with st.expander(f"⚠️ {len(_ls_ar['errors'])} error(s)"):
                    for _e in _ls_ar["errors"]:
                        st.markdown(f"- {_e}")
        except Exception as _exc:
            st.error(f"Resolve failed: {_exc}")

# ── Parlay Health Rollup ──────────────────────────────────────

if len(parlay_legs) >= 2:
    st.markdown(render_parlay_health(parlay_legs), unsafe_allow_html=True)

# ── Render awaiting tip-off cards ─────────────────────────────

if waiting_html:
    st.markdown(
        '<div style="margin-top:8px;">'
        '<div class="sweat-stat-label" style="margin-bottom:6px;">🕐 Awaiting Tip-Off</div>'
        f'{waiting_html}</div>',
        unsafe_allow_html=True,
    )

# ============================================================
# SECTION: Joseph's Live Vibe Checks (Pillar 4 Panic Room)
# ============================================================

if vibe_checks:
    st.divider()
    st.subheader("🎙️ Joseph's Live Panic Room")

    grudge = get_grudge_buffer()

    # ── Collect all headlines for the ticker bar ──────────────
    _STATE_HEADLINES = {
        "THE_HOOK":             "DYING ON THE HOOK!",
        "FREE_THROW_MERCHANT":  "FREE THROW MERCHANT!",
        "BENCH_SWEAT":          "BENCH SWEAT ALERT!",
        "USAGE_FREEZE_OUT":     "GIVE HIM THE BALL!",
        "GARBAGE_TIME_MIRACLE": "GARBAGE TIME MIRACLE!",
        "LOCKER_ROOM_TRAGEDY":  "INJURY SCARE!",
        "THE_REF_SHOW":         "BLAME THE REFS!",
        "THE_CLEAN_CASH":       "CASHED IT!",
    }

    all_headlines: list[str] = []
    panic_cards_html = ""

    # ── Find "Bet of the Night" — best pace closest to cash ──
    _best_bon_idx = -1
    _best_bon_pct = 0.0
    for _bi, (_bn, _bp) in enumerate(vibe_checks):
        if not _bp.get("cashed") and _bp.get("on_pace"):
            if _bp.get("pct_of_target", 0) > _best_bon_pct:
                _best_bon_pct = _bp["pct_of_target"]
                _best_bon_idx = _bi

    for _vi, (player_name, pace) in enumerate(vibe_checks):
        # Fast-path fragment reaction (always available offline)
        reaction = get_joseph_live_reaction(pace)

        # Build the Pillar 4 structured payload for this bet
        bet_for_payload = next(
            (b for b in active_bets
             if b.get("player_name", "") == player_name),
            {"player_name": player_name, "stat_type": "",
             "line": pace.get("target_stat", 0),
             "direction": pace.get("direction", "OVER")},
        )
        game = get_game_for_player(player_name, live_games)
        matched = match_live_player(player_name, all_live_players)

        payload = build_live_vibe_payload(
            ticket=bet_for_payload,
            live_stats=matched or {},
            game_context=game or {},
            grudge_buffer=grudge,
            pace_result=pace,
        )

        game_state = payload.get("game_state", "")

        # Map game state to a vibe status for the card glow
        from agent.response_parser import _STATE_TO_DEFAULT_VIBE
        vibe_status = _STATE_TO_DEFAULT_VIBE.get(game_state, "Sweating")

        headline = _STATE_HEADLINES.get(game_state, "JOSEPH IS SWEATING!")
        all_headlines.append(f"{player_name}: {headline}")

        # Render the panic room card
        panic_cards_html += render_panic_room_card(
            vibe_status=vibe_status,
            ticker_headline=headline,
            joseph_rant=reaction,
            player_name=player_name,
            game_state=game_state,
        )

        # Push reaction into grudge buffer for anti-repetition
        grudge.add(reaction)

    # ── Joseph's Animated Avatar ─────────────────────────────
    # Determine overall vibe for avatar expression
    _cashed_any = any(p.get("cashed") for _, p in vibe_checks)
    _panic_any = any(
        p.get("blowout_risk") or p.get("foul_trouble") for _, p in vibe_checks
    )
    if _cashed_any:
        _avatar_cls = "joseph-avatar-victory"
        _avatar_emoji = "😎"
    elif _panic_any:
        _avatar_cls = "joseph-avatar-panic"
        _avatar_emoji = "😱"
    else:
        _avatar_cls = ""
        _avatar_emoji = "🎙️"

    st.markdown(
        f'<div class="joseph-avatar-container">'
        f'<span style="font-size:2rem;" class="{_avatar_cls}">{_avatar_emoji}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Scrolling Ticker Tape with all headlines ─────────────
    if all_headlines:
        st.markdown(render_joseph_ticker_bar(all_headlines), unsafe_allow_html=True)

    # ── Bet of the Night highlight ───────────────────────────
    if _best_bon_idx >= 0:
        _bon_name, _bon_pace = vibe_checks[_best_bon_idx]
        st.markdown(
            f'<div style="text-align:center;margin:8px 0;">'
            f'<span style="background:linear-gradient(135deg,#eab308,#f59e0b);'
            f'color:#1a1a2e;padding:4px 14px;border-radius:6px;'
            f'font-size:0.85rem;font-weight:800;">🏆 BET OF THE NIGHT: '
            f'{_html_mod.escape(_bon_name)} — '
            f'{_bon_pace["pct_of_target"]:.0f}% of target</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Render all panic room cards
    if panic_cards_html:
        st.markdown(panic_cards_html, unsafe_allow_html=True)

    # Still offer the streaming text in expanders for detail
    st.markdown(
        '<div class="sweat-stat-label" style="margin-top:12px;margin-bottom:4px;">'
        '📜 Detailed Reactions</div>',
        unsafe_allow_html=True,
    )
    for player_name, pace in vibe_checks:
        reaction = get_joseph_live_reaction(pace)
        with st.expander(f"🎙️ {player_name}", expanded=pace.get("cashed", False)):
            try:
                st.write_stream(stream_joseph_text(reaction))
            except Exception:
                # Fallback when WebSocket closes mid-stream (e.g. auto-refresh)
                st.write(reaction)
