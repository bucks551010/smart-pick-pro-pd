"""X / Twitter — Tweepy v1.1 for media upload + v2 for tweet creation."""
from __future__ import annotations
from pathlib import Path

import tweepy

from config import SETTINGS
from distribute.base import PostResult


class TwitterPoster:
    channel = "twitter"

    def is_configured(self) -> bool:
        return all([
            SETTINGS.twitter_key, SETTINGS.twitter_secret,
            SETTINGS.twitter_token, SETTINGS.twitter_token_sec,
        ])

    def post(self, image_path: Path, text: str) -> PostResult:
        # v1.1 client for media upload (v2 still requires it)
        auth = tweepy.OAuth1UserHandler(
            SETTINGS.twitter_key, SETTINGS.twitter_secret,
            SETTINGS.twitter_token, SETTINGS.twitter_token_sec,
        )
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(filename=str(image_path))

        # v2 client for tweet creation
        client = tweepy.Client(
            consumer_key=SETTINGS.twitter_key,
            consumer_secret=SETTINGS.twitter_secret,
            access_token=SETTINGS.twitter_token,
            access_token_secret=SETTINGS.twitter_token_sec,
            bearer_token=SETTINGS.twitter_bearer or None,
        )
        resp = client.create_tweet(text=text[:280], media_ids=[media.media_id_string])
        tweet_id = resp.data["id"]
        return PostResult(
            ok=True, channel=self.channel,
            post_id=str(tweet_id),
            url=f"https://x.com/i/web/status/{tweet_id}",
        )

    def post_thread(self, tweets: list[str]) -> list["PostResult"]:
        """Post a text-only Twitter thread. First tweet is standalone; the rest are chained replies."""
        if not tweets:
            return []
        client = tweepy.Client(
            consumer_key=SETTINGS.twitter_key,
            consumer_secret=SETTINGS.twitter_secret,
            access_token=SETTINGS.twitter_token,
            access_token_secret=SETTINGS.twitter_token_sec,
            bearer_token=SETTINGS.twitter_bearer or None,
        )
        results: list[PostResult] = []
        reply_to_id: str | None = None
        for text in tweets:
            kwargs: dict = {"text": text[:280]}
            if reply_to_id:
                kwargs["in_reply_to_tweet_id"] = reply_to_id
            resp = client.create_tweet(**kwargs)
            tweet_id = str(resp.data["id"])
            reply_to_id = tweet_id
            results.append(PostResult(
                ok=True, channel=self.channel,
                post_id=tweet_id,
                url=f"https://x.com/i/web/status/{tweet_id}",
            ))
        return results
