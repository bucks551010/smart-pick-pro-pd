"""
Credential tester for the social engine.
Reads from social_engine/.env and pings each API with a read-only call.
Does NOT post anything.

Usage (from repo root):
    cd social_engine
    python scripts/test_credentials.py
"""

import os
import sys
from pathlib import Path

# ── Load .env from social_engine/ ─────────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())
else:
    print(f"⚠  No .env found at {_env_path} — using existing environment variables\n")

# ── Helpers ────────────────────────────────────────────────────────────────────
def ok(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  ✅  {label}{suffix}")

def fail(label: str, reason: str) -> None:
    print(f"  ❌  {label}  →  {reason}")

def skip(label: str, reason: str) -> None:
    print(f"  ⏭   {label}  →  {reason}")

# ── Gemini ─────────────────────────────────────────────────────────────────────
def test_gemini() -> None:
    print("\n── Gemini ──────────────────────────────────────────────────────────────")
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        skip("Gemini", "GEMINI_API_KEY not set")
        return
    try:
        from google import genai  # type: ignore
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents="Reply with the single word: OK",
        )
        text = resp.text.strip()
        ok("Gemini 2.5 Flash", f"response: {text[:40]}")
    except Exception as exc:
        fail("Gemini", str(exc))

# ── Twitter / X ────────────────────────────────────────────────────────────────
def test_twitter() -> None:
    print("\n── Twitter / X ─────────────────────────────────────────────────────────")
    api_key    = os.getenv("TWITTER_API_KEY", "")
    api_secret = os.getenv("TWITTER_API_SECRET", "")
    at         = os.getenv("TWITTER_ACCESS_TOKEN", "")
    at_secret  = os.getenv("TWITTER_ACCESS_SECRET", "")

    missing = [n for n, v in [
        ("TWITTER_API_KEY", api_key),
        ("TWITTER_API_SECRET", api_secret),
        ("TWITTER_ACCESS_TOKEN", at),
        ("TWITTER_ACCESS_SECRET", at_secret),
    ] if not v]

    if missing:
        skip("Twitter", f"missing: {', '.join(missing)}")
        return

    try:
        import tweepy  # type: ignore
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, at, at_secret)
        api  = tweepy.API(auth)
        me   = api.verify_credentials()
        ok("Twitter OAuth1 (v1.1)", f"@{me.screen_name}")
    except Exception as exc:
        fail("Twitter", str(exc))

    # v2 client check
    bearer = os.getenv("TWITTER_BEARER_TOKEN", "")
    if bearer:
        try:
            client = tweepy.Client(bearer_token=bearer)
            resp   = client.get_me()
            ok("Twitter v2 client", f"user id: {resp.data.id}")
        except Exception as exc:
            fail("Twitter v2 client", str(exc))
    else:
        skip("Twitter v2 Bearer", "TWITTER_BEARER_TOKEN not set (optional for posting)")

# ── Facebook ───────────────────────────────────────────────────────────────────
def test_facebook() -> None:
    print("\n── Facebook ────────────────────────────────────────────────────────────")
    token   = os.getenv("META_PAGE_ACCESS_TOKEN", "")
    page_id = os.getenv("META_PAGE_ID", "")

    if not token or not page_id:
        skip("Facebook", "META_PAGE_ACCESS_TOKEN or META_PAGE_ID not set")
        return

    try:
        import requests  # type: ignore
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{page_id}",
            params={"fields": "id,name,fan_count", "access_token": token},
            timeout=10,
        )
        data = r.json()
        if "error" in data:
            fail("Facebook Page", data["error"].get("message", str(data["error"])))
        else:
            ok("Facebook Page", f"{data.get('name')}  (fans: {data.get('fan_count','?')})")
    except Exception as exc:
        fail("Facebook", str(exc))

# ── Instagram ──────────────────────────────────────────────────────────────────
def test_instagram() -> None:
    print("\n── Instagram ───────────────────────────────────────────────────────────")
    token   = os.getenv("META_PAGE_ACCESS_TOKEN", "")
    ig_id   = os.getenv("META_INSTAGRAM_BUSINESS_ID", "")

    if not token or not ig_id:
        skip("Instagram", "META_PAGE_ACCESS_TOKEN or META_INSTAGRAM_BUSINESS_ID not set")
        return

    try:
        import requests  # type: ignore
        r = requests.get(
            f"https://graph.facebook.com/v21.0/{ig_id}",
            params={"fields": "id,username,followers_count", "access_token": token},
            timeout=10,
        )
        data = r.json()
        if "error" in data:
            fail("Instagram Business", data["error"].get("message", str(data["error"])))
        else:
            ok("Instagram Business", f"@{data.get('username')}  (followers: {data.get('followers_count','?')})")
    except Exception as exc:
        fail("Instagram", str(exc))

# ── Token expiry check ─────────────────────────────────────────────────────────
def test_token_expiry() -> None:
    print("\n── Token expiry ────────────────────────────────────────────────────────")
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "")
    if not token:
        skip("Token debug", "META_PAGE_ACCESS_TOKEN not set")
        return
    try:
        import requests  # type: ignore
        r = requests.get(
            "https://graph.facebook.com/debug_token",
            params={"input_token": token, "access_token": token},
            timeout=10,
        )
        data = r.json().get("data", {})
        if not data:
            fail("Token debug", str(r.json()))
            return
        token_type   = data.get("type", "?")
        expires_at   = data.get("expires_at", 0)
        is_valid     = data.get("is_valid", False)
        scopes       = data.get("scopes", [])

        status = "never expires" if expires_at == 0 else f"expires: {expires_at}"
        validity = "valid" if is_valid else "INVALID"
        ok("Token type", f"{token_type}  |  {validity}  |  {status}")

        required = {"pages_manage_posts", "pages_show_list",
                    "instagram_basic", "instagram_content_publish"}
        missing  = required - set(scopes)
        present  = required & set(scopes)
        if present:
            ok("Scopes present", ", ".join(sorted(present)))
        if missing:
            fail("Scopes missing", ", ".join(sorted(missing)))
    except Exception as exc:
        fail("Token debug", str(exc))

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Smart Pick Pro — Social Engine Credential Tester")
    print("  Read-only checks. Nothing will be posted.")
    print("=" * 60)

    test_gemini()
    test_twitter()
    test_facebook()
    test_instagram()
    test_token_expiry()

    print("\n" + "=" * 60)
    print("  Done. Fix any ❌ above before deploying the worker.")
    print("=" * 60 + "\n")
