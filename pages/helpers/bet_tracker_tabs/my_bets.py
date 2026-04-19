"""My Bets tab for Bet Tracker."""
import json
import streamlit as st
from styles.theme import get_summary_cards_html, get_bet_card_html
from tracking.database import (
    get_bets_summary,
    load_bets_page,
    export_bets_csv,
    delete_bet,
    update_bet_fields,
)
from tracking.bet_tracker import record_bet_result
from pages.helpers.bet_tracker_data import (
    reload_bets,
    tracker_today_iso,
    platform_selection_to_terms,
    render_bet_cards_chunked,
)


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("📋 My Bets")

    filter_choice = st.radio(
        "Filter bets",
        ["All", "Wins Only", "Losses Only", "Pending", "Platinum", "Gold", "Silver", "Bronze"],
        horizontal=True, label_visibility="collapsed", key="my_bets_filter_radio",
    )

    _bt_filter = st.multiselect(
        "Bet Classification",
        ["Standard", "Goblin", "Normal", "Fantasy"],
        default=[], key="bets_bet_type_filter",
    )

    _platform_terms = platform_selection_to_terms(platform_selections)

    _start_date = None
    _end_date = None
    if date_range and len(date_range) == 2:
        _start_date = date_range[0].isoformat()
        _end_date = date_range[1].isoformat()

    _result_filter = None
    _tier_filter = None
    if filter_choice == "Wins Only":
        _result_filter = "WIN"
    elif filter_choice == "Losses Only":
        _result_filter = "LOSS"
    elif filter_choice == "Pending":
        _result_filter = "PENDING"
    elif filter_choice in ("Platinum", "Gold", "Silver", "Bronze"):
        _tier_filter = filter_choice

    _bt_values = [bt.lower() for bt in _bt_filter] if _bt_filter else None

    _args = {
        "exclude_linked": True,
        "player_search": player_search.strip() if player_search else None,
        "start_date": _start_date,
        "end_date": _end_date,
        "direction": None if direction_filter == "All" else direction_filter,
        "platform_terms": _platform_terms,
        "result_filter": _result_filter,
        "tier_filter": _tier_filter,
        "bet_types": _bt_values,
    }

    _summary = get_bets_summary(**_args)
    _w = _summary.get("wins", 0)
    _l = _summary.get("losses", 0)
    _p = _summary.get("evens", 0)
    _pend = _summary.get("pending", 0)
    _wr = round(_w / max(_w + _l, 1) * 100, 1)

    st.markdown(
        get_summary_cards_html(total=_summary.get("total", 0), wins=_w, losses=_l, evens=_p, pending=_pend, win_rate=_wr),
        unsafe_allow_html=True,
    )

    if _summary.get("total", 0) == 0:
        st.info("No bets match the current filters.")
        return

    _pc1, _pc2, _pc3 = st.columns([1, 1, 3])
    with _pc1:
        _page_size = st.selectbox("Rows per page", [25, 50, 100, 200], index=1, key="my_bets_page_size")

    _sig = json.dumps({
        "player": _args["player_search"], "start": _start_date, "end": _end_date,
        "dir": _args["direction"], "platform": _platform_terms,
        "result": _result_filter, "tier": _tier_filter, "types": _bt_values,
        "page_size": _page_size,
    }, sort_keys=True)

    if st.session_state.get("my_bets_filter_signature") != _sig:
        st.session_state["my_bets_page"] = 1
        st.session_state["my_bets_filter_signature"] = _sig

    _total_rows = int(_summary.get("total", 0))
    _total_pages = max(1, (_total_rows + _page_size - 1) // _page_size)
    _cur = max(1, min(int(st.session_state.get("my_bets_page", 1)), _total_pages))
    st.session_state["my_bets_page"] = _cur

    with _pc2:
        _new = st.number_input("Page", min_value=1, max_value=_total_pages, value=_cur, step=1, key="my_bets_page_input")
        if int(_new) != _cur:
            st.session_state["my_bets_page"] = int(_new)
            st.rerun()

    _offset = (_cur - 1) * _page_size
    filtered_bets = load_bets_page(limit=_page_size, offset=_offset, **_args)

    with _pc3:
        _s = _offset + 1 if _total_rows > 0 else 0
        _e = min(_offset + len(filtered_bets), _total_rows)
        st.markdown(f"**Showing {_s}-{_e} of {_total_rows} bet(s)** (page {_cur}/{_total_pages})")

    # Export / Edit / Delete
    _ec, _edc, _dc = st.columns(3)
    with _ec:
        if filtered_bets:
            st.download_button(
                "📥 Export Page to CSV",
                data=export_bets_csv(filtered_bets),
                file_name=f"smartai_bets_page_{_cur}_{tracker_today_iso()}.csv",
                mime="text/csv", key="export_my_bets_csv",
            )

    _labels = {
        b.get("id", b.get("bet_id", idx)): (
            f"#{b.get('id', b.get('bet_id', idx))} — {b.get('player_name', '?')} "
            f"{b.get('direction', '')} {b.get('prop_line', '')} {str(b.get('stat_type', '')).title()}"
        )
        for idx, b in enumerate(filtered_bets)
    }

    with _edc:
        if _labels:
            with st.expander("✏️ Edit a Bet", expanded=False):
                with st.form("edit_bet_form_bt"):
                    _eid = st.selectbox("Select Bet", list(_labels.keys()), format_func=lambda x: _labels[x], key="edit_bet_select")
                    _el = st.number_input("New Line", min_value=0.0, max_value=200.0, value=0.0, step=0.5, key="edit_line")
                    _ed = st.selectbox("New Direction", ["—", "OVER", "UNDER"], key="edit_dir")
                    _ep = st.selectbox("New Platform", ["—", "PrizePicks", "Underdog Fantasy", "DraftKings Pick6"], key="edit_plat")
                    _en = st.text_input("New Notes", key="edit_notes")
                    _submit = st.form_submit_button("💾 Save Changes", type="primary")
                if _submit and _eid:
                    _updates = {}
                    if _el > 0:
                        _updates["prop_line"] = _el
                    if _ed != "—":
                        _updates["direction"] = _ed
                    if _ep != "—":
                        _updates["platform"] = _ep
                    if _en.strip():
                        _updates["notes"] = _en.strip()
                    if _updates:
                        _ok, _msg = update_bet_fields(_eid, _updates)
                        if _ok:
                            st.success(f"✅ {_msg}")
                            reload_bets()
                            st.rerun()
                        else:
                            st.error(f"❌ {_msg}")
                    else:
                        st.warning("No fields to update.")

    with _dc:
        if _labels:
            with st.expander("🗑️ Delete a Bet", expanded=False):
                with st.form("delete_bet_form_bt"):
                    _did = st.selectbox("Select Bet", list(_labels.keys()), format_func=lambda x: _labels[x], key="delete_bet_select")
                    st.warning("⚠️ This action cannot be undone.")
                    _del = st.form_submit_button("🗑️ Confirm Delete", type="primary")
                if _del and _did:
                    _ok, _msg = delete_bet(_did)
                    if _ok:
                        st.success(f"✅ {_msg}")
                        reload_bets()
                        st.rerun()
                    else:
                        st.error(f"❌ {_msg}")

    st.divider()

    # Mark a Result
    pending_bets = [b for b in filtered_bets if not b.get("result")]
    if pending_bets:
        with st.expander("✅ Mark a Result", expanded=False):
            _pl = {
                b.get("id", b.get("bet_id", idx)): (
                    f"#{b.get('id', b.get('bet_id', idx))} — {b.get('player_name', '?')} "
                    f"{b.get('direction', '')} {b.get('prop_line', '')} {str(b.get('stat_type', '')).title()}"
                )
                for idx, b in enumerate(pending_bets)
            }
            with st.form("mark_result_form_bt"):
                _sel = st.selectbox("Select Pending Bet", list(_pl.keys()), format_func=lambda x: _pl[x])
                _res = st.radio("Result", ["WIN", "LOSS", "EVEN"], horizontal=True)
                _act = st.number_input("Actual Stat Value", min_value=0.0, max_value=200.0, value=0.0, step=0.5)
                _sub = st.form_submit_button("💾 Save Result", type="primary")
            if _sub:
                ok, msg = record_bet_result(_sel, _res, _act)
                if ok:
                    st.success(f"✅ {msg}")
                    reload_bets()
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    # ── Bet Cards Grid by date ────────────────────────────────
    if not filtered_bets:
        st.info(f"No bets match the '{filter_choice}' filter on this page.")
        return

    _today_str = tracker_today_iso()
    _today_bets = [b for b in filtered_bets if b.get("bet_date", "") == _today_str]
    _past_by_date: dict = {}
    for _b in filtered_bets:
        _bd = _b.get("bet_date", "Unknown")
        if _bd != _today_str:
            _past_by_date.setdefault(_bd, []).append(_b)

    if _today_bets:
        st.subheader("📅 Today's Bets")
        render_bet_cards_chunked(_today_bets)

    for _pd in sorted(_past_by_date.keys(), reverse=True):
        _bets = _past_by_date[_pd]
        _pw = sum(1 for b in _bets if b.get("result") == "WIN")
        _pl2 = sum(1 for b in _bets if b.get("result") == "LOSS")
        _pp = sum(1 for b in _bets if not b.get("result"))
        _label = (
            f"📅 {_pd} — {len(_bets)} bet(s) · ✅{_pw} ❌{_pl2}"
            + (f" ⏳{_pp} pending" if _pp else "")
        )
        with st.expander(_label, expanded=False):
            render_bet_cards_chunked(_bets)
