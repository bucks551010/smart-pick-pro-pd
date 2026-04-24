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
        from google import genai
        _model = genai.Client(api_key=SETTINGS.gemini_api_key)
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

Asset type instructions:
- "results": Morning recap of last night's bets. Highlight wins count and mention that the
  winning props are shown so followers can verify each one. Reference win rate if strong.
- "slate": Pre-game picks post. Mention the platforms these picks are on (PrizePicks, Underdog,
  DK Pick6, etc.) so followers know where to act. Post goes out 2-3 hours before games tip off.
- "brand": Brand awareness CTA. Drive follows and free trial signups. 3x per week cadence.

Generate exactly THREE copy variations and a hashtag set. Reply with valid JSON only:
{{
  "hype":        "...energetic, 1-2 emoji, builds FOMO, ≤200 chars",
  "analytical":  "...data-led tone, references the edge/numbers, ≤220 chars",
  "direct_cta":  "...single CTA pivot to scan QR / visit link, ≤180 chars",
  "hashtags":    ["NBA","PropBets","..."]   // 6-10 tags, no #
}}
Compliance: no guarantees, no 'lock', no '#1 pick'. Always sound responsible.
"""


def generate_copy(asset_type: str, payload: dict[str, Any]) -> CopyVariants:
    """Call Gemini → return CopyVariants. Falls back to deterministic stubs if no key."""
    model = _get_model()
    if model is None:
        return _fallback(asset_type, payload)

    try:
        prompt = _PROMPT_TEMPLATE.format(asset_type=asset_type, payload=json.dumps(payload)[:4000])
        resp = model.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
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
        props = payload.get("winning_props", [])
        prop_line = f" | {props[0].get('player_name')} {props[0].get('stat_type')} {props[0].get('direction')} {props[0].get('prop_line')} ✅" if props else ""
        return CopyVariants(
            hype=f"🚀 {w}-{l} last night. All winning props shown — verify every one.{prop_line}",
            analytical=f"Last night's slate: {w}W-{l}L. Winning props listed — full transparency, always verifiable.",
            direct_cta=f"{w} winners last night. See the props, check the receipts. Tonight's picks drop soon.",
            hashtags=["NBA", "PropBets", "PrizePicks", "Underdog", "DFS", "SportsBetting", "SmartPickPro"],
        )
    if asset_type == "slate":
        n = len(payload.get("picks", []))
        platforms = payload.get("platforms", [])
        plat_str = " & ".join(platforms) if platforms else "PrizePicks/Underdog"
        return CopyVariants(
            hype=f"⚡ {n} picks LIVE on {plat_str}. Quant-driven. Receipts always shown.",
            analytical=f"{n} prop edges flagged tonight on {plat_str} by the Monte Carlo engine.",
            direct_cta=f"Tonight's picks on {plat_str} — scan the QR or hit the link in bio.",
            hashtags=["NBA", "NBAProps", "PrizePicks", "Underdog", "DFS", "Picks", "SmartPickPro"],
        )
    return CopyVariants(
        hype="The edge isn't luck. It's math. Join SmartPickPro 🧠⚡",
        analytical="Quantitative NBA prop analytics. 1,000 simulations per pick. Zero black boxes.",
        direct_cta="Free trial. Real edges. Tap the link → smartpickpro.app",
        hashtags=["NBA", "Analytics", "SportsBetting", "PropBets", "SmartPickPro"],
    )
