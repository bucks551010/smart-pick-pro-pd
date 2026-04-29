"""
webhook_server.py
-----------------
Standalone Flask server for receiving Stripe webhook events.

Stripe webhooks cannot be sent directly to a Streamlit app (Streamlit
only serves its own UI over HTTP). This lightweight Flask server runs
separately and updates the shared database when subscription events occur.

Deployment:
    Deploy on Railway, Render, or Fly.io. Register the public URL in
    Stripe Dashboard → Developers → Webhooks.

Usage:
    pip install flask stripe python-dotenv
    python webhook_server.py

Environment variables (set in .env or host config):
    STRIPE_SECRET_KEY       — Stripe API secret key
    STRIPE_WEBHOOK_SECRET   — Webhook endpoint signing secret (whsec_...)
    DATABASE_URL            — PostgreSQL connection string (Railway/Render)
    DB_PATH                 — SQLite database path fallback (default: db/smartai_nba.db)
"""

import datetime
import os
import logging
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

try:
    import stripe
except ImportError:
    raise SystemExit("stripe package is required: pip install stripe")

# ── Configuration ─────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_PATH = os.environ.get("DB_PATH", str(Path(os.environ.get("DB_DIR", str(Path(__file__).parent / "db"))) / "smartai_nba.db"))

if not STRIPE_SECRET_KEY:
    raise SystemExit("FATAL: STRIPE_SECRET_KEY is not set. Webhook server cannot start.")
if not STRIPE_WEBHOOK_SECRET:
    raise SystemExit("FATAL: STRIPE_WEBHOOK_SECRET is not set. Webhook server cannot start.")

stripe.api_key = STRIPE_SECRET_KEY

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_logger = logging.getLogger("webhook_server")

app = Flask(__name__)


# ── Database helper ───────────────────────────────────────────

def _update_subscription(subscription_id: str, status: str, email: str = "",
                         period_end: str = "") -> bool:
    """Insert or update a subscription row.

    Writes to PostgreSQL when DATABASE_URL is set (Railway production),
    falls back to SQLite for local development.
    """
    # ── PostgreSQL path (Railway production) ──────────────────────────
    if DATABASE_URL:
        conn = None
        try:
            import psycopg2  # type: ignore
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subscriptions
                        (subscription_id, customer_id, customer_email, status,
                         current_period_end, updated_at)
                    VALUES (%s, '', %s, %s, %s, NOW())
                    ON CONFLICT(subscription_id) DO UPDATE SET
                        status             = EXCLUDED.status,
                        customer_email     = CASE WHEN EXCLUDED.customer_email = ''
                                                 THEN subscriptions.customer_email
                                                 ELSE EXCLUDED.customer_email END,
                        current_period_end = CASE WHEN EXCLUDED.current_period_end = ''
                                                 THEN subscriptions.current_period_end
                                                 ELSE EXCLUDED.current_period_end END,
                        updated_at         = NOW()
                    """,
                    (subscription_id, email, status, period_end),
                )
            conn.commit()
            _logger.info("DB (PG) updated: %s → %s", subscription_id, status)
            return True
        except Exception as exc:
            _logger.error("PG update failed for %s: %s", subscription_id, exc)
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    # ── SQLite path (local development fallback) ───────────────────────
    conn = None
    try:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            INSERT INTO subscriptions
                (subscription_id, customer_id, customer_email, status,
                 current_period_end, updated_at)
            VALUES (?, '', ?, ?, ?, datetime('now'))
            ON CONFLICT(subscription_id) DO UPDATE SET
                status             = excluded.status,
                customer_email     = CASE WHEN excluded.customer_email = ''
                                         THEN subscriptions.customer_email
                                         ELSE excluded.customer_email END,
                current_period_end = CASE WHEN excluded.current_period_end = ''
                                         THEN subscriptions.current_period_end
                                         ELSE excluded.current_period_end END,
                updated_at         = datetime('now')
            """,
            (subscription_id, email, status, period_end),
        )
        conn.commit()
        _logger.info("DB (SQLite) updated: %s → %s", subscription_id, status)
        return True
    except Exception as exc:
        _logger.error("SQLite update failed for %s: %s", subscription_id, exc)
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ── Webhook endpoint ──────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Receive and process Stripe webhook events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        _logger.error("STRIPE_WEBHOOK_SECRET is not configured — rejecting webhook")
        return jsonify({"error": "webhook secret not configured"}), 500

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        _logger.warning("Webhook signature verification failed")
        return jsonify({"error": "invalid signature"}), 400
    except Exception as exc:
        _logger.error("Webhook construction error: %s", exc)
        return jsonify({"error": str(exc)}), 400

    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})
    _logger.info("Received event: %s", event_type)

    if event_type == "customer.subscription.updated":
        sub_id = data_object.get("id", "")
        status = data_object.get("status", "")
        email = data_object.get("customer_email", "")
        period_end = data_object.get("current_period_end", "")
        if isinstance(period_end, int):
            period_end = datetime.datetime.fromtimestamp(
                period_end, tz=datetime.timezone.utc
            ).isoformat()
        _update_subscription(sub_id, status, email, period_end)
        _logger.info("Subscription updated: %s → %s", sub_id, status)

    elif event_type == "customer.subscription.deleted":
        sub_id = data_object.get("id", "")
        _update_subscription(sub_id, "canceled")
        _logger.info("Subscription deleted: %s", sub_id)

    elif event_type == "invoice.payment_failed":
        sub_id = data_object.get("subscription", "")
        if sub_id:
            _update_subscription(sub_id, "past_due")
            _logger.info("Payment failed for subscription: %s", sub_id)

    else:
        _logger.debug("Unhandled event type: %s", event_type)

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    if not STRIPE_SECRET_KEY:
        _logger.warning("STRIPE_SECRET_KEY is not set — webhook verification will fail")
    if not STRIPE_WEBHOOK_SECRET:
        _logger.warning("STRIPE_WEBHOOK_SECRET is not set — all webhooks will be rejected")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
