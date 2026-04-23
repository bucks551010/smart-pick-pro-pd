"""LLM copy generation via Google Gemini (free tier).

Returns 3 tone variants per request:
  - hype       : energetic, emoji-heavy, drives FOMO
  - analytical : data-led, confident, builds authority
  - direct_cta : single-pivot CTA push
Each variant ships with platform-optimized hashtags.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from config import SETTINGS

_log = logging.getLogger(__name__)

# Module-level model handle (lazy init)
_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    if not SETTINGS.gemini_api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=SETTINGS.gemini_api_key)
        _model = genai.GenerativeModel("gemini-1.5-flash")
        return _model
    except Exception as e:
        _log.warning("Gemini init failed: %s", e)
        return None


@dataclass
class CopyVariants:
    hype:        str = ""
    analytical:  str = ""
    direct_cta:  str = ""
    hashtags:    list[str] = field(default_factory=list)

    def for_platform(self, platform: str, tone: str = "analytical") -> str:
        """Return tone-appropriate text + hashtags trimmed to platform limit."""
        body = {
            "hype":        self.hype,
            "analytical":  self.analytical,
            "direct_cta":  self.direct_cta,
        }.get(tone, self.analytical)
        tags = " ".join("#" + t.lstrip("#") for t in self.hashtags[:8])
        out = f"{body}\n\n{tags}".strip()
        # Twitter hard cap
        if platform == "twitter" and len(out) > 280:
            out = out[:277] + "..."
        return out


_PROMPT_TEMPLATE = """\
You write social-media copy for SmartPickPro — a quantitative NBA prop-betting analytics brand.
The voice is sharp, confident, data-driven, never reckless. NEVER promise wins.

Asset type: {asset_type}
Context payload (JSON): {payload}

Generate exactly THREE copy variations and a hashtag set. Reply with valid JSON only:
{{
  "hype":        "...energetic, 1-2 emoji, builds FOMO, ≤200 chars",
  "analytical":  "...data-led tone, references the edge/numbers, ≤220 chars",
  "direct_cta":  "...single CTA pivot to scan QR / visit link, ≤180 chars",
  "hashtags":    ["NBA","PropBets","..."]   // 6-10 tags, no #
}}
Compliance: no guarantees, no '#1', no 'lock'. Always sound responsible.
"""


def generate_copy(asset_type: str, payload: dict[str, Any]) -> CopyVariants:
    """Call Gemini → return CopyVariants. Falls back to deterministic stubs if no key."""
    model = _get_model()
    if model is None:
        return _fallback(asset_type, payload)

    try:
        prompt = _PROMPT_TEMPLATE.format(asset_type=asset_type, payload=json.dumps(payload)[:4000])
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        data = json.loads(resp.text)
        return CopyVariants(
            hype=data.get("hype", "").strip(),
            analytical=data.get("analytical", "").strip(),
            direct_cta=data.get("direct_cta", "").strip(),
            hashtags=[t.lstrip("#") for t in data.get("hashtags", []) if t],
        )
    except Exception as e:
        _log.warning("Gemini copy generation failed: %s — using fallback", e)
        return _fallback(asset_type, payload)


def _fallback(asset_type: str, payload: dict[str, Any]) -> CopyVariants:
    """Deterministic stubs so the engine still runs without an API key."""
    if asset_type == "results":
        w = payload.get("wins", 0); l = payload.get("losses", 0)
        return CopyVariants(
            hype=f"🚀 {w}-{l} on the night. The model keeps cooking.",
            analytical=f"Yesterday's slate closed {w}W-{l}L. Edge-weighted picks continue to outperform baseline.",
            direct_cta="Tonight's slate drops in 3 hrs. Scan to lock in.",
            hashtags=["NBA", "PropBets", "PrizePicks", "Underdog", "DFS", "SportsBetting", "SmartPickPro"],
        )
    if asset_type == "slate":
        n = len(payload.get("picks", []))
        return CopyVariants(
            hype=f"⚡ Tonight's {n}-leg edge slate is LIVE. Quant-driven. Receipts always shown.",
            analytical=f"{n} prop edges flagged tonight by the Monte Carlo engine. All confidence ≥75%.",
            direct_cta="Today's free picks — scan the QR or hit the link in bio.",
            hashtags=["NBA", "NBAProps", "PrizePicks", "Underdog", "DFS", "Picks", "SmartPickPro"],
        )
    return CopyVariants(
        hype="The edge isn't luck. It's math. Join SmartPickPro 🧠⚡",
        analytical="Quantitative NBA prop analytics. 1,000 simulations per pick. Zero black boxes.",
        direct_cta="Free trial. Real edges. Tap the link → smartpickpro.app",
        hashtags=["NBA", "Analytics", "SportsBetting", "PropBets", "SmartPickPro"],
    )
