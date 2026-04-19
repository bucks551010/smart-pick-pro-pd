# ============================================================
# FILE: pages/2_🔬_Prop_Scanner.py
# PURPOSE: Prop Scanner — enter, upload, or pull live prop lines,
#          then scan, filter, and analyse them with Smart Scan
#          and Quick Analysis cards.
# CONNECTS TO: data_manager.py, sportsbook_service.py, theme.py
# ============================================================

import streamlit as st
import datetime
import csv
import io

from data.data_manager import (
    load_players_data,
    load_props_data,
    load_props_from_session,
    save_props_to_session,
    get_all_player_names,
    parse_props_from_csv_text,
    get_csv_template,
    find_player_by_name,
    enrich_prop_with_player_data,
    validate_props_against_roster,
    get_player_status,
    load_injury_status,
)
from data.platform_mappings import (
    normalize_stat_type,
    detect_platform_from_stat_names,
    COMBO_STATS,
    FANTASY_SCORING,
)
try:
    from engine import SIMPLE_STAT_TYPES as _SIMPLE_STAT_TYPES
except ImportError:
    _SIMPLE_STAT_TYPES = frozenset({
        "points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers",
    })

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Prop Scanner — SmartBetPro NBA",
    page_icon="🔬",
    layout="wide",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import (
    get_global_css, get_education_box_html, get_prop_scanner_css,
    get_platform_badge_html, get_line_type_badge_html,
    get_value_gauge_html, get_confidence_badge_html,
    get_line_movement_html, get_prop_card_html,
)
st.markdown(get_global_css(), unsafe_allow_html=True)
st.markdown(get_prop_scanner_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Hero Banner & Floating Widget ─────────────
from utils.components import render_joseph_hero_banner, inject_joseph_floating
st.session_state["joseph_page_context"] = "page_prop_scanner"
inject_joseph_floating()

# ── Premium Status (partial gate — some features restricted) ──
from utils.auth import is_premium_user as _is_premium_user
try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH as _PREM_PATH
except Exception:
    _PREM_PATH = "/14_%F0%9F%92%8E_Subscription_Level"
FREE_PROP_LIMIT = 5   # Free users can manually enter up to 5 props
SMART_SCAN_PAGE_SIZE = 30  # Number of Smart Scan results per page
user_is_premium = _is_premium_user()

st.title("🔬 Prop Scanner")
st.markdown("Enter prop lines manually, upload a CSV, or **load live lines** directly from the platforms!")

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Prop Scanner — Three Ways to Load Props

    **Option 1: Manual Entry**
    - Use the form to enter individual props (player name, stat type, line)
    - Good for adding specific props not available on platforms

    **Option 2: CSV Upload**
    - Download the template, fill in your props, upload the file
    - Best for bulk entry or importing from your own research

    **Option 3: Get Live Platform Lines**
    - Go to the **📡 Live Games** page and click **📊 Get Live Props & Analyze**
    - Retrieves real live lines from all major sportsbooks via The Odds API

    💡 **Pro Tips:**
    - Load live lines for the most accurate analysis
    - Use the filter/sort options to focus on specific players or stat types
    """)

st.markdown(get_education_box_html(
    "📖 What is a Prop Bet?",
    """
    <strong>Prop Bet</strong>: A bet on whether a player will exceed (Over) or fall short of (Under) a
    statistical threshold set by the platform.<br><br>
    Example: "LeBron James Points OVER 24.5" — you win if LeBron scores 25 or more points.<br><br>
    <strong>How to read a prop line</strong>: The number (24.5) is the threshold.
    Always bet OVER or UNDER — never equal (that's a push/tie).<br><br>
    <strong>Platforms</strong>: PrizePicks, Underdog Fantasy, DraftKings Pick6 — each platform may have different line values.
    """
), unsafe_allow_html=True)

# ============================================================
# SECTION: Load Available Data (cached)
# ============================================================

@st.cache_data(ttl=300)
def _cached_load_players():
    return load_players_data()

@st.cache_data(ttl=300)
def _cached_load_injuries():
    return load_injury_status()

players_data = _cached_load_players()
all_player_names = get_all_player_names(players_data)

# Simple stats + combo + fantasy stat types
valid_stat_types = (
    sorted(_SIMPLE_STAT_TYPES)
    + sorted(COMBO_STATS.keys())
    + sorted(FANTASY_SCORING.keys())
    + ["double_double", "triple_double"]
)
valid_platforms = [
    "PrizePicks", "Underdog Fantasy", "DraftKings Pick6",
]

# ── Import platform service (optional — app works without it) ──
try:
    from data.sportsbook_service import (
        get_all_sportsbook_props,
        build_cross_platform_comparison,
        recommend_best_platform,
        summarize_props_by_platform,
        find_new_players_from_props,
        extract_active_players_from_props,
    )
    from data.data_manager import (
        save_platform_props_to_session,
        load_platform_props_from_session,
        save_platform_props_to_csv,
    )
    SPORTSBOOK_SERVICE_AVAILABLE = True
except ImportError:
    SPORTSBOOK_SERVICE_AVAILABLE = False

# ── Load current props & injury data once ─────────────────────
current_props = load_props_from_session(st.session_state)
injury_status_map = _cached_load_injuries()

# ── Injury-status classification ──────────────────────────────
UNAVAILABLE_STATUSES = {"Out", "Doubtful", "Injured Reserve"}
GTD_STATUSES = {"GTD", "Questionable", "Day-to-Day"}

unavailable_props = []
gtd_props = []
healthy_props = []

for prop in current_props:
    player_name = prop.get("player_name", "")
    status_info = get_player_status(player_name, injury_status_map)
    player_status = status_info.get("status", "Active")
    if player_status in UNAVAILABLE_STATUSES:
        unavailable_props.append((prop, player_status, status_info.get("injury_note", "")))
    elif player_status in GTD_STATUSES:
        gtd_props.append((prop, player_status, status_info.get("injury_note", "")))
    else:
        healthy_props.append((prop, player_status, status_info.get("injury_note", "")))


# ── Confidence score calculator ───────────────────────────────
def compute_confidence_score(line_diff_pct, player_status, form_label=""):
    """Combine line-vs-avg, injury status, and form into a 0-100 score."""
    score = 50  # base
    # Line value component (up to ±30)
    try:
        diff = float(line_diff_pct)
    except (TypeError, ValueError):
        diff = 0
    if diff < -20:
        score += 30
    elif diff < -10:
        score += 20
    elif diff < -5:
        score += 10
    elif diff > 20:
        score -= 20
    elif diff > 10:
        score -= 10

    # Injury component (up to -30)
    if player_status in UNAVAILABLE_STATUSES:
        score -= 30
    elif player_status in GTD_STATUSES:
        score -= 15

    # Form component (up to ±20)
    if "Hot" in str(form_label):
        score += 20
    elif "Cold" in str(form_label):
        score -= 15

    return max(0, min(100, score))


# ── Helper: build enriched display props ──────────────────────
def get_display_props(show_injured):
    """Return (display_props_raw, display_props_enriched) based on injury toggle."""
    if show_injured:
        raw = current_props
    else:
        raw = [p for p, _, _ in healthy_props + gtd_props]
    enriched = [enrich_prop_with_player_data(p, players_data) for p in raw]
    return raw, enriched


# ── Helper: get season avg for a stat type ────────────────────
def get_season_avg(prop, stat_type):
    """Return the season average for a given enriched prop and stat type."""
    stat_key = stat_type.lower()
    stat_avg_map = {
        "points": prop.get("season_pts_avg", 0),
        "rebounds": prop.get("season_reb_avg", 0),
        "assists": prop.get("season_ast_avg", 0),
    }
    return float(stat_avg_map.get(stat_key, 0) or 0)


# ── Helper: compute value line signal ─────────────────────────
def get_value_line_label(season_avg, line_diff_pct):
    """Return the Value Line label based on season avg and line diff %."""
    if season_avg and line_diff_pct < -12:
        return "🔥 Low Line"
    elif season_avg and line_diff_pct > 15:
        return "⚠️ High Line"
    elif season_avg:
        return "✅ Fair"
    return "—"


# ── Helper: compute context line description ──────────────────
def get_context_line_label(season_avg, line_diff_pct):
    """Return the Context Line label based on season avg and line diff %."""
    if season_avg and line_diff_pct > 10:
        return f"↑{line_diff_pct:.0f}% above avg"
    elif season_avg and line_diff_pct < -10:
        return f"↓{abs(line_diff_pct):.0f}% below avg"
    elif season_avg:
        return "near avg"
    return "—"


# ── Helper: get status emoji ──────────────────────────────────
STATUS_EMOJI_MAP = {
    "Out": "🔴", "Injured Reserve": "🔴", "Doubtful": "🔴",
    "Questionable": "🟡", "GTD": "🟡", "Day-to-Day": "🟡",
    "Active": "🟢", "Probable": "🟢",
}


# ── Line Movement Tracking ────────────────────────────────────
def detect_line_movements(new_props):
    """Compare new props to previously stored lines and return movement dict."""
    prev_lines = st.session_state.get("_prev_prop_lines", {})
    movements = {}
    new_lines = {}
    for p in new_props:
        key = (p.get("player_name", ""), p.get("stat_type", ""), p.get("platform", ""))
        new_line = float(p.get("line", 0))
        new_lines[key] = new_line
        if key in prev_lines:
            old_line = prev_lines[key]
            if abs(old_line - new_line) > 0.01:
                movements[key] = (old_line, new_line)
    # Store current lines for next comparison
    st.session_state["_prev_prop_lines"] = new_lines
    return movements


line_movements = detect_line_movements(current_props)


# ============================================================
# SECTION: Main Tabs Layout
# ============================================================

tab_table, tab_dashboard, tab_load, tab_manual = st.tabs([
    "📋 Props Table & Smart Scan",
    "📊 Dashboard",
    "🔄 Load Props",
    "✏️ Manual Entry",
])


# ════════════════════════════════════════════════════════════════
# TAB 1: Dashboard — KPI bar, Quick Analysis cards, Value Summary
# ════════════════════════════════════════════════════════════════

with tab_dashboard:
    if not current_props:
        st.info(
            "No props loaded yet. Switch to the **🔄 Load Props** tab to get started, "
            "or use **✏️ Manual Entry** to add individual props."
        )
    else:
        show_injured_dash = st.toggle(
            "👁️ Show injured players",
            value=False,
            key="dash_show_injured",
            help="Include Out/Doubtful players in the dashboard view.",
        )
        _, display_props_enriched = get_display_props(show_injured_dash)

        # ── Line Movement Alerts ──────────────────────────────────
        if line_movements:
            with st.expander(f"📈 Line Movements Detected ({len(line_movements)})", expanded=True):
                for (p_name, s_type, plat), (old_l, new_l) in line_movements.items():
                    mv_html = get_line_movement_html(old_l, new_l)
                    st.markdown(
                        f"**{p_name}** — {s_type.title()} ({plat}): {mv_html}",
                        unsafe_allow_html=True,
                    )

        # ── KPI Summary ───────────────────────────────────────────
        low_count = sum(1 for p in display_props_enriched if float(p.get("line_vs_avg_pct", 0) or 0) < -12)
        high_count = sum(1 for p in display_props_enriched if float(p.get("line_vs_avg_pct", 0) or 0) > 15)
        fair_count = len(display_props_enriched) - low_count - high_count

        kpi_cols = st.columns(5)
        with kpi_cols[0]:
            st.metric("Total Props", len(display_props_enriched))
        with kpi_cols[1]:
            st.metric("🔥 Low Lines (OVER)", low_count)
        with kpi_cols[2]:
            st.metric("⚠️ High Lines (UNDER)", high_count)
        with kpi_cols[3]:
            st.metric("✅ Fair Value", fair_count)
        with kpi_cols[4]:
            st.metric("🏥 Injured", len(unavailable_props))

        # ── Value Summary Banner (HTML) ───────────────────────────
        if low_count + high_count + fair_count > 0:
            st.markdown(
                f'<div style="background:rgba(0,213,89,0.04);border:1px solid rgba(0,213,89,0.13);'
                f'border-radius:6px;padding:8px 14px;margin-bottom:8px;font-size:0.83rem;color:#EEF0F6;">'
                f'📊 <strong>Line Value Summary:</strong> &nbsp; '
                f'<span style="color:#00D559;font-weight:700;">🔥 {low_count} Low (OVER value)</span> &nbsp;·&nbsp; '
                f'<span style="color:#69b4ff;font-weight:600;">✅ {fair_count} Fair</span> &nbsp;·&nbsp; '
                f'<span style="color:#F9C62B;font-weight:700;">⚠️ {high_count} High (UNDER value)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Best Bets Auto-Filter ─────────────────────────────────
        best_bets_active = st.toggle(
            "🎯 Best Bets Only — Show props >10% below avg, healthy, hot form",
            value=False,
            key="best_bets_filter",
        )

        # ── Quick Analysis Cards (lazy-loaded) ────────────────────
        qa_available = False
        try:
            from engine.player_intelligence import (
                build_quick_analysis_rows,
                aggregate_streak_summary,
            )
            from styles.theme import get_player_intel_css, get_form_dots_html, get_qa_card_html, get_qa_kpi_bar_html
            qa_available = True
        except ImportError:
            pass

        if qa_available:
            st.markdown(get_player_intel_css(), unsafe_allow_html=True)
            game_logs_cache = st.session_state.get("game_logs_cache", {})

            with st.spinner("Building quick analysis..."):
                qa_rows = build_quick_analysis_rows(
                    props=current_props,
                    players_data=players_data,
                    game_logs_cache=game_logs_cache,
                    injury_status_map=injury_status_map,
                )

            if qa_rows:
                # ── KPI bar ────────────────────────────────────────
                intel_stubs = [
                    {"player_name": r["player_name"], "form": {"form_label": r["form_label"]}}
                    for r in qa_rows
                ]
                streak_summary = aggregate_streak_summary(intel_stubs)
                flagged_count = sum(1 for r in qa_rows if r.get("is_flagged"))

                st.markdown(
                    get_qa_kpi_bar_html(
                        hot_count=streak_summary["hot_count"],
                        cold_count=streak_summary["cold_count"],
                        flagged_count=flagged_count,
                        total_count=len(qa_rows),
                    ),
                    unsafe_allow_html=True,
                )

                # ── Filters ────────────────────────────────────────
                qa_col1, qa_col2, qa_col3 = st.columns(3)
                with qa_col1:
                    qa_sort_by = st.selectbox(
                        "Sort by",
                        ["Edge % (Best first)", "Hit Rate (Best first)", "Player Name"],
                        key="qa_sort_by",
                    )
                with qa_col2:
                    qa_form_filter = st.selectbox(
                        "Form filter",
                        ["All", "Hot only 🔥", "Cold only 🧊", "No injury flags"],
                        key="qa_form_filter",
                    )
                with qa_col3:
                    qa_stat_filter = st.selectbox(
                        "Stat type",
                        ["All"] + sorted(set(r.get("stat_type", "") for r in qa_rows)),
                        key="qa_stat_filter",
                    )

                # Apply filters
                filtered_qa = qa_rows[:]
                if qa_form_filter == "Hot only 🔥":
                    filtered_qa = [r for r in filtered_qa if "Hot" in r.get("form_label", "")]
                elif qa_form_filter == "Cold only 🧊":
                    filtered_qa = [r for r in filtered_qa if "Cold" in r.get("form_label", "")]
                elif qa_form_filter == "No injury flags":
                    filtered_qa = [r for r in filtered_qa if not r.get("is_flagged")]
                if qa_stat_filter != "All":
                    filtered_qa = [r for r in filtered_qa if r.get("stat_type") == qa_stat_filter]

                # Best bets auto-filter
                if best_bets_active:
                    healthy_names_set = {p.get("player_name", "") for p, _, _ in healthy_props}
                    filtered_qa = [
                        r for r in filtered_qa
                        if r.get("edge_pct", 0) > 10
                        and r.get("player_name", "") in healthy_names_set
                        and "Hot" in r.get("form_label", "")
                    ]

                # Apply sort
                if qa_sort_by == "Edge % (Best first)":
                    filtered_qa.sort(key=lambda r: abs(r.get("edge_pct", 0)), reverse=True)
                elif qa_sort_by == "Hit Rate (Best first)":
                    filtered_qa.sort(key=lambda r: r.get("hit_rate", 0), reverse=True)
                else:
                    filtered_qa.sort(key=lambda r: r.get("player_name", ""))

                # ── Card grid ──────────────────────────────────────
                card_htmls = []
                for qrow in filtered_qa:
                    dots = get_form_dots_html(
                        qrow.get("form_results", []),
                        window=5,
                        prop_line=float(qrow.get("line", 0)),
                    )
                    card_htmls.append(get_qa_card_html(qrow, dots))

                count_bar = (
                    f'<div class="qa-count-bar">'
                    f'<span>Showing <b>{len(filtered_qa)}</b> of '
                    f'<b>{len(qa_rows)}</b> props</span></div>'
                )
                grid_html = (
                    count_bar
                    + '<div class="qa-grid">'
                    + "\n".join(card_htmls)
                    + "</div>"
                )
                st.markdown(grid_html, unsafe_allow_html=True)

                # ── Hot/Cold summary footer ────────────────────────
                if streak_summary["hot_players"]:
                    st.success(
                        f"🔥 **Hot players:** {', '.join(streak_summary['hot_players'][:8])}"
                    )
                if streak_summary["cold_players"]:
                    st.warning(
                        f"🧊 **Cold players:** {', '.join(streak_summary['cold_players'][:8])}"
                    )
            else:
                st.warning("No analysis rows generated.")
        else:
            st.info(f"ℹ️ {len(current_props)} props loaded. Quick Analysis unavailable (player_intelligence module not found).")


# ════════════════════════════════════════════════════════════════
# TAB 2: Load Props — Live pull, CSV upload, Quick Add paste
# ════════════════════════════════════════════════════════════════

with tab_load:
    st.subheader("🔄 Get Live Props")

    # ── Free tier: disable live platform loading ──────────────
    if not user_is_premium:
        st.markdown(
            '<div style="background:rgba(255,94,0,0.08);border:1px solid rgba(255,94,0,0.25);'
            'border-radius:10px;padding:12px 16px;margin-bottom:8px;">'
            '<span style="color:#ff9d00;font-weight:600;">🔒 Premium Feature</span>'
            f' — Live platform loading (all major sportsbooks) requires a '
            f'<a href="{_PREM_PATH}" style="color:#F9C62B;font-weight:700;">Premium subscription</a>. '
            'You can still enter up to 5 props manually on the ✏️ Manual Entry tab.</div>',
            unsafe_allow_html=True,
        )
    elif SPORTSBOOK_SERVICE_AVAILABLE:
        dk_enabled = st.session_state.get("load_draftkings_enabled", True)
        dk_api_key = st.session_state.get("odds_api_key", "").strip()

        # Platform checkboxes
        plat_col_pp, plat_col_ud, plat_col_dk = st.columns(3)
        with plat_col_pp:
            pp_on = st.checkbox("🟢 PrizePicks", value=True, key="scanner_pp_checkbox")
        with plat_col_ud:
            ud_on = st.checkbox("🟡 Underdog Fantasy", value=True, key="scanner_ud_checkbox")
        with plat_col_dk:
            dk_on = st.checkbox(
                "🔵 DraftKings Pick6",
                value=dk_enabled and bool(dk_api_key),
                key="scanner_dk_checkbox",
                disabled=not (dk_enabled and bool(dk_api_key)),
                help="Requires Odds API key — configure on ⚙️ Settings page." if not (dk_enabled and bool(dk_api_key)) else "",
            )

        enabled_platforms = []
        if pp_on:
            enabled_platforms.append("PrizePicks")
        if ud_on:
            enabled_platforms.append("Underdog Fantasy")
        if dk_on:
            enabled_platforms.append("DraftKings Pick6")

        st.markdown(
            f"Get tonight's live prop lines from: **{', '.join(enabled_platforms) if enabled_platforms else 'no platforms enabled'}**. "
            "Configure platforms on the [⚙️ Settings](/Settings) page."
        )

        live_btn_col, live_info_col = st.columns([2, 3])

        with live_btn_col:
            do_load = st.button(
                "🔄 Get Live Props",
                type="primary",
                width="stretch",
                help="Pull tonight's live prop lines from all enabled platforms.",
                disabled=not enabled_platforms,
            )

        with live_info_col:
            cached_platform_props = load_platform_props_from_session(st.session_state)
            if cached_platform_props:
                cached_summary = summarize_props_by_platform(cached_platform_props)
                retrieved_at = cached_platform_props[0].get("retrieved_at", "unknown time") if cached_platform_props else ""
                st.info(
                    f"📦 **{len(cached_platform_props)} props cached** "
                    f"({', '.join(f'{p}: {c}' for p, c in cached_summary.items())}) "
                    f"— retrieved at {retrieved_at[:16] if retrieved_at else 'unknown'}"
                )

        if do_load:
            progress_bar = st.progress(0, text="Starting platform load...")

            def scanner_progress(current, total, msg):
                pct = int((current / max(total, 1)) * 100)
                progress_bar.progress(pct, text=msg)

            # ── Joseph Loading Screen ─────────────────────────────
            try:
                from utils.joseph_loading import joseph_loading_placeholder
                joseph_loader = joseph_loading_placeholder("Loading live props from sportsbooks")
            except Exception:
                joseph_loader = None

            try:
                with st.spinner("Loading live props..."):
                    live_props = get_all_sportsbook_props(
                        include_prizepicks=pp_on,
                        include_underdog=ud_on,
                        include_draftkings=dk_on,
                        odds_api_key=dk_api_key or None,
                        progress_callback=scanner_progress,
                    )

                progress_bar.progress(100, text="Done!")
                if joseph_loader is not None:
                    try:
                        joseph_loader.empty()
                    except Exception:
                        pass

                if live_props:
                    save_platform_props_to_session(live_props, st.session_state)
                    save_platform_props_to_csv(live_props)
                    save_props_to_session(live_props, st.session_state)
                    load_summary = summarize_props_by_platform(live_props)
                    st.success(
                        f"✅ Loaded **{len(live_props)} live props**: "
                        + ", ".join(f"**{p}** ({c})" for p, c in load_summary.items())
                    )
                    missing_players = find_new_players_from_props(live_props, players_data)
                    if missing_players:
                        st.warning(
                            f"⚠️ **{len(missing_players)} player(s)** from platform props are not in your "
                            f"local database: {', '.join(missing_players[:5])}"
                            + (f" and {len(missing_players) - 5} more" if len(missing_players) > 5 else "")
                            + ". Run a **Smart Update** on the 📡 Smart NBA Data page to add their stats."
                        )
                    st.rerun()
                else:
                    st.warning("⚠️ No live props retrieved. Check your internet connection.")
            except Exception as load_err:
                err_str = str(load_err)
                if "WebSocketClosedError" not in err_str and "StreamClosedError" not in err_str:
                    st.error(f"❌ Failed to load live props: {load_err}")
            finally:
                try:
                    progress_bar.empty()
                except Exception:
                    pass
                if joseph_loader is not None:
                    try:
                        joseph_loader.empty()
                    except Exception:
                        pass

        # ── Cross-Platform Comparison Table ───────────────────────
        platform_props = load_platform_props_from_session(st.session_state)
        if platform_props:
            comparison = build_cross_platform_comparison(platform_props)
            multi_platform = {
                key: lines for key, lines in comparison.items()
                if len(lines) >= 2
            }

            if multi_platform:
                with st.expander(
                    f"📊 Cross-Platform Line Comparison ({len(multi_platform)} player+stat combos)",
                    expanded=False,
                ):
                    st.markdown(
                        "Lines available on **multiple platforms** — compare to find the best bet. "
                        "**OVER**: lower line is better. **UNDER**: higher line is better."
                    )

                    comparison_rows = []
                    for (p_name, s_type), lines in sorted(multi_platform.items()):
                        row = {"Player": p_name, "Stat": s_type}
                        for platform in valid_platforms:
                            row[platform] = lines.get(platform, "—")

                        numeric_lines = [v for v in lines.values() if isinstance(v, (int, float))]
                        if len(numeric_lines) >= 2:
                            spread = round(max(numeric_lines) - min(numeric_lines), 1)
                            row["Spread"] = spread
                            best_over_plat = min(lines, key=lambda p: lines[p])
                            row["Best OVER"] = f"{best_over_plat} ({lines[best_over_plat]})"
                            best_under_plat = max(lines, key=lambda p: lines[p])
                            row["Best UNDER"] = f"{best_under_plat} ({lines[best_under_plat]})"
                        else:
                            row["Spread"] = "—"
                            row["Best OVER"] = "—"
                            row["Best UNDER"] = "—"

                        comparison_rows.append(row)

                    if comparison_rows:
                        st.dataframe(comparison_rows, width="stretch", hide_index=True)
                        st.caption(
                            "💡 **Best OVER** = platform with the lowest line (easiest to beat). "
                            "**Best UNDER** = platform with the highest line (most room). "
                            "**Spread** = difference between highest and lowest line."
                        )

    else:
        st.info(
            "ℹ️ Live prop loading requires the `requests` library. "
            "Run `pip install requests` to enable this feature."
        )

    st.divider()

    # ── CSV Upload ────────────────────────────────────────────
    st.subheader("📤 Upload Props CSV")

    if not user_is_premium:
        st.markdown(
            '<div style="background:rgba(255,94,0,0.08);border:1px solid rgba(255,94,0,0.25);'
            'border-radius:10px;padding:12px 16px;">'
            '<span style="color:#ff9d00;font-weight:600;">🔒 Premium Feature</span>'
            f' — CSV upload requires a '
            f'<a href="{_PREM_PATH}" style="color:#F9C62B;font-weight:700;">Premium subscription</a>.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("**Required CSV format:**")
        st.code(
            "player_name,team,stat_type,line,platform,game_date\n"
            "LeBron James,LAL,points,24.5,PrizePicks,2026-03-05\n"
            "Stephen Curry,GSW,threes,3.5,DraftKings Pick6,2026-03-05",
            language="csv",
        )

        template_csv = get_csv_template()
        st.download_button(
            label="⬇️ Download CSV Template",
            data=template_csv,
            file_name="props_template.csv",
            mime="text/csv",
        )

        st.markdown("---")

        uploaded_file = st.file_uploader("Upload your props CSV file", type=["csv"])

        if uploaded_file is not None:
            file_content = uploaded_file.read().decode("utf-8")
            parsed_props, parse_errors = parse_props_from_csv_text(file_content)

            if parse_errors:
                for error in parse_errors:
                    st.warning(f"⚠️ {error}")

            if parsed_props:
                raw_stat_names = [p.get("stat_type", "") for p in parsed_props]
                detected_platform = detect_platform_from_stat_names(raw_stat_names)
                if detected_platform:
                    st.info(f"🔍 Auto-detected platform: **{detected_platform}**")

                for p in parsed_props:
                    raw_stat = p.get("stat_type", "")
                    platform_hint = p.get("platform", detected_platform or "")
                    normalized = normalize_stat_type(raw_stat, platform_hint)
                    if normalized != raw_stat:
                        p["stat_type"] = normalized

                st.success(f"✅ Parsed {len(parsed_props)} props from upload!")

                enriched_preview = [enrich_prop_with_player_data(p, players_data) for p in parsed_props]
                preview_rows = [
                    {
                        "Player": p.get("player_name", ""),
                        "Team": p.get("player_team", p.get("team", "")),
                        "Stat": p.get("stat_type", ""),
                        "Line": p.get("line", ""),
                        "Season Avg": round(p.get("season_pts_avg", 0), 1) if p.get("stat_type") == "points" else "—",
                        "Platform": p.get("platform", ""),
                    }
                    for p in enriched_preview[:10]
                ]
                st.markdown("**Preview:**")
                st.dataframe(preview_rows, width="stretch", hide_index=True)

                if len(parsed_props) > 10:
                    st.caption(f"... and {len(parsed_props) - 10} more")

                replace_col, add_col, _ = st.columns([1, 1, 2])
                with replace_col:
                    if st.button("🔄 Replace All Props", type="primary"):
                        save_props_to_session(parsed_props, st.session_state)
                        st.success(f"Replaced all props with {len(parsed_props)} from upload!")
                        st.rerun()
                with add_col:
                    if st.button("➕ Add to Existing"):
                        existing = load_props_from_session(st.session_state)
                        combined = existing + parsed_props
                        save_props_to_session(combined, st.session_state)
                        st.success(f"Added {len(parsed_props)} props. Total: {len(combined)}")
                        st.rerun()
            else:
                st.error("No valid props found in the uploaded file.")

    st.divider()

    # ── Quick Add (Paste CSV) ─────────────────────────────────
    st.subheader("⚡ Quick Add (Paste CSV data)")
    st.markdown("Paste prop lines directly as CSV text:")

    quick_add_text = st.text_area(
        "Paste CSV data here",
        placeholder="player_name,team,stat_type,line,platform\nLeBron James,LAL,points,24.5,PrizePicks\nStephen Curry,GSW,threes,3.5,DraftKings Pick6",
        height=150,
    )

    if st.button("⚡ Parse & Add Props") and quick_add_text.strip():
        parsed_props_quick, errors_quick = parse_props_from_csv_text(quick_add_text)

        for error in errors_quick:
            st.warning(f"⚠️ {error}")

        if parsed_props_quick:
            for p in parsed_props_quick:
                raw_stat = p.get("stat_type", "")
                platform_hint = p.get("platform", "")
                normalized = normalize_stat_type(raw_stat, platform_hint)
                if normalized != raw_stat:
                    p["stat_type"] = normalized

            existing = load_props_from_session(st.session_state)
            combined = existing + parsed_props_quick
            save_props_to_session(combined, st.session_state)
            st.success(f"✅ Added {len(parsed_props_quick)} props! Total: {len(combined)}")
            st.rerun()
        else:
            st.error("Could not parse any props from the input.")


# ════════════════════════════════════════════════════════════════
# TAB 3: Props Table & Smart Scan
# ════════════════════════════════════════════════════════════════

with tab_table:
    show_injured_table = st.toggle(
        "👁️ Show injured players anyway (Out/Doubtful)",
        value=False,
        key="table_show_injured",
        help="By default, players confirmed Out or Doubtful are hidden.",
    )

    # Summary banner for removed props
    if unavailable_props and not show_injured_table:
        st.error(
            f"⚠️ **{len(unavailable_props)} prop(s) hidden** — player(s) are confirmed "
            f"**Out or Doubtful**: "
            + ", ".join(f"**{p.get('player_name','')}**" for p, _, _ in unavailable_props)
            + ". Enable *'Show injured players anyway'* to view them."
        )

    _, display_enriched_table = get_display_props(show_injured_table)

    st.subheader(f"📋 Current Props ({len(display_enriched_table)} displayed / {len(current_props)} total)")

    # ── Smart Scan — always visible (not in expander) ─────────
    if display_enriched_table:
        st.markdown(
            "🔍 **Smart Scan** — Narrow down to the most promising props. "
            "Filters apply to the table and carry into analysis."
        )

        # Filter bar — Row 1
        filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns([2, 2, 2, 2, 3])
        with filter_col1:
            filter_platform = st.multiselect(
                "Platform",
                options=valid_platforms,
                default=[],
                placeholder="All platforms",
                key="scan_platform_filter",
            )
        with filter_col2:
            filter_stat = st.multiselect(
                "Stat Type",
                options=sorted({p.get("stat_type", "").capitalize() for p in display_enriched_table if p.get("stat_type")}),
                default=[],
                placeholder="All stats",
                key="scan_stat_filter",
            )
        with filter_col3:
            filter_team = st.multiselect(
                "Team",
                options=sorted({p.get("player_team", p.get("team", "")) for p in display_enriched_table if p.get("player_team") or p.get("team")}),
                default=[],
                placeholder="All teams",
                key="scan_team_filter",
            )
        with filter_col4:
            filter_line_type = st.multiselect(
                "Line Type",
                options=["⚪ Standard", "🟢 Goblin", "🔴 Demon"],
                default=[],
                placeholder="All types",
                key="scan_line_type_filter",
            )
        with filter_col5:
            search_player = st.text_input(
                "🔎 Search player",
                placeholder="Type player name...",
                key="scan_player_search",
            )

        # Filter bar — Row 2
        filter_col6, filter_col7, filter_col8, filter_col9 = st.columns([2, 3, 3, 3])
        with filter_col6:
            filter_healthy_only = st.toggle(
                "Healthy Only",
                value=True,
                key="scan_healthy_filter",
                help="Hide GTD/Out players from Smart Scan results",
            )
        with filter_col7:
            filter_line_range = st.slider(
                "Line Range",
                min_value=0.0, max_value=60.0, value=(0.0, 60.0), step=0.5,
                key="scan_line_range",
            )
        with filter_col8:
            filter_confidence = st.slider(
                "Min Confidence",
                min_value=0, max_value=100, value=0, step=5,
                key="scan_confidence_min",
            )
        with filter_col9:
            filter_value_signal = st.multiselect(
                "Value Line",
                options=["🔥 Low Line", "✅ Fair", "⚠️ High Line"],
                default=[],
                placeholder="All signals",
                key="scan_value_filter",
            )

        # Apply Smart Scan filters
        scanned_props = display_enriched_table[:]
        if filter_platform:
            scanned_props = [p for p in scanned_props if p.get("platform", "") in filter_platform]
        if filter_stat:
            scanned_props = [p for p in scanned_props if p.get("stat_type", "").capitalize() in filter_stat]
        if filter_team:
            scanned_props = [p for p in scanned_props if p.get("player_team", p.get("team", "")) in filter_team]
        if filter_line_type:
            _line_type_map = {"goblin": "🟢 Goblin", "demon": "🔴 Demon"}
            scanned_props = [
                p for p in scanned_props
                if _line_type_map.get(p.get("odds_type", "standard"), "⚪ Standard") in filter_line_type
            ]
        line_min, line_max = filter_line_range
        scanned_props = [p for p in scanned_props if line_min <= float(p.get("line", 0)) <= line_max]
        if filter_healthy_only:
            healthy_names_set = {p.get("player_name", "") for p, _, _ in healthy_props}
            scanned_props = [p for p in scanned_props if p.get("player_name", "") in healthy_names_set]
        if search_player.strip():
            search_lower = search_player.strip().lower()
            scanned_props = [p for p in scanned_props if search_lower in p.get("player_name", "").lower()]
        if filter_confidence > 0:
            def _prop_confidence(p):
                s = p.get("stat_type", "").capitalize()
                a = get_season_avg(p, s)
                d = round((float(p.get("line", 0)) - a) / a * 100, 1) if a > 0 else 0
                si = get_player_status(p.get("player_name", ""), injury_status_map)
                return compute_confidence_score(d, si.get("status", "Active"))
            scanned_props = [p for p in scanned_props if _prop_confidence(p) >= filter_confidence]
        if filter_value_signal:
            def _prop_value_signal(p):
                s = p.get("stat_type", "").capitalize()
                a = get_season_avg(p, s)
                d = round((float(p.get("line", 0)) - a) / a * 100, 1) if a > 0 else 0
                return get_value_line_label(a, d)
            scanned_props = [p for p in scanned_props if _prop_value_signal(p) in filter_value_signal]

        # Default sort by edge/value (absolute line_vs_avg_pct, descending)
        scanned_props.sort(key=lambda p: abs(float(p.get("line_vs_avg_pct", 0) or 0)), reverse=True)

        st.caption(f"**Smart Scan result: {len(scanned_props)} props** match your filters (out of {len(display_enriched_table)} displayed).")

        if scanned_props:
            # ── Paginated Smart Scan dataframe ────────────────────
            ITEMS_PER_PAGE = SMART_SCAN_PAGE_SIZE
            total_pages = max(1, (len(scanned_props) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            scan_page = st.number_input(
                "Page",
                min_value=1,
                max_value=total_pages,
                value=1,
                key="scan_page",
            ) if total_pages > 1 else 1
            page_start = (scan_page - 1) * ITEMS_PER_PAGE
            page_end = page_start + ITEMS_PER_PAGE
            scanned_page = scanned_props[page_start:page_end]

            scan_rows = []
            for sp in scanned_page:
                sp_name = sp.get("player_name", "")
                sp_stat = sp.get("stat_type", "").capitalize()
                sp_line = float(sp.get("line", 0))
                sp_avg = get_season_avg(sp, sp_stat)
                sp_diff = round((sp_line - sp_avg) / sp_avg * 100, 1) if sp_avg > 0 else 0
                sp_vs = f"{sp_diff:+.1f}%" if sp_avg > 0 else "—"

                sp_status_info = get_player_status(sp_name, injury_status_map)
                sp_player_status = sp_status_info.get("status", "Active")

                sp_conf = compute_confidence_score(sp_diff, sp_player_status)

                sp_value = get_value_line_label(sp_avg, sp_diff)
                sp_context = get_context_line_label(sp_avg, sp_diff)

                _ot = sp.get("odds_type", "standard")
                scan_rows.append({
                    "Player": sp_name,
                    "Stat": sp_stat,
                    "Line": sp_line,
                    "Line Type": {
                        "goblin": "🟢 Goblin",
                        "demon":  "🔴 Demon",
                    }.get(_ot, "⚪ Standard"),
                    "Bettable": "OVER only" if _ot in ("goblin", "demon") else "OVER / UNDER",
                    "Season Avg": round(sp_avg, 1) if sp_avg else "—",
                    "Line vs Avg": sp_vs,
                    "Value Line": sp_value,
                    "Context Line": sp_context,
                    "Confidence": sp_conf,
                    "Platform": sp.get("platform", ""),
                })
            st.dataframe(
                scan_rows,
                width="stretch",
                hide_index=True,
                column_config={
                    "Line": st.column_config.NumberColumn(format="%.1f"),
                    "Season Avg": st.column_config.NumberColumn(format="%.1f"),
                    "Line vs Avg": st.column_config.TextColumn(),
                    "Value Line": st.column_config.TextColumn(),
                    "Context Line": st.column_config.TextColumn(),
                    "Confidence": st.column_config.ProgressColumn(
                        min_value=0, max_value=100, format="%d",
                    ),
                },
            )
            if total_pages > 1:
                st.caption(f"Page {scan_page} of {total_pages} ({len(scanned_props)} total results)")

            # ── Export filtered CSV ───────────────────────────────
            if scanned_props:
                export_buf = io.StringIO()
                writer = csv.DictWriter(export_buf, fieldnames=["player_name", "stat_type", "line", "platform", "team", "game_date"])
                writer.writeheader()
                for sp in scanned_props:
                    writer.writerow({
                        "player_name": sp.get("player_name", ""),
                        "stat_type": sp.get("stat_type", ""),
                        "line": sp.get("line", ""),
                        "platform": sp.get("platform", ""),
                        "team": sp.get("player_team", sp.get("team", "")),
                        "game_date": sp.get("game_date", ""),
                    })
                st.download_button(
                    "📋 Export Filtered Props as CSV",
                    data=export_buf.getvalue(),
                    file_name="filtered_props.csv",
                    mime="text/csv",
                    key="export_filtered_csv",
                )

            # ── Bulk edit ─────────────────────────────────────────
            with st.expander("✏️ Bulk Edit Lines", expanded=False):
                st.markdown("Adjust prop lines for the Smart Scan results in bulk:")
                bulk_adjustments = {}
                for idx, bp in enumerate(scanned_page[:10]):
                    bp_name = bp.get("player_name", "")
                    bp_stat = bp.get("stat_type", "")
                    bp_line = float(bp.get("line", 0))
                    bcol_name, bcol_input, bcol_flag = st.columns([3, 2, 1])
                    with bcol_name:
                        st.markdown(f"**{bp_name}** — {bp_stat.title()}")
                    with bcol_input:
                        new_line = st.number_input(
                            "Line",
                            min_value=0.0, max_value=100.0,
                            value=bp_line, step=0.5,
                            key=f"bulk_line_{idx}",
                            label_visibility="collapsed",
                        )
                    with bcol_flag:
                        if new_line != bp_line:
                            bulk_adjustments[(bp_name, bp_stat)] = new_line

                if bulk_adjustments and st.button("💾 Apply Bulk Edits", type="primary", key="bulk_apply"):
                    updated = []
                    for raw_prop in current_props:
                        prop_key = (raw_prop.get("player_name", ""), raw_prop.get("stat_type", ""))
                        if prop_key in bulk_adjustments:
                            raw_prop = dict(raw_prop)
                            raw_prop["line"] = bulk_adjustments[prop_key]
                        updated.append(raw_prop)
                    save_props_to_session(updated, st.session_state)
                    st.success(f"✅ Updated {len(bulk_adjustments)} prop line(s)!")
                    st.rerun()

    # ── Main Props Table (card grid + data table) ─────────────
    if display_enriched_table:
        st.divider()

        # Toggle: card grid vs data table view
        view_mode = st.radio(
            "View mode",
            ["📊 Card Grid", "📋 Data Table"],
            horizontal=True,
            key="table_view_mode",
        )

        if view_mode == "📊 Card Grid":
            # Build card grid HTML
            card_htmls = []
            for prop in display_enriched_table:
                p_name = prop.get("player_name", "")
                team = prop.get("player_team", prop.get("team", ""))
                stat = prop.get("stat_type", "").capitalize()
                line = float(prop.get("line", 0))
                platform = prop.get("platform", "")
                line_diff = float(prop.get("line_vs_avg_pct", 0) or 0)
                season_avg = get_season_avg(prop, stat)
                odds_type = prop.get("odds_type", "standard")

                status_info = get_player_status(p_name, injury_status_map)
                p_status = status_info.get("status", "Active")
                s_emoji = STATUS_EMOJI_MAP.get(p_status, "⚪")

                player_id = prop.get("player_id", 0)
                confidence = compute_confidence_score(line_diff, p_status)

                # Line movement
                mv_key = (p_name, prop.get("stat_type", ""), platform)
                mv_html = ""
                if mv_key in line_movements:
                    old_l, new_l = line_movements[mv_key]
                    mv_html = get_line_movement_html(old_l, new_l)

                card_htmls.append(get_prop_card_html(
                    player_name=p_name,
                    team=team,
                    stat_type=stat,
                    line=line,
                    season_avg=season_avg,
                    line_diff_pct=line_diff,
                    odds_type=odds_type,
                    platform=platform,
                    status_emoji=s_emoji,
                    player_status=p_status,
                    confidence_score=confidence,
                    player_id=player_id,
                    movement_html=mv_html,
                ))

            grid_html = '<div class="ps-grid">' + "\n".join(card_htmls) + "</div>"
            st.markdown(grid_html, unsafe_allow_html=True)
        else:
            # Data table view
            display_rows = []
            for i, prop in enumerate(display_enriched_table):
                p_name = prop.get("player_name", "")
                team = prop.get("player_team", prop.get("team", ""))
                stat = prop.get("stat_type", "").capitalize()
                line = prop.get("line", 0)
                platform = prop.get("platform", "")
                line_diff = float(prop.get("line_vs_avg_pct", 0) or 0)
                season_avg = get_season_avg(prop, stat)

                status_info = get_player_status(p_name, injury_status_map)
                p_status = status_info.get("status", "Active")
                s_emoji = STATUS_EMOJI_MAP.get(p_status, "⚪")

                confidence = compute_confidence_score(line_diff, p_status)

                value_signal = get_value_line_label(season_avg, line_diff)
                context_line = get_context_line_label(season_avg, line_diff)

                display_rows.append({
                    "#": i + 1,
                    "Player": p_name,
                    "Status": f"{s_emoji} {p_status}",
                    "Team": team,
                    "Stat": stat,
                    "Line": line,
                    "Line Type": {
                        "goblin": "🟢 Goblin",
                        "demon":  "🔴 Demon",
                    }.get(prop.get("odds_type", "standard"), "⚪ Standard"),
                    "Season Avg": round(season_avg, 1) if season_avg else "—",
                    "Value Line": value_signal,
                    "Context Line": context_line,
                    "Confidence": confidence,
                    "Platform": platform,
                    "Date": prop.get("game_date", ""),
                })

            st.dataframe(
                display_rows,
                width="stretch",
                hide_index=True,
                column_config={
                    "Line": st.column_config.NumberColumn(format="%.1f"),
                    "Season Avg": st.column_config.NumberColumn(format="%.1f"),
                    "Value Line": st.column_config.TextColumn(),
                    "Context Line": st.column_config.TextColumn(),
                    "Confidence": st.column_config.ProgressColumn(
                        min_value=0, max_value=100, format="%d",
                    ),
                },
            )

        # ── GTD / Questionable warnings ───────────────────────────
        availability_warnings = []
        for p, p_status, note in gtd_props:
            p_name = p.get("player_name", "")
            availability_warnings.append(
                f"⚠️ **{p_name}** is **{p_status}**" + (f" — {note}" if note else "")
            )
        if show_injured_table:
            for p, p_status, note in unavailable_props:
                p_name = p.get("player_name", "")
                availability_warnings.append(
                    f"⛔ **{p_name}** is **{p_status}**" + (f" — {note}" if note else "")
                )

        if availability_warnings:
            with st.expander(
                f"🏥 Availability Alerts ({len(availability_warnings)} player(s))",
                expanded=True,
            ):
                for warning in availability_warnings:
                    if warning.startswith("⛔"):
                        st.error(warning)
                    else:
                        st.warning(warning)

        # ── Action buttons ────────────────────────────────────────
        action_col1, action_col2, _ = st.columns([1, 1, 3])
        with action_col1:
            if st.button("🗑️ Clear All Props"):
                st.session_state["current_props"] = []
                st.session_state["analysis_results"] = []
                st.rerun()
        with action_col2:
            if st.button("📦 Load Props from CSV"):
                saved_props = load_props_data()
                if saved_props:
                    save_props_to_session(saved_props, st.session_state)
                    st.success(f"Loaded {len(saved_props)} props from props.csv!")
                else:
                    st.info("No props found. Go to **📡 Smart NBA Data** to load live data first.")
                st.rerun()

        # ── Roster validation table ───────────────────────────────
        if players_data:
            from styles.theme import get_roster_health_html
            validation = validate_props_against_roster(current_props, players_data)
            total_validated = validation["total"]
            matched_count = validation["matched_count"]

            out_in_validation = [
                item for item in validation["matched"] + validation["fuzzy_matched"]
                if item.get("out_warning")
            ]
            if out_in_validation:
                for item in out_in_validation:
                    st.error(item["out_warning"])

            if total_validated > 0:
                with st.expander(
                    f"🧬 Roster Health: {matched_count}/{total_validated} props matched "
                    f"({int(matched_count / max(total_validated, 1) * 100)}%) — click to see details",
                    expanded=(len(validation["unmatched"]) > 0),
                ):
                    st.markdown(
                        get_roster_health_html(
                            validation["matched"],
                            validation["fuzzy_matched"],
                            validation["unmatched"],
                        ),
                        unsafe_allow_html=True,
                    )

    else:
        if current_props:
            st.info(
                f"No props to display. "
                f"{'All ' + str(len(current_props)) + ' prop(s) are hidden (players are Out/Doubtful). ' if unavailable_props and not show_injured_table else ''}"
                "Use the toggle above to show injured players."
            )
        else:
            st.info("No props loaded. Switch to the **🔄 Load Props** tab or **✏️ Manual Entry** to add props.")


# ════════════════════════════════════════════════════════════════
# TAB 4: Manual Entry
# ════════════════════════════════════════════════════════════════

with tab_manual:
    st.subheader("✏️ Add Props Manually")
    st.markdown("Enter one prop at a time. Click **Add Prop** to save each one.")

    with st.form("manual_prop_entry", clear_on_submit=True):
        form_col1, form_col2, form_col3, form_col4 = st.columns([3, 1, 1, 2])

        with form_col1:
            selected_player = st.selectbox(
                "Player Name *",
                options=["— Type or select —"] + all_player_names,
            )
            custom_player_name = st.text_input(
                "Or type player name:",
                placeholder="e.g., LeBron James",
            )

        with form_col2:
            stat_type_selection = st.selectbox("Stat Type *", options=valid_stat_types)

        with form_col3:
            prop_line_value = st.number_input(
                "Line *",
                min_value=0.0, max_value=100.0,
                value=24.5, step=0.5,
            )

        with form_col4:
            platform_selection = st.selectbox("Platform *", options=valid_platforms)

        form_col5, form_col6, _ = st.columns([2, 2, 3])
        with form_col5:
            team_input = st.text_input("Team (optional)", placeholder="e.g., LAL")
        with form_col6:
            game_date_input = st.date_input("Game Date", value=datetime.date.today())

        add_prop_button = st.form_submit_button(
            "➕ Add Prop",
            width="stretch",
            type="primary",
        )

    if add_prop_button:
        if custom_player_name.strip():
            final_player_name = custom_player_name.strip()
        elif selected_player != "— Type or select —":
            final_player_name = selected_player
        else:
            final_player_name = ""

        if not final_player_name:
            st.error("Please enter or select a player name.")
        elif prop_line_value <= 0:
            st.error("Prop line must be greater than 0.")
        else:
            auto_team = team_input.strip().upper() if team_input else ""
            if not auto_team:
                player_lookup = find_player_by_name(players_data, final_player_name)
                if player_lookup:
                    auto_team = player_lookup.get("team", "")

            new_prop = {
                "player_name": final_player_name,
                "team": auto_team,
                "stat_type": stat_type_selection,
                "line": prop_line_value,
                "platform": platform_selection,
                "game_date": game_date_input.isoformat(),
            }

            current_props_for_update = load_props_from_session(st.session_state)

            if not user_is_premium and len(current_props_for_update) >= FREE_PROP_LIMIT:
                st.warning(
                    f"⚠️ Free plan is limited to **{FREE_PROP_LIMIT} props**. "
                    f"Remove a prop first, or [**upgrade to Premium**]({_PREM_PATH}) "
                    "for unlimited props."
                )
            else:
                current_props_for_update.append(new_prop)
                save_props_to_session(current_props_for_update, st.session_state)
                st.success(f"✅ Added: {final_player_name} ({auto_team}) | {stat_type_selection} | {prop_line_value} | {platform_selection}")
                st.rerun()

