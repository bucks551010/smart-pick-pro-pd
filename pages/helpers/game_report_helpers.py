# ============================================================
# FILE: pages/helpers/game_report_helpers.py
# PURPOSE: HTML rendering helpers for the Game Report page.
#          Provides QDS-styled matchup cards, summary dashboards,
#          parlay cards, head-to-head bars, narrative wrappers,
#          and Game Builder prop cards.
# ============================================================

import html as _html
import re as _re

from styles.theme import (
    get_team_colors,
    get_qds_confidence_bar_html,
    get_qds_metrics_grid_html,
    get_line_value_badge_html,
)

ESPN_NBA = "https://a.espncdn.com/i/teamlogos/nba/500"
NBA_LOGO_FALLBACK = "https://cdn.nba.com/logos/leagues/logo-nba.svg"

# Only allow alphanumeric team abbreviations in URLs
_SAFE_ABBREV_RE = _re.compile(r"^[A-Za-z0-9]+$")


def _safe_logo_url(team_abbrev: str) -> str:
    """Return an ESPN logo URL only if the abbreviation is safe for a URL."""
    if _SAFE_ABBREV_RE.match(str(team_abbrev)):
        return f"{ESPN_NBA}/{team_abbrev.lower()}.png"
    return NBA_LOGO_FALLBACK


# ============================================================
# 1. Matchup Card — replaces plain expander labels
# ============================================================

def get_matchup_card_html(
    away_team: str,
    home_team: str,
    away_record: str = "",
    home_record: str = "",
    n_props: int = 0,
    n_high_conf: int = 0,
    game_time: str = "",
    away_seed: str = "",
    home_seed: str = "",
    away_streak: str = "",
    home_streak: str = "",
) -> str:
    """Render a QDS-styled matchup card with team logos, colors, records,
    conference seed, streak, and game time.

    Args:
        away_team: Away team abbreviation (e.g. "BOS").
        home_team: Home team abbreviation (e.g. "LAL").
        away_record: Win-loss record string for away team (e.g. "42-18").
        home_record: Win-loss record string for home team (e.g. "38-22").
        n_props: Number of analyzed props for this game.
        n_high_conf: Number of high-confidence picks (≥70).
        game_time: Game time string (e.g. "7:30 PM ET").
        away_seed: Conference seed for away team (e.g. "#2 E").
        home_seed: Conference seed for home team (e.g. "#5 W").
        away_streak: Current streak for away team (e.g. "W3").
        home_streak: Current streak for home team (e.g. "L2").

    Returns:
        HTML string for the matchup card.
    """
    away_color, _ = get_team_colors(away_team)
    home_color, _ = get_team_colors(home_team)
    away_logo = _safe_logo_url(away_team)
    home_logo = _safe_logo_url(home_team)

    safe_away = _html.escape(str(away_team))
    safe_home = _html.escape(str(home_team))
    safe_away_rec = _html.escape(str(away_record)) if away_record else ""
    safe_home_rec = _html.escape(str(home_record)) if home_record else ""

    def _streak_badge(streak_str):
        """Return a colored streak badge HTML or empty string."""
        if not streak_str:
            return ""
        s = _html.escape(str(streak_str))
        if s.startswith("W"):
            return (f'<span style="color:#00D559;font-size:0.68rem;font-weight:600;">'
                    f'🔥 {s}</span>')
        if s.startswith("L"):
            return (f'<span style="color:#F24336;font-size:0.68rem;font-weight:600;">'
                    f'❄️ {s}</span>')
        return f'<span style="color:#6B7A9A;font-size:0.68rem;">{s}</span>'

    def _seed_badge(seed_str):
        """Return a small seed/rank badge or empty string."""
        if not seed_str:
            return ""
        return (f'<span style="background:rgba(0,180,255,0.12);color:#63b3ed;'
                f'padding:1px 6px;border-radius:8px;font-size:0.65rem;'
                f'font-weight:600;">{_html.escape(str(seed_str))}</span>')

    props_badge = ""
    if n_props:
        props_badge = (
            f'<div style="display:flex;gap:10px;justify-content:center;margin-top:8px;">'
            f'<span style="background:rgba(0,213,89,0.10);color:#00D559;padding:3px 10px;'
            f'border-radius:12px;font-size:0.72rem;font-weight:600;">'
            f'{n_props} props</span>'
            f'<span style="background:rgba(255,204,0,0.12);color:#F9C62B;padding:3px 10px;'
            f'border-radius:12px;font-size:0.72rem;font-weight:600;">'
            f'{n_high_conf} high-conf</span>'
            f'</div>'
        )
    else:
        props_badge = (
            f'<div style="text-align:center;margin-top:6px;font-size:0.72rem;'
            f'color:#6B7A9A;">No props analyzed yet</div>'
        )

    # Game time badge (centered above the matchup)
    time_html = ""
    if game_time:
        time_html = (
            f'<div style="text-align:center;margin-bottom:8px;">'
            f'<span style="background:rgba(0,213,89,0.08);color:#6B7A9A;'
            f'padding:2px 10px;border-radius:10px;font-size:0.70rem;'
            f'font-weight:600;letter-spacing:0.5px;">'
            f'🕐 {_html.escape(str(game_time))}</span></div>'
        )

    return (
        f'<div style="background:linear-gradient(135deg,rgba(0,213,89,0.04) 0%,rgba(0,180,255,0.04) 100%);'
        f'border:1px solid rgba(0,213,89,0.12);border-radius:12px;padding:12px 14px;'
        f'margin-bottom:6px;">'
        + time_html
        + f'<div style="display:flex;align-items:center;justify-content:center;gap:20px;flex-wrap:wrap;">'
        # Away team
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:70px;">'
        f'<img src="{away_logo}" onerror="this.src=\'{NBA_LOGO_FALLBACK}\'" '
        f'style="width:44px;height:44px;object-fit:contain;'
        f'filter:drop-shadow(0 0 6px rgba(0,180,255,0.4));" alt="{safe_away}">'
        f'<div style="font-family:\'Inter\',sans-serif;font-weight:700;font-size:0.95rem;'
        f'color:{away_color};">{safe_away}</div>'
        + (f'<div style="font-size:0.72rem;color:#6B7A9A;">{safe_away_rec}</div>' if safe_away_rec else "")
        + f'<div style="display:flex;gap:6px;align-items:center;">'
        + _seed_badge(away_seed)
        + _streak_badge(away_streak)
        + f'</div>'
        + f'</div>'
        # @ divider
        f'<div style="font-family:\'Inter\',sans-serif;font-size:0.85rem;color:#6B7A9A;'
        f'padding:4px 12px;background:rgba(0,180,255,0.08);border-radius:20px;">@</div>'
        # Home team
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:70px;">'
        f'<img src="{home_logo}" onerror="this.src=\'{NBA_LOGO_FALLBACK}\'" '
        f'style="width:44px;height:44px;object-fit:contain;'
        f'filter:drop-shadow(0 0 6px rgba(0,180,255,0.4));" alt="{safe_home}">'
        f'<div style="font-family:\'Inter\',sans-serif;font-weight:700;font-size:0.95rem;'
        f'color:{home_color};">{safe_home}</div>'
        + (f'<div style="font-size:0.72rem;color:#6B7A9A;">{safe_home_rec}</div>' if safe_home_rec else "")
        + f'<div style="display:flex;gap:6px;align-items:center;">'
        + _seed_badge(home_seed)
        + _streak_badge(home_streak)
        + f'</div>'
        + f'</div>'
        f'</div>'
        + props_badge
        + f'</div>'
    )


# ============================================================
# 2. Summary Dashboard — 4-column metrics grid
# ============================================================

def get_summary_dashboard_html(
    total_props: int,
    high_conf_picks: int,
    avg_safe_score: float,
    best_pick_label: str,
) -> str:
    """Render a 4-column QDS metrics grid for the report summary dashboard.

    Args:
        total_props: Total number of analyzed props.
        high_conf_picks: Number of picks with confidence ≥ 70.
        avg_safe_score: Mean SAFE Score across all props (0-100).
        best_pick_label: Label for the best pick (e.g. "LeBron · Points").

    Returns:
        HTML string for the dashboard row.
    """
    metrics = [
        {"label": "Total Props", "value": str(total_props), "icon": "📊"},
        {"label": "High-Conf Picks", "value": str(high_conf_picks), "icon": "🔒"},
        {"label": "Avg SAFE Score", "value": f"{avg_safe_score:.1f}", "icon": "⚡"},
        {"label": "Best Pick Tonight", "value": str(best_pick_label), "icon": "🏆"},
    ]
    return get_qds_metrics_grid_html(metrics)


# ============================================================
# 3. Expanded Head-to-Head Visualization (Dean Oliver Four Factors)
# ============================================================

def get_h2h_bars_html(away_abbrev: str, home_abbrev: str, stats: list) -> str:
    """Render head-to-head comparison bars with animated CSS transitions.

    Args:
        away_abbrev: Away team abbreviation.
        home_abbrev: Home team abbreviation.
        stats: List of tuples (label, away_val, home_val, range_lo, range_hi, lower_is_better).
            ``lower_is_better`` (bool) flips the color logic so that lower = green.

    Returns:
        HTML string with animated comparison bars.
    """
    safe_away = _html.escape(str(away_abbrev))
    safe_home = _html.escape(str(home_abbrev))
    away_color, _ = get_team_colors(away_abbrev)
    home_color, _ = get_team_colors(home_abbrev)

    rows_html = ""
    for item in stats:
        label, a_val, h_val, lo, hi, flip = item
        rng = max(hi - lo, 1)
        a_pct = round(max(0, min(100, (a_val - lo) / rng * 100)))
        h_pct = round(max(0, min(100, (h_val - lo) / rng * 100)))
        a_better = (a_val < h_val) if flip else (a_val > h_val)
        a_bar_color = "#00D559" if a_better else "#8b949e"
        h_bar_color = "#00D559" if not a_better else "#8b949e"

        rows_html += (
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">'
            # Away value
            f'<div style="width:40px;text-align:right;font-size:0.72rem;color:{a_bar_color};'
            f'font-weight:600;">{a_val:.1f}</div>'
            # Bars
            f'<div style="flex:1;display:flex;align-items:center;gap:3px;">'
            f'<div style="flex:1;height:10px;background:#161B27;border-radius:3px;'
            f'position:relative;overflow:hidden;">'
            f'<div style="position:absolute;right:0;width:{a_pct}%;height:10px;'
            f'background:{a_bar_color};border-radius:3px;'
            f'transition:width 1.5s cubic-bezier(0.4,0,0.2,1);"></div>'
            f'</div>'
            f'<div style="width:44px;text-align:center;font-size:0.65rem;font-weight:700;'
            f'color:#EEF0F6;font-family:\'Inter\',sans-serif;">{_html.escape(label)}</div>'
            f'<div style="flex:1;height:10px;background:#161B27;border-radius:3px;'
            f'overflow:hidden;">'
            f'<div style="width:{h_pct}%;height:10px;background:{h_bar_color};border-radius:3px;'
            f'transition:width 1.5s cubic-bezier(0.4,0,0.2,1);"></div>'
            f'</div>'
            f'</div>'
            # Home value
            f'<div style="width:40px;text-align:left;font-size:0.72rem;color:{h_bar_color};'
            f'font-weight:600;">{h_val:.1f}</div>'
            f'</div>'
        )

    return (
        f'<div style="background:rgba(0,0,0,0.25);border-radius:10px;padding:12px 14px;'
        f'margin-top:8px;border:1px solid rgba(0,213,89,0.08);">'
        f'<div style="font-family:\'Inter\',sans-serif;font-size:0.72rem;color:#6B7A9A;'
        f'font-weight:600;margin-bottom:12px;letter-spacing:1px;text-align:center;">'
        f'⚡ HEAD-TO-HEAD — DEAN OLIVER FOUR FACTORS</div>'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:10px;'
        f'padding:0 4px;">'
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<img src="{_safe_logo_url(away_abbrev)}" '
        f'onerror="this.src=\'{NBA_LOGO_FALLBACK}\'" '
        f'style="width:20px;height:20px;object-fit:contain;" alt="{safe_away}">'
        f'<span style="font-size:0.78rem;font-weight:700;color:{away_color};">{safe_away}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<span style="font-size:0.78rem;font-weight:700;color:{home_color};">{safe_home}</span>'
        f'<img src="{_safe_logo_url(home_abbrev)}" '
        f'onerror="this.src=\'{NBA_LOGO_FALLBACK}\'" '
        f'style="width:20px;height:20px;object-fit:contain;" alt="{safe_home}">'
        f'</div>'
        f'</div>'
        f'{rows_html}'
        f'</div>'
    )


# ============================================================
# 4. QDS-Styled Parlay Cards
# ============================================================

def get_parlay_card_html(combo_type: str, picks: list, safe_avg: str, strategy: str) -> str:
    """Render a QDS-styled parlay suggestion card.

    Args:
        combo_type: Parlay type label (e.g. "Power Play (2)").
        picks: List of pick description strings.
        safe_avg: Average SAFE score string.
        strategy: Strategy description.

    Returns:
        HTML string for the parlay card.
    """
    safe_combo = _html.escape(str(combo_type))
    safe_avg_s = _html.escape(str(safe_avg))
    safe_strat = _html.escape(str(strategy))

    # Determine card accent color by combo type
    if "Power" in combo_type:
        accent = "#00D959"
        icon = "⚡"
    elif "Triple" in combo_type:
        accent = "#50a874"
        icon = "🎯"
    else:
        accent = "#90d0a8"
        icon = "🚀"

    picks_html = ""
    for i, pick in enumerate(picks):
        safe_pick = _html.escape(str(pick))
        picks_html += (
            f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0;'
            f'border-bottom:1px solid rgba(0,217,89,0.06);">'
            f'<span style="color:{accent};font-size:0.75rem;font-weight:700;'
            f'font-family:JetBrains Mono,monospace;">'
            f'Leg {i + 1}</span>'
            f'<span style="color:#e8f5ec;font-size:0.84rem;font-family:Inter,sans-serif;">{safe_pick}</span>'
            f'</div>'
        )

    return (
        f'<div style="background:rgba(4,8,6,0.88);border-radius:12px;padding:14px 18px;'
        f'margin-bottom:10px;'
        f'border:1px solid rgba(0,217,89,0.12);border-left:3px solid {accent};'
        f'transition:transform 0.2s ease,box-shadow 0.2s ease;"'
        f' onmouseenter="this.style.transform=\'translateY(-2px)\';'
        f'this.style.boxShadow=\'0 8px 30px rgba(0,0,0,0.4)\'"'
        f' onmouseleave="this.style.transform=\'translateY(0)\';'
        f'this.style.boxShadow=\'none\'">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:8px;">'
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<span style="font-size:1rem;">{icon}</span>'
        f'<span style="color:{accent};font-weight:700;font-family:Bebas Neue,Inter,sans-serif;'
        f'font-size:0.9rem;letter-spacing:1px;">{safe_combo}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="background:rgba(0,217,89,0.1);color:#00D959;padding:3px 10px;'
        f'border-radius:6px;font-size:0.72rem;font-weight:700;'
        f'font-family:JetBrains Mono,monospace;">'
        f'SAFE {safe_avg_s}/100</span>'
        f'</div>'
        f'</div>'
        f'{picks_html}'
        f'<div style="font-size:0.72rem;color:rgba(144,208,168,0.5);margin-top:6px;'
        f'font-family:JetBrains Mono,monospace;">'
        f'{safe_strat}</div>'
        f'</div>'
    )


# ============================================================
# 5. Game Builder QDS Prop Card
# ============================================================

def get_builder_prop_card_html(
    player_name: str,
    team: str,
    stat_type: str,
    direction: str,
    prop_line: float,
    projected: float,
    over_prob: float,
    confidence: float,
    minutes: float,
    season_avg: float = 0.0,
) -> str:
    """Render a QDS-styled prop card for Game Builder results.

    Args:
        player_name: Player's full name.
        team: Team abbreviation.
        stat_type: Stat type (e.g. "points").
        direction: "OVER" or "UNDER".
        prop_line: Prop line value.
        projected: Projected value.
        over_prob: Over probability (0.0-1.0).
        confidence: Confidence score (0-100).
        minutes: Minutes used.
        season_avg: Player's season average for this stat (0 = unavailable).

    Returns:
        HTML string for the prop card.
    """
    team_color, _ = get_team_colors(team)
    safe_name = _html.escape(str(player_name))
    safe_team = _html.escape(str(team))
    safe_stat = _html.escape(str(stat_type).upper())
    safe_dir = _html.escape(str(direction).upper())

    # Tier determination
    if confidence >= 85:
        tier_label = "QUANTUM PICK"
        tier_color = "#00D559"
        tier_icon = "💎"
    elif confidence >= 70:
        tier_label = "STRONG PICK"
        tier_color = "#F9C62B"
        tier_icon = "🔒"
    elif confidence >= 55:
        tier_label = "SAFE PICK"
        tier_color = "#00b4ff"
        tier_icon = "✓"
    else:
        tier_label = "PICK"
        tier_color = "#A0AABE"
        tier_icon = "⭐"

    # Direction colors
    if safe_dir == "OVER":
        dir_color = "#69f0ae"
        dir_bg = "rgba(105,240,174,0.12)"
        dir_icon = "📈"
    else:
        dir_color = "#F24336"
        dir_bg = "rgba(255,107,107,0.12)"
        dir_icon = "📉"

    prob_pct = over_prob * 100
    conf_bar = get_qds_confidence_bar_html(
        f"{safe_stat} {safe_dir} {prop_line}", confidence, tier_icon
    )

    # Line Value vs Average badge (display-only)
    _line_val_badge = ""
    try:
        _s_avg = float(season_avg or 0)
        _p_line = float(prop_line or 0)
        if _s_avg > 0 and _p_line > 0:
            _lv_gap = (_p_line - _s_avg) / _s_avg * 100.0
            _line_val_badge = get_line_value_badge_html(_lv_gap)
    except (TypeError, ValueError):
        pass

    metrics = get_qds_metrics_grid_html([
        {"label": "Projected", "value": f"{projected:.1f}", "icon": "🎯"},
        {"label": "Probability", "value": f"{prob_pct:.1f}%", "icon": "📊"},
        {"label": "Confidence", "value": f"{confidence:.0f}", "icon": "⚡"},
        {"label": "Minutes", "value": f"{minutes:.0f}", "icon": "⏱️"},
    ])

    return (
        f'<div class="qds-na-card" style="border-top-color:{tier_color};">'
        # Badge row
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
        f'<span style="background:{dir_bg};color:{dir_color};padding:2px 8px;'
        f'border-radius:4px;font-size:0.72rem;font-weight:700;'
        f'border:1px solid {dir_color}40;">{dir_icon} {safe_dir}</span>'
        f'<span class="qds-na-badge" style="background:{tier_color};color:#0D0F14;">'
        f'{tier_icon} {tier_label}</span>'
        f'</div>'
        # Player row
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">'
        f'<div style="width:44px;height:44px;border-radius:50%;'
        f'background:{team_color};display:flex;align-items:center;justify-content:center;'
        f'font-weight:700;font-size:0.85rem;color:#fff;flex-shrink:0;">'
        f'{safe_team}</div>'
        f'<div style="flex:1;">'
        f'<div class="qds-na-player-name">{safe_name}'
        f'<span class="qds-na-team-badge" style="background:{team_color};color:#fff;">'
        f'{safe_team}</span></div>'
        f'<div class="qds-na-prop-desc">{safe_stat} {safe_dir} {prop_line}{_line_val_badge}</div>'
        f'</div>'
        f'<div style="text-align:center;flex-shrink:0;">'
        f'<div style="font-size:0.65rem;color:var(--qds-text-muted);'
        f'text-transform:uppercase;letter-spacing:0.5px;">SAFE Score™</div>'
        f'<div class="qds-na-score">{confidence / 10:.1f}'
        f'<span style="font-size:0.85rem;color:var(--qds-text-muted);">/10</span></div>'
        f'</div>'
        f'</div>'
        # Confidence bar
        f'{conf_bar}'
        # Metrics grid
        f'{metrics}'
        f'</div>'
    )


# ============================================================
# 6. Narrative Card Wrapper
# ============================================================

def get_narrative_card_html(
    away_team: str,
    home_team: str,
) -> str:
    """Wrap a game narrative in a QDS-styled card with team-colored accents.

    Args:
        away_team: Away team abbreviation.
        home_team: Home team abbreviation.

    Returns:
        HTML string wrapping the narrative.
    """
    home_color, _ = get_team_colors(home_team)
    away_color, _ = get_team_colors(away_team)
    away_logo = _safe_logo_url(away_team)
    home_logo = _safe_logo_url(home_team)
    safe_away = _html.escape(str(away_team))
    safe_home = _html.escape(str(home_team))

    return (
        f'<div style="background:rgba(20,26,45,0.90);border-radius:12px;padding:18px 16px;'
        f'border-left:4px solid {home_color};border-right:4px solid {away_color};'
        f'border-top:1px solid rgba(0,213,89,0.10);border-bottom:1px solid rgba(0,213,89,0.10);'
        f'position:relative;overflow:hidden;">'
        # Watermark logos
        f'<img src="{away_logo}" onerror="this.style.display=\'none\'" '
        f'style="position:absolute;top:10px;left:10px;width:60px;height:60px;'
        f'object-fit:contain;opacity:0.06;pointer-events:none;" alt="">'
        f'<img src="{home_logo}" onerror="this.style.display=\'none\'" '
        f'style="position:absolute;bottom:10px;right:10px;width:60px;height:60px;'
        f'object-fit:contain;opacity:0.06;pointer-events:none;" alt="">'
        # Header
        f'<div style="display:flex;align-items:center;justify-content:center;gap:12px;'
        f'margin-bottom:14px;">'
        f'<img src="{away_logo}" onerror="this.src=\'{NBA_LOGO_FALLBACK}\'" '
        f'style="width:28px;height:28px;object-fit:contain;" alt="{safe_away}">'
        f'<span style="font-family:\'Inter\',sans-serif;font-size:0.85rem;color:#6B7A9A;">@</span>'
        f'<img src="{home_logo}" onerror="this.src=\'{NBA_LOGO_FALLBACK}\'" '
        f'style="width:28px;height:28px;object-fit:contain;" alt="{safe_home}">'
        f'</div>'
        # Narrative content — will be rendered by Streamlit markdown separately
        f'</div>'
    )


# ============================================================
# 7. All Picks Premium Table
# ============================================================

_TIER_STYLES = {
    "platinum": ("#00D559", "rgba(0,213,89,0.12)", "rgba(0,213,89,0.30)"),
    "gold":     ("#ffb347", "rgba(255,179,71,0.12)", "rgba(255,179,71,0.30)"),
    "silver":   ("#94A3B8", "rgba(148,163,184,0.10)", "rgba(148,163,184,0.20)"),
}


def get_picks_summary_chips_html(rows: list) -> str:
    """Render summary stat chips above the picks table."""
    total = len(rows)
    if total == 0:
        return ""

    avg_safe = sum(r.get("SAFE", 0) for r in rows) / total if total else 0
    over_ct = sum(1 for r in rows if str(r.get("Dir", "")).upper() == "OVER")
    under_ct = total - over_ct

    tier_counts: dict[str, int] = {}
    for r in rows:
        t = str(r.get("Tier", "")).lower()
        tier_counts[t] = tier_counts.get(t, 0) + 1

    tier_chips = ""
    for t_name in ("platinum", "gold", "silver"):
        ct = tier_counts.get(t_name, 0)
        if ct == 0:
            continue
        color, bg, _ = _TIER_STYLES.get(t_name, _TIER_STYLES["silver"])
        tier_chips += (
            f'<span class="grt-chip" style="background:{bg};color:{color};'
            f'border:1px solid {color}30;">'
            f'{t_name.upper()} {ct}</span>'
        )

    safe_color = "#69f0ae" if avg_safe >= 70 else "#ffb347" if avg_safe >= 55 else "#F24336"

    return (
        f'<div class="grt-summary-bar">'
        f'<span class="grt-chip" style="background:rgba(0,213,89,0.08);color:#00D559;'
        f'border:1px solid rgba(0,213,89,0.25);">📋 {total} PICKS</span>'
        f'<span class="grt-chip" style="background:rgba(105,240,174,0.08);color:{safe_color};'
        f'border:1px solid {safe_color}30;">⚡ AVG SAFE {avg_safe:.1f}</span>'
        f'<span class="grt-chip" style="background:rgba(105,240,174,0.08);color:#69f0ae;'
        f'border:1px solid rgba(105,240,174,0.25);">📈 {over_ct} OVER</span>'
        f'<span class="grt-chip" style="background:rgba(255,107,107,0.08);color:#F24336;'
        f'border:1px solid rgba(255,107,107,0.25);">📉 {under_ct} UNDER</span>'
        f'{tier_chips}'
        f'</div>'
    )


def get_picks_table_html(rows: list) -> str:
    """Render a premium styled HTML table for All Player Props & Picks.

    Args:
        rows: List of dicts with keys Player, Team, Stat, Dir, Line, Proj,
              SAFE, Edge%, Tier (from ``_build_all_picks_table``).

    Returns:
        Full HTML string including summary chips + table.
    """
    if not rows:
        return ""

    summary = get_picks_summary_chips_html(rows)

    # Table header
    header = (
        '<thead><tr>'
        '<th class="grt-th grt-th-rank">#</th>'
        '<th class="grt-th">PLAYER</th>'
        '<th class="grt-th grt-th-center">STAT</th>'
        '<th class="grt-th grt-th-center">DIR</th>'
        '<th class="grt-th grt-th-right">LINE</th>'
        '<th class="grt-th grt-th-right">PROJ</th>'
        '<th class="grt-th grt-th-center">SAFE</th>'
        '<th class="grt-th grt-th-right">EDGE%</th>'
        '<th class="grt-th grt-th-center">TIER</th>'
        '</tr></thead>'
    )

    # Table rows
    body_rows = []
    for i, r in enumerate(rows, 1):
        player = _html.escape(str(r.get("Player", "?")))
        team = _html.escape(str(r.get("Team", "")))
        stat = _html.escape(str(r.get("Stat", "")))
        direction = str(r.get("Dir", "")).upper()
        line = float(r.get("Line", 0))
        proj = float(r.get("Proj", 0))
        safe = float(r.get("SAFE", 0))
        edge = float(r.get("Edge%", 0))
        tier = str(r.get("Tier", "")).lower()

        # Team color dot
        team_color, _ = get_team_colors(team)

        # Direction badge
        if direction == "OVER":
            dir_html = '<span class="grt-dir grt-dir-over">▲ OVER</span>'
        else:
            dir_html = '<span class="grt-dir grt-dir-under">▼ UNDER</span>'

        # Proj vs Line gap
        gap = proj - line
        if direction == "UNDER":
            gap = line - proj
        gap_color = "#69f0ae" if gap > 0 else "#F24336" if gap < 0 else "#6B7A9A"

        # SAFE score bar + number
        safe_pct = min(safe, 100)
        if safe >= 75:
            safe_color = "#00D559"
        elif safe >= 65:
            safe_color = "#69f0ae"
        elif safe >= 55:
            safe_color = "#ffb347"
        else:
            safe_color = "#F24336"
        safe_html = (
            f'<div class="grt-safe-wrap">'
            f'<span class="grt-safe-num" style="color:{safe_color};">{safe:.1f}</span>'
            f'<div class="grt-safe-track">'
            f'<div class="grt-safe-fill" style="width:{safe_pct}%;background:{safe_color};"></div>'
            f'</div>'
            f'</div>'
        )

        # Edge color
        if edge > 0:
            edge_color = "#69f0ae"
            edge_prefix = "+"
        elif edge < 0:
            edge_color = "#F24336"
            edge_prefix = ""
        else:
            edge_color = "#6B7A9A"
            edge_prefix = ""
        edge_html = (
            f'<span style="color:{edge_color};font-weight:600;">'
            f'{edge_prefix}{edge:.1f}%</span>'
        )

        # Tier badge
        t_color, t_bg, t_border = _TIER_STYLES.get(tier, _TIER_STYLES["silver"])
        tier_html = (
            f'<span class="grt-tier" style="background:{t_bg};color:{t_color};'
            f'border:1px solid {t_border};">{tier.upper()}</span>'
        )

        # Rank badge — top 3 get accent
        if i <= 3:
            rank_html = f'<span class="grt-rank grt-rank-top">{i}</span>'
        else:
            rank_html = f'<span class="grt-rank">{i}</span>'

        body_rows.append(
            f'<tr class="grt-row">'
            f'<td class="grt-td grt-td-rank">{rank_html}</td>'
            f'<td class="grt-td grt-td-player">'
            f'<span class="grt-team-dot" style="background:{team_color};"></span>'
            f'<span class="grt-player-name">{player}</span>'
            f'<span class="grt-team-label">{team}</span>'
            f'</td>'
            f'<td class="grt-td grt-td-center">{stat}</td>'
            f'<td class="grt-td grt-td-center">{dir_html}</td>'
            f'<td class="grt-td grt-td-right grt-mono">{line:.1f}</td>'
            f'<td class="grt-td grt-td-right">'
            f'<span class="grt-mono" style="color:{gap_color};">{proj:.1f}</span>'
            f'</td>'
            f'<td class="grt-td grt-td-center">{safe_html}</td>'
            f'<td class="grt-td grt-td-right">{edge_html}</td>'
            f'<td class="grt-td grt-td-center">{tier_html}</td>'
            f'</tr>'
        )

    body = "<tbody>" + "\n".join(body_rows) + "</tbody>"

    return (
        f'{summary}'
        f'<div class="grt-table-wrap">'
        f'<table class="grt-table">{header}{body}</table>'
        f'</div>'
    )
