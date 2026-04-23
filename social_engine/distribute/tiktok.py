"""TikTok Content Posting API.

NOTE: TikTok's image-only "Photo Mode" posting requires the
PHOTO posting endpoint and a public image URL (no file upload).
For video posts, swap the endpoint and add MP4 generation upstream.
"""
from __future__ import annotations
import time
from pathlib import Path

import requests

from config import SETTINGS
from distribute.base import PostResult
from distribute.meta import _public_image_url


class TikTokPoster:
    channel = "tiktok"
    _BASE = "https://open.tiktokapis.com/v2/post/publish"

    def is_configured(self) -> bool:
        return bool(SETTINGS.tiktok_token and SETTINGS.tiktok_open_id)

    def post(self, image_path: Path, text: str) -> PostResult:
        # 1. Init photo upload
        init = requests.post(
            f"{self._BASE}/content/init/",
            headers={"Authorization": f"Bearer {SETTINGS.tiktok_token}"},
            json={
                "post_info": {
                    "title": text[:90],          # TikTok title cap
                    "description": text,
                    "disable_comment": False,
                    "auto_add_music": True,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "photo_cover_index": 0,
                    "photo_images": [_public_image_url(image_path)],
                },
                "post_mode": "DIRECT_POST",
                "media_type": "PHOTO",
            },
            timeout=60,
        )
        init.raise_for_status()
        publish_id = init.json()["data"]["publish_id"]

        # 2. Poll status until PUBLISH_COMPLETE
        for _ in range(10):
            status = requests.post(
                f"{self._BASE}/status/fetch/",
                headers={"Authorization": f"Bearer {SETTINGS.tiktok_token}"},
                json={"publish_id": publish_id},
                timeout=20,
            ).json()
            phase = status.get("data", {}).get("status", "")
            if phase == "PUBLISH_COMPLETE":
                return PostResult(True, self.channel, post_id=publish_id, url="")
            if phase == "FAILED":
                return PostResult(False, self.channel, post_id=publish_id,
                                  error=status.get("data", {}).get("fail_reason", "unknown"))
            time.sleep(3)

        return PostResult(False, self.channel, post_id=publish_id,
                          error="timeout waiting for PUBLISH_COMPLETE")
