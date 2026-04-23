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


def deploy_campaign(
    images_by_size: dict[str, Path],
    text_by_channel: dict[str, str],
    channels: Iterable[str],
) -> list[PostResult]:
    """For each channel, pick the right-sized image + tone-shaped text, then post."""
    results: list[PostResult] = []
    for ch in channels:
        poster = _REGISTRY.get(ch)
        if poster is None:
            results.append(PostResult(False, ch, error=f"unknown channel '{ch}'"))
            continue

        size_key = CHANNEL_SIZE.get(ch, "square")
        img = images_by_size.get(size_key) or next(iter(images_by_size.values()), None)
        if img is None:
            results.append(PostResult(False, ch, error="no image rendered for this channel"))
            continue

        text = text_by_channel.get(ch, "")
        results.append(safe_post(poster, img, text))
    return results
