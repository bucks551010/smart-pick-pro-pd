"""utils/email_templates.py — Branded HTML email templates for Smart Pick Pro.

All templates use:
  - Inline CSS only (Gmail/Outlook strip <style> blocks in some clients)
  - Max-width: 600px with fluid fallback for mobile
  - Dark professional theme matching the app (#0a0d14 bg, #00d4ff accent)
  - Plain-text fallback alongside every HTML body
  - Handlebars-compatible variable placeholders documented in comments

Variable legend (Liquid / Handlebars equivalents):
  display_name  → {{ user_name }}
  verify_url    → {{ verify_link }}
  reset_url     → {{ reset_link }}
  reset_code    → {{ reset_code }}
  expires_min   → {{ expires_minutes }}
  app_url       → {{ app_url }}
"""
from __future__ import annotations

# ── Shared design tokens ───────────────────────────────────────────────────────
_BG          = "#0a0d14"
_CARD_BG     = "#131920"
_BORDER      = "#1e2940"
_ACCENT_1    = "#00d4ff"
_ACCENT_2    = "#7b2ff7"
_TEXT        = "#e0e6f0"
_MUTED       = "#8b9ab0"
_BTN_START   = "#00c3f0"
_BTN_END     = "#6a1fe0"
_SUCCESS     = "#00d48a"

_BASE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:{bg};font-family:-apple-system,BlinkMacSystemFont,\
'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <!--[if mso]><table width="600" align="center" cellpadding="0" cellspacing="0"><tr><td><![endif]-->
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="max-width:600px;margin:0 auto;">
    <!-- Header -->
    <tr>
      <td style="padding:32px 24px 0;text-align:center;">
        <div style="display:inline-block;background:linear-gradient(135deg,{a1},{a2});\
padding:2px;border-radius:14px;">
          <div style="background:{card};border-radius:12px;padding:12px 24px;">
            <span style="font-size:22px;font-weight:800;letter-spacing:-0.5px;
                         background:linear-gradient(135deg,{a1},{a2});
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         color:{a1};">
              ⚡ Smart Pick Pro
            </span>
          </div>
        </div>
      </td>
    </tr>
    <!-- Body card -->
    <tr>
      <td style="padding:24px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="background:{card};border:1px solid {border};\
border-radius:16px;overflow:hidden;">
          <!-- Gradient top bar -->
          <tr>
            <td style="height:4px;background:linear-gradient(90deg,{a1},{a2});"></td>
          </tr>
          <tr>
            <td style="padding:32px 32px 0;">
              {body}
            </td>
          </tr>
          <!-- Footer inside card -->
          <tr>
            <td style="padding:24px 32px;border-top:1px solid {border};margin-top:24px;">
              <p style="margin:0;font-size:12px;color:{muted};line-height:1.6;">
                This email was sent by Smart Pick Pro.<br>
                If you didn't request this, you can safely ignore it.<br>
                <a href="https://smartpickpro.ai" style="color:{a1};text-decoration:none;">
                  smartpickpro.ai
                </a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <!-- Bottom padding -->
    <tr><td style="height:32px;"></td></tr>
  </table>
  <!--[if mso]></td></tr></table><![endif]-->
</body>
</html>"""


def _wrap(subject: str, body: str) -> str:
    return _BASE_HTML.format(
        subject=subject,
        bg=_BG,
        card=_CARD_BG,
        border=_BORDER,
        a1=_ACCENT_1,
        a2=_ACCENT_2,
        text=_TEXT,
        muted=_MUTED,
        body=body,
    )


def _cta_button(label: str, url: str) -> str:
    return f"""\
<table cellpadding="0" cellspacing="0" border="0" style="margin:24px auto;">
  <tr>
    <td style="border-radius:10px;background:linear-gradient(135deg,{_BTN_START},{_BTN_END});">
      <a href="{url}"
         style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:700;
                color:#ffffff;text-decoration:none;border-radius:10px;
                letter-spacing:0.3px;">
        {label}
      </a>
    </td>
  </tr>
</table>"""


def _h1(text: str) -> str:
    return (
        f'<h1 style="margin:0 0 8px;font-size:26px;font-weight:800;color:{_TEXT};'
        f'letter-spacing:-0.5px;">{text}</h1>'
    )


def _p(text: str, *, muted: bool = False, small: bool = False) -> str:
    color = _MUTED if muted else _TEXT
    size = "13px" if small else "15px"
    return (
        f'<p style="margin:0 0 16px;font-size:{size};color:{color};'
        f'line-height:1.7;">{text}</p>'
    )


def _divider() -> str:
    return f'<hr style="border:none;border-top:1px solid {_BORDER};margin:24px 0;">'


def _badge(text: str) -> str:
    return (
        f'<span style="display:inline-block;padding:4px 10px;border-radius:20px;'
        f'font-size:11px;font-weight:700;letter-spacing:1px;color:{_ACCENT_1};'
        f'background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.25);">'
        f'{text}</span>'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Email Verification (Welcome + Verify)
# ═══════════════════════════════════════════════════════════════════════════════

def render_verification_email(
    display_name: str,
    verify_url: str,
) -> tuple[str, str]:
    """Return (html, plain_text) for the welcome + email verification email.

    Handlebars equivalent: {{ user_name }}, {{ verify_link }}
    """
    name = display_name or "there"
    body = f"""
{_badge("ACTION REQUIRED")}
<br><br>
{_h1("Verify your email address")}
{_p(f"Hi {name}, welcome to <strong style='color:{_TEXT};'>Smart Pick Pro</strong> — "
    f"the AI platform that fuses 6 neural networks and 300+ props every night.")}
{_p("Click the button below to confirm your email address and unlock your full account.")}
{_cta_button("✅ Verify My Email", verify_url)}
{_p("This link expires in <strong style='color:{_TEXT};'>24 hours</strong>. "
    "If you didn't create an account, you can safely ignore this email.",
    muted=True)}
{_divider()}
{_p("Or copy and paste this link into your browser:", muted=True, small=True)}
<p style="margin:0 0 16px;font-size:12px;color:{_ACCENT_1};word-break:break-all;">{verify_url}</p>
<br>
"""

    plain = f"""Welcome to Smart Pick Pro!

Hi {name},

Please verify your email address by visiting the link below:

{verify_url}

This link expires in 24 hours.

If you didn't create an account, ignore this email.

— Smart Pick Pro
https://smartpickpro.ai
"""
    return _wrap("Verify your Smart Pick Pro email", body), plain


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Password Reset (Link version — for the new secure flow)
# ═══════════════════════════════════════════════════════════════════════════════

def render_password_reset_email(
    display_name: str,
    reset_url: str,
    expires_min: int = 30,
) -> tuple[str, str]:
    """Return (html, plain_text) for the password reset email.

    Handlebars equivalent: {{ user_name }}, {{ reset_link }}, {{ expires_minutes }}
    """
    name = display_name or "there"
    body = f"""
{_badge("SECURITY NOTICE")}
<br><br>
{_h1("Reset your password")}
{_p(f"Hi {name}, we received a request to reset the password for your Smart Pick Pro account.")}
{_p("Click the button below to choose a new password. "
    f"This link expires in <strong style='color:{_ACCENT_1};'>{expires_min} minutes</strong>.")}
{_cta_button("🔐 Reset My Password", reset_url)}
{_p("If you didn't request a password reset, your account is safe — "
    "just ignore this email. The link will expire automatically.",
    muted=True)}
{_divider()}
{_p("Or copy and paste this link into your browser:", muted=True, small=True)}
<p style="margin:0 0 16px;font-size:12px;color:{_ACCENT_1};word-break:break-all;">{reset_url}</p>
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="background:rgba(123,47,247,0.08);border:1px solid rgba(123,47,247,0.2);
              border-radius:8px;margin-bottom:16px;">
  <tr>
    <td style="padding:12px 16px;">
      <p style="margin:0;font-size:12px;color:{_MUTED};line-height:1.6;">
        🔒 <strong style="color:{_TEXT};">Security tips:</strong> Smart Pick Pro will never
        ask for your password by email or phone. This link can only be used once.
      </p>
    </td>
  </tr>
</table>
<br>
"""
    plain = f"""Password Reset Request — Smart Pick Pro

Hi {name},

We received a request to reset your password.

Visit this link to reset it (expires in {expires_min} minutes):

{reset_url}

If you didn't request this, your account is safe — ignore this email.

— Smart Pick Pro
https://smartpickpro.ai
"""
    return _wrap("Reset your Smart Pick Pro password", body), plain


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 6-Digit Code Reset (adapter for the existing in-app code flow)
# ═══════════════════════════════════════════════════════════════════════════════

def render_reset_code_email(
    display_name: str,
    code: str,
    expires_min: int = 15,
) -> tuple[str, str]:
    """Return (html, plain_text) for the 6-digit reset code email.

    Handlebars equivalent: {{ user_name }}, {{ reset_code }}, {{ expires_minutes }}
    """
    name = display_name or "there"
    body = f"""
{_badge("SECURITY CODE")}
<br><br>
{_h1("Your password reset code")}
{_p(f"Hi {name}, here is your Smart Pick Pro password reset code:")}
<table cellpadding="0" cellspacing="0" border="0" style="margin:0 auto 24px;">
  <tr>
    <td style="background:rgba(0,212,255,0.08);border:2px solid {_ACCENT_1};
               border-radius:12px;padding:20px 40px;text-align:center;">
      <span style="font-size:40px;font-weight:900;letter-spacing:12px;
                   color:{_ACCENT_1};font-family:monospace;">{code}</span>
    </td>
  </tr>
</table>
{_p(f"Enter this code in the app. It expires in "
    f"<strong style='color:{_ACCENT_1};'>{expires_min} minutes</strong>.",
    muted=True)}
{_p("If you didn't request this, you can safely ignore this email.", muted=True)}
<br>
"""
    plain = f"""Password Reset Code — Smart Pick Pro

Hi {name},

Your Smart Pick Pro password reset code is:

    {code}

Enter this code in the app. It expires in {expires_min} minutes.

If you didn't request this, ignore this email.

— Smart Pick Pro
https://smartpickpro.ai
"""
    return _wrap("Your Smart Pick Pro reset code", body), plain


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Welcome Confirmed (post-verification)
# ═══════════════════════════════════════════════════════════════════════════════

def render_welcome_confirmed_email(
    display_name: str,
    app_url: str = "https://smartpickpro.ai",
) -> tuple[str, str]:
    """Return (html, plain_text) for the post-verification welcome email.

    Handlebars equivalent: {{ user_name }}, {{ app_url }}
    """
    name = display_name or "there"
    features = [
        ("⚡", "6 Neural Networks", "SAFE Score, ensemble modeling, edge detection"),
        ("📊", "300+ Props / Night", "PrizePicks, DraftKings & Underdog scanned daily"),
        ("📈", "+18% Avg ROI", "Verified hit rate across 8,400+ graded picks"),
        ("🎯", "Instant Access", "No credit card — free forever"),
    ]
    feat_rows = "".join(
        f"""<tr>
          <td style="padding:10px 0;vertical-align:top;width:40px;font-size:20px;">{ico}</td>
          <td style="padding:10px 0;vertical-align:top;">
            <strong style="color:{_TEXT};font-size:14px;">{title}</strong><br>
            <span style="color:{_MUTED};font-size:13px;">{desc}</span>
          </td>
        </tr>"""
        for ico, title, desc in features
    )
    body = f"""
{_badge("YOU'RE IN")}
<br><br>
{_h1(f"Welcome to the edge, {name}! 🎉")}
{_p("Your email is verified and your account is fully active. "
    "The AI is already working — let's make some winning picks.")}
{_cta_button("🚀 Open My Dashboard", app_url)}
{_divider()}
<p style="margin:0 0 12px;font-size:13px;font-weight:700;color:{_MUTED};
           text-transform:uppercase;letter-spacing:1px;">What you get — free</p>
<table cellpadding="0" cellspacing="0" border="0" width="100%">
  {feat_rows}
</table>
<br>
"""
    plain = f"""Welcome to Smart Pick Pro, {name}!

Your email is verified and your account is fully active.

Open your dashboard: {app_url}

What you get for free:
- 6 Neural Networks (SAFE Score, ensemble modeling, edge detection)
- 300+ Props / Night (PrizePicks, DraftKings & Underdog)
- +18% Avg ROI (verified across 8,400+ graded picks)
- Instant access — no credit card

— Smart Pick Pro
https://smartpickpro.ai
"""
    return _wrap(f"Welcome to Smart Pick Pro, {name}!", body), plain
