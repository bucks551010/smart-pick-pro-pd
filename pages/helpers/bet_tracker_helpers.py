# ============================================================
# FILE: pages/helpers/bet_tracker_helpers.py
# PURPOSE: Helper functions for the Bet Tracker page.
#          Extracted from pages/11_📈_Bet_Tracker.py to reduce page size.
# ============================================================
import logging
import math

_logger = logging.getLogger(__name__)


def build_tier_performance_rows(tier_perf: dict) -> list:
    """Build table rows for Win Rate by Tier section."""
    tier_order = ["Platinum", "Gold", "Silver", "Bronze"]
    return [
        {
            "Tier": t,
            "Total": tier_perf[t].get("total", 0),
            "Wins":  tier_perf[t].get("wins", 0),
            "Losses": tier_perf[t].get("losses", 0),
            "Win Rate": f"{tier_perf[t].get('win_rate', 0):.1f}%",
        }
        for t in tier_order if t in tier_perf
    ]


def build_platform_performance_rows(plat_perf: dict) -> list:
    """Build table rows for Win Rate by Platform section."""
    return [
        {
            "Platform": p,
            "Total": d.get("total", 0),
            "Wins":  d.get("wins", 0),
            "Win Rate": f"{d.get('win_rate', 0):.1f}%",
        }
        for p, d in plat_perf.items()
    ]


def build_stat_performance_rows(stat_perf: dict) -> list:
    """Build table rows for Win Rate by Stat Type section."""
    return [
        {
            "Stat Type": s.capitalize(),
            "Total": d.get("total", 0),
            "Wins":  d.get("wins", 0),
            "Win Rate": f"{d.get('win_rate', 0):.1f}%",
        }
        for s, d in sorted(stat_perf.items())
    ]


def build_bet_type_performance_rows(bet_type_perf: dict) -> list:
    """Build table rows for Win Rate by Bet Classification section."""
    return [
        {
            "Bet Type":  bt.title(),
            "Total":     d.get("total", 0),
            "Wins":      d.get("wins", 0),
            "Losses":    d.get("losses", 0),
            "Win Rate":  f"{d.get('win_rate', 0):.1f}%",
        }
        for bt, d in sorted(bet_type_perf.items())
    ]


def classify_uncertain_subtype(notes: str) -> str:
    """
    Classify an uncertain pick's risk subtype from its notes string.

    Returns one of: "Conflict", "Variance", "Fatigue", "Regression", "Other".
    """
    notes_lower = (notes or "").lower()
    if "conflict" in notes_lower:
        return "Conflict"
    if "variance" in notes_lower or "high-variance" in notes_lower:
        return "Variance"
    if "fatigue" in notes_lower or "back-to-back" in notes_lower or "blowout" in notes_lower:
        return "Fatigue"
    if "regression" in notes_lower or "hot streak" in notes_lower or "inflated" in notes_lower:
        return "Regression"
    return "Other"


def get_uncertain_subtype_counts(uncertain_bets: list) -> dict:
    """
    Count how many uncertain picks fall into each risk subtype.

    Args:
        uncertain_bets: List of bet dicts with "notes" field.

    Returns:
        Dict mapping subtype name → count (only non-zero counts included).
    """
    counts: dict = {"Conflict": 0, "Variance": 0, "Fatigue": 0, "Regression": 0, "Other": 0}
    for bet in uncertain_bets:
        subtype = classify_uncertain_subtype(bet.get("notes", ""))
        counts[subtype] = counts.get(subtype, 0) + 1
    return {k: v for k, v in counts.items() if v > 0}


def calculate_win_rate(wins: int, total: int) -> float:
    """Calculate win rate percentage, safe against division by zero."""
    if total <= 0:
        return 0.0
    return round(wins / total * 100, 1)


def format_streak(streak: int) -> str:
    """Format a win/loss streak as a human-readable string."""
    if streak > 0:
        return f"🔥 {streak}W streak"
    elif streak < 0:
        return f"❄️ {abs(streak)}L streak"
    return "➡️ No streak"


def get_calendar_heatmap_html(bets_by_date: dict, num_days: int = 42) -> str:
    """
    Render a GitHub-style calendar heatmap showing daily win rates.

    Args:
        bets_by_date: Dict mapping date strings (YYYY-MM-DD) to lists of bet dicts.
        num_days: How many days to show (default 42 = 6 weeks).

    Returns:
        HTML string with the heatmap grid.
    """
    import datetime as _dt

    today = _dt.date.today()
    # Build cells for the last num_days days
    cells_html = ""
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Header row with day labels
    header = "".join(
        f'<div class="heatmap-day-label">{d}</div>' for d in day_labels
    )

    # Pad to start on Monday
    start_date = today - _dt.timedelta(days=num_days - 1)
    # Align to Monday
    offset = start_date.weekday()  # 0=Mon
    start_date -= _dt.timedelta(days=offset)

    for i in range((today - start_date).days + 1):
        d = start_date + _dt.timedelta(days=i)
        d_str = d.isoformat()
        day_bets = bets_by_date.get(d_str, [])

        if not day_bets:
            cells_html += f'<div class="heatmap-cell heatmap-cell-empty" title="{d_str}: no bets"></div>'
            continue

        wins = sum(1 for b in day_bets if b.get("result") == "WIN")
        losses = sum(1 for b in day_bets if b.get("result") == "LOSS")
        total_resolved = wins + losses
        pending = sum(1 for b in day_bets if b.get("result") not in ("WIN", "LOSS", "EVEN"))

        if total_resolved == 0:
            cells_html += (
                f'<div class="heatmap-cell heatmap-cell-neutral" '
                f'title="{d_str}: {len(day_bets)} bet(s), all pending"></div>'
            )
            continue

        wr = wins / total_resolved * 100

        if wr >= 70:
            cell_class = "heatmap-cell-green-4"
        elif wr >= 55:
            cell_class = "heatmap-cell-green-2"
        elif wr >= 45:
            cell_class = "heatmap-cell-neutral"
        elif wr >= 30:
            cell_class = "heatmap-cell-red-2"
        else:
            cell_class = "heatmap-cell-red-4"

        title = f"{d_str}: {wins}W/{losses}L ({wr:.0f}%)"
        if pending:
            title += f" +{pending} pending"
        cells_html += f'<div class="heatmap-cell {cell_class}" title="{title}"></div>'

    return (
        f'<div style="margin:10px 0;">'
        f'<div class="heatmap-grid">{header}{cells_html}</div>'
        f'<div style="display:flex;gap:6px;align-items:center;margin-top:8px;font-size:0.70rem;color:#3A4460;">'
        f'<span>Less</span>'
        f'<div style="width:12px;height:12px;border-radius:2px;background:rgba(255,68,68,0.55);"></div>'
        f'<div style="width:12px;height:12px;border-radius:2px;background:rgba(255,204,0,0.20);"></div>'
        f'<div style="width:12px;height:12px;border-radius:2px;background:rgba(0,213,89,0.35);"></div>'
        f'<div style="width:12px;height:12px;border-radius:2px;background:rgba(0,213,89,0.80);"></div>'
        f'<span>More</span>'
        f'</div>'
        f'</div>'
    )


def get_achievement_ring_html(icon: str, name: str, desc: str, progress: float, earned: bool) -> str:
    """
    Render an achievement badge with a circular SVG progress ring.

    Args:
        icon: Emoji icon for the badge.
        name: Badge name.
        desc: Badge description.
        progress: Progress toward next badge (0.0 to 1.0). 1.0 = earned.
        earned: Whether the badge is fully earned.

    Returns:
        HTML string for the badge card.
    """
    import html as _h

    radius = 30
    circumference = 2 * math.pi * radius
    dash = circumference * min(progress, 1.0)
    gap = circumference - dash

    ring_color = "#00D559" if earned else "#3A4460"
    badge_class = "badge-earned" if earned else "badge-locked"
    opacity = "1" if earned else "0.45"

    return (
        f'<div class="achievement-ring-wrap">'
        f'<svg width="70" height="70" viewBox="0 0 70 70">'
        f'<circle cx="35" cy="35" r="{radius}" fill="none" '
        f'stroke="rgba(255,255,255,0.06)" stroke-width="4"/>'
        f'<circle cx="35" cy="35" r="{radius}" fill="none" '
        f'stroke="{ring_color}" stroke-width="4" stroke-linecap="round" '
        f'stroke-dasharray="{dash:.1f} {gap:.1f}" '
        f'transform="rotate(-90 35 35)"/>'
        f'<text x="35" y="40" text-anchor="middle" font-size="20" '
        f'style="opacity:{opacity};">{icon}</text>'
        f'</svg>'
        f'<div class="achievement-ring-label {badge_class}">{_h.escape(name)}</div>'
        f'<div class="achievement-ring-desc">{_h.escape(desc)}</div>'
        + (f'<div class="achievement-ring-progress">{progress*100:.0f}% complete</div>'
           if not earned else '')
        + f'</div>'
    )


def get_level_badge_html(total_bets: int, win_rate: float) -> str:
    """
    Determine and render the user's level badge.

    Level system: Rookie → Starter → All-Star → MVP → GOAT
    Based on total volume + win rate.

    Returns:
        HTML string for the level badge.
    """
    if total_bets >= 500 and win_rate >= 60:
        level_class = "level-goat"
        level_name = "🐐 GOAT"
    elif total_bets >= 200 and win_rate >= 58:
        level_class = "level-mvp"
        level_name = "🏆 MVP"
    elif total_bets >= 100 and win_rate >= 55:
        level_class = "level-allstar"
        level_name = "⭐ All-Star"
    elif total_bets >= 30 and win_rate >= 50:
        level_class = "level-starter"
        level_name = "🏀 Starter"
    else:
        level_class = "level-rookie"
        level_name = "🌱 Rookie"

    return f'<span class="level-badge {level_class}">{level_name}</span>'
