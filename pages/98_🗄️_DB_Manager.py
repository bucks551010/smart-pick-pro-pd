# ============================================================
# FILE: pages/98_🗄️_DB_Manager.py
# PURPOSE: Elite admin database control center.
#          Every write routes through _db_write so changes
#          hit PostgreSQL (Railway prod) and SQLite (local dev)
#          automatically — one action, both databases, instant.
#          Every write also bumps _bump_data_version() so ALL
#          running Streamlit pages detect the change within 60s
#          and reload their caches automatically.
# ACCESS:  Admin-only (is_admin_user gate).
# ============================================================

import datetime
import json
import time as _time

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="DB Control Center · Smart Pick Pro",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from utils.page_bootstrap import inject_theme_css, init_session_state
inject_theme_css()

from utils.auth_gate import require_login, is_admin_user
if not require_login():
    st.stop()
init_session_state()
if not is_admin_user():
    st.error("🔒 Access denied. Administrators only.")
    st.stop()

from tracking.database import (
    _db_read,
    _db_write,
    _DATABASE_URL,
    _nba_today_iso,
    _bump_data_version,
    get_data_version,
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Page background ─────────────────────────── */
[data-testid="stAppViewContainer"]>.main {
    background: radial-gradient(ellipse at 20% 0%,rgba(45,158,255,.08) 0%,transparent 55%),
                radial-gradient(ellipse at 80% 100%,rgba(176,110,255,.07) 0%,transparent 55%),
                #0a0d14 !important;
}
[data-testid="stSidebar"]{ background:#070a10 !important; border-right:1px solid rgba(45,158,255,.12) !important; }
.block-container{ padding-top:0 !important; max-width:1440px !important; }

/* ── Hero ────────────────────────────────────── */
.dbc-hero{
    background:linear-gradient(135deg,#0f1928 0%,#0a0d14 40%,#0d1020 100%);
    border:1px solid rgba(45,158,255,.18); border-radius:16px;
    padding:26px 36px 18px; margin-bottom:22px; position:relative; overflow:hidden;
}
.dbc-hero::before{
    content:""; position:absolute; top:0; left:0; right:0; height:2px;
    background:linear-gradient(90deg,#2D9EFF 0%,#B06EFF 50%,#00D559 100%);
}
.dbc-hero-title{ font-size:1.9rem; font-weight:800; color:#f0f4ff; margin:0 0 4px; }
.dbc-hero-sub{ font-size:.82rem; color:#7a8499; margin:0 0 14px; }

/* ── Badges ──────────────────────────────────── */
.dbc-badge{
    display:inline-flex; align-items:center; gap:5px;
    padding:3px 11px; border-radius:20px;
    font-size:.72rem; font-weight:600; letter-spacing:.5px; text-transform:uppercase;
}
.dbc-badge-blue  { background:rgba(45,158,255,.12); color:#2D9EFF; border:1px solid rgba(45,158,255,.25); }
.dbc-badge-gold  { background:rgba(249,198,43,.12);  color:#F9C62B; border:1px solid rgba(249,198,43,.25); }
.dbc-badge-green { background:rgba(0,213,89,.10);    color:#00D559; border:1px solid rgba(0,213,89,.22); }
.dbc-badge-red   { background:rgba(242,67,54,.10);   color:#F24336; border:1px solid rgba(242,67,54,.22); }
.dbc-badge-violet{ background:rgba(176,110,255,.12); color:#B06EFF; border:1px solid rgba(176,110,255,.25); }
.dbc-dot { width:6px;height:6px;border-radius:50%;background:currentColor;
           animation:dbc-pulse 2s ease-in-out infinite; display:inline-block; }
@keyframes dbc-pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.7)}}

/* ── Cards ───────────────────────────────────── */
.qa-card{
    background:rgba(15,20,40,.8); border:1px solid rgba(45,158,255,.1);
    border-radius:12px; padding:16px 18px; margin-bottom:12px;
}
.qa-card:hover{ border-color:rgba(45,158,255,.22); }
.qa-card-title{ font-size:.82rem; font-weight:700; color:#7a8499;
    text-transform:uppercase; letter-spacing:.6px; margin-bottom:10px; }

/* ── Section headers ─────────────────────────── */
.sec-hdr{
    font-size:.95rem; font-weight:700; color:#f0f4ff;
    padding-bottom:8px; margin-bottom:12px;
    border-bottom:1px solid rgba(45,158,255,.12);
}

/* ── Notify banner ───────────────────────────── */
.dbc-notify{
    background:rgba(0,213,89,.08); border:1px solid rgba(0,213,89,.25);
    border-left:3px solid #00D559; border-radius:8px;
    padding:10px 14px; margin-bottom:10px; font-size:.82rem; color:#00D559;
}

/* ── Metrics ─────────────────────────────────── */
[data-testid="stMetric"]{
    background:linear-gradient(135deg,rgba(15,20,40,.9) 0%,rgba(10,13,20,.95) 100%) !important;
    border:1px solid rgba(45,158,255,.12) !important;
    border-radius:12px !important; padding:14px 18px 12px !important;
}
[data-testid="stMetric"]:hover{ border-color:rgba(45,158,255,.28) !important; }
[data-testid="stMetricLabel"]{ font-size:.70rem !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:.7px !important; color:#7a8499 !important; }
[data-testid="stMetricValue"]{ font-size:1.5rem !important; font-weight:800 !important; color:#f0f4ff !important; }

/* ── Buttons ─────────────────────────────────── */
[data-testid="stButton"]>button{ border-radius:8px !important; font-weight:600 !important;
    transition:all .2s !important; }
[data-testid="stButton"]>button:hover{ transform:translateY(-1px) !important; }

/* ── Tables ──────────────────────────────────── */
[data-testid="stDataFrame"],
[data-testid="stDataEditor"]{ border-radius:10px !important; overflow:hidden !important; }

/* ── Tabs ────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"]{ font-weight:600 !important; font-size:.82rem !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{ color:#2D9EFF !important; }

/* ── Expanders ───────────────────────────────── */
[data-testid="stExpander"]{ background:rgba(15,20,40,.6) !important;
    border:1px solid rgba(45,158,255,.1) !important; border-radius:10px !important; }

/* ── Scrollbar ───────────────────────────────── */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:#0a0d14}
::-webkit-scrollbar-thumb{background:rgba(45,158,255,.3);border-radius:6px}
::-webkit-scrollbar-thumb:hover{background:#2D9EFF}

/* ── Download buttons ─────────────────────────── */
[data-testid="stDownloadButton"]>button{
    background:rgba(0,213,89,.08) !important; border:1px solid rgba(0,213,89,.25) !important;
    color:#00D559 !important; font-weight:600 !important; border-radius:8px !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_BACKEND = "PostgreSQL · Railway" if _DATABASE_URL else "SQLite · local"
_TODAY   = _nba_today_iso()


def _count(table: str) -> int:
    try:
        r = _db_read(f"SELECT COUNT(*) AS n FROM {table}")
        return r[0]["n"] if r else 0
    except Exception:
        return -1


def _load_today_picks() -> int:
    """Trigger the scheduler's full analysis pipeline for today and return picks inserted."""
    try:
        # Wipe today's pending picks first so stale players don't survive the reload
        from tracking.database import purge_todays_pending_picks as _ptp
        _ptp(_TODAY)
    except Exception:
        pass
    try:
        from etl.scheduler import _run_auto_analysis
        return _run_auto_analysis(_TODAY, force=True)
    except Exception as _ltp_err:
        st.error(f"Analysis pipeline error: {_ltp_err}")
        return -1


def _run_write(sql: str, params=(), caller: str = "dbm", bump: bool = True) -> bool:
    """Execute a write, clear Streamlit cache, bump data_version, show toast."""
    try:
        _db_write(sql, params, caller=caller)
        st.cache_data.clear()
        if bump:
            _bump_data_version(_TODAY)
            st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")
        return True
    except Exception as exc:
        st.error(f"Write error: {exc}")
        return False


def _confirm_button(label: str, key: str, danger: bool = False) -> bool:
    """Two-click confirm. Returns True only on the confirmed click."""
    armed = f"_armed_{key}"
    if not st.session_state.get(armed):
        if st.button(label, key=key, type="primary" if danger else "secondary"):
            st.session_state[armed] = True
            st.rerun()
        return False
    st.warning("⚠️ Are you sure? This cannot be undone.")
    c1, c2 = st.columns(2)
    if c1.button("✅ Yes, do it", key=f"{key}_yes", type="primary"):
        st.session_state.pop(armed, None)
        return True
    if c2.button("❌ Cancel", key=f"{key}_no"):
        st.session_state.pop(armed, None)
        st.rerun()
    return False


def _apply_editor_changes(
    original_rows: list,
    edited_df: pd.DataFrame,
    table: str,
    pk_col: str,
    editable_cols: list,
) -> int:
    """Diff original vs edited df and issue UPDATEs for changed cells. Returns change count."""
    if not original_rows:
        return 0
    orig_df = pd.DataFrame(original_rows)
    changes = 0
    for _, erow in edited_df.iterrows():
        pk_val = erow.get(pk_col)
        if pk_val is None or (isinstance(pk_val, float) and pd.isna(pk_val)):
            continue
        orig_matches = orig_df[orig_df[pk_col] == pk_val]
        if orig_matches.empty:
            continue
        orig_row = orig_matches.iloc[0]
        for col in editable_cols:
            if col not in erow.index or col not in orig_row.index:
                continue
            new_v, old_v = erow[col], orig_row[col]
            new_s = "" if (new_v is None or (isinstance(new_v, float) and pd.isna(new_v))) else str(new_v)
            old_s = "" if (old_v is None or (isinstance(old_v, float) and pd.isna(old_v))) else str(old_v)
            if new_s != old_s:
                _run_write(
                    f"UPDATE {table} SET {col} = ? WHERE {pk_col} = ?",
                    (new_s if new_s != "" else None, pk_val),
                    caller=f"dbm_editor_{table}",
                    bump=False,
                )
                changes += 1
    if changes:
        _bump_data_version(_TODAY)
        st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")
    return changes


# ─────────────────────────────────────────────────────────────────────────────
# Hero header
# ─────────────────────────────────────────────────────────────────────────────
_badge_cls  = "dbc-badge-green" if _DATABASE_URL else "dbc-badge-gold"
_last_write = st.session_state.get("_dbm_last_write", "—")

_dv = get_data_version()
_dv_age_s = int(_time.time() - _dv) if _dv else None
_dv_str = (
    "just now"        if _dv_age_s is not None and _dv_age_s < 60 else
    f"{_dv_age_s // 60}m ago" if _dv_age_s is not None else "—"
)

# Pre-compute for Python < 3.12 f-string compatibility
_bets_n        = _count('bets')
_picks_n       = _count('all_analysis_picks')
_write_badge   = 'dbc-badge-green' if _last_write != '\u2014' else 'dbc-badge-blue'
_write_label   = ('\u2705 Last write: ' + _last_write) if _last_write != '\u2014' else '\U0001f550 No writes this session'

st.markdown(f"""
<div class="dbc-hero">
  <div class="dbc-hero-title">🗄️ DB Control Center</div>
  <div class="dbc-hero-sub">
    Total control over every database table · All writes sync to all running pages automatically
  </div>
  <span class="dbc-badge {_badge_cls}"><span class="dbc-dot"></span> {_BACKEND}</span>
  &nbsp;<span class="dbc-badge dbc-badge-blue">📅 {_TODAY}</span>
  &nbsp;<span class="dbc-badge dbc-badge-gold">💰 {_bets_n:,} bets</span>
  &nbsp;<span class="dbc-badge dbc-badge-violet">⚡ {_picks_n:,} picks</span>
  &nbsp;<span class="dbc-badge {_write_badge}">
    {_write_label}
  </span>
  &nbsp;<span class="dbc-badge dbc-badge-blue">🔄 Version bumped: {_dv_str}</span>
</div>
""", unsafe_allow_html=True)

if st.session_state.get("_dbm_last_write"):
    st.markdown(
        f"<div class='dbc-notify'>✅ Last write at <strong>{_last_write}</strong> — "
        f"<code>data_version</code> bumped · All pages will reload within 60 s</div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Top-level tabs
# ─────────────────────────────────────────────────────────────────────────────
_TAB_QA, _TAB_BETS, _TAB_PICKS, _TAB_USERS, _TAB_CACHE, _TAB_TABLES, _TAB_SQL = st.tabs([
    "⚡ Quick Actions",
    "💰 Bets Editor",
    "🎯 Picks Editor",
    "👥 Users",
    "📡 Slate & Cache",
    "🗄️ All Tables",
    "🔧 Raw SQL",
])

# =============================================================================
# TAB 1 — QUICK ACTIONS
# =============================================================================
with _TAB_QA:
    st.markdown("<div class='sec-hdr'>⚡ One-Click Power Controls</div>", unsafe_allow_html=True)
    st.caption("Every action executes immediately and bumps `data_version` — all running pages refresh within 60 s.")

    def _pending_bets_n():
        r = _db_read("SELECT COUNT(*) AS n FROM bets WHERE result IS NULL OR result = ''")
        return r[0]["n"] if r else 0

    def _today_bets_n():
        r = _db_read("SELECT COUNT(*) AS n FROM bets WHERE bet_date = ?", (_TODAY,))
        return r[0]["n"] if r else 0

    def _today_auto_n():
        r = _db_read("SELECT COUNT(*) AS n FROM bets WHERE bet_date = ? AND auto_logged = 1", (_TODAY,))
        return r[0]["n"] if r else 0

    _lc = st.columns(6)
    _lc[0].metric("💰 Total Bets",         f"{_count('bets'):,}")
    _lc[1].metric("📅 Today\'s Bets",       f"{_today_bets_n():,}")
    _lc[2].metric("🤖 Today Auto-Logged",   f"{_today_auto_n():,}")
    _lc[3].metric("⏳ Pending (all time)",  f"{_pending_bets_n():,}")
    _lc[4].metric("🧠 Sessions",            f"{_count('analysis_sessions'):,}")
    _lc[5].metric("🏀 Game Log Rows",       f"{_count('player_game_logs'):,}")

    st.markdown("---")

    # ── Bets ──────────────────────────────────────────────────────────────
    st.markdown("<div class='qa-card'><div class='qa-card-title'>💰 Bet Management</div>", unsafe_allow_html=True)
    _qa = st.columns(4)

    with _qa[0]:
        st.caption("Delete today\'s pending auto-logged bets — forces a fresh sync on next load")
        if _confirm_button("🗑️ Clear Today\'s Auto-Logs", "qa_clear_today_auto", danger=True):
            _n = _db_read(
                "SELECT COUNT(*) AS n FROM bets "
                "WHERE bet_date = ? AND auto_logged = 1 AND (result IS NULL OR result = '')",
                (_TODAY,),
            )
            _cnt = _n[0]["n"] if _n else 0
            if _run_write(
                "DELETE FROM bets WHERE bet_date = ? AND auto_logged = 1 AND (result IS NULL OR result = '')",
                (_TODAY,), "qa_clear_today_auto",
            ):
                st.toast(f"🗑️ Deleted {_cnt} auto-logged bets — pages refreshing…", icon="✅")

    with _qa[1]:
        st.caption("Set every unresolved bet result back to NULL (pending)")
        if _confirm_button("🔄 Reset All Results → Pending", "qa_reset_results"):
            if _run_write(
                "UPDATE bets SET result = NULL WHERE result IS NOT NULL AND result != ''",
                caller="qa_reset_results",
            ):
                st.toast("🔄 All bet results reset to pending", icon="✅")

    with _qa[2]:
        st.caption("Permanently delete every bet with no result")
        if _confirm_button("🗑️ Delete All Pending Bets", "qa_del_all_pending", danger=True):
            _n = _db_read("SELECT COUNT(*) AS n FROM bets WHERE result IS NULL OR result = ''")
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM bets WHERE result IS NULL OR result = ''", caller="qa_del_pending"):
                st.toast(f"🗑️ Deleted {_cnt} pending bets", icon="✅")

    with _qa[3]:
        st.caption("Wipe every row in the bets table")
        if _confirm_button("⛔ NUKE All Bets", "qa_nuke_bets", danger=True):
            if _run_write("DELETE FROM bets", caller="qa_nuke_bets"):
                st.toast("⛔ All bets deleted", icon="✅")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Picks ─────────────────────────────────────────────────────────────
    st.markdown("<div class='qa-card'><div class='qa-card-title'>⚡ Analysis Picks</div>", unsafe_allow_html=True)
    _qb = st.columns(4)

    with _qb[0]:
        st.caption("Delete today\'s picks — forces a fresh QAM run on next visit")
        if _confirm_button("🗑️ Clear Today\'s Picks", "qa_del_today_picks", danger=True):
            _n = _db_read("SELECT COUNT(*) AS n FROM all_analysis_picks WHERE pick_date = ?", (_TODAY,))
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM all_analysis_picks WHERE pick_date = ?",
                          (_TODAY,), "qa_del_today_picks"):
                st.toast(f"🗑️ Deleted {_cnt} picks for today — pages refreshing…", icon="✅")

    with _qb[1]:
        _cutoff_30 = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        st.caption(f"Delete picks older than 30 days (before {_cutoff_30})")
        if _confirm_button("🧹 Purge Picks > 30 days", "qa_purge_picks"):
            _n = _db_read("SELECT COUNT(*) AS n FROM all_analysis_picks WHERE pick_date < ?", (_cutoff_30,))
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM all_analysis_picks WHERE pick_date < ?",
                          (_cutoff_30,), "qa_purge_picks"):
                st.toast(f"🧹 Purged {_cnt} old picks", icon="✅")

    with _qb[2]:
        st.caption("Delete all unresolved analysis picks")
        if _confirm_button("🗑️ Delete Pending Picks", "qa_del_pending_picks"):
            _n = _db_read("SELECT COUNT(*) AS n FROM all_analysis_picks WHERE result IS NULL OR result = ''")
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM all_analysis_picks WHERE result IS NULL OR result = ''",
                          caller="qa_del_pending_picks"):
                st.toast(f"🗑️ Deleted {_cnt} pending picks", icon="✅")

    with _qb[3]:
        st.caption("Wipe every analysis pick across all dates")
        if _confirm_button("⛔ NUKE All Picks", "qa_nuke_picks", danger=True):
            if _run_write("DELETE FROM all_analysis_picks", caller="qa_nuke_picks"):
                st.toast("⛔ All analysis picks deleted", icon="✅")

    # ── Load Today's Picks (full row) ──────────────────────────────────────
    _qlb = st.columns([3, 1])
    with _qlb[0]:
        st.caption(
            "Fetch live props → run full Quantum analysis → store results for today. "
            "Use this after clearing picks or any time you want a fresh run outside the scheduler window."
        )
    with _qlb[1]:
        if st.button("🔄 Load Today's Picks", key="qa_load_today_picks", type="primary", use_container_width=True):
            with st.spinner("Running full analysis pipeline — fetching props, simulating, storing picks…"):
                _ltp_n = _load_today_picks()
            if _ltp_n > 0:
                st.cache_data.clear()
                st.toast(f"✅ {_ltp_n} picks loaded for {_TODAY} — open QAM to view", icon="✅")
                st.rerun()
            elif _ltp_n == 0:
                st.warning("Analysis ran but returned 0 picks — no props available or outside game window.")
            # -1 means error already shown by _load_today_picks()

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Surgical Pick Delete ───────────────────────────────────────────────
    st.markdown(
        "<div class='qa-card'><div class='qa-card-title'>🔬 Surgical Pick Delete</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Filter by any combination of team, player, stat type, platform, or date range — "
        "then preview and delete exactly what you want."
    )

    # Load distinct values for filter dropdowns
    try:
        _sd_teams_raw = _db_read(
            "SELECT DISTINCT team FROM all_analysis_picks WHERE team IS NOT NULL AND team != '' "
            "ORDER BY team"
        )
        _sd_teams = ["(all)"] + [r["team"] for r in _sd_teams_raw if r.get("team")]
    except Exception:
        _sd_teams = ["(all)"]
    try:
        _sd_stats_raw = _db_read(
            "SELECT DISTINCT stat_type FROM all_analysis_picks WHERE stat_type IS NOT NULL AND stat_type != '' "
            "ORDER BY stat_type"
        )
        _sd_stats = ["(all)"] + [r["stat_type"] for r in _sd_stats_raw if r.get("stat_type")]
    except Exception:
        _sd_stats = ["(all)"]
    try:
        _sd_plats_raw = _db_read(
            "SELECT DISTINCT platform FROM all_analysis_picks WHERE platform IS NOT NULL AND platform != '' "
            "ORDER BY platform"
        )
        _sd_plats = ["(all)"] + [r["platform"] for r in _sd_plats_raw if r.get("platform")]
    except Exception:
        _sd_plats = ["(all)"]
    try:
        _sd_dates_raw = _db_read(
            "SELECT DISTINCT pick_date FROM all_analysis_picks WHERE pick_date IS NOT NULL "
            "ORDER BY pick_date DESC LIMIT 30"
        )
        _sd_dates = ["(all)"] + [r["pick_date"] for r in _sd_dates_raw if r.get("pick_date")]
    except Exception:
        _sd_dates = ["(all)"]

    _sdf1, _sdf2, _sdf3, _sdf4, _sdf5 = st.columns(5)
    with _sdf1:
        _sd_team = st.selectbox("🏀 Team", _sd_teams, key="sd_team")
    with _sdf2:
        _sd_player = st.text_input("👤 Player name (partial OK)", key="sd_player").strip()
    with _sdf3:
        _sd_stat = st.selectbox("📊 Stat type", _sd_stats, key="sd_stat")
    with _sdf4:
        _sd_plat = st.selectbox("📱 Platform", _sd_plats, key="sd_plat")
    with _sdf5:
        _sd_date = st.selectbox("📅 Pick date", _sd_dates, key="sd_date")

    # Build WHERE clause from non-default selections
    _sd_where_parts: list[str] = []
    _sd_params: list = []
    if _sd_team and _sd_team != "(all)":
        _sd_where_parts.append("LOWER(team) = LOWER(?)")
        _sd_params.append(_sd_team)
    if _sd_player:
        _sd_where_parts.append("LOWER(player_name) LIKE ?")
        _sd_params.append(f"%{_sd_player.lower()}%")
    if _sd_stat and _sd_stat != "(all)":
        _sd_where_parts.append("LOWER(stat_type) = LOWER(?)")
        _sd_params.append(_sd_stat)
    if _sd_plat and _sd_plat != "(all)":
        _sd_where_parts.append("LOWER(platform) = LOWER(?)")
        _sd_params.append(_sd_plat)
    if _sd_date and _sd_date != "(all)":
        _sd_where_parts.append("pick_date = ?")
        _sd_params.append(_sd_date)

    _sd_where_sql = ("WHERE " + " AND ".join(_sd_where_parts)) if _sd_where_parts else ""

    # Preview matching rows
    _sd_preview_rows: list = []
    if _sd_where_sql:
        try:
            _sd_preview_rows = _db_read(
                f"SELECT pick_id, pick_date, player_name, team, stat_type, prop_line, "
                f"direction, platform, tier, confidence_score "
                f"FROM all_analysis_picks {_sd_where_sql} "
                f"ORDER BY pick_date DESC, confidence_score DESC LIMIT 200",
                tuple(_sd_params),
            )
        except Exception as _sd_err:
            st.error(f"Preview query failed: {_sd_err}")

    _sd_cols = st.columns([2, 1])
    with _sd_cols[0]:
        if not _sd_where_sql:
            st.info("Set at least one filter above to preview matching picks.")
        elif _sd_preview_rows:
            import pandas as _sd_pd
            _sd_df = _sd_pd.DataFrame(_sd_preview_rows)
            st.dataframe(_sd_df, use_container_width=True, height=220)
            st.caption(f"**{len(_sd_preview_rows)}** matching picks shown (capped at 200)")
        else:
            st.info("No picks match the current filters.")

    with _sd_cols[1]:
        if _sd_where_sql and _sd_preview_rows:
            _sd_count_q = _db_read(
                f"SELECT COUNT(*) AS n FROM all_analysis_picks {_sd_where_sql}",
                tuple(_sd_params),
            )
            _sd_total = _sd_count_q[0]["n"] if _sd_count_q else len(_sd_preview_rows)
            st.metric("Rows to delete", f"{_sd_total:,}")
            # Build a human-readable label
            _sd_label_parts = []
            if _sd_team and _sd_team != "(all)":
                _sd_label_parts.append(f"team={_sd_team}")
            if _sd_player:
                _sd_label_parts.append(f"player~{_sd_player}")
            if _sd_stat and _sd_stat != "(all)":
                _sd_label_parts.append(f"stat={_sd_stat}")
            if _sd_plat and _sd_plat != "(all)":
                _sd_label_parts.append(f"platform={_sd_plat}")
            if _sd_date and _sd_date != "(all)":
                _sd_label_parts.append(f"date={_sd_date}")
            _sd_label = "Delete: " + ", ".join(_sd_label_parts) if _sd_label_parts else "Delete filtered"
            if _confirm_button(f"🗑️ {_sd_label}", "sd_delete_filtered", danger=True):
                if _run_write(
                    f"DELETE FROM all_analysis_picks {_sd_where_sql}",
                    tuple(_sd_params),
                    "sd_delete_filtered",
                ):
                    st.toast(f"🗑️ Deleted {_sd_total} picks ({', '.join(_sd_label_parts)})", icon="✅")
                    st.rerun()
        elif _sd_where_sql:
            st.info("Nothing to delete.")
        else:
            st.caption("Set a filter to enable deletion.")

    # ── Reload after delete ───────────────────────────────────────────────
    st.divider()
    _sd_reload_cols = st.columns([3, 1])
    with _sd_reload_cols[0]:
        st.caption("After deleting picks, click here to immediately re-run the full analysis pipeline and reload today's picks.")
    with _sd_reload_cols[1]:
        if st.button("🔄 Load Today's Picks", key="sd_reload_picks", type="primary", use_container_width=True):
            with st.spinner("Re-running full analysis…"):
                _sd_reload_n = _load_today_picks()
            if _sd_reload_n > 0:
                st.cache_data.clear()
                st.toast(f"✅ {_sd_reload_n} picks loaded for {_TODAY}", icon="✅")
                st.rerun()
            elif _sd_reload_n == 0:
                st.warning("0 picks returned — no props available or outside game window.")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Sessions / State ──────────────────────────────────────────────────
    st.markdown("<div class='qa-card'><div class='qa-card-title'>🧠 Sessions &amp; App State</div>", unsafe_allow_html=True)
    _qc = st.columns(4)

    with _qc[0]:
        st.caption("Clear today\'s saved analysis session — QAM re-runs on next visit")
        if _confirm_button("🔄 Reset Today\'s Session", "qa_reset_session"):
            if _run_write("DELETE FROM analysis_sessions WHERE analysis_timestamp >= ?",
                          (_TODAY,), "qa_reset_session"):
                st.toast("🔄 Today\'s session cleared — QAM will re-run", icon="✅")

    with _qc[1]:
        _cutoff_7 = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        st.caption("Delete all sessions older than 7 days")
        if _confirm_button("🧹 Purge Old Sessions", "qa_purge_sessions"):
            _n = _db_read("SELECT COUNT(*) AS n FROM analysis_sessions WHERE analysis_timestamp < ?", (_cutoff_7,))
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM analysis_sessions WHERE analysis_timestamp < ?",
                          (_cutoff_7,), "qa_purge_sessions"):
                st.toast(f"🧹 Purged {_cnt} old sessions", icon="✅")

    with _qc[2]:
        st.caption("Reset the persisted page state blob (app loads fresh next visit)")
        if _confirm_button("📌 Reset Page State", "qa_reset_page_state"):
            if _run_write("DELETE FROM page_state", caller="qa_reset_page_state"):
                st.toast("📌 Page state cleared", icon="✅")

    with _qc[3]:
        st.caption("Reset all app_state key-value entries")
        if _confirm_button("🔧 Reset App State", "qa_reset_app_state"):
            if _run_write("DELETE FROM app_state", caller="qa_reset_app_state"):
                st.toast("🔧 App state cleared", icon="✅")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Manual version bump ───────────────────────────────────────────────
    st.markdown("<div class='qa-card'><div class='qa-card-title'>🔄 Force Live Refresh</div>", unsafe_allow_html=True)
    _qe = st.columns([3, 1])
    _qe[0].caption(
        "Bump `data_version` right now — all running Streamlit pages will detect the change "
        "on their next 60-second polling cycle and clear their pick/session caches."
    )
    if _qe[1].button("🔄 Bump Data Version Now", key="qa_manual_bump", type="primary"):
        _bump_data_version(_TODAY)
        st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")
        st.toast("🔄 data_version bumped — all pages will refresh within 60 s", icon="✅")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Maintenance ───────────────────────────────────────────────────────
    st.markdown("<div class='qa-card'><div class='qa-card-title'>🔧 Maintenance</div>", unsafe_allow_html=True)
    _qd = st.columns(4)

    with _qd[0]:
        _cutoff_3 = (datetime.date.today() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        st.caption("Purge cached game log rows older than 3 days")
        if _confirm_button("🏀 Purge Old Game Logs", "qa_purge_gamelogs"):
            _n = _db_read("SELECT COUNT(*) AS n FROM player_game_logs WHERE retrieved_at < ?", (_cutoff_3,))
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM player_game_logs WHERE retrieved_at < ?",
                          (_cutoff_3,), "qa_purge_gamelogs"):
                st.toast(f"🏀 Purged {_cnt} old game log rows", icon="✅")

    with _qd[1]:
        _cutoff_60 = (datetime.date.today() - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        st.caption("Delete prediction history rows older than 60 days")
        if _confirm_button("🎯 Purge Old Predictions", "qa_purge_preds"):
            _n = _db_read("SELECT COUNT(*) AS n FROM prediction_history WHERE prediction_date < ?", (_cutoff_60,))
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM prediction_history WHERE prediction_date < ?",
                          (_cutoff_60,), "qa_purge_preds"):
                st.toast(f"🎯 Purged {_cnt} old prediction rows", icon="✅")

    with _qd[2]:
        _cutoff_90 = (datetime.date.today() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
        st.caption("Delete daily snapshots older than 90 days")
        if _confirm_button("📊 Purge Old Snapshots", "qa_purge_snapshots"):
            _n = _db_read("SELECT COUNT(*) AS n FROM daily_snapshots WHERE snapshot_date < ?", (_cutoff_90,))
            _cnt = _n[0]["n"] if _n else 0
            if _run_write("DELETE FROM daily_snapshots WHERE snapshot_date < ?",
                          (_cutoff_90,), "qa_purge_snapshots"):
                st.toast(f"📊 Purged {_cnt} old snapshots", icon="✅")

    with _qd[3]:
        st.caption("Keep only the 50 most recent backtest runs")
        if _confirm_button("📈 Trim Backtest History", "qa_trim_backtests"):
            _ids = _db_read("SELECT backtest_id FROM backtest_results ORDER BY backtest_id DESC LIMIT 50")
            if _ids:
                _keep = tuple(r["backtest_id"] for r in _ids)
                _total_bt = _count("backtest_results")
                _to_del = max(0, _total_bt - 50)
                if _to_del > 0:
                    _ph = ",".join(["?"] * len(_keep))
                    if _run_write(f"DELETE FROM backtest_results WHERE backtest_id NOT IN ({_ph})",
                                  _keep, "qa_trim_backtests"):
                        st.toast(f"📈 Trimmed {_to_del} old backtest records", icon="✅")
                else:
                    st.info("Nothing to trim — fewer than 50 backtest records.")

    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# TAB 2 — BETS EDITOR
# =============================================================================
with _TAB_BETS:
    st.markdown("<div class='sec-hdr'>💰 Bets Editor</div>", unsafe_allow_html=True)
    st.caption("Edit cells directly in the grid. **Save Changes** commits and bumps data_version so all pages update instantly.")

    _bf = st.columns([2, 2, 2, 2])
    _bet_date_str = str(_bf[0].date_input("Date", value=datetime.date.today(), key="bets_date_filter"))
    _bet_res_f    = _bf[1].selectbox("Result", ["All","Pending only","Win","Loss","Push"], key="bets_res_f")
    _bet_plat_f   = _bf[2].text_input("Platform (blank=all)", key="bets_plat_f", placeholder="PrizePicks")
    _bet_auto_f   = _bf[3].selectbox("Logged by", ["All","Auto-logged only","Manual only"], key="bets_auto_f")

    _bw, _bp_list = ["bet_date = ?"], [_bet_date_str]
    if _bet_res_f == "Pending only":
        _bw.append("(result IS NULL OR result = '')")
    elif _bet_res_f in ("Win","Loss","Push"):
        _bw.append("LOWER(result) = ?"); _bp_list.append(_bet_res_f.lower())
    if _bet_plat_f.strip():
        _bw.append("LOWER(platform) LIKE ?"); _bp_list.append(f"%{_bet_plat_f.strip().lower()}%")
    if _bet_auto_f == "Auto-logged only": _bw.append("auto_logged = 1")
    elif _bet_auto_f == "Manual only":    _bw.append("auto_logged = 0")

    _bets_rows = _db_read(
        "SELECT bet_id,bet_date,player_name,team,stat_type,prop_line,direction,"
        "platform,tier,bet_type,confidence_score,edge_percentage,result,actual_value,notes,auto_logged "
        f"FROM bets WHERE {' AND '.join(_bw)} ORDER BY bet_id DESC LIMIT 300",
        tuple(_bp_list),
    )

    if not _bets_rows:
        st.info(f"No bets found for {_bet_date_str} with current filters.")
    else:
        _rc = st.columns([4, 2, 2, 2])
        _rc[0].markdown(f"**{len(_bets_rows)} row(s)** shown")
        _wins    = sum(1 for r in _bets_rows if str(r.get("result","")).lower() == "win")
        _losses  = sum(1 for r in _bets_rows if str(r.get("result","")).lower() == "loss")
        _pending = sum(1 for r in _bets_rows if not r.get("result"))
        _rc[1].metric("✅ Wins", _wins)
        _rc[2].metric("❌ Losses", _losses)
        _rc[3].metric("⏳ Pending", _pending)

        with st.expander("⚡ Bulk-set result for ALL shown rows", expanded=False):
            _bk = st.columns([2, 2, 2])
            _bulk_res = _bk[0].selectbox("Set result to:", ["win","loss","push",""], key="bets_bulk_res")
            _bulk_act = _bk[1].text_input("Actual value (optional):", key="bets_bulk_act", placeholder="28.5")
            if _bk[2].button("⚡ Apply to All Shown", key="bets_bulk_apply", type="primary"):
                _ids = tuple(r["bet_id"] for r in _bets_rows)
                _ph2 = ",".join(["?"] * len(_ids))
                _bsql = "UPDATE bets SET result = ? "
                _bparams: list = [_bulk_res if _bulk_res else None]
                if _bulk_act.strip():
                    try:
                        _bsql += ", actual_value = ? "; _bparams.append(float(_bulk_act.strip()))
                    except ValueError:
                        pass
                _bsql += f"WHERE bet_id IN ({_ph2})"
                _bparams.extend(_ids)
                if _run_write(_bsql, tuple(_bparams), "bets_bulk"):
                    st.toast(f"✅ Updated {len(_ids)} bets — pages refreshing…", icon="✅")
                    st.rerun()

        _bets_orig = _bets_rows
        _edited_bets = st.data_editor(
            pd.DataFrame(_bets_rows),
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "bet_id":           st.column_config.NumberColumn("ID",       disabled=True, width="small"),
                "bet_date":         st.column_config.TextColumn("Date",       width="small"),
                "player_name":      st.column_config.TextColumn("Player",     width="medium"),
                "team":             st.column_config.TextColumn("Team",       width="small"),
                "stat_type":        st.column_config.TextColumn("Stat",       width="small"),
                "prop_line":        st.column_config.NumberColumn("Line",     format="%.1f", width="small"),
                "direction":        st.column_config.SelectboxColumn("Dir",   options=["OVER","UNDER"], width="small"),
                "platform":         st.column_config.TextColumn("Platform",   width="medium"),
                "tier":             st.column_config.SelectboxColumn("Tier",  options=["Bronze","Silver","Gold","Platinum","Diamond",""], width="small"),
                "bet_type":         st.column_config.SelectboxColumn("Type",  options=["normal","goblin","demon",""], width="small"),
                "confidence_score": st.column_config.NumberColumn("Conf",     format="%.1f", width="small"),
                "edge_percentage":  st.column_config.NumberColumn("Edge",     format="%.1f", width="small"),
                "result":           st.column_config.SelectboxColumn("Result",options=["","win","loss","push"], width="small"),
                "actual_value":     st.column_config.NumberColumn("Actual",   format="%.1f", width="small"),
                "notes":            st.column_config.TextColumn("Notes",      width="large"),
                "auto_logged":      st.column_config.CheckboxColumn("Auto",   width="small"),
            },
            key="bets_editor",
        )

        _sc = st.columns([2, 2, 4])
        if _sc[0].button("💾 Save Changes", key="bets_save", type="primary"):
            _edited_ids = set()
            if "bet_id" in _edited_bets.columns:
                for v in _edited_bets["bet_id"].tolist():
                    if v is not None and not (isinstance(v, float) and pd.isna(v)):
                        try: _edited_ids.add(int(v))
                        except (ValueError, TypeError): pass
            _orig_ids = {r["bet_id"] for r in _bets_rows if r.get("bet_id") is not None}
            _del_n = sum(1 for _did in (_orig_ids - _edited_ids)
                        if _run_write("DELETE FROM bets WHERE bet_id = ?", (_did,), "bets_ed_del", bump=False))

            _editable_b = ["bet_date","player_name","team","stat_type","prop_line","direction",
                           "platform","tier","bet_type","confidence_score","edge_percentage",
                           "result","actual_value","notes","auto_logged"]
            _chg_n = _apply_editor_changes(_bets_orig, _edited_bets, "bets", "bet_id", _editable_b)

            _new_rows = _edited_bets[_edited_bets["bet_id"].isna()] if "bet_id" in _edited_bets.columns else pd.DataFrame()
            _ins_n = 0
            for _, _nr in _new_rows.iterrows():
                _nd = {k: v for k, v in _nr.items()
                       if k != "bet_id" and v is not None and not (isinstance(v, float) and pd.isna(v))}
                if _nd:
                    _nc, _nph = list(_nd.keys()), ",".join(["?"] * len(_nd))
                    if _run_write(f"INSERT INTO bets ({','.join(_nc)}) VALUES ({_nph})",
                                  tuple(_nd.values()), "bets_ed_ins", bump=False):
                        _ins_n += 1

            if _chg_n or _del_n or _ins_n:
                _bump_data_version(_TODAY)
                st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")

            _msgs = [m for m in [
                f"{_chg_n} field(s) updated" if _chg_n else "",
                f"{_del_n} row(s) deleted" if _del_n else "",
                f"{_ins_n} row(s) inserted" if _ins_n else "",
            ] if m]
            if _msgs:
                st.toast(f"✅ {' · '.join(_msgs)} — pages refreshing…", icon="✅")
            else:
                st.info("No changes detected.")

        _sc[1].download_button(
            "⬇️ Export CSV", pd.DataFrame(_bets_rows).to_csv(index=False).encode(),
            file_name=f"bets_{_bet_date_str}.csv", mime="text/csv", key="bets_export",
        )

# =============================================================================
# TAB 3 — PICKS EDITOR
# =============================================================================
with _TAB_PICKS:
    st.markdown("<div class='sec-hdr'>🎯 Analysis Picks Editor</div>", unsafe_allow_html=True)
    st.caption("Edit QAM analysis picks inline. Mark results, fix lines, or remove rows. All saves bump data_version.")

    # ── Load Today's Picks trigger ────────────────────────────────────────
    _pet_cols = st.columns([4, 1])
    with _pet_cols[1]:
        if st.button("🔄 Load Today's Picks", key="picks_tab_load", type="primary", use_container_width=True):
            with st.spinner("Fetching props & running full analysis…"):
                _pet_n = _load_today_picks()
            if _pet_n > 0:
                st.cache_data.clear()
                st.toast(f"✅ {_pet_n} picks loaded for {_TODAY}", icon="✅")
                st.rerun()
            elif _pet_n == 0:
                st.warning("0 picks returned — no props available or outside game window.")

    st.divider()

    _pf = st.columns([2, 2, 2])
    _pick_date_str = str(_pf[0].date_input("Date", value=datetime.date.today(), key="picks_date_f"))
    _pick_res_f    = _pf[1].selectbox("Result", ["All","Pending only","Correct","Incorrect"], key="picks_res_f")
    _pick_tier_f   = _pf[2].selectbox("Tier", ["All","Platinum","Diamond","Gold","Silver","Bronze"], key="picks_tier_f")

    _pw, _pp_list = ["pick_date = ?"], [_pick_date_str]
    if _pick_res_f == "Pending only":    _pw.append("(result IS NULL OR result = '')")
    elif _pick_res_f == "Correct":       _pw.append("LOWER(result) = 'correct'")
    elif _pick_res_f == "Incorrect":     _pw.append("LOWER(result) = 'incorrect'")
    if _pick_tier_f != "All":            _pw.append("tier = ?"); _pp_list.append(_pick_tier_f)

    _picks_rows = _db_read(
        "SELECT pick_id,pick_date,player_name,team,stat_type,prop_line,direction,"
        "platform,tier,bet_type,confidence_score,edge_percentage,result,actual_value,notes "
        f"FROM all_analysis_picks WHERE {' AND '.join(_pw)} ORDER BY pick_id DESC LIMIT 300",
        tuple(_pp_list),
    )

    if not _picks_rows:
        st.info(f"No picks found for {_pick_date_str} with current filters.")
    else:
        _prc = st.columns([4, 2, 2, 2])
        _prc[0].markdown(f"**{len(_picks_rows)} row(s)** shown")
        _p_correct = sum(1 for r in _picks_rows if str(r.get("result","")).lower() == "correct")
        _p_wrong   = sum(1 for r in _picks_rows if str(r.get("result","")).lower() == "incorrect")
        _p_pend    = sum(1 for r in _picks_rows if not r.get("result"))
        _prc[1].metric("✅ Correct", _p_correct)
        _prc[2].metric("❌ Incorrect", _p_wrong)
        _prc[3].metric("⏳ Pending", _p_pend)

        with st.expander("⚡ Bulk-set result for ALL shown rows", expanded=False):
            _pbk = st.columns([2, 2])
            _p_bulk = _pbk[0].selectbox("Set result to:", ["correct","incorrect","push",""], key="picks_bulk_res")
            if _pbk[1].button("⚡ Apply to All Shown", key="picks_bulk_apply", type="primary"):
                _pids = tuple(r["pick_id"] for r in _picks_rows)
                _pph = ",".join(["?"] * len(_pids))
                if _run_write(
                    f"UPDATE all_analysis_picks SET result = ? WHERE pick_id IN ({_pph})",
                    (_p_bulk if _p_bulk else None, *_pids), "picks_bulk",
                ):
                    st.toast(f"✅ Updated {len(_pids)} picks — pages refreshing…", icon="✅")
                    st.rerun()

        _picks_orig = _picks_rows
        _edited_picks = st.data_editor(
            pd.DataFrame(_picks_rows),
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "pick_id":          st.column_config.NumberColumn("ID",      disabled=True, width="small"),
                "pick_date":        st.column_config.TextColumn("Date",      width="small"),
                "player_name":      st.column_config.TextColumn("Player",    width="medium"),
                "team":             st.column_config.TextColumn("Team",      width="small"),
                "stat_type":        st.column_config.TextColumn("Stat",      width="small"),
                "prop_line":        st.column_config.NumberColumn("Line",    format="%.1f", width="small"),
                "direction":        st.column_config.SelectboxColumn("Dir",  options=["OVER","UNDER"], width="small"),
                "platform":         st.column_config.TextColumn("Platform",  width="medium"),
                "tier":             st.column_config.SelectboxColumn("Tier", options=["Bronze","Silver","Gold","Platinum","Diamond",""], width="small"),
                "bet_type":         st.column_config.SelectboxColumn("Type", options=["normal","goblin","demon",""], width="small"),
                "confidence_score": st.column_config.NumberColumn("Conf",    format="%.1f", width="small"),
                "edge_percentage":  st.column_config.NumberColumn("Edge",    format="%.1f", width="small"),
                "result":           st.column_config.SelectboxColumn("Result",options=["","correct","incorrect","push"], width="small"),
                "actual_value":     st.column_config.NumberColumn("Actual",  format="%.1f", width="small"),
                "notes":            st.column_config.TextColumn("Notes",     width="large"),
            },
            key="picks_editor",
        )

        if st.button("💾 Save Changes", key="picks_save", type="primary"):
            _p_edit_ids = set()
            if "pick_id" in _edited_picks.columns:
                for v in _edited_picks["pick_id"].tolist():
                    if v is not None and not (isinstance(v, float) and pd.isna(v)):
                        try: _p_edit_ids.add(int(v))
                        except (ValueError, TypeError): pass
            _p_orig_ids = {r["pick_id"] for r in _picks_rows if r.get("pick_id") is not None}
            _p_del_n = sum(1 for _pdid in (_p_orig_ids - _p_edit_ids)
                           if _run_write("DELETE FROM all_analysis_picks WHERE pick_id = ?",
                                        (_pdid,), "picks_ed_del", bump=False))

            _p_editable = ["pick_date","player_name","team","stat_type","prop_line","direction",
                           "platform","tier","bet_type","confidence_score","edge_percentage",
                           "result","actual_value","notes"]
            _p_chg_n = _apply_editor_changes(_picks_orig, _edited_picks, "all_analysis_picks",
                                             "pick_id", _p_editable)

            _p_new = _edited_picks[_edited_picks["pick_id"].isna()] if "pick_id" in _edited_picks.columns else pd.DataFrame()
            _p_ins_n = 0
            for _, _pnr in _p_new.iterrows():
                _pnd = {k: v for k, v in _pnr.items()
                        if k != "pick_id" and v is not None and not (isinstance(v, float) and pd.isna(v))}
                if _pnd:
                    _pc = list(_pnd.keys())
                    _pph2 = ",".join(["?"] * len(_pc))
                    if _run_write(f"INSERT INTO all_analysis_picks ({','.join(_pc)}) VALUES ({_pph2})",
                                  tuple(_pnd.values()), "picks_ed_ins", bump=False):
                        _p_ins_n += 1

            if _p_chg_n or _p_del_n or _p_ins_n:
                _bump_data_version(_TODAY)
                st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")

            _pmsgs = [m for m in [
                f"{_p_chg_n} field(s) updated" if _p_chg_n else "",
                f"{_p_del_n} row(s) deleted" if _p_del_n else "",
                f"{_p_ins_n} row(s) inserted" if _p_ins_n else "",
            ] if m]
            if _pmsgs:
                st.toast(f"✅ {' · '.join(_pmsgs)} — pages refreshing…", icon="✅")
            else:
                st.info("No changes detected.")

# =============================================================================
# TAB 4 — USERS
# =============================================================================
with _TAB_USERS:
    st.markdown("<div class='sec-hdr'>👥 User Management</div>", unsafe_allow_html=True)
    st.caption("Search, edit tiers, lock/unlock accounts. Changes write through to the live DB immediately.")

    try:
        _u_kpi = (_db_read(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN LOWER(COALESCE(plan_tier,'free'))!='free' THEN 1 ELSE 0 END) AS paid,
                      SUM(CASE WHEN LOWER(COALESCE(plan_tier,'free'))='free' THEN 1 ELSE 0 END) AS free,
                      SUM(CASE WHEN is_admin=1 THEN 1 ELSE 0 END) AS admins,
                      SUM(CASE WHEN lockout_until IS NOT NULL THEN 1 ELSE 0 END) AS locked
               FROM users"""
        ) or [{}])[0]

        _uc = st.columns(5)
        _uc[0].metric("👥 Total Users",  _u_kpi.get("total", 0))
        _uc[1].metric("💎 Paid",         _u_kpi.get("paid",  0))
        _uc[2].metric("🆓 Free",         _u_kpi.get("free",  0))
        _uc[3].metric("👑 Admins",       _u_kpi.get("admins",0))
        _uc[4].metric("🔒 Locked",       _u_kpi.get("locked",0))

        st.markdown("---")

        with st.expander("📋 User Roster", expanded=True):
            _usr_search = st.text_input("🔍 Search by email or name", key="usr_search", placeholder="user@example.com")
            _usr_rows = _db_read(
                "SELECT user_id, email, display_name, "
                "COALESCE(plan_tier,'free') AS tier, "
                "SUBSTR(created_at,1,10) AS joined, "
                "SUBSTR(COALESCE(last_login_at,'—'),1,10) AS last_login, "
                "COALESCE(failed_login_count,0) AS failed_logins, "
                "CASE WHEN is_admin=1 THEN 'Yes' ELSE 'No' END AS admin, "
                "CASE WHEN lockout_until IS NOT NULL THEN '🔒' ELSE '—' END AS status "
                "FROM users ORDER BY created_at DESC LIMIT 500"
            )
            if _usr_rows:
                _df_usr = pd.DataFrame(_usr_rows)
                if _usr_search:
                    _mask = _df_usr.apply(lambda row: _usr_search.lower() in row.to_string().lower(), axis=1)
                    _df_usr = _df_usr[_mask]
                st.dataframe(_df_usr, use_container_width=True, hide_index=True)
            else:
                st.info("No users found.")

        with st.expander("⚙️ Change Subscription Tier", expanded=False):
            _t1, _t2, _t3 = st.columns([3, 2, 1])
            _tier_email = _t1.text_input("User email", key="tier_email", placeholder="user@example.com")
            _new_tier   = _t2.selectbox("New tier", ["free","sharp_iq","smart_money","insider_circle","admin"], key="tier_new")
            if _t3.button("✅ Apply", key="tier_apply", type="primary"):
                if _tier_email.strip():
                    if _run_write(
                        "UPDATE users SET plan_tier=? WHERE LOWER(email)=LOWER(?)",
                        (_new_tier, _tier_email.strip()), "usr_tier_override",
                    ):
                        st.toast(f"✅ Tier → {_new_tier} for {_tier_email}", icon="✅")
                        st.rerun()
                else:
                    st.warning("Enter an email address.")

        with st.expander("👑 Grant / Revoke Admin", expanded=False):
            _a1, _a2, _a3 = st.columns([3, 2, 1])
            _admin_email  = _a1.text_input("User email", key="admin_email", placeholder="user@example.com")
            _admin_action = _a2.selectbox("Action", ["Grant admin", "Revoke admin"], key="admin_action")
            if _a3.button("✅ Apply", key="admin_apply", type="primary"):
                if _admin_email.strip():
                    _is_admin_v = 1 if _admin_action == "Grant admin" else 0
                    if _run_write(
                        "UPDATE users SET is_admin=? WHERE LOWER(email)=LOWER(?)",
                        (_is_admin_v, _admin_email.strip()), "usr_admin_toggle",
                    ):
                        st.toast(f"{'👑 Admin granted' if _is_admin_v else '🚫 Admin revoked'}: {_admin_email}", icon="✅")
                        st.rerun()

        with st.expander("🔒 Lock / Unlock Account", expanded=False):
            _l1, _l2, _l3 = st.columns([3, 2, 1])
            _lock_email  = _l1.text_input("User email", key="lock_email", placeholder="user@example.com")
            _lock_action = _l2.selectbox("Action", ["Lock (1 year)","Unlock account"], key="lock_action")
            if _l3.button("✅ Apply", key="lock_apply", type="primary"):
                if _lock_email.strip():
                    if "Lock" in _lock_action:
                        _until = (datetime.datetime.utcnow() + datetime.timedelta(days=365)).isoformat()
                        _res = _run_write(
                            "UPDATE users SET lockout_until=? WHERE LOWER(email)=LOWER(?)",
                            (_until, _lock_email.strip()), "usr_lock",
                        )
                    else:
                        _res = _run_write(
                            "UPDATE users SET lockout_until=NULL, failed_login_count=0 WHERE LOWER(email)=LOWER(?)",
                            (_lock_email.strip(),), "usr_unlock",
                        )
                    if _res:
                        st.toast(f"{'🔒 Locked' if 'Lock' in _lock_action else '🔓 Unlocked'}: {_lock_email}", icon="✅")
                        st.rerun()

        with st.expander("🔑 Reset Failed Login Count", expanded=False):
            _rf1, _rf2 = st.columns([3, 1])
            _rf_email = _rf1.text_input("User email", key="rf_email", placeholder="user@example.com")
            if _rf2.button("🔑 Reset", key="rf_apply", type="primary"):
                if _rf_email.strip():
                    if _run_write(
                        "UPDATE users SET failed_login_count=0 WHERE LOWER(email)=LOWER(?)",
                        (_rf_email.strip(),), "usr_reset_fails",
                    ):
                        st.toast(f"✅ Failed login count reset for {_rf_email}", icon="✅")
                        st.rerun()

        with st.expander("⛔ Delete User Account", expanded=False):
            _du1, _du2 = st.columns([3, 1])
            _du_email = _du1.text_input("User email (exact)", key="du_email", placeholder="user@example.com")
            if _du2.button("⛔ Delete", key="du_apply", type="primary"):
                if _du_email.strip():
                    _du_row = _db_read("SELECT user_id, email FROM users WHERE LOWER(email)=LOWER(?)", (_du_email.strip(),))
                    if _du_row:
                        st.warning(f"Will delete: **{_du_row[0]['email']}** (id={_du_row[0]['user_id']})")
                        if _confirm_button("⛔ Confirm Delete User", f"du_confirm", danger=True):
                            if _run_write(
                                "DELETE FROM users WHERE LOWER(email)=LOWER(?)",
                                (_du_email.strip(),), "usr_delete",
                            ):
                                st.toast(f"⛔ User deleted: {_du_email}", icon="✅")
                                st.rerun()
                    else:
                        st.warning("User not found.")

    except Exception as _usr_exc:
        st.warning(f"Could not load user data: {_usr_exc}")

# =============================================================================
# TAB 5 — SLATE & CACHE
# =============================================================================
with _TAB_CACHE:
    st.markdown("<div class='sec-hdr'>📡 Slate & Cache Control</div>", unsafe_allow_html=True)
    st.caption("Control the JSON pick cache and data version signals that drive the home page and all live displays.")

    import pathlib as _pl
    import json as _js

    _cache_path = _pl.Path("cache") / "slate_cache.json"

    st.markdown("#### 📄 slate_cache.json")
    if _cache_path.exists():
        try:
            _sc_data   = _js.loads(_cache_path.read_text(encoding="utf-8"))
            _sc_date   = _sc_data.get("date", "—")
            _sc_picks  = len(_sc_data.get("picks", []))
            _sc_eon    = _sc_data.get("_eon_cleared", False)
            _sc_size   = round(_cache_path.stat().st_size / 1024, 1)
            _ci = st.columns(3)
            _ci[0].metric("📅 Cache Date", _sc_date)
            _ci[1].metric("⚡ Picks in Cache", _sc_picks)
            _ci[2].metric("📦 File Size", f"{_sc_size} KB")
            if _sc_eon:
                st.info("🌙 EON-cleared marker is active — home page shows empty slate.")
            with st.expander("👁️ View Raw Cache", expanded=False):
                st.json(_sc_data if _sc_picks <= 10 else {**_sc_data, "picks": _sc_data["picks"][:5], "_truncated": True})
        except Exception as _ce:
            st.warning(f"Could not parse cache: {_ce}")
    else:
        st.info("slate_cache.json does not exist yet.")

    _cc = st.columns(3)

    with _cc[0]:
        st.caption("Write an EON-cleared marker — home page shows no picks until analysis runs")
        if st.button("🌙 Mark as EON Cleared", key="cache_eon", type="secondary"):
            try:
                _cache_path.parent.mkdir(parents=True, exist_ok=True)
                _cache_path.write_text(
                    _js.dumps({"_eon_cleared": True, "date": _TODAY,
                               "written_at": datetime.datetime.utcnow().isoformat(), "picks": []}, indent=2),
                    encoding="utf-8",
                )
                _bump_data_version(_TODAY)
                st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")
                st.toast("🌙 EON marker written — home page will show empty slate", icon="✅")
                st.rerun()
            except Exception as _ee:
                st.error(f"Failed: {_ee}")

    with _cc[1]:
        st.caption("Delete the cache file entirely — next home page load reads from DB")
        if st.button("🗑️ Delete Cache File", key="cache_delete", type="secondary"):
            try:
                if _cache_path.exists():
                    _cache_path.unlink()
                _bump_data_version(_TODAY)
                st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")
                st.toast("🗑️ Cache file deleted — pages will read from DB", icon="✅")
                st.rerun()
            except Exception as _de:
                st.error(f"Failed: {_de}")

    with _cc[2]:
        st.caption("Rebuild the cache from today\'s DB picks")
        if st.button("🔄 Rebuild Cache from DB", key="cache_rebuild", type="primary"):
            try:
                from tracking.database import get_slate_picks_for_today
                _db_picks = get_slate_picks_for_today()
                _cache_path.parent.mkdir(parents=True, exist_ok=True)
                _cache_path.write_text(
                    _js.dumps({"date": _TODAY, "written_at": datetime.datetime.utcnow().isoformat(),
                               "picks": _db_picks}, indent=2, default=str),
                    encoding="utf-8",
                )
                _bump_data_version(_TODAY)
                st.session_state["_dbm_last_write"] = datetime.datetime.now().strftime("%H:%M:%S")
                st.toast(f"🔄 Cache rebuilt with {len(_db_picks)} picks", icon="✅")
                st.rerun()
            except Exception as _re:
                st.error(f"Rebuild failed: {_re}")

    st.markdown("---")
    st.markdown("#### 🔄 data_version signal")
    _dv_path = _pl.Path("cache") / "data_version.json"
    if _dv_path.exists():
        try:
            _dv_data    = _js.loads(_dv_path.read_text(encoding="utf-8"))
            _dv_age_raw = _time.time() - float(_dv_data.get("version", 0))
            _dv2c = st.columns(3)
            _dv2c[0].metric("Version timestamp", datetime.datetime.fromtimestamp(float(_dv_data.get("version",0))).strftime("%H:%M:%S"))
            _dv2c[1].metric("Date", _dv_data.get("date", "—"))
            _dv2c[2].metric("Age", f"{int(_dv_age_raw)}s" if _dv_age_raw < 3600 else f"{int(_dv_age_raw//60)}m")
        except Exception:
            st.info("Could not parse data_version.json")
    else:
        st.info("data_version.json not found — created on next bump.")
    st.caption("Every write in this page calls `_bump_data_version()`. The home page\'s 60-second poller detects the new version and triggers a re-render automatically.")

    st.markdown("---")
    st.markdown("#### 🧠 Latest Analysis Sessions")
    _sess_rows = _db_read(
        "SELECT session_id, analysis_timestamp, COALESCE(prop_count,0) AS picks, sport "
        "FROM analysis_sessions ORDER BY session_id DESC LIMIT 10"
    )
    if _sess_rows:
        st.dataframe(pd.DataFrame(_sess_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No analysis sessions recorded yet.")

# =============================================================================
# TAB 6 — ALL TABLES (generic CRUD)
# =============================================================================
with _TAB_TABLES:
    st.markdown("<div class='sec-hdr'>🗄️ All Tables — Generic CRUD</div>", unsafe_allow_html=True)

    _TABLES = [
        ("bets",               "💰", "Logged bets & auto-logged picks",      "bet_id"),
        ("all_analysis_picks", "⚡", "All QAM Neural Analysis outputs",       "pick_id"),
        ("analysis_sessions",  "🧠", "Saved analysis sessions",              "session_id"),
        ("users",              "👥", "User accounts & tiers",                "user_id"),
        ("subscriptions",      "💎", "Stripe subscription records",          "subscription_id"),
        ("entries",            "📋", "Parlay entry records",                 "entry_id"),
        ("daily_snapshots",    "📊", "Daily performance snapshots",          "snapshot_id"),
        ("prediction_history", "🎯", "Model calibration history",            "prediction_id"),
        ("player_game_logs",   "🏀", "Cached NBA game logs",                 "log_id"),
        ("backtest_results",   "📈", "Backtest run results",                 "backtest_id"),
        ("bet_audit_log",      "🔍", "Bet edit audit trail",                 "audit_id"),
        ("user_settings",      "⚙️",  "User settings (JSON)",                "settings_id"),
        ("page_state",         "📌", "Persisted page state",                 "state_id"),
        ("app_state",          "🔧", "App key-value store",                  "key"),
        ("slate_cache",        "📡", "ETL slate cache runs",                 "id"),
    ]
    _TM = {t[0]: {"emoji": t[1], "desc": t[2], "pk": t[3]} for t in _TABLES}

    _ov = st.columns(5)
    for _i, (_tn, _te, _td, _tp) in enumerate(_TABLES):
        _ov[_i % 5].metric(f"{_te} {_tn}", f"{_count(_tn):,}")

    st.markdown("---")

    _sel = st.selectbox(
        "Table:",
        [t[0] for t in _TABLES],
        format_func=lambda t: f"{_TM[t]['emoji']}  {t}  —  {_TM[t]['desc']}",
        key="all_tbl_sel",
    )
    _tpk     = _TM[_sel]["pk"]
    _t_total = _count(_sel)
    st.caption(f"**{_sel}** · {_t_total:,} rows · PK: `{_tpk}`")

    _at1, _at2, _at3, _at4 = st.tabs(["👁️ View / Search", "✏️ Edit Row", "🗑️ Delete", "➕ Insert"])

    with _at1:
        _av = st.columns([2, 3, 1])
        _at_ps  = _av[0].selectbox("Rows/page", [50,100,200,500], index=1, key=f"at_ps_{_sel}")
        _at_sv  = _av[1].text_input("🔍 Search", key=f"at_sv_{_sel}", placeholder="Leave blank for all")
        _max_p  = max(1, (_t_total - 1) // _at_ps + 1) if _t_total else 1
        _at_pg  = _av[2].number_input("Page", 1, _max_p, 1, key=f"at_pg_{_sel}")
        _at_off = (_at_pg - 1) * _at_ps

        _at_rows = _db_read(f"SELECT * FROM {_sel} ORDER BY rowid DESC LIMIT ? OFFSET ?",
                            (_at_ps, _at_off))
        if _at_sv.strip() and _at_rows:
            _at_tcols = [c for c, v in _at_rows[0].items() if isinstance(v, str) and c != _tpk]
            if _at_tcols:
                _at_rows = _db_read(
                    f"SELECT * FROM {_sel} WHERE LOWER(CAST({_at_tcols[0]} AS TEXT)) LIKE ? "
                    f"ORDER BY rowid DESC LIMIT ? OFFSET ?",
                    (f"%{_at_sv.strip().lower()}%", _at_ps, _at_off),
                )
        if _at_rows:
            _at_df = pd.DataFrame(_at_rows)
            st.dataframe(_at_df, use_container_width=True, hide_index=True)
            st.caption(f"{len(_at_rows)} rows shown (page {_at_pg}/{_max_p})")
            st.download_button(
                f"⬇️ Export {_sel}.csv",
                _at_df.to_csv(index=False).encode(),
                file_name=f"{_sel}_{datetime.date.today()}.csv",
                mime="text/csv", key=f"at_exp_{_sel}",
            )
        else:
            st.info(f"No rows in `{_sel}`.")

    with _at2:
        _ep = st.text_input(f"`{_tpk}` value:", key=f"at_ep_{_sel}", placeholder="e.g. 42")
        if _ep:
            _er = _db_read(f"SELECT * FROM {_sel} WHERE {_tpk} = ?", (_ep,))
            if not _er:
                st.warning(f"No row with {_tpk} = {_ep!r}")
            else:
                _erow = _er[0]
                st.success("Row found — edit below and save.")
                _ev: dict = {}
                _ec = st.columns(2)
                for _ei, _ef in enumerate([c for c in _erow if c != _tpk]):
                    _cur = _erow[_ef]
                    _wc  = _ec[_ei % 2]
                    if _cur is None or isinstance(_cur, (int, float)):
                        _ev[_ef] = _wc.text_input(f"`{_ef}`", value="" if _cur is None else str(_cur),
                                                   key=f"at_ev_{_sel}_{_ef}")
                    else:
                        _ev[_ef] = _wc.text_area(f"`{_ef}`", value=str(_cur), height=70,
                                                  key=f"at_ev_{_sel}_{_ef}")
                if st.button("💾 Save", key=f"at_save_{_sel}", type="primary"):
                    _ok = all(
                        _run_write(f"UPDATE {_sel} SET {_f} = ? WHERE {_tpk} = ?",
                                   (_nv or None, _ep), f"at_edit_{_sel}")
                        for _f, _nv in _ev.items()
                        if str(_nv) != str(_erow.get(_f, "") or "")
                    )
                    if _ok:
                        st.toast("✅ Saved — pages refreshing…", icon="✅")

    with _at3:
        _dm = st.radio("Mode:", ["Single row","Bulk filter","Purge all"], key=f"at_dm_{_sel}", horizontal=True)
        if _dm == "Single row":
            _dpk = st.text_input(f"`{_tpk}` to delete:", key=f"at_dpk_{_sel}")
            if _dpk:
                _dp = _db_read(f"SELECT * FROM {_sel} WHERE {_tpk} = ?", (_dpk,))
                if _dp:
                    st.dataframe(pd.DataFrame(_dp), use_container_width=True, hide_index=True)
                    if st.button("🗑️ Delete", key=f"at_drow_{_sel}", type="primary"):
                        if _run_write(f"DELETE FROM {_sel} WHERE {_tpk} = ?", (_dpk,), f"at_del_{_sel}"):
                            st.toast("✅ Deleted — pages refreshing…", icon="✅")
                else:
                    st.warning("Row not found.")
        elif _dm == "Bulk filter":
            _bc, _bo, _bv = st.columns(3)
            _bfc = _bc.text_input("Column:", key=f"at_bfc_{_sel}", placeholder="bet_date")
            _bfo = _bo.selectbox("Operator:", ["=","<",">","<=",">=","LIKE"], key=f"at_bfo_{_sel}")
            _bfv = _bv.text_input("Value:", key=f"at_bfv_{_sel}")
            if _bfc and _bfv:
                _bfn = _db_read(f"SELECT COUNT(*) AS n FROM {_sel} WHERE {_bfc} {_bfo} ?", (_bfv,))
                _bfcnt = _bfn[0]["n"] if _bfn else 0
                st.info(f"Will delete **{_bfcnt:,}** rows.")
                if _bfcnt > 0 and _confirm_button(f"🗑️ Delete {_bfcnt:,} rows", f"at_bf_{_sel}", danger=True):
                    if _run_write(f"DELETE FROM {_sel} WHERE {_bfc} {_bfo} ?", (_bfv,), f"at_bf_{_sel}"):
                        st.toast(f"✅ Deleted {_bfcnt:,} rows — pages refreshing…", icon="✅")
        else:
            st.error(f"Will DELETE EVERY row in `{_sel}`.")
            if _confirm_button(f"⛔ PURGE ALL — {_sel}", f"at_purge_{_sel}", danger=True):
                if _run_write(f"DELETE FROM {_sel}", caller=f"at_purge_{_sel}"):
                    st.toast(f"✅ All rows deleted from `{_sel}` — pages refreshing…", icon="✅")

    with _at4:
        st.caption(f"Insert into `{_sel}`. Leave PK blank for auto-increment.")
        _is = _db_read(f"SELECT * FROM {_sel} LIMIT 1")
        if _is:
            _ic_list = [c for c in _is[0] if c != _tpk]
            _iv: dict = {}
            _ic = st.columns(2)
            for _ii, _ifc in enumerate(_ic_list):
                _iv[_ifc] = _ic[_ii % 2].text_input(
                    f"`{_ifc}`", value="",
                    help=f"e.g. {str(_is[0].get(_ifc,''))[:50]}" if _is[0].get(_ifc) else "",
                    key=f"at_ins_{_sel}_{_ifc}",
                )
        else:
            _ic_list = []
            _iv = {}
            _json_raw = st.text_area("Row as JSON:", height=120, key=f"at_ins_json_{_sel}",
                                      placeholder="{'col':'val'}")
        if st.button("➕ Insert", key=f"at_ins_btn_{_sel}", type="primary"):
            if _ic_list:
                _iclean = {k: v for k, v in _iv.items() if v}
            else:
                try:    _iclean = json.loads(_json_raw)
                except Exception as _je: st.error(f"JSON error: {_je}"); _iclean = {}
            if _iclean:
                _ik, _iph = list(_iclean.keys()), ",".join(["?"] * len(_iclean))
                if _run_write(f"INSERT INTO {_sel} ({','.join(_ik)}) VALUES ({_iph})",
                              tuple(_iclean.values()), f"at_ins_{_sel}"):
                    st.toast(f"✅ Row inserted into `{_sel}` — pages refreshing…", icon="✅")
            else:
                st.warning("Nothing to insert.")

# =============================================================================
# TAB 7 — RAW SQL CONSOLE
# =============================================================================
with _TAB_SQL:
    st.markdown("<div class='sec-hdr'>🔧 Raw SQL Console</div>", unsafe_allow_html=True)
    st.warning("⚠️ Writes execute immediately on the active backend and bump `data_version`. No undo.")

    _sql_mode = st.radio(
        "Mode:", ["SELECT (read)", "Write (INSERT / UPDATE / DELETE / DDL)"],
        horizontal=True, key="sql_mode",
    )
    _sql_input = st.text_area(
        "SQL:", height=160, key="sql_input",
        placeholder=f"SELECT * FROM bets WHERE bet_date = '{_TODAY}' ORDER BY created_at DESC LIMIT 50",
    )

    _sr = st.columns([2, 2, 4])
    if _sr[0].button("▶️ Run", key="sql_run", type="primary") and _sql_input.strip():
        if _sql_mode.startswith("SELECT"):
            _res = _db_read(_sql_input.strip())
            if _res:
                _rdf = pd.DataFrame(_res)
                st.dataframe(_rdf, use_container_width=True, hide_index=True)
                st.caption(f"{len(_res)} row(s)")
                _sr[1].download_button(
                    "⬇️ Export", _rdf.to_csv(index=False).encode(),
                    file_name=f"query_{datetime.date.today()}.csv", mime="text/csv", key="sql_export",
                )
            else:
                st.info("No rows returned.")
        else:
            if _run_write(_sql_input.strip(), caller="sql_console"):
                st.toast("✅ Write executed — pages refreshing…", icon="✅")

    with st.expander("📋 Quick reference queries"):
        _month_start = datetime.date.today().strftime('%Y-%m-01')
        st.code(f"""-- Today\'s pending bets
SELECT * FROM bets WHERE bet_date = '{_TODAY}' AND (result IS NULL OR result=\'\');

-- Mark a bet result
UPDATE bets SET result=\'win\', actual_value=28.5 WHERE bet_id=123;

-- Today\'s picks by confidence
SELECT player_name,stat_type,prop_line,direction,tier,confidence_score,result
FROM all_analysis_picks WHERE pick_date='{_TODAY}' ORDER BY confidence_score DESC;

-- Win rate this month
SELECT result, COUNT(*) AS cnt FROM bets
WHERE bet_date >= '{_month_start}' AND result IS NOT NULL AND result != \'\'
GROUP BY result;

-- Latest sessions
SELECT session_id,analysis_timestamp,prop_count FROM analysis_sessions
ORDER BY session_id DESC LIMIT 5;

-- Check data version (cross-container)
SELECT * FROM app_state WHERE key=\'data_version\';

-- Active users (last 7 days)
SELECT user_id,email,plan_tier,last_login_at FROM users
WHERE last_login_at >= datetime(\'now\',\'-7 days\') ORDER BY last_login_at DESC;
""", language="sql")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"🗄️ DB Control Center  ·  Backend: **{_BACKEND}**  ·  Today: **{_TODAY}**  ·  "
    f"Last write: **{st.session_state.get('_dbm_last_write', '—')}**  ·  "
    "All writes bump `data_version` — running pages auto-refresh within 60 s"
)
