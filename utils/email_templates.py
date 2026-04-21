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
_BG          = "#050810"
_CARD_BG     = "#0d1220"
_BORDER      = "#1a2540"
_ACCENT_1    = "#00d4ff"
_ACCENT_2    = "#7b2ff7"
_GREEN       = "#00D559"
_TEXT        = "#e0e6f0"
_MUTED       = "#8b9ab0"
_BTN_START   = "#00c3f0"
_BTN_END     = "#6a1fe0"
_SUCCESS     = "#00d48a"

# Logo served from GitHub raw content (public repo).
# Update _LOGO_URL if hosted elsewhere (CDN, Railway static mount, etc.).
_LOGO_URL = (
    "https://raw.githubusercontent.com/bucks551010/smart-pick-pro-pd"
    "/master/Smart_Pick_Pro_Logo.png"
)

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

    <!-- ── Logo header ─────────────────────────────────────────── -->
    <tr>
      <td style="padding:36px 24px 0;text-align:center;">
        <!--[if !mso]><!-->
        <img src="{logo_url}"
             alt="Smart Pick Pro — AI-Powered Sports Intelligence"
             width="140" height="auto"
             style="display:inline-block;max-width:140px;height:auto;
                    border:0;outline:0;text-decoration:none;" />
        <!--<![endif]-->
        <!--[if mso]>
        <div style="font-size:22px;font-weight:800;color:#00d4ff;
                    font-family:Arial,sans-serif;letter-spacing:-0.5px;">
          &#9889; SmartPickPro
        </div>
        <![endif]-->
      </td>
    </tr>

    <!-- ── Body card ───────────────────────────────────────────── -->
    <tr>
      <td style="padding:20px 24px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="background:{card};border:1px solid {border};\
border-radius:18px;overflow:hidden;">
          <!-- Animated-style gradient top bar (static gradient for email) -->
          <tr>
            <td style="height:4px;background:linear-gradient(90deg,{a1} 0%,{a2} 50%,{green} 100%);
                       padding:0;font-size:0;line-height:0;"></td>
          </tr>
          <tr>
            <td style="padding:36px 36px 0;">
              {body}
            </td>
          </tr>
          <!-- Footer inside card -->
          <tr>
            <td style="padding:24px 36px 28px;border-top:1px solid {border};margin-top:24px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-size:12px;color:{muted};line-height:1.7;">
                    You're receiving this because you subscribed to Smart Pick Pro.<br>
                    <a href="{app_url}" style="color:{a1};text-decoration:none;font-weight:600;">
                      smartpickpro.ai</a>
                    &nbsp;&middot;&nbsp;
                    <a href="mailto:support@smartpickpro.ai"
                       style="color:{muted};text-decoration:none;">support@smartpickpro.ai</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- Bottom padding -->
    <tr><td style="height:36px;"></td></tr>
  </table>
  <!--[if mso]></td></tr></table><![endif]-->
</body>
</html>"""


def _wrap(subject: str, body: str, app_url: str = "https://smartpickpro.ai") -> str:
    return _BASE_HTML.format(
        subject=subject,
        bg=_BG,
        card=_CARD_BG,
        border=_BORDER,
        a1=_ACCENT_1,
        a2=_ACCENT_2,
        green=_GREEN,
        text=_TEXT,
        muted=_MUTED,
        logo_url=_LOGO_URL,
        app_url=app_url,
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


def _stat_box(value: str, label: str, color: str = _ACCENT_1) -> str:
    return (
        f'<td style="text-align:center;padding:18px 12px;">'
        f'<div style="font-size:28px;font-weight:900;color:{color};'
        f'letter-spacing:-1px;line-height:1;">{value}</div>'
        f'<div style="font-size:11px;font-weight:700;color:{_MUTED};'
        f'text-transform:uppercase;letter-spacing:1.2px;margin-top:6px;">{label}</div>'
        f'</td>'
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


# ═══════════════════════════════════════════════════════════════════════════════
# DRIP SEQUENCE — 3-Part Post-Subscription Automated Emails
# Scheduled by notifications.schedule_drip_sequence()
# Fired by notifications.send_pending_drip_emails() (ETL scheduler)
#
# Step 0 (immediate) — render_paid_welcome_email()
# Step 1 (Day +2)    — render_day2_protip_email()
# Step 2 (Day +5)    — render_day5_roi_email()
# ═══════════════════════════════════════════════════════════════════════════════

def render_paid_welcome_email(
    display_name: str,
    plan_name: str = "Smart Pick Pro",
    app_url: str = "https://smartpickpro.ai",
) -> tuple[str, str]:
    """Email 1 (immediate) - Welcome to the Inner Circle.

    Returns (html, plain_text).
    """
    name = display_name or "there"
    plan = plan_name or "Smart Pick Pro"

    steps = [
        ("01", "#00D559", "Open the Quantum Analysis Matrix",
         "Sidebar ? QAM ? Analyze. The AI scans 300+ props and ranks every edge in seconds."),
        ("02", "#00d4ff", "Check Platform AI Picks",
         "Your personalized PrizePicks &amp; Underdog slate is updated every game night."),
        ("03", "#c084fc", "Read SAFE Scores &amp; Edge %",
         "SAFE 85+ means Tier-1 edge. Edge % is your sizing guide. Use both together."),
    ]
    step_rows = "".join(
        f"""<tr>
          <td style="padding:0 0 16px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="background:rgba(255,255,255,0.03);border:1px solid {_BORDER};
                          border-radius:12px;overflow:hidden;">
              <tr>
                <td style="width:5px;background:{color};padding:0;font-size:0;line-height:0;"></td>
                <td style="padding:15px 18px;">
                  <div style="font-size:10px;font-weight:800;color:{color};
                       text-transform:uppercase;letter-spacing:2px;margin-bottom:4px;">
                    Step {num}</div>
                  <div style="font-size:15px;font-weight:700;color:{_TEXT};
                       margin-bottom:4px;">{title}</div>
                  <div style="font-size:13px;color:{_MUTED};line-height:1.6;">{desc}</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""
        for num, color, title, desc in steps
    )

    body = f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:linear-gradient(135deg,rgba(0,212,255,0.07),rgba(123,47,247,0.07));
              border:1px solid rgba(0,212,255,0.15);border-radius:14px;margin-bottom:28px;">
  <tr>
    <td style="padding:28px 28px 22px;text-align:center;">
      <div style="display:inline-block;padding:5px 16px;border-radius:100px;
                  background:rgba(0,213,89,0.1);border:1px solid rgba(0,213,89,0.3);
                  font-size:11px;font-weight:800;color:#00D559;
                  text-transform:uppercase;letter-spacing:1.5px;margin-bottom:14px;">
        &#10003; {plan} Active
      </div>
      <h1 style="margin:0 0 10px;font-size:26px;font-weight:900;color:{_TEXT};
                 letter-spacing:-0.5px;line-height:1.2;">
        Welcome to the inner circle,&nbsp;{name}
      </h1>
      <p style="margin:0;font-size:14px;color:{_MUTED};line-height:1.7;">
        Your subscription is confirmed. The AI is scanning tonight's slate right now&nbsp;&mdash;<br>
        here's how to get your first edge in under&nbsp;3 minutes.
      </p>
    </td>
  </tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="border:1px solid {_BORDER};border-radius:12px;
              background:rgba(255,255,255,0.02);margin-bottom:28px;">
  <tr>
    <td style="text-align:center;padding:18px 12px;">
      <div style="font-size:28px;font-weight:900;color:{_ACCENT_1};letter-spacing:-1px;line-height:1;">300+</div>
      <div style="font-size:11px;font-weight:700;color:{_MUTED};text-transform:uppercase;letter-spacing:1.2px;margin-top:6px;">Props Nightly</div>
    </td>
    <td style="width:1px;background:{_BORDER};padding:0;"></td>
    <td style="text-align:center;padding:18px 12px;">
      <div style="font-size:28px;font-weight:900;color:#00D559;letter-spacing:-1px;line-height:1;">71.4%</div>
      <div style="font-size:11px;font-weight:700;color:{_MUTED};text-transform:uppercase;letter-spacing:1.2px;margin-top:6px;">Tier-1 Hit Rate</div>
    </td>
    <td style="width:1px;background:{_BORDER};padding:0;"></td>
    <td style="text-align:center;padding:18px 12px;">
      <div style="font-size:28px;font-weight:900;color:#c084fc;letter-spacing:-1px;line-height:1;">8,400+</div>
      <div style="font-size:11px;font-weight:700;color:{_MUTED};text-transform:uppercase;letter-spacing:1.2px;margin-top:6px;">Picks Graded</div>
    </td>
  </tr>
</table>

<p style="margin:0 0 14px;font-size:12px;font-weight:700;color:{_MUTED};
   text-transform:uppercase;letter-spacing:1.5px;">Your 3-Step Quickstart</p>
<table cellpadding="0" cellspacing="0" border="0" width="100%">
  {step_rows}
</table>

{_cta_button("&#128640; Launch Your Dashboard", app_url)}

<p style="margin:12px 0 28px;font-size:12px;color:{_MUTED};text-align:center;line-height:1.7;">
  Questions? Reply to this email or write to
  <a href="mailto:support@smartpickpro.ai"
     style="color:{_ACCENT_1};text-decoration:none;">support@smartpickpro.ai</a>
  &nbsp;&mdash;&nbsp;we typically respond within 2&nbsp;hours.
</p>
"""
    plain = f"""Welcome to the inner circle, {name}!

Your {plan} subscription is confirmed and active.

Stats: 300+ props analyzed nightly � 71.4% Tier-1 hit rate � 8,400+ picks graded

Launch your dashboard: {app_url}

YOUR 3-STEP QUICKSTART
----------------------
01. Open the Quantum Analysis Matrix
    Sidebar ? QAM ? Analyze. The AI scans 300+ props in seconds.

02. Check Platform AI Picks
    Your PrizePicks & Underdog slate updates every game night.

03. Read SAFE Scores & Edge %
    SAFE 85+ = Tier-1 edge. Edge % is your sizing guide.

Support: support@smartpickpro.ai (typically respond within 2 hours)

-- Smart Pick Pro � https://smartpickpro.ai
"""
    subject = f"Welcome to the inner circle \u2014 your {plan} is live \u26a1"
    return _wrap(subject, body, app_url), plain


def render_day2_protip_email(
    display_name: str,
    plan_name: str = "Smart Pick Pro",
    app_url: str = "https://smartpickpro.ai",
) -> tuple[str, str]:
    """Email 2 (Day +2) � The Pro-Tip: Filter by Tier.

    Returns (html, plain_text).
    """
    name = display_name or "there"
    qam_url = f"{app_url}/?page=qam"

    tiers = [
        ("#ff4757", "Tier 1 \u2014 Spec", "SAFE 85+",
         "Maximum edge. 2\u20133 picks per night. Build your highest-confidence entry here.",
         "71.4% hit rate"),
        ("#fbbf24", "Tier 2 \u2014 Value", "SAFE 70\u201384",
         "Strong value, broader coverage. Ideal for 3-pick and 5-pick flex slates.",
         "64.8% hit rate"),
        ("#00D559", "Tier 3 \u2014 Scout", "SAFE 55\u201369",
         "Supporting picks in larger entries only. Never build a slate from these alone.",
         "58.2% hit rate"),
    ]
    tier_rows = "".join(
        f"""<tr>
          <td style="padding:0 0 12px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="border:1px solid rgba(255,255,255,0.06);border-radius:12px;
                          background:rgba(255,255,255,0.02);overflow:hidden;">
              <tr>
                <td style="width:4px;background:{color};padding:0;font-size:0;line-height:0;"></td>
                <td style="padding:14px 16px;">
                  <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                      <td>
                        <div style="font-size:14px;font-weight:800;color:{_TEXT};
                             margin-bottom:3px;">{tier_name}</div>
                        <div style="font-size:11px;font-weight:700;color:{color};
                             text-transform:uppercase;letter-spacing:1px;">{safe_label}</div>
                        <div style="font-size:12px;color:{_MUTED};line-height:1.6;
                             margin-top:6px;">{desc}</div>
                      </td>
                      <td style="text-align:right;white-space:nowrap;padding-left:12px;
                                 vertical-align:top;">
                        <div style="display:inline-block;padding:4px 10px;border-radius:100px;
                                    background:rgba(255,255,255,0.05);
                                    font-size:11px;font-weight:700;color:{color};">
                          {stat}
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""
        for color, tier_name, safe_label, desc, stat in tiers
    )

    body = f"""
<h1 style="margin:0 0 8px;font-size:24px;font-weight:900;color:{_TEXT};
           letter-spacing:-0.5px;line-height:1.25;">
  The feature most users miss,&nbsp;{name}
</h1>
<p style="margin:0 0 24px;font-size:14px;color:{_MUTED};line-height:1.7;">
  Most subscribers see the picks.
  <strong style="color:{_TEXT};">Power users filter by tier.</strong>
  Here's the strategy that separates recreational bettors from edge players.
</p>

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:rgba(0,213,89,0.06);border:1px solid rgba(0,213,89,0.2);
              border-radius:12px;margin-bottom:28px;">
  <tr>
    <td style="padding:18px 20px;">
      <div style="font-size:11px;font-weight:800;color:#00D559;text-transform:uppercase;
                  letter-spacing:1.5px;margin-bottom:8px;">&#127919; The Key Insight</div>
      <p style="margin:0;font-size:14px;color:{_TEXT};line-height:1.7;">
        The <strong>SAFE Score</strong> (Statistical Analysis Framework Estimator) is a
        composite signal built from&nbsp;6&nbsp;neural models.
        Use the tier filter in QAM to surface only the picks that match your risk profile.
      </p>
    </td>
  </tr>
</table>

<p style="margin:0 0 14px;font-size:12px;font-weight:700;color:{_MUTED};
   text-transform:uppercase;letter-spacing:1.5px;">The SAFE Score Tier System</p>
<table cellpadding="0" cellspacing="0" border="0" width="100%">
  {tier_rows}
</table>

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:rgba(0,212,255,0.06);border:1px solid rgba(0,212,255,0.15);
              border-radius:12px;margin:20px 0 28px;">
  <tr>
    <td style="padding:18px 20px;">
      <div style="font-size:11px;font-weight:800;color:{_ACCENT_1};text-transform:uppercase;
                  letter-spacing:1.5px;margin-bottom:8px;">&#128161; Pro Move</div>
      <p style="margin:0;font-size:14px;color:{_TEXT};line-height:1.7;">
        On game nights, open QAM, set the filter to <strong>Tier&nbsp;1 only</strong>, and build
        your highest-edge slate from those 2\u20133 picks.
        Our backtested Tier&nbsp;1 hit rate is
        <strong style="color:{_SUCCESS};">71.4%</strong>
        across the last&nbsp;1,200 graded picks.
      </p>
    </td>
  </tr>
</table>

{_cta_button("&#127919; Open QAM &amp; Filter by Tier", qam_url)}

<p style="margin:12px 0 28px;font-size:12px;color:{_MUTED};text-align:center;">
  Tomorrow we'll show you the advanced ROI calculation strategy.
</p>
"""
    plain = f"""Hey {name}, here's the pro tip most users discover too late.

Most subscribers see the picks. Power users filter by tier.

THE SAFE SCORE TIER SYSTEM
--------------------------
  Tier 1 - Spec (SAFE 85+)      71.4% hit rate
  Highest edge. 2-3 picks per night. Best for max-confidence entries.

  Tier 2 - Value (SAFE 70-84)   64.8% hit rate
  Strong value, broader coverage. Good for 3-pick and 5-pick slates.

  Tier 3 - Scout (SAFE 55-69)   58.2% hit rate
  Supporting picks in larger entries only.

PRO MOVE: Set QAM filter to Tier 1 only on game nights.
Backtested Tier-1 hit rate: 71.4% across 1,200 graded picks.

Open QAM: {qam_url}
Tomorrow: the advanced ROI calculation strategy.

-- Smart Pick Pro � https://smartpickpro.ai
"""
    subject = f"The pro tip your edge depends on, {name} \U0001f3af"
    return _wrap(subject, body, app_url), plain


def render_day5_roi_email(
    display_name: str,
    plan_name: str = "Smart Pick Pro",
    app_url: str = "https://smartpickpro.ai",
) -> tuple[str, str]:
    """Email 3 (Day +5) � Maximizing Your ROI.

    Returns (html, plain_text).
    """
    name = display_name or "there"
    qam_url = f"{app_url}/?page=qam"

    rows = [
        ("Entry size rule",
         "Never risk more than 2\u20133% of bankroll on a single entry", False),
        ("SAFE 85+ (Tier 1)",
         "Maximum units \u2014 full entry at normal size", True),
        ("SAFE 70\u201384 (Tier 2)",
         "Standard units \u2014 normal sized entry", False),
        ("SAFE 55\u201369 (Tier 3)",
         "Half units \u2014 use only in larger flex entries", True),
        ("Edge % above 8%",
         "Strong edge \u2014 consider 1.5\u00d7 your standard entry size", False),
        ("Correlation filter",
         "Avoid stacking 3+ picks from the same game (correlated variance)", True),
    ]
    roi_rows = "".join(
        f"""<tr style="background:{'rgba(255,255,255,0.025)' if alt else 'transparent'};">
          <td style="padding:12px 16px;font-size:13px;font-weight:700;color:{_TEXT};
               border-bottom:1px solid {_BORDER};width:40%;">{label}</td>
          <td style="padding:12px 16px;font-size:13px;color:{_MUTED};
               border-bottom:1px solid {_BORDER};">{val}</td>
        </tr>"""
        for label, val, alt in rows
    )

    body = f"""
<h1 style="margin:0 0 8px;font-size:24px;font-weight:900;color:{_TEXT};
           letter-spacing:-0.5px;line-height:1.25;">
  How to maximize your long-term ROI,&nbsp;{name}
</h1>
<p style="margin:0 0 24px;font-size:14px;color:{_MUTED};line-height:1.7;">
  After 5 days with Smart Pick Pro, you've seen the picks. Now let's talk about
  <strong style="color:{_TEXT};">how professionals use them</strong> to build
  consistent, compounding returns \u2014 not just one-off wins.
</p>

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:linear-gradient(135deg,rgba(0,212,255,0.06),rgba(123,47,247,0.06));
              border:1px solid rgba(0,212,255,0.15);border-radius:12px;margin-bottom:28px;">
  <tr>
    <td style="padding:20px 22px;">
      <div style="font-size:11px;font-weight:800;color:{_ACCENT_1};text-transform:uppercase;
                  letter-spacing:1.5px;margin-bottom:8px;">&#128161; Core Principle</div>
      <p style="margin:0;font-size:14px;color:{_TEXT};line-height:1.75;">
        The AI gives you edge on every pick. Your job is to
        <strong style="color:{_ACCENT_1};">size entries according to that edge</strong>,
        not just pick winners.<br><br>
        A 65% hit rate with poor sizing still loses money.
        A 58% hit rate with disciplined sizing compounds consistently.
      </p>
    </td>
  </tr>
</table>

<p style="margin:0 0 14px;font-size:12px;font-weight:700;color:{_MUTED};
   text-transform:uppercase;letter-spacing:1.5px;">The Smart Pick Pro ROI Framework</p>
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="border:1px solid {_BORDER};border-radius:12px;overflow:hidden;
              margin-bottom:28px;">
  <tr style="background:rgba(0,212,255,0.06);">
    <td style="padding:10px 16px;font-size:11px;font-weight:700;color:{_MUTED};
        text-transform:uppercase;letter-spacing:1.2px;width:40%;">Signal</td>
    <td style="padding:10px 16px;font-size:11px;font-weight:700;color:{_MUTED};
        text-transform:uppercase;letter-spacing:1.2px;">Action</td>
  </tr>
  {roi_rows}
</table>

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:rgba(0,213,89,0.06);border:1px solid rgba(0,213,89,0.2);
              border-radius:12px;margin-bottom:28px;">
  <tr>
    <td style="padding:18px 20px;">
      <div style="font-size:11px;font-weight:800;color:#00D559;text-transform:uppercase;
                  letter-spacing:1.5px;margin-bottom:10px;">&#128200; Edge % as a Multiplier</div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="padding:0 16px 0 0;font-size:13px;color:{_TEXT};width:50%;">
            <strong>Edge 12%</strong>
            <span style="color:{_MUTED};font-size:12px;display:block;margin-top:3px;">
              \u2192 1.5\u00d7 your standard entry
            </span>
          </td>
          <td style="font-size:13px;color:{_TEXT};">
            <strong>Edge 6%</strong>
            <span style="color:{_MUTED};font-size:12px;display:block;margin-top:3px;">
              \u2192 0.5\u00d7 your standard entry
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>

{_cta_button("&#128200; Review Tonight's Edge Picks", qam_url)}

<p style="margin:12px 0 28px;font-size:12px;color:{_MUTED};text-align:center;line-height:1.7;">
  Questions or want a strategy consult? Reply to this email or write to
  <a href="mailto:support@smartpickpro.ai"
     style="color:{_ACCENT_1};text-decoration:none;">support@smartpickpro.ai</a>.
  We read every reply.
</p>
"""
    plain = f"""Hey {name}, let's talk long-term ROI strategy.

After 5 days with Smart Pick Pro, here's how professionals use picks
to build consistent, compounding returns.

CORE PRINCIPLE
--------------
The AI gives you edge on every pick.
Your job is to SIZE entries according to that edge, not just pick winners.

A 65% hit rate with poor sizing still loses money.
A 58% hit rate with disciplined sizing compounds consistently.

THE ROI FRAMEWORK
-----------------
Entry size rule:       Never risk more than 2-3% of bankroll per entry
SAFE 85+ (Tier 1):     Maximum units - full entry at normal size
SAFE 70-84 (Tier 2):   Standard units - normal sized entry
SAFE 55-69 (Tier 3):   Half units - use only in larger flex entries
Edge % above 8%:       Consider 1.5x your standard entry size
Correlation filter:    Avoid 3+ picks from the same game

EDGE % AS A MULTIPLIER
----------------------
  Edge 12% -> 1.5x standard entry
  Edge 6%  -> 0.5x standard entry

Review tonight's picks: {qam_url}
Support: support@smartpickpro.ai

-- Smart Pick Pro � https://smartpickpro.ai
"""
    subject = "How to maximize your ROI with Smart Pick Pro \U0001f4c8"
    return _wrap(subject, body, app_url), plain