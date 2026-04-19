"""Achievements tab for Bet Tracker."""
import datetime
import streamlit as st
from pages.helpers.bet_tracker_data import (
    cached_load_all_bets,
    RESULT_EMOJI,
)
from pages.helpers.bet_tracker_helpers import (
    get_achievement_ring_html,
    get_level_badge_html,
)


# ── Level / XP system ────────────────────────────────────────
_LEVELS = [
    (0,    "Rookie"),
    (25,   "Contender"),
    (75,   "Starter"),
    (150,  "All-Star"),
    (300,  "MVP"),
    (500,  "Hall of Fame"),
    (1000, "GOAT"),
]

def _get_level(total_bets: int):
    _label = "Rookie"
    _next_thresh = 25
    for thresh, name in _LEVELS:
        if total_bets >= thresh:
            _label = name
    for thresh, name in _LEVELS:
        if thresh > total_bets:
            _next_thresh = thresh
            break
    else:
        _next_thresh = total_bets + 1
    return _label, _next_thresh


# ── Achievement definitions ───────────────────────────────────
_ACHIEVEMENTS = [
    {"key": "first_win", "name": "🏆 First Win", "desc": "Win your first bet", "check": lambda s: s["wins"] >= 1},
    {"key": "ten_wins", "name": "🔟 Ten-Timer", "desc": "Win 10 bets", "check": lambda s: s["wins"] >= 10},
    {"key": "fifty_wins", "name": "🏅 Fifty Club", "desc": "Win 50 bets", "check": lambda s: s["wins"] >= 50},
    {"key": "hundred_wins", "name": "💯 Centurion", "desc": "Win 100 bets", "check": lambda s: s["wins"] >= 100},
    {"key": "streak_3", "name": "🔥 Hot Streak 3", "desc": "Win 3 in a row", "check": lambda s: s["max_streak"] >= 3},
    {"key": "streak_5", "name": "🔥🔥 On Fire", "desc": "Win 5 in a row", "check": lambda s: s["max_streak"] >= 5},
    {"key": "streak_10", "name": "🔥🔥🔥 Inferno", "desc": "Win 10 in a row", "check": lambda s: s["max_streak"] >= 10},
    {"key": "perfect_day", "name": "✨ Perfect Day", "desc": "Win every bet on a day (3+)", "check": lambda s: s["perfect_days"] >= 1},
    {"key": "comeback_king", "name": "👑 Comeback King", "desc": "Go positive after being -5u", "check": lambda s: s["biggest_comeback"] >= 5},
    {"key": "wr_60", "name": "📊 60% Club", "desc": "Maintain 60%+ win rate (20+ bets)", "check": lambda s: s["win_rate"] >= 60 and s["resolved"] >= 20},
    {"key": "wr_70", "name": "🌟 70% Elite", "desc": "Maintain 70%+ win rate (30+ bets)", "check": lambda s: s["win_rate"] >= 70 and s["resolved"] >= 30},
    {"key": "week_warrior", "name": "📅 7-Day Warrior", "desc": "Bet on 7 consecutive days", "check": lambda s: s["max_day_streak"] >= 7},
    {"key": "plat_winner", "name": "💎 Platinum Winner", "desc": "Win a Platinum-tier bet", "check": lambda s: s["plat_wins"] >= 1},
    {"key": "triple_plat", "name": "💎💎💎 Triple Platinum", "desc": "Win 3 Platinum bets in one day", "check": lambda s: s["max_plat_day"] >= 3},
]


def _compute_stats(bets):
    resolved = sorted(
        [b for b in bets if b.get("result") in ("WIN", "LOSS")],
        key=lambda b: (b.get("bet_date", ""), b.get("id", 0)),
    )
    wins = sum(1 for b in resolved if b.get("result") == "WIN")
    losses = sum(1 for b in resolved if b.get("result") == "LOSS")
    wr = round(wins / max(wins + losses, 1) * 100, 1)

    max_streak = 0
    cur_streak = 0
    biggest_comeback = 0
    min_pnl = 0.0
    cum_pnl = 0.0
    for b in resolved:
        if b.get("result") == "WIN":
            cur_streak += 1
            cum_pnl += 1.0
        else:
            cur_streak = 0
            cum_pnl -= 1.0
        max_streak = max(max_streak, cur_streak)
        if cum_pnl < min_pnl:
            min_pnl = cum_pnl
        if min_pnl < 0 and cum_pnl > 0:
            biggest_comeback = max(biggest_comeback, abs(min_pnl))

    # Per-day stats
    by_date: dict = {}
    for b in resolved:
        by_date.setdefault(b.get("bet_date", ""), []).append(b)
    perfect_days = 0
    for d, day in by_date.items():
        _dw = sum(1 for b in day if b.get("result") == "WIN")
        if _dw == len(day) and len(day) >= 3:
            perfect_days += 1

    # Day streak (consecutive days with at least one bet)
    dates = sorted({b.get("bet_date", "")[:10] for b in bets if b.get("bet_date")})
    max_day_streak = 0
    cur_day_streak = 0
    prev_date = None
    for ds in dates:
        try:
            d = datetime.date.fromisoformat(ds)
        except ValueError:
            continue
        if prev_date and (d - prev_date).days == 1:
            cur_day_streak += 1
        else:
            cur_day_streak = 1
        max_day_streak = max(max_day_streak, cur_day_streak)
        prev_date = d

    plat_wins = sum(1 for b in resolved if b.get("result") == "WIN" and str(b.get("tier", "")).lower() == "platinum")
    _plat_days: dict = {}
    for b in resolved:
        if b.get("result") == "WIN" and str(b.get("tier", "")).lower() == "platinum":
            _plat_days[b.get("bet_date", "")] = _plat_days.get(b.get("bet_date", ""), 0) + 1
    max_plat_day = max(_plat_days.values()) if _plat_days else 0

    return {
        "total": len(bets),
        "resolved": len(resolved),
        "wins": wins,
        "losses": losses,
        "win_rate": wr,
        "max_streak": max_streak,
        "perfect_days": perfect_days,
        "biggest_comeback": biggest_comeback,
        "max_day_streak": max_day_streak,
        "plat_wins": plat_wins,
        "max_plat_day": max_plat_day,
        "by_date": by_date,
    }


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("🏆 Achievements & Badges")

    all_bets = cached_load_all_bets(exclude_linked=False)
    if not all_bets:
        st.info("📭 No bets logged yet. Start betting to unlock achievements!")
        return

    stats = _compute_stats(all_bets)

    # Level badge
    level_name, next_thresh = _get_level(stats["total"])
    progress = stats["total"] / max(next_thresh, 1) * 100
    st.markdown(get_level_badge_html(stats["total"], stats["win_rate"]), unsafe_allow_html=True)
    st.progress(min(progress / 100, 1.0), text=f"{stats['total']} / {next_thresh} bets to next level")

    st.divider()

    # Key stats
    _c = st.columns(5)
    _c[0].metric("Total Bets", stats["total"])
    _c[1].metric("Resolved", stats["resolved"])
    _c[2].metric("Win Rate", f"{stats['win_rate']:.1f}%")
    _c[3].metric("Best Streak", f"🔥 {stats['max_streak']}")
    _c[4].metric("Perfect Days", f"✨ {stats['perfect_days']}")

    st.divider()

    # Achievements grid
    unlocked = [a for a in _ACHIEVEMENTS if a["check"](stats)]
    locked = [a for a in _ACHIEVEMENTS if not a["check"](stats)]

    st.markdown(f"### Unlocked ({len(unlocked)}/{len(_ACHIEVEMENTS)})")
    if unlocked:
        _cols = st.columns(min(len(unlocked), 4))
        for i, a in enumerate(unlocked):
            with _cols[i % len(_cols)]:
                st.markdown(
                    get_achievement_ring_html(a["name"][:2], a["name"][2:].strip(), a["desc"], 1.0, True),
                    unsafe_allow_html=True,
                )
    else:
        st.info("No achievements unlocked yet. Keep betting!")

    if locked:
        st.markdown(f"### Locked ({len(locked)})")
        _cols = st.columns(min(len(locked), 4))
        for i, a in enumerate(locked):
            with _cols[i % len(_cols)]:
                st.markdown(
                    get_achievement_ring_html(a["name"][:2], a["name"][2:].strip(), a["desc"], 0.0, False),
                    unsafe_allow_html=True,
                )

    st.divider()

    # Timeline
    st.markdown("### 📅 Recent Activity Timeline")
    by_date = stats["by_date"]
    if by_date:
        for date_str in sorted(by_date.keys(), reverse=True)[:14]:
            day = by_date[date_str]
            w = sum(1 for b in day if b.get("result") == "WIN")
            l = sum(1 for b in day if b.get("result") == "LOSS")
            t = w + l
            wr = round(w / max(t, 1) * 100, 0) if t else None
            dot = "🟢" if wr is not None and wr >= 55 else "🔴" if wr is not None and wr < 45 else "🟡"
            st.markdown(
                f"{dot} **{date_str}** — {len(day)} bets · "
                f"{'✅' + str(w) + ' ❌' + str(l) if t else '⏳ all pending'}"
                + (f" · {wr:.0f}% WR" if wr is not None else "")
            )
    else:
        st.info("No resolved bets to show.")
