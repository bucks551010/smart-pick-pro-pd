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
