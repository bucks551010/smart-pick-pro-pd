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
    """Email 1 (immediate) — 'Welcome to the Inner Circle'.

    Sent the moment Stripe confirms the subscription.
    Contains: tier confirmation, 3-step quickstart, Getting Started guide link,
    and support contact.

    Returns (html, plain_text).
    """
    name = display_name or "there"
    plan = plan_name or "Smart Pick Pro"
    guide_url = f"{app_url}/?guide=start"

    onboarding_rows = "".join(
        f"""<tr>
          <td style="padding:10px 0;vertical-align:top;width:32px;font-size:18px;">{ico}</td>
          <td style="padding:10px 0;vertical-align:top;">
            <strong style="color:{_TEXT};font-size:14px;">{title}</strong><br>
            <span style="color:{_MUTED};font-size:13px;">{desc}</span>
          </td>
        </tr>"""
        for ico, title, desc in [
            ("⚡", "Run the Quantum Analysis Matrix",
             "Navigate to QAM in the sidebar → hit Analyze. The AI scans 300+ props in seconds."),
            ("🎯", "Check Platform AI Picks",
             "Your personalized PrizePicks & Underdog recommendations are updated each game night."),
            ("📈", "Read the SAFE Score",
             "Every pick shows a SAFE Score (0-100). Anything above 75 is a high-confidence edge."),
        ]
    )

    body = f"""
{_badge(plan.upper())}
<br><br>
{_h1(f"Welcome to the inner circle, {name}! \U0001f389")}
{_p("Your subscription is confirmed and active. The AI is already processing tonight's "
    "slate \u2014 here's how to get your first winning edge in under 3 minutes.")}
{_cta_button("\U0001f680 Launch Your Dashboard", app_url)}
{_divider()}
<p style="margin:0 0 12px;font-size:13px;font-weight:700;color:{_MUTED};
   text-transform:uppercase;letter-spacing:1px;">Your 3-Step Quickstart</p>
<table cellpadding="0" cellspacing="0" border="0" width="100%">
  {onboarding_rows}
</table>
{_divider()}
<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:{_MUTED};
   text-transform:uppercase;letter-spacing:1px;">Getting Started Guide &amp; Support</p>
{_p(f'<a href="{guide_url}" style="color:{_ACCENT_1};text-decoration:none;">'
    f'\U0001f4d6 Getting Started Guide</a> \u2014 step-by-step walkthrough of every feature.')}
{_p(f'Questions? Reply to this email or reach us at '
    f'<a href="mailto:support@smartpickpro.ai" style="color:{_ACCENT_1};'
    f'text-decoration:none;">support@smartpickpro.ai</a> \u2014 we typically respond within 2 hours.')}
<br>
"""
    plain = f"""Welcome to the inner circle, {name}!

Your {plan} subscription is confirmed and active.

Launch your dashboard: {app_url}

Your 3-Step Quickstart:
1. Run the Quantum Analysis Matrix
   Go to QAM in the sidebar, hit Analyze. The AI scans 300+ props in seconds.

2. Check Platform AI Picks
   Your personalized PrizePicks & Underdog recommendations update each game night.

3. Read the SAFE Score
   Every pick shows a SAFE Score (0-100). Anything above 75 is a high-confidence edge.

Getting Started Guide: {guide_url}
Support: support@smartpickpro.ai (typically respond within 2 hours)

-- Smart Pick Pro
https://smartpickpro.ai
"""
    subject = f"Welcome to the inner circle \u2014 your {plan} is live \u26a1"
    return _wrap(subject, body), plain


def render_day2_protip_email(
    display_name: str,
    plan_name: str = "Smart Pick Pro",
    app_url: str = "https://smartpickpro.ai",
) -> tuple[str, str]:
    """Email 2 (Day +2) — 'The Pro-Tip'.

    Highlights the SAFE Score tier filter \u2014 the advanced feature most users
    discover late. Includes backtested hit-rate stats and exact usage strategy.

    Returns (html, plain_text).
    """
    name = display_name or "there"
    qam_url = f"{app_url}/?page=qam"

    tip_rows = "".join(
        f"""<tr>
          <td style="padding:8px 0;vertical-align:top;width:28px;font-size:16px;">{ico}</td>
          <td style="padding:8px 0;vertical-align:top;">
            <strong style="color:{_TEXT};font-size:14px;">{title}</strong><br>
            <span style="color:{_MUTED};font-size:13px;">{desc}</span>
          </td>
        </tr>"""
        for ico, title, desc in [
            ("\U0001f534", "Tier 1 \u2014 Spec (SAFE 85+)",
             "Highest edge. Typically 2\u20133 picks per night. Best for max-confidence entries."),
            ("\U0001f7e1", "Tier 2 \u2014 Value (SAFE 70\u201384)",
             "Strong value with broader coverage. Ideal for 3-pick and 5-pick slates."),
            ("\U0001f7e2", "Tier 3 \u2014 Scout (SAFE 55\u201369)",
             "Use as supporting picks in larger entries. Never build a slate from these alone."),
        ]
    )

    body = f"""
{_badge("PRO TIP")}
<br><br>
{_h1(f"The feature most users miss, {name}")}
{_p("Most subscribers see the picks. "
    f"<strong style='color:{_TEXT}'>Power users filter by tier.</strong> "
    "Here's the strategy that separates recreational bettors from edge players.")}
{_divider()}
<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:{_MUTED};
   text-transform:uppercase;letter-spacing:1px;">The SAFE Score Tier System</p>
{_p(f"The <strong style='color:{_TEXT}'>SAFE Score</strong> (Statistical Analysis Framework "
    "Estimator) is a composite signal built from 6 neural models. Use the tier filter in "
    "the QAM sidebar to surface only the picks that match your risk profile:")}
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="background:rgba(0,212,255,0.04);border:1px solid rgba(0,212,255,0.12);
              border-radius:10px;padding:8px 16px;">
  {tip_rows}
</table>
<br>
{_p(f"<strong style='color:{_TEXT}'>Pro move:</strong> On game nights, open QAM, set the "
    "filter to Tier 1 only, and build your highest-edge slate from those 2\u20133 picks. "
    "Our backtested Tier 1 hit rate is "
    f"<strong style='color:{_SUCCESS}'>71.4%</strong> "
    "across the last 1,200 graded picks.")}
{_cta_button("\U0001f3af Open QAM & Filter by Tier", qam_url)}
{_divider()}
{_p("Tomorrow we'll show you the advanced ROI calculation strategy. Stay tuned.",
    muted=True, small=True)}
<br>
"""
    plain = f"""Hey {name}, here's the pro tip most users discover too late.

Most subscribers see the picks. Power users filter by tier.

THE SAFE SCORE TIER SYSTEM
--------------------------
The SAFE Score is a composite signal from 6 neural models.
Filter by tier in the QAM sidebar to match your risk profile:

  Tier 1 - Spec (SAFE 85+)
  Highest edge. 2-3 picks per night. Best for max-confidence entries.

  Tier 2 - Value (SAFE 70-84)
  Strong value with broader coverage. Ideal for 3-pick and 5-pick slates.

  Tier 3 - Scout (SAFE 55-69)
  Use as supporting picks in larger entries only.

Pro move: Set the QAM filter to Tier 1 only.
Backtested Tier 1 hit rate: 71.4% across 1,200 graded picks.

Open QAM: {qam_url}

Tomorrow: the advanced ROI calculation strategy.

-- Smart Pick Pro
https://smartpickpro.ai
"""
    subject = f"The pro tip your edge depends on, {name} \U0001f3af"
    return _wrap(subject, body), plain


def render_day5_roi_email(
    display_name: str,
    plan_name: str = "Smart Pick Pro",
    app_url: str = "https://smartpickpro.ai",
) -> tuple[str, str]:
    """Email 3 (Day +5) — 'Maximizing Your ROI'.

    Long-term ROI strategy: bankroll sizing, SAFE tier stacking, and how to
    use Edge % for entry sizing decisions.

    Returns (html, plain_text).
    """
    name = display_name or "there"
    qam_url = f"{app_url}/?page=qam"

    roi_rows = "".join(
        f"""<tr>
          <td style="padding:10px 16px;border-bottom:1px solid {_BORDER};
              vertical-align:top;width:40%;">
            <strong style="color:{_TEXT};font-size:13px;">{label}</strong>
          </td>
          <td style="padding:10px 16px;border-bottom:1px solid {_BORDER};
              vertical-align:top;">
            <span style="color:{_MUTED};font-size:13px;">{val}</span>
          </td>
        </tr>"""
        for label, val in [
            ("Entry size rule",
             "Never risk more than 2\u20133% of bankroll on a single entry"),
            ("SAFE 85+ (Tier 1)",
             "Maximum units \u2014 full entry at normal size"),
            ("SAFE 70\u201384 (Tier 2)",
             "Standard units \u2014 normal sized entry"),
            ("SAFE 55\u201369 (Tier 3)",
             "Half units \u2014 use only in larger flex entries"),
            ("Edge % above 8%",
             "Strong edge \u2014 consider 1.5\u00d7 your standard entry size"),
            ("Correlation filter",
             "Avoid stacking 3+ picks from the same game (correlated variance)"),
        ]
    )

    body = f"""
{_badge("ROI STRATEGY")}
<br><br>
{_h1(f"How to maximize your long-term ROI, {name}")}
{_p("After 5 days with Smart Pick Pro, you've seen the picks. Now let's talk about "
    f"<strong style='color:{_TEXT}'>how professionals use them</strong> to build "
    "consistent, compounding returns \u2014 not just one-off wins.")}
{_divider()}
<p style="margin:0 0 12px;font-size:13px;font-weight:700;color:{_MUTED};
   text-transform:uppercase;letter-spacing:1px;">The Smart Pick Pro ROI Framework</p>
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="border:1px solid {_BORDER};border-radius:10px;overflow:hidden;">
  <tr style="background:rgba(0,212,255,0.06);">
    <td style="padding:8px 16px;font-size:12px;font-weight:700;color:{_MUTED};
        text-transform:uppercase;letter-spacing:1px;width:40%;">Signal</td>
    <td style="padding:8px 16px;font-size:12px;font-weight:700;color:{_MUTED};
        text-transform:uppercase;letter-spacing:1px;">Action</td>
  </tr>
  {roi_rows}
</table>
<br>
{_p(f"<strong style='color:{_TEXT}'>The core principle:</strong> The AI gives you edge on "
    "every pick. Your job is to "
    f"<strong style='color:{_ACCENT_1}'>size entries according to that edge</strong>, "
    "not just pick winners. A 65% hit rate with poor sizing still loses money. "
    "A 58% hit rate with disciplined sizing compounds consistently.")}
{_p("The Edge % shown on each pick in QAM is your sizing guide. Treat it as a multiplier: "
    "Edge 12% = 1.5\u00d7 standard entry. Edge 6% = 0.5\u00d7 standard entry.")}
{_cta_button("\U0001f4c8 Review Tonight's Edge Picks", qam_url)}
{_divider()}
{_p(f'Questions or want a strategy consult? Reply to this email or write to '
    f'<a href="mailto:support@smartpickpro.ai" style="color:{_ACCENT_1};text-decoration:none;">'
    f'support@smartpickpro.ai</a> \u2014 we read every reply.',
    muted=True, small=True)}
<br>
"""
    plain = f"""Hey {name}, let's talk about long-term ROI strategy.

After 5 days with Smart Pick Pro, you've seen the picks.
Here's how professionals use them to build consistent, compounding returns.

THE SMART PICK PRO ROI FRAMEWORK
----------------------------------
Entry size rule:       Never risk more than 2-3% of bankroll per entry
SAFE 85+ (Tier 1):     Maximum units - full entry at normal size
SAFE 70-84 (Tier 2):   Standard units - normal sized entry
SAFE 55-69 (Tier 3):   Half units - use only in larger flex entries
Edge % above 8%:       Consider 1.5x your standard entry size
Correlation filter:    Avoid 3+ picks from the same game

THE CORE PRINCIPLE
------------------
The AI gives you edge on every pick. Your job is to SIZE entries
according to that edge, not just pick winners.

Edge % as a multiplier:
  Edge 12% -> 1.5x standard entry
  Edge 6%  -> 0.5x standard entry

A 65% hit rate with poor sizing still loses money.
A 58% hit rate with disciplined sizing compounds consistently.

Review tonight's picks: {qam_url}
Support: support@smartpickpro.ai

-- Smart Pick Pro
https://smartpickpro.ai
"""
    subject = "How to maximize your ROI with Smart Pick Pro \U0001f4c8"
    return _wrap(subject, body), plain
