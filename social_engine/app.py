"""SmartPickPro Social Engine — Streamlit Control Room.

Run:  streamlit run app.py
"""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path

import streamlit as st

from config import BRAND, OUTPUT_SIZES, SETTINGS
from core import data_source as ds
from core.llm_copy import generate_copy
from distribute.campaign import deploy_campaign
from render.headless import render_to_images, render_png_bytes
from render.jinja_engine import render_html
from render.card_templates import TEMPLATES

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

# ── Top-level tabs ────────────────────────────────────────────
tab_campaign, tab_templates = st.tabs(["🚀 Campaign Builder", "🎨 Card Templates"])


# ══════════════════════════════════════════════════════════════
# TAB 2 — CARD TEMPLATES  (single-image + carousel + reels)
# ══════════════════════════════════════════════════════════════
with tab_templates:
    import io, zipfile
    from render.card_templates import render_carousel

    st.markdown("### Pick a design, choose a size, preview & export.")
    st.caption("Safe inner margins on every template — nothing bleeds to the edge.")

    ctrl_col, prev_col = st.columns([1, 1.4])

    # ── shared session-state buckets ──────────────────────────
    for _k in ("tmpl_html", "tmpl_png", "tmpl_slides_html", "tmpl_slides_png"):
        if _k not in st.session_state:
            st.session_state[_k] = {}

    # ── controls ─────────────────────────────────────────────
    with ctrl_col:
        tmpl_options = {v["label"]: k for k, v in TEMPLATES.items()}
        chosen_label = st.radio("**Template**", list(tmpl_options.keys()), key="tmpl_radio")
        chosen_key   = tmpl_options[chosen_label]
        tmpl         = TEMPLATES[chosen_key]
        st.caption(tmpl["description"])
        is_carousel  = tmpl.get("needs_carousel", False)

        st.divider()

        size_label = st.selectbox(
            "**Platform / Size**",
            list(tmpl["sizes"].keys()),
            key="tmpl_size",
            help="Each size is optimised for the platform.",
        )
        w, h = tmpl["sizes"][size_label]
        st.caption(f"{w} × {h} px")

        st.divider()

        result_date = st.date_input("Results date", value=date.today(), key="tmpl_date")
        n_show      = st.slider("Picks shown", 1, 9, 7, key="tmpl_npicks")
        if is_carousel:
            st.info("ℹ Carousel: cover + one slide per pick + CTA slide.")

        st.divider()

        st.markdown("**Post to channels**")
        tmpl_channels: list[str] = []
        for ch, lbl in [("twitter","X / Twitter"), ("facebook","Facebook"),
                         ("instagram","Instagram"), ("threads","Threads")]:
            if st.checkbox(lbl, value=(ch in ("twitter","instagram")), key=f"tmpl_ch_{ch}"):
                tmpl_channels.append(ch)

        render_btn   = st.button("🖼 Render Preview",  use_container_width=True, key="tmpl_render")
        if is_carousel:
            download_btn = st.button("💾 Download ZIP",    use_container_width=True, key="tmpl_dl",     type="secondary")
        else:
            download_btn = st.button("💾 Download PNG",    use_container_width=True, key="tmpl_dl",     type="secondary")
        deploy_btn   = st.button("🚀 Post Now",         use_container_width=True, key="tmpl_deploy",  type="primary")

    # ── helpers ───────────────────────────────────────────────
    def _get_results_picks() -> tuple[int, int, float, list[dict]]:
        try:
            summary = ds.get_results_for_date(result_date)
            picks = [
                {
                    "player_name":  b.player_name,
                    "stat_type":    b.stat_type,
                    "prop_line":    b.prop_line,
                    "direction":    getattr(b, "direction", "OVER"),
                    "actual_value": getattr(b, "actual_value", None),
                    "platform":     getattr(b, "platform", ""),
                    "result":       b.result,
                }
                for b in summary.bets[:n_show]
            ]
            return summary.wins, summary.losses, summary.win_rate, picks
        except Exception:
            return 338, 130, 72.2, []

    def _build_single_html(w: int, h: int) -> str:
        fn          = tmpl["fn"]
        needs_picks = tmpl.get("needs_picks", False)
        wins, losses, wr, picks = _get_results_picks()
        if needs_picks:
            return fn(wins, losses, wr, picks, width=w, height=h)
        return fn(wins, losses, wr, width=w, height=h)

    def _build_carousel_slides(w: int, h: int) -> list[str]:
        wins, losses, wr, picks = _get_results_picks()
        return render_carousel(wins, losses, wr, picks, w, h,
                               date_str=result_date.strftime("%b %d · %Y").upper())

    cache_key = f"{chosen_key}_{size_label}_{result_date}_{n_show}"

    # ── preview panel ─────────────────────────────────────────
    with prev_col:
        if is_carousel:
            st.markdown("**Carousel Preview** — scroll through slides below")
        else:
            st.markdown("**Preview**")
        st.caption(f"Final export: {w} × {h} px")

        # ── CAROUSEL branch ───────────────────────────────────
        if is_carousel:
            if render_btn or cache_key not in st.session_state["tmpl_slides_html"]:
                with st.spinner("Rendering slides…"):
                    try:
                        slides_html = _build_carousel_slides(w, h)
                        st.session_state["tmpl_slides_html"][cache_key] = slides_html
                        st.session_state["tmpl_slides_png"].pop(cache_key, None)
                    except Exception as e:
                        st.error(f"Render error: {e}")
                        slides_html = []
            else:
                slides_html = st.session_state["tmpl_slides_html"].get(cache_key, [])

            if slides_html:
                st.caption(f"{len(slides_html)} slides total")
                # slide strip — show thumbnails in a scrollable row
                cols_per_row = 3
                for row_start in range(0, len(slides_html), cols_per_row):
                    row_slides = slides_html[row_start:row_start + cols_per_row]
                    thumb_cols = st.columns(len(row_slides))
                    for ci, (html_s, tc) in enumerate(zip(row_slides, thumb_cols)):
                        slide_idx = row_start + ci + 1
                        label = "Cover" if slide_idx == 1 else ("CTA" if slide_idx == len(slides_html) else f"Pick {slide_idx-1}")
                        with tc:
                            st.caption(f"**{slide_idx}** · {label}")
                            thumb_h = min(280, int(240 * h / w))
                            st.components.v1.html(html_s, height=thumb_h, scrolling=False)

            # Download ZIP
            if download_btn and slides_html:
                if cache_key not in st.session_state["tmpl_slides_png"]:
                    with st.spinner(f"Exporting {len(slides_html)} slides…"):
                        pngs: list[bytes] = []
                        prog = st.progress(0)
                        for i, html_s in enumerate(slides_html):
                            pngs.append(render_png_bytes(html_s, width=w, height=h))
                            prog.progress((i + 1) / len(slides_html))
                        prog.empty()
                        st.session_state["tmpl_slides_png"][cache_key] = pngs
                pngs = st.session_state["tmpl_slides_png"][cache_key]

                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, png_bytes in enumerate(pngs, start=1):
                        label_s = "cover" if i == 1 else ("cta" if i == len(pngs) else f"pick_{i-1:02d}")
                        zf.writestr(f"slide_{i:02d}_{label_s}.png", png_bytes)
                buf.seek(0)
                total_kb = sum(len(p) for p in pngs) // 1024
                st.download_button(
                    label=f"⬇ Download carousel ({len(pngs)} slides, ~{total_kb}KB)",
                    data=buf,
                    file_name=f"carousel_{chosen_key}_{result_date}.zip",
                    mime="application/zip",
                    key="tmpl_dl_link",
                )
                st.success(f"{len(pngs)} slides zipped — {total_kb} KB total")

            # Post carousel
            if deploy_btn and slides_html:
                if not tmpl_channels:
                    st.error("Select at least one channel first.")
                else:
                    if cache_key not in st.session_state["tmpl_slides_png"]:
                        with st.spinner(f"Exporting {len(slides_html)} slides…"):
                            pngs = []
                            prog = st.progress(0)
                            for i, html_s in enumerate(slides_html):
                                pngs.append(render_png_bytes(html_s, width=w, height=h))
                                prog.progress((i + 1) / len(slides_html))
                            prog.empty()
                            st.session_state["tmpl_slides_png"][cache_key] = pngs
                    pngs = st.session_state["tmpl_slides_png"][cache_key]

                    out_dir = Path("_out") / f"carousel_{chosen_key}_{result_date}"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    image_paths: dict[str, Path] = {}
                    for i, png_bytes in enumerate(pngs, start=1):
                        lbl = "cover" if i == 1 else ("cta" if i == len(pngs) else f"pick_{i-1:02d}")
                        p = out_dir / f"slide_{i:02d}_{lbl}.png"
                        p.write_bytes(png_bytes)
                        image_paths[f"slide_{i:02d}"] = p

                    with st.spinner("Posting carousel…"):
                        wins, losses, wr, _ = _get_results_picks()
                        try:
                            cv       = generate_copy("results", {"wins": wins, "losses": losses,
                                                                  "win_rate": wr, "roi_pct": None})
                            text_map = {ch: cv.for_platform(ch, "hype") for ch in tmpl_channels}
                        except Exception:
                            text_map = {ch: f"🔥 {wins}-{losses} last night · {wr}% win rate\n\nSwipe for the full receipts. #SmartPickPro #NBA" for ch in tmpl_channels}
                        results = deploy_campaign(image_paths, text_map, tmpl_channels)

                    st.subheader("📋 Post Results")
                    for r in results:
                        if r.ok:
                            st.success(f"✅ {r.channel} — {r.url or r.post_id}")
                        else:
                            st.error(f"❌ {r.channel} — {r.error}")

        # ── SINGLE IMAGE branch ───────────────────────────────
        else:
            if render_btn or cache_key not in st.session_state["tmpl_html"]:
                with st.spinner("Rendering…"):
                    try:
                        html_out = _build_single_html(w, h)
                        st.session_state["tmpl_html"][cache_key] = html_out
                        st.session_state["tmpl_png"].pop(cache_key, None)
                    except Exception as e:
                        st.error(f"Render error: {e}")
                        html_out = None
            else:
                html_out = st.session_state["tmpl_html"].get(cache_key)

            if html_out:
                preview_h = min(640, int(500 * h / w))
                st.components.v1.html(html_out, height=preview_h, scrolling=False)

            if download_btn and html_out:
                if cache_key not in st.session_state["tmpl_png"]:
                    with st.spinner("Exporting full-res PNG…"):
                        png = render_png_bytes(html_out, width=w, height=h)
                        st.session_state["tmpl_png"][cache_key] = png
                png = st.session_state["tmpl_png"][cache_key]
                fname = f"smartpickpro_{chosen_key}_{w}x{h}.png"
                st.download_button(
                    label=f"⬇ Download  {fname}",
                    data=png,
                    file_name=fname,
                    mime="image/png",
                    key="tmpl_dl_link",
                )
                st.success(f"PNG ready — {len(png)//1024} KB")

            if deploy_btn and html_out:
                if not tmpl_channels:
                    st.error("Select at least one channel first.")
                else:
                    if cache_key not in st.session_state["tmpl_png"]:
                        with st.spinner("Exporting PNG…"):
                            png = render_png_bytes(html_out, width=w, height=h)
                            st.session_state["tmpl_png"][cache_key] = png
                    png = st.session_state["tmpl_png"][cache_key]

                    out_path = Path("_out") / f"tmpl_{chosen_key}_{w}x{h}.png"
                    out_path.parent.mkdir(exist_ok=True)
                    out_path.write_bytes(png)

                    with st.spinner("Posting…"):
                        wins, losses, wr, _ = _get_results_picks()
                        try:
                            cv = generate_copy("results", {"wins": wins, "losses": losses,
                                                           "win_rate": wr, "roi_pct": None})
                            text_map = {ch: cv.for_platform(ch, "hype") for ch in tmpl_channels}
                        except Exception:
                            text_map = {ch: f"🔥 {wins}-{losses} last night · {wr}% win rate\n\nAll results on file. #SmartPickPro #NBA" for ch in tmpl_channels}

                        results = deploy_campaign({"square": out_path}, text_map, tmpl_channels)

                    for r in results:
                        if r.ok:
                            st.success(f"✅ {r.channel} — {r.url or r.post_id}")
                        else:
                            st.error(f"❌ {r.channel} — {r.error}")


# ══════════════════════════════════════════════════════════════
# TAB 1 — CAMPAIGN BUILDER (original flow)
# ══════════════════════════════════════════════════════════════
with tab_campaign:
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
            result_date_camp = st.date_input("Results date", value=date.today(), key="camp_rdate")
            n_picks = st.slider("Bets shown on graphic", 1, 8, 6)

        else:
            cta_headline = st.text_input("Headline", "THE EDGE ISN'T LUCK. IT'S MATH.")
            cta_sub      = st.text_input("Sub-headline",
                "1,000 Quantum simulations per pick. Zero black boxes. Free trial.")
            cta_button   = st.text_input("Button text", "→ START FREE")

        st.divider()
        st.subheader("Channels")
        channels: list[str] = []
        for ch, label in [("twitter","X / Twitter"), ("facebook","Facebook"),
                          ("instagram","Instagram"), ("threads","Threads"), ("tiktok","TikTok")]:
            if st.checkbox(label, value=True, key=f"ch_{ch}"):
                channels.append(ch)

        st.divider()
        st.subheader("Sizes to render")
        sizes: list[str] = []
        for sz in OUTPUT_SIZES:
            if st.checkbox(sz.title(), value=True, key=f"sz_{sz}"):
                sizes.append(sz)

    col_left, col_right = st.columns([1, 1])

    ctx: dict = {}
    template_name = ""
    utm_source = ""
    utm_campaign_name = ""
    copy_payload: dict = {}
    copy_asset_type = ""

    if asset == "The Slate":
        if slate_kind == "Top 3":
            c_picks = ds.get_top_n_picks(3, pick_date)
            title, sub = "Tonight's Top 3", "Highest-confidence quant edges"
        elif slate_kind == "QEG (edge ≥ threshold)":
            c_picks = ds.get_qeg_picks(edge_min, pick_date)
            title, sub = "Quantum Edge Gap", f"Edge ≥ {edge_min:.1f}%"
        elif slate_kind.startswith("Platform: "):
            plat = slate_kind.split(": ", 1)[1]
            c_picks = ds.get_platform_picks(plat, pick_date)
            title, sub = f"{plat} Slate", "Tonight's edge picks"
        else:
            c_picks = ds.get_slate_for_date(pick_date)
            title, sub = "Tonight's Full Slate", f"{len(c_picks)} edge plays"
        c_picks = c_picks[:n_picks]
        ctx = {"eyebrow": "TONIGHT'S SLATE", "title": title, "subtitle": sub,
               "picks": c_picks, "cols": 2 if len(c_picks) > 1 else 1}
        template_name = "slate.html"
        utm_source, utm_campaign_name = "manual_slate", f"manual_slate_{pick_date:%Y%m%d}"
        copy_asset_type = "slate"
        copy_payload = {"picks": c_picks, "filter": slate_kind}

    elif asset == "The Results":
        summary = ds.get_results_for_date(result_date_camp)
        ctx = {
            "title": f"{summary.wins}-{summary.losses} on {summary.bet_date}",
            "subtitle": "Receipts always shown.",
            "wins": summary.wins, "losses": summary.losses,
            "win_rate": summary.win_rate, "roi_pct": summary.roi_pct,
            "picks": summary.bets[:n_picks], "cols": 2,
        }
        template_name = "results.html"
        utm_source, utm_campaign_name = "manual_recap", f"manual_recap_{summary.bet_date}"
        copy_asset_type = "results"
        copy_payload = {"wins": summary.wins, "losses": summary.losses,
                        "win_rate": summary.win_rate, "roi_pct": summary.roi_pct}

    else:
        ctx = {"title": "Quant NBA Analytics", "headline": cta_headline,
               "subheadline": cta_sub, "button_text": cta_button}
        template_name = "brand_cta.html"
        utm_source, utm_campaign_name = "manual_brand", f"manual_brand_{date.today():%Y%m%d}"
        copy_asset_type = "brand"
        copy_payload = {"product": "SmartPickPro NBA"}

    with col_left:
        st.subheader("📄 Preview")
        try:
            html = render_html(template_name, ctx, utm_source=utm_source,
                               utm_campaign=utm_campaign_name)
            st.components.v1.html(html, height=560, scrolling=False)
        except Exception as e:
            st.error(f"Template render failed: {e}")
            html = None

    with col_right:
        st.subheader("🧠 AI Copy")

        if "copy_cache" not in st.session_state:
            st.session_state["copy_cache"] = None

        if st.button("✨ Generate copy variants"):
            with st.spinner("Calling Gemini…"):
                st.session_state["copy_cache"] = generate_copy(copy_asset_type, copy_payload)

        cv = st.session_state["copy_cache"]
        if cv:
            st.markdown("**🔥 Hype**");        st.code(cv.hype,        language="text")
            st.markdown("**📊 Analytical**");  st.code(cv.analytical,  language="text")
            st.markdown("**🎯 Direct CTA**");  st.code(cv.direct_cta,  language="text")
            st.markdown("**# Hashtags**");     st.code(" ".join(f"#{t}" for t in cv.hashtags))
        else:
            st.info("Click **Generate copy variants** (or set GEMINI_API_KEY).")

        st.divider()

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
            else:
                if not cv:
                    cv = generate_copy(copy_asset_type, copy_payload)
                    st.session_state["copy_cache"] = cv
                with st.spinner("Rendering images…"):
                    images = render_to_images(html, sizes=sizes or None,
                                              name_prefix=utm_campaign_name or "manual")
                st.success(f"Rendered {len(images)} image(s).")
                for sz, p in images.items():
                    st.image(str(p), caption=f"{sz} — {p.name}", width=240)
                text_by_channel = {ch: cv.for_platform(ch, tone_overrides[ch]) for ch in channels}
                with st.spinner("Posting to platforms…"):
                    results = deploy_campaign(images, text_by_channel, channels)
                st.subheader("📋 Deploy Report")
                for r in results:
                    if r.ok:
                        st.success(f"✅ {r.channel} — posted ({r.url or r.post_id})")
                    else:
                        st.error(f"❌ {r.channel} — {r.error}")
