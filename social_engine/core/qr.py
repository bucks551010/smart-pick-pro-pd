"""QR code generation with UTM tracking → base64 data URI for HTML embed."""
from __future__ import annotations
import base64
import io
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import qrcode


def build_utm_url(
    base_url: str,
    *,
    source: str,        # twitter | facebook | instagram | threads | tiktok
    medium: str = "social",
    campaign: str,      # e.g. "morning_recap_20260423"
    content: str = "",
) -> str:
    """Append UTM params to base_url, preserving any existing query string."""
    parsed = urlparse(base_url)
    qs = dict(parse_qsl(parsed.query))
    qs.update({
        "utm_source":   source,
        "utm_medium":   medium,
        "utm_campaign": campaign,
    })
    if content:
        qs["utm_content"] = content
    return urlunparse(parsed._replace(query=urlencode(qs)))


def qr_data_uri(url: str, *, box_size: int = 8, border: int = 2) -> str:
    """Return `data:image/png;base64,...` for inline <img> embed."""
    img = qrcode.make(url, box_size=box_size, border=border)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
