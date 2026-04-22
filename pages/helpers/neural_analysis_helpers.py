# ============================================================
# FILE: pages/helpers/neural_analysis_helpers.py
# PURPOSE: Helper functions for the Neural Analysis page.
#          Extracted from pages/3_⚡_Quantum_Analysis_Matrix.py to reduce page size.
# ============================================================
import streamlit as st
# st.html(unsafe_allow_javascript=True) is required so DOMPurify preserves <style> tags
import math
import html as _html

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    import logging
    _logger = logging.getLogger(__name__)

from engine.confidence import get_tier_color
from engine.odds_engine import american_odds_to_implied_probability as _odds_to_implied_prob
from data.data_manager import get_player_status
from styles.theme import (
    get_logo_img_tag,
    get_qds_confidence_bar_html,
    get_qds_prop_card_html,
    get_player_intel_css,
    get_availability_badge_html,
    get_form_dots_html,
    get_matchup_grade_badge_html,
    get_intel_strip_html,
    get_line_value_badge_html,
)

try:
    from engine.player_intelligence import (
        get_player_intelligence_summary,
        get_recent_form_vs_line,
        get_availability_context,
    )
    _PLAYER_INTEL_AVAILABLE = True
except ImportError:
    _PLAYER_INTEL_AVAILABLE = False

import os as _os

_ASSETS_DIR = "assets"

# Prefix used to identify composite fantasy-score stat types.
# Change here propagates everywhere in this module.
_FANTASY_SCORE_STAT_PREFIX = "fantasy_score"


def _is_fantasy_score_stat(stat_type: str) -> bool:
    """Return True if *stat_type* is a composite fantasy-score stat."""
    return str(stat_type).startswith(_FANTASY_SCORE_STAT_PREFIX)


def find_game_context_for_player(player_team, todays_games_list):
    """
    Find tonight's game context for a given team.

    Args:
        player_team (str): Team abbreviation like 'LAL'
        todays_games_list (list of dict): Tonight's configured games

    Returns:
        dict: Game context with opponent, home/away, spread, total, game_id,
              home_team_id, away_team_id (for advanced API enrichment).
    """
    # Lazy import so the module stays importable without data dependencies
    try:
        from data.player_profile_service import _TEAM_ABBREV_TO_ID as _TID_MAP
    except Exception:
        _TID_MAP = {}

    for game in todays_games_list:
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")
        game_id = str(game.get("game_id") or game.get("GAME_ID") or "")
        # Prefer explicit NBA team IDs; fall back to static abbreviation map
        home_team_id = (
            game.get("home_team_id")
            or game.get("HOME_TEAM_ID")
            or _TID_MAP.get(str(home_team).upper())
        )
        away_team_id = (
            game.get("away_team_id")
            or game.get("VISITOR_TEAM_ID")
            or _TID_MAP.get(str(away_team).upper())
        )

        if player_team == home_team:
            return {
                "opponent": away_team,
                "is_home": True,
                "rest_days": 2,
                "game_total": game.get("game_total", 220.0),
                "vegas_spread": game.get("vegas_spread", 0.0),
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
            }
        elif player_team == away_team:
            return {
                "opponent": home_team,
                "is_home": False,
                "rest_days": 2,
                "game_total": game.get("game_total", 220.0),
                "vegas_spread": -game.get("vegas_spread", 0.0),
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
            }

    return {
        "opponent": "",
        "is_home": True,
        "rest_days": 2,
        "game_total": 220.0,
        "vegas_spread": 0.0,
        "game_id": "",
        "home_team": "",
        "away_team": "",
        "home_team_id": None,
        "away_team_id": None,
    }


# Stat emoji map
_STAT_EMOJI = {
    "points": "🏀", "rebounds": "📊", "assists": "🎯",
    "threes": "🎯", "steals": "⚡", "blocks": "🛡️", "turnovers": "❌",
}


def render_inline_breakdown_html(result, accent_color="#00D559", show_forces=True):
    """Generate an inline HTML breakdown block for any analysis card.

    Returns an HTML string containing:
    - Distribution row: P10, Median, P90, σ, Projection
    - Directional forces: OVER / UNDER force lists with star ratings
    - Score breakdown: confidence-factor progress bars

    This is used by the Best Single Bets, 50/50, and Uncertain
    sections so that every card shows the full quantitative picture
    without requiring the user to expand anything.

    Args:
        result (dict): Full analysis result from the simulation loop.
        accent_color (str): Primary accent CSS colour for headers.
        show_forces (bool): Whether to include the forces columns.

    Returns:
        str: HTML string safe for ``st.markdown(..., unsafe_allow_html=True)``.
    """
    p10 = result.get("percentile_10", 0) or 0
    p50 = result.get("percentile_50", 0) or 0
    p90 = result.get("percentile_90", 0) or 0
    std = result.get("simulated_std", result.get("std_dev", 0)) or 0
    proj = result.get("adjusted_projection", result.get("projected_stat", 0)) or 0

    try:
        p10_d = f"{float(p10):.1f}"
    except (ValueError, TypeError):
        p10_d = "—"
    try:
        p50_d = f"{float(p50):.1f}"
    except (ValueError, TypeError):
        p50_d = "—"
    try:
        p90_d = f"{float(p90):.1f}"
    except (ValueError, TypeError):
        p90_d = "—"
    try:
        std_d = f"{float(std):.1f}"
    except (ValueError, TypeError):
        std_d = "—"
    try:
        proj_d = f"{float(proj):.1f}"
    except (ValueError, TypeError):
        proj_d = "—"

    # ── distribution row ─────────────────────────────────────────
    dist_html = (
        '<div class="nah-dist-row">'
        f'<div class="nah-dist-cell"><div class="nah-dist-val nah-dist-val-p10">{p10_d}</div><div class="nah-dist-label">P10</div></div>'
        f'<div class="nah-dist-cell"><div class="nah-dist-val nah-dist-val-med">{p50_d}</div><div class="nah-dist-label">MED</div></div>'
        f'<div class="nah-dist-cell"><div class="nah-dist-val nah-dist-val-p90">{p90_d}</div><div class="nah-dist-label">P90</div></div>'
        f'<div class="nah-dist-cell"><div class="nah-dist-val nah-dist-val-std">{std_d}</div><div class="nah-dist-label">σ</div></div>'
        f'<div class="nah-dist-cell"><div class="nah-dist-val nah-dist-val-proj">{proj_d}</div><div class="nah-dist-label">Proj</div></div>'
        '</div>'
    )

    # ── directional forces ───────────────────────────────────────
    forces_html = ""
    if show_forces:
        forces = result.get("forces", {}) or {}
        over_forces = forces.get("over_forces", []) or []
        under_forces = forces.get("under_forces", []) or []

        def _force_items(flist):
            if not flist:
                return '<span class="nah-force-none">None</span>'
            parts = []
            for f in flist:
                if not isinstance(f, dict):
                    continue
                fname = str(f.get("name", "") or "")
                # Line Value badge rendered prominently at the top
                if fname in ("Low Line Value", "High Line Value"):
                    _gap = f.get("gap_pct", 0)
                    badge = get_line_value_badge_html(_gap)
                    if badge:
                        parts.insert(0, f'<div class="nah-force-item">{badge}</div>')
                    continue
                strength = max(1, min(5, round(float(f.get("strength", 1)))))
                stars = "⭐" * strength
                name = _html.escape(fname)
                parts.append(
                    f'<div class="nah-force-item">{stars} {name}</div>'
                )
            return "".join(parts) if parts else '<span class="nah-force-none">None</span>'

        forces_html = (
            '<div class="nah-forces-row">'
            '<div class="nah-force-col nah-force-col-over">'
            '<div class="nah-force-heading nah-force-heading-over">▲ MORE</div>'
            f'{_force_items(over_forces)}'
            '</div>'
            '<div class="nah-force-col nah-force-col-under">'
            '<div class="nah-force-heading nah-force-heading-under">▼ LESS</div>'
            f'{_force_items(under_forces)}'
            '</div>'
            '</div>'
        )

    # ── score breakdown bars ─────────────────────────────────────
    breakdown = result.get("score_breakdown", {}) or {}
    breakdown_html = ""
    if breakdown:
        bars = []
        for factor, score in breakdown.items():
            try:
                score_f = float(score or 0)
            except (ValueError, TypeError):
                continue
            label = _html.escape(
                factor.replace("_score", "").replace("_", " ").title()
            )
            bar_w = min(100, max(0, score_f))
            if bar_w >= 70:
                bar_c = "#00D559"
            elif bar_w >= 40:
                bar_c = "#ff5e00"
            else:
                bar_c = "#F24336"
            bars.append(
                f'<div class="nah-bkd-row">'
                f'<span class="nah-bkd-label">{label}</span>'
                f'<span class="nah-bkd-score" style="color:{accent_color};">{score_f:.0f}</span>'
                f'<div class="nah-bkd-track">'
                f'<div class="nah-bkd-fill" style="width:{bar_w:.1f}%;background:{bar_c};"></div>'
                '</div></div>'
            )
        if bars:
            breakdown_html = '<div class="nah-breakdown">' + "".join(bars) + '</div>'

    # ── Kelly TARGET ALLOCATION row ──────────────────────────────
    kelly_html = ""
    try:
        import streamlit as _st_mod
        from engine.odds_engine import calculate_fractional_kelly
        _direction = result.get("direction", "OVER")
        _book_odds = (result.get("over_odds", -110)
                      if _direction == "OVER"
                      else result.get("under_odds", -110))
        _model_prob = (result.get("probability_over", 0.5)
                       if _direction == "OVER"
                       else (1.0 - result.get("probability_over", 0.5)))
        _bankroll = float(_st_mod.session_state.get("total_bankroll", 1000.0))
        _kelly_mult = float(_st_mod.session_state.get("kelly_multiplier", 0.25))
        _kelly = calculate_fractional_kelly(_model_prob, _book_odds, _kelly_mult)
        _wager = round(_kelly["fractional_kelly"] * _bankroll, 2)
        if _wager > 0:
            _fk_pct = _kelly["fractional_kelly"] * 100
            kelly_html = (
                '<div class="nah-kelly-row">'
                '<span class="nah-kelly-label">🎯 WAGER</span>'
                f'<span class="nah-kelly-amount">${_wager:,.2f}</span>'
                f'<span class="nah-kelly-pct">{_fk_pct:.1f}% of ${_bankroll:,.0f}</span>'
                '</div>'
            )
    except Exception:
        pass

    return dist_html + forces_html + breakdown_html + kelly_html


def _build_dfs_metrics_html(result):
    """Build an HTML strip showing DFS parlay EV metrics from Phase 2.

    Renders the quarantined target-line probability, best flex tier,
    per-leg DFS edge vs breakeven, and Kelly fraction.  Returns an
    empty string when no DFS metrics are present on the result dict.

    Args:
        result (dict): Full analysis result dict (must include
            ``dfs_parlay_ev`` and/or ``dfs_breakevens`` from Phase 2).

    Returns:
        str: HTML snippet for the DFS metrics strip, or ``""``.
    """
    parlay = result.get("dfs_parlay_ev")
    if not parlay:
        return ""

    tiers = parlay.get("tiers", {})
    best_tier = parlay.get("best_tier")
    kelly_frac = parlay.get("kelly_fraction", 0.0)
    platform = result.get("dfs_platform") or result.get("platform", "")
    prob_target = result.get("probability_over_target")
    target_line = result.get("prop_target_line")

    # Build tier pills — one per tier (3-6), highlighting the best
    tier_pills = []
    for n in (3, 4, 5, 6):
        t = tiers.get(n) or tiers.get(str(n))
        if not t:
            continue
        beats = t.get("beats_breakeven", False)
        edge = t.get("edge_vs_breakeven", 0) * 100
        be_prob = t.get("breakeven", 0) * 100
        is_best = (n == best_tier)
        if is_best:
            bg = "rgba(0,213,89,0.15)"
            border = "rgba(0,213,89,0.5)"
            color = "#00D559"
        elif beats:
            bg = "rgba(0,198,255,0.08)"
            border = "rgba(0,198,255,0.25)"
            color = "#00C6FF"
        else:
            bg = "rgba(100,116,139,0.08)"
            border = "rgba(100,116,139,0.25)"
            color = "#64748b"
        pill = (
            f'<div class="nah-dfs-pill" style="background:{bg};border:1px solid {border};">'
            f'<div class="nah-dfs-pill-label" style="color:{color};">'
            f'{n}-Pick{"  ★" if is_best else ""}</div>'
            f'<div class="nah-dfs-pill-edge" style="color:{color};">'
            f'{edge:+.1f}%</div>'
            f'<div class="nah-dfs-pill-be">BE {be_prob:.0f}%</div>'
            f'</div>'
        )
        tier_pills.append(pill)

    if not tier_pills:
        return ""

    pills_html = (
        '<div class="nah-dfs-pills">'
        + "".join(tier_pills)
        + '</div>'
    )

    # Header line with platform + target probability
    header_parts = ['<span class="nah-dfs-label">📈 DFS FLEX EV</span>']
    if platform:
        header_parts.append(
            f'<span class="nah-dfs-platform">'
            f'({_html.escape(str(platform))})</span>'
        )
    if prob_target is not None and target_line is not None:
        _pt_pct = float(prob_target) * 100
        header_parts.append(
            f'<span class="nah-dfs-prob">'
            f'P(hit {float(target_line):.1f}) = {_pt_pct:.0f}%</span>'
        )

    header_html = (
        '<div class="nah-dfs-header">'
        + "".join(header_parts)
        + '</div>'
    )

    # Kelly line for DFS
    kelly_html = ""
    if best_tier and kelly_frac > 0:
        kelly_pct = kelly_frac * 100
        kelly_html = (
            f'<div class="nah-dfs-kelly">'
            f'Kelly: {kelly_pct:.2f}% · Best: {best_tier}-Pick Flex</div>'
        )

    return (
        '<div class="nah-dfs-wrap">'
        + header_html + pills_html + kelly_html +
        '</div>'
    )


def _build_result_metrics(result):
    """Build the 4-item metrics list for a QDS prop card."""
    stat_type  = result.get("stat_type", "points").lower()
    avg_map    = {
        "points": "season_pts_avg", "rebounds": "season_reb_avg",
        "assists": "season_ast_avg", "threes": "season_threes_avg",
    }
    season_avg = result.get(avg_map.get(stat_type, ""), 0) or 0
    line       = result.get("line", 0)
    projection = result.get("adjusted_projection") or result.get("projected_stat") or 0
    edge_pct   = result.get("edge_percentage", 0)
    defense_f  = result.get("overall_adjustment", 1.0)
    form_ratio = result.get("recent_form_ratio")

    # Situational: season avg vs line
    line_diff  = round(float(line) - float(season_avg), 1)
    sit_val    = (
        f"Avg {season_avg:.1f} / Line {line} "
        f"({'▲' if line_diff > 0 else '▼'}{abs(line_diff):.1f})"
    )

    # Archetype matchup: defense factor as multiplier
    matchup_val = (
        f"{'Favorable' if float(defense_f) < 1.0 else 'Tough'} "
        f"({float(defense_f):.2f}x)"
    )

    # Form: recent form ratio
    if form_ratio is not None:
        form_label = "Hot 🔥" if float(form_ratio) > 1.05 else (
            "Cold 🧊" if float(form_ratio) < 0.95 else "Neutral"
        )
        form_val = f"{float(form_ratio):.2f}x ({form_label})"
    else:
        form_val = "N/A"

    # Edge vs line
    edge_sign = "+" if float(edge_pct) >= 0 else ""
    edge_val  = f"{edge_sign}{float(edge_pct):.1f}%"

    return [
        {"icon": "📊", "label": "Situational",      "value": sit_val},
        {"icon": "🛡️", "label": "Archetype Matchup", "value": matchup_val},
        {"icon": "🔥", "label": "Form (5-game)",     "value": form_val},
        {"icon": "⚡", "label": "Edge vs Line",       "value": edge_val},
    ]


def _build_bonus_factors(result):
    """Build the bonus factors list for a QDS prop card."""
    bonus = []
    over_forces  = result.get("forces", {}).get("over_forces",  [])
    under_forces = result.get("forces", {}).get("under_forces", [])
    direction    = result.get("direction", "OVER")
    forces_to_show = over_forces if direction == "OVER" else under_forces
    for f in forces_to_show[:4]:
        lbl  = f.get("name", f.get("label", f.get("factor", "")))
        desc = f.get("description", f.get("detail", ""))
        if lbl:
            bonus.append(f"{lbl}" + (f" — {desc}" if desc else ""))

    # Append traps / warnings as bonus notes
    trap = result.get("trap_line_result", {})
    if trap and trap.get("is_trap"):
        bonus.append(f"⚠️ {trap.get('warning_message', 'Possible trap line')}")

    ls_force = result.get("line_sharpness_force")
    if ls_force:
        bonus.append(f"📐 Sharp line: {ls_force.get('description', '')}")

    teammate_notes = result.get("teammate_out_notes", [])
    for note in teammate_notes[:2]:
        bonus.append(f"👥 {note}")

    return bonus[:6]  # cap at 6 items


def _format_record(wins, losses):
    """Return a ``'W-L'`` string or ``''`` when data is missing/zero."""
    if wins is not None and losses is not None and (wins > 0 or losses > 0):
        return f"{wins}-{losses}"
    return ""


def _group_picks_by_game(picks):
    """Group a list of raw pick dicts by game matchup.

    Returns a dict mapping matchup labels (e.g. ``'BOS @ LAL'``) to dicts
    with ``"picks"`` (list of pick dicts) and ``"meta"`` (game metadata
    including team abbreviations, W-L records, and conf rank).
    Falls back to the player's team if no game context is available.
    """
    import streamlit as st

    groups: dict[str, dict] = {}
    todays_games = st.session_state.get("todays_games") or []

    # Build team → matchup label mapping + game metadata
    team_to_game: dict[str, str] = {}
    game_meta: dict[str, dict] = {}  # matchup_label → metadata
    for g in todays_games:
        ht = (g.get("home_team") or "").upper().strip()
        at = (g.get("away_team") or "").upper().strip()
        if ht and at:
            label = f"{at} @ {ht}"
            team_to_game[ht] = label
            team_to_game[at] = label

            hw = g.get("home_wins")
            hl = g.get("home_losses")
            aw = g.get("away_wins")
            al = g.get("away_losses")
            game_meta[label] = {
                "home_team": ht,
                "away_team": at,
                "home_record": _format_record(hw, hl),
                "away_record": _format_record(aw, al),
                "home_conf_rank": g.get("home_conf_rank", 0),
                "away_conf_rank": g.get("away_conf_rank", 0),
            }

    for p in picks:
        team = (
            p.get("team", "") or p.get("player_team", "")
        ).upper().strip()
        matchup = team_to_game.get(team, team or "Other")
        if matchup not in groups:
            groups[matchup] = {"picks": [], "meta": game_meta.get(matchup, {})}
        groups[matchup]["picks"].append(p)

    return groups


def _build_entry_strategy(results):
    """Build entry strategy matrix entries from top results (2–6 legs).

    Enforces unique players per parlay (no repeating the same player on
    multiple props) and excludes fantasy-score variants from parlay legs.
    """
    top = [
        r for r in results
        if not r.get("should_avoid", False)
        and not r.get("player_is_out", False)
        and abs(r.get("edge_percentage", 0)) >= 3.0
        # Exclude fantasy-score composite stats from parlay legs
        and not _is_fantasy_score_stat(r.get("stat_type", ""))
    ]
    top = sorted(top, key=lambda r: r.get("confidence_score", 0), reverse=True)

    _LEG_LABELS = {
        2: "Power Play (2-Leg)",
        3: "Triple Threat (3-Leg)",
        4: "Quad Stack (4-Leg)",
        5: "High Roller (5-Leg)",
        6: "Max Entry (6-Leg)",
    }
    _LEG_STRATEGIES = {
        2: "Highest-confidence 2-leg — best win rate.",
        3: "Top-3 picks, balanced risk vs. reward.",
        4: "Aggressive 4-leg for elevated payout.",
        5: "High ceiling, diversified 5-leg.",
        6: "Max multiplier — only for high-edge slates.",
    }

    def _pick_unique_players(candidates, num_legs):
        """Return up to num_legs picks with no repeated players.

        Enforces team diversity: picks from at least two different
        teams when the candidate pool spans multiple teams, so parlays
        include bets from both sides of a matchup.
        """
        seen_players: set = set()
        selected = []
        for r in candidates:
            pname = r.get("player_name", "")
            if pname and pname in seen_players:
                continue
            seen_players.add(pname)
            selected.append(r)
            if len(selected) == num_legs:
                break

        # ── Team diversity check ────────────────────────────────
        # If all selected picks are from one team but the candidate
        # pool contains players from other teams, swap the weakest
        # pick for the best pick from a different team.
        if len(selected) >= 2:
            teams_in = {(p.get("team") or p.get("player_team") or "").upper().strip()
                        for p in selected}
            teams_in.discard("")
            if len(teams_in) == 1:
                only_team = next(iter(teams_in))
                # Find best unused candidate from a different team
                used_names = {p.get("player_name", "") for p in selected}
                for alt in candidates:
                    alt_team = (alt.get("team") or alt.get("player_team") or "").upper().strip()
                    alt_name = alt.get("player_name", "")
                    if alt_team and alt_team != only_team and alt_name not in used_names:
                        # Replace the last (weakest) pick with this one
                        selected[-1] = alt
                        break

        return selected

    entries = []
    for num_legs in range(2, 7):
        picks = _pick_unique_players(top, num_legs)
        if len(picks) < num_legs:
            continue
        avg_conf = round(sum(r.get("confidence_score", 0) for r in picks) / num_legs, 1)

        # Combined probability (independent legs)
        combined_prob = 1.0
        for p in picks:
            prob = p.get("confidence_score", 50) / 100.0
            combined_prob *= max(0.01, min(0.99, prob))
        combined_prob_pct = round(combined_prob * 100, 1)

        avg_edge = round(
            sum(p.get("edge_percentage", 0) for p in picks) / num_legs, 1
        )

        # Reasoning tags
        reasons = []
        if all(p.get("edge_percentage", 0) > 5 for p in picks):
            reasons.append("All legs 5%+ edge")
        if any(p.get("tier") == "Platinum" for p in picks):
            reasons.append("Anchored by Platinum pick")
        teams_in_parlay = {p.get("team", p.get("player_team", "")) for p in picks}
        if len(teams_in_parlay) >= num_legs:
            reasons.append("Diversified across games")
        reasons.append("Unique players per leg")

        entries.append({
            "combo_type":    _LEG_LABELS.get(num_legs, f"{num_legs}-Leg"),
            "num_legs":      num_legs,
            "picks": [
                f"{r['player_name']} {r['direction']} {r['line']} {r['stat_type'].title()}"
                for r in picks
            ],
            "safe_avg":      f"{avg_conf:.1f}",
            "combined_prob": combined_prob_pct,
            "avg_edge":      avg_edge,
            "strategy":      _LEG_STRATEGIES.get(num_legs, ""),
            "reasons":       reasons,
            "raw_picks":     picks,
            "game_groups":   _group_picks_by_game(picks),
        })

    return entries


def _render_qds_full_breakdown_html(result):
    """Generate QDS-styled HTML for the full breakdown section.

    Uses the same colour palette as the Game Report's QDS dark-card CSS:
    background #14192b, primary #ff5e00, cyan #00D559, text #EEF0F6.
    Wrapped in a native <details>/<summary> element so it collapses
    inside the existing dark-card visual context without a plain Streamlit
    expander frame breaking the design.

    Rendered via st.html() which auto-sizes the iframe to fit the content,
    avoiding both blank space and content cutoff.

    Args:
        result (dict): Full analysis result from the simulation loop.

    Returns:
        str: Full standalone HTML document ready for st.html().
    """
    player = _html.escape(str(result.get("player_name", "Unknown")))
    stat   = _html.escape(str(result.get("stat_type", "points")).title())

    p10 = result.get("percentile_10", 0) or 0
    p50 = result.get("percentile_50", 0) or 0
    p90 = result.get("percentile_90", 0) or 0
    std = result.get("simulated_std", result.get("std_dev", 0)) or 0

    over_forces  = result.get("forces", {}).get("over_forces",  []) or []
    under_forces = result.get("forces", {}).get("under_forces", []) or []
    breakdown    = result.get("score_breakdown", {}) or {}
    explanation  = result.get("explanation") or {}
    should_avoid = result.get("should_avoid", False)
    avoid_reasons = result.get("avoid_reasons", []) or []

    # ── Forces HTML ──────────────────────────────────────────────
    def _forces_html(forces):
        if not forces:
            return '<span style="color:#A0AABE;font-size:0.85rem;">None detected</span>'
        parts = []
        for f in (forces or []):
            if not isinstance(f, dict):
                continue
            stars = "⭐" * max(1, min(5, round(float(f.get("strength", 1) or 1))))
            name  = _html.escape(str(f.get("name", "") or ""))
            desc  = _html.escape(str(f.get("description", "") or ""))
            parts.append(
                '<div style="margin-bottom:6px;padding:4px 0;">'
                '<span style="color:#00D559;">' + stars + '</span> '
                '<strong style="color:#ff5e00;">' + name + '</strong><br>'
                '<span style="color:#EEF0F6;font-size:0.8rem;">' + desc + '</span>'
                '</div>'
            )
        return "".join(parts) if parts else '<span style="color:#A0AABE;font-size:0.85rem;">None detected</span>'

    # ── Score-breakdown bars ─────────────────────────────────────
    breakdown_rows = []
    if breakdown:
        for factor, score in breakdown.items():
            label = _html.escape(
                factor.replace("_score", "").replace("_", " ").title()
            )
            bar_w = min(100, max(0, float(score or 0)))
            if bar_w >= 70:
                bar_c = "#00D559"
            elif bar_w >= 40:
                bar_c = "#ff5e00"
            else:
                bar_c = "#F24336"
            bar_c_fade = bar_c + "88"
            breakdown_rows.append(
                '<div style="margin-bottom:8px;">'
                '<div style="display:flex;justify-content:space-between;font-size:0.8rem;color:#EEF0F6;margin-bottom:3px;">'
                '<span>' + label + '</span>'
                '<span style="color:#ff5e00;font-weight:600;">' + f"{score:.0f}" + '/100</span>'
                '</div>'
                '<div style="height:6px;background:#161B27;border-radius:3px;">'
                '<div style="height:6px;width:' + f"{bar_w:.1f}" + '%;background:linear-gradient(90deg,' + bar_c + ',' + bar_c_fade + ');border-radius:3px;"></div>'
                '</div></div>'
            )
    breakdown_html = ""
    if breakdown_rows:
        breakdown_html = (
            '<div style="margin-bottom:15px;">'
            '<div style="color:#ff5e00;font-weight:600;font-size:0.9rem;margin-bottom:10px;">🔬 Confidence Score Breakdown</div>'
            + "".join(breakdown_rows)
            + '</div>'
        )

    # ── Explanation sections ─────────────────────────────────────
    explain_parts = []
    if explanation:
        sections = [
            ("📊 Season Avg vs Line",  "average_vs_line"),
            ("🛡️ Matchup Analysis",    "matchup_explanation"),
            ("⚡ Game Pace",            "pace_explanation"),
            ("🏠 Home/Away",           "home_away_explanation"),
            ("😴 Rest Days",           "rest_explanation"),
            ("💰 Vegas Lines",         "vegas_explanation"),
        ]
        for label, key in sections:
            text = explanation.get(key, "")
            if text:
                explain_parts.append(
                    '<div style="margin-bottom:8px;padding:8px;background:rgba(20,25,43,0.5);border-radius:4px;border-left:2px solid #ff5e00;">'
                    '<div style="color:#ff5e00;font-weight:600;font-size:0.8rem;">' + label + '</div>'
                    '<div style="color:#EEF0F6;font-size:0.85rem;margin-top:4px;">' + _html.escape(str(text)) + '</div>'
                    '</div>'
                )
    explain_html = "".join(explain_parts)

    # ── Avoid warning ────────────────────────────────────────────
    avoid_html = ""
    if should_avoid and avoid_reasons:
        reasons_str = _html.escape(" | ".join(str(r) for r in avoid_reasons))
        avoid_html = (
            '<div style="margin-bottom:10px;padding:8px 12px;background:rgba(255,68,68,0.1);border-radius:6px;border-left:3px solid #F24336;color:#F24336;font-size:0.85rem;">'
            '⚠️ <strong>Avoid List:</strong> ' + reasons_str +
            '</div>'
        )

    # ── Distribution grid (table-based for universal compatibility) ─
    dist_html = (
        '<div style="margin-bottom:15px;">'
        '<div style="color:#ff5e00;font-weight:600;font-size:0.9rem;margin-bottom:8px;">📊 Distribution</div>'
        '<table style="width:100%;border-collapse:separate;border-spacing:4px;">'
        '<tr>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#A0AABE;font-size:0.75rem;">10th pct</div>'
        '<div style="color:#ff5e00;font-weight:700;font-size:1rem;">' + f"{p10:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#A0AABE;font-size:0.75rem;">Median</div>'
        '<div style="color:#00D559;font-weight:700;font-size:1rem;">' + f"{p50:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#A0AABE;font-size:0.75rem;">90th pct</div>'
        '<div style="color:#ff5e00;font-weight:700;font-size:1rem;">' + f"{p90:.1f}" + '</div>'
        '</td>'
        '<td style="text-align:center;padding:8px;background:rgba(20,25,43,0.7);border-radius:6px;width:25%;">'
        '<div style="color:#A0AABE;font-size:0.75rem;">Std Dev</div>'
        '<div style="color:#ffffff;font-weight:700;font-size:1rem;">' + f"{std:.1f}" + '</div>'
        '</td>'
        '</tr>'
        '</table>'
        '</div>'
    )

    # ── Forces grid (table-based for universal compatibility) ────
    forces_html = (
        '<table style="width:100%;border-collapse:separate;border-spacing:8px;margin-bottom:15px;">'
        '<tr>'
        '<td style="padding:12px;background:rgba(0,213,89,0.05);border-radius:6px;border-left:3px solid #00D559;vertical-align:top;width:50%;">'
        '<div style="color:#00D559;font-weight:600;font-size:0.85rem;margin-bottom:8px;">🔵 Forces MORE</div>'
        + _forces_html(over_forces) +
        '</td>'
        '<td style="padding:12px;background:rgba(255,94,0,0.05);border-radius:6px;border-left:3px solid #ff5e00;vertical-align:top;width:50%;">'
        '<div style="color:#ff5e00;font-weight:600;font-size:0.85rem;margin-bottom:8px;">🔴 Forces LESS</div>'
        + _forces_html(under_forces) +
        '</td>'
        '</tr>'
        '</table>'
    )

    # ── Full breakdown wrapped in <details>/<summary> ────────────
    inner_content = dist_html + forces_html + avoid_html + breakdown_html + explain_html

    body_html = (
        '<details style="margin-top:4px;">'
        '<summary style="cursor:pointer;padding:10px 14px;'
        'background:#14192b;border:1px solid rgba(255,94,0,0.2);border-radius:6px;'
        'color:#ff5e00;font-weight:600;font-size:0.9rem;list-style:none;'
        'user-select:none;">'
        '&#128202; Full Breakdown &#8212; ' + player + ' ' + stat +
        '</summary>'
        '<div style="padding:14px 15px 16px;background:#0f1424;border:1px solid rgba(255,94,0,0.15);'
        'border-top:none;border-radius:0 0 6px 6px;color:#EEF0F6;font-size:0.85rem;line-height:1.7;">'
        + inner_content +
        '</div>'
        '</details>'
    )

    # Wrap in a full standalone HTML document so st.html() renders it correctly.
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<style>'
        'body{margin:0;padding:0;background:transparent;font-family:Inter,sans-serif;}'
        'details summary::-webkit-details-marker{display:none;}'
        '</style></head><body>'
        + body_html +
        '</body></html>'
    )


# ============================================================
# SECTION: Player Intelligence Rendering Helpers
# These helpers enrich each analysis card with live form data,
# injury status, and matchup context sourced from the new
# engine/player_intelligence.py module.
# ============================================================

# Track whether we've already injected the intel CSS in this run.
_intel_css_injected: set = set()


def _inject_intel_css() -> None:
    """Inject player intelligence CSS once per Streamlit session."""
    if "injected" not in _intel_css_injected:
        st.markdown(get_player_intel_css(), unsafe_allow_html=True)
        _intel_css_injected.add("injected")


def render_player_intel_strip(
    result: dict,
    injury_status_map: dict,
    game_logs: list | None = None,
) -> None:
    """Render a compact player intelligence strip beneath the main prop card.

    Shows:
    - Availability / injury status badge
    - Form dots (last 5 games hit/miss vs prop line)
    - Hit-rate percentage
    - Matchup grade badge (when available from result)
    - Season-avg edge vs line

    Args:
        result:             Full analysis result dict (from the simulation loop).
        injury_status_map:  Dict loaded from data/injury_status.json.
        game_logs:          Optional list of recent game-log dicts.  When provided
                            form dots are computed from actual game results instead
                            of the cached form ratio in *result*.
    """
    if not _PLAYER_INTEL_AVAILABLE:
        return

    _inject_intel_css()

    player = result.get("player_name", "")
    stat   = (result.get("stat_type") or "points").lower()
    line   = float(result.get("line") or 0)

    # ── Availability badge ────────────────────────────────────────
    avail = get_availability_context(player, injury_status_map)
    avail_html = get_availability_badge_html(
        avail["badge_label"], avail["badge_class"], avail["injury_note"]
    )

    # ── Form dots ─────────────────────────────────────────────────
    form_results: list = []
    form_label = "No Data"
    hit_rate = 0.0
    streak_label = ""

    if game_logs and line > 0:
        form_data = get_recent_form_vs_line(game_logs, stat, line)
        form_results = form_data.get("results", [])
        form_label   = form_data.get("form_label", "No Data")
        hit_rate     = form_data.get("hit_rate", 0.0)
        streak       = form_data.get("streak", {})
        if streak.get("active"):
            streak_label = streak.get("label", "")
    elif result.get("recent_form_ratio") is not None:
        # Fall back to projection-derived form label
        form_ratio = float(result.get("recent_form_ratio", 1.0))
        if form_ratio > 1.05:
            form_label = "Hot 🔥"
        elif form_ratio < 0.95:
            form_label = "Cold 🧊"
        else:
            form_label = "Neutral ➡️"

    form_html = get_form_dots_html(form_results, window=5, prop_line=line)

    # ── Matchup grade ──────────────────────────────────────────────
    # result may contain 'matchup_grade' if we populated it upstream
    grade_info = result.get("matchup_grade") or {}
    grade = grade_info.get("grade", "N/A")
    grade_label = grade_info.get("label", "No Data")
    grade_cls   = grade_info.get("color_class", "grade-na")
    grade_html  = get_matchup_grade_badge_html(grade, grade_label, grade_cls)

    # ── Season avg edge ───────────────────────────────────────────
    season_avg = 0.0
    _stat_avg_key = f"{stat}_avg"
    _alt_avg_keys = {
        "points": "season_pts_avg", "rebounds": "season_reb_avg",
        "assists": "season_ast_avg",
    }
    try:
        season_avg = float(
            result.get(_stat_avg_key)
            or result.get(_alt_avg_keys.get(stat, ""), 0)
            or 0
        )
    except (TypeError, ValueError):
        season_avg = 0.0

    edge_pct = ((season_avg - line) / line * 100.0) if line > 0 and season_avg > 0 else 0.0
    direction = "OVER" if edge_pct >= 0 else "UNDER"

    # ── Build and render strip ────────────────────────────────────
    strip_html = get_intel_strip_html(
        availability_html=avail_html,
        form_html=form_html,
        hit_rate_pct=hit_rate,
        form_label=form_label,
        grade_html=grade_html,
        edge_pct=round(edge_pct, 1),
        direction=direction,
        streak_label=streak_label,
    )
    st.markdown(strip_html, unsafe_allow_html=True)


def render_recent_form_section(
    player_name: str,
    stat_type: str,
    prop_line: float,
    game_logs: list,
    window: int = 10,
) -> None:
    """Render an expandable recent form section with per-game hit/miss table.

    Shows the last *window* games with the actual stat value, whether the
    player hit the over, and the margin vs the prop line.

    This section is shown inside the SAFE Score™ Breakdown expander.
    """
    if not _PLAYER_INTEL_AVAILABLE or not game_logs or prop_line <= 0:
        return

    form_data = get_recent_form_vs_line(game_logs, stat_type, prop_line, window=window)
    if not form_data.get("sufficient_data"):
        return

    results = form_data.get("results", [])
    hit_rate = form_data.get("hit_rate", 0.0)
    hits = form_data.get("hits", 0)
    total = len(results)
    form_label = form_data.get("form_label", "")

    form_color = "#ff7b2e" if "Hot" in form_label else "#5bc8f5" if "Cold" in form_label else "#6B7A9A"

    st.markdown(
        f'<div style="color:{form_color};font-weight:700;font-size:0.82rem;margin:8px 0 4px;">'
        f'📈 Recent Form vs Line {prop_line}: '
        f'{hits}/{total} Over ({hit_rate * 100:.0f}%) — {form_label}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Table rows
    rows_html = []
    for i, r in enumerate(results):
        hit_color = "#00d084" if r["hit"] else "#ff4d4d"
        hit_text  = "✅ HIT" if r["hit"] else "❌ MISS"
        sign = "+" if r["margin"] >= 0 else ""
        matchup_str = r.get("matchup", "")
        rows_html.append(
            f'<tr style="background:{"rgba(0,208,132,0.06)" if r["hit"] else "rgba(255,77,77,0.06)"};">'
            f'<td style="padding:4px 8px;color:#6B7A9A;font-size:0.75rem;">{r.get("date","")}</td>'
            f'<td style="padding:4px 8px;color:#a0b4c8;font-size:0.75rem;">{matchup_str}</td>'
            f'<td style="padding:4px 8px;color:#e8f4ff;font-weight:600;text-align:center;">{r["value"]}</td>'
            f'<td style="padding:4px 8px;color:{hit_color};font-weight:700;text-align:center;">{hit_text}</td>'
            f'<td style="padding:4px 8px;color:{hit_color};text-align:center;font-size:0.78rem;">{sign}{r["margin"]}</td>'
            f'</tr>'
        )

    table_html = (
        '<table style="width:100%;border-collapse:collapse;margin-bottom:8px;">'
        '<thead><tr>'
        '<th style="text-align:left;padding:4px 8px;color:#5a6e8a;font-size:0.72rem;">Date</th>'
        '<th style="text-align:left;padding:4px 8px;color:#5a6e8a;font-size:0.72rem;">Matchup</th>'
        '<th style="text-align:center;padding:4px 8px;color:#5a6e8a;font-size:0.72rem;">Value</th>'
        '<th style="text-align:center;padding:4px 8px;color:#5a6e8a;font-size:0.72rem;">Result</th>'
        '<th style="text-align:center;padding:4px 8px;color:#5a6e8a;font-size:0.72rem;">vs Line</th>'
        '</tr></thead>'
        '<tbody>' + "".join(rows_html) + '</tbody>'
        '</table>'
    )

    st.markdown(table_html, unsafe_allow_html=True)

    # Streak banner
    streak = form_data.get("streak", {})
    if streak.get("active") and streak.get("count", 0) >= 3:
        banner_cls = "streak-banner-hot" if streak["type"] == "hit" else "streak-banner-cold"
        st.markdown(
            f'<div class="{banner_cls}">{_html.escape(streak.get("label", ""))}</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# END SECTION: Player Intelligence Rendering Helpers
# ============================================================


def display_prop_analysis_card_qds(result):
    """
    Display a QDS-styled analysis card for one prop result.

    OUT / IR players show a prominent error banner and return early.
    Questionable / Day-to-Day players show a warning.
    All other players get the full QDS prop card with metrics grid,
    confidence bar, bonus factors, and an Add to Entry button.

    Args:
        result (dict): Full analysis result from the simulation loop.
    """
    player   = result.get("player_name", "Unknown")
    stat     = result.get("stat_type", "").lower()
    line     = result.get("line", 0)
    direction = result.get("direction", "OVER")
    confidence = result.get("confidence_score", 50)
    should_avoid = result.get("should_avoid", False)
    platform = result.get("platform", "")
    team     = result.get("player_team", result.get("team", ""))

    # ── OUT / Injured Reserve ────────────────────────────────────
    if result.get("player_is_out", False):
        player_status = result.get("player_status", "Out")
        status_note   = result.get("player_status_note", "")
        st.error(
            f"❌ **{player}** is **{player_status}** — prop skipped. "
            + (f"_{status_note}_" if status_note else "")
            + "\n\nRemove this prop from your list."
        )
        return

    # ── Warn for Questionable / Day-to-Day ──────────────────────
    player_status = result.get("player_status") or (
        get_player_status(player, st.session_state.get("injury_status_map", {}))
        .get("status", "Active")
    )
    if player_status in ("Questionable", "Day-to-Day", "GTD", "Doubtful"):
        note = result.get("player_status_note", "")
        st.warning(
            f"⚠️ **{player}** is listed as **{player_status}**"
            + (f" — {note}" if note else "")
            + ". Monitor status before betting."
        )

    # ── Tier badge icon ──────────────────────────────────────────
    tier = result.get("tier", "Bronze")
    tier_icon_map = {"Platinum": "💎", "Gold": "🔒", "Silver": "✓", "Bronze": "⭐"}
    tier_icon = tier_icon_map.get(tier, "⭐")

    # ── Bet Classification badge ─────────────────────────────────
    bet_type       = result.get("bet_type", "normal")
    bet_type_emoji = result.get("bet_type_emoji", "")
    bet_type_label = result.get("bet_type_label", "")
    bet_type_reasons = result.get("bet_type_reasons", []) or []

    # ── Risk flags warning bar ────────────────────────────────────
    _risk_flags = result.get("risk_flags", [])
    if _risk_flags:
        _risk_str = " | ".join(_risk_flags[:2])
        st.markdown(
            f'<div style="background:rgba(255,193,7,0.10);border:1px solid #ffc107;border-radius:5px;'
            f'padding:5px 12px;margin-bottom:6px;font-size:0.78rem;">'
            f'<span style="color:#ffc107;font-weight:600;">⚠️ RISK FLAGS: </span>'
            f'<span style="color:#ffe082;">{_html.escape(_risk_str)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── True odds / implied probability display ───────────────────
    _over_odds  = result.get("over_odds",  -110)
    _under_odds = result.get("under_odds", -110)
    _odds_for_dir = _over_odds if direction == "OVER" else _under_odds
    if _odds_for_dir and _odds_for_dir != 0:
        _odds_str = f"+{_odds_for_dir}" if int(_odds_for_dir) > 0 else str(int(_odds_for_dir))
        # Implied probability from odds — use the canonical function from odds_engine
        _implied_prob = _odds_to_implied_prob(_odds_for_dir) * 100.0
        _model_prob = (result.get("probability_over", 0.5) if direction == "OVER"
                       else 1.0 - result.get("probability_over", 0.5)) * 100.0
        _true_edge_pct = _model_prob - _implied_prob
        _proj_val = result.get("adjusted_projection", 0)

        # Minutes trend indicator (from Feature 6 rotation tracking)
        _mt_indicator = result.get("minutes_trend_indicator", "")
        _mt_info      = result.get("minutes_trend")
        _mt_extra = ""
        if _mt_info and _mt_info.get("games_analyzed", 0) > 0 and _mt_indicator in ("🔺", "🔻"):
            _mt_recent = _mt_info.get("recent_avg_minutes", 0)
            _mt_season = _mt_info.get("season_avg_minutes", 0)
            _mt_dir    = "up" if _mt_indicator == "🔺" else "down"
            _mt_extra  = (
                f' &nbsp;|&nbsp; <span style="color:#{"69f0ae" if _mt_dir == "up" else "ff9966"};'
                f'font-weight:600;">'
                f'{_mt_indicator} Min Trend: {_mt_recent:.0f} vs {_mt_season:.0f} avg</span>'
            )

        st.markdown(
            f'<div style="background:rgba(0,213,89,0.05);border:1px solid rgba(0,213,89,0.2);'
            f'border-radius:6px;padding:6px 12px;margin-bottom:6px;font-size:0.78rem;color:#a0c0d8;">'
            f'<span style="color:#00D559;font-weight:600;">Platform Line:</span> '
            f'{direction.title()} {line} &nbsp;|&nbsp; '
            f'<span style="color:#00D559;font-weight:600;">Odds:</span> {_odds_str} &nbsp;|&nbsp; '
            f'<span style="color:#00D559;font-weight:600;">Model Proj:</span> {_proj_val:.1f} &nbsp;|&nbsp; '
            f'<span style="color:#00D559;font-weight:600;">Breakeven:</span> {_implied_prob:.1f}% &nbsp;|&nbsp; '
            f'<span style="color:#{"4caf50" if _true_edge_pct > 0 else "ff4444"};font-weight:600;">'
            f'True Edge: {_true_edge_pct:+.1f}%</span>'
            + _mt_extra +
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Prop description string ──────────────────────────────────
    stat_emoji = _STAT_EMOJI.get(stat, "🏀")
    dir_label  = "More" if direction == "OVER" else "Less"
    prop_text  = f"{stat_emoji} {dir_label} {line} {stat.title()}"

    # ── Ensemble / model badges ───────────────────────────────────
    _ensemble_used    = result.get("ensemble_used", False)
    _ensemble_models  = result.get("ensemble_models", 1)
    _ens_disagree     = result.get("ensemble_disagreement", "")
    _projected_mins   = result.get("projected_minutes")
    _season_avg_show  = float(result.get(f"season_{stat}_avg",
                          result.get(f"{stat}_avg", 0) or 0))
    # Derive the per-stat season avg from the player's stored data
    if _season_avg_show == 0:
        _stat_avg_key_map = {
            "points": "season_pts_avg", "rebounds": "season_reb_avg",
            "assists": "season_ast_avg",
        }
        _season_avg_show = float(result.get(_stat_avg_key_map.get(stat, ""), 0) or 0)

    _meta_badges = []
    # ── Win Score badge ──────────────────────────────────────────
    _cws = result.get("composite_win_score", 0)
    _cws_grade = result.get("win_score_grade", "")
    _cws_label = result.get("win_score_label", "")
    if _cws > 0 and _cws_grade:
        _cws_color_map = {
            "A+": "#00e676", "A": "#69f0ae", "B+": "#29b6f6",
            "B": "#4fc3f7", "C": "#ffa726", "D": "#ff7043", "F": "#ef5350",
        }
        _cws_color = _cws_color_map.get(_cws_grade, "#90a4ae")
        _cws_bg = f"rgba({','.join(str(int(_cws_color.lstrip('#')[i:i+2], 16)) for i in (0,2,4))},0.12)"
        _meta_badges.append(
            f'<span style="background:{_cws_bg};color:{_cws_color};padding:2px 7px;'
            f'border-radius:4px;font-size:0.72rem;font-weight:700;border:1px solid {_cws_color}40;">'
            f'🎯 Win Score: {_cws:.0f} ({_cws_grade})</span>'
        )
    if _ensemble_used and _ensemble_models >= 2:
        _meta_badges.append(
            f'<span style="background:rgba(0,168,255,0.15);color:#29b6f6;padding:2px 7px;'
            f'border-radius:4px;font-size:0.72rem;font-weight:700;border:1px solid rgba(0,168,255,0.3);">'
            f'🧬 {_ensemble_models}-Model Ensemble</span>'
        )
    if _projected_mins:
        _meta_badges.append(
            f'<span style="background:rgba(0,200,83,0.12);color:#69f0ae;padding:2px 7px;'
            f'border-radius:4px;font-size:0.72rem;font-weight:700;border:1px solid rgba(0,200,83,0.2);">'
            f'⏱️ Proj. {_projected_mins:.0f} min</span>'
        )
    if _season_avg_show > 0:
        _gap = line - _season_avg_show
        _gap_color = "#F24336" if _gap > 0 else "#69f0ae"
        _meta_badges.append(
            f'<span style="background:rgba(255,255,255,0.04);color:{_gap_color};padding:2px 7px;'
            f'border-radius:4px;font-size:0.72rem;border:1px solid rgba(255,255,255,0.08);">'
            f'Season avg: {_season_avg_show:.1f} · Line gap: {_gap:+.1f}</span>'
        )
    if _ens_disagree and ("disagree" in _ens_disagree.lower() or "⚠️" in _ens_disagree):
        _meta_badges.append(
            f'<span style="background:rgba(255,165,0,0.12);color:#ffa726;padding:2px 7px;'
            f'border-radius:4px;font-size:0.72rem;font-weight:700;border:1px solid rgba(255,165,0,0.25);">'
            f'⚠️ Model Disagree</span>'
        )
    if _meta_badges:
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px;">'
            + "".join(_meta_badges)
            + f'</div>',
            unsafe_allow_html=True,
        )

    # ── Build metrics & bonus factors ────────────────────────────
    metrics       = _build_result_metrics(result)
    bonus_factors = _build_bonus_factors(result)

    # ── Render QDS prop card ─────────────────────────────────────
    player_id = result.get("player_id", "") or ""
    _opponent = result.get("opponent", "") or ""
    _is_home = result.get("is_home")
    _season_stats = {
        "pts_avg": float(result.get("season_pts_avg", result.get("points_avg", 0)) or 0),
        "reb_avg": float(result.get("season_reb_avg", result.get("rebounds_avg", 0)) or 0),
        "ast_avg": float(result.get("season_ast_avg", result.get("assists_avg", 0)) or 0),
    }
    card_html = get_qds_prop_card_html(
        player_name=player,
        team=team,
        prop_text=prop_text,
        score=confidence,
        tier=tier,
        metrics=metrics,
        bonus_factors=bonus_factors,
        player_id=player_id if player_id else None,
        opponent=_opponent if _opponent else None,
        is_home=_is_home,
        season_stats=_season_stats,
        bet_direction=direction,
    )
    st.markdown(card_html, unsafe_allow_html=True)

    # ── Player Intelligence Strip (form dots + availability + grade) ─
    _injury_map = st.session_state.get("injury_status_map", {})
    _recent_logs = result.get("recent_form_games") or []
    render_player_intel_strip(result, _injury_map, game_logs=_recent_logs)

    # ── Confidence bar (standalone) ──────────────────────────────
    conf_bar_html = get_qds_confidence_bar_html(
        label=f"{player} — {prop_text}",
        percentage=confidence,
        tier_icon=tier_icon,
    )
    # (Already embedded in prop card — skip duplicate)

    # ── Add to Entry button ──────────────────────────────────────
    pick_key = f"{player}_{stat}_{line}_{direction}"
    selected_picks = st.session_state.get("selected_picks", [])
    already_added  = any(p.get("key") == pick_key for p in selected_picks)

    _btn_col, _detail_col = st.columns([1, 2])
    with _btn_col:
        btn_label    = "✅ Added" if already_added else "➕ Add to Entry"
        btn_disabled = already_added
        if st.button(btn_label, key=f"add_pick_{pick_key}", disabled=btn_disabled):
            st.session_state["selected_picks"].append({
                "key":             pick_key,
                "player_name":     player,
                "stat_type":       stat,
                "line":            line,
                "direction":       direction,
                "confidence_score": confidence,
                "tier":            tier,
                "tier_emoji":      tier_icon,
                "platform":        platform,
                "edge_percentage": result.get("edge_percentage", 0),
            })
            st.rerun()

    with _detail_col:
        # Quick stats pill row
        _prob_pct = result.get("probability_over", 0.5) * 100 if direction == "OVER" else (1 - result.get("probability_over", 0.5)) * 100
        _edge_pct = result.get("edge_percentage", 0)
        _proj_val = result.get("adjusted_projection", 0)
        _gp = result.get("games_played")
        _gp_str = f" · {_gp}G" if _gp else ""
        st.caption(
            f"📊 Prob: {_prob_pct:.0f}% · Edge: {_edge_pct:+.1f}% · "
            f"Proj: {_proj_val:.1f}{_gp_str}"
        )

        # ── [TARGET ALLOCATION] — Kelly Criterion wager ──────────
        try:
            from engine.odds_engine import calculate_fractional_kelly, calculate_fair_odds_from_simulation
            _bankroll = float(st.session_state.get("total_bankroll", 1000.0))
            _kelly_mult = float(st.session_state.get("kelly_multiplier", 0.25))
            _book_odds = result.get("over_odds", -110) if direction == "OVER" else result.get("under_odds", -110)
            _model_prob = result.get("probability_over", 0.5) if direction == "OVER" else (1.0 - result.get("probability_over", 0.5))
            _kelly_result = calculate_fractional_kelly(_model_prob, _book_odds, _kelly_mult)
            _wager = round(_kelly_result["fractional_kelly"] * _bankroll, 2)
            _wager_display = f"${_wager:,.2f}" if _wager > 0 else "$0.00"
            _fk_pct = _kelly_result["fractional_kelly"] * 100
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#070A13,#0F172A);border:1px solid rgba(0,198,255,0.25);'
                f'border-radius:8px;padding:8px 12px;margin:6px 0;">'
                f'<span style="color:#64748b;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;">'
                f'🎯 TARGET ALLOCATION</span><br>'
                f'<span style="color:#00C6FF;font-size:1.15rem;font-weight:800;font-family:\'JetBrains Mono\',monospace;'
                f'font-variant-numeric:tabular-nums;">{_wager_display}</span>'
                f'<span style="color:#475569;font-size:0.68rem;margin-left:6px;">'
                f'({_fk_pct:.1f}% of ${_bankroll:,.0f})</span></div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

        # ── DFS Flex EV Metrics Strip (Phase 3) ──────────────────
        _dfs_strip = _build_dfs_metrics_html(result)
        if _dfs_strip:
            st.markdown(_dfs_strip, unsafe_allow_html=True)

        # ── Fair-Value Odds Slider ────────────────────────────────
        _sim_array = result.get("simulated_results", [])
        if _sim_array and len(_sim_array) >= 10:
            try:
                _base_line = float(result.get("line", 0))
                _p10 = float(result.get("percentile_10", _base_line - 5))
                _p90 = float(result.get("percentile_90", _base_line + 5))
                _slider_min = max(0.0, round(_p10 - 2.0, 1))
                _slider_max = round(_p90 + 2.0, 1)
                # Guard: ensure valid slider range (min < max)
                if _slider_max <= _slider_min:
                    _slider_max = _slider_min + 5.0
                # Clamp base_line inside slider range
                _base_line = max(_slider_min, min(_slider_max, _base_line))
                _slider_key = (
                    f"fair_odds_{result.get('player_name', '')}_{stat}_{line}"
                    f"_{platform}_{direction}"
                )
                _target = st.slider(
                    "🔬 Explore Line",
                    min_value=_slider_min,
                    max_value=_slider_max,
                    value=_base_line,
                    step=0.5,
                    key=_slider_key,
                    help="Slide to explore fair-value odds at different prop lines.",
                )
                _fair_result = calculate_fair_odds_from_simulation(_sim_array, _target, direction)
                _fair_odds = _fair_result["fair_odds"]
                _fair_prob = _fair_result["win_probability"] * 100
                _odds_str = f"+{_fair_odds:.0f}" if _fair_odds > 0 else f"{_fair_odds:.0f}"
                st.markdown(
                    f'<div style="text-align:center;padding:6px 10px;background:rgba(0,198,255,0.06);'
                    f'border:1px solid rgba(0,198,255,0.18);border-radius:6px;margin-top:4px;">'
                    f'<span style="color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;">'
                    f'FAIR VALUE AT {_target:.1f}</span><br>'
                    f'<span style="color:#00C6FF;font-size:1.3rem;font-weight:900;font-family:\'JetBrains Mono\',monospace;'
                    f'font-variant-numeric:tabular-nums;text-shadow:0 0 12px rgba(0,198,255,0.5);">'
                    f'{_odds_str}</span>'
                    f'<span style="color:#475569;font-size:0.68rem;margin-left:6px;">'
                    f'({_fair_prob:.1f}%)</span></div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                pass

    # ── Confidence Score Breakdown Expander ───────────────────────
    _score_bd = result.get("score_breakdown", {})
    _forces = result.get("forces", {})
    _over_forces_list  = _forces.get("over_forces",  []) or []
    _under_forces_list = _forces.get("under_forces", []) or []
    _avoid_reasons = result.get("avoid_reasons", []) or []
    _tm_notes = result.get("teammate_out_notes", []) or []
    _ens_weights = result.get("ensemble_model_weights", {}) or {}

    with st.expander(f"🔬 SAFE Score™ Breakdown — {confidence:.0f}/100", expanded=False):
        # Score breakdown table
        if _score_bd:
            _bd_rows = []
            for _factor, _pts in sorted(_score_bd.items(), key=lambda x: abs(x[1] or 0), reverse=True):
                _pts_val = _pts or 0
                _bd_rows.append({
                    "Factor": _factor.replace("_", " ").title(),
                    "Points": f"{_pts_val:+.1f}",
                    "Impact": "✅ Boost" if _pts_val > 0 else ("❌ Penalty" if _pts_val < 0 else "➡️ Neutral"),
                })
            st.dataframe(_bd_rows, hide_index=True, use_container_width=True)
        else:
            st.caption("Score breakdown not available for this pick.")

        # Directional forces summary
        if _over_forces_list or _under_forces_list:
            _fc1, _fc2 = st.columns(2)
            with _fc1:
                st.markdown(
                    f'<div style="color:#00D559;font-size:0.8rem;font-weight:700;">⬆️ MORE Forces ({len(_over_forces_list)})</div>',
                    unsafe_allow_html=True,
                )
                for _f in _over_forces_list[:5]:
                    _fname = _f.get("name", _f.get("force", "")) if isinstance(_f, dict) else str(_f)
                    st.markdown(f'<div style="color:#a0d0b0;font-size:0.77rem;">• {_html.escape(str(_fname))}</div>', unsafe_allow_html=True)
            with _fc2:
                st.markdown(
                    f'<div style="color:#F24336;font-size:0.8rem;font-weight:700;">⬇️ LESS Forces ({len(_under_forces_list)})</div>',
                    unsafe_allow_html=True,
                )
                for _f in _under_forces_list[:5]:
                    _fname = _f.get("name", _f.get("force", "")) if isinstance(_f, dict) else str(_f)
                    st.markdown(f'<div style="color:#d0a0a0;font-size:0.77rem;">• {_html.escape(str(_fname))}</div>', unsafe_allow_html=True)

        # Ensemble model weights (if used)
        if _ens_weights:
            _wt_parts = [f"{k.replace('_', ' ').title()}: {v*100:.0f}%" for k, v in _ens_weights.items() if v > 0]
            if _wt_parts:
                st.caption(f"🧬 Ensemble weights: {' · '.join(_wt_parts)}")

        # Teammate boost notes
        if _tm_notes:
            for _tn in _tm_notes[:3]:
                st.caption(f"💪 {_tn}")

        # Projected minutes
        _proj_min = result.get("projected_minutes")
        if _proj_min:
            st.caption(f"⏱️ Projected minutes: **{_proj_min:.0f}** (minutes model)")

        # Recent form vs line — detailed game-by-game table
        if _recent_logs:
            render_recent_form_section(player, stat, line, _recent_logs, window=10)

        # Avoid reasons (if any)
        if _avoid_reasons:
            for _ar in _avoid_reasons[:3]:
                st.markdown(
                    f'<div style="color:#F9C62B;font-size:0.78rem;background:rgba(255,80,0,0.08);'
                    f'border-radius:4px;padding:4px 8px;margin-top:3px;">⚠️ {_html.escape(str(_ar))}</div>',
                    unsafe_allow_html=True,
                )

    # ── Full Breakdown (QDS-styled HTML rendered via st.html for auto-sizing) ─
    breakdown_html = _render_qds_full_breakdown_html(result)
    st.html(breakdown_html, unsafe_allow_javascript=True)


