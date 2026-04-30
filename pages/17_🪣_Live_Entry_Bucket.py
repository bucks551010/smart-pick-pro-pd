# ============================================================
# FILE: pages/17_🪣_Live_Entry_Bucket.py
# PURPOSE: Per-user staging area for picks added from the QAM.
#          Users review their picks here, optionally remove some,
#          then either:
#            (a) "Send to Entry Builder" — pushes them into the
#                shared selected_picks session state for slip
#                generation, OR
#            (b) "Lock as personal bets" — writes one bet row
#                per leg directly into the bets table (tagged
#                with user_email) so the Bet Tracker page picks
#                them up under that user's view.
#
# SECURITY:
#   • Bucket rows are scoped by user_email; the page only ever
#     loads/writes for the active user (utils.user_session).
#   • In dev / no-Stripe mode the user is "anonymous@local"
#     so the page still works without auth.
# ============================================================

import datetime as _dt
import streamlit as st

st.set_page_config(
    page_title="Live Entry Bucket — Smart Pick Pro",
    page_icon="🪣",
    layout="wide",
)

# ── Auth gate ────────────────────────────────────────────────────
try:
    from utils.auth_gate import require_login as _require_login
    if not _require_login():
        st.stop()
except ImportError:
    pass

# ── Inject global theme ──────────────────────────────────────────
try:
    from styles.theme import get_global_css
    st.markdown(get_global_css(), unsafe_allow_html=True)
except Exception:
    pass

from utils.user_session import (
    get_current_user_email,
    get_user_display_label,
    is_anonymous_user,
)
from tracking.live_bucket import (
    get_bucket,
    remove_bucket_id,
    clear_bucket,
    bucket_count,
    pick_to_selected_format,
    get_bucket_as_selected_picks,
)

_user_email = get_current_user_email()


# ── Header ───────────────────────────────────────────────────────
st.markdown(
    """
    <div style="padding:18px 22px;border-radius:14px;
                background:linear-gradient(135deg,rgba(0,240,255,0.08),rgba(200,0,255,0.08));
                border:1px solid rgba(0,240,255,0.18);margin-bottom:16px;">
      <div style="font-size:1.6rem;font-weight:800;
                  background:linear-gradient(135deg,#00f0ff,#c800ff);
                  -webkit-background-clip:text;color:transparent;">
        🪣 Live Entry Bucket
      </div>
      <div style="color:rgba(255,255,255,0.6);font-size:0.95rem;margin-top:4px;">
        Your personal staging area. Add picks from the
        <b>⚡ Quantum Analysis Matrix</b>, review them here, then send
        to the <b>🧬 Entry Builder</b> or lock them straight into your
        tracked bets.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(get_user_display_label())
if is_anonymous_user():
    st.info(
        "🛈 You're in **guest mode**. Your bucket is shared by every "
        "guest viewer on this device. Subscribe / sign in to keep your "
        "bucket private and synced across devices."
    )

# ── Load bucket ───────────────────────────────────────────────────
_rows = get_bucket(_user_email)
_total = len(_rows)

_top_c1, _top_c2, _top_c3, _top_c4 = st.columns([1, 1, 1, 1])
with _top_c1:
    st.metric("🪣 Picks in bucket", _total)
with _top_c2:
    _platinum = sum(1 for r in _rows if r.get("tier") == "Platinum")
    st.metric("💎 Platinum", _platinum)
with _top_c3:
    _gold = sum(1 for r in _rows if r.get("tier") == "Gold")
    st.metric("🥇 Gold", _gold)
with _top_c4:
    _avg_edge = (
        sum(float(r.get("edge_percentage") or 0) for r in _rows) / _total
        if _total else 0.0
    )
    st.metric("📈 Avg Edge", f"{_avg_edge:.1f}%")

st.divider()

if _total == 0:
    st.info(
        "Your bucket is empty. Head to the **⚡ Quantum Analysis Matrix** "
        "and use the **🪣 Bucket** controls to stage picks for review."
    )
    if st.button("⚡ Open Quantum Analysis Matrix", type="primary"):
        st.switch_page("pages/3_⚡_Quantum_Analysis_Matrix.py")
    st.stop()


# ── Action buttons ────────────────────────────────────────────────
_act_c1, _act_c2, _act_c3, _act_c4 = st.columns([1.1, 1.1, 1.0, 0.8])

with _act_c1:
    if st.button("🧬 Send to Entry Builder", type="primary",
                 help="Copy bucket picks into the Entry Builder cart"):
        _converted = [pick_to_selected_format(r) for r in _rows]
        _existing = st.session_state.get("selected_picks", []) or []
        _seen = {p.get("key") for p in _existing}
        _added = 0
        for p in _converted:
            if p.get("key") and p["key"] not in _seen:
                _existing.append(p)
                _seen.add(p["key"])
                _added += 1
        st.session_state["selected_picks"] = _existing
        st.success(f"✅ Sent {_added} pick(s) to Entry Builder.")
        try:
            st.switch_page("pages/8_🧬_Entry_Builder.py")
        except Exception:
            st.info("Open the 🧬 Entry Builder page to view your slip.")

with _act_c2:
    _lock_now = st.button(
        "🔒 Lock as personal bets",
        help="Log every pick in your bucket as an individual bet "
             "tagged to your account (no entry/parlay). Picks remain "
             "in your bucket — clear after locking if desired.",
    )

with _act_c3:
    _platform_default = next(
        (r.get("platform") for r in _rows if r.get("platform")), "Custom"
    )
    _entry_fee = st.number_input(
        "Entry $ (for parlay-lock)", min_value=0.0, max_value=10000.0,
        value=5.0, step=1.0, key="_bucket_entry_fee",
    )

with _act_c4:
    if st.button("🗑️ Clear bucket", help="Remove every pick from your bucket"):
        _n = clear_bucket(_user_email)
        st.toast(f"🗑️ Cleared {_n} pick(s) from your bucket")
        st.rerun()


# ── "Lock as personal bets" handler ──────────────────────────────
if _lock_now:
    try:
        from tracking.database import insert_bet, insert_entry, link_bets_to_entry, _nba_today_iso as _leb_today_fn
    except Exception as _imp_err:
        st.error(f"Database module unavailable: {_imp_err}")
        st.stop()

    # ET-anchored date so Railway UTC server doesn't tag 8 PM-midnight ET
    # bet_lock writes as tomorrow.
    try:
        _today = _leb_today_fn()
    except Exception:
        _today = _dt.date.today().isoformat()
    _bet_ids: list[int] = []
    _failed = 0

    for _row in _rows:
        _bet_data = {
            "bet_date":         _today,
            "player_name":      _row.get("player_name", ""),
            "team":             _row.get("team", ""),
            "stat_type":        _row.get("stat_type", ""),
            "prop_line":        float(_row.get("prop_line") or 0.0),
            "direction":        _row.get("direction", "OVER"),
            "platform":         _row.get("platform", "") or _platform_default,
            "confidence_score": float(_row.get("confidence_score") or 0.0),
            "probability_over": float(_row.get("probability_over") or 0.0),
            "edge_percentage":  float(_row.get("edge_percentage") or 0.0),
            "tier":             _row.get("tier", "") or "Bronze",
            "entry_type":       "bucket-lock",
            "entry_fee":        0.0,
            "notes":            "Locked from Live Entry Bucket",
            "auto_logged":      0,
            "bet_type":         _row.get("bet_type", "normal"),
            "source":           "live_entry_bucket",
            "user_email":       _user_email,
        }
        _bid = insert_bet(_bet_data)
        if _bid:
            _bet_ids.append(int(_bid))
        else:
            _failed += 1

    # Optionally also create a single entries row when fee > 0
    if _entry_fee and _bet_ids:
        _entry_id = insert_entry({
            "entry_date":     _today,
            "platform":       _platform_default,
            "entry_type":     "parlay",
            "entry_fee":      float(_entry_fee),
            "expected_value": 0.0,
            "pick_count":     len(_bet_ids),
            "notes":          "Locked from Live Entry Bucket",
            "user_email":     _user_email,
        })
        if _entry_id:
            try:
                link_bets_to_entry(_bet_ids, int(_entry_id))
            except Exception:
                pass

    if _bet_ids:
        st.success(
            f"🔒 Locked {len(_bet_ids)} bet(s) into your tracked bets "
            f"as **{_user_email}**."
            + (f" ({_failed} failed)" if _failed else "")
        )
        st.balloons()
        # Clear bucket after successful lock so it doesn't double-log
        clear_bucket(_user_email)
        st.toast("🪣 Bucket cleared after lock.")
        if st.button("📈 Open Bet Tracker"):
            st.switch_page("pages/12_📈_Bet_Tracker.py")
        st.rerun()
    else:
        st.error(f"Failed to lock any bets ({_failed} errors). Check logs.")


st.divider()

# ── Pick list w/ per-row remove ──────────────────────────────────
st.markdown("### 🎯 Your bucket")

for _row in _rows:
    _bid = _row.get("bucket_id")
    _emoji = _row.get("tier_emoji") or ""
    _tier = _row.get("tier") or ""
    _player = _row.get("player_name") or "—"
    _stat = (_row.get("stat_type") or "").upper()
    _direction = _row.get("direction") or "OVER"
    _line = _row.get("prop_line") or 0
    _platform = _row.get("platform") or "—"
    _conf = float(_row.get("confidence_score") or 0)
    _edge = float(_row.get("edge_percentage") or 0)
    _odds = _row.get("odds_type") or "standard"
    _added_at = _row.get("added_at") or ""

    _rc1, _rc2, _rc3, _rc4 = st.columns([3, 1.2, 1.2, 0.8])
    with _rc1:
        st.markdown(
            f"**{_emoji} {_player}** · {_stat} {_direction} **{_line}** "
            f"<span style='color:#9ca3af;font-size:0.85rem;'>"
            f"({_platform} · {_odds})</span>",
            unsafe_allow_html=True,
        )
        if _added_at:
            st.caption(f"Added {_added_at}")
    with _rc2:
        st.metric("Conf", f"{_conf:.0f}", label_visibility="visible")
    with _rc3:
        st.metric("Edge", f"{_edge:.1f}%", label_visibility="visible")
    with _rc4:
        if st.button("❌", key=f"_rm_bucket_{_bid}", help="Remove from bucket"):
            if remove_bucket_id(_bid):
                st.toast("Removed from bucket.")
                st.rerun()
            else:
                st.warning("Could not remove pick.")
    st.markdown(
        "<hr style='margin:6px 0;border:none;border-top:1px solid rgba(255,255,255,0.06);'/>",
        unsafe_allow_html=True,
    )
