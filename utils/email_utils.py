"""utils/email_utils.py — Transactional email sending for Smart Pick Pro.

Recommended provider: SendGrid (100 emails/day free, excellent deliverability)
Fallback: SMTP via stdlib smtplib (works with Mailgun, Postmark, AWS SES SMTP,
          or any SMTP relay).

Configuration (set in Railway environment variables):
─────────────────────────────────────────────────────────────────────────────
Primary — SendGrid REST API (preferred):
  SENDGRID_API_KEY      Your SendGrid API key (starts with "SG.")
  SENDGRID_FROM_EMAIL   Verified sender: e.g. noreply@smartpickpro.ai
  SENDGRID_FROM_NAME    Display name: e.g. "Smart Pick Pro"  (optional)

Fallback — SMTP (any provider):
  SMTP_HOST     e.g. smtp.mailgun.org / smtp.postmarkapp.com / email-smtp.us-east-1.amazonaws.com
  SMTP_PORT     587 (STARTTLS) or 465 (SSL)
  SMTP_USER     SMTP username (often the "from" address)
  SMTP_PASSWORD SMTP password / API key
  SMTP_FROM     Sender address (defaults to SMTP_USER)

Why SendGrid?
  - 100 free emails/day, no credit card
  - Single v3 API call — no extra SDK needed (uses requests, already installed)
  - Automatic SPF/DKIM alignment when you verify a sender domain

SPF / DKIM / DMARC checklist (DNS records — set on your domain registrar):
  SPF:   v=spf1 include:sendgrid.net ~all
  DKIM:  SendGrid generates two CNAME records during domain verification
  DMARC: v=DMARC1; p=quarantine; rua=mailto:dmarc@smartpickpro.ai
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.logger import get_logger

_logger = get_logger(__name__)

# ── Provider config ────────────────────────────────────────────────────────────
_SG_API_KEY   = os.environ.get("SENDGRID_API_KEY", "")
_SG_FROM      = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@smartpickpro.ai")
_SG_FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "Smart Pick Pro")

_SMTP_HOST    = os.environ.get("SMTP_HOST", "")
_SMTP_PORT    = int(os.environ.get("SMTP_PORT", "587"))
_SMTP_USER    = os.environ.get("SMTP_USER", "")
_SMTP_PASS    = os.environ.get("SMTP_PASSWORD", "")
_SMTP_FROM    = os.environ.get("SMTP_FROM", _SMTP_USER)


def send_transactional_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """Send a transactional email via SendGrid (primary) or SMTP (fallback).

    Returns True on success, False on failure.  Errors are logged but never
    raised so a send failure never breaks user-facing flows.

    Security notes:
    - to_email is the only external value embedded in the payload.
      It is validated upstream via _valid_email() before reaching here.
    - Subject / body values come from our own templates, not user input.
    """
    if not to_email or "@" not in to_email:
        _logger.warning("send_transactional_email: invalid recipient %r", to_email)
        return False

    # Attempt 1: SendGrid REST API
    if _SG_API_KEY:
        try:
            return _send_via_sendgrid(to_email, to_name, subject, html_body, text_body)
        except Exception as exc:
            _logger.warning("SendGrid send failed, trying SMTP fallback: %s", exc)

    # Attempt 2: SMTP fallback
    if _SMTP_HOST and _SMTP_USER:
        try:
            return _send_via_smtp(to_email, to_name, subject, html_body, text_body)
        except Exception as exc:
            _logger.error("SMTP send also failed: %s", exc)

    _logger.warning(
        "Email not sent to %s — no provider configured. "
        "Set SENDGRID_API_KEY or SMTP_HOST/SMTP_USER/SMTP_PASSWORD.",
        to_email,
    )
    return False


def _send_via_sendgrid(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """Send via SendGrid v3 REST API using only the ``requests`` library."""
    import requests  # already in requirements.txt

    payload = {
        "personalizations": [
            {
                "to": [{"email": to_email, "name": to_name or to_email.split("@")[0]}],
                "subject": subject,
            }
        ],
        "from": {"email": _SG_FROM, "name": _SG_FROM_NAME},
        "reply_to": {"email": _SG_FROM, "name": _SG_FROM_NAME},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text_body},
            {"type": "text/html",  "value": html_body},
        ],
    }

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        json=payload,
        headers={
            "Authorization": f"Bearer {_SG_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )

    if resp.status_code in (200, 202):
        _logger.info("SendGrid: email sent to %s (subject: %s)", to_email, subject)
        return True

    _logger.warning(
        "SendGrid returned %d: %s", resp.status_code, resp.text[:200]
    )
    return False


def _send_via_smtp(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """Send via SMTP using stdlib smtplib with STARTTLS."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{_SG_FROM_NAME} <{_SMTP_FROM}>"
    msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    ctx = ssl.create_default_context()
    if _SMTP_PORT == 465:
        with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, context=ctx) as server:
            server.login(_SMTP_USER, _SMTP_PASS)
            server.sendmail(_SMTP_FROM, to_email, msg.as_string())
    else:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(_SMTP_USER, _SMTP_PASS)
            server.sendmail(_SMTP_FROM, to_email, msg.as_string())

    _logger.info("SMTP: email sent to %s (subject: %s)", to_email, subject)
    return True


# ── Convenience senders ────────────────────────────────────────────────────────

def send_verification_email(
    to_email: str,
    display_name: str,
    verify_url: str,
) -> bool:
    """Send the welcome + email-verification email."""
    from utils.email_templates import render_verification_email
    html, text = render_verification_email(display_name, verify_url)
    return send_transactional_email(
        to_email, display_name,
        "Verify your Smart Pick Pro email",
        html, text,
    )


def send_password_reset_email(
    to_email: str,
    display_name: str,
    reset_url: str,
    expires_min: int = 30,
) -> bool:
    """Send the password-reset link email."""
    from utils.email_templates import render_password_reset_email
    html, text = render_password_reset_email(display_name, reset_url, expires_min)
    return send_transactional_email(
        to_email, display_name,
        "Reset your Smart Pick Pro password",
        html, text,
    )


def send_reset_code_only_email(
    to_email: str,
    display_name: str,
    code: str,
    expires_min: int = 15,
) -> bool:
    """Send a 6-digit reset code email (for the in-app code flow)."""
    from utils.email_templates import render_reset_code_email
    html, text = render_reset_code_email(display_name, code, expires_min)
    return send_transactional_email(
        to_email, display_name,
        "Your Smart Pick Pro reset code",
        html, text,
    )


def send_welcome_confirmed_email(
    to_email: str,
    display_name: str,
    app_url: str = "https://smartpickpro.ai",
) -> bool:
    """Send the post-verification welcome email."""
    from utils.email_templates import render_welcome_confirmed_email
    html, text = render_welcome_confirmed_email(display_name, app_url)
    return send_transactional_email(
        to_email, display_name,
        f"Welcome to Smart Pick Pro, {display_name}!",
        html, text,
    )


def send_admin_new_user_alert(user_email: str, display_name: str) -> bool:
    """Notify the site owner whenever a new user signs up."""
    import os
    from datetime import datetime, timezone
    admin_email = os.environ.get("ADMIN_NOTIFY_EMAIL", "")
    if not admin_email:
        return False
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"New Sign-Up: {display_name} ({user_email})"
    html = f"""<html><body style="font-family:sans-serif;background:#0a0d14;color:#e0e6f0;padding:32px;">
<div style="max-width:480px;margin:0 auto;background:#131920;border-radius:12px;padding:28px;">
<h2 style="color:#00d4ff;margin-top:0;">New User Sign-Up</h2>
<p><strong>Name:</strong> {display_name}</p>
<p><strong>Email:</strong> {user_email}</p>
<p><strong>Time:</strong> {now}</p>
</div></body></html>"""
    text = f"New Sign-Up\nName: {display_name}\nEmail: {user_email}\nTime: {now}"
    return send_transactional_email(admin_email, "Admin", subject, html, text)
