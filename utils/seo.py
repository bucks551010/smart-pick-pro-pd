# ============================================================
# FILE: utils/seo.py
# PURPOSE: God-mode SEO for Streamlit — injects meta tags, Open Graph,
#          Twitter Cards, JSON-LD structured data, canonical URLs,
#          preconnect hints, and PWA manifest into the parent frame.
# ============================================================

import streamlit as st
import os
import json
from typing import Optional

# ── Configuration ─────────────────────────────────────────────
_SITE_NAME = "Smart Pick Pro"
_SITE_DESCRIPTION = (
    "AI-powered NBA prop betting analytics. Neural edge detection, "
    "quantum analysis, real-time line movement tracking, and machine "
    "learning projections for DraftKings, FanDuel, PrizePicks & more."
)
_SITE_KEYWORDS = (
    "NBA props, NBA betting analytics, AI sports predictions, "
    "prop scanner, player projections, DraftKings picks, FanDuel props, "
    "PrizePicks optimizer, NBA machine learning, smart money bets, "
    "NBA line movement, player prop analysis, NBA DFS optimizer, "
    "sports betting AI, quantum analysis NBA, NBA edge detection, "
    "basketball analytics, NBA bet tracker, prop bet calculator, "
    "NBA player simulator, correlation matrix NBA"
)
_DEFAULT_OG_IMAGE = "/assets/Gold_Logo.png"
_TWITTER_HANDLE = "@SmartPickPro"
_THEME_COLOR = "#00f0ff"
_BG_COLOR = "#070A13"


def _get_base_url() -> str:
    """Return the app's canonical base URL from env."""
    return os.environ.get("APP_URL", "https://smartpickpro.ai").rstrip("/")


def inject_seo(
    page_title: Optional[str] = None,
    page_description: Optional[str] = None,
    page_path: str = "/",
    page_keywords: Optional[str] = None,
    og_image: Optional[str] = None,
    article_type: str = "website",
    noindex: bool = False,
):
    """
    Inject comprehensive SEO meta tags into the Streamlit parent frame.
    Call once per page, right after set_page_config.

    Args:
        page_title: Page-specific title (appended with site name)
        page_description: Page-specific meta description (155 chars max recommended)
        page_path: URL path for canonical (e.g. "/prop-scanner")
        page_keywords: Additional page-specific keywords
        og_image: Override OG image path
        article_type: Open Graph type (website, article, product)
        noindex: Set True for pages that shouldn't be indexed (e.g. Settings)
    """
    # Prevent double-injection
    if st.session_state.get("_seo_injected_" + page_path):
        return
    st.session_state["_seo_injected_" + page_path] = True

    base_url = _get_base_url()
    canonical = f"{base_url}{page_path}"
    full_title = f"{page_title} | {_SITE_NAME}" if page_title else _SITE_NAME
    description = page_description or _SITE_DESCRIPTION
    keywords = page_keywords or _SITE_KEYWORDS
    image_url = f"{base_url}{og_image or _DEFAULT_OG_IMAGE}"
    robots = "noindex, nofollow" if noindex else "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"

    # JSON-LD Structured Data
    jsonld_org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": _SITE_NAME,
        "url": base_url,
        "logo": f"{base_url}/assets/Gold_Logo.png",
        "description": _SITE_DESCRIPTION,
        "sameAs": [],
    }

    jsonld_webapp = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": _SITE_NAME,
        "url": base_url,
        "description": _SITE_DESCRIPTION,
        "applicationCategory": "SportsApplication",
        "operatingSystem": "Web",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD",
            "description": "Free tier available — premium tiers from $9.99/mo",
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.9",
            "ratingCount": "127",
            "bestRating": "5",
        },
        "featureList": [
            "AI-Powered Prop Scanner",
            "Neural Quantum Analysis Matrix",
            "Real-Time Line Movement Tracking",
            "Smart Money Detection",
            "Player Projection Simulator",
            "Entry Builder & Optimizer",
            "Correlation Matrix",
            "Live Game Sweat Tracker",
        ],
    }

    jsonld_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": base_url,
            },
        ],
    }
    if page_title and page_path != "/":
        jsonld_breadcrumb["itemListElement"].append({
            "@type": "ListItem",
            "position": 2,
            "name": page_title,
            "item": canonical,
        })

    # Build the mega injection script
    meta_html = f"""
    <script>
    (function() {{
        if (window.__spp_seo_done) return;
        window.__spp_seo_done = true;

        var head = window.parent.document.head;
        var doc = window.parent.document;

        // Helper to create and append meta tag
        function setMeta(name, content, isProperty) {{
            if (!content) return;
            var attr = isProperty ? 'property' : 'name';
            var existing = head.querySelector('meta[' + attr + '="' + name + '"]');
            if (existing) {{ existing.setAttribute('content', content); return; }}
            var m = doc.createElement('meta');
            m.setAttribute(attr, name);
            m.setAttribute('content', content);
            head.appendChild(m);
        }}

        // ── Page Title ──
        doc.title = {json.dumps(full_title)};

        // ── Basic Meta ──
        setMeta('description', {json.dumps(description)}, false);
        setMeta('keywords', {json.dumps(keywords)}, false);
        setMeta('robots', {json.dumps(robots)}, false);
        setMeta('author', 'Smart Pick Pro', false);
        setMeta('generator', 'Smart Pick Pro AI Engine', false);
        setMeta('theme-color', '{_THEME_COLOR}', false);
        setMeta('color-scheme', 'dark', false);
        setMeta('application-name', '{_SITE_NAME}', false);
        setMeta('apple-mobile-web-app-title', '{_SITE_NAME}', false);
        setMeta('apple-mobile-web-app-capable', 'yes', false);
        setMeta('apple-mobile-web-app-status-bar-style', 'black-translucent', false);
        setMeta('mobile-web-app-capable', 'yes', false);
        setMeta('msapplication-TileColor', '{_BG_COLOR}', false);
        setMeta('msapplication-navbutton-color', '{_THEME_COLOR}', false);

        // ── Canonical URL ──
        var canon = head.querySelector('link[rel="canonical"]');
        if (!canon) {{
            canon = doc.createElement('link');
            canon.setAttribute('rel', 'canonical');
            head.appendChild(canon);
        }}
        canon.setAttribute('href', {json.dumps(canonical)});

        // ── Open Graph ──
        setMeta('og:type', {json.dumps(article_type)}, true);
        setMeta('og:title', {json.dumps(full_title)}, true);
        setMeta('og:description', {json.dumps(description)}, true);
        setMeta('og:url', {json.dumps(canonical)}, true);
        setMeta('og:image', {json.dumps(image_url)}, true);
        setMeta('og:image:width', '1200', true);
        setMeta('og:image:height', '630', true);
        setMeta('og:image:alt', '{_SITE_NAME} - AI NBA Analytics', true);
        setMeta('og:site_name', '{_SITE_NAME}', true);
        setMeta('og:locale', 'en_US', true);

        // ── Twitter Card ──
        setMeta('twitter:card', 'summary_large_image', false);
        setMeta('twitter:site', '{_TWITTER_HANDLE}', false);
        setMeta('twitter:title', {json.dumps(full_title)}, false);
        setMeta('twitter:description', {json.dumps(description)}, false);
        setMeta('twitter:image', {json.dumps(image_url)}, false);
        setMeta('twitter:image:alt', '{_SITE_NAME} - AI NBA Analytics', false);

        // ── Preconnect hints for performance ──
        var preconnects = [
            'https://www.googletagmanager.com',
            'https://www.google-analytics.com',
            'https://fonts.googleapis.com',
            'https://fonts.gstatic.com'
        ];
        preconnects.forEach(function(url) {{
            var link = doc.createElement('link');
            link.setAttribute('rel', 'preconnect');
            link.setAttribute('href', url);
            link.setAttribute('crossorigin', '');
            head.appendChild(link);
        }});

        // ── DNS Prefetch ──
        var dnsPrefetch = [
            'https://cdn.nba.com',
            'https://stats.nba.com',
            'https://api.the-odds-api.com'
        ];
        dnsPrefetch.forEach(function(url) {{
            var link = doc.createElement('link');
            link.setAttribute('rel', 'dns-prefetch');
            link.setAttribute('href', url);
            head.appendChild(link);
        }});

        // ── PWA Manifest ──
        var manifest = head.querySelector('link[rel="manifest"]');
        if (!manifest) {{
            manifest = doc.createElement('link');
            manifest.setAttribute('rel', 'manifest');
            manifest.setAttribute('href', '/manifest.json');
            head.appendChild(manifest);
        }}

        // ── JSON-LD Structured Data ──
        var schemas = {json.dumps([jsonld_org, jsonld_webapp, jsonld_breadcrumb])};
        schemas.forEach(function(schema) {{
            var script = doc.createElement('script');
            script.setAttribute('type', 'application/ld+json');
            script.textContent = JSON.stringify(schema);
            head.appendChild(script);
        }});

        // ── Accessibility lang attribute ──
        doc.documentElement.setAttribute('lang', 'en');
        doc.documentElement.setAttribute('dir', 'ltr');
    }})();
    </script>
    """
    st.html(meta_html)


# ── Page-specific SEO presets ─────────────────────────────────

SEO_PAGES = {
    "Home": {
        "page_title": "AI-Powered NBA Prop Betting Analytics",
        "page_description": "Smart Pick Pro uses neural networks and quantum analysis to find +EV NBA props. Real-time edge detection across DraftKings, FanDuel, PrizePicks. Free tier available.",
        "page_path": "/",
    },
    "Live Sweat": {
        "page_title": "Live Sweat Tracker — Real-Time NBA Bet Monitoring",
        "page_description": "Track your active NBA bets in real-time with live score updates, win probability shifts, and cash-out recommendations powered by AI.",
        "page_path": "/live-sweat",
    },
    "Live Games": {
        "page_title": "Live NBA Games — Real-Time Scores & In-Play Analytics",
        "page_description": "Monitor every live NBA game with real-time box scores, momentum shifts, and in-play prop opportunities identified by our AI engine.",
        "page_path": "/live-games",
    },
    "Prop Scanner": {
        "page_title": "AI Prop Scanner — Find +EV NBA Player Props",
        "page_description": "Scan 500+ NBA player props in seconds. Our AI identifies mispriced lines across DraftKings, FanDuel, and PrizePicks with edge percentages and confidence scores.",
        "page_path": "/prop-scanner",
    },
    "Quantum Analysis": {
        "page_title": "Quantum Analysis Matrix — Deep Neural NBA Projections",
        "page_description": "Advanced neural analysis engine running 2000+ Quantum simulations per player. Get quantum-grade confidence scores and edge detection for NBA props.",
        "page_path": "/quantum-analysis",
    },
    "Smart Money Bets": {
        "page_title": "Smart Money Bets — Follow the Sharp Action",
        "page_description": "See where sharp bettors and syndicates are placing NBA money. Reverse-engineer line movement to identify institutional-grade prop plays.",
        "page_path": "/smart-money",
    },
    "The Studio": {
        "page_title": "The Studio — AI Sports Betting Research Lab",
        "page_description": "Deep-dive research studio for NBA analytics. Advanced statistical models, trend analysis, and proprietary algorithms for serious sports bettors.",
        "page_path": "/studio",
    },
    "Game Report": {
        "page_title": "Game Report — Pre-Game NBA Analytics & Predictions",
        "page_description": "Comprehensive pre-game reports for every NBA matchup. Includes projected lineups, pace analysis, defensive matchups, and prop recommendations.",
        "page_path": "/game-report",
    },
    "Player Simulator": {
        "page_title": "Player Simulator — Quantum NBA Prop Projections",
        "page_description": "Simulate any NBA player's performance with Quantum methods. Adjust minutes, pace, and matchup factors to project props with confidence intervals.",
        "page_path": "/player-simulator",
    },
    "Entry Builder": {
        "page_title": "Entry Builder — Optimize DFS & Prop Parlays",
        "page_description": "Build optimized DFS lineups and prop parlays with correlation-aware AI. Maximize expected value across PrizePicks, Underdog, and DraftKings.",
        "page_path": "/entry-builder",
    },
    "Risk Shield": {
        "page_title": "Risk Shield — Bankroll Management & Risk Analysis",
        "page_description": "AI-powered bankroll protection. Kelly criterion sizing, variance tracking, tilt detection, and drawdown alerts to keep your betting profitable.",
        "page_path": "/risk-shield",
    },
    "Smart NBA Data": {
        "page_title": "Smart NBA Data — Real-Time Stats & Data Feeds",
        "page_description": "Live NBA data feeds powering our AI engine. Player stats, team metrics, injury reports, and lineup data updated in real-time.",
        "page_path": "/nba-data",
    },
    "Correlation Matrix": {
        "page_title": "Correlation Matrix — NBA Prop Correlation Finder",
        "page_description": "Discover hidden correlations between NBA player props. Build high-correlation parlays and identify same-game multi opportunities.",
        "page_path": "/correlation-matrix",
    },
    "Bet Tracker": {
        "page_title": "Bet Tracker — Track ROI & Model Performance",
        "page_description": "Track every bet with automatic grading. See your ROI, win rate, CLV, and model accuracy over time with beautiful analytics dashboards.",
        "page_path": "/bet-tracker",
    },
    "Proving Grounds": {
        "page_title": "Proving Grounds — Backtest & Validate Strategies",
        "page_description": "Backtest betting strategies against historical NBA data. Validate edge persistence, measure Sharpe ratios, and prove profitability before risking capital.",
        "page_path": "/proving-grounds",
    },
    "Settings": {
        "page_title": "Settings",
        "page_description": "Configure Smart Pick Pro NBA prediction engine settings.",
        "page_path": "/settings",
        "noindex": True,
    },
    "Subscription": {
        "page_title": "Pricing & Plans — Smart Pick Pro Subscription Tiers",
        "page_description": "Choose your Smart Pick Pro plan. Free tier included. Sharp IQ ($9.99/mo), Smart Money ($24.99/mo), and Insider Circle for serious NBA bettors.",
        "page_path": "/pricing",
    },
    "Results Ledger": {
        "page_title": "Results Ledger — AI Pick History & Graded Outcomes",
        "page_description": "View the full graded history of every AI-generated NBA prop pick. Transparent win/loss record, ROI over time, and model accuracy statistics.",
        "page_path": "/results",
    },
    "Admin Metrics": {
        "page_title": "Admin Metrics",
        "page_description": "Internal platform metrics dashboard.",
        "page_path": "/admin",
        "noindex": True,
    },
}


def inject_page_seo(page_name: str):
    """
    One-liner SEO injection — looks up the page preset and injects all tags.
    Usage: inject_page_seo("Prop Scanner")
    """
    preset = SEO_PAGES.get(page_name, {})
    inject_seo(
        page_title=preset.get("page_title", page_name),
        page_description=preset.get("page_description"),
        page_path=preset.get("page_path", "/"),
        og_image=preset.get("og_image"),
        noindex=preset.get("noindex", False),
    )


# ══════════════════════════════════════════════════════════════
# PHASE 1 EXTENSION: Dynamic Player-Prop & Game Meta Injection
# ══════════════════════════════════════════════════════════════

def inject_player_prop_seo(
    player_name: str,
    stat_type: str,
    line: float,
    confidence: float,
    platform: str = "PrizePicks",
    og_image_url: Optional[str] = None,
) -> None:
    """
    Inject dynamic meta tags for a specific player prop context.

    Produces title/description/OG tags optimised for queries like
    "LeBron James points prop tonight" and surfaces rich previews
    when the page is shared on Twitter/iMessage.

    Args:
        player_name:  Full player name (e.g. "LeBron James")
        stat_type:    Prop type (e.g. "Points", "Rebounds", "Assists")
        line:         Prop line (e.g. 27.5)
        confidence:   Model confidence 0-100 (e.g. 84.2)
        platform:     Sportsbook / DFS platform (e.g. "DraftKings")
        og_image_url: Absolute URL to a player-specific OG image.
                      Falls back to NBA CDN headshot heuristic if omitted.
    """
    base_url = _get_base_url()
    direction = "OVER" if confidence >= 50 else "UNDER"
    conf_pct = f"{confidence:.0f}%"

    # Prefer supplied image; otherwise attempt NBA CDN headshot as OG image
    if not og_image_url:
        try:
            from data.player_profile_service import get_headshot_url as _ghu
            og_image_url = _ghu(player_name) or f"{base_url}{_DEFAULT_OG_IMAGE}"
        except Exception:
            og_image_url = f"{base_url}{_DEFAULT_OG_IMAGE}"

    title = (
        f"{player_name} {stat_type} Prop: {direction} {line} "
        f"({conf_pct} AI Confidence) | {_SITE_NAME}"
    )
    description = (
        f"AI analysis on {player_name}'s {stat_type} prop at {line} on {platform}. "
        f"Neural model shows {conf_pct} confidence in the {direction}. "
        f"Real-time edge detection, matchup breakdown, and quantum simulations."
    )
    keywords = (
        f"{player_name} prop, {player_name} {stat_type.lower()} prop, "
        f"{player_name} {platform} pick, NBA props today, "
        f"{player_name} projection, {stat_type} over under "
        + _SITE_KEYWORDS
    )
    # Slug: lowercase, spaces → hyphens, strip non-alphanumeric except hyphens
    import re as _re
    slug = _re.sub(r"[^a-z0-9-]", "", player_name.lower().replace(" ", "-"))
    page_path = f"/prop/{slug}"

    inject_seo(
        page_title=title.split(" | ")[0],  # inject_seo adds " | site_name" suffix
        page_description=description,
        page_path=page_path,
        page_keywords=keywords,
        og_image=None,
        article_type="article",
    )

    # Override OG image with player headshot (after base inject_seo ran)
    if og_image_url:
        _override_og_image(og_image_url, player_name)


def inject_game_seo(
    home_team: str,
    away_team: str,
    game_date: str,
    picks_count: int = 0,
) -> None:
    """
    Inject dynamic meta tags for a specific NBA game context.

    Targets queries like "Celtics vs Lakers AI picks tonight".

    Args:
        home_team:    Home team name (e.g. "Los Angeles Lakers")
        away_team:    Away team name (e.g. "Boston Celtics")
        game_date:    ISO date string (e.g. "2026-04-24")
        picks_count:  Number of AI picks surfaced for this game
    """
    title = f"{away_team} vs {home_team} AI Picks {game_date}"
    desc_suffix = (
        f" {picks_count} AI-identified prop edges available."
        if picks_count > 0 else ""
    )
    description = (
        f"Neural AI analysis for {away_team} at {home_team} on {game_date}."
        f" Quantum simulations, line movement, smart money signals, and "
        f"player prop recommendations for DraftKings, FanDuel, PrizePicks."
        f"{desc_suffix}"
    )
    import re as _re
    slug = _re.sub(
        r"[^a-z0-9-]", "",
        f"{away_team.lower().replace(' ', '-')}-vs-{home_team.lower().replace(' ', '-')}"
    )
    inject_seo(
        page_title=title,
        page_description=description,
        page_path=f"/game/{slug}/{game_date}",
        article_type="article",
    )


def _override_og_image(image_url: str, alt_text: str) -> None:
    """Push an updated og:image into the DOM after the primary inject_seo call."""
    safe_url = image_url.replace("'", "\\'")
    safe_alt = alt_text.replace("'", "\\'")
    st.html(f"""
    <script>
    (function() {{
        var head = window.parent.document.head;
        function setMeta(prop, val) {{
            var el = head.querySelector('meta[property="' + prop + '"]');
            if (el) el.setAttribute('content', val);
        }}
        setMeta('og:image', '{safe_url}');
        setMeta('og:image:alt', '{safe_alt}');
        var tw = head.querySelector('meta[name="twitter:image"]');
        if (tw) tw.setAttribute('content', '{safe_url}');
    }})();
    </script>
    """)


# ══════════════════════════════════════════════════════════════
# PHASE 2: Additional JSON-LD Structured Data Schemas
# ══════════════════════════════════════════════════════════════

def inject_sports_event_jsonld(
    home_team: str,
    away_team: str,
    game_date: str,
    location: Optional[str] = None,
) -> None:
    """
    Inject a SportsEvent JSON-LD schema for a specific NBA game.

    Enables Google to show the game as a rich result with teams,
    date, and location — boosting SERP click-through for game queries.

    Args:
        home_team:  Home team name
        away_team:  Away team name
        game_date:  ISO date string (YYYY-MM-DD)
        location:   Optional arena/city string (e.g. "Crypto.com Arena")
    """
    base_url = _get_base_url()
    schema: dict = {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": f"{away_team} vs {home_team}",
        "startDate": game_date,
        "sport": "Basketball",
        "url": base_url,
        "organizer": {
            "@type": "SportsOrganization",
            "name": "NBA",
            "url": "https://www.nba.com",
        },
        "homeTeam": {
            "@type": "SportsTeam",
            "name": home_team,
            "sport": "Basketball",
        },
        "awayTeam": {
            "@type": "SportsTeam",
            "name": away_team,
            "sport": "Basketball",
        },
    }
    if location:
        schema["location"] = {
            "@type": "Place",
            "name": location,
        }
    _inject_raw_jsonld(schema)


def inject_dataset_jsonld(
    name: str,
    description: str,
    item_count: int = 0,
) -> None:
    """
    Inject a Dataset JSON-LD schema for analytics/prop-scanner pages.

    Signals to Google that the page contains structured data and
    qualifies for Dataset rich results.

    Args:
        name:        Dataset name (e.g. "NBA Player Prop Analytics — 2026 Season")
        description: What the dataset contains
        item_count:  Number of records/props (0 = omit from schema)
    """
    base_url = _get_base_url()
    schema: dict = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": name,
        "description": description,
        "url": base_url,
        "creator": {
            "@type": "Organization",
            "name": _SITE_NAME,
            "url": base_url,
        },
        "license": "https://creativecommons.org/licenses/by-nc/4.0/",
        "isAccessibleForFree": True,
        "keywords": [
            "NBA props", "player projections", "AI sports analytics",
            "basketball statistics", "prop betting", "machine learning NBA",
        ],
    }
    if item_count > 0:
        schema["size"] = f"{item_count} player prop records"
    _inject_raw_jsonld(schema)


def inject_item_list_jsonld(picks: list) -> None:
    """
    Inject an ItemList JSON-LD schema for a list of prop picks.

    Enables Google to render individual picks as list rich results.

    Args:
        picks: List of dicts with keys: player_name, stat_type, line,
               confidence, platform, direction (optional).
    """
    if not picks:
        return
    base_url = _get_base_url()
    items = []
    for i, pick in enumerate(picks[:20], 1):  # cap at 20 items per Google guidance
        pname = pick.get("player_name") or pick.get("player") or ""
        stat = pick.get("stat_type") or pick.get("prop_type") or "Prop"
        line = pick.get("line") or pick.get("prop_line") or ""
        conf = pick.get("confidence") or pick.get("confidence_score") or ""
        import re as _re
        slug = _re.sub(r"[^a-z0-9-]", "", pname.lower().replace(" ", "-"))
        items.append({
            "@type": "ListItem",
            "position": i,
            "name": f"{pname} {stat} {line}",
            "url": f"{base_url}/prop/{slug}",
            "description": (
                f"AI confidence: {conf}%" if conf else
                f"{pname} {stat} prop pick"
            ),
        })
    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Today's AI NBA Prop Picks — {_SITE_NAME}",
        "description": (
            "AI-identified +EV NBA player prop picks with neural confidence scores."
        ),
        "url": base_url,
        "itemListElement": items,
    }
    _inject_raw_jsonld(schema)


def _inject_raw_jsonld(schema: dict) -> None:
    """Inject a single JSON-LD schema block invisibly into the parent DOM."""
    escaped = json.dumps(schema, ensure_ascii=False)
    st.html(f"""
    <script type="application/ld+json">
    {escaped}
    </script>
    """)


# ══════════════════════════════════════════════════════════════
# PHASE 3: Semantic Heading Architecture
# ══════════════════════════════════════════════════════════════

def inject_semantic_heading_css() -> None:
    """
    Inject CSS that enforces a clear H1 → H2 → H3 visual hierarchy.

    Streamlit's default stylesheet flattens heading sizes.  These rules
    restore a readable hierarchy without overriding the dark theme palette.
    Also injects a visually-hidden H1 helper class used by render_seo_h1().
    """
    css = """
    <style>
    /* ── Semantic heading hierarchy for Streamlit markdown ── */

    /* H1 — Page title: large, accent-coloured, single per page */
    .main h1,
    [data-testid="stMarkdownContainer"] h1 {
        font-size: clamp(1.75rem, 3.5vw, 2.5rem) !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em !important;
        line-height: 1.15 !important;
        color: #00f0ff !important;
        margin-bottom: 0.5rem !important;
        margin-top: 0.25rem !important;
    }

    /* H2 — Section headers: medium, secondary accent */
    .main h2,
    [data-testid="stMarkdownContainer"] h2 {
        font-size: clamp(1.25rem, 2.5vw, 1.75rem) !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em !important;
        line-height: 1.25 !important;
        color: #a8d8ff !important;
        margin-bottom: 0.4rem !important;
        margin-top: 1.5rem !important;
        border-bottom: 1px solid rgba(0,240,255,0.12) !important;
        padding-bottom: 0.3rem !important;
    }

    /* H3 — Sub-section: readable, slightly muted */
    .main h3,
    [data-testid="stMarkdownContainer"] h3 {
        font-size: clamp(1.05rem, 2vw, 1.35rem) !important;
        font-weight: 600 !important;
        line-height: 1.3 !important;
        color: #dce4f0 !important;
        margin-bottom: 0.3rem !important;
        margin-top: 1.25rem !important;
    }

    /* H4-H6 — Tertiary: normal weight, slightly dimmed */
    .main h4, .main h5, .main h6,
    [data-testid="stMarkdownContainer"] h4,
    [data-testid="stMarkdownContainer"] h5,
    [data-testid="stMarkdownContainer"] h6 {
        font-size: 1rem !important;
        font-weight: 500 !important;
        color: #9aafc8 !important;
        margin-bottom: 0.25rem !important;
        margin-top: 1rem !important;
    }

    /* ── SEO-only visually-hidden H1 (screen-reader + Googlebot visible) ── */
    .spp-seo-h1 {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        margin: -1px !important;
        padding: 0 !important;
        overflow: hidden !important;
        clip: rect(0,0,0,0) !important;
        white-space: nowrap !important;
        border: 0 !important;
    }

    /* ── Image alt-text rendering for broken images ── */
    img[alt] {
        font-size: 0.75rem;
        color: #9aafc8;
    }
    </style>
    """
    st.html(css)


def render_seo_h1(text: str, visible: bool = False) -> None:
    """
    Emit a semantic <h1> containing the primary keyword phrase.

    When ``visible=False`` (default), the H1 is positioned off-screen so
    it's invisible to users but fully readable by Googlebot and screen
    readers — a best-practice "SEO anchor" technique.

    When ``visible=True``, it renders as the normal styled page title.

    Args:
        text:    The H1 content — should be the primary keyword phrase
                 for this page (e.g. "AI NBA Prop Betting Analytics")
        visible: True = render as visible page title, False = SEO-only
    """
    import html as _html_mod
    safe = _html_mod.escape(text)
    cls = "" if visible else ' class="spp-seo-h1"'
    st.html(f"<h1{cls}>{safe}</h1>")
