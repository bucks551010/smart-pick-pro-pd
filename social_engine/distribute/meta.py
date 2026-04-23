"""Meta Graph API distributors — Facebook Page, Instagram Business, Threads.

All three live under the same Page Access Token. IG and Threads require the image
to be publicly reachable (URL), not a file upload — so we expose the local _out/
directory via the Streamlit static-files server (or a CDN in prod).
"""
from __future__ import annotations
import logging
from pathlib import Path
import time

import requests

from config import SETTINGS
from distribute.base import PostResult

_log = logging.getLogger(__name__)
_API = "https://graph.facebook.com/v21.0"


def _public_image_url(image_path: Path) -> str:
    """Return a public URL for the given local image.

    PRODUCTION: serve _out/ via a CDN, signed URL, or your main app's static route.
    Set PUBLIC_ASSET_BASE_URL in env to override.
    """
    import os
    base = os.getenv("PUBLIC_ASSET_BASE_URL", "").rstrip("/")
    if base:
        return f"{base}/{image_path.name}"
    # Dev fallback — Streamlit's static directory if mounted at /app/static
    return f"{SETTINGS.brand_url.rstrip('/')}/static/{image_path.name}"


# ── FACEBOOK PAGE ────────────────────────────────────────────

class FacebookPoster:
    channel = "facebook"

    def is_configured(self) -> bool:
        return bool(SETTINGS.meta_token and SETTINGS.meta_page_id)

    def post(self, image_path: Path, text: str) -> PostResult:
        url = f"{_API}/{SETTINGS.meta_page_id}/photos"
        with image_path.open("rb") as f:
            r = requests.post(
                url,
                data={"caption": text, "access_token": SETTINGS.meta_token},
                files={"source": f},
                timeout=60,
            )
        r.raise_for_status()
        data = r.json()
        post_id = data.get("post_id") or data.get("id", "")
        return PostResult(True, self.channel, post_id=post_id,
                          url=f"https://facebook.com/{post_id}")


# ── INSTAGRAM BUSINESS ───────────────────────────────────────

class InstagramPoster:
    channel = "instagram"

    def is_configured(self) -> bool:
        return bool(SETTINGS.meta_token and SETTINGS.meta_ig_id)

    def post(self, image_path: Path, text: str) -> PostResult:
        # 1. Create media container
        create = requests.post(
            f"{_API}/{SETTINGS.meta_ig_id}/media",
            data={
                "image_url":   _public_image_url(image_path),
                "caption":     text,
                "access_token": SETTINGS.meta_token,
            },
            timeout=60,
        )
        create.raise_for_status()
        creation_id = create.json()["id"]

        # 2. Poll until container is FINISHED (IG quirk)
        for _ in range(8):
            status = requests.get(
                f"{_API}/{creation_id}",
                params={"fields": "status_code", "access_token": SETTINGS.meta_token},
                timeout=20,
            ).json()
            if status.get("status_code") == "FINISHED":
                break
            time.sleep(2)

        # 3. Publish
        pub = requests.post(
            f"{_API}/{SETTINGS.meta_ig_id}/media_publish",
            data={"creation_id": creation_id, "access_token": SETTINGS.meta_token},
            timeout=60,
        )
        pub.raise_for_status()
        media_id = pub.json()["id"]
        return PostResult(True, self.channel, post_id=media_id,
                          url=f"https://www.instagram.com/p/{media_id}")


# ── THREADS ──────────────────────────────────────────────────

class ThreadsPoster:
    channel = "threads"
    _BASE = "https://graph.threads.net/v1.0"

    def is_configured(self) -> bool:
        return bool(SETTINGS.meta_token and SETTINGS.meta_threads_id)

    def post(self, image_path: Path, text: str) -> PostResult:
        # 1. Create container
        create = requests.post(
            f"{self._BASE}/{SETTINGS.meta_threads_id}/threads",
            data={
                "media_type":  "IMAGE",
                "image_url":   _public_image_url(image_path),
                "text":        text,
                "access_token": SETTINGS.meta_token,
            },
            timeout=60,
        )
        create.raise_for_status()
        creation_id = create.json()["id"]
        time.sleep(3)  # Threads recommends ~3s wait before publish

        # 2. Publish
        pub = requests.post(
            f"{self._BASE}/{SETTINGS.meta_threads_id}/threads_publish",
            data={"creation_id": creation_id, "access_token": SETTINGS.meta_token},
            timeout=60,
        )
        pub.raise_for_status()
        post_id = pub.json()["id"]
        return PostResult(True, self.channel, post_id=post_id, url="")
