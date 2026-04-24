"""SmartPickPro Social Engine — Streamlit Control Room.

Run:  streamlit run app.py
"""
from __future__ import annotations
import logging
from datetime import date

import streamlit as st

from config import BRAND, OUTPUT_SIZES, SETTINGS
from core import data_source as ds
from core.llm_copy import generate_copy
from distribute.campaign import deploy_campaign
from render.headless import render_to_images
from render.jinja_engine import render_html

logging.basicConfig(level=logging.INFO)

# ── Page config + minimal theme ──────────────────────────────
st.set_page_config(page_title="Social Engine", page_icon="📣", layout="wide")
st.markdown(f"""
<style>
  html, body, [data-testid="stApp"] {{ background:{BRAND['bg']}!important; color:{BRAND['text']}!important; }}
  .block-container {{ padding-top: 2rem; }}
  h1, h2, h3 {{ color: #fff; }}
  div[data-testid="stMetric"] {{ background:{BRAND['panel']}; padding:1rem; border-radius:.6rem;
                                  border:1px solid rgba(0,240,255,.2); }}
</style>
""", unsafe_allow_html=True)

st.title("📣 SmartPickPro — Social Engine")
st.caption("Render → Generate copy → Deploy. Same pipeline used by the scheduler & webhook.")

# ── Sidebar: campaign type + filters ─────────────────────────
with st.sidebar:
    st.header("Campaign Builder")
    asset = st.selectbox(
        "Asset type",
        ["The Slate", "The Results", "Brand / CTA"],
        index=0,
    )

    if asset == "The Slate":
        slate_kind = st.selectbox(
            "Slate variant",
            ["Top 3", "QEG (edge ≥ threshold)", "Platform: PrizePicks",
             "Platform: Underdog Fantasy", "Platform: DraftKings Pick6", "Full slate"],
        )
        if slate_kind == "QEG (edge ≥ threshold)":
            edge_min = st.slider("Edge threshold (%)", 1.0, 20.0, 5.0, 0.5)
        else:
            edge_min = 0.0
        n_picks = st.slider("Max picks shown", 1, 9, 6)
        pick_date = st.date_input("Date", value=date.today())

    elif asset == "The Results":
        result_date = st.date_input("Results date", value=date.today())
        n_picks = st.slider("Bets shown on graphic", 1, 8, 6)

    else:  # Brand / CTA
        cta_headline = st.text_input("Headline", "THE EDGE ISN'T LUCK. IT'S MATH.")
        cta_sub      = st.text_input("Sub-headline",
            "1,000 Quantum simulations per pick. Zero black boxes. Free trial.")
        cta_button   = st.text_input("Button text", "→ START FREE")

    st.divider()
    st.subheader("Channels")
    channels = []
    for ch, label in [("twitter","X / Twitter"), ("facebook","Facebook"),
                      ("instagram","Instagram"), ("threads","Threads"), ("tiktok","TikTok")]:
        if st.checkbox(label, value=True, key=f"ch_{ch}"):
            channels.append(ch)

    st.divider()
    st.subheader("Sizes to render")
    sizes = []
    for sz in OUTPUT_SIZES:
        if st.checkbox(sz.title(), value=True, key=f"sz_{sz}"):
            sizes.append(sz)


# ── Main: pull data + render preview ─────────────────────────
col_left, col_right = st.columns([1, 1])

# Build context based on asset choice
ctx: dict = {}
template_name = ""
utm_source = ""
utm_campaign = ""
copy_payload: dict = {}
copy_asset_type = ""

if asset == "The Slate":
    if slate_kind == "Top 3":
        picks = ds.get_top_n_picks(3, pick_date)
        title, sub = "Tonight's Top 3", "Highest-confidence quant edges"
    elif slate_kind == "QEG (edge ≥ threshold)":
        picks = ds.get_qeg_picks(edge_min, pick_date)
        title, sub = "Quantum Edge Gap", f"Edge ≥ {edge_min:.1f}%"
    elif slate_kind.startswith("Platform: "):
        plat = slate_kind.split(": ", 1)[1]
        picks = ds.get_platform_picks(plat, pick_date)
        title, sub = f"{plat} Slate", "Tonight's edge picks"
    else:
        picks = ds.get_slate_for_date(pick_date)
        title, sub = "Tonight's Full Slate", f"{len(picks)} edge plays"

    picks = picks[:n_picks]
    ctx = {
        "eyebrow": "TONIGHT'S SLATE", "title": title, "subtitle": sub,
        "picks": picks, "cols": 2 if len(picks) > 1 else 1,
    }
    template_name = "slate.html"
    utm_source, utm_campaign = "manual_slate", f"manual_slate_{pick_date:%Y%m%d}"
    copy_asset_type = "slate"
    copy_payload = {"picks": picks, "filter": slate_kind}

elif asset == "The Results":
    summary = ds.get_results_for_date(result_date)
    ctx = {
        "title": f"{summary.wins}-{summary.losses} on {summary.bet_date}",
        "subtitle": "Receipts always shown.",
        "wins": summary.wins, "losses": summary.losses,
        "win_rate": summary.win_rate, "roi_pct": summary.roi_pct,
        "picks": summary.bets[:n_picks], "cols": 2,
    }
    template_name = "results.html"
    utm_source, utm_campaign = "manual_recap", f"manual_recap_{summary.bet_date}"
    copy_asset_type = "results"
    copy_payload = {
        "wins": summary.wins, "losses": summary.losses,
        "win_rate": summary.win_rate, "roi_pct": summary.roi_pct,
    }

else:  # Brand / CTA
    ctx = {
        "title": "Quant NBA Analytics",
        "headline": cta_headline, "subheadline": cta_sub,
        "button_text": cta_button,
    }
    template_name = "brand_cta.html"
    utm_source, utm_campaign = "manual_brand", f"manual_brand_{date.today():%Y%m%d}"
    copy_asset_type = "brand"
    copy_payload = {"product": "SmartPickPro NBA"}


# ── LEFT: HTML preview ───────────────────────────────────────
with col_left:
    st.subheader("📄 Preview")
    try:
        html = render_html(template_name, ctx, utm_source=utm_source, utm_campaign=utm_campaign)
        # Show iframe-style preview at 540x540 (scaled square)
        st.components.v1.html(html, height=560, scrolling=False)
    except Exception as e:
        st.error(f"Template render failed: {e}")
        html = None


# ── RIGHT: LLM copy + actions ────────────────────────────────
with col_right:
    st.subheader("🧠 AI Copy")

    if "copy_cache" not in st.session_state:
        st.session_state["copy_cache"] = None

    if st.button("✨ Generate copy variants"):
        with st.spinner("Calling Gemini..."):
            st.session_state["copy_cache"] = generate_copy(copy_asset_type, copy_payload)

    cv = st.session_state["copy_cache"]
    if cv:
        st.markdown("**🔥 Hype**");        st.code(cv.hype,        language="text")
        st.markdown("**📊 Analytical**");  st.code(cv.analytical,  language="text")
        st.markdown("**🎯 Direct CTA**");  st.code(cv.direct_cta,  language="text")
        st.markdown("**# Hashtags**");     st.code(" ".join(f"#{t}" for t in cv.hashtags))
    else:
        st.info("Click **Generate copy variants** above (or set GEMINI_API_KEY for live LLM).")

    st.divider()

    # Per-channel tone override
    st.markdown("**Channel tone overrides**")
    tone_overrides: dict[str, str] = {}
    for ch in channels:
        tone_overrides[ch] = st.selectbox(
            ch, ["analytical", "hype", "direct_cta"],
            index={"twitter": 2, "instagram": 1, "tiktok": 1}.get(ch, 0),
            key=f"tone_{ch}",
        )

    st.divider()

    if st.button("🚀 DEPLOY CAMPAIGN", type="primary", use_container_width=True):
        if not html:
            st.error("Cannot deploy — preview failed to render.")
        elif not channels:
            st.error("Select at least one channel.")
        elif not cv:
            st.warning("Generating copy first...")
            cv = generate_copy(copy_asset_type, copy_payload)
            st.session_state["copy_cache"] = cv

        if html and channels:
            with st.spinner("Rendering images..."):
                images = render_to_images(html, sizes=sizes or None,
                                          name_prefix=utm_campaign or "manual")
            st.success(f"Rendered {len(images)} image(s).")
            for sz, p in images.items():
                st.image(str(p), caption=f"{sz} — {p.name}", width=240)

            text_by_channel = {ch: cv.for_platform(ch, tone_overrides[ch]) for ch in channels}

            with st.spinner("Posting to platforms..."):
                results = deploy_campaign(images, text_by_channel, channels)

            st.subheader("📋 Deploy Report")
            for r in results:
                if r.ok:
                    st.success(f"✅ {r.channel} — posted ({r.url or r.post_id})")
                else:
                    st.error(f"❌ {r.channel} — {r.error}")
