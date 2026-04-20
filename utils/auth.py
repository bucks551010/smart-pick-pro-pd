# ============================================================
# FILE: utils/auth.py
# PURPOSE: Lightweight session-based authentication for
#          SmartBetPro NBA's subscription system.
#
# HOW IT WORKS:
#   • After a Stripe Checkout redirect, the URL contains
#     ?session_id=XXX which we capture via st.query_params.
#   • We verify the session with Stripe, store the sub details
#     in Streamlit session state AND in the SQLite database.
#   • On each page load, is_premium_user() checks session state
#     first (fast), then the database (slow), then Stripe API
#     (slowest — only when needed).
#   • Returning users can restore their session by entering
#     the email they used when subscribing.
#
# FREE TIER:
#   When Stripe is not configured (STRIPE_SECRET_KEY missing),
#   is_premium_user() returns True so all features are unlocked.
#   This is the "developer / free demo" mode.
#
# NON-PRODUCTION BYPASS:
#   When the SMARTAI_PRODUCTION env var is absent or not "true",
#   is_premium_user() returns True regardless of Stripe status.
#   Set SMARTAI_PRODUCTION=true to enforce subscription checks.
# ============================================================

import os
import logging
import streamlit as st
import datetime

_logger = logging.getLogger(__name__)

# ── Startup Warning: Detect misconfigured production state ────
# If STRIPE_SECRET_KEY is set but SMARTAI_PRODUCTION is not "true",
# that means real Stripe keys are active but premium gates are disabled.
if os.environ.get("STRIPE_SECRET_KEY") and os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
    _logger.warning(
        "⚠️  STRIPE_SECRET_KEY is set but SMARTAI_PRODUCTION is not 'true'. "
        "Premium features are NOT gated. Set SMARTAI_PRODUCTION=true for live deployments."
    )

from utils.stripe_manager import (
    is_stripe_configured,
    verify_checkout_session,
    get_subscription_by_id,
    get_subscription_by_email,
)
from tracking.database import (
    initialize_database,
    get_database_connection,
)

# ── PostgreSQL subscription support ──────────────────────────
# When Railway PostgreSQL is connected, subscriptions are stored
# there instead of (and in addition to) the SQLite database, so
# they survive container restarts and volume-less deployments.
_PG_SUB_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
_HAS_PG_SUB = False
if _PG_SUB_URL:
    try:
        import psycopg2 as _psycopg2          # type: ignore
        import psycopg2.extras as _psycopg2x  # type: ignore
        _HAS_PG_SUB = True
    except ImportError:
        pass

_pg_sub_initialized = False

def _ensure_pg_subscriptions_table() -> None:
    """Create the subscriptions table in PostgreSQL if it doesn't exist."""
    global _pg_sub_initialized
    if _pg_sub_initialized or not _HAS_PG_SUB:
        return
    try:
        conn = _psycopg2.connect(_PG_SUB_URL)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    customer_email TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    plan_name TEXT DEFAULT 'Premium',
                    current_period_start TEXT,
                    current_period_end TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
        conn.commit()
        conn.close()
        _pg_sub_initialized = True
    except Exception as exc:
        _logger.error("Failed to init PG subscriptions table: %s", exc)

# ============================================================
# SECTION: Session State Keys
# ============================================================

# These are the keys we use to store subscription info in
# Streamlit's session state (like a temporary memory store).
_SS_IS_PREMIUM        = "_sub_is_premium"       # bool
_SS_SUBSCRIPTION_ID   = "_sub_subscription_id"  # str (sub_XXX)
_SS_CUSTOMER_ID       = "_sub_customer_id"       # str (cus_XXX)
_SS_CUSTOMER_EMAIL    = "_sub_customer_email"    # str
_SS_PLAN_NAME         = "_sub_plan_name"         # str
_SS_PERIOD_END        = "_sub_period_end"        # str (ISO date)
_SS_STATUS            = "_sub_status"            # str
_SS_VERIFIED_AT       = "_sub_verified_at"       # float (timestamp)

# How long (in seconds) to cache the premium status before
# re-checking Stripe API.  30 minutes = 1800 seconds.
_CACHE_TTL_SECONDS = 1800


# ============================================================
# SECTION: Database Helpers
# ============================================================

def _save_subscription_to_db(sub_data: dict) -> bool:
    """
    Save or update a subscription record in the SQLite database.

    This persists the subscription so returning users can be
    identified even after their Streamlit session expires.

    Args:
        sub_data (dict): Must contain at minimum:
                         subscription_id, customer_id, status.

    Returns:
        bool: True if saved successfully.
    """
    subscription_id = sub_data.get("subscription_id", "")
    if not subscription_id:
        return False

    params = (
        subscription_id,
        sub_data.get("customer_id", ""),
        sub_data.get("customer_email", ""),
        sub_data.get("status", "active"),
        sub_data.get("plan_name", "Premium"),
        sub_data.get("period_start", ""),
        sub_data.get("period_end", ""),
    )

    # ── Write to PostgreSQL when available ────────────────────
    if _HAS_PG_SUB:
        try:
            _ensure_pg_subscriptions_table()
            conn = _psycopg2.connect(_PG_SUB_URL)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subscriptions
                        (subscription_id, customer_id, customer_email,
                         status, plan_name,
                         current_period_start, current_period_end,
                         updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT(subscription_id) DO UPDATE SET
                        status               = EXCLUDED.status,
                        customer_email       = EXCLUDED.customer_email,
                        current_period_start = EXCLUDED.current_period_start,
                        current_period_end   = EXCLUDED.current_period_end,
                        updated_at           = NOW()
                    """,
                    params,
                )
            conn.commit()
            conn.close()
            return True
        except Exception as exc:
            _logger.error("Failed to save subscription to PG: %s", exc)

    # ── Fallback: SQLite ──────────────────────────────────────
    try:
        initialize_database()
        with get_database_connection() as conn:
            conn.execute(
                """
                INSERT INTO subscriptions
                    (subscription_id, customer_id, customer_email,
                     status, plan_name,
                     current_period_start, current_period_end,
                     updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(subscription_id) DO UPDATE SET
                    status               = excluded.status,
                    customer_email       = excluded.customer_email,
                    current_period_start = excluded.current_period_start,
                    current_period_end   = excluded.current_period_end,
                    updated_at           = datetime('now')
                """,
                params,
            )
            conn.commit()
        return True
    except Exception as exc:
        _logger.error("Failed to save subscription to DB: %s", exc)
        return False


def _load_subscription_from_db(subscription_id: str) -> dict | None:
    """
    Load a subscription record from the SQLite database.

    Args:
        subscription_id (str): Stripe Subscription ID.

    Returns:
        dict or None: Subscription row as a dict, or None if not found.
    """
    if not subscription_id:
        return None
    try:
        initialize_database()
        with get_database_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM subscriptions WHERE subscription_id = ?",
                (subscription_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
    except Exception as exc:
        _logger.error("Failed to load subscription from DB: %s", exc)
    return None


def _load_subscription_by_email_from_db(email: str) -> dict | None:
    """
    Look up a subscription in the local DB by customer email.

    Args:
        email (str): Customer's email address.

    Returns:
        dict or None: Most recent active subscription row, or None.
    """
    if not email:
        return None

    # ── Check PostgreSQL first when available ─────────────────
    if _HAS_PG_SUB:
        try:
            _ensure_pg_subscriptions_table()
            conn = _psycopg2.connect(
                _PG_SUB_URL,
                cursor_factory=_psycopg2x.RealDictCursor,
            )
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM subscriptions
                    WHERE customer_email = %s
                      AND status IN ('active', 'trialing')
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (email,),
                )
                row = cur.fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception as exc:
            _logger.error("Failed to look up subscription by email in PG: %s", exc)

    # ── Fallback: SQLite ──────────────────────────────────────
    try:
        initialize_database()
        with get_database_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE customer_email = ?
                  AND status IN ('active', 'trialing')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (email,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
    except Exception as exc:
        _logger.error("Failed to look up subscription by email: %s", exc)
    return None


# ============================================================
# SECTION: Session State Helpers
# ============================================================

def _store_premium_in_session(sub_info: dict) -> None:
    """
    Write subscription details into Streamlit session state.

    Args:
        sub_info (dict): Subscription info dict with keys matching
                         _SS_* constants above.
    """
    import time
    st.session_state[_SS_IS_PREMIUM]      = True
    st.session_state[_SS_SUBSCRIPTION_ID] = sub_info.get("subscription_id", "")
    st.session_state[_SS_CUSTOMER_ID]     = sub_info.get("customer_id", "")
    st.session_state[_SS_CUSTOMER_EMAIL]  = sub_info.get("customer_email", "")
    st.session_state[_SS_PLAN_NAME]       = sub_info.get("plan_name", "Premium")
    st.session_state[_SS_PERIOD_END]      = sub_info.get("period_end", "")
    st.session_state[_SS_STATUS]          = sub_info.get("status", "active")
    st.session_state[_SS_VERIFIED_AT]     = time.time()


def _clear_premium_from_session() -> None:
    """Remove all premium subscription data from session state."""
    for key in (
        _SS_IS_PREMIUM, _SS_SUBSCRIPTION_ID, _SS_CUSTOMER_ID,
        _SS_CUSTOMER_EMAIL, _SS_PLAN_NAME, _SS_PERIOD_END,
        _SS_STATUS, _SS_VERIFIED_AT,
    ):
        st.session_state.pop(key, None)


def _is_cache_fresh() -> bool:
    """
    Check if the cached premium status is still valid.

    Returns:
        bool: True if the cache is less than _CACHE_TTL_SECONDS old.
    """
    import time
    verified_at = st.session_state.get(_SS_VERIFIED_AT, 0)
    if not verified_at:
        return False
    return (time.time() - verified_at) < _CACHE_TTL_SECONDS


# ============================================================
# SECTION: Checkout Session Capture (URL param handling)
# ============================================================

def handle_checkout_redirect() -> bool:
    """
    Check if the current page URL contains a Stripe Checkout
    session_id parameter and process it if found.

    Call this at the top of the Premium page (and optionally
    on app.py) to capture returning users after payment.

    Returns:
        bool: True if a new subscription was successfully activated.
    """
    params = st.query_params
    session_id = params.get("session_id", "")
    if not session_id:
        return False

    # Don't re-process if we already handled this session
    if st.session_state.get("_checkout_session_processed") == session_id:
        return st.session_state.get(_SS_IS_PREMIUM, False)

    # Verify with Stripe
    result = verify_checkout_session(session_id)
    if not result.get("success"):
        return False

    # Store in session state
    _store_premium_in_session(result)

    # Persist to database
    _save_subscription_to_db(result)

    # Mark session as processed so we don't re-verify on reruns
    st.session_state["_checkout_session_processed"] = session_id

    return True


# ============================================================
# SECTION: Core Premium Check
# ============================================================

def is_premium_user() -> bool:
    """
    Check if the current session has an active premium subscription.

    Check order (fastest to slowest):
      0. Non-production bypass → return True (all features unlocked).
      1. If Stripe is NOT configured → return True (free/dev mode).
      2. Session state cache (if fresh) → return cached value.
      3. Database lookup (using stored subscription_id).
      4. Stripe API re-verification (last resort, updates cache).

    Returns:
        bool: True if the user has an active premium subscription.
    """
    # ── Layer 0: Non-production bypass — all features unlocked ─
    # In development / staging, skip subscription enforcement so
    # every feature is accessible.  To enforce subscriptions in
    # production, set the environment variable:
    #     SMARTAI_PRODUCTION=true
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        _logger.debug("Premium bypass active — SMARTAI_PRODUCTION is not set")
        return True

    # ── Layer 1: Dev/demo mode — no Stripe configured ─────────
    if not is_stripe_configured():
        _logger.debug("Premium gate: granted (Stripe not configured)")
        return True  # Everything is free when Stripe isn't set up

    # ── Layer 2: Fresh session state cache ────────────────────
    if _is_cache_fresh() and st.session_state.get(_SS_IS_PREMIUM) is True:
        return True

    # ── Layer 2b: Handle incoming checkout redirect ────────────
    if handle_checkout_redirect():
        return True

    # ── Layer 3: Database check using stored sub_id ──────────
    subscription_id = st.session_state.get(_SS_SUBSCRIPTION_ID, "")
    if subscription_id:
        db_row = _load_subscription_from_db(subscription_id)
        if db_row and db_row.get("status") in ("active", "trialing"):
            # One-time payments (Insider Circle) use a synthetic ID
            # prefixed with "otp_" — these are perpetual and don't
            # need Stripe re-verification.
            if subscription_id.startswith("otp_"):
                _store_premium_in_session({
                    "subscription_id": subscription_id,
                    "customer_id": db_row.get("customer_id", ""),
                    "customer_email": db_row.get("customer_email", ""),
                    "plan_name": db_row.get("plan_name", "Insider Circle"),
                    "period_end": "",
                    "status": "active",
                })
                return True

            # Re-verify with Stripe if cache is stale
            result = get_subscription_by_id(subscription_id)
            if result.get("is_active"):
                # Update cache with fresh data
                _store_premium_in_session({
                    "subscription_id": subscription_id,
                    "customer_id": db_row.get("customer_id", ""),
                    "customer_email": db_row.get("customer_email", ""),
                    "plan_name": db_row.get("plan_name", "Premium"),
                    "period_end": result.get("period_end", ""),
                    "status": result.get("status", "active"),
                })
                return True
            else:
                # Subscription is no longer active
                _clear_premium_from_session()
                return False

    # ── Layer 4: User is not premium ─────────────────────────
    _logger.debug("Premium gate: denied (no active subscription found)")
    return False


def get_subscription_status() -> dict:
    """
    Get detailed subscription status for the current session.

    Returns:
        dict with keys:
            is_premium    (bool):  Whether user is premium.
            plan_name     (str):   Plan name (e.g., "Premium").
            status        (str):   Stripe status (e.g., "active").
            period_end    (str):   ISO date of next billing date.
            customer_email (str):  Customer email.
            stripe_configured (bool): Whether Stripe is set up.
    """
    stripe_configured = is_stripe_configured()
    premium = is_premium_user()

    return {
        "is_premium": premium,
        "plan_name": st.session_state.get(_SS_PLAN_NAME, "Premium"),
        "status": st.session_state.get(_SS_STATUS, "active" if not stripe_configured else ""),
        "period_end": st.session_state.get(_SS_PERIOD_END, ""),
        "customer_email": st.session_state.get(_SS_CUSTOMER_EMAIL, ""),
        "stripe_configured": stripe_configured,
    }


def restore_subscription_by_email(email: str) -> bool:
    """
    Allow a returning user to restore their premium access by
    entering the email they used when subscribing.

    Check order:
      1. Local database (fast, no API call).
      2. Stripe API (if not in local DB).

    Args:
        email (str): Customer email address.

    Returns:
        bool: True if an active subscription was found and restored.
    """
    if not email or not email.strip():
        return False

    email = email.strip().lower()

    # ── Check local DB first ──────────────────────────────────
    db_row = _load_subscription_by_email_from_db(email)
    if db_row and db_row.get("status") in ("active", "trialing"):
        subscription_id = db_row.get("subscription_id", "")
        # One-time payments (otp_ prefix) are perpetual — skip Stripe check
        if subscription_id.startswith("otp_"):
            _store_premium_in_session({
                "subscription_id": subscription_id,
                "customer_id": db_row.get("customer_id", ""),
                "customer_email": email,
                "plan_name": db_row.get("plan_name", "Insider Circle"),
                "period_end": "",
                "status": "active",
            })
            return True
        # Re-verify with Stripe to ensure still active
        if is_stripe_configured() and subscription_id:
            result = get_subscription_by_id(subscription_id)
            if not result.get("is_active"):
                return False
        _store_premium_in_session({
            "subscription_id": subscription_id,
            "customer_id": db_row.get("customer_id", ""),
            "customer_email": email,
            "plan_name": db_row.get("plan_name", "Premium"),
            "period_end": db_row.get("current_period_end", ""),
            "status": db_row.get("status", "active"),
        })
        return True

    # ── Check Stripe API ──────────────────────────────────────
    if not is_stripe_configured():
        return False

    result = get_subscription_by_email(email)
    if result.get("is_active"):
        sub_info = {
            "subscription_id": result.get("subscription_id", ""),
            "customer_id": result.get("customer_id", ""),
            "customer_email": email,
            "plan_name": "Premium",
            "period_end": result.get("period_end", ""),
            "status": result.get("status", "active"),
        }
        _store_premium_in_session(sub_info)
        _save_subscription_to_db(sub_info)
        return True

    return False


def logout_premium() -> None:
    """
    Clear the current premium session.
    The user will need to re-authenticate to access premium features.
    """
    _clear_premium_from_session()
    # Also clear the checkout session flag
    st.session_state.pop("_checkout_session_processed", None)


# ============================================================
# SECTION: Tier System
# ============================================================
# Four tiers, each strictly including the features of all lower tiers.
# Tier names match what the subscription page displays.

TIER_FREE          = "free"
TIER_SHARP_IQ      = "sharp_iq"
TIER_SMART_MONEY   = "smart_money"
TIER_INSIDER       = "insider_circle"

# Ordered lowest → highest so we can compare by index.
_TIER_ORDER = [TIER_FREE, TIER_SHARP_IQ, TIER_SMART_MONEY, TIER_INSIDER]

# Human-readable labels for display.
TIER_LABELS = {
    TIER_FREE:        "⭐ Smart Rookie",
    TIER_SHARP_IQ:    "🔥 Sharp IQ",
    TIER_SMART_MONEY: "💎 Smart Money",
    TIER_INSIDER:     "👑 Insider Circle",
}

# Map various plan_name strings that might come back from Stripe
# (product name, price nickname, legacy values) → canonical tier key.
_PLAN_NAME_TO_TIER: dict[str, str] = {
    # Exact matches from Stripe products / nicknames
    "sharp iq":           TIER_SHARP_IQ,
    "sharp iq monthly":   TIER_SHARP_IQ,
    "sharp iq annual":    TIER_SHARP_IQ,
    "smart money":        TIER_SMART_MONEY,
    "smart money monthly": TIER_SMART_MONEY,
    "smart money annual": TIER_SMART_MONEY,
    "insider circle":     TIER_INSIDER,
    "insider":            TIER_INSIDER,
    # Legacy / fallback
    "premium":            TIER_SHARP_IQ,
    "pro":                TIER_SMART_MONEY,
}

# Map Stripe price_id env-var names → tier for direct resolution.
_PRICE_ENV_TO_TIER: dict[str, str] = {
    os.environ.get("STRIPE_PRICE_SHARP_IQ", ""):      TIER_SHARP_IQ,
    os.environ.get("STRIPE_PRICE_SMART_MONEY", ""):    TIER_SMART_MONEY,
    os.environ.get("STRIPE_PRICE_INSIDER_CIRCLE", ""): TIER_INSIDER,
    # Annual variants (if you add separate env vars later, add here)
}
# Remove empty key if env vars aren't set
_PRICE_ENV_TO_TIER.pop("", None)

# QAM prop limits per tier.
TIER_QAM_LIMITS = {
    TIER_FREE:        10,
    TIER_SHARP_IQ:    25,
    TIER_SMART_MONEY: 9999,   # effectively unlimited
    TIER_INSIDER:     9999,
}

# Page access requirements — the minimum tier needed for each page.
# Pages not listed here are accessible to ALL tiers (including free).
PAGE_TIER_REQUIREMENTS: dict[str, str] = {
    # Free tier pages (listed for documentation, not enforced):
    # "0_💦_Live_Sweat"            → free
    # "1_📡_Live_Games"            → free
    # "10_📡_Smart_NBA_Data"       → free
    # "14_⚙️_Settings"             → free
    # "15_💎_Subscription_Level"   → free

    # Sharp IQ ($9.99/mo)
    "2_🔬_Prop_Scanner":           TIER_SHARP_IQ,
    "6_📋_Game_Report":            TIER_SHARP_IQ,
    "7_🔮_Player_Simulator":       TIER_SHARP_IQ,
    "8_🧬_Entry_Builder":          TIER_SHARP_IQ,
    "9_🛡️_Risk_Shield":           TIER_SHARP_IQ,
    "12_📈_Bet_Tracker":           TIER_SHARP_IQ,

    # Smart Money ($24.99/mo)
    "4_💰_Smart_Money_Bets":       TIER_SMART_MONEY,
    "5_🎙️_The_Studio":            TIER_SMART_MONEY,
    "11_🗺️_Correlation_Matrix":   TIER_SMART_MONEY,
    "13_📊_Proving_Grounds":       TIER_SMART_MONEY,
}


def get_user_tier() -> str:
    """Return the canonical tier key for the current user.

    Resolution order:
      1. Non-production bypass → insider_circle (everything unlocked).
      2. Stripe not configured → insider_circle.
      3. Not premium → free.
      4. Match stored plan_name → tier.
      5. Match stored price_id → tier (fallback).
      6. Default → sharp_iq (lowest paid).
    """
    # Dev / non-production: everything unlocked
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        return TIER_INSIDER

    if not is_stripe_configured():
        return TIER_INSIDER

    if not is_premium_user():
        return TIER_FREE

    # Try plan_name first
    plan_name = st.session_state.get(_SS_PLAN_NAME, "")
    if plan_name:
        tier = _PLAN_NAME_TO_TIER.get(plan_name.lower().strip())
        if tier:
            return tier

    # Try matching by price_id stored during checkout
    price_id = st.session_state.get("_sub_price_id", "")
    if price_id and price_id in _PRICE_ENV_TO_TIER:
        return _PRICE_ENV_TO_TIER[price_id]

    # Fallback: premium but unknown plan → treat as lowest paid tier
    return TIER_SHARP_IQ


def tier_has_access(user_tier: str, required_tier: str) -> bool:
    """Return True if *user_tier* meets or exceeds *required_tier*."""
    try:
        return _TIER_ORDER.index(user_tier) >= _TIER_ORDER.index(required_tier)
    except ValueError:
        return False


def get_tier_label(tier: str) -> str:
    """Return the human-readable emoji label for a tier key."""
    return TIER_LABELS.get(tier, TIER_LABELS[TIER_FREE])
