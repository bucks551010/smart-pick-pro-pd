# pages/18_📣_Social_Post_Studio.py
# Social Post Studio — compose & publish to X, Instagram, Facebook, Threads, TikTok
# Uses social_engine/ infrastructure already in the repo.

import streamlit as st
import sys
import os
from pathlib import Path
from datetime import date, timedelta

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
_SE_ROOT = _ROOT / "social_engine"
sys.path.insert(0, str(_SE_ROOT))

try:
    from dotenv import load_dotenv
    _env = _ROOT / ".env"
    if _env.exists():
        load_dotenv(_env)
    _se_env = _SE_ROOT / ".env"
    if _se_env.exists():
        load_dotenv(_se_env)
except ImportError:
    pass

st.set_page_config(
    page_title="Social Post Studio — Smart Pick Pro",
    page_icon="📣",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Admin-only gate ────────────────────────────────────────────
from utils.page_bootstrap import inject_theme_css, init_session_state
inject_theme_css()
from utils.auth_gate import require_login, is_admin_user
if not require_login():
    st.stop()
init_session_state()
if not is_admin_user():
    st.error("🔒 Access denied. This page is restricted to administrators.")
    st.stop()

try:
    from styles.theme import get_global_css
    st.markdown(get_global_css(), unsafe_allow_html=True)
except Exception:
    pass

# ── CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
  --sp-bg:     #070A13;
  --sp-panel:  #0F172A;
  --sp-accent: #00f0ff;
  --sp-green:  #00D559;
  --sp-red:    #F24336;
  --sp-gold:   #F9C62B;
  --sp-purple: #7C3AED;
  --sp-muted:  #8899BB;
}
.sp-hero {
  background: linear-gradient(135deg, #070A13 0%, #0a1628 100%);
  border: 1px solid rgba(0,240,255,0.10);
  border-top: 3px solid #7C3AED;
  border-radius: 12px;
  padding: 2rem 2.5rem 1.5rem;
  margin-bottom: 1.5rem;
}
.sp-eyebrow {
  font-size: 0.68rem; font-weight: 700; letter-spacing: 0.3em;
  color: #00f0ff; text-transform: uppercase; margin-bottom: 0.4rem;
}
.sp-headline {
  font-size: 2rem; font-weight: 900; color: #fff; margin-bottom: 0.3rem;
}
.sp-sub { font-size: 0.95rem; color: #8899BB; }
.sp-channel-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: #0F172A; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px; padding: 6px 14px;
  font-size: 0.8rem; font-weight: 700; color: #e2e8f0;
  margin: 4px;
}
.sp-channel-badge.configured { border-color: #00D559; color: #00D559; }
.sp-channel-badge.unconfigured { border-color: #F24336; color: #64748b; }
.sp-result-ok {
  background: rgba(0,213,89,0.08); border: 1px solid #00D559;
  border-radius: 10px; padding: 12px 16px; margin: 6px 0;
  color: #00D559; font-weight: 700; font-size: 0.9rem;
}
.sp-result-err {
  background: rgba(242,67,54,0.08); border: 1px solid #F24336;
  border-radius: 10px; padding: 12px 16px; margin: 6px 0;
  color: #F24336; font-weight: 700; font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ── Hero ───────────────────────────────────────────────────────
st.markdown("""
<div class="sp-hero">
  <div class="sp-eyebrow">SMARTPICKPRO &nbsp;·&nbsp; SOCIAL POST STUDIO &nbsp;·&nbsp; MULTI-CHANNEL</div>
  <div class="sp-headline">📣 Social Post Studio</div>
  <div class="sp-sub">Compose once. Post to X, Instagram, Facebook, Threads, and TikTok in one click.</div>
</div>
""", unsafe_allow_html=True)

# ── Load social_engine config ─────────────────────────────────
@st.cache_resource(show_spinner=False)
def _load_se_config():
    """Build a settings object directly from env vars — avoids any import collision."""
    import os
    from dataclasses import dataclass

    # Load social_engine/.env if it exists (supplements the main app .env)
    try:
        from dotenv import load_dotenv
        _se_env = _SE_ROOT / ".env"
        if _se_env.exists():
            load_dotenv(_se_env, override=False)
    except Exception:
        pass

    @dataclass(frozen=True)
    class _Settings:
        twitter_key:        str
        twitter_secret:     str
        twitter_token:      str
        twitter_token_sec:  str
        twitter_bearer:     str
        meta_token:         str
        meta_page_id:       str
        meta_ig_id:         str
        meta_threads_id:    str
        tiktok_token:       str
        tiktok_open_id:     str
        gemini_api_key:     str

    return _Settings(
        twitter_key=       os.getenv("TWITTER_API_KEY", ""),
        twitter_secret=    os.getenv("TWITTER_API_SECRET", ""),
        twitter_token=     os.getenv("TWITTER_ACCESS_TOKEN", ""),
        twitter_token_sec= os.getenv("TWITTER_ACCESS_SECRET", ""),
        twitter_bearer=    os.getenv("TWITTER_BEARER_TOKEN", ""),
        meta_token=        os.getenv("META_PAGE_ACCESS_TOKEN", ""),
        meta_page_id=      os.getenv("META_PAGE_ID", ""),
        meta_ig_id=        os.getenv("META_INSTAGRAM_BUSINESS_ID", ""),
        meta_threads_id=   os.getenv("META_THREADS_USER_ID", ""),
        tiktok_token=      os.getenv("TIKTOK_ACCESS_TOKEN", ""),
        tiktok_open_id=    os.getenv("TIKTOK_OPEN_ID", ""),
        gemini_api_key=    os.getenv("GEMINI_API_KEY", ""),
    )

cfg = _load_se_config()

# ── Channel Status ────────────────────────────────────────────
def _ch_status(name: str, check: bool) -> str:
    cls = "configured" if check else "unconfigured"
    icon = "✓" if check else "✗"
    return f'<span class="sp-channel-badge {cls}">{icon} {name}</span>'

_tw_ok  = all([cfg.twitter_key, cfg.twitter_secret, cfg.twitter_token, cfg.twitter_token_sec])
_fb_ok  = bool(cfg.meta_token and cfg.meta_page_id)
_ig_ok  = bool(cfg.meta_token and cfg.meta_ig_id)
_th_ok  = bool(cfg.meta_token and cfg.meta_threads_id)
_tt_ok  = bool(cfg.tiktok_token and cfg.tiktok_open_id)
_gem_ok = bool(cfg.gemini_api_key)

st.markdown(
    "<div style='margin-bottom:1.5rem'>"
    + _ch_status("X / Twitter", _tw_ok)
    + _ch_status("Facebook", _fb_ok)
    + _ch_status("Instagram", _ig_ok)
    + _ch_status("Threads", _th_ok)
    + _ch_status("TikTok", _tt_ok)
    + _ch_status("Gemini AI Copy", _gem_ok)
    + "</div>",
    unsafe_allow_html=True,
)

configured_channels = {
    "twitter":   _tw_ok,
    "facebook":  _fb_ok,
    "instagram": _ig_ok,
    "threads":   _th_ok,
    "tiktok":    _tt_ok,
}
any_configured = any(configured_channels.values())

if not any_configured:
    st.warning(
        "No social channels are configured yet. Add your API credentials to "
        "`social_engine/.env` (see `social_engine/CREDENTIALS.md` for setup instructions), "
        "then restart the app."
    )

# ── Tabs ──────────────────────────────────────────────────────
tab_compose, tab_picks, tab_results, tab_weekly, tab_creds = st.tabs([
    "✍️ Compose Post",
    "📊 Post Today's Picks",
    "🏆 Post Results Recap",
    "📅 Weekly Win Card",
    "🔑 Credentials Guide",
])

# ─────────────────────────────────────────────────────────────
# TAB 1 — COMPOSE POST
# ─────────────────────────────────────────────────────────────
with tab_compose:
    st.subheader("Compose & Post")
    st.caption("Write your post copy manually or use AI to generate it, then choose your channels.")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        post_text = st.text_area(
            "Post copy",
            height=160,
            placeholder=(
                "E.g. — 🔒 Anthony Edwards 26.5+ PTS — SAFE Score 87\n"
                "QME flagged this edge 3 hours before tip.\n"
                "Every win AND loss posted publicly. Receipts on file. 🧾\n\n"
                "#NBA #PrizePicks #SmartPickPro"
            ),
            key="compose_text",
        )
        char_left = 280 - len(post_text)
        st.caption(f"Twitter: {char_left} chars remaining {'✓' if char_left >= 0 else '⚠️ over limit'}")

        uploaded_image = st.file_uploader(
            "Attach image (optional)", type=["png", "jpg", "jpeg"], key="compose_img"
        )

        ai_help = st.expander("✨ Generate copy with AI (Gemini)")
        with ai_help:
            if not _gem_ok:
                st.warning("Set `GEMINI_API_KEY` in `social_engine/.env` to enable AI copy generation.")
            else:
                ai_asset = st.selectbox(
                    "Post type",
                    ["slate", "results", "weekly", "brand"],
                    key="ai_asset_type",
                )
                ai_context = st.text_area(
                    "Context (JSON or plain text)",
                    height=80,
                    key="ai_context",
                    placeholder='{"wins": 8, "losses": 2, "win_rate": 80.0}',
                )
                ai_tone = st.selectbox("Tone", ["analytical", "hype", "direct_cta"], key="ai_tone")
                if st.button("🤖 Generate Copy", key="ai_gen"):
                    with st.spinner("Asking Gemini…"):
                        try:
                            import sys as _sys, importlib
                            _orig = _sys.path[:]
                            _sys.path.insert(0, str(_SE_ROOT))
                            from core.llm_copy import generate_copy
                            import json as _json
                            try:
                                ctx = _json.loads(ai_context) if ai_context.strip() else {}
                            except Exception:
                                ctx = {"note": ai_context}
                            variants = generate_copy(ai_asset, ctx)
                            _sys.path[:] = _orig
                            st.session_state["compose_text"] = variants.for_platform("twitter", ai_tone)
                            st.success("Copy generated — it has been loaded into the text area above.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI generation failed: {e}")

    with col_right:
        st.markdown("**Choose channels**")
        sel_channels = []
        for ch, ok in configured_channels.items():
            label = f"{ch.capitalize()} {'✓' if ok else '(not configured)'}"
            if st.checkbox(label, value=ok, disabled=not ok, key=f"ch_{ch}"):
                sel_channels.append(ch)

        st.markdown("")
        if st.button("🚀 Send Post", type="primary", disabled=(not any_configured or not post_text.strip())):
            if not sel_channels:
                st.warning("Select at least one channel.")
            else:
                # Save uploaded image to a temp file if provided
                import tempfile
                img_path = None
                if uploaded_image:
                    suffix = Path(uploaded_image.name).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_image.getbuffer())
                        img_path = Path(tmp.name)
                else:
                    # Use a blank placeholder image so channels that require one still work
                    img_path = _ROOT / "assets" / "default_post_card.png"
                    if not img_path.exists():
                        img_path = None

                with st.spinner("Posting…"):
                    try:
                        _orig = sys.path[:]
                        sys.path.insert(0, str(_SE_ROOT))

                        from distribute.campaign import deploy_campaign
                        # We only have one image size here — map it to all slots
                        images_by_size = {}
                        if img_path and img_path.exists():
                            for sz in ("square", "landscape", "portrait"):
                                images_by_size[sz] = img_path

                        text_by_channel = {ch: post_text for ch in sel_channels}

                        results_list = deploy_campaign(
                            images_by_size=images_by_size,
                            text_by_channel=text_by_channel,
                            channels=sel_channels,
                        )
                        sys.path[:] = _orig

                        for r in results_list:
                            if r.ok:
                                link = f' — <a href="{r.url}" target="_blank">View post</a>' if r.url else ""
                                st.markdown(
                                    f'<div class="sp-result-ok">✓ {r.channel.upper()} — Posted successfully{link}</div>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    f'<div class="sp-result-err">✗ {r.channel.upper()} — {r.error}</div>',
                                    unsafe_allow_html=True,
                                )
                    except Exception as e:
                        st.error(f"Post failed: {e}")

# ─────────────────────────────────────────────────────────────
# TAB 2 — POST TODAY'S PICKS
# ─────────────────────────────────────────────────────────────
with tab_picks:
    st.subheader("Post Today's Picks")
    st.caption("Pull today's top picks from the database and share them as a pre-game slate post.")

    pick_date = st.date_input("Pick date", value=date.today(), key="picks_date")
    top_n = st.slider("How many picks to feature", 1, 10, 3, key="picks_n")
    picks_tone = st.selectbox("Copy tone", ["analytical", "hype", "direct_cta"], key="picks_tone")

    if st.button("🔍 Load Picks", key="load_picks"):
        try:
            from tracking.database import load_bets_by_date_range
            rows = load_bets_by_date_range(str(pick_date), str(pick_date))
            if not rows:
                # Try analysis picks table
                from tracking.database import load_analysis_picks_for_date
                rows = load_analysis_picks_for_date(str(pick_date))

            if rows:
                rows = sorted(rows, key=lambda r: float(r.get("confidence_score") or 0), reverse=True)[:top_n]
                st.session_state["slate_picks"] = rows
                st.success(f"Loaded {len(rows)} picks for {pick_date}")
            else:
                st.warning("No picks found for this date. Run the Quantum Analysis Matrix first.")
        except Exception as e:
            st.error(f"Could not load picks: {e}")

    if "slate_picks" in st.session_state and st.session_state["slate_picks"]:
        picks = st.session_state["slate_picks"]
        st.markdown("**Picks to feature:**")
        for p in picks:
            conf = p.get("confidence_score") or p.get("confidence") or "—"
            edge = p.get("edge_pct") or p.get("edge_percentage") or "—"
            plat = p.get("platform") or "—"
            line = p.get("prop_line") or p.get("line_value") or "—"
            dirn = (p.get("direction") or "").upper()
            stat = p.get("stat_type") or "—"
            st.markdown(
                f"**{p.get('player_name','?')}** · {dirn} {line} {stat} · "
                f"Conf: {conf} · Edge: {edge} · {plat}"
            )

        # Build copy
        _STAT_ABBR = {"Points":"PTS","Assists":"AST","Rebounds":"REB","3-Pointers Made":"3PM","Fantasy Score":"FPTS"}
        pick_lines = "\n".join(
            f"{'🔒' if str(p.get('tier','')).upper()=='PLATINUM' else '🔥' if str(p.get('tier','')).upper()=='GOLD' else '✅'} "
            f"{p.get('player_name','?')} "
            f"{(p.get('direction') or '').upper()} {p.get('prop_line') or p.get('line_value') or '?'} "
            f"{_STAT_ABBR.get(p.get('stat_type',''),p.get('stat_type',''))} "
            f"[{p.get('platform','?')}]"
            for p in picks
        )
        default_copy = (
            f"🔬 TODAY'S SLATE — {pick_date.strftime('%b %d').upper()}\n\n"
            f"{pick_lines}\n\n"
            f"All picks shown publicly. Every win AND loss posted. Receipts on file. 🧾\n"
            f"#NBA #PrizePicks #SmartPickPro #QME"
        )
        picks_copy = st.text_area("Post copy (edit as needed)", value=default_copy, height=200, key="picks_copy")

        sel_picks_channels = []
        st.markdown("**Post to:**")
        pcols = st.columns(5)
        ch_list = list(configured_channels.items())
        for i, (ch, ok) in enumerate(ch_list):
            with pcols[i % 5]:
                if st.checkbox(ch.capitalize(), value=ok, disabled=not ok, key=f"pch_{ch}"):
                    sel_picks_channels.append(ch)

        if st.button("🚀 Post Picks", type="primary", disabled=not any_configured, key="post_picks"):
            if not sel_picks_channels:
                st.warning("Select at least one channel.")
            else:
                with st.spinner("Posting…"):
                    try:
                        _orig = sys.path[:]
                        sys.path.insert(0, str(_SE_ROOT))
                        from distribute.campaign import deploy_campaign
                        text_by_channel = {ch: picks_copy for ch in sel_picks_channels}
                        results_list = deploy_campaign({}, text_by_channel, sel_picks_channels)
                        sys.path[:] = _orig
                        for r in results_list:
                            if r.ok:
                                link = f' — <a href="{r.url}" target="_blank">View</a>' if r.url else ""
                                st.markdown(f'<div class="sp-result-ok">✓ {r.channel.upper()} posted{link}</div>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div class="sp-result-err">✗ {r.channel.upper()} — {r.error}</div>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Post failed: {e}")

# ─────────────────────────────────────────────────────────────
# TAB 3 — POST RESULTS RECAP
# ─────────────────────────────────────────────────────────────
with tab_results:
    st.subheader("Post Results Recap")
    st.caption("Pull yesterday's (or any date's) W/L results and post a morning recap.")

    recap_date = st.date_input("Results date", value=date.today() - timedelta(days=1), key="recap_date")

    if st.button("📊 Load Results", key="load_results"):
        try:
            from tracking.database import load_bets_by_date_range
            rows = load_bets_by_date_range(str(recap_date), str(recap_date))
            resolved = [r for r in rows if (r.get("result") or "").upper() in ("WIN", "LOSS", "PUSH", "EVEN")]
            wins   = sum(1 for r in resolved if (r.get("result") or "").upper() == "WIN")
            losses = sum(1 for r in resolved if (r.get("result") or "").upper() == "LOSS")
            total  = len(rows)
            wr     = (wins / (wins + losses) * 100) if (wins + losses) else 0
            st.session_state["recap_data"] = {
                "date": str(recap_date), "wins": wins, "losses": losses,
                "total": total, "win_rate": wr, "rows": resolved,
            }
            st.success(f"Loaded results for {recap_date}: {wins}W / {losses}L ({wr:.0f}%)")
        except Exception as e:
            st.error(f"Could not load results: {e}")

    if "recap_data" in st.session_state:
        rd = st.session_state["recap_data"]
        wins, losses, wr = rd["wins"], rd["losses"], rd["win_rate"]

        win_lines = "\n".join(
            f"✅ {r.get('player_name','?')} "
            f"{(r.get('direction') or '').upper()} {r.get('prop_line') or r.get('line_value') or '?'} "
            f"{r.get('stat_type','')}"
            for r in rd["rows"]
            if (r.get("result") or "").upper() == "WIN"
        )[:800]

        default_recap = (
            f"🧾 RECEIPTS — {date.fromisoformat(rd['date']).strftime('%b %d').upper()}\n\n"
            f"✅ {wins}W / ❌ {losses}L — {wr:.0f}% WIN RATE\n\n"
            + (f"{win_lines}\n\n" if win_lines else "")
            + "Every win AND loss posted publicly. Zero hidden losses.\n"
            "#NBA #SmartPickPro #Receipts #PrizePicks"
        )
        recap_copy = st.text_area("Post copy", value=default_recap, height=220, key="recap_copy")

        sel_recap_channels = []
        rcols = st.columns(5)
        for i, (ch, ok) in enumerate(configured_channels.items()):
            with rcols[i % 5]:
                if st.checkbox(ch.capitalize(), value=ok, disabled=not ok, key=f"rch_{ch}"):
                    sel_recap_channels.append(ch)

        if st.button("🚀 Post Recap", type="primary", disabled=not any_configured, key="post_recap"):
            if not sel_recap_channels:
                st.warning("Select at least one channel.")
            else:
                with st.spinner("Posting…"):
                    try:
                        _orig = sys.path[:]
                        sys.path.insert(0, str(_SE_ROOT))
                        from distribute.campaign import deploy_campaign
                        text_by_channel = {ch: recap_copy for ch in sel_recap_channels}
                        results_list = deploy_campaign({}, text_by_channel, sel_recap_channels)
                        sys.path[:] = _orig
                        for r in results_list:
                            if r.ok:
                                link = f' — <a href="{r.url}" target="_blank">View</a>' if r.url else ""
                                st.markdown(f'<div class="sp-result-ok">✓ {r.channel.upper()} posted{link}</div>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div class="sp-result-err">✗ {r.channel.upper()} — {r.error}</div>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Post failed: {e}")

# ─────────────────────────────────────────────────────────────
# TAB 4 — WEEKLY WIN CARD
# ─────────────────────────────────────────────────────────────
with tab_weekly:
    st.subheader("Weekly Win Card Generator")
    st.caption("Generate a premium shareable HTML card showing this week's record — ready to post.")

    _today = date.today()
    _default_monday = _today - timedelta(days=_today.weekday())
    wcol1, wcol2 = st.columns([2, 3])

    with wcol1:
        week_start = st.date_input("Week start (Monday)", value=_default_monday, key="wc_start")
        week_end   = st.date_input("Week end", value=_today, key="wc_end")
        card_title = st.text_input("Card title", value="THIS WEEK'S RECEIPTS", key="wc_title")
        show_win_list = st.checkbox("Show individual wins", value=True, key="wc_list")
        max_wins_shown = st.slider("Max wins to list", 3, 15, 8, key="wc_max") if show_win_list else 0

        if st.button("🎨 Generate Win Card", type="primary", key="wc_gen"):
            try:
                from tracking.database import load_bets_by_date_range
                _wrows = load_bets_by_date_range(str(week_start), str(week_end))
                _wwins   = [r for r in _wrows if (r.get("result") or "").upper() == "WIN"]
                _wlosses = [r for r in _wrows if (r.get("result") or "").upper() == "LOSS"]
                _wpush   = [r for r in _wrows if (r.get("result") or "").upper() in ("PUSH","EVEN")]
                _wresolved = len(_wwins) + len(_wlosses)
                _wwr = (_wresolved and len(_wwins) / _wresolved * 100) or 0
                _ABBR = {"Points":"PTS","Assists":"AST","Rebounds":"REB","3-Pointers Made":"3PM",
                         "Fantasy Score":"FPTS","Blocks":"BLK","Steals":"STL","Turnovers":"TO",
                         "points":"PTS","assists":"AST","rebounds":"REB","fgm":"FGM",
                         "points_rebounds":"P+R","points_assists":"P+A","points_rebounds_assists":"P+R+A"}

                # Build win rows HTML
                win_rows_html = ""
                for _w in _wwins[:max_wins_shown]:
                    _pname = _w.get("player_name") or "?"
                    _stat  = _ABBR.get(_w.get("stat_type") or "", _w.get("stat_type") or "")
                    _dir   = (_w.get("direction") or "").upper()
                    _line  = _w.get("line_value") or _w.get("prop_line") or "?"
                    _plat  = (_w.get("platform") or "").upper()
                    _conf  = _w.get("confidence_score")
                    _conf_str = f'<span style="font-size:0.72rem;color:#64748b;margin-left:6px">{_conf:.0f}</span>' if _conf else ""
                    win_rows_html += f'''
  <div style="display:flex;align-items:center;gap:10px;padding:10px 16px;
    border-bottom:1px solid rgba(255,255,255,0.04)">
    <span style="color:#00D559;font-size:1.1rem;flex-shrink:0">✓</span>
    <div style="flex:1;min-width:0">
      <div style="font-weight:800;font-size:0.95rem;color:#f1f5f9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_pname}</div>
      <div style="font-size:0.75rem;color:#64748b">{_dir} {_line} {_stat}</div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <span style="font-size:0.65rem;font-weight:700;letter-spacing:0.1em;
        background:rgba(0,240,255,0.07);border:1px solid rgba(0,240,255,0.15);
        border-radius:4px;padding:2px 7px;color:#00f0ff">{_plat}</span>
      {_conf_str}
    </div>
  </div>'''
                if len(_wwins) > max_wins_shown:
                    _extra = len(_wwins) - max_wins_shown
                    win_rows_html += f'<div style="text-align:center;padding:10px;color:#475569;font-size:0.75rem">+ {_extra} more wins</div>'

                # Win rate color
                _wr_clr = "#00D559" if _wwr >= 65 else "#F9C62B" if _wwr >= 50 else "#F24336"
                _wr_bar = min(_wwr, 100)

                # Date range label
                _dr_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}".upper()

                # Build full card HTML
                card_html = f'''<div style="
  font-family:'Segoe UI',system-ui,sans-serif;
  background:linear-gradient(160deg,#060B18 0%,#0A1428 50%,#060B18 100%);
  border:1px solid rgba(0,213,89,0.20);
  border-top:4px solid #00D559;
  border-radius:16px;
  max-width:540px;
  overflow:hidden;
  box-shadow:0 20px 60px rgba(0,0,0,0.6),0 0 40px rgba(0,213,89,0.08);
">
  <!-- Header -->
  <div style="padding:24px 24px 16px;position:relative;overflow:hidden">
    <div style="position:absolute;top:-30px;right:-30px;width:160px;height:160px;
      background:radial-gradient(circle,rgba(0,213,89,0.12) 0%,transparent 70%)"></div>
    <div style="font-size:0.62rem;font-weight:800;letter-spacing:0.35em;
      color:#00f0ff;text-transform:uppercase;margin-bottom:6px">
      SmartPickPro &nbsp;·&nbsp; {_dr_label}
    </div>
    <div style="font-size:2.2rem;font-weight:900;color:#ffffff;letter-spacing:0.02em;line-height:1">
      {card_title}
    </div>
    <div style="font-size:0.78rem;color:#475569;margin-top:4px">
      Quantum Matrix Engine™ 5.6 &nbsp;·&nbsp; Every win AND loss posted publicly
    </div>
  </div>

  <!-- Big stats row -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1px;
    background:rgba(255,255,255,0.04);border-top:1px solid rgba(255,255,255,0.06);
    border-bottom:1px solid rgba(255,255,255,0.06)">
    <div style="background:#070C1A;padding:18px 16px;text-align:center">
      <div style="font-size:2.8rem;font-weight:900;color:#00D559;
        text-shadow:0 0 30px rgba(0,213,89,0.5);line-height:1">{len(_wwins)}</div>
      <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.2em;
        color:#475569;text-transform:uppercase;margin-top:4px">WINS</div>
    </div>
    <div style="background:#070C1A;padding:18px 16px;text-align:center">
      <div style="font-size:2.8rem;font-weight:900;color:#F24336;line-height:1">{len(_wlosses)}</div>
      <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.2em;
        color:#475569;text-transform:uppercase;margin-top:4px">LOSSES</div>
    </div>
    <div style="background:#070C1A;padding:18px 16px;text-align:center">
      <div style="font-size:2.8rem;font-weight:900;color:{_wr_clr};
        text-shadow:0 0 20px {_wr_clr}66;line-height:1">{_wwr:.0f}%</div>
      <div style="font-size:0.62rem;font-weight:700;letter-spacing:0.2em;
        color:#475569;text-transform:uppercase;margin-top:4px">WIN RATE</div>
    </div>
  </div>

  <!-- Win rate bar -->
  <div style="padding:0 24px;margin-top:16px">
    <div style="display:flex;justify-content:space-between;margin-bottom:6px">
      <span style="font-size:0.65rem;font-weight:700;letter-spacing:0.15em;
        color:#475569;text-transform:uppercase">Win Rate</span>
      <span style="font-size:0.65rem;font-weight:700;color:{_wr_clr}">{_wwr:.1f}%</span>
    </div>
    <div style="height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden">
      <div style="width:{_wr_bar:.0f}%;height:100%;background:{_wr_clr};
        border-radius:3px;box-shadow:0 0 12px {_wr_clr}88;
        transition:width 1s ease"></div>
    </div>
  </div>

  <!-- Win list -->
  {'<div style="margin-top:16px;border-top:1px solid rgba(255,255,255,0.06)">' + win_rows_html + '</div>' if show_win_list and win_rows_html else ""}

  <!-- Footer -->
  <div style="padding:14px 24px;border-top:1px solid rgba(255,255,255,0.05);
    display:flex;align-items:center;justify-content:space-between;margin-top:8px">
    <div style="font-size:0.65rem;font-weight:800;letter-spacing:0.15em;color:#1e3a5f">
      smartpickpro.ai
    </div>
    <div style="font-size:0.6rem;color:#1e3a5f;text-align:right">
      21+ · Not gambling advice · Play responsibly
    </div>
  </div>
</div>'''

                st.session_state["wc_html"] = card_html
                st.session_state["wc_stats"] = {
                    "wins": len(_wwins), "losses": len(_wlosses),
                    "win_rate": _wwr, "resolved": _wresolved,
                    "week_start": str(week_start), "week_end": str(week_end),
                }
            except Exception as e:
                st.error(f"Could not load data: {e}")

    with wcol2:
        if "wc_html" in st.session_state:
            st.markdown("**Preview:**")
            st.components.v1.html(
                f'<div style="background:#030508;padding:24px;min-height:400px">'
                f'{st.session_state["wc_html"]}'
                f'</div>',
                height=620,
                scrolling=True,
            )

            # Download button
            st.download_button(
                label="⬇️ Download HTML Card",
                data=f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>SmartPickPro Weekly Win Card</title>
<style>body{{margin:0;background:#030508;display:flex;justify-content:center;align-items:flex-start;padding:40px;min-height:100vh}}</style>
</head><body>{st.session_state["wc_html"]}</body></html>''',
                file_name=f"smartpickpro_weekly_{st.session_state['wc_stats']['week_start']}.html",
                mime="text/html",
                key="wc_download",
            )

            # Post copy for social
            st.markdown("**Ready-to-post caption:**")
            _s = st.session_state["wc_stats"]
            _caption = (
                f"📊 {card_title}\n\n"
                f"✅ {_s['wins']}W / ❌ {_s['losses']}L — {_s['win_rate']:.0f}% WIN RATE\n"
                f"Week of {date.fromisoformat(_s['week_start']).strftime('%b %d')} – {date.fromisoformat(_s['week_end']).strftime('%b %d')}\n\n"
                f"Every win AND loss posted publicly. Zero hidden losses. Receipts always on file. 🧾\n"
                f"#NBA #SmartPickPro #Receipts #PrizePicks #WeeklyRecord"
            )
            _caption_edit = st.text_area("Caption (edit as needed)", value=_caption, height=160, key="wc_caption")

            # Quick post
            st.markdown("**Post to:**")
            _wc_channels = []
            _wc_cols = st.columns(5)
            for _i, (_ch, _ok) in enumerate(configured_channels.items()):
                with _wc_cols[_i % 5]:
                    if st.checkbox(_ch.capitalize(), value=_ok, disabled=not _ok, key=f"wcc_{_ch}"):
                        _wc_channels.append(_ch)

            if st.button("🚀 Post Weekly Card", type="primary", disabled=not any_configured, key="wc_post"):
                if not _wc_channels:
                    st.warning("Select at least one channel.")
                else:
                    with st.spinner("Posting…"):
                        try:
                            _orig = sys.path[:]
                            sys.path.insert(0, str(_SE_ROOT))
                            from distribute.campaign import deploy_campaign
                            _tbch = {ch: _caption_edit for ch in _wc_channels}
                            _res = deploy_campaign({}, _tbch, _wc_channels)
                            sys.path[:] = _orig
                            for _r in _res:
                                if _r.ok:
                                    _lnk = f' — <a href="{_r.url}" target="_blank">View</a>' if _r.url else ""
                                    st.markdown(f'<div class="sp-result-ok">✓ {_r.channel.upper()} posted{_lnk}</div>', unsafe_allow_html=True)
                                else:
                                    st.markdown(f'<div class="sp-result-err">✗ {_r.channel.upper()} — {_r.error}</div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Post failed: {e}")
        else:
            st.markdown(
                '<div style="background:#0F172A;border:1px solid rgba(0,213,89,0.12);'
                'border-radius:12px;padding:48px;text-align:center;color:#334155">'
                '<div style="font-size:2.5rem;margin-bottom:12px">📅</div>'
                '<div style="font-size:0.85rem;font-weight:600">Click "Generate Win Card" to preview</div>'
                '</div>',
                unsafe_allow_html=True,
            )

# ─────────────────────────────────────────────────────────────
# TAB 5 — CREDENTIALS GUIDE
# ─────────────────────────────────────────────────────────────
with tab_creds:
    st.subheader("Credentials Setup")
    st.caption(
        "Create `social_engine/.env` (copy from `social_engine/.env.example`) "
        "and fill in the keys below. The app reads them on each restart."
    )

    with st.expander("🐦 X / Twitter — Basic tier ($100/mo for image posts)", expanded=not _tw_ok):
        st.markdown("""
1. Go to [developer.x.com](https://developer.x.com/en/portal/dashboard)
2. Create a Project → App → set permissions to **Read and write**
3. Generate **API Key**, **API Key Secret**, **Access Token**, **Access Token Secret**, **Bearer Token**

Add to `social_engine/.env`:
```
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_BEARER_TOKEN=...
```
        """)

    with st.expander("📘 Facebook / Instagram / Threads — Meta Graph API", expanded=not _fb_ok):
        st.markdown("""
1. Create a Facebook App at [developers.facebook.com](https://developers.facebook.com)
2. Add **Facebook Login for Business** + **Instagram Graph API** + **Threads API**
3. Generate a **Page Access Token** for your Facebook Page
4. Get your **Page ID**, **Instagram Business Account ID**, **Threads User ID**

Add to `social_engine/.env`:
```
META_PAGE_ACCESS_TOKEN=...
META_PAGE_ID=...
META_INSTAGRAM_BUSINESS_ID=...
META_THREADS_USER_ID=...
```
        """)

    with st.expander("🎵 TikTok — Content Posting API", expanded=not _tt_ok):
        st.markdown("""
1. Register at [developers.tiktok.com](https://developers.tiktok.com/)
2. Create an app → request **Content Posting API** access
3. Complete OAuth to get an **Access Token** and your **Open ID**

Add to `social_engine/.env`:
```
TIKTOK_ACCESS_TOKEN=...
TIKTOK_OPEN_ID=...
```
        """)

    with st.expander("🤖 Gemini AI Copy — Free (1500 requests/day)", expanded=not _gem_ok):
        st.markdown("""
1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key** — free tier is plenty for daily posts

Add to `social_engine/.env`:
```
GEMINI_API_KEY=AIzaSy...
```
        """)

    with st.expander("🖼️ Public image hosting (required for Instagram/Threads/TikTok)"):
        st.markdown("""
Instagram, Threads, and TikTok require a **public image URL** rather than a file upload.

Set this in `social_engine/.env`:
```
PUBLIC_ASSET_BASE_URL=https://your-app.up.railway.app/static
```
Twitter and Facebook accept direct file uploads and work without this.
        """)

    st.info(
        "After updating `.env`, restart the Streamlit app for credentials to take effect. "
        "Full setup guide: `social_engine/CREDENTIALS.md`"
    )
