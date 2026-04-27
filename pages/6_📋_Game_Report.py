# ============================================================
# FILE: pages/4_📋_Game_Report.py
# PURPOSE: Generate a comprehensive QDS-styled game betting
#          report using SmartBetPro's AI analysis results.
# DESIGN:  Quantum Design System (QDS) — dark futuristic theme
#          with collapsible sections, animated confidence bars,
#          SAFE Score™ prop cards, team analysis, and entry
#          strategy matrix (matching reference QDS HTML spec).
# USAGE:   Load games + run Neural Analysis first, then visit
#          this page to generate a report for any matchup.
# ============================================================

import streamlit as st
# st.html(unsafe_allow_javascript=True) is required so DOMPurify preserves <style> tags
import datetime
import html
import time

from styles.theme import (
    get_global_css,
    get_game_report_html,
    get_qds_css,
    get_qds_strategy_table_html,
    get_team_colors,
)
from engine import is_unbettable_line

from pages.helpers.game_report_helpers import (
    get_matchup_card_html,
    get_summary_dashboard_html,
    get_h2h_bars_html,
    get_parlay_card_html,
    get_builder_prop_card_html,
    get_narrative_card_html,
)

# Import the new state-of-the-art game prediction engine
try:
    from engine.game_prediction import predict_game_from_abbrevs as _engine_predict_game
    _GAME_PREDICTION_ENGINE_AVAILABLE = True
except ImportError:
    _GAME_PREDICTION_ENGINE_AVAILABLE = False

# ============================================================
# SECTION: Page Configuration
# ============================================================

st.set_page_config(
    page_title="Game Report — SmartBetPro NBA",
    page_icon="📋",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Game Report")
from utils.seo import inject_page_seo
inject_page_seo("Game Report")

# ── Tier Gate ─────────────────────────────────────────────────
from utils.tier_gate import require_tier
if not require_tier():
    st.stop()

st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_qds_css(), unsafe_allow_html=True)

# ── Reduce excessive bottom padding / blank space ─────────────
st.markdown(
    '<style>.main .block-container{padding-bottom:1rem !important}</style>',
    unsafe_allow_html=True,
)

# ── Joseph M. Smith Hero Banner & Floating Widget ─────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating, render_sidebar_auth
st.session_state["joseph_page_context"] = "page_game_report"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()

# ── Premium Gate ───────────────────────────────────────────────
from utils.premium_gate import premium_gate
if not premium_gate("Game Report"):
    st.stop()
# ── End Premium Gate ───────────────────────────────────────────


# ============================================================
# SECTION: Data Loading
# ============================================================

todays_games     = st.session_state.get("todays_games",     [])
analysis_results = st.session_state.get("analysis_results", [])

# Fallback: load today's pre-computed picks from DB when session is empty
# (e.g. user navigates directly to this page without visiting Home first)
if not analysis_results:
    try:
        from tracking.database import get_slate_picks_for_today as _gr_gsp
        _gr_picks = _gr_gsp()
        if _gr_picks:
            analysis_results = _gr_picks
            st.session_state["analysis_results"] = _gr_picks
    except Exception:
        pass

# Load team stats for game predictions (pace, ortg, drtg)
try:
    from data.data_manager import load_teams_data as _load_teams
    _teams_list = _load_teams()
    TEAMS_DATA = {t.get("abbreviation", "").upper(): t for t in _teams_list if t.get("abbreviation")}
except Exception:
    TEAMS_DATA = {}

_LEAGUE_AVG_DRTG = 113.0  # typical NBA league-average defensive rating

# Load sample player data for key-player matchup display
try:
    from data.data_manager import load_players_data as _load_players
    _players_raw = _load_players()
    # Build {team_abbrev_upper: [player_dict, ...]} for fast lookup
    PLAYERS_BY_TEAM: dict = {}
    for _p in _players_raw:
        _t = _p.get("team", "").upper().strip()
        if _t:
            PLAYERS_BY_TEAM.setdefault(_t, []).append(_p)
except Exception:
    PLAYERS_BY_TEAM = {}

# ── Build expanded team alias set for stale-result filtering ──────
# Covers common NBA abbreviation variants (e.g. "GS" ↔ "GSW", "NY" ↔ "NYK").
_ABBREV_ALIASES = {
    "GS": "GSW", "GSW": "GS",
    "NY": "NYK", "NYK": "NY",
    "NO": "NOP", "NOP": "NO",
    "SA": "SAS", "SAS": "SA",
    "UTAH": "UTA", "UTA": "UTAH",
    "WSH": "WAS", "WAS": "WSH",
    "BKN": "BRK", "BRK": "BKN",
    "PHX": "PHO", "PHO": "PHX",
    "CHA": "CHO", "CHO": "CHA",
}

def _expand_teams(abbrevs: set) -> set:
    """Return abbrevs expanded with all known alias variants."""
    expanded = set(abbrevs)
    for a in list(abbrevs):
        alias = _ABBREV_ALIASES.get(a)
        if alias:
            expanded.add(alias)
    return expanded

# ── Backfill empty player_team from player database or opponent/game data ──
# Props from some sources (Odds API, etc.) don't include the player's team.
# The analysis orchestrator may inherit the empty team. Resolve it here so
# per-game filtering works correctly.
if analysis_results:
    # Build player → team lookup from loaded player data
    _player_team_lookup: dict = {}
    for _p in (_players_raw if '_players_raw' in dir() else []):
        _pn = _p.get("name", "").strip()
        _pt = _p.get("team", "").strip()
        if _pn and _pt:
            _player_team_lookup[_pn.lower()] = _pt.upper()

    # Also build opponent → team reverse lookup from game data
    _team_opponent_map: dict = {}  # {team_upper: opponent_upper}
    for _game in todays_games:
        _ht = _game.get("home_team", "").upper().strip()
        _at = _game.get("away_team", "").upper().strip()
        if _ht and _at:
            _team_opponent_map[_ht] = _at
            _team_opponent_map[_at] = _ht

    _backfilled = 0
    for _r in analysis_results:
        _rt = (_r.get("player_team") or _r.get("team") or "").strip()
        if not _rt:
            # Try 1: look up player name in player database
            _rn = (_r.get("player_name") or "").strip().lower()
            if _rn and _rn in _player_team_lookup:
                _resolved = _player_team_lookup[_rn]
                _r["player_team"] = _resolved
                _r["team"] = _resolved
                _backfilled += 1
                continue
            # Try 2: derive from opponent field + game data
            _opp = (_r.get("opponent") or "").upper().strip()
            if _opp and _opp in _team_opponent_map:
                _resolved = _team_opponent_map[_opp]
                _r["player_team"] = _resolved
                _r["team"] = _resolved
                _backfilled += 1
    if _backfilled > 0:
        import logging as _logging
        _logging.getLogger(__name__).info(
            "Game Report: backfilled team for %d result(s) with empty player_team.",
            _backfilled,
        )

# ── Filter out stale results not matching tonight's teams ──────
# If the user ran analysis yesterday and didn't clear session state,
# results for teams not playing tonight are silently removed here
# rather than polluting the report with stale data.
# Uses case-insensitive, stripped fuzzy team matching + alias expansion.
if todays_games and analysis_results:
    playing_teams = set()
    for _game in todays_games:
        ht = _game.get("home_team", "").upper().strip()
        at = _game.get("away_team", "").upper().strip()
        if ht:
            playing_teams.add(ht)
        if at:
            playing_teams.add(at)
    playing_teams.discard("")
    playing_teams = _expand_teams(playing_teams)

    if playing_teams:
        _valid = [
            r for r in analysis_results
            if (
                r.get("player_team", r.get("team", "")).upper().strip() in playing_teams
                or r.get("opponent", "").upper().strip() in playing_teams
                or not r.get("player_team", r.get("team", "")).strip()
            )
        ]
        _stale_count = len(analysis_results) - len(_valid)
        if _stale_count > 0:
            st.warning(
                f"⚠️ Filtered out {_stale_count} stale result(s) from a previous "
                "session (players not on tonight's teams)."
            )
        analysis_results = _valid

# ── Freshness check — warn if results are older than 6 hours ──
_analysis_ts = st.session_state.get("analysis_timestamp")
if _analysis_ts and analysis_results:
    try:
        if isinstance(_analysis_ts, str):
            _analysis_ts = datetime.datetime.fromisoformat(_analysis_ts)
        _age_hours = (datetime.datetime.now() - _analysis_ts).total_seconds() / 3600
        if _age_hours > 6:
            st.warning(
                f"⚠️ Analysis results are {_age_hours:.0f} hour(s) old. "
                "Re-run **⚡ Neural Analysis** for fresh data."
            )
    except (TypeError, ValueError):
        pass

# ============================================================
# END SECTION: Data Loading
# ============================================================


# ============================================================
# SECTION: Page Header
# ============================================================

st.title("📋 Game Report")
st.markdown(
    "AI-powered prop betting report with **SAFE Score™** analysis — "
    "collapsible sections, confidence bars, and entry strategy matrix."
)

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Game Report — AI-Powered Analysis
    
    The Game Report provides a **comprehensive breakdown** of any selected game using the SAFE Score™ system.
    
    **How to Generate a Report**
    1. Run analysis on the **⚡ Quantum Analysis Matrix** page first
    2. Select a game from the dropdown to view its full report
    3. Expand sections to see detailed player-by-player breakdowns
    
    **What You'll See**
    - **SAFE Score™**: Our composite confidence metric (0-100) combining probability, edge, and risk
    - **Confidence Bars**: Visual indicator of how confident the model is in each pick
    - **Entry Strategy Matrix**: Suggested parlay combinations ranked by expected value
    - **Force Analysis**: Directional factors pushing a prop OVER or UNDER
    
    💡 **Pro Tips:**
    - Focus on picks with SAFE Scores above 65 (Gold tier and above)
    - The Entry Strategy Matrix suggests which picks combine well in parlays
    - Use the force analysis to understand WHY the model likes a pick, not just that it does
    """)

st.divider()

# ============================================================
# END SECTION: Page Header
# ============================================================


# ============================================================
# SECTION: Matchup Selector
# ============================================================

selected_game = None

if todays_games:
    col_sel, col_meta = st.columns([2, 1])

    with col_sel:
        game_labels = [
            f"{g.get('away_team','?')} @ {g.get('home_team','?')}"
            for g in todays_games
        ]
        options = ["— All games tonight —"] + game_labels
        sel_idx = st.selectbox(
            "🏟️ Select Matchup",
            range(len(options)),
            format_func=lambda i: options[i],
            index=0,
            help="Filter to a specific game, or show all games tonight.",
        )
        if sel_idx > 0:
            selected_game = todays_games[sel_idx - 1]

    with col_meta:
        n_props   = len(analysis_results)
        n_picks   = len([r for r in analysis_results if r.get("confidence_score", 0) >= 70])
        avg_safe  = (
            sum(r.get("confidence_score", 0) for r in analysis_results) / max(n_props, 1)
        ) if n_props else 0.0
        # Best pick tonight
        _best = max(analysis_results, key=lambda r: r.get("confidence_score", 0), default=None) if analysis_results else None
        _best_label = (
            f"{_best.get('player_name', '?')} · {_best.get('stat_type', '').title()}"
            if _best else "—"
        )
        st.markdown(
            get_summary_dashboard_html(n_props, n_picks, avg_safe, _best_label),
            unsafe_allow_html=True,
        )

    if not analysis_results:
        st.info(
            "💡 Games loaded. Run **⚡ Neural Analysis** to add prop predictions to each report — "
            "team stats and game predictions are shown below for all matchups."
        )

elif not todays_games and analysis_results:
    if st.button("📋 Generate Full Report for All Props", use_container_width=True):
        st.session_state["game_report_show_all"] = True
        st.rerun()

elif not todays_games and not analysis_results:
    st.info(
        "💡 No games loaded yet. "
        "Go to **📡 Live Games** to load tonight's NBA slate, "
        "then run **⚡ Neural Analysis** to generate prop predictions."
    )
    st.page_link("pages/1_📡_Live_Games.py", label="📡 Go to Live Games", icon="🏀")

# ============================================================
# END SECTION: Matchup Selector
# ============================================================


# ============================================================
# SECTION: Filter Results to Selected Game
# ============================================================

if selected_game and analysis_results:
    home = selected_game.get("home_team", "").upper().strip()
    away = selected_game.get("away_team", "").upper().strip()
    game_teams = _expand_teams({home, away} - {""})
    filtered = [
        r for r in analysis_results
        if (
            r.get("player_team", r.get("team", "")).upper().strip() in game_teams
            or r.get("opponent", "").upper().strip() in game_teams
        )
    ]
    report_results = filtered if filtered else analysis_results
elif analysis_results:
    report_results = analysis_results
else:
    report_results = []

# ============================================================
# END SECTION: Filter Results to Selected Game
# ============================================================


# ============================================================
# SECTION: Tabbed Interface — Game Report | Game Builder | Narrative
# ============================================================

_tab_report, _tab_builder, _tab_narrative = st.tabs([
    "📊 Game Report",
    "🏗️ Game Builder",
    "📖 Game Narrative",
])

# Helper functions are defined at module level below before the tab content

_FANTASY_SCORE_STAT_PREFIX = "fantasy_score"


def _is_fantasy_score_stat(stat_type: str) -> bool:
    """Return True if *stat_type* is a composite fantasy-score stat."""
    return str(stat_type).startswith(_FANTASY_SCORE_STAT_PREFIX)


def _build_entry_strategy(results):
    """Build entry strategy matrix parlay combos from analysis results.

    Args:
        results: List of analysis result dicts from Neural Analysis engine.

    Returns:
        list[dict]: Parlay combo entries (2-leg, 3-leg, 5-leg) with
        unique-player constraint.  Fantasy-score composite stat types
        are excluded so legs stay comparable across sportsbooks.
    """
    top = [
        r for r in results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and abs(r.get("edge_percentage", 0)) >= 5.0
        # Exclude fantasy-score composite stats from parlay legs
        and not _is_fantasy_score_stat(r.get("stat_type", ""))
    ]
    top = sorted(top, key=lambda r: r.get("confidence_score", 0), reverse=True)

    def _pick_unique_players(candidates, num_legs, exclude_players=None):
        """Return up to num_legs picks with no repeated players.

        Enforces team diversity: swaps the weakest pick for the best
        pick from a different team when all selections are same-team.

        Args:
            candidates: Sorted list of pick dicts.
            num_legs: Max number of picks to return.
            exclude_players: Optional set of player names to skip so that
                each combo tier offers genuinely different picks.
        """
        exclude = exclude_players or set()
        seen: set = set()
        selected = []
        for r in candidates:
            pname = r.get("player_name", "")
            if pname and (pname in seen or pname in exclude):
                continue
            seen.add(pname)
            selected.append(r)
            if len(selected) == num_legs:
                break

        # Team diversity: replace weakest pick if all from same team
        if len(selected) >= 2:
            teams_in = {(p.get("team") or p.get("player_team") or "").upper().strip()
                        for p in selected}
            teams_in.discard("")
            if len(teams_in) == 1:
                only_team = next(iter(teams_in))
                used_names = {p.get("player_name", "") for p in selected}
                used_names.update(exclude)
                for alt in candidates:
                    alt_team = (alt.get("team") or alt.get("player_team") or "").upper().strip()
                    alt_name = alt.get("player_name", "")
                    if alt_team and alt_team != only_team and alt_name not in used_names:
                        selected[-1] = alt
                        break

        return selected

    def _fmt(picks):
        return [
            f"{r['player_name']} {r['direction']} {r.get('prop_line', r.get('line', ''))} {r['stat_type'].title()}"
            for r in picks
        ]

    entries = []
    used_players: set = set()

    # ── Power Play (2-leg): highest-confidence pair ───────────
    picks2 = _pick_unique_players(top, 2)
    if len(picks2) >= 2:
        avg2 = round(sum(r.get("confidence_score", 0) for r in picks2) / 2, 1)
        entries.append({
            "combo_type": "Power Play (2)",
            "picks": _fmt(picks2),
            "safe_avg": f"{avg2:.1f}",
            "strategy": "Highest-confidence 2-leg.",
        })
        used_players.update(r.get("player_name", "") for r in picks2)

    # ── Triple Threat (3-leg): next-best 3 picks (no overlap) ─
    # Sort remaining by edge% for variety, fall back to confidence.
    edge_sorted = sorted(
        top,
        key=lambda r: abs(r.get("edge_percentage", 0)),
        reverse=True,
    )
    picks3 = _pick_unique_players(edge_sorted, 3, exclude_players=used_players)
    if len(picks3) < 3:
        # Not enough non-overlapping picks; allow overlap but sort by edge
        picks3 = _pick_unique_players(edge_sorted, 3)
    if len(picks3) >= 3:
        avg3 = round(sum(r.get("confidence_score", 0) for r in picks3) / 3, 1)
        entries.append({
            "combo_type": "Triple Threat (3)",
            "picks": _fmt(picks3),
            "safe_avg": f"{avg3:.1f}",
            "strategy": "Best-edge 3-leg, balanced risk.",
        })
        used_players.update(r.get("player_name", "") for r in picks3)

    # ── Max Parlay (5-leg): diversified across remaining pool ──
    picks5 = _pick_unique_players(top, 5, exclude_players=used_players)
    if len(picks5) < 5:
        # Not enough fresh players; fill from full pool
        picks5 = _pick_unique_players(top, 5)
    if len(picks5) >= 5:
        avg5 = round(sum(r.get("confidence_score", 0) for r in picks5) / 5, 1)
        entries.append({
            "combo_type": "Max Parlay (5)",
            "picks": _fmt(picks5),
            "safe_avg": f"{avg5:.1f}",
            "strategy": "High ceiling, diversified 5-leg.",
        })
    return entries


def _build_all_picks_table(results):
    """Build a sorted list of all individual picks for display.

    Args:
        results: List of analysis result dicts from Neural Analysis engine.

    Returns:
        list[dict]: Enriched rows with columns matching the Prop Scanner
        layout.  Includes every analyzed prop (no edge threshold) so the
        user can see the full picture.
    """
    all_picks = sorted(
        [r for r in results if not r.get("player_is_out", False)],
        key=lambda r: r.get("confidence_score", 0),
        reverse=True,
    )
    rows = []
    for r in all_picks:
        # ── Skip unbettable demon / goblin alternate lines ────
        if is_unbettable_line(r):
            continue

        proj = round(r.get("adjusted_projection", r.get("projected_value", r.get("projection", 0))) or 0, 1)
        line = r.get("prop_line", r.get("line", 0)) or 0
        stat = r.get("stat_type", "")

        # Season average lookup
        season_avg = 0.0
        _avg_key = f"season_{stat}_avg"
        season_avg = r.get(_avg_key, 0) or 0
        if not season_avg:
            season_avg = r.get(f"{stat}_avg", 0) or 0
        season_avg = round(float(season_avg), 1) if season_avg else 0.0

        # Line vs Avg %
        line_vs_avg = r.get("line_vs_avg_pct", 0) or 0
        if not line_vs_avg and season_avg > 0 and line > 0:
            line_vs_avg = round((line - season_avg) / season_avg * 100, 1)
        else:
            line_vs_avg = round(float(line_vs_avg), 1)

        direction = r.get("direction", "")

        # Value signal
        if season_avg and line_vs_avg < -12:
            value = "🔥 Low Line"
        elif season_avg and line_vs_avg > 15:
            value = "⚠️ High Line"
        elif season_avg:
            value = "✅ Fair"
        else:
            value = "—"

        # Probability %
        prob_over = r.get("probability_over", 0) or 0
        hit_prob = prob_over if direction == "OVER" else (1.0 - prob_over)

        rows.append({
            "Player":     r.get("player_name", "?"),
            "Team":       r.get("player_team", r.get("team", "")),
            "Stat":       stat.title(),
            "Dir":        direction,
            "Line":       line,
            "Proj":       proj,
            "Avg":        season_avg if season_avg else None,
            "Line vs Avg": f"{line_vs_avg:+.1f}%" if season_avg else "—",
            "Value":      value,
            "Hit%":       round(hit_prob * 100, 1),
            "SAFE":       round(r.get("confidence_score", 0), 1),
            "↑ Edge%":    round(r.get("edge_percentage", 0), 1),
            "Tier":       r.get("tier", ""),
            "Platform":   r.get("platform", ""),
        })
    return rows


# Column config for the enriched picks dataframe
_PICKS_COL_CONFIG = {
    "Player":      st.column_config.TextColumn(width=140),
    "Team":        st.column_config.TextColumn(width=60),
    "Stat":        st.column_config.TextColumn(width=100),
    "Dir":         st.column_config.TextColumn(width=65),
    "Line":        st.column_config.NumberColumn(format="%.1f", width=70),
    "Proj":        st.column_config.NumberColumn(format="%.1f", width=70),
    "Avg":         st.column_config.NumberColumn(format="%.1f", width=70),
    "Line vs Avg": st.column_config.TextColumn(width=95),
    "Value":       st.column_config.TextColumn(width=105),
    "Hit%":        st.column_config.NumberColumn(format="%.1f%%", width=70),
    "SAFE":        st.column_config.NumberColumn(format="%.1f", width=65),
    "↑ Edge%":     st.column_config.NumberColumn(format="%.1f", width=75),
    "Tier":        st.column_config.TextColumn(width=70),
    "Platform":    st.column_config.TextColumn(width=95),
}


def _predict_game(home_abbrev, away_abbrev, vegas_spread=None, game_total=None):
    """
    Predict a game using the multi-layer game prediction engine.

    Calls engine/game_prediction.py which implements:
      Layer 1: Dean Oliver Four-Factor Model
      Layer 2: Pace-Adjusted Possessions (60/40 toward faster team)
      Layer 3: Quantum Matrix Game Simulation (2000 iterations)
      Layer 4: Vegas Bayesian Blending (55% model / 45% Vegas)
      Layer 5: Confidence & Context Scoring

    Returns the rich prediction dict from the engine, or None on failure.
    Falls back to a lightweight formula if the engine is unavailable.
    """
    if _GAME_PREDICTION_ENGINE_AVAILABLE:
        try:
            result = _engine_predict_game(
                home_abbrev=home_abbrev,
                away_abbrev=away_abbrev,
                teams_data_dict=TEAMS_DATA,
                vegas_spread=vegas_spread,
                game_total=game_total,
                num_simulations=2000,
            )
            # Cache prediction in session state for cross-page access
            if result:
                cache_key = f"{home_abbrev}_{away_abbrev}"
                if "game_predictions" not in st.session_state:
                    st.session_state["game_predictions"] = {}
                st.session_state["game_predictions"][cache_key] = result
            return result
        except Exception:
            pass  # Fall through to legacy fallback

    # ── Legacy fallback (used only if engine import fails) ────
    home_t = TEAMS_DATA.get(home_abbrev.upper(), {})
    away_t = TEAMS_DATA.get(away_abbrev.upper(), {})
    if not home_t or not away_t:
        return None
    try:
        home_ortg = float(home_t.get("ortg", 113.0) or 113.0)
        home_drtg = float(home_t.get("drtg", 113.0) or 113.0)
        home_pace = float(home_t.get("pace", 100.0) or 100.0)
        away_ortg = float(away_t.get("ortg", 113.0) or 113.0)
        away_drtg = float(away_t.get("drtg", 113.0) or 113.0)
        away_pace = float(away_t.get("pace", 100.0) or 100.0)
        avg_pace  = (home_pace + away_pace) / 2.0
        _HOME_ADV = 1.012
        home_score = round(home_ortg * (avg_pace / 100.0) * (_LEAGUE_AVG_DRTG / away_drtg) * _HOME_ADV, 1)
        away_score = round(away_ortg * (avg_pace / 100.0) * (_LEAGUE_AVG_DRTG / home_drtg) / _HOME_ADV, 1)
        if home_score == away_score:
            home_score += 1.0
        predicted_total  = round(home_score + away_score, 1)
        predicted_margin = round(abs(home_score - away_score), 1)
        predicted_winner = home_abbrev if home_score >= away_score else away_abbrev
        return {
            "home_score": home_score, "away_score": away_score,
            "predicted_total": predicted_total, "predicted_winner": predicted_winner,
            "predicted_margin": predicted_margin,
            "home_ortg": home_ortg, "home_drtg": home_drtg, "home_pace": home_pace,
            "away_ortg": away_ortg, "away_drtg": away_drtg, "away_pace": away_pace,
        }
    except Exception:
        return None


def _render_game_team_stats(game, game_pred):
    """Render a compact team-stats comparison + game prediction row."""
    home = game.get("home_team", "?").upper()
    away = game.get("away_team", "?").upper()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**{away}** (away)")
    c2.markdown(f"**{home}** (home)")

    if game_pred:
        c3.markdown(
            f"**Predicted:** {away} {game_pred['away_score']:.0f} — "
            f"{home} {game_pred['home_score']:.0f}"
        )
        c4.markdown(
            f"**Total:** {game_pred['predicted_total']:.0f} · "
            f"**Winner:** {game_pred['predicted_winner']} by {game_pred['predicted_margin']:.0f}"
        )

    # ── Standings Context (API-NBA) ──────────────────────────────
    _standings_map: dict = {}
    for _s in st.session_state.get("league_standings", []):
        _standings_map[_s.get("team_abbreviation", "").upper()] = _s

    _st_home = _standings_map.get(home, {})
    _st_away = _standings_map.get(away, {})
    if _st_home or _st_away:
        def _record_str(sd: dict) -> str:
            if not sd:
                return "—"
            w = sd.get("wins", 0)
            l = sd.get("losses", 0)
            rank = sd.get("conference_rank", "")
            conf = (sd.get("conference") or "")[:1].upper()
            streak = sd.get("streak") or ""
            l10w = sd.get("last_10_wins", 0)
            l10l = sd.get("last_10_losses", 0)
            parts = [f"**{w}-{l}**"]
            if rank:
                parts.append(f"#{rank} {conf}")
            if l10w + l10l > 0:
                parts.append(f"L10: {l10w}-{l10l}")
            if streak:
                parts.append(f"Str: {streak}")
            return " · ".join(parts)

        _s1, _s2 = st.columns(2)
        _s1.markdown(f"🏀 **{away}**: {_record_str(_st_away)}", unsafe_allow_html=True)
        _s2.markdown(f"🏀 **{home}**: {_record_str(_st_home)}", unsafe_allow_html=True)

    # ── Head-to-Head Visualization (Dean Oliver Four Factors) ────────
    ht = TEAMS_DATA.get(home, {})
    at = TEAMS_DATA.get(away, {})
    if ht or at:
        # Extended stats: original 3 + Dean Oliver Four Factors
        _h2h_stats = [
            ("Pace",  float(at.get("pace", 100) or 100), float(ht.get("pace", 100) or 100), 85, 115, False),
            ("ORtg",  float(at.get("ortg", 113) or 113), float(ht.get("ortg", 113) or 113), 105, 125, False),
            ("DRtg",  float(at.get("drtg", 113) or 113), float(ht.get("drtg", 113) or 113), 105, 125, True),
            ("NetRtg",
             float(at.get("ortg", 113) or 113) - float(at.get("drtg", 113) or 113),
             float(ht.get("ortg", 113) or 113) - float(ht.get("drtg", 113) or 113),
             -15, 15, False),
            ("eFG%",  float(at.get("efg_pct", 52) or 52), float(ht.get("efg_pct", 52) or 52), 45, 60, False),
            ("TOV%",  float(at.get("tov_pct", 13) or 13), float(ht.get("tov_pct", 13) or 13), 8, 20, True),
            ("FTRate",float(at.get("ft_rate", 0.25) or 0.25), float(ht.get("ft_rate", 0.25) or 0.25), 0.15, 0.40, False),
        ]

        st.markdown(
            get_h2h_bars_html(away, home, _h2h_stats),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"| Stat | {away} | {home} |\n"
            f"|------|-------|--------|\n"
            f"| Pace | {at.get('pace','—')} | {ht.get('pace','—')} |\n"
            f"| ORtg | {at.get('ortg','—')} | {ht.get('ortg','—')} |\n"
            f"| DRtg | {at.get('drtg','—')} | {ht.get('drtg','—')} |"
        )


def _render_key_players(team_abbrev, label):
    """
    Show the top 3 scorers and top rebounder from players.csv for a team.
    Falls back gracefully if no data is available.
    """
    players = PLAYERS_BY_TEAM.get(team_abbrev.upper(), [])
    if not players:
        st.caption(f"No player data available for {team_abbrev}.")
        return

    # Sort by points avg, take top 4
    top_by_pts = sorted(players, key=lambda p: float(p.get("points_avg", 0) or 0), reverse=True)[:4]
    # Top rebounder (may already be in top_by_pts)
    top_reb = max(players, key=lambda p: float(p.get("rebounds_avg", 0) or 0), default=None)

    # Combine without duplicates
    shown = {p.get("name", p.get("player_name", "")) for p in top_by_pts}
    key_players = list(top_by_pts)
    if top_reb:
        top_reb_name = top_reb.get("name", top_reb.get("player_name", ""))
        if top_reb_name and top_reb_name not in shown:
            key_players.append(top_reb)

    st.markdown(f"**{label} Key Players** (season averages)")
    rows = []
    for p in key_players:
        name = p.get("name", p.get("player_name", "Unknown"))
        rows.append({
            "Player": name,
            "Pos":    p.get("position", "—"),
            "PTS":    float(p.get("points_avg", 0) or 0),
            "REB":    float(p.get("rebounds_avg", 0) or 0),
            "AST":    float(p.get("assists_avg", 0) or 0),
            "3PM":    float(p.get("threes_avg", 0) or 0),
            "MIN":    float(p.get("minutes_avg", 0) or 0),
        })
    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PTS": st.column_config.NumberColumn(format="%.1f"),
            "REB": st.column_config.NumberColumn(format="%.1f"),
            "AST": st.column_config.NumberColumn(format="%.1f"),
            "3PM": st.column_config.NumberColumn(format="%.1f"),
            "MIN": st.column_config.NumberColumn(format="%.1f"),
        },
    )


# ── Determine which games to display (deduplicated) ──────────
with _tab_report:
    if selected_game:
        _games_to_show = [selected_game]
    else:
        # Deduplicate: keep only the first occurrence of each home+away pair
        _seen_matchups: set = set()
        _games_to_show = []
        for _g in todays_games:
            _key = (
                _g.get("home_team", "").upper().strip(),
                _g.get("away_team", "").upper().strip(),
            )
            if _key not in _seen_matchups and (_key[0] or _key[1]):
                _seen_matchups.add(_key)
                _games_to_show.append(_g)

    if _games_to_show:
        for game in _games_to_show:
            home = game.get("home_team", "").upper().strip()
            away = game.get("away_team", "").upper().strip()
            game_teams_expanded = _expand_teams({home, away} - {""})
            game_results = [
                r for r in report_results
                if (
                    r.get("player_team", r.get("team", "")).upper().strip() in game_teams_expanded
                    or r.get("opponent", "").upper().strip() in game_teams_expanded
                )
            ]
            n_game_props = len(game_results)
            n_conf = len([r for r in game_results if r.get("confidence_score", 0) >= 70])

            # Always show every game — even when no props have been analyzed
            expander_label = (
                f"🏀 {away} @ {home}"
                + (f" — {n_game_props} props · {n_conf} high-conf" if n_game_props else " — no props analyzed")
            )

            # ── QDS Matchup Card above expander (with logos + records) ──
            _standings_map_mc: dict = {}
            for _s_mc in st.session_state.get("league_standings", []):
                _standings_map_mc[_s_mc.get("team_abbreviation", "").upper()] = _s_mc
            _home_sd = _standings_map_mc.get(home, {})
            _away_sd = _standings_map_mc.get(away, {})
            _home_rec = f"{_home_sd.get('wins', 0)}-{_home_sd.get('losses', 0)}" if _home_sd else ""
            _away_rec = f"{_away_sd.get('wins', 0)}-{_away_sd.get('losses', 0)}" if _away_sd else ""

            # Backfill game dict with standings data so downstream renderers
            # (get_game_report_html, team stats panels) pick up records.
            if _home_sd and not game.get("home_wins"):
                game["home_wins"] = _home_sd.get("wins", 0)
                game["home_losses"] = _home_sd.get("losses", 0)
            if _away_sd and not game.get("away_wins"):
                game["away_wins"] = _away_sd.get("wins", 0)
                game["away_losses"] = _away_sd.get("losses", 0)

            # Extract conference seed, streak, and game time for the matchup card
            _home_rank = _home_sd.get("conference_rank", game.get("home_conference_rank", 0))
            _home_conf_ltr = (_home_sd.get("conference") or game.get("home_conference") or "")[:1].upper()
            _away_rank = _away_sd.get("conference_rank", game.get("away_conference_rank", 0))
            _away_conf_ltr = (_away_sd.get("conference") or game.get("away_conference") or "")[:1].upper()
            _home_seed_str = f"#{_home_rank} {_home_conf_ltr}" if _home_rank else ""
            _away_seed_str = f"#{_away_rank} {_away_conf_ltr}" if _away_rank else ""
            _home_streak_str = _home_sd.get("streak") or game.get("home_streak") or ""
            _away_streak_str = _away_sd.get("streak") or game.get("away_streak") or ""
            _game_time_str = game.get("game_time_et") or ""

            st.markdown(
                get_matchup_card_html(
                    away_team=away,
                    home_team=home,
                    away_record=_away_rec,
                    home_record=_home_rec,
                    n_props=n_game_props,
                    n_high_conf=n_conf,
                    game_time=_game_time_str,
                    away_seed=_away_seed_str,
                    home_seed=_home_seed_str,
                    away_streak=_away_streak_str,
                    home_streak=_home_streak_str,
                ),
                unsafe_allow_html=True,
            )

            with st.expander(expander_label, expanded=True):
                # Pass Vegas lines from the game object if available
                _game_vs = game.get("vegas_spread")
                _game_gt = game.get("game_total")
                game_pred = _predict_game(
                    home, away,
                    vegas_spread=float(_game_vs) if _game_vs is not None else None,
                    game_total=float(_game_gt) if _game_gt is not None else None,
                )

                # ── Always show team stats + game prediction ───────────
                st.markdown("#### 📊 Team Stats & Game Prediction")
                _render_game_team_stats(game, game_pred)

                # ── Show Odds API consensus lines if available ─────────
                _bk_count = game.get("bookmaker_count", 0)
                if _bk_count > 0:
                    _cons_spread = game.get("consensus_spread")
                    _cons_total  = game.get("consensus_total")
                    _ml_home     = game.get("moneyline_home")
                    _ml_away     = game.get("moneyline_away")
                    _sr          = game.get("spread_range", (None, None)) or (None, None)
                    _tr          = game.get("total_range", (None, None)) or (None, None)

                    def _fmt_ml_gr(ml):
                        if ml is None:
                            return "—"
                        v = round(float(ml))
                        return f"+{v}" if v > 0 else str(v)

                    _oc1, _oc2, _oc3, _oc4 = st.columns(4)
                    _oc1.metric(
                        "Consensus Spread",
                        f"{_cons_spread:+.1f}" if _cons_spread is not None else "—",
                        help=f"Range across {_bk_count} books: {_sr[0]:+.1f} to {_sr[1]:+.1f}" if (_sr[0] is not None and _sr[1] is not None) else f"From {_bk_count} books",
                    )
                    _oc2.metric(
                        "Consensus O/U",
                        f"{_cons_total:.1f}" if _cons_total is not None else "—",
                        help=f"Range: {_tr[0]:.1f} to {_tr[1]:.1f}" if (_tr[0] is not None and _tr[1] is not None) else f"From {_bk_count} books",
                    )
                    _oc3.metric(f"{home} Moneyline", _fmt_ml_gr(_ml_home), help="Consensus across all bookmakers")
                    _oc4.metric(f"{away} Moneyline", _fmt_ml_gr(_ml_away), help="Consensus across all bookmakers")
                    st.caption(f"📚 Consensus from {_bk_count} bookmakers")

                if game_pred:
                    # Rich multi-metric caption if engine provided full output
                    _home_wp  = game_pred.get("home_win_probability")
                    _away_wp  = game_pred.get("away_win_probability")
                    _ot_prob  = game_pred.get("overtime_probability")
                    _conf     = game_pred.get("game_prediction_confidence")
                    _pace_env = game_pred.get("pace_environment")
                    _blow_p   = game_pred.get("blowout_probability")

                    if _home_wp is not None:
                        # Engine output — show full metrics in columns
                        _pc1, _pc2, _pc3, _pc4 = st.columns(4)
                        _pc1.metric(
                            "Predicted Score",
                            f"{away} {game_pred['away_score']} — {home} {game_pred['home_score']}"
                        )
                        _pc2.metric(
                            "Winner",
                            f"{game_pred['predicted_winner']} by {game_pred['predicted_margin']}",
                            help=f"Home win prob: {_home_wp:.0%}  |  Away: {_away_wp:.0%}",
                        )
                        _pc3.metric(
                            "Total / Pace",
                            f"{game_pred['predicted_total']} pts · {_pace_env}",
                            help=f"OT prob: {_ot_prob:.1%}  |  Blowout: {_blow_p:.1%}",
                        )
                        _pc4.metric(
                            "Prediction Confidence",
                            f"{_conf}/100",
                            help="Based on data quality, matchup clarity, Vegas alignment, and pace.",
                        )
                        # Model factors detail (shown inline — expanders cannot be nested)
                        _mf = game_pred.get("model_factors", {})
                        if _mf:
                            st.markdown("**🔬 Model Factors**")
                            _mf_cols = st.columns(4)
                            _mf_labels = [
                                ("4-Factor Edge",      _mf.get("four_factor_edge", "—")),
                                ("Pace Environment",   _mf.get("pace_edge", "—")),
                                ("Home Court Boost",   _mf.get("home_court_boost", "—")),
                                ("Vegas Blend",        _mf.get("vegas_blend", "—")),
                            ]
                            for _c, (_lbl, _val) in zip(_mf_cols, _mf_labels):
                                _c.metric(_lbl, _val)
                    else:
                        st.caption(
                            f"🔮 Predicted: **{away} {game_pred['away_score']:.0f}** vs "
                            f"**{home} {game_pred['home_score']:.0f}** · "
                            f"Total: **{game_pred['predicted_total']:.0f}** · "
                            f"Predicted winner: **{game_pred['predicted_winner']}** "
                            f"by **{game_pred['predicted_margin']:.0f}**"
                        )

                st.divider()

                if game_results:
                    # ── Top Value Picks (best edge%) ──────────────────
                    _value_picks = sorted(
                        [r for r in game_results
                         if not r.get("should_avoid", False)
                         and abs(r.get("edge_percentage", 0)) >= 3.0],
                        key=lambda r: abs(r.get("edge_percentage", 0)),
                        reverse=True,
                    )[:3]
                    if _value_picks:
                        st.markdown("#### 💎 Top Value Picks (Highest Edge)")
                        _vp_cols = st.columns(min(3, len(_value_picks)))
                        for _vc, _vp in zip(_vp_cols, _value_picks):
                            _vp_edge = _vp.get("edge_percentage", 0)
                            _vp_dir = _vp.get("direction", "OVER")
                            _edge_color = "#00D559" if _vp_edge > 0 else "#F24336"
                            _dir_icon = "📈" if _vp_dir == "OVER" else "📉"
                            _vc.markdown(
                                f'<div style="background:rgba(0,213,89,0.05);'
                                f'border:1px solid {_edge_color}30;border-radius:10px;'
                                f'padding:12px;text-align:center;">'
                                f'<div style="font-weight:700;color:#EEF0F6;font-size:0.9rem;">'
                                f'{_vp.get("player_name", "?")}</div>'
                                f'<div style="color:#6B7A9A;font-size:0.78rem;margin:4px 0;">'
                                f'{_dir_icon} {_vp_dir} {_vp.get("prop_line", _vp.get("line", 0))} {_vp.get("stat_type", "").title()}</div>'
                                f'<div style="color:{_edge_color};font-weight:700;font-size:1.1rem;">'
                                f'{_vp_edge:+.1f}% Edge</div>'
                                f'<div style="color:#6B7A9A;font-size:0.72rem;margin-top:4px;">'
                                f'SAFE: {_vp.get("confidence_score", 0):.0f}/100</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        st.divider()

                    # ── Injury Impact Summary ─────────────────────────
                    _inj_map_gr = st.session_state.get("injury_status_map", {})
                    _inj_statuses_gr = {"Out", "Doubtful", "Injured Reserve", "Game Time Decision"}
                    _home_players_gr = PLAYERS_BY_TEAM.get(home, [])
                    _away_players_gr = PLAYERS_BY_TEAM.get(away, [])
                    _home_out_gr = [
                        p.get("name", "?")
                        for p in _home_players_gr[:12]
                        if _inj_map_gr.get(p.get("name", ""), {}).get("status", "Active") in _inj_statuses_gr
                    ]
                    _away_out_gr = [
                        p.get("name", "?")
                        for p in _away_players_gr[:12]
                        if _inj_map_gr.get(p.get("name", ""), {}).get("status", "Active") in _inj_statuses_gr
                    ]
                    if _home_out_gr or _away_out_gr:
                        st.markdown("#### 🏥 Injury Impact")
                        _inj_c1, _inj_c2 = st.columns(2)
                        with _inj_c1:
                            if _away_out_gr:
                                st.markdown(
                                    f"**{away}**: " + ", ".join(
                                        f"🚫 {html.escape(n)}" for n in _away_out_gr[:4]
                                    ),
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(f"**{away}**: ✅ No major injuries")
                        with _inj_c2:
                            if _home_out_gr:
                                st.markdown(
                                    f"**{home}**: " + ", ".join(
                                        f"🚫 {html.escape(n)}" for n in _home_out_gr[:4]
                                    ),
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(f"**{home}**: ✅ No major injuries")
                        st.divider()

                    # ── All Props & Picks for this game ───────────────
                    all_picks_rows = _build_all_picks_table(game_results)
                    if all_picks_rows:
                        st.markdown("#### 📋 All Player Props & Picks")
                        st.dataframe(
                            all_picks_rows,
                            use_container_width=True,
                            hide_index=True,
                            height=min(len(all_picks_rows) * 36 + 38, 600),
                            column_config=_PICKS_COL_CONFIG,
                        )
                        st.divider()

                    # ── Suggested Parlays for this game ───────────────
                    game_strategy = _build_entry_strategy(game_results)
                    if game_strategy:
                        st.markdown("#### 🎯 Suggested Parlays")
                        for _e in game_strategy[:3]:
                            st.markdown(
                                get_parlay_card_html(
                                    combo_type=_e.get("combo_type", ""),
                                    picks=_e.get("picks", []),
                                    safe_avg=_e.get("safe_avg", ""),
                                    strategy=_e.get("strategy", ""),
                                ),
                                unsafe_allow_html=True,
                            )
                        st.divider()

                    # ── Full QDS prop card report ──────────────────────
                    html_content = get_game_report_html(
                        game=game,
                        analysis_results=game_results,
                    )
                    st.html(html_content)
                else:
                    # ── Key player matchups from players.csv ────────
                    kp_col1, kp_col2 = st.columns(2)
                    with kp_col1:
                        _render_key_players(away, away)
                    with kp_col2:
                        _render_key_players(home, home)

                    # Diagnostic: show why analysis isn't matching this game
                    _raw_count = len(st.session_state.get("analysis_results", []))
                    if _raw_count > 0:
                        # Analysis exists in session but didn't match this game's teams
                        _sample_teams = set()
                        for _sr in st.session_state.get("analysis_results", [])[:20]:
                            _st = (_sr.get("player_team") or _sr.get("team") or "").upper().strip()
                            if _st:
                                _sample_teams.add(_st)
                        _team_info = f" (result teams: {', '.join(sorted(_sample_teams)[:6])})" if _sample_teams else " (result teams are empty — player team data may be missing)"
                        st.warning(
                            f"⚠️ {_raw_count} analysis result(s) exist in session but none matched "
                            f"**{away} @ {home}**{_team_info}. "
                            "Try re-running **⚡ Neural Analysis** — the report will auto-populate."
                        )
                    else:
                        st.info(
                            "📭 No props analyzed for this game yet — "
                            "run **⚡ Neural Analysis** with props for these teams "
                            "to see full prop predictions and parlay suggestions."
                        )

        # ── Overall Entry Strategy Matrix (cross-game) ────────────────────
        if report_results and not selected_game and len(todays_games) > 1:
            all_strategy = _build_entry_strategy(report_results)
            if all_strategy:
                st.divider()
                st.subheader("📊 Cross-Game Entry Strategy Matrix")
                st.markdown(
                    "Best multi-leg combinations across ALL tonight's matchups, "
                    "ranked by SAFE Score™.",
                )
                st.markdown(get_qds_strategy_table_html(all_strategy), unsafe_allow_html=True)

    elif analysis_results and not todays_games:
        # No games loaded — but analysis results exist from a previous session
        # Show all-picks table above the full HTML report
        all_picks_rows_no_game = _build_all_picks_table(report_results)
        if all_picks_rows_no_game:
            st.markdown("#### 📋 All Player Props & Picks")
            st.dataframe(
                all_picks_rows_no_game,
                use_container_width=True,
                hide_index=True,
                height=min(len(all_picks_rows_no_game) * 36 + 38, 600),
                column_config=_PICKS_COL_CONFIG,
            )
            st.divider()

        # Parlay suggestions
        all_strategy_no_game = _build_entry_strategy(report_results)
        if all_strategy_no_game:
            st.markdown("#### 🎯 Suggested Parlays")
            st.markdown(get_qds_strategy_table_html(all_strategy_no_game), unsafe_allow_html=True)
            st.divider()

        html_content = get_game_report_html(
            game=None,
            analysis_results=report_results,
        )
        st.html(html_content)
    else:
        st.info(
            "💡 Load tonight's games on the **📡 Live Games** page to see a full report for every matchup."
        )
        st.page_link("pages/1_📡_Live_Games.py", label="📡 Go to Live Games", icon="🏀")

    # ════ JOSEPH COMMENTS ON GAME REPORT ════
    if analysis_results and st.session_state.get("joseph_enabled", True):
        try:
            from utils.joseph_widget import inject_joseph_inline_commentary
            inject_joseph_inline_commentary(analysis_results[:10], "analysis_results")
        except Exception:
            pass
    # ════ END JOSEPH GAME REPORT COMMENT ════

# ============================================================
# END SECTION: Render QDS Game Report
# ============================================================


# ============================================================
# SECTION: Game Builder Tab
# ============================================================

with _tab_builder:
    st.subheader("🏗️ Game Builder & Custom Analyzer")
    st.caption("Build a custom game simulation with specific rosters and minutes")

    from data.data_manager import load_teams_data as _load_teams_gb, load_players_data as _load_players_gb
    _teams_data_gb = _load_teams_gb()
    _team_names_gb = sorted([t.get("abbreviation", t.get("name", "")) for t in _teams_data_gb]) if _teams_data_gb else []

    col_home_gb, col_away_gb = st.columns(2)
    with col_home_gb:
        home_team_gb = st.selectbox("🏠 Home Team", options=_team_names_gb, key="gb_home_team")
    with col_away_gb:
        away_team_gb = st.selectbox(
            "🚌 Away Team",
            options=_team_names_gb,
            key="gb_away_team",
            index=min(1, len(_team_names_gb) - 1) if len(_team_names_gb) > 1 else 0,
        )

    if home_team_gb and away_team_gb and home_team_gb != away_team_gb:
        _all_players_gb = _load_players_gb()

        # Minimum minutes threshold to show in the default rotation view
        _ROTATION_MIN_THRESHOLD = 15.0   # Players averaging ≥ 15 min/game are rotation players

        def _get_team_players_gb(team_abbrev, all_players):
            """Return players for a team, sorted by minutes descending."""
            team_players = [
                p for p in all_players
                if p.get("team", "").upper() == team_abbrev.upper()
            ]
            # Sort by minutes (most minutes = stars first)
            team_players.sort(
                key=lambda p: float(p.get("minutes_avg", p.get("season_min_avg", 0)) or 0),
                reverse=True,
            )
            return team_players

        def _split_rotation_bench(players):
            """Split player list into rotation (≥15 min) and bench (< 15 min)."""
            rotation = [
                p for p in players
                if float(p.get("minutes_avg", p.get("season_min_avg", 0)) or 0) >= _ROTATION_MIN_THRESHOLD
            ]
            bench = [
                p for p in players
                if float(p.get("minutes_avg", p.get("season_min_avg", 0)) or 0) < _ROTATION_MIN_THRESHOLD
            ]
            return rotation, bench

        def _get_injury_badge(p):
            """Return an inline injury status badge (emoji string) for the player."""
            inj = st.session_state.get("injury_status_map", {})
            pname = p.get("name", "")
            status = inj.get(pname, {}).get("status", "") if isinstance(inj.get(pname), dict) else inj.get(pname, "")
            if not status:
                return ""
            s_up = str(status).upper()
            if s_up in ("OUT", "INJURED RESERVE"):
                return " 🚫 OUT"
            if "GTD" in s_up or "QUESTIONABLE" in s_up or "DOUBTFUL" in s_up:
                return " ⚠️ GTD"
            return ""

        def _render_player_row_gb(p, team_key_prefix, active_dict, minutes_dict, is_bench=False):
            """
            Render a single player row in the Game Builder:
              - Checkbox (active / inactive)
              - Name (bold rotation, muted bench) + injury badge
              - Inline stats: MIN | PTS | REB | AST
              - Minutes slider (only when active)
            """
            pname   = p.get("name", "Unknown")
            avg_min = float(p.get("minutes_avg", p.get("season_min_avg", 0)) or 0)
            pts     = float(p.get("points_avg",   0) or 0)
            reb     = float(p.get("rebounds_avg", 0) or 0)
            ast     = float(p.get("assists_avg",  0) or 0)
            badge   = _get_injury_badge(p)

            # Default checked: rotation players = True, bench = False
            default_active = not is_bench

            # Label: muted styling via non-bold for bench
            stat_inline = f"{avg_min:.0f} min | {pts:.1f} pts | {reb:.1f} reb | {ast:.1f} ast"
            label = f"{pname}{badge}  ·  {stat_inline}"

            is_active = st.checkbox(
                label,
                value=default_active,
                key=f"{team_key_prefix}_{pname}",
            )
            if is_active:
                adj_min = st.slider(
                    f"Minutes — {pname}",
                    min_value=0,
                    max_value=48,
                    value=max(1, int(avg_min)),
                    key=f"{team_key_prefix}_m_{pname}",
                )
                active_dict[pname] = p
                minutes_dict[pname] = adj_min

        home_players_gb = _get_team_players_gb(home_team_gb, _all_players_gb)
        away_players_gb = _get_team_players_gb(away_team_gb, _all_players_gb)

        home_rotation_gb, home_bench_gb = _split_rotation_bench(home_players_gb)
        away_rotation_gb, away_bench_gb = _split_rotation_bench(away_players_gb)

        st.markdown("---")
        col_hp_gb, col_ap_gb = st.columns(2)

        home_active_gb = {}
        home_minutes_gb = {}
        away_active_gb = {}
        away_minutes_gb = {}

        with col_hp_gb:
            st.markdown(
                f"**🏠 {home_team_gb} Rotation** "
                f"<span style='color:#6B7A9A;font-size:0.8rem;'>({len(home_rotation_gb)} players · ≥15 min/g)</span>",
                unsafe_allow_html=True,
            )
            for p in home_rotation_gb:
                _render_player_row_gb(p, f"gb_h", home_active_gb, home_minutes_gb, is_bench=False)

            if home_bench_gb:
                _show_home_bench = st.toggle(
                    f"📋 Show Bench ({len(home_bench_gb)} players < 15 min/g)",
                    value=False,
                    key="gb_show_home_bench",
                )
                if _show_home_bench:
                    st.markdown(
                        "<span style='color:#6B7A9A;font-size:0.8rem;'>📋 Bench (&lt;15 min/game)</span>",
                        unsafe_allow_html=True,
                    )
                    for p in home_bench_gb:
                        _render_player_row_gb(p, f"gb_hb", home_active_gb, home_minutes_gb, is_bench=True)

        with col_ap_gb:
            st.markdown(
                f"**🚌 {away_team_gb} Rotation** "
                f"<span style='color:#6B7A9A;font-size:0.8rem;'>({len(away_rotation_gb)} players · ≥15 min/g)</span>",
                unsafe_allow_html=True,
            )
            for p in away_rotation_gb:
                _render_player_row_gb(p, f"gb_a", away_active_gb, away_minutes_gb, is_bench=False)

            if away_bench_gb:
                _show_away_bench = st.toggle(
                    f"📋 Show Bench ({len(away_bench_gb)} players < 15 min/g)",
                    value=False,
                    key="gb_show_away_bench",
                )
                if _show_away_bench:
                    st.markdown(
                        "<span style='color:#6B7A9A;font-size:0.8rem;'>📋 Bench (&lt;15 min/game)</span>",
                        unsafe_allow_html=True,
                    )
                    for p in away_bench_gb:
                        _render_player_row_gb(p, f"gb_ab", away_active_gb, away_minutes_gb, is_bench=True)

        # Game settings
        st.markdown("---")
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            gb_total = st.number_input("Game Total (O/U)", min_value=180.0, max_value=260.0, value=220.0, step=0.5, key="gb_total")
        with gc2:
            gb_spread = st.number_input("Spread (home)", min_value=-30.0, max_value=30.0, value=-3.0, step=0.5, key="gb_spread")
        with gc3:
            gb_sims = st.select_slider("Simulations", options=[500, 1000, 2000, 5000], value=1000, key="gb_sims")

        if st.button("🚀 Run Custom Analysis", type="primary", key="gb_run"):
            from engine.projections import build_player_projection, get_stat_standard_deviation
            from engine.simulation import run_quantum_matrix_simulation
            from engine.confidence import calculate_confidence_score
            from data.data_manager import load_defensive_ratings_data as _load_def_gb

            _t0_gb = time.time()

            with st.status("🏗️ Running Game Builder Simulation...", expanded=True) as _gb_status:
                # ── Joseph Loading Screen — NBA fun facts while Game Builder runs ──
                try:
                    from utils.joseph_loading import joseph_loading_placeholder
                    _joseph_gb_loader = joseph_loading_placeholder("Building Game Report")
                except Exception:
                    _joseph_gb_loader = None
                # Step 1: Load engine data
                st.write("⚙️ Loading engine data...")
                _defensive_ratings_gb = _load_def_gb()
                _teams_for_sim_gb = _load_teams_gb()

                # Step 2: Run team-level game prediction first
                st.write(f"🔮 Generating game prediction ({home_team_gb} vs {away_team_gb})...")
                if _GAME_PREDICTION_ENGINE_AVAILABLE:
                    try:
                        _gb_game_pred = _engine_predict_game(
                            home_abbrev=home_team_gb,
                            away_abbrev=away_team_gb,
                            teams_data_dict=TEAMS_DATA,
                            vegas_spread=float(gb_spread) if gb_spread else None,
                            game_total=float(gb_total) if gb_total else None,
                            num_simulations=2000,
                        )
                        if _gb_game_pred:
                            st.session_state["gb_game_pred"] = _gb_game_pred
                    except Exception:
                        _gb_game_pred = None
                else:
                    _gb_game_pred = None

                custom_results_gb = []
                all_active_gb = list(home_active_gb.items()) + list(away_active_gb.items())
                all_minutes_gb = {**home_minutes_gb, **away_minutes_gb}
                total_players = len(all_active_gb)

                # Step 3: Per-player projections
                prog_gb = st.progress(0, text="Starting player projections...")
                for idx_gb, (pname_gb, pdata_gb) in enumerate(all_active_gb):
                    is_home_gb = pname_gb in home_active_gb
                    team_label = home_team_gb if is_home_gb else away_team_gb
                    prog_text = f"Projecting {pname_gb} ({team_label}) — {idx_gb + 1}/{total_players}"
                    prog_gb.progress((idx_gb + 1) / max(total_players, 1), text=prog_text)
                    st.write(f"  📊 {prog_text}")

                    pdata_adj_gb = dict(pdata_gb)
                    pdata_adj_gb["minutes_avg"] = all_minutes_gb.get(pname_gb, float(pdata_gb.get("minutes_avg", 28) or 28))
                    opponent_gb = away_team_gb if is_home_gb else home_team_gb

                    # Look up player estimated metrics from Deep Fetch enrichment.
                    # The enrichment dict is keyed by game_id as stored by enrich_tonights_slate()
                    # which uses the synthetic key format "{HOME}_vs_{AWAY}" produced by
                    # live_data_fetcher.  Try both orderings for robustness.
                    _gb_adv_ctx: dict | None = None
                    try:
                        _adv_enr_all = st.session_state.get("advanced_enrichment", {})
                        _gb_game_key = f"{home_team_gb}_vs_{away_team_gb}"
                        _gb_enr = (
                            _adv_enr_all.get(_gb_game_key)
                            or _adv_enr_all.get(f"{away_team_gb}_vs_{home_team_gb}")
                            or {}
                        )
                        _gb_metrics = _gb_enr.get("player_metrics", [])
                        _gb_pid = pdata_gb.get("player_id") or pdata_gb.get("id")
                        _gb_pname_lwr = pname_gb.lower()
                        for _gm in _gb_metrics:
                            _gmid = _gm.get("PLAYER_ID") or _gm.get("playerId")
                            _gmname = str(_gm.get("PLAYER_NAME") or _gm.get("playerName") or "").lower()
                            if (_gb_pid and _gmid and int(_gb_pid) == int(_gmid)) or (
                                _gb_pname_lwr and _gmname and _gb_pname_lwr in _gmname
                            ):
                                _usg = _gm.get("E_USG_PCT") or _gm.get("USG_PCT") or _gm.get("usage_pct")
                                if _usg is not None:
                                    try:
                                        _usg_f = float(_usg)
                                        _gb_adv_ctx = {"usage_pct": _usg_f / 100.0 if _usg_f > 1.0 else _usg_f}
                                    except (TypeError, ValueError):
                                        pass
                                break
                    except Exception:
                        pass

                    for stat_gb in ["points", "rebounds", "assists", "threes"]:
                        stat_avg_gb = float(pdata_adj_gb.get(f"{stat_gb}_avg", 0) or 0)
                        if stat_avg_gb <= 0:
                            continue
                        orig_min_gb = float(pdata_gb.get("minutes_avg", 28) or 28)
                        if orig_min_gb > 0:
                            stat_avg_gb = stat_avg_gb * (pdata_adj_gb["minutes_avg"] / orig_min_gb)

                        try:
                            proj_gb = build_player_projection(
                                player_data=pdata_adj_gb,
                                opponent_team_abbreviation=opponent_gb,
                                is_home_game=is_home_gb,
                                rest_days=2,
                                game_total=gb_total,
                                defensive_ratings_data=_defensive_ratings_gb,
                                teams_data=_teams_for_sim_gb,
                                vegas_spread=gb_spread if is_home_gb else -gb_spread,
                                advanced_context=_gb_adv_ctx,
                            )
                            projected_value_gb = float(proj_gb.get(f"projected_{stat_gb}", stat_avg_gb) or stat_avg_gb)
                        except Exception:
                            projected_value_gb = stat_avg_gb
                            proj_gb = {}

                        if projected_value_gb <= 0:
                            continue

                        std_dev_gb = get_stat_standard_deviation(pdata_adj_gb, stat_gb)
                        if not std_dev_gb or std_dev_gb <= 0:
                            std_dev_gb = projected_value_gb * 0.25

                        prop_line_gb = round(projected_value_gb * 2) / 2

                        try:
                            sim_gb = run_quantum_matrix_simulation(
                                projected_stat_average=projected_value_gb,
                                stat_standard_deviation=std_dev_gb,
                                prop_line=prop_line_gb,
                                number_of_simulations=gb_sims,
                                blowout_risk_factor=proj_gb.get("blowout_risk_factor", 0.1),
                                pace_adjustment_factor=proj_gb.get("pace_factor", 1.0),
                                matchup_adjustment_factor=proj_gb.get("defense_factor", 1.0),
                                home_away_adjustment=proj_gb.get("home_away_factor", 0.0),
                                rest_adjustment_factor=proj_gb.get("rest_factor", 1.0),
                                game_context={
                                    "is_home": is_home_gb,
                                    "vegas_spread": gb_spread if is_home_gb else -gb_spread,
                                    "game_total": gb_total,
                                },
                            )
                            over_prob_gb = sim_gb.get("probability_over", sim_gb.get("over_probability", 0.5))
                        except Exception:
                            over_prob_gb = 0.5
                            sim_gb = {}

                        try:
                            edge_gb = (over_prob_gb - 0.5238) * 100.0
                            _forces_gb = {
                                "over_count": 1 if over_prob_gb >= 0.5 else 0,
                                "under_count": 0 if over_prob_gb >= 0.5 else 1,
                                "over_forces": [],
                                "under_forces": [],
                            }
                            conf_gb = calculate_confidence_score(
                                probability_over=over_prob_gb,
                                edge_percentage=edge_gb,
                                directional_forces=_forces_gb,
                                defense_factor=proj_gb.get("defense_factor", 1.0),
                                stat_standard_deviation=std_dev_gb,
                                stat_average=stat_avg_gb,
                                simulation_results=sim_gb,
                                games_played=gb_sims,
                                stat_type=stat_gb,
                            )
                            conf_score_gb = conf_gb.get("confidence_score", 0) if isinstance(conf_gb, dict) else float(conf_gb or 0)
                        except Exception:
                            conf_score_gb = 0

                        custom_results_gb.append({
                            "player_name": pname_gb,
                            "team": home_team_gb if is_home_gb else away_team_gb,
                            "stat_type": stat_gb,
                            "prop_line": prop_line_gb,
                            "projected": round(projected_value_gb, 1),
                            "over_probability": over_prob_gb,
                            "confidence_score": conf_score_gb,
                            "minutes_used": pdata_adj_gb["minutes_avg"],
                            "season_avg": stat_avg_gb,
                        })

                prog_gb.empty()
                # Dismiss the Joseph loading screen
                if _joseph_gb_loader is not None:
                    try:
                        _joseph_gb_loader.empty()
                    except Exception:
                        pass

                _elapsed_gb = time.time() - _t0_gb
                _gb_status.update(
                    label=f"✅ Simulation complete — {len(all_active_gb)} players × 4 stats "
                          f"= {len(custom_results_gb)} projections in {_elapsed_gb:.1f}s",
                    state="complete",
                    expanded=False,
                )

            st.session_state["custom_game_analysis"] = custom_results_gb

        # Display custom results if available
        if st.session_state.get("custom_game_analysis"):
            # Show game-level prediction from the new engine if available
            _gb_gp = st.session_state.get("gb_game_pred")
            if _gb_gp:
                st.markdown("### 🔮 Game Score Prediction")
                _gp_c1, _gp_c2, _gp_c3, _gp_c4 = st.columns(4)
                _gp_c1.metric(
                    "Predicted Score",
                    f"{away_team_gb} {_gb_gp['away_score']} — {home_team_gb} {_gb_gp['home_score']}",
                )
                _gp_c2.metric(
                    "Winner",
                    f"{_gb_gp['predicted_winner']} by {_gb_gp['predicted_margin']}",
                    help=(
                        f"Home win prob: {_gb_gp.get('home_win_probability', 0):.0%}  |  "
                        f"Away: {_gb_gp.get('away_win_probability', 0):.0%}"
                    ),
                )
                _gp_c3.metric(
                    "Total / Pace",
                    f"{_gb_gp['predicted_total']} pts · {_gb_gp.get('pace_environment', '—')}",
                    help=(
                        f"OT prob: {_gb_gp.get('overtime_probability', 0):.1%}  |  "
                        f"Blowout: {_gb_gp.get('blowout_probability', 0):.1%}"
                    ),
                )
                _gp_c4.metric(
                    "Confidence",
                    f"{_gb_gp.get('game_prediction_confidence', '—')}/100",
                )
                st.divider()

            st.markdown("### 📊 Custom Simulation Results")
            custom_res_gb = st.session_state["custom_game_analysis"]
            custom_res_sorted_gb = sorted(custom_res_gb, key=lambda x: x.get("confidence_score", 0), reverse=True)

            for r_gb in custom_res_sorted_gb[:20]:  # Top 20
                over_prob_r = r_gb.get("over_probability", 0.5)
                direction_r = "OVER" if over_prob_r > 0.5 else "UNDER"
                conf_r = r_gb.get("confidence_score", 0)
                st.markdown(
                    get_builder_prop_card_html(
                        player_name=r_gb["player_name"],
                        team=r_gb["team"],
                        stat_type=r_gb["stat_type"],
                        direction=direction_r,
                        prop_line=r_gb["prop_line"],
                        projected=r_gb["projected"],
                        over_prob=over_prob_r,
                        confidence=conf_r,
                        minutes=r_gb["minutes_used"],
                        season_avg=r_gb.get("season_avg", 0),
                    ),
                    unsafe_allow_html=True,
                )
    elif home_team_gb == away_team_gb:
        st.warning("⚠️ Home and Away teams must be different.")
    else:
        st.info("Select both a home and away team to begin building a custom game simulation.")

# ============================================================
# END SECTION: Game Builder Tab
# ============================================================


# ============================================================
# SECTION: Game Narrative Tab
# ============================================================

def _generate_game_narrative(game, _analysis_results):
    """Generate a readable game preview narrative from analysis results.

    Uses the new game prediction engine for projected scores when available.
    """
    home_team_n = game.get("home_team", "Home")
    away_team_n = game.get("away_team", "Away")
    total_n     = game.get("game_total", 220)
    spread_n    = game.get("vegas_spread", 0)

    # Get top picks for this game (match by player_team OR opponent)
    _narrative_game_teams = _expand_teams(
        {home_team_n.upper(), away_team_n.upper()} - {""}
    )
    game_picks_n = [
        r for r in _analysis_results
        if (
            r.get("player_team", r.get("team", "")).upper().strip() in _narrative_game_teams
            or r.get("opponent", "").upper().strip() in _narrative_game_teams
        )
        and r.get("confidence_score", 0) >= 55
        and not r.get("player_is_out", False)
    ]
    game_picks_n = sorted(game_picks_n, key=lambda x: x.get("confidence_score", 0), reverse=True)

    narrative_n = f"## 🏀 GAME PREVIEW: {away_team_n} @ {home_team_n}\n\n"

    # Projected score — use new engine when possible
    _engine_pred = None
    if _GAME_PREDICTION_ENGINE_AVAILABLE:
        try:
            _engine_pred = _engine_predict_game(
                home_abbrev=home_team_n,
                away_abbrev=away_team_n,
                teams_data_dict=TEAMS_DATA,
                vegas_spread=float(spread_n) if spread_n else None,
                game_total=float(total_n) if total_n else None,
                num_simulations=2000,
            )
        except Exception:
            _engine_pred = None

    if _engine_pred:
        proj_home_n = _engine_pred["home_score"]
        proj_away_n = _engine_pred["away_score"]
        winner_n    = _engine_pred["predicted_winner"]
        margin_n    = _engine_pred["predicted_margin"]
        home_wp     = _engine_pred.get("home_win_probability", 0)
        away_wp     = _engine_pred.get("away_win_probability", 0)
        pace_env    = _engine_pred.get("pace_environment", "")
        ot_prob     = _engine_pred.get("overtime_probability", 0)
        conf_n      = _engine_pred.get("game_prediction_confidence", 0)

        narrative_n += (
            f"The model projects a **{away_team_n} {proj_away_n} — {home_team_n} {proj_home_n}** final "
            f"(confidence: {conf_n}/100).\n\n"
        )
        narrative_n += (
            f"**{winner_n}** is projected to win by **{margin_n} points**. "
            f"Win probability: {home_team_n} {home_wp:.0%} · {away_team_n} {away_wp:.0%}. "
            f"Overtime probability: {ot_prob:.1%}.\n\n"
        )
        if pace_env:
            narrative_n += f"Expected pace environment: **{pace_env}** ({_engine_pred.get('expected_possessions', '—')} possessions).\n\n"
        _mf = _engine_pred.get("model_factors", {})
        if _mf:
            narrative_n += (
                f"*Model factors: {_mf.get('four_factor_edge','—')} four-factor edge · "
                f"{_mf.get('home_court_boost','—')} home-court · "
                f"{_mf.get('vegas_blend','—')}*\n\n"
            )
    else:
        # Fallback: derive from Vegas lines if available
        try:
            total_float  = float(total_n or 220)
            spread_float = float(spread_n or 0)
            proj_home_n  = round(total_float / 2 + abs(spread_float) / 2 * (-1 if spread_float > 0 else 1))
            proj_away_n  = round(total_float - proj_home_n)
            narrative_n += f"The model projects a **{away_team_n} {proj_away_n} — {home_team_n} {proj_home_n}** final.\n\n"
        except Exception:
            narrative_n += f"Game Total: {total_n}\n\n"

    # Spread analysis
    try:
        spread_val = float(spread_n or 0)
        if spread_val != 0:
            fav_n = home_team_n if spread_val < 0 else away_team_n
            dog_n = away_team_n if spread_val < 0 else home_team_n
            narrative_n += f"**{fav_n}** is favored by {abs(spread_val):.1f} points over **{dog_n}**.\n\n"
    except Exception:
        pass

    # Top picks from this matchup
    if game_picks_n:
        narrative_n += "### 🎯 TOP PICKS FROM THIS MATCHUP\n"
        for pick_n in game_picks_n[:5]:
            prob_n = pick_n.get("over_probability", pick_n.get("probability_over", 0.5)) * 100
            direction_n = "OVER" if pick_n.get("over_probability", pick_n.get("probability_over", 0.5)) > 0.5 else "UNDER"
            conf_n = pick_n.get("confidence_score", 0)
            tier_n = "Platinum" if conf_n >= 85 else "Gold" if conf_n >= 70 else "Silver"
            stat_label = pick_n.get("stat_type", "").replace("_", " ")
            line_val = pick_n.get("prop_line", pick_n.get("line", 0))
            narrative_n += (
                f"• **{pick_n['player_name']}** {direction_n} {line_val} {stat_label} "
                f"— {prob_n:.0f}% probability, {tier_n} tier\n"
            )

    return narrative_n


with _tab_narrative:
    st.subheader("📖 Game Narrative")
    st.caption("AI-generated game preview story from analysis results")

    if not analysis_results:
        st.info(
            "💡 Run **⚡ Neural Analysis** first to generate narrative previews. "
            "The narrative is built from prop analysis results."
        )
    elif not todays_games:
        st.info(
            "💡 Load tonight's games on the **📡 Live Games** page to generate per-game narratives."
        )
    else:
        _narrative_games = _games_to_show if "_games_to_show" in dir() and _games_to_show else todays_games
        for _narr_game in _narrative_games:
            _narr_home = _narr_game.get("home_team", "")
            _narr_away = _narr_game.get("away_team", "")
            with st.expander(f"🏀 {_narr_away} @ {_narr_home}", expanded=True):
                # QDS-styled narrative card with team-colored accents & watermark logos
                st.markdown(
                    get_narrative_card_html(
                        away_team=_narr_away,
                        home_team=_narr_home,
                    ),
                    unsafe_allow_html=True,
                )
                _narrative_text = _generate_game_narrative(_narr_game, analysis_results)
                st.markdown(_narrative_text)

# ============================================================
# END SECTION: Game Narrative Tab
# ============================================================
