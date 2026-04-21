# ============================================================
# FILE: utils/stripe_manager.py
# PURPOSE: Stripe API integration for SmartBetPro NBA.
#          Handles subscription checkout, customer portal,
#          and subscription status verification.
#
# HOW IT WORKS:
#   1. User clicks "Subscribe Now" → create_checkout_session()
#      generates a Stripe Checkout URL → user is redirected.
#   2. After payment, Stripe redirects back with ?session_id=XXX
#   3. verify_checkout_session() confirms payment + stores sub.
#   4. get_subscription_status() checks if subscription is active.
#
# ENVIRONMENT VARIABLES REQUIRED:
#   STRIPE_SECRET_KEY      — Stripe secret API key (sk_live_... or sk_test_...)
#   STRIPE_PUBLISHABLE_KEY — Stripe publishable key (pk_live_... or pk_test_...)
#   STRIPE_PRICE_ID        — Price ID from Stripe dashboard (price_XXX)
#   STRIPE_WEBHOOK_SECRET  — (optional) Webhook signing secret (whsec_XXX)
#   APP_URL                — Base URL of the deployed app (e.g. https://your-app.streamlit.app)
#
# GRACEFUL DEGRADATION:
#   If STRIPE_SECRET_KEY is not set, all functions return safe defaults
#   so the app continues to work without crashing.
# ============================================================

import os
import datetime

# ============================================================
# SECTION: Stripe SDK Import
# ============================================================

# Import Stripe SDK — install with: pip install stripe
# If not installed, all Stripe functions return safe defaults.
try:
    import stripe as _stripe
    _STRIPE_AVAILABLE = True
except ImportError:
    _stripe = None
    _STRIPE_AVAILABLE = False

# ============================================================
# SECTION: Configuration
# ============================================================

# Read environment variables (never hard-code keys in source code!)
STRIPE_SECRET_KEY      = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_PRICE_ID        = os.environ.get("STRIPE_PRICE_ID", "")  # legacy fallback
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_URL                = os.environ.get("APP_URL", "http://localhost:8501")

# ── Per-tier Price IDs (new 4-tier model) ─────────────────────
STRIPE_PRICE_SHARP_IQ      = os.environ.get("STRIPE_PRICE_SHARP_IQ", "")
STRIPE_PRICE_SMART_MONEY   = os.environ.get("STRIPE_PRICE_SMART_MONEY", "")
STRIPE_PRICE_INSIDER_CIRCLE = os.environ.get("STRIPE_PRICE_INSIDER_CIRCLE", "")

# Map lookup keys → (price_id, checkout_mode)
# "subscription" for recurring, "payment" for one-time.
_PRICE_MAP = {
    "sharp_iq":       (STRIPE_PRICE_SHARP_IQ,      "subscription"),
    "smart_money":    (STRIPE_PRICE_SMART_MONEY,    "subscription"),
    "insider_circle": (STRIPE_PRICE_INSIDER_CIRCLE, "payment"),
}

# Reverse map: price_id → canonical plan name (used when resolving
# the plan name from a Stripe checkout session or subscription).
_PRICE_ID_TO_PLAN_NAME: dict[str, str] = {}
if STRIPE_PRICE_SHARP_IQ:
    _PRICE_ID_TO_PLAN_NAME[STRIPE_PRICE_SHARP_IQ] = "Sharp IQ"
if STRIPE_PRICE_SMART_MONEY:
    _PRICE_ID_TO_PLAN_NAME[STRIPE_PRICE_SMART_MONEY] = "Smart Money"
if STRIPE_PRICE_INSIDER_CIRCLE:
    _PRICE_ID_TO_PLAN_NAME[STRIPE_PRICE_INSIDER_CIRCLE] = "Insider Circle"

# Remove trailing slash from APP_URL so URL construction is clean
APP_URL = APP_URL.rstrip("/")

# Path to the Premium page (URL-encoded emoji in page name).
# Used in redirect URLs passed to Stripe.
_PREMIUM_PAGE_PATH = "/15_%F0%9F%92%8E_Subscription_Level"

# ── Helpers for Stripe API version differences ────────────────
def _get_period_end(sub) -> int | None:
    """Get current_period_end from subscription or its first item."""
    val = getattr(sub, "current_period_end", None)
    if val:
        return val
    try:
        return sub["items"]["data"][0]["current_period_end"]
    except Exception:
        return None


def _get_period_start(sub) -> int | None:
    """Get current_period_start from subscription or its first item."""
    val = getattr(sub, "current_period_start", None)
    if val:
        return val
    try:
        return sub["items"]["data"][0]["current_period_start"]
    except Exception:
        return None


# ── Configure Stripe SDK with our secret key ─────────────────
# This must be done before any Stripe API calls.
def _configure_stripe():
    """
    Configure the Stripe SDK with the secret API key.

    Returns:
        bool: True if Stripe is configured and ready, False otherwise.
    """
    if not _STRIPE_AVAILABLE:
        return False
    if not STRIPE_SECRET_KEY:
        return False
    _stripe.api_key = STRIPE_SECRET_KEY
    return True


# ============================================================
# SECTION: Checkout Session
# ============================================================

def create_checkout_session(customer_email: str = "", price_lookup: str = "") -> dict:
    """
    Create a Stripe Checkout Session for a new subscription.

    The user is redirected to Stripe's hosted checkout page,
    enters their payment details, and is then redirected back
    to APP_URL/pages/14_💎_Subscription_Level?session_id=XXX on success.

    Args:
        customer_email (str): Pre-fill the checkout form with
                              the user's email (optional).

    Returns:
        dict with keys:
            success (bool): Whether the session was created.
            url     (str):  Redirect URL for Stripe Checkout.
            session_id (str): Stripe Checkout Session ID.
            error   (str):  Error message if success=False.
    """
    if not _configure_stripe():
        return {
            "success": False,
            "url": "",
            "session_id": "",
            "error": "Stripe is not configured. Please set STRIPE_SECRET_KEY.",
        }

    # ── Resolve price ID from lookup key or fall back to legacy ──
    price_id = ""
    checkout_mode = "subscription"
    if price_lookup and price_lookup in _PRICE_MAP:
        price_id, checkout_mode = _PRICE_MAP[price_lookup]
    if not price_id:
        price_id = STRIPE_PRICE_ID  # legacy single-price fallback
    if not price_id:
        return {
            "success": False,
            "url": "",
            "session_id": "",
            "error": "Stripe Price ID not configured for this tier.",
        }

    try:
        # Build success and cancel URLs
        # success_url includes {CHECKOUT_SESSION_ID} which Stripe replaces
        # with the actual session ID after payment — so we can verify it.
        # Redirect to app root — Streamlit doesn't route URL-encoded page
        # paths, and the home page already runs handle_checkout_redirect().
        success_url = f"{APP_URL}/?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url  = f"{APP_URL}/"

        # Build session parameters
        session_params = {
            "mode": checkout_mode,
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                    **(
                        {"tax_rates": [os.environ["STRIPE_TAX_RATE_ID"]]}
                        if os.environ.get("STRIPE_TAX_RATE_ID")
                        else {}
                    ),
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
            # Allow promotion codes (discount codes) at checkout
            "allow_promotion_codes": True,
        }

        # Pre-fill email if provided (improves conversion rate)
        if customer_email:
            session_params["customer_email"] = customer_email

        # Create the session via Stripe API
        session = _stripe.checkout.Session.create(**session_params)

        return {
            "success": True,
            "url": session.url,
            "session_id": session.id,
            "error": "",
        }

    except Exception as exc:
        return {
            "success": False,
            "url": "",
            "session_id": "",
            "error": str(exc),
        }


# ============================================================
# SECTION: Checkout Session Verification
# ============================================================

def verify_checkout_session(session_id: str) -> dict:
    """
    Verify a completed Stripe Checkout Session and extract
    subscription details.

    Call this after Stripe redirects back to the app with
    ?session_id=XXX in the URL. It confirms the payment was
    successful and retrieves the subscription info.

    Args:
        session_id (str): The Stripe Checkout Session ID
                         (from ?session_id=XXX in the URL).

    Returns:
        dict with keys:
            success         (bool): Whether verification passed.
            subscription_id (str):  Stripe Subscription ID.
            customer_id     (str):  Stripe Customer ID.
            customer_email  (str):  Customer's email address.
            status          (str):  Subscription status (e.g. "active").
            plan_name       (str):  Name of the subscribed plan.
            period_start    (str):  ISO date of current period start.
            period_end      (str):  ISO date of current period end.
            error           (str):  Error message if success=False.
    """
    if not _configure_stripe():
        return {
            "success": False,
            "subscription_id": "",
            "customer_id": "",
            "customer_email": "",
            "status": "",
            "plan_name": "Premium",
            "period_start": "",
            "period_end": "",
            "error": "Stripe is not configured.",
        }

    try:
        # Retrieve the checkout session from Stripe API
        # expand=['subscription', 'customer'] loads nested objects in one call
        session = _stripe.checkout.Session.retrieve(
            session_id,
            expand=["subscription", "customer"],
        )

        # Verify the payment was successful
        if session.payment_status not in ("paid", "no_payment_required"):
            return {
                "success": False,
                "subscription_id": "",
                "customer_id": "",
                "customer_email": "",
                "status": "",
                "plan_name": "Premium",
                "period_start": "",
                "period_end": "",
                "error": f"Payment not completed. Status: {session.payment_status}",
            }

        # Extract subscription details
        subscription = session.subscription
        customer     = session.customer

        # Get customer email
        customer_email = ""
        if customer and hasattr(customer, "email"):
            customer_email = customer.email or ""
        elif session.customer_email:
            customer_email = session.customer_email

        # Get subscription period dates
        period_start = ""
        period_end   = ""
        status       = "active"
        plan_name    = "Premium"

        if subscription:
            status = subscription.status
            _ps = _get_period_start(subscription)
            if _ps:
                period_start = datetime.datetime.fromtimestamp(_ps).isoformat()
            _pe = _get_period_end(subscription)
            if _pe:
                period_end = datetime.datetime.fromtimestamp(_pe).isoformat()
            # Resolve plan name from price_id → canonical name, then
            # fall back to Stripe nickname / product name.
            try:
                price = subscription["items"]["data"][0]["price"]
                _price_id = price.get("id", "")
                if _price_id and _price_id in _PRICE_ID_TO_PLAN_NAME:
                    plan_name = _PRICE_ID_TO_PLAN_NAME[_price_id]
                elif price.get("nickname"):
                    plan_name = price["nickname"]
                elif price.get("product"):
                    product = _stripe.Product.retrieve(price["product"])
                    plan_name = product.get("name", "Premium")
            except Exception:
                pass  # Use default plan name
        else:
            # One-time payment (e.g. Insider Circle) — no subscription
            # object.  Resolve plan_name from the checkout line items.
            try:
                line_items = _stripe.checkout.Session.list_line_items(session_id, limit=1)
                if line_items and line_items.data:
                    _price_id = line_items.data[0].price.id if line_items.data[0].price else ""
                    if _price_id and _price_id in _PRICE_ID_TO_PLAN_NAME:
                        plan_name = _PRICE_ID_TO_PLAN_NAME[_price_id]
                    elif line_items.data[0].description:
                        plan_name = line_items.data[0].description
            except Exception:
                pass
            # One-time purchases are perpetual — no expiry
            status = "active"

        # For one-time payments, use the checkout session ID as a
        # synthetic subscription_id so the record can be persisted.
        sub_id = subscription.id if subscription else f"otp_{session.id}"

        return {
            "success": True,
            "subscription_id": sub_id,
            "customer_id": customer.id if customer else "",
            "customer_email": customer_email,
            "status": status,
            "plan_name": plan_name,
            "period_start": period_start,
            "period_end": period_end,
            "error": "",
        }

    except Exception as exc:
        return {
            "success": False,
            "subscription_id": "",
            "customer_id": "",
            "customer_email": "",
            "status": "",
            "plan_name": "Premium",
            "period_start": "",
            "period_end": "",
            "error": str(exc),
        }


# ============================================================
# SECTION: Subscription Status Lookup
# ============================================================

def get_subscription_by_id(subscription_id: str) -> dict:
    """
    Get the current status of a Stripe subscription by its ID.

    Use this to verify that a stored subscription is still active
    (not cancelled or past_due) before granting access to premium
    features.

    Args:
        subscription_id (str): Stripe Subscription ID (sub_XXX).

    Returns:
        dict with keys:
            success  (bool): Whether the API call succeeded.
            status   (str):  Subscription status ("active", "cancelled", etc.)
            is_active (bool): True if status is "active" or "trialing".
            period_end (str): ISO date when the current period ends.
            error    (str):  Error message if success=False.
    """
    if not _configure_stripe():
        # When Stripe isn't configured, treat as active (free demo mode)
        return {
            "success": True,
            "status": "active",
            "is_active": True,
            "period_end": "",
            "error": "",
        }

    if not subscription_id:
        return {
            "success": False,
            "status": "",
            "is_active": False,
            "period_end": "",
            "error": "No subscription ID provided.",
        }

    try:
        subscription = _stripe.Subscription.retrieve(subscription_id)
        is_active = subscription.status in ("active", "trialing")

        period_end = ""
        _pe = _get_period_end(subscription)
        if _pe:
            period_end = datetime.datetime.fromtimestamp(_pe).isoformat()

        return {
            "success": True,
            "status": subscription.status,
            "is_active": is_active,
            "period_end": period_end,
            "error": "",
        }

    except Exception as exc:
        return {
            "success": False,
            "status": "",
            "is_active": False,
            "period_end": "",
            "error": str(exc),
        }


def get_subscription_by_email(customer_email: str) -> dict:
    """
    Look up a customer's active subscription by their email address.

    Useful for returning users who want to restore access by entering
    their email (since Streamlit session state is lost on browser close).

    Args:
        customer_email (str): The email used when subscribing.

    Returns:
        dict with keys:
            success         (bool):
            subscription_id (str):
            customer_id     (str):
            status          (str):
            is_active       (bool):
            period_end      (str):
            error           (str):
    """
    if not _configure_stripe():
        return {
            "success": False,
            "subscription_id": "",
            "customer_id": "",
            "status": "",
            "is_active": False,
            "period_end": "",
            "error": "Stripe is not configured.",
        }

    if not customer_email:
        return {
            "success": False,
            "subscription_id": "",
            "customer_id": "",
            "status": "",
            "is_active": False,
            "period_end": "",
            "error": "No email provided.",
        }

    try:
        # Search for customers with this email
        customers = _stripe.Customer.list(email=customer_email, limit=1)
        if not customers.data:
            return {
                "success": False,
                "subscription_id": "",
                "customer_id": "",
                "status": "",
                "is_active": False,
                "period_end": "",
                "error": "No customer found with that email.",
            }

        customer = customers.data[0]

        # Find their active subscription
        subscriptions = _stripe.Subscription.list(
            customer=customer.id,
            status="active",
            limit=1,
        )

        if not subscriptions.data:
            # Check for trialing subscriptions too
            subscriptions = _stripe.Subscription.list(
                customer=customer.id,
                status="trialing",
                limit=1,
            )

        if not subscriptions.data:
            return {
                "success": False,
                "subscription_id": "",
                "customer_id": customer.id,
                "status": "inactive",
                "is_active": False,
                "period_end": "",
                "error": "No active subscription found for this email.",
            }

        sub = subscriptions.data[0]
        period_end = ""
        _pe = _get_period_end(sub)
        if _pe:
            period_end = datetime.datetime.fromtimestamp(_pe).isoformat()

        return {
            "success": True,
            "subscription_id": sub.id,
            "customer_id": customer.id,
            "status": sub.status,
            "is_active": sub.status in ("active", "trialing"),
            "period_end": period_end,
            "error": "",
        }

    except Exception as exc:
        return {
            "success": False,
            "subscription_id": "",
            "customer_id": "",
            "status": "",
            "is_active": False,
            "period_end": "",
            "error": str(exc),
        }


# ============================================================
# SECTION: Customer Portal
# ============================================================

def create_customer_portal_session(customer_id: str) -> dict:
    """
    Create a Stripe Customer Portal session for managing subscriptions.

    The Customer Portal lets subscribers cancel, upgrade, update
    billing info, and view invoices — all handled by Stripe.

    Args:
        customer_id (str): Stripe Customer ID (cus_XXX).

    Returns:
        dict with keys:
            success (bool): Whether the session was created.
            url     (str):  Redirect URL for the Customer Portal.
            error   (str):  Error message if success=False.
    """
    if not _configure_stripe():
        return {
            "success": False,
            "url": "",
            "error": "Stripe is not configured.",
        }

    if not customer_id:
        return {
            "success": False,
            "url": "",
            "error": "No customer ID provided.",
        }

    try:
        return_url = f"{APP_URL}/"
        portal_session = _stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return {
            "success": True,
            "url": portal_session.url,
            "error": "",
        }
    except Exception as exc:
        return {
            "success": False,
            "url": "",
            "error": str(exc),
        }


# ============================================================
# SECTION: Utility Helpers
# ============================================================

def is_stripe_configured() -> bool:
    """
    Check whether Stripe is configured and ready to use.

    Returns:
        bool: True if STRIPE_SECRET_KEY is set and stripe SDK is installed.
    """
    return bool(_STRIPE_AVAILABLE and STRIPE_SECRET_KEY)


def get_publishable_key() -> str:
    """
    Return the Stripe publishable key for use in the frontend.

    Returns:
        str: Publishable key (pk_live_... or pk_test_...) or empty string.
    """
    return STRIPE_PUBLISHABLE_KEY
