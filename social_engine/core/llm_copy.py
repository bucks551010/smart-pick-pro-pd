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
from core.brand_voice import (
    VOICE_GUIDELINES, BRAND_NAME, ENGINE_NAME, ENGINE_VERSION, SCORE_NAME,
    TAGLINES, get_hashtags,
)

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
{voice_guidelines}

═══ TASK ═══
Asset type: {asset_type}
Context payload (JSON): {payload}

Asset type instructions:
- "results": Morning recap — post WINS count prominently, mention that all winning props
  are shown publicly for verification. Reference win rate if above 60%. Lead with the
  transparency angle ("receipts on file", "verify every one").
- "slate": Pre-game post — mention the specific platforms (PrizePicks, Underdog, DK Pick6).
  Reference the QME engine and edge percentages where available. Post goes out 2-3 hrs pre-tip.
- "weekly": Sunday scorecard — full week W-L record. Emphasize the receipts/transparency angle.
  Show the math (win rate %, ROI if positive).
- "brand": Brand awareness — drive free trial signups & follows. Rotate angles:
  transparency, engine authority, math/edge, no-black-box, receipts culture.

Generate exactly THREE copy variations and a hashtag set. Reply with valid JSON only:
{{
  "hype":        "...high energy, 1-2 emoji max, urgency/FOMO, ≤200 chars",
  "analytical":  "...data-led, references engine/score/edge numbers, ≤220 chars",
  "direct_cta":  "...one clear action (link in bio / scan QR / free trial), ≤180 chars",
  "hashtags":    ["NBA","PropBets","..."]   // 6-10 tags, no # prefix
}}
Hard rules: no 'lock', no 'guaranteed', no '#1 pick', no 'can\'t miss'.
Always include a transparency or responsible gambling signal.
"""


def generate_copy(asset_type: str, payload: dict[str, Any]) -> CopyVariants:
    """Call Gemini → return CopyVariants. Falls back to deterministic stubs if no key."""
    model = _get_model()
    if model is None:
        return _fallback(asset_type, payload)

    try:
        prompt = _PROMPT_TEMPLATE.format(
            voice_guidelines=VOICE_GUIDELINES,
            asset_type=asset_type,
            payload=json.dumps(payload)[:4000],
        )
        resp = model.models.generate_content(
            model="models/gemini-2.5-flash",
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
    """Brand-voice-aligned stubs — used when Gemini is unavailable."""
    if asset_type == "results":
        w = payload.get("wins", 0); l = payload.get("losses", 0)
        wr = payload.get("win_rate", 0.0)
        props = payload.get("winning_props", [])
        first = f" — {props[0].get('player_name')} {props[0].get('direction')} {props[0].get('prop_line')} ✅" if props else ""
        rate_txt = f" ({wr:.0f}% win rate)" if wr >= 60 else ""
        return CopyVariants(
            hype=f"🧾 {w}-{l} last night{rate_txt}. Every pick posted publicly — verify each one yourself.{first}",
            analytical=(
                f"Last night: {w}W-{l}L{rate_txt}. {ENGINE_NAME} {ENGINE_VERSION} — "
                f"full results posted, zero hidden losses. {TAGLINES['transparency']}"
            ),
            direct_cta=(
                f"{w} wins last night. All {w + l} picks shown — receipts always on file. "
                f"Tonight's analysis drops soon → {TAGLINES['cta']}"
            ),
            hashtags=get_hashtags("results"),
        )
    if asset_type == "weekly":
        w = payload.get("wins", 0); l = payload.get("losses", 0)
        wr = payload.get("win_rate", 0.0)
        roi = payload.get("roi_pct")
        roi_txt = f" | +{roi:.1f}% ROI" if roi and roi > 0 else ""
        return CopyVariants(
            hype=f"📊 {w}-{l} this week ({wr:.0f}% win rate{roi_txt}). Every pick verified — receipts on file.",
            analytical=(
                f"Weekly scorecard: {w}W-{l}L | {wr:.0f}% win rate{roi_txt}. "
                f"{ENGINE_NAME} {ENGINE_VERSION}. All picks posted — wins AND losses. Always."
            ),
            direct_cta=f"{w} wins this week. Full record posted → {TAGLINES['transparency']}",
            hashtags=get_hashtags("weekly"),
        )
    if asset_type == "slate":
        picks = payload.get("picks", [])
        n = len(picks)
        platforms = payload.get("platforms", [])
        plat_str = " & ".join(platforms) if platforms else "PrizePicks / Underdog"
        top = picks[0] if picks else {}
        top_line = (
            f" Top edge: {top.get('player_name')} {top.get('direction')} "
            f"{top.get('prop_line')} @ {top.get('confidence_score', 0):.0f}% SAFE Score."
        ) if top else ""
        return CopyVariants(
            hype=f"⚡ {n} Quantum edges live on {plat_str}.{top_line} Receipts always posted.",
            analytical=(
                f"{n} props flagged by {ENGINE_NAME} {ENGINE_VERSION} on {plat_str}. "
                f"{SCORE_NAME} driven. {TAGLINES['authority']}"
            ),
            direct_cta=(
                f"Tonight's {n} picks on {plat_str} — link in bio. "
                f"{TAGLINES['primary']}"
            ),
            hashtags=get_hashtags("slate"),
        )
    # brand / default
    return CopyVariants(
        hype=f"🧠⚡ {TAGLINES['primary']} {ENGINE_NAME} {ENGINE_VERSION} — free trial now.",
        analytical=(
            f"{ENGINE_NAME} {ENGINE_VERSION}: 1,000+ Quantum simulations per NBA prop. "
            f"{SCORE_NAME}. {TAGLINES['authority']}"
        ),
        direct_cta=f"{TAGLINES['cta']} → {BRAND_NAME}.app",
        hashtags=get_hashtags("brand"),
    )
