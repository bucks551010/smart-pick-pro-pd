# ============================================================
# FILE: pages/98_🗄️_DB_Manager.py
# PURPOSE: Admin database manager — full CRUD over all tracking
#          tables.  All reads/writes route through _db_read /
#          _db_write so every change is reflected in BOTH the
#          local SQLite (dev) and PostgreSQL (Railway/prod) DB.
#
# ACCESS: Admin-only (is_admin_user gate).
# ============================================================

import os
import json
import datetime

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="DB Manager · Smart Pick Pro",
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
    st.error("🔒 Access denied. This page is restricted to administrators.")
    st.stop()

from tracking.database import _db_read, _db_write, _DATABASE_URL

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] > .main {
    background: radial-gradient(ellipse at 20% 0%, rgba(45,158,255,0.08) 0%, transparent 55%),
                radial-gradient(ellipse at 80% 100%, rgba(176,110,255,0.07) 0%, transparent 55%),
                #0a0d14 !important;
}
[data-testid="stSidebar"] {
    background: #070a10 !important;
    border-right: 1px solid rgba(45,158,255,0.12) !important;
}
.block-container { padding-top: 0 !important; max-width: 1400px !important; }

.dbm-hero {
    background: linear-gradient(135deg, #0f1928 0%, #0a0d14 40%, #0d1020 100%);
    border: 1px solid rgba(45,158,255,0.18);
    border-radius: 16px;
    padding: 26px 36px 20px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.dbm-hero::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #2D9EFF 0%, #B06EFF 50%, #00D559 100%);
}
.dbm-hero-title { font-size: 1.9rem; font-weight: 800; color: #f0f4ff; margin: 0 0 4px; }
.dbm-hero-sub   { font-size: 0.82rem; color: #7a8499; margin: 0 0 14px; }
.dbm-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 11px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;
}
.dbm-badge-blue  { background: rgba(45,158,255,0.12); color: #2D9EFF; border: 1px solid rgba(45,158,255,0.25); }
.dbm-badge-gold  { background: rgba(249,198,43,0.12);  color: #F9C62B; border: 1px solid rgba(249,198,43,0.25); }
.dbm-badge-green { background: rgba(0,213,89,0.10);    color: #00D559; border: 1px solid rgba(0,213,89,0.22); }
.dbm-badge-red   { background: rgba(242,67,54,0.10);   color: #F24336; border: 1px solid rgba(242,67,54,0.22); }

.dbm-section {
    background: rgba(15,20,40,0.7);
    border: 1px solid rgba(45,158,255,0.1);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 20px;
}
.dbm-section-title {
    font-size: 1rem; font-weight: 700; color: #f0f4ff;
    margin: 0 0 14px; padding-bottom: 10px;
    border-bottom: 1px solid rgba(45,158,255,0.1);
    display: flex; align-items: center; gap: 8px;
}
.dbm-tbl-count {
    font-size: 0.7rem; color: #7a8499; background: rgba(45,158,255,0.08);
    border: 1px solid rgba(45,158,255,0.15); border-radius: 10px;
    padding: 1px 8px; margin-left: auto;
}

[data-testid="stDataFrame"] { border-radius: 10px !important; }
[data-testid="stButton"] > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Backend badge ─────────────────────────────────────────────────────────────
_backend = "PostgreSQL (Railway)" if _DATABASE_URL else "SQLite (local)"
_badge_cls = "dbm-badge-green" if _DATABASE_URL else "dbm-badge-gold"

st.markdown(f"""
<div class="dbm-hero">
  <div class="dbm-hero-title">🗄️ Database Manager</div>
  <div class="dbm-hero-sub">Full CRUD control over every tracking table. All edits sync to both SQLite and PostgreSQL.</div>
  <span class="dbm-badge {_badge_cls}">● {_backend}</span>
  &nbsp;<span class="dbm-badge dbm-badge-blue">🔐 Admin Only</span>
</div>
""", unsafe_allow_html=True)

# ── Table registry ────────────────────────────────────────────────────────────
# (table_name, emoji, description, primary_key_col)
_TABLES = [
    ("bets",               "💰", "Logged bets & auto-logged picks",        "bet_id"),
    ("all_analysis_picks", "⚡", "All QAM Neural Analysis outputs",         "pick_id"),
    ("analysis_sessions",  "🧠", "Saved analysis sessions (JSON blob)",     "session_id"),
    ("subscriptions",      "💎", "Stripe subscription records",             "subscription_id"),
    ("entries",            "📋", "Parlay entry records",                    "entry_id"),
    ("daily_snapshots",    "📊", "Daily aggregated performance snapshots",  "snapshot_id"),
    ("prediction_history", "🎯", "Model calibration prediction history",    "prediction_id"),
    ("player_game_logs",   "🏀", "Cached NBA game logs (per player)",       "log_id"),
    ("backtest_results",   "📈", "Historical backtest run results",         "backtest_id"),
    ("bet_audit_log",      "🔍", "Audit trail for bet edits/deletes",       "audit_id"),
    ("user_settings",      "⚙️", "User-configured app settings (JSON)",     "settings_id"),
    ("page_state",         "📌", "Persisted page state blob",               "state_id"),
    ("app_state",          "🔧", "Key-value application state store",       "key"),
    ("slate_cache",        "📡", "ETL slate cache run history",             "id"),
]

_TABLE_NAMES = [t[0] for t in _TABLES]
_TABLE_META  = {t[0]: {"emoji": t[1], "desc": t[2], "pk": t[3]} for t in _TABLES}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _count(table: str) -> int:
    try:
        rows = _db_read(f"SELECT COUNT(*) AS n FROM {table}")
        return rows[0]["n"] if rows else 0
    except Exception:
        return -1


def _fetch_rows(table: str, limit: int = 200, offset: int = 0,
                search_col: str = "", search_val: str = "") -> list[dict]:
    try:
        if search_col and search_val:
            return _db_read(
                f"SELECT * FROM {table} WHERE LOWER(CAST({search_col} AS TEXT)) LIKE ? "
                f"ORDER BY rowid DESC LIMIT ? OFFSET ?",
                (f"%{search_val.lower()}%", limit, offset),
            )
        return _db_read(
            f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    except Exception as exc:
        st.error(f"Fetch error: {exc}")
        return []


def _delete_row(table: str, pk_col: str, pk_val) -> bool:
    try:
        _db_write(f"DELETE FROM {table} WHERE {pk_col} = ?", (pk_val,),
                  caller=f"dbm_delete_{table}")
        return True
    except Exception as exc:
        st.error(f"Delete error: {exc}")
        return False


def _update_row(table: str, pk_col: str, pk_val, field: str, new_val) -> bool:
    try:
        _db_write(
            f"UPDATE {table} SET {field} = ? WHERE {pk_col} = ?",
            (new_val, pk_val),
            caller=f"dbm_update_{table}",
        )
        return True
    except Exception as exc:
        st.error(f"Update error: {exc}")
        return False


def _insert_row(table: str, data: dict) -> bool:
    cols = list(data.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    try:
        _db_write(
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
            tuple(data.values()),
            caller=f"dbm_insert_{table}",
        )
        return True
    except Exception as exc:
        st.error(f"Insert error: {exc}")
        return False


# ── Overview: row counts for all tables ───────────────────────────────────────
with st.expander("📊 Table Overview", expanded=True):
    _cols = st.columns(7)
    for i, (tname, emoji, desc, _pk) in enumerate(_TABLES):
        cnt = _count(tname)
        _cols[i % 7].metric(f"{emoji} {tname}", f"{cnt:,}" if cnt >= 0 else "—")

st.markdown("---")

# ── Table selector ────────────────────────────────────────────────────────────
_sel_table = st.selectbox(
    "Select table to manage:",
    _TABLE_NAMES,
    format_func=lambda t: f"{_TABLE_META[t]['emoji']}  {t}  —  {_TABLE_META[t]['desc']}",
    key="dbm_table_select",
)

_pk_col  = _TABLE_META[_sel_table]["pk"]
_total   = _count(_sel_table)

st.markdown(f"""
<div class="dbm-section">
  <div class="dbm-section-title">
    {_TABLE_META[_sel_table]['emoji']} &nbsp; <b>{_sel_table}</b>
    &nbsp;<span style="color:#7a8499;font-size:0.78rem;font-weight:400">{_TABLE_META[_sel_table]['desc']}</span>
    <span class="dbm-tbl-count">{_total:,} rows total</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Action tabs ───────────────────────────────────────────────────────────────
_tab_view, _tab_edit, _tab_delete, _tab_add, _tab_sql = st.tabs([
    "👁️ View / Search", "✏️ Edit Row", "🗑️ Delete Rows", "➕ Add Row", "🔧 Raw SQL"
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB: View / Search
# ─────────────────────────────────────────────────────────────────────────────
with _tab_view:
    _vcol1, _vcol2, _vcol3 = st.columns([2, 3, 1])
    with _vcol1:
        _page_size = st.selectbox("Rows per page", [50, 100, 200, 500], index=1,
                                   key=f"dbm_page_size_{_sel_table}")
    with _vcol2:
        _search_val = st.text_input("🔍 Search value (scans all text columns)",
                                     key=f"dbm_search_{_sel_table}", placeholder="Leave blank to show all")
    with _vcol3:
        # Page navigation
        _max_page = max(1, (_total - 1) // _page_size + 1) if _total > 0 else 1
        _page_num = st.number_input("Page", min_value=1, max_value=_max_page,
                                     value=1, key=f"dbm_page_{_sel_table}")

    _offset = (_page_num - 1) * _page_size

    # If search, do a broad LIKE across the first text column detected
    _rows = _fetch_rows(_sel_table, limit=_page_size, offset=_offset,
                        search_col="", search_val="")  # broad fetch first to get columns

    if _search_val and _rows:
        # Detect text columns from first row
        _text_cols = [c for c, v in _rows[0].items()
                      if isinstance(v, str) and c != _pk_col]
        if _text_cols:
            # Re-fetch filtered by first text column matching
            _rows = _fetch_rows(_sel_table, limit=_page_size, offset=_offset,
                                search_col=_text_cols[0], search_val=_search_val)

    if _rows:
        _df = pd.DataFrame(_rows)
        st.dataframe(_df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(_rows)} rows (page {_page_num}/{_max_page}, offset {_offset})")

        # Download button
        _csv = _df.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"⬇️ Export {_sel_table}.csv",
            _csv,
            file_name=f"{_sel_table}_{datetime.date.today()}.csv",
            mime="text/csv",
            key=f"dbm_export_{_sel_table}",
        )
    else:
        st.info(f"No rows found in `{_sel_table}`.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB: Edit Row
# ─────────────────────────────────────────────────────────────────────────────
with _tab_edit:
    st.caption(f"Find a row by its primary key (`{_pk_col}`), then edit any field.")
    _pk_input = st.text_input(f"Primary key value ({_pk_col}):",
                               key=f"dbm_edit_pk_{_sel_table}", placeholder="e.g. 42")
    if _pk_input:
        _edit_rows = _db_read(
            f"SELECT * FROM {_sel_table} WHERE {_pk_col} = ?", (_pk_input,)
        )
        if not _edit_rows:
            st.warning(f"No row found with {_pk_col} = {_pk_input!r}")
        else:
            _edit_row = _edit_rows[0]
            st.success(f"Row found — edit fields below and click **Save**.")
            _edit_cols = [c for c in _edit_row.keys() if c != _pk_col]

            _new_vals: dict = {}
            for _field in _edit_cols:
                _cur = _edit_row[_field]
                _label = f"`{_field}`"
                if _cur is None:
                    _new_vals[_field] = st.text_input(_label, value="",
                                                       key=f"dbm_edit_{_sel_table}_{_field}")
                elif isinstance(_cur, (int, float)):
                    _new_vals[_field] = st.text_input(_label, value=str(_cur),
                                                       key=f"dbm_edit_{_sel_table}_{_field}")
                else:
                    _new_vals[_field] = st.text_area(_label, value=str(_cur),
                                                      height=80,
                                                      key=f"dbm_edit_{_sel_table}_{_field}")

            if st.button("💾 Save Changes", key=f"dbm_save_{_sel_table}", type="primary"):
                _ok_all = True
                for _field, _nv in _new_vals.items():
                    _orig = str(_edit_row.get(_field, "") or "")
                    if _nv != _orig:
                        _ok = _update_row(_sel_table, _pk_col, _pk_input, _field, _nv)
                        if not _ok:
                            _ok_all = False
                if _ok_all:
                    st.success("✅ Row updated successfully. Changes are live in the database.")
                    st.cache_data.clear()
                else:
                    st.error("⚠️ One or more fields failed to update — check errors above.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB: Delete Rows
# ─────────────────────────────────────────────────────────────────────────────
with _tab_delete:
    st.caption("Delete one row by primary key, or bulk-delete rows matching a filter.")

    _del_mode = st.radio("Delete mode:", ["Single row", "Bulk filter", "Purge all rows"],
                          key=f"dbm_del_mode_{_sel_table}", horizontal=True)

    if _del_mode == "Single row":
        _del_pk = st.text_input(f"Primary key (`{_pk_col}`) to delete:",
                                 key=f"dbm_del_pk_{_sel_table}")
        if _del_pk:
            _preview = _db_read(f"SELECT * FROM {_sel_table} WHERE {_pk_col} = ?", (_del_pk,))
            if _preview:
                st.dataframe(pd.DataFrame(_preview), use_container_width=True, hide_index=True)
                if st.button("🗑️ Delete this row", key=f"dbm_del_single_{_sel_table}",
                              type="primary"):
                    if _delete_row(_sel_table, _pk_col, _del_pk):
                        st.success(f"✅ Row {_del_pk} deleted.")
                        st.cache_data.clear()
            else:
                st.warning(f"No row with {_pk_col} = {_del_pk!r}")

    elif _del_mode == "Bulk filter":
        st.warning("⚠️ This will permanently delete all matching rows.")
        _bf_col  = st.text_input("Column name to filter on:", key=f"dbm_bf_col_{_sel_table}",
                                  placeholder="e.g. bet_date")
        _bf_op   = st.selectbox("Operator:", ["=", "<", ">", "<=", ">=", "LIKE"],
                                 key=f"dbm_bf_op_{_sel_table}")
        _bf_val  = st.text_input("Value:", key=f"dbm_bf_val_{_sel_table}",
                                  placeholder="e.g. 2026-04-01")
        if _bf_col and _bf_val:
            _preview_sql = f"SELECT COUNT(*) AS n FROM {_sel_table} WHERE {_bf_col} {_bf_op} ?"
            try:
                _preview_cnt = _db_read(_preview_sql, (_bf_val,))
                _n = _preview_cnt[0]["n"] if _preview_cnt else 0
                st.info(f"This will delete **{_n:,}** row(s).")
                if _n > 0 and st.button(f"🗑️ Delete {_n:,} rows", type="primary",
                                         key=f"dbm_bf_del_{_sel_table}"):
                    _db_write(
                        f"DELETE FROM {_sel_table} WHERE {_bf_col} {_bf_op} ?",
                        (_bf_val,),
                        caller=f"dbm_bulk_delete_{_sel_table}",
                    )
                    st.success(f"✅ Deleted {_n:,} rows from `{_sel_table}`.")
                    st.cache_data.clear()
            except Exception as exc:
                st.error(f"Preview error: {exc}")

    else:  # Purge all rows
        st.error(f"⛔ This will DELETE ALL rows from `{_sel_table}` permanently.")
        _confirm = st.text_input(f"Type the table name **{_sel_table}** to confirm:",
                                  key=f"dbm_purge_confirm_{_sel_table}")
        if _confirm == _sel_table:
            if st.button(f"⛔ PURGE ALL rows from {_sel_table}", type="primary",
                          key=f"dbm_purge_{_sel_table}"):
                _db_write(f"DELETE FROM {_sel_table}", caller=f"dbm_purge_{_sel_table}")
                st.success(f"✅ All rows deleted from `{_sel_table}`.")
                st.cache_data.clear()

# ─────────────────────────────────────────────────────────────────────────────
# TAB: Add Row
# ─────────────────────────────────────────────────────────────────────────────
with _tab_add:
    st.caption(f"Insert a new row into `{_sel_table}`. Leave auto-increment fields blank.")

    # Sample existing row to infer columns + default empty values
    _sample = _db_read(f"SELECT * FROM {_sel_table} LIMIT 1")
    if _sample:
        _add_cols = [c for c in _sample[0].keys() if c != _pk_col]
    else:
        # Table empty — ask user for JSON
        _add_cols = []

    if _add_cols:
        _new_row: dict = {}
        _add_col1, _add_col2 = st.columns(2)
        for i, _field in enumerate(_add_cols):
            _sample_val = _sample[0].get(_field, "")
            _widget_col = _add_col1 if i % 2 == 0 else _add_col2
            _new_row[_field] = _widget_col.text_input(
                f"`{_field}`",
                value="",
                help=f"Sample: {str(_sample_val)[:60]}" if _sample_val is not None else "",
                key=f"dbm_add_{_sel_table}_{_field}",
            )

        if st.button("➕ Insert Row", key=f"dbm_insert_{_sel_table}", type="primary"):
            # Strip empty strings → None so nullable columns don't get empty strings
            _clean = {k: (v if v != "" else None) for k, v in _new_row.items()}
            # Remove None values to let DB defaults apply
            _clean = {k: v for k, v in _clean.items() if v is not None}
            if not _clean:
                st.warning("All fields are empty — nothing to insert.")
            else:
                if _insert_row(_sel_table, _clean):
                    st.success(f"✅ Row inserted into `{_sel_table}`.")
                    st.cache_data.clear()
    else:
        st.info(f"`{_sel_table}` is empty. Enter row data as JSON:")
        _json_input = st.text_area("Row data (JSON object):",
                                    height=120,
                                    key=f"dbm_add_json_{_sel_table}",
                                    placeholder='{"field": "value", ...}')
        if st.button("➕ Insert Row (JSON)", key=f"dbm_insert_json_{_sel_table}", type="primary"):
            try:
                _data = json.loads(_json_input)
                if _insert_row(_sel_table, _data):
                    st.success(f"✅ Row inserted.")
                    st.cache_data.clear()
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB: Raw SQL
# ─────────────────────────────────────────────────────────────────────────────
with _tab_sql:
    st.caption("Run any SQL against the active backend (SQLite or PostgreSQL). SELECT = read. Everything else = write.")
    st.warning("⚠️ Write queries execute immediately with no undo. Use with care.")

    _sql_type = st.radio("Query type:", ["SELECT (read)", "Write (INSERT / UPDATE / DELETE / DDL)"],
                          horizontal=True, key="dbm_sql_type")
    _sql_input = st.text_area(
        "SQL:",
        height=140,
        key="dbm_sql_input",
        placeholder="SELECT * FROM bets WHERE bet_date = '2026-04-25' LIMIT 20",
    )

    if st.button("▶️ Run SQL", key="dbm_run_sql", type="primary") and _sql_input.strip():
        _clean_sql = _sql_input.strip()
        if _sql_type.startswith("SELECT"):
            _result = _db_read(_clean_sql)
            if _result:
                st.dataframe(pd.DataFrame(_result), use_container_width=True, hide_index=True)
                st.caption(f"{len(_result)} row(s) returned")
            else:
                st.info("No rows returned.")
        else:
            try:
                _db_write(_clean_sql, caller="dbm_raw_sql")
                st.success("✅ Write query executed successfully.")
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Write error: {exc}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"🗄️ DB Manager  ·  Backend: **{_backend}**  ·  "
    f"All writes route through `_db_write` (PostgreSQL on Railway, SQLite locally)  ·  "
    f"Changes are immediate and permanent."
)
