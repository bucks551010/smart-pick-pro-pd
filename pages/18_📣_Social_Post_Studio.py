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
    try:
        import importlib.util, sys as _sys
        _spec = importlib.util.spec_from_file_location(
            "_se_config", str(_SE_ROOT / "config.py")
        )
        _mod = importlib.util.module_from_spec(_spec)
        # Give the module its own namespace so dotenv loads from social_engine/.env
        _spec.loader.exec_module(_mod)
        return _mod.SETTINGS
    except Exception as e:
        st.error(f"Could not load social_engine config: {e}")
        return None

cfg = _load_se_config()

if cfg is None:
    st.error("Could not load social_engine config. Check that `social_engine/config.py` is accessible.")
    st.stop()

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
tab_compose, tab_picks, tab_results, tab_creds = st.tabs([
    "✍️ Compose Post",
    "📊 Post Today's Picks",
    "🏆 Post Results Recap",
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
# TAB 4 — CREDENTIALS GUIDE
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
