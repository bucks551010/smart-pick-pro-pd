# ============================================================
# FILE: pages/helpers/quantum_analysis_helpers.py
# PURPOSE: Helper functions for the Quantum Analysis Matrix page.
#          Extracted from pages/3_⚡_Quantum_Analysis_Matrix.py to
#          reduce page size and improve maintainability.
# ============================================================
import html as _html
import re as _re

from data.platform_mappings import display_stat_name as _display_stat_name
from styles.theme import get_education_box_html, get_team_colors

# ESPN CDN base for team logos (same as game_report_helpers)
_ESPN_NBA = "https://a.espncdn.com/i/teamlogos/nba/500"
_NBA_LOGO_FALLBACK = "https://cdn.nba.com/logos/leagues/logo-nba.svg"
_SAFE_ABBREV_RE = _re.compile(r"^[A-Za-z0-9]+$")


def _safe_logo_url(team_abbrev: str) -> str:
    """Return an ESPN logo URL only if the abbreviation is safe for a URL."""
    if _SAFE_ABBREV_RE.match(str(team_abbrev)):
        return f"{_ESPN_NBA}/{team_abbrev.lower()}.png"
    return _NBA_LOGO_FALLBACK


# ── Constants ─────────────────────────────────────────────────────────────────

JOSEPH_DESK_SIZE_CSS = """<style>
.joseph-live-desk{
    padding:10px 12px !important;
    margin:10px 0 !important;
    font-size:0.85rem !important;
    overflow-y:visible;
}
.joseph-live-desk .joseph-desk-avatar{
    width:40px !important;height:40px !important;
}
.joseph-live-desk h3,.joseph-live-desk h4{
    font-size:0.85rem !important;margin:4px 0 !important;
}
.joseph-live-desk .joseph-desk-title{
    font-size:0.9rem !important;
}
</style>"""

IMPACT_COLORS = {"high": "#F24336", "medium": "#ffd700", "low": "#8b949e"}

CATEGORY_EMOJI = {
    "injury": "🏥", "trade": "🔄", "performance": "📈",
    "suspension": "🚫", "contract": "💰", "roster": "📋",
}

SIGNAL_COLORS = {"sharp_buy": "#00D559", "sharp_fade": "#F24336", "neutral": "#8b949e"}

# Shared positive/negative accent colors used for edge and direction styling
_POSITIVE_COLOR = "#00D559"
_NEGATIVE_COLOR = "#F24336"

SIGNAL_LABELS = {
    "sharp_buy": "🟢 SHARP BUY",
    "sharp_fade": "🔴 SHARP FADE",
    "neutral": "⚪ NEUTRAL",
}

PARLAY_STARS = {2: "", 3: "", 4: "", 5: "", 6: ""}

PARLAY_LABELS = {
    2: "2-Leg Power Play",
    3: "3-Leg Triple Lock",
    4: "4-Leg Precision",
    5: "5-Leg Mega Entry",
    6: "6-Leg Max Entry",
}


# ── DFS Flex Edge ─────────────────────────────────────────────────────────────

def render_dfs_flex_edge_html(beats_be_count: int, total_dfs: int,
                              avg_dfs_edge: float) -> str:
    """Return the DFS FLEX EDGE inline card HTML."""
    edge_c = "#00D559" if avg_dfs_edge > 0 else "#ff5e00"
    return (
        f'<div class="qam-dfs-edge">'
        f'<span class="qam-dfs-edge-label">📈 DFS FLEX EDGE</span>'
        f'<span class="qam-dfs-edge-sub">{beats_be_count}/{total_dfs} legs beat breakeven</span>'
        f'<span class="qam-dfs-edge-val" style="color:{edge_c};">'
        f'Avg Edge: {avg_dfs_edge:+.1f}%</span>'
        f'</div>'
    )


# ── Tier Distribution + Best Pick ─────────────────────────────────────────────

def render_tier_distribution_html(platinum_count: int, gold_count: int,
                                  silver_count: int, bronze_count: int,
                                  avg_edge: float, best_pick: dict | None) -> str:
    """Return the slate-summary tier-distribution dashboard HTML."""
    tier_bar = (
        f'<span class="qam-tier-platinum">💎 {platinum_count} Platinum</span>'
        f' &nbsp;·&nbsp; <span class="qam-tier-gold">🥇 {gold_count} Gold</span>'
        f' &nbsp;·&nbsp; <span class="qam-tier-silver">🥈 {silver_count} Silver</span>'
        f' &nbsp;·&nbsp; <span class="qam-tier-bronze">🥉 {bronze_count} Bronze</span>'
    )
    best_html = ""
    if best_pick:
        bp_name = _html.escape(str(best_pick.get("player_name", "")))
        bp_stat = _html.escape(str(best_pick.get("stat_type", "")).title())
        bp_line = best_pick.get("line", 0)
        bp_dir = "More" if best_pick.get("direction") == "OVER" else "Less"
        bp_conf = best_pick.get("confidence_score", 0)
        bp_tier = best_pick.get("tier", "")
        bp_emoji = {"Platinum": "💎", "Gold": "🥇", "Silver": "🥈", "Bronze": "🥉"}.get(bp_tier, "🏀")
        best_html = (
            f'<div class="qam-best-pick">'
            f'<span class="qam-best-pick-label">🏆 Best Pick: </span>'
            f'<span class="qam-best-pick-detail">{bp_emoji} {bp_name} — {bp_dir} {bp_line} {bp_stat}</span>'
            f'<span class="qam-best-pick-conf">{bp_conf:.0f}/100</span>'
            f'</div>'
        )
    return (
        f'<div class="qam-tier-dist">'
        f'<div class="qam-tier-dist-header">'
        f'🗂️ Tier Distribution &nbsp;·&nbsp; '
        f'<span class="qam-avg-edge">Avg Edge: {avg_edge:.1f}%</span>'
        f'</div>'
        f'<div class="qam-tier-dist-bar">{tier_bar}</div>'
        + best_html
        + f'</div>'
    )


# ── Player News Alert Card ───────────────────────────────────────────────────

def render_news_alert_html(news_item: dict) -> str:
    """Return HTML for a single player-news alert card."""
    title = news_item.get("title", "")
    player = news_item.get("player_name", "")
    body = news_item.get("body", "")
    category = news_item.get("category", "")
    impact = news_item.get("impact", "").lower()
    pub = news_item.get("published_at", "")[:10]

    color = IMPACT_COLORS.get(impact, "#555")
    emoji = CATEGORY_EMOJI.get(category, "📰")

    return (
        f'<div class="qam-news-alert" style="border-left:4px solid {color};">'
        f'<div class="qam-news-alert-header">'
        f'<span class="qam-news-alert-title">{emoji} {_html.escape(title[:80])}</span>'
        f'<span class="qam-news-alert-badge" style="background:{color};">'
        f'{impact.upper() if impact else "NEWS"}</span>'
        f'</div>'
        f'<div class="qam-news-alert-meta">'
        f'<strong class="qam-news-alert-player">{_html.escape(player)}</strong>'
        + (f' · {_html.escape(pub)}' if pub else "")
        + f'</div>'
        + (f'<div class="qam-news-alert-body">'
           f'{_html.escape(body[:200])}'
           + ("…" if len(body) > 200 else "")
           + f'</div>' if body else "")
        + f'</div>'
    )


# ── Market Movement Alert Card ────────────────────────────────────────────────

def render_market_movement_html(result: dict) -> str:
    """Return HTML for a single market-movement alert card."""
    mm = result.get("market_movement", {})
    player = result.get("player_name", "")
    stat = result.get("stat_type", "")
    direction = mm.get("direction", "")
    shift = mm.get("line_shift", 0)
    signal = mm.get("signal", "neutral")
    adj = mm.get("confidence_adjustment", 0)

    sig_c = SIGNAL_COLORS.get(signal, "#8b949e")
    sig_lbl = SIGNAL_LABELS.get(signal, "⚪ NEUTRAL")

    return (
        f'<div class="qam-market-move" style="border-left:4px solid {sig_c};">'
        f'<div class="qam-market-move-header">'
        f'<span class="qam-market-move-player">'
        f'{_html.escape(player)} — {_html.escape(stat.title())} {_html.escape(direction)}</span>'
        f'<span class="qam-market-move-signal" style="color:{sig_c};">{sig_lbl}</span>'
        f'</div>'
        f'<div class="qam-market-move-detail">'
        f'Line shift: <strong class="qam-detail-value">{shift:+.1f}</strong>'
        + (f' · Confidence adj: <strong style="color:{sig_c};">{adj:+.1f}</strong>' if adj else '')
        + f'</div></div>'
    )


# ── Uncertain Pick Warning Header ─────────────────────────────────────────────

def render_uncertain_header_html() -> str:
    """Return the explanatory header + education box for the Uncertain Picks section."""
    header = (
        '<div class="qam-uncertain-header">'
        '<strong class="qam-uncertain-header-title">UNCERTAIN PICKS — Conflicting Signals</strong><br>'
        '<span class="qam-uncertain-header-desc">These picks have hidden structural risks: '
        'conflicting forces, high variance with low edge, fatigue combos, or hot-streak regression. '
        'They are automatically added to your Avoid List.</span>'
        '</div>'
    )
    education = get_education_box_html(
        "What are Uncertain Picks (Risk Flags)?",
        "Uncertain picks have one or more hidden risk signals that make them dangerous despite "
        "appearing to have edge.<br><br>"
        "<strong>There are 4 risk patterns:</strong><br>"
        "1. <strong>Conflicting Forces:</strong> The model's forces are fighting each other — "
        "nearly 50/50 MORE vs LESS. It's a coin flip disguised as an edge.<br>"
        "2. <strong>High Variance:</strong> High-variance stat (3-pointers, steals, blocks) "
        "with a tiny edge (&lt;8%). These stats are too random game-to-game.<br>"
        "3. <strong>Fatigue:</strong> Back-to-back game + big spread (blowout expected). "
        "Player will likely rest in the 4th quarter.<br>"
        "4. <strong>Regression:</strong> The line is set at a hot streak value (125%+ of "
        "season average). The player is due to come back to earth.<br><br>"
        "Uncertain picks are <em>automatically added to your Avoid List</em>.",
    )
    return header + education


# ── Uncertain Pick Card ──────────────────────────────────────────────────────

def _classify_flag_type(flags: list) -> str:
    """Classify the risk type from flag text list."""
    for ft in flags:
        ftl = str(ft).lower()
        if "conflict" in ftl:
            return "Conflicting Forces"
        if "variance" in ftl or "high-variance" in ftl:
            return "High Variance"
        if "fatigue" in ftl or "back-to-back" in ftl:
            return "Fatigue Risk"
        if "regression" in ftl or "hot streak" in ftl or "inflated" in ftl:
            return "Regression Risk"
    return "Uncertain"


def render_uncertain_pick_html(pick: dict, inline_breakdown_html: str = "") -> str:
    """Return HTML for a single uncertain-pick risk-warning card.

    Parameters
    ----------
    pick : dict
        Full analysis result dict for the uncertain pick.
    inline_breakdown_html : str
        Pre-rendered inline breakdown HTML (from ``render_inline_breakdown_html``).
    """
    name = _html.escape(str(pick.get("player_name", "")))
    team = _html.escape(str(pick.get("player_team", pick.get("team", ""))))
    stat = _html.escape(str(pick.get("stat_type", "")).title())
    direction = _html.escape(str(pick.get("direction", "OVER")))
    line = pick.get("line", 0)
    proj = pick.get("adjusted_projection", 0)
    edge = pick.get("edge_percentage", 0)
    flags = pick.get("risk_flags", pick.get("bet_type_reasons", []))

    team_badge = (
        f'<span class="qam-uncertain-team-badge">{team}</span>'
        if team else ""
    )

    flags_html = "".join(
        f'<li>{_html.escape(str(r))}</li>'
        for r in flags
    )

    flag_type = _classify_flag_type(flags)

    return (
        f'<div class="qam-uncertain-card">'
        f'<div class="qam-uncertain-card-header">'
        f'<div>'
        f'<span class="qam-uncertain-name">⚠️ {name}</span>'
        f'{team_badge}'
        f'<span class="qam-uncertain-flag-type">{flag_type}</span>'
        f'</div>'
        f'<div class="qam-uncertain-card-right">'
        f'<span class="qam-uncertain-prop">{direction} {line} {stat} '
        f'(Proj: {proj:.1f})</span>'
        f'<br><span class="qam-uncertain-edge">'
        f'Edge: {edge:+.1f}%</span>'
        f'</div>'
        f'</div>'
        f'<div class="qam-uncertain-flags">'
        f'<span class="qam-uncertain-flags-label">RISK FLAGS (AVOID):</span>'
        f'<ul>{flags_html}</ul>'
        f'</div>'
        + inline_breakdown_html
        + f'</div>'
    )


# ── Quantum Edge Gap Banner ──────────────────────────────────────────────────

_QEG_LINE_DEVIATION_THRESHOLD = 25.0  # Minimum |line_vs_avg_pct| to qualify

QEG_EDGE_THRESHOLD = _QEG_LINE_DEVIATION_THRESHOLD  # Public alias for page import


def render_quantum_edge_gap_banner_html(
    picks: list,
) -> str:
    """Return the Quantum Edge Gap section banner HTML with summary stats.

    Parameters
    ----------
    picks:
        List of result dicts that qualified for the edge gap (either
        line_vs_avg_pct deviation or edge_percentage ≥ threshold).
    """
    total = len(picks)
    over_ct = sum(1 for p in picks if p.get("direction", "").upper() == "OVER")
    under_ct = total - over_ct
    over_pct = (over_ct / total * 100) if total else 0

    # Edge stats — always meaningful (edge_percentage present on every pick)
    edges = [abs(float(p.get("edge_percentage", 0))) for p in picks]
    avg_edge = sum(edges) / total if total else 0
    peak_edge = max(edges) if edges else 0

    # Line deviation — only from picks that actually have deviation data
    devs = [abs(float(p.get("line_vs_avg_pct", 0))) for p in picks
            if float(p.get("line_vs_avg_pct", 0)) != 0]
    dev_count = len(devs)
    avg_dev = sum(devs) / dev_count if devs else 0

    # Confidence
    confs = [float(p.get("confidence_score", 0)) for p in picks]
    avg_conf = sum(confs) / total if total else 0

    _thr = int(_QEG_LINE_DEVIATION_THRESHOLD)

    # Build optional bottom sub-stat chips
    _sub_parts: list[str] = []
    _sub_parts.append(
        f'<span class="qeg-sub-chip">'
        f'<span class="qeg-sub-icon">🎯</span>'
        f'{avg_conf:.0f} Avg Confidence</span>'
    )
    if dev_count > 0:
        _sub_parts.append(
            f'<span class="qeg-sub-chip">'
            f'<span class="qeg-sub-icon">📊</span>'
            f'{dev_count} Line Dev{"s" if dev_count != 1 else ""}'
            f' ({avg_dev:.1f}% avg)</span>'
        )

    return (
        '<div class="qeg-banner-v2">'
        '<div class="qeg-banner-v2-inner">'
        # Scanline overlay
        '<div class="qeg-scanline-overlay"></div>'
        # Header
        '<div class="qeg-v2-header">'
        '<div class="qeg-v2-icon-ring"><span>⚡</span></div>'
        '<div class="qeg-v2-title-block">'
        f'<h3 class="qeg-v2-title">QUANTUM EDGE GAP</h3>'
        f'<p class="qeg-v2-subtitle">Extreme-value signals where model edge ≥ {_thr}%</p>'
        '</div>'
        '</div>'
        # Main metrics row
        '<div class="qeg-v2-metrics">'
        # Count block
        '<div class="qeg-v2-count-block">'
        f'<span class="qeg-v2-count-num">{total}</span>'
        '<span class="qeg-v2-count-label">SIGNALS</span>'
        '</div>'
        # Over/Under split bar
        '<div class="qeg-v2-split-block">'
        '<div class="qeg-v2-split-labels">'
        f'<span class="qeg-v2-split-over">{over_ct} OVER</span>'
        f'<span class="qeg-v2-split-under">{under_ct} UNDER</span>'
        '</div>'
        f'<div class="qeg-v2-split-bar">'
        f'<div class="qeg-v2-split-fill-over" style="width:{over_pct:.1f}%"></div>'
        f'<div class="qeg-v2-split-fill-under" style="width:{100 - over_pct:.1f}%"></div>'
        '</div>'
        '</div>'
        # Edge metrics
        '<div class="qeg-v2-edge-block">'
        '<div class="qeg-v2-edge-stat">'
        f'<span class="qeg-v2-edge-val">{avg_edge:.1f}%</span>'
        '<span class="qeg-v2-edge-lbl">AVG EDGE</span>'
        '</div>'
        '<div class="qeg-v2-edge-divider"></div>'
        '<div class="qeg-v2-edge-stat">'
        f'<span class="qeg-v2-edge-val qeg-v2-peak">{peak_edge:.1f}%</span>'
        '<span class="qeg-v2-edge-lbl">PEAK</span>'
        '</div>'
        '</div>'
        '</div>'
        # Sub-stats
        '<div class="qeg-v2-sub">'
        + ''.join(_sub_parts)
        + '</div>'
        '</div>'
        '</div>'
    )


_NBA_HEADSHOT_CDN = "https://cdn.nba.com/headshots/nba/latest/260x190"


def _resolve_headshot_url(player_id: str, player_name: str = "", size: str = "260x190") -> str:
    """Return NBA CDN headshot URL from player_id; fall back to name-based lookup.

    DB-loaded picks lack player_id, so this lets card renderers resolve a photo
    via data.player_profile_service without requiring pre-enriched picks.
    """
    if player_id:
        return f"https://cdn.nba.com/headshots/nba/latest/{size}/{player_id}.png"
    if player_name:
        try:
            from data.player_profile_service import get_headshot_url as _ghu
            url = _ghu(str(player_name))
            if url and size != "260x190":
                url = url.replace("1040x760", size).replace("260x190", size)
            return url or ""
        except Exception:
            pass
    return ""


# SVG circumference for the edge gauge (r=25, C=2*pi*25 ≈ 157)
_GAUGE_CIRCUMFERENCE = 157


_STAT_AVG_KEYS = {
    # Core stats
    "points": "season_pts_avg",
    "rebounds": "season_reb_avg",
    "assists": "season_ast_avg",
    "threes": "season_threes_avg",
    "steals": "season_stl_avg",
    "blocks": "season_blk_avg",
    "turnovers": "season_tov_avg",
    "minutes": "season_minutes_avg",
    # Shooting stats
    "ftm": "season_ftm_avg",
    "fga": "season_fga_avg",
    "fgm": "season_fgm_avg",
    "fta": "season_fta_avg",
    # Rebound splits
    "offensive_rebounds": "season_oreb_avg",
    "defensive_rebounds": "season_dreb_avg",
    # Other
    "personal_fouls": "season_pf_avg",
    # Combo stats (summed from components)
    "points_rebounds": "season_pts_reb_avg",
    "points_assists": "season_pts_ast_avg",
    "rebounds_assists": "season_reb_ast_avg",
    "points_rebounds_assists": "season_pra_avg",
    "blocks_steals": "season_blk_stl_avg",
}


def _edge_gauge_svg(edge_pct: float, display: str) -> str:
    """Return an inline SVG circular gauge for the edge percentage.

    The ring fills proportionally: 0% = empty, ≥50% = full.
    """
    clamped = max(0.0, min(50.0, abs(edge_pct)))
    fill_frac = clamped / 50.0
    offset = _GAUGE_CIRCUMFERENCE * (1 - fill_frac)
    return (
        f'<svg class="qeg-edge-gauge" viewBox="0 0 64 64">'
        f'<circle class="qeg-gauge-bg" cx="32" cy="32" r="25"/>'
        f'<circle class="qeg-gauge-ring" cx="32" cy="32" r="25" '
        f'stroke-dasharray="{_GAUGE_CIRCUMFERENCE}" '
        f'stroke-dashoffset="{offset:.1f}"/>'
        f'<text class="qeg-gauge-text" x="32" y="32">{_html.escape(display)}</text>'
        f'</svg>'
    )


def render_quantum_edge_gap_card_html(result: dict, rank: int = 0) -> str:
    """Return HTML for a single PP-style Quantum Edge Gap prop card.

    Each card is a 175px ``<details>`` element that expands to 310px
    on click, matching the PrizePicks card layout with horizontal scroll.
    """
    player_name = _html.escape(str(result.get("player_name", "Unknown")))
    stat_type = _html.escape(str(result.get("stat_type", "")))
    team = _html.escape(
        str(result.get("player_team", result.get("team", "")))
    )
    platform = _html.escape(str(result.get("platform", "")))
    if platform == "PrizePicks":
        platform = "Smart Pick"
    tier = _html.escape(str(result.get("tier", "Bronze")))
    tier_lower = tier.lower()

    # Prop line
    prop_line = result.get("prop_line", result.get("line", 0))
    try:
        line_val = float(prop_line)
        line_display = f"{line_val:g}"
    except (ValueError, TypeError):
        line_val = 0
        line_display = "\u2014"

    # Confidence
    confidence = result.get("confidence_score", 0)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0
    conf_pct = max(0, min(100, confidence))

    # Edge
    edge = result.get("edge_percentage", result.get("edge", 0))
    try:
        edge_val = float(edge)
        edge_display = f"{edge_val:+.1f}%"
    except (ValueError, TypeError):
        edge_val = 0
        edge_display = "\u2014"

    # Direction
    direction = str(result.get("direction", "")).upper()
    dir_label = "OVER" if direction == "OVER" else "UNDER"
    dir_css = "qeg-prop-over" if direction == "OVER" else "qeg-prop-under"
    dir_arrow = "\u25b2" if direction == "OVER" else "\u25bc"

    # Probability — direction-aware
    prob_over = result.get("probability_over", 0)
    try:
        _prob_raw = float(prob_over)
    except (ValueError, TypeError):
        _prob_raw = 0.5
    _prob_dir = _prob_raw if direction == "OVER" else (1.0 - _prob_raw)
    prob_pct = f"{_prob_dir * 100:.0f}%"
    over_pct_raw = max(0, min(100, _prob_raw * 100))
    under_pct_raw = 100 - over_pct_raw

    # Projection
    projection = result.get("adjusted_projection", 0)
    try:
        proj_val = float(projection)
        proj_display = f"{proj_val:.1f}"
    except (ValueError, TypeError):
        proj_display = "\u2014"

    # Percentiles
    def _safe_fmt(val):
        try:
            return f"{float(val):.1f}"
        except (ValueError, TypeError):
            return "\u2014"

    p10_d = _safe_fmt(result.get("percentile_10", 0))
    p50_d = _safe_fmt(result.get("percentile_50", 0))
    p90_d = _safe_fmt(result.get("percentile_90", 0))

    # Season average
    stat_key_lower = stat_type.lower().replace(" ", "_")
    season_avg_key = _STAT_AVG_KEYS.get(stat_key_lower, "")
    season_avg = result.get(season_avg_key, 0) if season_avg_key else 0
    try:
        season_avg = float(season_avg)
    except (ValueError, TypeError):
        season_avg = 0
    avg_display = f"{season_avg:.1f}" if season_avg > 0 else ""

    # Headshot
    player_id = result.get("player_id", "") or ""
    headshot_url = _resolve_headshot_url(player_id, player_name)

    # Stat type display label
    stat_display = _display_stat_name(stat_type)

    # Glow for platinum/gold
    glow = ""
    if tier_lower in ("platinum", "gold"):
        glow = f" qeg-prop-{tier_lower}"

    # Opponent + game info
    opponent = _html.escape(str(result.get("opponent", "")))
    is_home = result.get("is_home")
    if opponent:
        ha = "vs" if is_home else "@"
        game_info = f"{ha} {opponent}"
    else:
        game_info = ""

    # Position
    position = _html.escape(str(result.get("position", "")))
    team_pos_str = " - ".join(filter(None, [team, position]))

    # Button classes
    over_btn_cls = "qeg-btn-over-active" if direction == "OVER" else "qeg-btn-over-inactive"
    under_btn_cls = "qeg-btn-under-active" if direction == "UNDER" else "qeg-btn-under-inactive"
    prob_fill_cls = "qeg-prop-prob-fill-over" if direction == "OVER" else "qeg-prop-prob-fill-under"
    prob_w = _prob_dir * 100
    prob_lbl_cls = "qeg-prop-prob-label-over" if direction == "OVER" else "qeg-prop-prob-label-under"

    # Rank badge
    rank_html = f'<span class="qeg-prop-rank">#{rank}</span>' if rank > 0 else ""

    # Stagger animation delay
    delay_style = f' style="animation-delay:{(rank - 1) * 0.06:.2f}s;"' if rank > 0 else ""

    # Headshot HTML
    _onerror_hide = "this.style.display='none'"
    hs_img = (
        f'<img class="qeg-prop-hs" src="{_html.escape(headshot_url)}" '
        f'alt="{player_name}" loading="lazy" '
        f'onerror="{_onerror_hide}">'
    )

    # == CARD FACE (summary) ==========================================
    platform_span = f'<span class="qeg-prop-platform">{platform}</span>' if platform else ""
    face_html = (
        f'<div class="qeg-prop-status">'
        f'{rank_html}'
        f'<span class="qeg-tier qeg-tier-{tier_lower}">{tier}</span>'
        f'{platform_span}'
        f'</div>'
        f'<div class="qeg-prop-hs-wrap">{hs_img}</div>'
        f'<div class="qeg-prop-team-pos">{team_pos_str}</div>'
        f'<div class="qeg-prop-player-name">{player_name}</div>'
        f'<div class="qeg-prop-game-info">{game_info}</div>'
        f'<div class="qeg-prop-line-area">'
        f'<div class="qeg-prop-big-line">{line_display}</div>'
        f'<div class="qeg-prop-stat-name">{_html.escape(stat_display)}</div>'
        f'</div>'
        f'<div class="qeg-prop-prob-bar">'
        f'<div class="{prob_fill_cls}" style="width:{prob_w:.1f}%;"></div>'
        f'</div>'
        f'<div class="qeg-prop-prob-label {prob_lbl_cls}">{prob_pct}</div>'
        f'<div class="qeg-btn-row">'
        f'<div class="qeg-btn {under_btn_cls}">&#8595; Less</div>'
        f'<div class="qeg-btn {over_btn_cls}">&#8593; More</div>'
        f'</div>'
    )

    # == EXPANDED DETAIL PANEL ========================================
    gauge_svg = _edge_gauge_svg(edge_val, edge_display)
    prop_call = f"{dir_arrow} {dir_label} {line_display} {stat_display}"
    prop_call_cls = "qeg-detail-prop-over" if direction == "OVER" else "qeg-detail-prop-under"

    # Detail header
    _onerror_hide_detail = "this.style.display='none'"
    detail_hs = (
        f'<img class="qeg-detail-hs" src="{_html.escape(headshot_url)}" '
        f'alt="{player_name}" loading="lazy" '
        f'onerror="{_onerror_hide_detail}">'
    )

    # Team badge color
    team_colors = get_team_colors(
        str(result.get("player_team", result.get("team", "")))
    )
    team_bg = team_colors[0] if team_colors else "#4a5568"

    detail_hdr = (
        f'<div class="qeg-detail-hdr">'
        f'{detail_hs}'
        f'<div class="qeg-detail-info">'
        f'<div class="qeg-detail-name">{player_name}</div>'
        f'<div class="qeg-detail-sub">'
        f'<span class="qeg-detail-team-badge" style="background:{team_bg};">{team}</span>'
        f'{(" \u00b7 " + position) if position else ""}'
        f'{(" \u00b7 " + game_info) if game_info else ""}'
        f'</div>'
        f'</div>'
        f'</div>'
    )

    # Avg comparison
    avg_html = ""
    if avg_display:
        avg_html = (
            f'<div class="qeg-detail-avg">'
            f'Season avg <span class="qeg-detail-avg-val">{avg_display}</span>'
            f'</div>'
        )

    expanded_html = (
        f'<div class="qeg-prop-expanded">'
        f'{detail_hdr}'
        f'<div class="qeg-detail-prop-call {prop_call_cls}">{prop_call}</div>'
        f'<div class="qeg-sec-label">Edge &amp; Projection</div>'
        f'<div class="qeg-detail-edge">'
        f'{gauge_svg}'
        f'<div class="qeg-detail-edge-info">'
        f'<div class="qeg-detail-edge-val">{edge_display}</div>'
        f'<div class="qeg-detail-edge-lbl">Model Edge</div>'
        f'</div>'
        f'</div>'
        f'{avg_html}'
        f'<div class="qeg-sec-label">Metrics</div>'
        f'<div class="qeg-detail-metrics">'
        f'<div class="qeg-dm"><div class="qeg-dm-val">{prob_pct}</div><div class="qeg-dm-lbl">Prob</div></div>'
        f'<div class="qeg-dm"><div class="qeg-dm-val">{confidence:.0f}</div><div class="qeg-dm-lbl">SAFE</div></div>'
        f'<div class="qeg-dm"><div class="qeg-dm-val">{edge_display}</div><div class="qeg-dm-lbl">Edge</div></div>'
        f'<div class="qeg-dm"><div class="qeg-dm-val">{proj_display}</div><div class="qeg-dm-lbl">Proj</div></div>'
        f'</div>'
        f'<div class="qeg-sec-label">Distribution</div>'
        f'<div class="qeg-detail-dist">'
        f'<div class="qeg-dd"><div class="qeg-dd-val">{p10_d}</div><div class="qeg-dd-lbl">P10</div></div>'
        f'<div class="qeg-dd qeg-dd-med"><div class="qeg-dd-val">{p50_d}</div><div class="qeg-dd-lbl">MED</div></div>'
        f'<div class="qeg-dd"><div class="qeg-dd-val">{p90_d}</div><div class="qeg-dd-lbl">P90</div></div>'
        f'<div class="qeg-dd qeg-dd-proj"><div class="qeg-dd-val">{proj_display}</div><div class="qeg-dd-lbl">Proj</div></div>'
        f'</div>'
        f'<div class="qeg-sec-label">Direction</div>'
        f'<div class="qeg-detail-force">'
        f'<span class="qeg-df-lbl qeg-df-lbl-over">{over_pct_raw:.0f}%</span>'
        f'<div class="qeg-df-track">'
        f'<div class="qeg-df-fill-over" style="width:{over_pct_raw:.1f}%;"></div>'
        f'<div class="qeg-df-fill-under" style="width:{under_pct_raw:.1f}%;"></div>'
        f'</div>'
        f'<span class="qeg-df-lbl qeg-df-lbl-under">{under_pct_raw:.0f}%</span>'
        f'</div>'
        f'</div>'
    )

    return (
        f'<details class="qeg-prop {dir_css}{glow}"{delay_style}>'
        f'<summary>{face_html}</summary>'
        f'{expanded_html}'
        f'</details>'
    )


# ── Quantum Edge Gap Filtering, Deduplication & Grouping ─────────────────────


def filter_qeg_picks(
    results: list,
    edge_threshold: float | None = None,
    todays_teams: "set | None" = None,
) -> list:
    """Return QEG-qualified picks from *results*.

    Filtering rules:

    1. **Standard lines only** – ``odds_type`` must be ``"standard"`` (or
       absent, which defaults to ``"standard"``).
    2. **Exclude goblins / demons** – any pick whose ``odds_type`` is
       ``"goblin"`` or ``"demon"`` is dropped.
    3. **Qualification** – a pick qualifies if it meets **either** criterion:

       a. **Line deviation** – ``line_vs_avg_pct`` deviates ≥ *threshold* %
          from the season average in the qualifying direction:
          • **OVER**: ``line_vs_avg_pct <= -threshold`` (line 25–100 % below avg).
          • **UNDER**: ``line_vs_avg_pct >= +threshold`` (line 25–100 % above avg).

       b. **Edge percentage** – ``|edge_percentage| >= threshold``.

    4. **Exclude injured/avoided picks** – ``player_is_out`` and
       ``should_avoid`` are both excluded. OUT players have an artificially
       set ``edge_percentage = -50.0`` that would falsely pass Criterion B.

    Parameters
    ----------
    results:
        Full list of analysis result dicts (e.g. ``displayed_results``).
    edge_threshold:
        Minimum threshold %. Defaults to the module-level
        ``_QEG_LINE_DEVIATION_THRESHOLD`` (20.0).
    """
    thr = edge_threshold if edge_threshold is not None else _QEG_LINE_DEVIATION_THRESHOLD
    filtered: list = []
    for r in results:
        # Skip picks for teams not playing tonight when caller supplies the set.
        if todays_teams and r.get("team", "") not in todays_teams:
            continue

        # Skip out/injured players and explicitly avoided picks — these have
        # artificially extreme edge_percentage values (-50.0 for OUT players)
        # that would otherwise trigger Criterion B and produce misleading picks.
        if r.get("player_is_out", False) or r.get("should_avoid", False):
            continue

        odds_type = str(r.get("odds_type", "standard")).strip().lower()
        if odds_type != "standard":
            continue

        line_dev = float(r.get("line_vs_avg_pct", 0))
        direction = str(r.get("direction", "")).upper()
        edge_pct = abs(float(r.get("edge_percentage", 0)))

        # Criterion A: line deviation in the qualifying direction
        line_qualifies = (
            (direction == "OVER" and line_dev <= -thr)
            or (direction == "UNDER" and line_dev >= thr)
        )
        # Criterion B: edge percentage magnitude
        edge_qualifies = edge_pct >= thr

        if line_qualifies or edge_qualifies:
            filtered.append(r)
    return filtered


def deduplicate_qeg_picks(picks: list) -> list:
    """Remove duplicate QEG picks keeping the one with the highest |edge|.

    Duplicates are identified by ``(player_name, stat_type, line)`` tuple.
    """
    seen: dict[tuple, dict] = {}
    for p in picks:
        key = (
            str(p.get("player_name", "")).strip().lower(),
            str(p.get("stat_type", "")).strip().lower(),
            p.get("line", p.get("prop_line", 0)),
        )
        existing = seen.get(key)
        if existing is None or abs(p.get("edge_percentage", 0)) > abs(existing.get("edge_percentage", 0)):
            seen[key] = p
    return list(seen.values())


def render_quantum_edge_gap_grouped_html(picks: list) -> str:
    """Return PP-style HTML grouping QEG picks by player with horizontal scroll.

    Each player gets an expandable row (``<details class="qeg-player-row">``)
    containing a horizontal scroll strip of PP-style prop cards.
    Single-prop players render as a flat horizontal strip without the
    expandable wrapper.
    """
    from collections import OrderedDict

    groups: OrderedDict[str, list] = OrderedDict()
    for p in picks:
        name = p.get("player_name", "Unknown")
        groups.setdefault(name, []).append(p)

    # Separate singles and multi-prop groups so singles render first
    single_groups: list[tuple[str, list]] = []
    multi_groups: list[tuple[str, list]] = []
    for player_name, player_picks in groups.items():
        if len(player_picks) == 1:
            single_groups.append((player_name, player_picks))
        else:
            multi_groups.append((player_name, player_picks))

    parts: list[str] = []
    global_rank = 0

    # ── Singles: all in one horizontal wrap row ──────────────────
    if single_groups:
        single_cards: list[str] = []
        for player_name, player_picks in single_groups:
            global_rank += 1
            single_cards.append(
                render_quantum_edge_gap_card_html(player_picks[0], rank=global_rank)
            )
        parts.append(
            '<div class="qeg-singles-row">'
            + "".join(single_cards)
            + '</div>'
        )

    # ── Multi-prop groups: expandable rows ───────────────────────
    for player_name, player_picks in multi_groups:
        card_htmls = []
        for pp in player_picks:
            global_rank += 1
            card_htmls.append(render_quantum_edge_gap_card_html(pp, rank=global_rank))
        cards_str = "".join(card_htmls)

        best_edge = max(abs(p.get("edge_percentage", 0)) for p in player_picks)
        team = _html.escape(
            str(player_picks[0].get("player_team", player_picks[0].get("team", "")))
        )
        player_id = player_picks[0].get("player_id", "") or ""
        headshot_url = _resolve_headshot_url(player_id, player_name)
        _onerr_sum = "this.style.display='none'"
        headshot_img = (
            f'<img class="qeg-sum-head" src="{_html.escape(headshot_url)}" '
            f'alt="{_html.escape(player_name)}" loading="lazy" '
            f'onerror="{_onerr_sum}">'
            if headshot_url else ""
        )
        prop_label = f"{len(player_picks)} prop{'s' if len(player_picks) != 1 else ''}"

        # Team color for badge
        team_colors = get_team_colors(
            str(player_picks[0].get("player_team", player_picks[0].get("team", "")))
        )
        team_bg = team_colors[0] if team_colors else "#4a5568"

        border_color = "#50a874"  # default green
        # If all picks are UNDER, use red
        if all(str(p.get("direction", "")).upper() == "UNDER" for p in player_picks):
            border_color = "#c85555"

        parts.append(
            f'<details class="qeg-player-row" style="border-left-color:{border_color};">'
            f'<summary>'
            f'<span class="qeg-sum-arrow">&#9654;</span>'
            f'{headshot_img}'
            f'<div style="display:flex;flex-direction:column;gap:2px;min-width:0;flex:1;">'
            f'<span class="qeg-sum-name">{_html.escape(player_name)}</span>'
            f'<div style="display:flex;align-items:center;gap:5px;">'
            f'<span class="qeg-sum-team" style="background:{team_bg};">{team}</span>'
            f'<span class="qeg-sum-props">{prop_label}</span>'
            f'</div>'
            f'</div>'
            f'<span class="qeg-sum-edge">Edge {best_edge:.1f}%</span>'
            f'</summary>'
            f'<div class="qeg-player-body">'
            f'<div class="qeg-props-scroll">{cards_str}</div>'
            f'</div>'
            f'</details>'
        )

    return "".join(parts)


# ── Gold Tier Banner ──────────────────────────────────────────────────────────

def render_gold_tier_banner_html() -> str:
    """Return the Gold Tier picks banner HTML."""
    return (
        '<div class="qam-gold-banner">'
        '<h3>🥇 Gold Tier Picks</h3>'
        '<p>'
        'High-confidence picks with strong model projections and favorable matchups. '
        'Gold picks are ideal for your core entry legs.'
        '</p>'
        '</div>'
    )


# ── Best Single Bets Header ──────────────────────────────────────────────────

def render_best_single_bets_header_html() -> str:
    """Return the Best Single Bets section header HTML."""
    return (
        '<div class="qam-section-header qam-section-header-single">'
        '<h3>🏆 Best Single Bets</h3>'
        '<p>Top individual picks ranked by SAFE Score™ — Silver tier and above</p>'
        '</div>'
    )


# ── Strongly Suggested Parlays Header ─────────────────────────────────────────

def render_parlays_header_html() -> str:
    """Return the Strongly Suggested Parlays section header HTML."""
    return (
        '<div class="espn-parlay-section-header">'
        '<div class="espn-parlay-section-left">'
        '<div class="espn-parlay-section-icon">AI</div>'
        '<div>'
        '<h3 class="espn-parlay-section-title">AI-Optimized Parlays</h3>'
        '<p class="espn-parlay-section-sub">Multi-leg combos ranked by combined EDGE Score\u2122 &mdash; diversified across games</p>'
        '</div>'
        '</div>'
        '<div class="espn-parlay-section-badge">SMART PICK PRO</div>'
        '</div>'
    )


# ── Parlay Combo Card ────────────────────────────────────────────────────────

def render_parlay_card_html(entry: dict, card_index: int) -> str:
    """Return HTML for a single parlay-combo entry card.

    Parameters
    ----------
    entry : dict
        Parlay entry with keys: num_legs, combo_type, picks, reasons,
        strategy, combined_prob, avg_edge, safe_avg.
        Optionally ``raw_picks`` with full result dicts and ``game_groups``
        mapping ``matchup_label → [pick_strings]``.
    card_index : int
        Zero-based index; top-2 entries get a glow border.
    """
    num = entry.get("num_legs", 0)
    label = PARLAY_LABELS.get(num, entry.get("combo_type", ""))
    top_pick = " espn-parlay-top" if card_index < 2 else ""

    # ── Build picks, grouped by game when available ──────────
    game_groups = entry.get("game_groups", {})
    raw_picks = entry.get("raw_picks", [])

    picks_html = '<div class="plc-row">'
    if game_groups:
        for matchup, group_data in game_groups.items():
            if isinstance(group_data, dict):
                legs = group_data.get("picks", [])
            else:
                legs = group_data

            for leg in legs:
                picks_html += _render_single_leg_html(leg, raw_picks)
    else:
        for pick_str in entry.get("picks", []):
            picks_html += _render_leg_from_string(pick_str, raw_picks)
    picks_html += '</div>'

    # ── Reason tags ──────────────────────────────────────────
    reasons = entry.get("reasons", [])
    reason_html = ""
    if reasons:
        tags = "".join(
            f'<span class="espn-parlay-tag">{_html.escape(r)}</span>'
            for r in reasons
        )
        reason_html = f'<div class="espn-parlay-tags">{tags}</div>'
    elif entry.get("strategy"):
        tag = f'<span class="espn-parlay-tag">{_html.escape(entry["strategy"])}</span>'
        reason_html = f'<div class="espn-parlay-tags">{tag}</div>'

    # ── Stats footer ─────────────────────────────────────────
    combined = entry.get("combined_prob", 0)
    avg_edge = entry.get("avg_edge", 0)
    avg_conf = entry.get("safe_avg", "—")

    edge_color = _POSITIVE_COLOR if avg_edge > 0 else _NEGATIVE_COLOR

    # Rank label
    rank_labels = {0: "TOP PICK", 1: "RUNNER-UP"}
    rank_label = rank_labels.get(card_index, f"#{card_index + 1}")

    # SAFE score bar width (clamp 0-100)
    try:
        safe_val = float(avg_conf)
    except (ValueError, TypeError):
        safe_val = 0
    bar_width = max(0, min(100, safe_val))

    # SAFE bar color by tier
    if safe_val >= 80:
        bar_color = "#00D559"
    elif safe_val >= 60:
        bar_color = "#2D9EFF"
    else:
        bar_color = "#6B7A9A"

    # Edge color badge style
    if avg_edge > 0:
        edge_badge = (
            f'<span class="espn-parlay-stat-num" '
            f'style="color:#00D559;">{avg_edge:+.1f}%</span>'
        )
    else:
        edge_badge = (
            f'<span class="espn-parlay-stat-num" '
            f'style="color:#F24336;">{avg_edge:+.1f}%</span>'
        )

    return (
        f'<div class="espn-parlay-card{top_pick}" style="animation-delay:{card_index * 0.08}s;">'
        # Top bar
        f'<div class="espn-parlay-topbar">'
        f'<span class="espn-parlay-rank">{_html.escape(rank_label)}</span>'
        f'<span class="espn-parlay-label">{_html.escape(label)}</span>'
        f'</div>'
        # Main content — vertical picks
        f'<div class="espn-parlay-body">'
        f'<div class="espn-parlay-picks">'
        f'{picks_html}'
        f'</div>'
        f'</div>'
        # Tags
        f'{reason_html}'
        # Footer stats — metric cells like .pc-m
        f'<div class="espn-parlay-footer">'
        f'<div class="espn-parlay-stat">'
        f'<span class="espn-parlay-stat-num espn-parlay-safe">{combined:.0f}%</span>'
        f'<span class="espn-parlay-stat-lbl">PROB</span>'
        f'</div>'
        f'<div class="espn-parlay-stat">'
        f'{edge_badge}'
        f'<span class="espn-parlay-stat-lbl">AVG EDGE</span>'
        f'</div>'
        f'<div class="espn-parlay-stat">'
        f'<span class="espn-parlay-stat-num">{num}</span>'
        f'<span class="espn-parlay-stat-lbl">LEGS</span>'
        f'</div>'
        f'<div class="espn-parlay-stat">'
        f'<span class="espn-parlay-stat-num espn-parlay-safe">{avg_conf}</span>'
        f'<div style="width:100%;max-width:60px;height:4px;background:rgba(255,255,255,0.06);'
        f'border-radius:100px;margin-top:5px;overflow:hidden;'
        f'box-shadow:inset 0 1px 2px rgba(0,0,0,0.2);">'
        f'<div style="width:{bar_width}%;height:100%;background:{bar_color};'
        f'border-radius:100px;box-shadow:0 0 4px {bar_color};"></div>'
        f'</div>'
        f'<span class="espn-parlay-stat-lbl">SAFE SCORE</span>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _render_game_group_label(matchup: str, meta: dict) -> str:
    """Render the game group header with team logos, abbreviations, and W-L records.

    Parameters
    ----------
    matchup : str
        Matchup label like ``'BOS @ LAL'``.
    meta : dict
        Game metadata with keys: ``home_team``, ``away_team``,
        ``home_record``, ``away_record``, ``home_conf_rank``,
        ``away_conf_rank``.  May be empty for fallback labels.
    """
    away_team = meta.get("away_team", "")
    home_team = meta.get("home_team", "")

    # If we have structured meta, render the rich label with logos
    if away_team and home_team:
        away_color, _ = get_team_colors(away_team)
        home_color, _ = get_team_colors(home_team)
        away_logo = _safe_logo_url(away_team)
        home_logo = _safe_logo_url(home_team)
        away_rec = _html.escape(meta.get("away_record", ""))
        home_rec = _html.escape(meta.get("home_record", ""))
        safe_away = _html.escape(away_team)
        safe_home = _html.escape(home_team)

        away_rec_html = f' <span class="espn-parlay-team-rec">({away_rec})</span>' if away_rec else ""
        home_rec_html = f' <span class="espn-parlay-team-rec">({home_rec})</span>' if home_rec else ""

        _onerror_logo = f"this.onerror=null;this.src='{_NBA_LOGO_FALLBACK}'"
        return (
            f'<div class="espn-parlay-matchup">'
            f'<div class="espn-parlay-team">'
            f'<img class="espn-parlay-team-logo" '
            f'src="{away_logo}" alt="{safe_away}" '
            f'onerror="{_onerror_logo}">'
            f'<span class="espn-parlay-team-name" style="color:{away_color};">{safe_away}</span>'
            f'{away_rec_html}'
            f'</div>'
            f'<span class="espn-parlay-vs">@</span>'
            f'<div class="espn-parlay-team">'
            f'<img class="espn-parlay-team-logo" '
            f'src="{home_logo}" alt="{safe_home}" '
            f'onerror="{_onerror_logo}">' 
            f'<span class="espn-parlay-team-name" style="color:{home_color};">{safe_home}</span>'
            f'{home_rec_html}'
            f'</div>'
            f'</div>'
        )

    # Fallback: plain text label (no game context available)
    safe_matchup = _html.escape(matchup)
    return (
        f'<div class="espn-parlay-matchup">'
        f'<span class="espn-parlay-team-name" style="color:#90d0a8;">{safe_matchup}</span>'
        f'</div>'
    )


def _render_single_leg_html(leg_info: dict, raw_picks: list) -> str:
    """Render one pick leg as a hero-style mini card.

    Parameters
    ----------
    leg_info : dict
        Full analysis result dict with ``player_name``, ``player_team``,
        ``player_id``, ``direction``, ``line``, ``stat_type``,
        ``edge_percentage``, ``tier``, ``confidence_score``, etc.
    raw_picks : list
        Full raw pick dicts (used as fallback for edge/tier lookup).
    """
    pname = _html.escape(str(leg_info.get("player_name", "")))
    team = _html.escape((leg_info.get("player_team", leg_info.get("team", "")) or "").upper())
    direction = (leg_info.get("direction", "") or "").upper()
    line = leg_info.get("line", "")
    raw_stat = (leg_info.get("stat_type", "") or "").lower().strip()
    stat = _html.escape(_display_stat_name(raw_stat))
    edge = leg_info.get("edge_percentage", 0) or 0
    tier = (leg_info.get("tier", "") or "").lower()
    conf = leg_info.get("confidence_score", 0) or 0

    try:
        line_val = f'{float(line):g}'
    except (ValueError, TypeError):
        line_val = str(line) if line else "\u2014"

    # Direction
    dir_label = "MORE" if direction == "OVER" else "LESS"
    dir_arrow = "&#8593;" if direction == "OVER" else "&#8595;"

    # Tier class
    tier_cls = ""
    if tier == "platinum":
        tier_cls = " plc-platinum"
    elif tier == "gold":
        tier_cls = " plc-gold"

    # Headshot
    player_id = leg_info.get("player_id", "") or ""
    headshot_url = _resolve_headshot_url(player_id, leg_info.get("player_name", "") or "")
    team_colors = get_team_colors(leg_info.get("player_team", leg_info.get("team", "")) or "")
    team_color = team_colors[0] if team_colors else "rgba(255,255,255,0.12)"

    _onerror_hide_plc = "this.style.display='none'"
    headshot_html = (
        f'<div class="plc-hs-wrap">'
        f'<img class="plc-hs" '
        f'style="--plc-team-color:{team_color};" '
        f'src="{headshot_url}" alt="{pname}" '
        f'onerror="{_onerror_hide_plc}">'
        f'</div>'
    ) if headshot_url else ""

    # Tier badge
    tier_badge = ""
    if tier in ("platinum", "gold", "silver"):
        tier_badge = (
            f'<span class="plc-tier plc-tier-{tier}">'
            f'{tier.title()}</span>'
        )

    # Edge color
    edge_color = "#00D559" if edge > 0 else "#F24336"
    edge_sign = "+" if edge > 0 else ""

    return (
        f'<div class="plc-card{tier_cls}">'
        # Tier + team status row
        f'<div class="plc-status">'
        f'{tier_badge}'
        f'</div>'
        # Headshot
        f'{headshot_html}'
        # Player info
        f'<div class="plc-team">{team}</div>'
        f'<div class="plc-name">{pname}</div>'
        # Big line
        f'<div class="plc-line-area">'
        f'<div class="plc-line">{_html.escape(line_val)}</div>'
        f'<div class="plc-stat">{stat}</div>'
        f'</div>'
        # Direction button
        f'<div class="plc-dir" data-dir="{_html.escape(direction)}">'
        f'{dir_arrow} {dir_label}</div>'
        # Bottom metrics: Edge + Confidence
        f'<div class="plc-metrics">'
        f'<div class="plc-m">'
        f'<div class="plc-m-val" style="color:{edge_color};">{edge_sign}{edge:.1f}%</div>'
        f'<div class="plc-m-lbl">Edge</div>'
        f'</div>'
        f'<div class="plc-m">'
        f'<div class="plc-m-val">{conf:.0f}</div>'
        f'<div class="plc-m-lbl">Conf</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _render_leg_from_string(pick_str: str, raw_picks: list) -> str:
    """Render a legacy pick string as a styled leg row.

    Falls back to matching the player name against raw_picks for edge/tier.
    """
    parts = pick_str.split(" ", 1)
    pname = _html.escape(parts[0]) if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    # Try to find matching raw pick for edge/tier
    edge = 0.0
    tier = ""
    direction = ""
    for rp in raw_picks:
        if rp.get("player_name", "") == (parts[0] if parts else ""):
            edge = rp.get("edge_percentage", 0) or 0
            tier = (rp.get("tier", "") or "").lower()
            direction = (rp.get("direction", "") or "").upper()
            break

    # Parse direction from rest string if not found
    if not direction:
        rest_upper = rest.upper()
        if rest_upper.startswith("OVER"):
            direction = "OVER"
        elif rest_upper.startswith("UNDER"):
            direction = "UNDER"

    dir_cls = "espn-leg-over" if direction == "OVER" else "espn-leg-under"
    dir_label = _html.escape(direction)

    # Remove direction from rest to avoid duplication
    rest_cleaned = rest
    if direction and rest.upper().startswith(direction):
        rest_cleaned = rest[len(direction):].strip()

    tier_html = ""
    if tier in ("platinum", "gold", "silver"):
        tier_html = f'<span class="espn-leg-tier espn-leg-tier-{tier}">{tier.title()}</span>'

    edge_color = _POSITIVE_COLOR if edge > 0 else _NEGATIVE_COLOR

    return (
        f'<div class="espn-leg-row">'
        f'<div class="espn-leg-left">'
        f'<span class="espn-leg-player">{pname}</span>'
        f'<span class="espn-leg-dir {dir_cls}">{dir_label}</span>'
        f'<span class="espn-leg-detail">{_html.escape(rest_cleaned)}</span>'
        f'{tier_html}'
        f'</div>'
        f'<span class="espn-leg-edge" style="color:{edge_color};">{edge:+.1f}%</span>'
        f'</div>'
    )


# ── Game Matchup Card (replaces plain expander labels) ───────────────────────

def render_game_matchup_card_html(
    away_team: str,
    home_team: str,
    away_record: str = "",
    home_record: str = "",
    n_players: int = 0,
    n_props: int = 0,
) -> str:
    """Return an HTML matchup banner with team logos, colors, records,
    and prop/player counts for the QAM game group headers.

    Uses a horizontal split-bar layout with team-color gradient accents.
    """
    away_color, _ = get_team_colors(away_team)
    home_color, _ = get_team_colors(home_team)
    away_logo = _safe_logo_url(away_team)
    home_logo = _safe_logo_url(home_team)
    safe_away = _html.escape(str(away_team))
    safe_home = _html.escape(str(home_team))
    _onerror_logo_qam = f"this.onerror=null;this.src='{_NBA_LOGO_FALLBACK}'"
    safe_away_rec = _html.escape(str(away_record)) if away_record else ""
    safe_home_rec = _html.escape(str(home_record)) if home_record else ""

    away_rec_html = (
        f'<span class="qam-mu-record">{safe_away_rec}</span>'
        if safe_away_rec else ""
    )
    home_rec_html = (
        f'<span class="qam-mu-record">{safe_home_rec}</span>'
        if safe_home_rec else ""
    )

    return (
        f'<div class="qam-mu-bar" style="'
        f'--away-clr:{away_color};--home-clr:{home_color};">'
        # Away side
        f'<div class="qam-mu-side qam-mu-away">'
        f'<img class="qam-mu-logo" src="{away_logo}" alt="{safe_away}" '
        f'onerror="{_onerror_logo_qam}">' 
        f'<div class="qam-mu-team-info">'
        f'<span class="qam-mu-abbrev" style="color:{away_color};">'
        f'{safe_away}</span>'
        f'{away_rec_html}'
        f'</div>'
        f'</div>'
        # Centre divider
        f'<div class="qam-mu-centre">'
        f'<span class="qam-mu-at">@</span>'
        f'<div class="qam-mu-counts">'
        f'<span class="qam-mu-count">'
        f'👤 {n_players}</span>'
        f'<span class="qam-mu-count">'
        f'📋 {n_props}</span>'
        f'</div>'
        f'</div>'
        # Home side
        f'<div class="qam-mu-side qam-mu-home">'
        f'<div class="qam-mu-team-info" style="text-align:right;">'
        f'<span class="qam-mu-abbrev" style="color:{home_color};">'
        f'{safe_home}</span>'
        f'{home_rec_html}'
        f'</div>'
        f'<img class="qam-mu-logo" src="{home_logo}" alt="{safe_home}" '
        f'onerror="{_onerror_logo_qam}">' 
        f'</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════
# TOP 3 TONIGHT — Hero Cards
# ═══════════════════════════════════════════════════════════════

def render_hero_section_html(top_picks: list) -> str:
    """Build the Top 3 Tonight hero section HTML.

    Parameters
    ----------
    top_picks : list
        Up to 3 analysis result dicts, pre-sorted by confidence descending.

    Returns
    -------
    str
        Complete HTML for the hero section (empty string if no picks).
    """
    if not top_picks:
        return ""

    cards: list[str] = []
    for idx, r in enumerate(top_picks[:3]):
        name = _html.escape(r.get("player_name", "Unknown"))
        team = _html.escape((r.get("player_team", "") or "").upper())
        opp = r.get("opponent", "")
        is_home = r.get("is_home")
        if opp:
            ha = "vs" if is_home else "@"
            game_info = f"{ha} {_html.escape(opp)}"
        else:
            game_info = ""

        raw_stat = (r.get("stat_type", "") or "").lower().strip()
        stat = _html.escape(_display_stat_name(raw_stat))
        direction = (r.get("direction", "OVER") or "OVER").upper()
        dir_label = "MORE" if direction == "OVER" else "LESS"
        dir_arrow = "&#8593;" if direction == "OVER" else "&#8595;"
        try:
            line_val_num = float(r.get("prop_line", r.get("line", 0)))
            line_val = f'{line_val_num:g}'
        except (ValueError, TypeError):
            line_val_num = 0
            line_val = "\u2014"

        tier = r.get("tier", "Gold")
        conf = r.get("confidence_score", 0)
        edge = r.get("edge_percentage", 0)
        _prob_over_raw = float(r.get("probability_over", 0) or 0)
        prob = (_prob_over_raw if direction == "OVER" else 1.0 - _prob_over_raw) * 100

        # Confidence color
        if conf >= 80:
            conf_color = "#00D559"
        elif conf >= 65:
            conf_color = "#F9C62B"
        else:
            conf_color = "#2D9EFF"

        # ── Projection ───────────────────────────────────────
        try:
            proj_val = float(r.get("adjusted_projection", 0) or 0)
        except (ValueError, TypeError):
            proj_val = 0
        proj_display = f'{proj_val:.1f}' if proj_val else "\u2014"

        # Projection vs Line bar
        proj_bar_html = ""
        if proj_val and line_val_num:
            diff = proj_val - line_val_num
            bar_color = "#00D559" if diff > 0 else "#F24336"
            bar_label = f'+{diff:.1f}' if diff > 0 else f'{diff:.1f}'
            bar_width = min(abs(diff / line_val_num * 100), 100) if line_val_num else 0
            proj_bar_html = (
                f'<div class="qam-hero-proj-bar">'
                f'<div class="qam-hero-proj-bar-label">'
                f'<span style="color:#6B7A9A;">Line {_html.escape(line_val)}</span>'
                f'<span style="color:{bar_color};font-weight:700;">'
                f'Proj {proj_display} ({bar_label})</span>'
                f'</div>'
                f'<div class="qam-hero-proj-bar-track">'
                f'<div class="qam-hero-proj-bar-fill" '
                f'style="width:{bar_width:.0f}%;background:{bar_color};"></div>'
                f'</div>'
                f'</div>'
            )

        # ── Headshot with team-colored ring ──────────────────
        player_id = r.get("player_id", "") or ""
        headshot_url = _resolve_headshot_url(player_id, name, size="1040x760")
        team_colors = get_team_colors(r.get("player_team", "") or "")
        team_color = team_colors[0] if team_colors else "rgba(255,255,255,0.12)"
        _onerror_hero = "this.style.display='none'"
        headshot_html = (
            f'<div class="qam-hero-hs-wrap">'
            f'<img class="qam-hero-headshot" '
            f'style="--hero-team-color:{team_color};" '
            f'src="{headshot_url}" alt="{name}" '
            f'onerror="{_onerror_hero}">'
            f'</div>'
        ) if headshot_url else ""

        # ── Simulation range ─────────────────────────────────
        try:
            p10 = float(r.get("percentile_10", 0) or 0)
        except (ValueError, TypeError):
            p10 = 0
        try:
            p90 = float(r.get("percentile_90", 0) or 0)
        except (ValueError, TypeError):
            p90 = 0
        range_html = ""
        if p10 and p90:
            range_html = (
                f'<div class="qam-hero-range">'
                f'<span class="qam-hero-range-label">SIM RANGE</span>'
                f'<span class="qam-hero-range-vals">'
                f'{p10:.1f} &mdash; {p90:.1f}</span>'
                f'</div>'
            )

        # Projection color
        proj_color = "#00D559" if proj_val > line_val_num else "#F24336"

        cards.append(
            f'<div class="qam-hero-card" data-tier="{_html.escape(tier)}" '
            f'style="animation-delay:{idx * 120}ms;">'
            f'<span class="qam-hero-rank">#{idx + 1}</span>'
            # Status bar: tier + team
            f'<div class="qam-hero-status">'
            f'<span class="qam-hero-tier" data-tier="{_html.escape(tier)}">'
            f'{_html.escape(tier)}</span>'
            f'</div>'
            # Centered headshot
            f'{headshot_html}'
            # Player info centered
            f'<div class="qam-hero-team-pos">{team}</div>'
            f'<div class="qam-hero-name">{name}</div>'
            f'<div class="qam-hero-game-info">{game_info}</div>'
            # Big line number + stat
            f'<div class="qam-hero-line-area">'
            f'<div class="qam-hero-line">{_html.escape(line_val)}</div>'
            f'<div class="qam-hero-stat">{stat}</div>'
            f'</div>'
            # Direction button (active pill)
            f'<div class="qam-hero-dir" data-dir="{_html.escape(direction)}">'
            f'{dir_arrow} {dir_label}</div>'
            # Projection bar
            f'{proj_bar_html}'
            # Metrics grid
            f'<div class="qam-hero-metrics">'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val" style="color:{conf_color};">{conf:.0f}</div>'
            f'<div class="qam-hero-metric-label">Confidence</div>'
            f'</div>'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val" style="color:#00D559;">{edge:+.1f}%</div>'
            f'<div class="qam-hero-metric-label">Edge</div>'
            f'</div>'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val">{prob:.0f}%</div>'
            f'<div class="qam-hero-metric-label">Probability</div>'
            f'</div>'
            f'<div class="qam-hero-metric">'
            f'<div class="qam-hero-metric-val" style="color:{proj_color};">{proj_display}</div>'
            f'<div class="qam-hero-metric-label">Projection</div>'
            f'</div>'
            f'</div>'
            # Sim range
            f'{range_html}'
            f'</div>'
        )

    return (
        f'<div class="qam-hero-section">'
        f'<div class="qam-hero-label">\U0001f9e0 Neural Top Signals \u2014 Tonight</div>'
        f'<div class="qam-hero-grid">{"".join(cards)}</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════
# PLATFORM AI PICKS — Stunning electric AI-themed cards
# ═══════════════════════════════════════════════════════════════

def render_platform_picks_html(picks: list) -> str:
    """Build the Platform AI Picks section HTML.

    Parameters
    ----------
    picks : list
        Analysis result dicts for platform picks, pre-sorted by confidence.

    Returns
    -------
    str
        Complete HTML for the Platform AI Picks section.
    """
    if not picks:
        return ""

    cards: list[str] = []
    for idx, r in enumerate(picks):
        name = _html.escape(r.get("player_name", "Unknown"))
        team = _html.escape((r.get("player_team", "") or "").upper())
        _raw_platform = r.get("platform", "Platform") or "Platform"
        if _raw_platform == "PrizePicks":
            _raw_platform = "Smart Pick"
        platform = _html.escape(_raw_platform)
        opp = r.get("opponent", "")
        is_home = r.get("is_home")
        if opp:
            ha = "vs" if is_home else "@"
            game_info = f"{ha} {_html.escape(opp)}"
        else:
            game_info = ""

        raw_stat = (r.get("stat_type", "") or "").lower().strip()
        stat = _html.escape(_display_stat_name(raw_stat))
        direction = (r.get("direction", "OVER") or "OVER").upper()
        dir_label = "MORE" if direction == "OVER" else "LESS"
        dir_arrow = "&#8593;" if direction == "OVER" else "&#8595;"
        try:
            line_val_num = float(r.get("prop_line", r.get("line", 0)))
            line_val = f'{line_val_num:g}'
        except (ValueError, TypeError):
            line_val_num = 0
            line_val = "\u2014"

        tier = r.get("tier", "Gold")
        conf = r.get("confidence_score", 0)
        edge = r.get("edge_percentage", 0)
        _prob_over_raw = float(r.get("probability_over", 0) or 0)
        prob = (_prob_over_raw if direction == "OVER" else 1.0 - _prob_over_raw) * 100

        # Confidence color (AI purple/blue palette)
        if conf >= 80:
            conf_color = "#c084fc"
        elif conf >= 65:
            conf_color = "#fbbf24"
        else:
            conf_color = "#60a5fa"

        # Projection
        try:
            proj_val = float(r.get("adjusted_projection", 0) or 0)
        except (ValueError, TypeError):
            proj_val = 0
        proj_display = f'{proj_val:.1f}' if proj_val else "\u2014"

        # Projection bar
        proj_bar_html = ""
        if proj_val and line_val_num:
            diff = proj_val - line_val_num
            bar_color = "#c084fc" if diff > 0 else "#60a5fa"
            bar_label = f'+{diff:.1f}' if diff > 0 else f'{diff:.1f}'
            bar_width = min(abs(diff / line_val_num * 100), 100) if line_val_num else 0
            proj_bar_html = (
                f'<div class="plat-proj-bar">'
                f'<div class="plat-proj-bar-label">'
                f'<span style="color:#7c82a8;">Line {_html.escape(line_val)}</span>'
                f'<span style="color:{bar_color};font-weight:700;">'
                f'Proj {proj_display} ({bar_label})</span>'
                f'</div>'
                f'<div class="plat-proj-bar-track">'
                f'<div class="plat-proj-bar-fill" '
                f'style="width:{bar_width:.0f}%;"></div>'
                f'</div>'
                f'</div>'
            )

        # Headshot
        player_id = r.get("player_id", "") or ""
        headshot_url = _resolve_headshot_url(player_id, name, size="1040x760")
        _onerror_plat = "this.style.display='none'"
        headshot_html = (
            f'<div class="plat-hs-wrap">'
            f'<img class="plat-headshot" '
            f'src="{headshot_url}" alt="{name}" '
            f'onerror="{_onerror_plat}">'
            f'</div>'
        ) if headshot_url else ""

        # Sim range
        try:
            p10 = float(r.get("percentile_10", 0) or 0)
        except (ValueError, TypeError):
            p10 = 0
        try:
            p90 = float(r.get("percentile_90", 0) or 0)
        except (ValueError, TypeError):
            p90 = 0
        range_html = ""
        if p10 and p90:
            range_html = (
                f'<div class="plat-range">'
                f'<span class="plat-range-label">SIM RANGE</span>'
                f'<span class="plat-range-vals">'
                f'{p10:.1f} &mdash; {p90:.1f}</span>'
                f'</div>'
            )

        # Projection color
        proj_color = "#c084fc" if proj_val > line_val_num else "#60a5fa"

        cards.append(
            f'<div class="plat-card">'
            f'<span class="plat-rank">#{idx + 1}</span>'
            # Status bar: platform badge
            f'<div class="plat-status">'
            f'<span class="plat-badge">'
            f'<span class="plat-badge-icon">&#9889;</span> '
            f'{platform} AI</span>'
            f'</div>'
            # Headshot
            f'{headshot_html}'
            # Player info
            f'<div class="plat-team-pos">{team}</div>'
            f'<div class="plat-name">{name}</div>'
            f'<div class="plat-game-info">{game_info}</div>'
            # Line area
            f'<div class="plat-line-area">'
            f'<div class="plat-line">{_html.escape(line_val)}</div>'
            f'<div class="plat-stat">{stat}</div>'
            f'</div>'
            # Direction
            f'<div class="plat-dir" data-dir="{_html.escape(direction)}">'
            f'{dir_arrow} {dir_label}</div>'
            # Projection bar
            f'{proj_bar_html}'
            # Metrics
            f'<div class="plat-metrics">'
            f'<div class="plat-metric">'
            f'<div class="plat-metric-val" style="color:{conf_color};">{conf:.0f}</div>'
            f'<div class="plat-metric-label">Confidence</div>'
            f'</div>'
            f'<div class="plat-metric">'
            f'<div class="plat-metric-val" style="color:#c084fc;">{edge:+.1f}%</div>'
            f'<div class="plat-metric-label">Edge</div>'
            f'</div>'
            f'<div class="plat-metric">'
            f'<div class="plat-metric-val">{prob:.0f}%</div>'
            f'<div class="plat-metric-label">Probability</div>'
            f'</div>'
            f'<div class="plat-metric">'
            f'<div class="plat-metric-val" style="color:{proj_color};">{proj_display}</div>'
            f'<div class="plat-metric-label">Projection</div>'
            f'</div>'
            f'</div>'
            # Sim range
            f'{range_html}'
            f'</div>'
        )

    return (
        f'<div class="plat-section">'
        f'<div class="plat-label">&#9889; Platform AI Picks</div>'
        f'<div class="plat-grid">{"".join(cards)}</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════
# QUICK VIEW — Compact one-line-per-pick table
# ═══════════════════════════════════════════════════════════════

def render_quick_view_html(results: list, best_pick_keys: set | None = None) -> str:
    """Build the Quick View compact table HTML.

    Parameters
    ----------
    results : list
        Analysis result dicts (active only, pre-sorted).
    best_pick_keys : set or None
        Set of (player_name, stat_type_lower, line) tuples that are top picks.

    Returns
    -------
    str
        Complete HTML table for Quick View mode.
    """
    if not results:
        return ""

    best_pick_keys = best_pick_keys or set()
    rows: list[str] = []

    for r in results:
        if r.get("player_is_out", False):
            continue

        name = _html.escape(r.get("player_name", "Unknown"))
        raw_stat = (r.get("stat_type", "") or "").lower().strip()
        stat = _html.escape(_display_stat_name(raw_stat))
        direction = (r.get("direction", "OVER") or "OVER").upper()
        dir_label = "MORE" if direction == "OVER" else "LESS"
        try:
            line_val = f'{float(r.get("prop_line", r.get("line", 0))):g}'
        except (ValueError, TypeError):
            line_val = "—"

        tier = r.get("tier", "Bronze")
        conf = r.get("confidence_score", 0)
        edge = r.get("edge_percentage", 0)

        # Confidence color
        if conf >= 80:
            conf_color = "#00D559"
        elif conf >= 65:
            conf_color = "#FFD700"
        elif conf >= 50:
            conf_color = "#00b4ff"
        else:
            conf_color = "#94A3B8"

        # Badges
        badges = ""
        rk = (
            r.get("player_name", ""),
            (r.get("stat_type", "") or "").lower(),
            r.get("prop_line", r.get("line", 0)),
        )
        if rk in best_pick_keys:
            badges += '<span class="qam-quick-badge qam-quick-badge-top">⭐ TOP</span>'
        if r.get("should_avoid", False):
            badges += '<span class="qam-quick-badge qam-quick-badge-avoid">⚠️</span>'

        rows.append(
            f'<tr>'
            f'<td><span class="qam-quick-player">{name}</span>{badges}</td>'
            f'<td><span class="qam-quick-stat">{stat}</span></td>'
            f'<td><span class="qam-quick-line">{_html.escape(line_val)}</span></td>'
            f'<td><span class="qam-quick-dir" data-dir="{_html.escape(direction)}">'
            f'{dir_label}</span></td>'
            f'<td><span class="qam-quick-conf" style="color:{conf_color};">'
            f'{conf:.0f}</span></td>'
            f'<td><span class="qam-quick-edge">{edge:+.1f}%</span></td>'
            f'<td><span class="qam-quick-tier" data-tier="{_html.escape(tier)}">'
            f'{_html.escape(tier)}</span></td>'
            f'</tr>'
        )

    return (
        f'<table class="qam-quick-table">'
        f'<thead><tr>'
        f'<th>Player</th><th>Stat</th><th>Line</th>'
        f'<th>Dir</th><th>Conf</th><th>Edge</th><th>Tier</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table>'
    )
