"""Common Poster contract — every channel implements .post()."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class PostResult:
    ok:        bool
    channel:   str
    post_id:   str = ""
    url:       str = ""
    error:     str = ""


class Poster(Protocol):
    channel: str
    def is_configured(self) -> bool: ...
    def post(self, image_path: Path, text: str) -> PostResult: ...


def safe_post(poster: Poster, image_path: Path, text: str) -> PostResult:
    """Wrap .post() so a single channel failure never crashes the campaign."""
    if not poster.is_configured():
        return PostResult(False, poster.channel, error="not configured (missing credentials)")
    try:
        return poster.post(image_path, text)
    except Exception as exc:
        logging.getLogger(f"social.{poster.channel}").exception("Post failed")
        return PostResult(False, poster.channel, error=f"{type(exc).__name__}: {exc}")
