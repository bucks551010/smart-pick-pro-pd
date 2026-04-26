"""Parlays tab for Bet Tracker."""
import streamlit as st
from styles.theme import get_summary_cards_html
from tracking.database import (
    insert_entry,
    load_all_entries,
    link_bets_to_entry,
    get_entry_legs,
    resolve_entry_from_legs,
    delete_entry,
)
from pages.helpers.bet_tracker_data import (
    cached_load_all_bets,
    reload_bets,
    tracker_today_date,
)


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("🎰 Parlay / Entry Tracker")
    st.markdown("Track multi-leg entries as parlays. All legs must hit for a parlay WIN.")

    # Scope to current user so parlay counts match the user's own entries.
    try:
        from utils.user_session import get_current_user_email as _prl_get_ue
        _prl_ue = _prl_get_ue() or None
    except Exception:
        _prl_ue = st.session_state.get("_bet_tracker_user_email") or None

    # ── Create New Parlay ─────────────────────────────────────
    with st.expander("➕ Create New Parlay Entry", expanded=False):
        with st.form("create_parlay_form"):
            _pc = st.columns([1, 1, 1])
            with _pc[0]:
                _date = st.date_input("Entry Date", value=tracker_today_date(), key="parlay_date_input")
            with _pc[1]:
                _plat = st.selectbox("Platform", ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6", "Other"], key="parlay_platform_input")
            with _pc[2]:
                _fee = st.number_input("Entry Fee ($)", min_value=0.0, max_value=5000.0, value=10.0, step=5.0, key="parlay_fee_input")

            _type = st.selectbox("Entry Type", ["Parlay (All Must Hit)", "Flex Play (Some Can Miss)", "Power Play"], key="parlay_type_input")

            _avail = cached_load_all_bets()
            _unlinked = [b for b in _avail if not b.get("entry_id") and b.get("bet_date", "") == _date.isoformat()]
            _labels = {
                b.get("bet_id", b.get("id", idx)): (
                    f"#{b.get('bet_id', b.get('id', idx))} — {b.get('player_name', '?')} "
                    f"{b.get('direction', '')} {b.get('prop_line', '')} "
                    f"{str(b.get('stat_type', '')).title()} ({b.get('result') or 'Pending'})"
                )
                for idx, b in enumerate(_unlinked)
            }
            _legs = st.multiselect(
                "Select Legs (bets from same day)", list(_labels.keys()),
                format_func=lambda x: _labels.get(x, str(x)), key="parlay_legs_select",
            )
            _notes = st.text_input("Notes (optional)", key="parlay_notes_input")
            _submit = st.form_submit_button("🎰 Create Entry", type="primary")

        if _submit:
            if len(_legs) < 2:
                st.warning("⚠️ Select at least 2 legs.")
            else:
                _eid = insert_entry({
                    "entry_date": _date.isoformat(), "platform": _plat,
                    "entry_type": _type.split(" ")[0].lower(),
                    "entry_fee": _fee, "expected_value": 0.0,
                    "pick_count": len(_legs), "notes": _notes,
                    "user_email": _prl_ue,
                })
                if _eid:
                    link_bets_to_entry(_legs, _eid)
                    resolve_entry_from_legs(_eid)
                    reload_bets()
                    st.success(f"✅ Created entry #{_eid} with {len(_legs)} leg(s).")
                    st.rerun()
                else:
                    st.error("❌ Failed to create entry.")

    st.divider()

    _entries = load_all_entries(user_email=_prl_ue)
    if not _entries:
        st.info("📭 No parlay entries yet. Create one above or use **🧬 Entry Builder**.")
        return

    _total = len(_entries)
    _resolved = [e for e in _entries if e.get("result") in ("WIN", "LOSS", "EVEN")]
    _wins = sum(1 for e in _resolved if e.get("result") == "WIN")
    _losses = sum(1 for e in _resolved if e.get("result") == "LOSS")
    _pending = sum(1 for e in _entries if e.get("result") not in ("WIN", "LOSS", "EVEN"))
    _wr = round(_wins / max(_wins + _losses, 1) * 100, 1)
    _fees = sum(float(e.get("entry_fee") or 0) for e in _entries)
    _payouts = sum(float(e.get("payout") or 0) for e in _resolved if e.get("result") == "WIN")
    _pnl = _payouts - _fees

    st.markdown(
        get_summary_cards_html(
            total=_total, wins=_wins, losses=_losses,
            evens=sum(1 for e in _resolved if e.get("result") == "EVEN"),
            pending=_pending, win_rate=_wr,
        ),
        unsafe_allow_html=True,
    )

    _p1, _p2, _p3 = st.columns(3)
    _p1.metric("Total Wagered", f"${_fees:.2f}")
    _p2.metric("Total Payouts", f"${_payouts:.2f}")
    _p3.metric("Net P&L", f"${_pnl:+.2f}",
               delta="Profit" if _pnl > 0 else ("Break-even" if _pnl == 0 else "Loss"),
               delta_color="normal" if _pnl >= 0 else "inverse")

    st.divider()

    if st.button("🔄 Resolve All Entries", key="resolve_all_entries_btn", type="primary"):
        _cnt = 0
        for _e in _entries:
            if not _e.get("result"):
                if resolve_entry_from_legs(_e["entry_id"]):
                    _cnt += 1
        if _cnt > 0:
            st.success(f"✅ Resolved {_cnt} entries.")
            st.rerun()
        else:
            st.info("No entries resolved — legs may still be pending.")

    st.divider()

    for _entry in _entries:
        _eid = _entry.get("entry_id", "?")
        _edate = _entry.get("entry_date", "")
        _eplat = _entry.get("platform", "?")
        _etype = _entry.get("entry_type", "parlay")
        _efee = float(_entry.get("entry_fee") or 0)
        _epayout = _entry.get("payout")
        _eresult = _entry.get("result")
        _epicks = _entry.get("pick_count", 0)
        _enotes = _entry.get("notes", "")

        if _eresult == "WIN":
            _badge = '<span class="result-win">✅ WIN</span>'
            _border = "#00D559"
        elif _eresult == "LOSS":
            _badge = '<span class="result-loss">❌ LOSS</span>'
            _border = "#F24336"
        elif _eresult == "EVEN":
            _badge = '<span class="result-even">🔄 EVEN</span>'
            _border = "#A0AABE"
        else:
            _badge = '<span class="result-pending">⏳ PENDING</span>'
            _border = "#F9C62B"

        _payout_str = f"${_epayout:.2f}" if _epayout is not None else "—"
        _icon = "✅" if _eresult == "WIN" else "❌" if _eresult == "LOSS" else "⏳"

        with st.expander(
            f"{_icon} Entry #{_eid} — {_epicks} legs on {_eplat} ({_edate})"
            + (f" — {_eresult}" if _eresult else " — Pending"),
            expanded=not _eresult,
        ):
            st.markdown(
                f'<div style="border-left:4px solid {_border};background:rgba(13,17,23,0.85);'
                f'border-radius:10px;padding:14px 18px;margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><strong style="color:#e8f0ff;font-family:Inter,sans-serif;">'
                f'🎰 Entry #{_eid}</strong>'
                f'<span style="color:#6B7A9A;margin-left:10px;">{_eplat} · {_etype}</span></div>'
                f'{_badge}</div>'
                f'<div style="color:#6B7A9A;font-size:0.82rem;margin-top:6px;">'
                f'Fee: <strong>${_efee:.2f}</strong> · Payout: <strong>{_payout_str}</strong> · '
                f'{_epicks} leg(s)'
                + (f' · <em>{_enotes}</em>' if _enotes else '')
                + '</div></div>',
                unsafe_allow_html=True,
            )
            _legs_data = get_entry_legs(_eid)
            if _legs_data:
                st.markdown(f"**Legs ({len(_legs_data)}):**")
                for _leg in _legs_data:
                    _lr = _leg.get("result") or "Pending"
                    _li = {"WIN": "✅", "LOSS": "❌", "EVEN": "🔄"}.get(_lr, "⏳")
                    st.markdown(
                        f"&nbsp;&nbsp;{_li} **{_leg.get('player_name', '?')}** — "
                        f"{_leg.get('direction', '')} {_leg.get('prop_line', '')} "
                        f"{str(_leg.get('stat_type', '')).title()} ({_lr})"
                    )
            else:
                st.caption("No legs linked.")
            if st.button(f"🗑️ Delete Entry #{_eid}", key=f"del_entry_{_eid}"):
                _ok, _msg = delete_entry(_eid)
                if _ok:
                    st.success(_msg)
                    reload_bets()
                    st.rerun()
                else:
                    st.error(_msg)
