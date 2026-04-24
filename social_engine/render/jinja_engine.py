"""Jinja2 template rendering with brand context auto-injection."""
from __future__ import annotations
from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import BRAND, COMPLIANCE_FOOTER, SETTINGS, TEMPLATE_DIR
from core.headshots import enrich_picks_with_headshots
from core.qr import build_utm_url, qr_data_uri


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Pre-load shared CSS once and re-render with brand vars on each call
def _render_base_css() -> str:
    raw = (TEMPLATE_DIR / "_base.css").read_text(encoding="utf-8")
    return _env.from_string(raw).render(brand=BRAND)


def render_html(
    template_name: str,
    context: dict[str, Any],
    *,
    utm_source: str = "social",
    utm_campaign: str = "",
) -> str:
    """Render a template with brand + compliance + QR auto-injected."""
    qr_target = build_utm_url(
        SETTINGS.brand_url,
        source=utm_source,
        campaign=utm_campaign or f"auto_{datetime.utcnow():%Y%m%d}",
    )

    full_ctx: dict[str, Any] = {
        "brand":              BRAND,
        "base_css":           _render_base_css(),
        "watermark_text":     SETTINGS.watermark_text,
        "compliance_footer":  COMPLIANCE_FOOTER,
        "qr_data_uri":        qr_data_uri(qr_target),
        "date_str":           datetime.now().strftime("%a, %b %d %Y"),
    }
    full_ctx.update(context)

    # Enrich any picks list with NBA headshots (cached after first fetch)
    if "picks" in full_ctx and isinstance(full_ctx["picks"], list):
        full_ctx["picks"] = enrich_picks_with_headshots(full_ctx["picks"])

    return _env.get_template(template_name).render(**full_ctx)
