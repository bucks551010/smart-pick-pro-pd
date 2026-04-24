# API Credentials Setup Guide

Complete walk-through for every credential the social engine accepts.
Skip any section — the engine runs in demo mode without keys.

> ⚠️ **Never commit `.env` to git.** It is in `.gitignore`. Use Railway's
> **Variables** tab in production, not a checked-in file.

---

## 1. Google Gemini (LLM copy generation) — FREE

Free tier: **15 RPM, 1500 requests/day** — more than enough for daily posts.

1. Visit https://aistudio.google.com/app/apikey
2. Sign in with any Google account.
3. Click **Create API key** → choose any project (or "Create new").
4. Copy the key.

```env
GEMINI_API_KEY=AIzaSy...
```

---

## 2. X / Twitter (Tweepy)

Required tier: **Basic** ($100/mo) or **Free** (50 posts/day, no media).
For image posts you need at least **Basic**.

1. Apply at https://developer.x.com/en/portal/dashboard
2. Create a **Project** → create an **App** inside it.
3. In the App's **User authentication settings**:
   - App permissions: **Read and write**
   - Type of App: **Web app, automated app or bot**
   - Callback URL: `https://your-app.railway.app/oauth/callback` (placeholder OK)
4. Tab **Keys and tokens**:
   - Generate **API Key** + **API Key Secret** → save
   - Generate **Access Token** + **Access Token Secret** (must be R/W) → save
   - Copy **Bearer Token** → save

```env
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_BEARER_TOKEN=...
```

---

## 3. Meta Graph API — Facebook + Instagram + Threads

> All three live under the **same Page Access Token**, but each requires
> different prerequisites. Read all three before starting.

### 3a. Prerequisites
1. A **Facebook Page** you own.
2. A **Facebook App** at https://developers.facebook.com → Create App → "Business".
3. Add product **Facebook Login for Business** + **Instagram Graph API** + **Threads API** (Threads is currently in beta — request access).
4. Switch your app to **Live mode** when ready.

### 3b. Get a long-lived Page Access Token
1. Open https://developers.facebook.com/tools/explorer
2. Choose your App.
3. Under **User or Page**, pick your Page.
4. Add permissions:
   - `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
   - `instagram_basic`, `instagram_content_publish`
   - `threads_basic`, `threads_content_publish` (if Threads access granted)
5. Click **Generate Access Token** → exchange it for a long-lived token:
   ```
   GET https://graph.facebook.com/v21.0/oauth/access_token
       ?grant_type=fb_exchange_token
       &client_id={app-id}
       &client_secret={app-secret}
       &fb_exchange_token={short-lived-token}
   ```
   The returned token is a 60-day Page token — refresh before it expires.

### 3c. Get the IDs
```
GET https://graph.facebook.com/v21.0/me/accounts?access_token={token}
   → returns { data: [{ id: "<META_PAGE_ID>", ... }] }

GET https://graph.facebook.com/v21.0/{META_PAGE_ID}?fields=instagram_business_account,connected_threads_user
   → instagram_business_account.id  → META_INSTAGRAM_BUSINESS_ID
   → connected_threads_user.id       → META_THREADS_USER_ID
```

```env
META_PAGE_ACCESS_TOKEN=EAAG...
META_PAGE_ID=12345...
META_INSTAGRAM_BUSINESS_ID=178414...
META_THREADS_USER_ID=98765...
```

### 3d. ⚠️ Public image hosting

Instagram + Threads APIs require the image as a **public URL** (no file upload).
Set `PUBLIC_ASSET_BASE_URL` to wherever you serve `social_engine/_out/` from.

For Railway, the simplest options:
- Mount `_out/` to a Railway volume + serve via your main app's static route
- Push to S3/Cloudflare R2 and set `PUBLIC_ASSET_BASE_URL=https://cdn.yourdomain.com`

```env
PUBLIC_ASSET_BASE_URL=https://cdn.smartpickpro.ai/social
```

---

## 4. TikTok Content Posting API

1. Apply at https://developers.tiktok.com → Create app.
2. Add product **Content Posting API**.
3. Configure scopes: `video.publish`, `video.upload`, `user.info.basic`.
4. Submit for **Direct Post** access (review takes ~3-7 days).
5. After approval, complete OAuth to get an `access_token` and `open_id`.

```env
TIKTOK_ACCESS_TOKEN=act.xxx
TIKTOK_OPEN_ID=...
```

---

## 5. Webhook security

Generate a long random secret used to authenticate calls from your main app
to the worker's `/trigger/*` endpoints.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```env
WEBHOOK_SHARED_SECRET=<paste output here>
```

---

## 6. Database connection

Point the social engine at the **same** database your main app writes to.
The engine only reads from `all_analysis_picks`, `bets`, and `games`.

```env
# Postgres (recommended for production)
DATABASE_URL=postgres://user:password@host:5432/smartpickpro

# SQLite (dev only)
DATABASE_URL=sqlite:////app/db/smartai_nba.db
```

If your main app is on Railway with Postgres, copy the `DATABASE_URL` from
the Postgres service's Variables tab into both Social Engine services.

---

## Verification

After filling `.env`, run:

```bash
streamlit run app.py
```

The sidebar **DEPLOY CAMPAIGN** report will show `❌ <channel> — not configured`
for any platform whose credentials are missing — non-fatal, the rest still post.
