"""api/routes/seo.py — Dynamic sitemap.xml and robots.txt endpoints.

These endpoints sit in front of the static files and serve auto-dated,
live-generated versions.  The dynamic sitemap is what Google should
consume (via the Sitemap: directive in robots.txt); it always reflects
today's lastmod date on high-volatility pages so Googlebot re-crawls
them on an appropriate schedule.

Endpoints:
    GET /sitemap.xml   — Full XML sitemap with today's lastmod dates
    GET /robots.txt    — Canonical robots.txt (primary source of truth)
"""
import datetime
import os

from utils.logger import get_logger

_logger = get_logger(__name__)

try:
    from fastapi import APIRouter
    from fastapi.responses import Response
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    APIRouter = None  # type: ignore
    Response = None   # type: ignore

if _FASTAPI_AVAILABLE:
    router = APIRouter(tags=["seo"])

    # ── Sitemap page definitions ──────────────────────────────────────────────
    # Each entry: (path, changefreq, priority, is_daily_volatile)
    # is_daily_volatile=True → lastmod = today (re-indexes daily picks pages)
    # is_daily_volatile=False → lastmod = app release date (stable pages)
    _RELEASE_DATE = "2026-04-24"

    _SITEMAP_PAGES: list[tuple[str, str, str, bool]] = [
        ("/",                  "daily",   "1.0",  True),
        ("/prop-scanner",      "hourly",  "0.95", True),
        ("/quantum-analysis",  "hourly",  "0.95", True),
        ("/live-games",        "always",  "0.90", True),
        ("/live-sweat",        "always",  "0.90", True),
        ("/smart-money",       "hourly",  "0.85", True),
        ("/entry-builder",     "daily",   "0.85", True),
        ("/player-simulator",  "daily",   "0.85", True),
        ("/game-report",       "daily",   "0.80", True),
        ("/correlation-matrix","daily",   "0.80", False),
        ("/bet-tracker",       "daily",   "0.80", False),
        ("/risk-shield",       "daily",   "0.75", False),
        ("/studio",            "daily",   "0.75", False),
        ("/nba-data",          "hourly",  "0.70", True),
        ("/results",           "daily",   "0.75", True),
        ("/proving-grounds",   "weekly",  "0.65", False),
        ("/pricing",           "monthly", "0.70", False),
    ]

    def _build_sitemap_xml() -> str:
        base_url = os.environ.get("APP_URL", "https://smartpickpro.ai").rstrip("/")
        today = datetime.date.today().isoformat()
        lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
            "",
        ]

        for path, changefreq, priority, volatile in _SITEMAP_PAGES:
            lastmod = today if volatile else _RELEASE_DATE
            lines += [
                "  <url>",
                f"    <loc>{base_url}{path}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
                "",
            ]

        # Home page image entry
        lines.insert(
            lines.index("  </url>", 4) + 1,
            (
                "    <image:image>\n"
                f"      <image:loc>{base_url}/assets/Gold_Logo.png</image:loc>\n"
                f"      <image:title>Smart Pick Pro — AI NBA Analytics</image:title>\n"
                "    </image:image>"
            ),
        )

        lines.append("</urlset>")
        return "\n".join(lines)

    @router.get(
        "/sitemap.xml",
        summary="Dynamic XML sitemap",
        description=(
            "Returns a fresh XML sitemap with today's lastmod dates on "
            "high-volatility pages so Googlebot schedules daily re-crawls."
        ),
    )
    async def dynamic_sitemap() -> Response:
        """Serve a dynamically generated sitemap.xml."""
        try:
            xml = _build_sitemap_xml()
        except Exception as exc:
            _logger.error("Sitemap generation failed: %s", exc)
            # Fall back to static file if generation fails
            static_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "static", "sitemap.xml"
            )
            try:
                with open(static_path, "r", encoding="utf-8") as fh:
                    xml = fh.read()
            except Exception:
                return Response(
                    content="<?xml version='1.0'?><urlset/>",
                    media_type="application/xml",
                    status_code=500,
                )
        return Response(
            content=xml,
            media_type="application/xml",
            headers={
                "Cache-Control": "public, max-age=3600",  # 1-hour CDN cache
                "X-Content-Type-Options": "nosniff",
            },
        )

    _ROBOTS_TXT = """\
# ============================================================
# robots.txt — SmartPickPro.ai  (served dynamically by FastAPI)
# ============================================================

User-agent: *
Allow: /

# Streamlit internals
Disallow: /_stcore/
Disallow: /component/
Disallow: /stream

# API / health endpoints (JSON, not indexable)
Disallow: /api/
Disallow: /health
Disallow: /healthz

# Private pages
Disallow: /settings
Disallow: /admin

# Player & game URLs explicitly allowed for rich indexing
Allow: /?player=
Allow: /?game=
Allow: /prop/
Allow: /game/

Sitemap: {base_url}/sitemap.xml

User-agent: Googlebot
Allow: /
Disallow: /_stcore/
Disallow: /component/
Disallow: /stream
Disallow: /api/
Crawl-delay: 1

User-agent: Bingbot
Allow: /
Disallow: /_stcore/
Disallow: /component/
Disallow: /api/
Crawl-delay: 2

User-agent: Twitterbot
Allow: /

User-agent: facebookexternalhit
Allow: /

User-agent: LinkedInBot
Allow: /

User-agent: Slackbot
Allow: /

User-agent: WhatsApp
Allow: /

User-agent: GPTBot
Allow: /
Disallow: /api/
Disallow: /admin

User-agent: anthropic-ai
Allow: /
Disallow: /api/
Disallow: /admin
"""

    @router.get(
        "/robots.txt",
        summary="Canonical robots.txt",
        description="Primary robots.txt served by the FastAPI layer with dynamic base URL.",
    )
    async def canonical_robots() -> Response:
        """Serve robots.txt with the correct APP_URL injected."""
        base_url = os.environ.get("APP_URL", "https://smartpickpro.ai").rstrip("/")
        content = _ROBOTS_TXT.format(base_url=base_url)
        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Cache-Control": "public, max-age=86400",  # 24-hour CDN cache
                "X-Content-Type-Options": "nosniff",
            },
        )

else:
    router = None  # type: ignore
