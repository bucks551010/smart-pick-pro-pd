"""Joseph's Bets tab for Bet Tracker."""
import streamlit as st
from styles.theme import get_bet_card_css, get_bet_card_html
from pages.helpers.bet_tracker_data import (
    cached_load_all_bets,
    is_joseph_bet,
    in_bet_date_window,
    render_bet_cards_chunked,
    RESULT_EMOJI,
)
import logging

_logger = logging.getLogger(__name__)


def render(platform_selections, player_search, date_range, direction_filter):
    st.subheader("🎙️ Joseph M. Smith's Bets — Tracker Subset")
    st.markdown(
        "Track all bets placed by Joseph M. Smith — filtered from your bet database. "
        "Joseph's picks are auto-logged from **The Studio** page."
    )

    _col1, _col2 = st.columns([2, 5])
    with _col1:
        _scope = st.selectbox(
            "Joseph Scope",
            ["Today", "Last 7 Days", "Last 30 Days", "All Time"],
            index=0, key="joseph_scope_filter",
        )
    with _col2:
        st.caption("Joseph tab only includes bets tagged as Joseph via source/platform/notes.")

    try:
        _all = cached_load_all_bets()
        _joseph = [b for b in _all if is_joseph_bet(b)]
        _joseph = [b for b in _joseph if in_bet_date_window(b, _scope, "bet_date")]

        if _joseph:
            _total = len(_joseph)
            _wins = sum(1 for b in _joseph if str(b.get("result", "")).upper() == "WIN")
            _losses = sum(1 for b in _joseph if str(b.get("result", "")).upper() == "LOSS")
            _pending = sum(1 for b in _joseph if not b.get("result") or str(b.get("result", "")).upper() not in ("WIN", "LOSS", "EVEN"))
            _wr = _wins / max(_wins + _losses, 1)

            _m1, _m2, _m3, _m4 = st.columns(4)
            _m1.metric("Total Bets", _total)
            _m2.metric("Win Rate", f"{_wr:.1%}" if (_wins + _losses) > 0 else "—")
            _m3.metric("Wins / Losses", f"{_wins}W / {_losses}L")
            _m4.metric("Pending", _pending)
            st.caption("Joseph counts only Joseph-tagged tracker bets. It is a subset of Health.")

            st.markdown("---")
            st.markdown(get_bet_card_css(), unsafe_allow_html=True)

            _cards = []
            for _jb in sorted(_joseph, key=lambda x: x.get("bet_date", ""), reverse=True)[:30]:
                _card = get_bet_card_html(_jb)
                if _card:
                    _cards.append(_card)
                else:
                    _name = _jb.get("player_name", "Unknown")
                    _stat = _jb.get("stat_type", "")
                    _dir = _jb.get("direction", "")
                    _line = _jb.get("prop_line", "")
                    _result = _jb.get("result", "pending")
                    _emoji = RESULT_EMOJI.get(str(_result).upper() if _result else None, "⏳")
                    st.markdown(
                        f"**{_name}** — {_stat} {_dir} {_line} | Result: {_emoji} {_result or 'pending'}"
                    )
            if _cards:
                render_bet_cards_chunked(
                    sorted(_joseph, key=lambda x: x.get("bet_date", ""), reverse=True)[:30]
                )
        else:
            st.info(
                "🎙️ No Joseph M. Smith bets found yet.\n\n"
                "Go to **🎙️ The Studio** and run Neural Analysis — "
                "Joseph's SMASH and LEAN picks will be auto-logged here."
            )
    except Exception as _err:
        _logger.warning("Failed to load Joseph's bets: %s", _err)
        st.warning("Could not load Joseph's bet history.")
