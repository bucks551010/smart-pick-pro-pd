"""High-level campaign deploy: render → distribute across all enabled channels."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Iterable

from config import CHANNEL_SIZE
from distribute.base import PostResult, safe_post
from distribute.twitter import TwitterPoster
from distribute.meta import FacebookPoster, InstagramPoster, ThreadsPoster
from distribute.tiktok import TikTokPoster

_log = logging.getLogger(__name__)

_REGISTRY = {
    "twitter":   TwitterPoster(),
    "facebook":  FacebookPoster(),
    "instagram": InstagramPoster(),
    "threads":   ThreadsPoster(),
    "tiktok":    TikTokPoster(),
}


def _is_carousel(images_by_size: dict[str, Path]) -> bool:
    """True when keys are slide_NN (carousel output from app.py)."""
    return bool(images_by_size) and all(k.startswith("slide_") for k in images_by_size)


def deploy_campaign(
    images_by_size: dict[str, Path],
    text_by_channel: dict[str, str],
    channels: Iterable[str],
) -> list[PostResult]:
    """For each channel, pick the right-sized image + tone-shaped text, then post.

    When images_by_size contains slide_NN keys (carousel), Instagram receives a
    full multi-slide carousel post; all other channels receive the cover slide.
    """
    is_carousel = _is_carousel(images_by_size)
    carousel_slides = list(images_by_size.values()) if is_carousel else []

    results: list[PostResult] = []
    for ch in channels:
        poster = _REGISTRY.get(ch)
        if poster is None:
            results.append(PostResult(False, ch, error=f"unknown channel '{ch}'"))
            continue

        text = text_by_channel.get(ch, "")

        if is_carousel:
            if ch == "instagram":
                # Full multi-slide carousel via Graph API
                ig: InstagramPoster = _REGISTRY["instagram"]  # type: ignore[assignment]
                if not ig.is_configured():
                    results.append(PostResult(False, ch, error="not configured (missing credentials)"))
                else:
                    try:
                        results.append(ig.post_carousel(carousel_slides, text))
                    except Exception as exc:
                        _log.exception("Instagram carousel post failed")
                        results.append(PostResult(False, ch, error=f"{type(exc).__name__}: {exc}"))
                continue
            else:
                # Non-IG channels: post the cover slide (slide_01) as a single image
                img = carousel_slides[0] if carousel_slides else None
        else:
            size_key = CHANNEL_SIZE.get(ch, "square")
            img = images_by_size.get(size_key) or next(iter(images_by_size.values()), None)

        if img is None:
            results.append(PostResult(False, ch, error="no image rendered for this channel"))
            continue

        results.append(safe_post(poster, img, text))
    return results
