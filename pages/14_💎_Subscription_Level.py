# ============================================================
# FILE: pages/14_💎_Subscription_Level.py
# PURPOSE: SmartBetPro NBA subscription management page.
#          Shows pricing, feature comparison, and handles
#          Stripe Checkout redirects for new subscribers.
#          Existing subscribers can manage their plan via the
#          Stripe Customer Portal.
# ============================================================

import streamlit as st
import datetime

# ============================================================
# SECTION: Page Configuration (must be first Streamlit call)
# ============================================================

st.set_page_config(
    page_title="Premium — SmartBetPro NBA",
    page_icon="💎",
    layout="wide",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html, get_premium_footer_html
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ────────────────────────────
from utils.components import inject_joseph_floating
st.session_state["joseph_page_context"] = "page_premium"
inject_joseph_floating()

# ─── Premium Page Custom CSS ──────────────────────────────────
st.markdown("""
<style>
/* ── Hero Section ─────────────────────────────────────── */
.premium-hero {
    background: linear-gradient(135deg, #0a1428 0%, #0d1f3c 50%, #0a1428 100%);
    border: 1px solid rgba(0, 213, 89, 0.25);
    border-radius: 18px;
    padding: 40px 48px;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 32px;
    box-shadow: 0 0 60px rgba(0,213,89,0.07), 0 8px 40px rgba(0,0,0,0.6);
}
.premium-hero::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg,
        #00D559 0%, #00D559 25%, #F9C62B 60%, #2D9EFF 100%);
    background-size: 200% 100%;
    animation: heroShimmer 4s ease infinite;
}
@keyframes heroShimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
.hero-diamond {
    font-size: 4rem;
    animation: diamondFloat 3s ease-in-out infinite;
    display: block;
    margin-bottom: 12px;
}
@keyframes diamondFloat {
    0%, 100% { transform: translateY(0);   }
    50%       { transform: translateY(-8px); }
}
.hero-title {
    font-family: 'Inter', 'Courier New', monospace;
    font-size: 2.4rem;
    font-weight: 900;
    background: linear-gradient(90deg, #00D559, #00D559);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 8px;
}
.hero-subtitle {
    color: #A0AABE;
    font-size: 1.1rem;
    max-width: 560px;
    margin: 0 auto 24px;
    line-height: 1.7;
}
.hero-badge {
    display: inline-block;
    background: rgba(255, 94, 0, 0.18);
    border: 1px solid rgba(255, 94, 0, 0.45);
    color: #F9C62B;
    border-radius: 20px;
    padding: 4px 18px;
    font-size: 0.83rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* ── Pricing Card ─────────────────────────────────────── */
.pricing-card {
    background: rgba(14, 20, 40, 0.95);
    border: 2px solid rgba(0, 213, 89, 0.4);
    border-radius: 18px;
    padding: 36px 32px;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 40px rgba(0,213,89,0.13), 0 8px 32px rgba(0,0,0,0.5);
    max-width: 380px;
    margin: 0 auto;
}
.pricing-card::after {
    content: 'MOST POPULAR';
    position: absolute;
    top: 16px; right: -28px;
    background: linear-gradient(135deg, #F9C62B, #ff8c00);
    color: white;
    font-size: 0.65rem;
    font-weight: 800;
    padding: 4px 36px;
    transform: rotate(40deg);
    letter-spacing: 1.5px;
}
.price-amount {
    font-family: 'Inter', monospace;
    font-size: 3.2rem;
    font-weight: 900;
    color: #00D559;
    line-height: 1;
    text-shadow: 0 0 30px rgba(0,213,89,0.45);
}
.price-period {
    color: #607080;
    font-size: 0.9rem;
    margin-bottom: 20px;
}
.price-plan-name {
    font-family: 'Inter', monospace;
    font-size: 1.1rem;
    color: #00D559;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 2px;
}
.price-feature-list {
    list-style: none;
    padding: 0;
    margin: 16px 0 24px;
    text-align: left;
}
.price-feature-list li {
    color: #EEF0F6;
    font-size: 0.87rem;
    padding: 6px 0 6px 28px;
    position: relative;
    border-bottom: 1px solid rgba(0,213,89,0.06);
}
.price-feature-list li:last-child { border-bottom: none; }
.price-feature-list li::before {
    content: '✓';
    position: absolute;
    left: 4px;
    color: #00D559;
    font-weight: 800;
}

/* ── Feature Comparison Table ─────────────────────────── */
.compare-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 16px 0;
    font-size: 0.88rem;
}
.compare-table th {
    background: rgba(0, 213, 89, 0.08);
    color: #00D559;
    font-family: 'Inter', monospace;
    font-size: 0.78rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 12px 16px;
    border-bottom: 2px solid rgba(0,213,89,0.22);
    text-align: center;
}
.compare-table th:first-child { text-align: left; }
.compare-table td {
    padding: 10px 16px;
    border-bottom: 1px solid rgba(0,213,89,0.06);
    color: #b8c8e0;
    text-align: center;
    vertical-align: middle;
}
.compare-table td:first-child {
    text-align: left;
    color: #d0e0f8;
    font-weight: 500;
}
.compare-table tr:hover td {
    background: rgba(0,213,89,0.04);
}
.check-yes  { color: #00D559; font-size: 1.1rem; }
.check-no   { color: #3a4a60; font-size: 1.0rem; }
.check-limit { color: #ff9d00; font-size: 0.82rem; font-weight: 700; }

/* ── Status Cards ─────────────────────────────────────── */
.sub-status-card {
    background: rgba(0, 213, 89, 0.06);
    border: 1.5px solid rgba(0, 213, 89, 0.35);
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 24px;
    box-shadow: 0 0 24px rgba(0,213,89,0.08);
}
.sub-status-title {
    font-family: 'Inter', monospace;
    color: #00D559;
    font-size: 1.1rem;
    margin: 0 0 6px;
}
.sub-detail {
    color: #90aac8;
    font-size: 0.87rem;
    margin: 3px 0;
}
.sub-detail strong { color: #c8d8f0; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SECTION: Handle Stripe Checkout Redirect
# ============================================================

# When Stripe redirects back after payment, the URL contains
# ?session_id=XXX — we capture and verify it here.
from utils.auth import (
    handle_checkout_redirect,
    is_premium_user,
    get_subscription_status,
    restore_subscription_by_email,
    logout_premium,
)
from utils.stripe_manager import (
    is_stripe_configured,
    create_checkout_session,
    create_customer_portal_session,
    get_publishable_key,
)

# Check for cancelled checkout (user clicked "back" on Stripe)
params = st.query_params
if params.get("cancelled"):
    st.warning("⚠️ Checkout cancelled. You can try again anytime!")

# Process successful checkout redirect
newly_subscribed = handle_checkout_redirect()
if newly_subscribed:
    st.balloons()
    st.success(
        "🎉 **Welcome to SmartBetPro Premium!** "
        "Your subscription is now active. All premium features are unlocked."
    )

# ============================================================
# SECTION: Hero Banner
# ============================================================

st.markdown("""
<div class="premium-hero">
  <span class="hero-diamond">💎</span>
  <p class="hero-title">SmartBetPro Premium</p>
  <p class="hero-subtitle">
    Unlock the full power of our NBA AI — unlimited prop analysis,
    advanced Quantum Matrix Engine 5.6 simulations, parlay construction, risk
    management, and complete performance tracking.
  </p>
  <span class="hero-badge">🏀 NBA Season 2025-26</span>
</div>
""", unsafe_allow_html=True)

with st.expander("📖 How Subscriptions Work", expanded=False):
    st.markdown("""
    ### SmartBetPro Premium — What You Get
    
    **Free Tier**
    - View live scores and basic game information
    - Access Smart NBA Data for stats, standings & more
    - Limited analysis features
    
    **Premium Tier**
    - ⚡ Full Quantum Analysis Matrix with unlimited simulations
    - 🧬 Entry Builder for optimal parlay construction
    - 📋 AI Game Reports with SAFE Score™ breakdowns
    - 🔮 Player Simulator for scenario modeling
    - 📈 Bet Tracker with model health monitoring
    - 📊 Historical Backtester for strategy validation
    - 🎰 Vegas Vault for cross-book edge detection
    - 🎙️ Full Studio access with Joseph M. Smith AI analysis
    
    **How Payment Works**
    - Secure checkout through Stripe (industry-standard payment processor)
    - Cancel anytime — no long-term commitment
    - Your subscription status is verified automatically on each visit
    
    💡 **Already subscribed?** Your status appears at the top of this page. Use "Manage Subscription" to update billing or cancel.
    """)

# ============================================================
# SECTION: Subscriber View (already premium)
# ============================================================

sub_status = get_subscription_status()

if sub_status["is_premium"]:
    st.markdown("""
<div class="sub-status-card">
  <p class="sub-status-title">✅ Premium Active</p>
  <p class="sub-detail">You have full access to all SmartBetPro NBA features.</p>
</div>
""", unsafe_allow_html=True)

    # Show subscription details
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Plan", sub_status["plan_name"] or "Premium")
    with col_b:
        status_label = sub_status["status"].capitalize() if sub_status["status"] else "Active"
        st.metric("Status", status_label)
    with col_c:
        period_end = sub_status["period_end"]
        if period_end:
            try:
                end_dt = datetime.datetime.fromisoformat(period_end)
                next_billing = end_dt.strftime("%b %d, %Y")
            except Exception:
                next_billing = period_end[:10]
        else:
            next_billing = "—"
        st.metric("Next Billing", next_billing)

    st.divider()

    # Customer Portal Button (manage billing, cancel, etc.)
    customer_id = st.session_state.get("_sub_customer_id", "")
    if customer_id and is_stripe_configured():
        col_portal, col_logout, _ = st.columns([1, 1, 2])
        with col_portal:
            if st.button("⚙️ Manage Subscription", use_container_width=True):
                with st.spinner("Opening Stripe Customer Portal…"):
                    portal = create_customer_portal_session(customer_id)
                    if portal["success"]:
                        st.markdown(
                            f'<meta http-equiv="refresh" content="0; url={portal["url"]}">',
                            unsafe_allow_html=True,
                        )
                        st.info(
                            f"Redirecting to Stripe… [Click here if not redirected]({portal['url']})"
                        )
                    else:
                        st.error(f"Could not open portal: {portal['error']}")
        with col_logout:
            if st.button("🚪 Sign Out", use_container_width=True):
                logout_premium()
                st.rerun()
    elif is_stripe_configured():
        st.info(
            "To manage your subscription, visit "
            "[Stripe Customer Portal](https://billing.stripe.com) directly."
        )

    # Premium features quick-links
    st.subheader("🚀 Your Premium Features")
    feat_cols = st.columns(3)
    features = [
        ("🧬", "Entry Builder",     "pages/6_🧬_Entry_Builder.py"),
        ("🛡️", "Risk Shield",        "pages/8_🛡️_Risk_Shield.py"),
        ("📋", "Game Report",        "pages/4_📋_Game_Report.py"),
        ("🔮", "Player Simulator",  "pages/5_🔮_Player_Simulator.py"),
        ("📈", "Bet Tracker",        "pages/11_📈_Bet_Tracker.py"),
        ("🔬", "Full Prop Scanner",  "pages/2_🔬_Prop_Scanner.py"),
    ]
    for i, (icon, name, page) in enumerate(features):
        with feat_cols[i % 3]:
            if st.button(f"{icon} {name}", use_container_width=True, key=f"_prem_link_{i}"):
                st.switch_page(page)

    st.markdown(get_premium_footer_html(), unsafe_allow_html=True)
    st.stop()  # Don't show pricing section to existing subscribers

# ============================================================
# SECTION: Upgrade / Pricing Section (non-premium users)
# ============================================================

col_pricing, col_compare = st.columns([1, 2], gap="large")

with col_pricing:
    # ── Pricing Card ──────────────────────────────────────────
    st.markdown("""
<div class="pricing-card">
  <p class="price-plan-name">Premium Plan</p>
  <p class="price-amount">$9<span style="font-size:1.4rem">.99</span></p>
  <p class="price-period">per month &nbsp;·&nbsp; Cancel anytime</p>
  <ul class="price-feature-list">
    <li>Unlimited prop analysis</li>
    <li>Full Entry Builder (parlays + EV)</li>
    <li>Risk Shield — avoid traps</li>
    <li>AI Game Reports</li>
    <li>Player Quantum Matrix Simulator</li>
    <li>Bet Tracker &amp; model health</li>
    <li>Priority feature access</li>
    <li>Powered by Stripe — secure</li>
  </ul>
</div>
""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Subscribe Button ──────────────────────────────────────
    if is_stripe_configured():
        with st.form("checkout_form"):
            email_input = st.text_input(
                "Your email address (optional)",
                placeholder="you@example.com",
                help="Pre-fills the Stripe checkout form. Not required.",
            )
            subscribe_btn = st.form_submit_button(
                "🚀 Subscribe Now — $9.99/mo",
                type="primary",
                use_container_width=True,
            )

        if subscribe_btn:
            with st.spinner("Creating your checkout session…"):
                result = create_checkout_session(
                    customer_email=email_input.strip() if email_input else ""
                )
            if result["success"]:
                st.markdown(
                    f'<meta http-equiv="refresh" content="0; url={result["url"]}">',
                    unsafe_allow_html=True,
                )
                st.info(
                    f"Redirecting to Stripe Checkout… "
                    f"[Click here if not redirected]({result['url']})"
                )
            else:
                st.error(f"Checkout error: {result['error']}")
    else:
        # Stripe not configured — show "coming soon" message
        st.info(
            "**Subscriptions coming soon!** 🎉\n\n"
            "We're setting up secure payments via Stripe. "
            "In the meantime, all features are available for free.\n\n"
            "Check back soon for the paid launch."
        )

    # ── Restore Access ────────────────────────────────────────
    with st.expander("🔑 Already subscribed? Restore access"):
        st.markdown(
            "Enter the email you used when subscribing to restore your premium access."
        )
        restore_email = st.text_input(
            "Email address",
            key="_restore_email",
            placeholder="you@example.com",
        )
        if st.button("Restore Access", key="_restore_btn"):
            if not restore_email.strip():
                st.error("Please enter your email address.")
            else:
                with st.spinner("Looking up your subscription…"):
                    found = restore_subscription_by_email(restore_email.strip())
                if found:
                    st.success("✅ Premium access restored! Refreshing…")
                    st.rerun()
                else:
                    st.error(
                        "No active subscription found for that email. "
                        "Please check the address or contact support."
                    )

with col_compare:
    # ── Feature Comparison Table ──────────────────────────────
    st.markdown("### 📊 Free vs Premium")
    st.markdown("""
<table class="compare-table">
  <thead>
    <tr>
      <th>Feature</th>
      <th>⭐ Free</th>
      <th>💎 Premium</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>💦 Live Sweat</td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📡 Live Games (Vegas lines)</td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>⚙️ Settings &amp; Smart NBA Data</td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — Manual Entry</td>
      <td><span class="check-limit">Up to 5 props</span></td>
      <td><span class="check-yes">✓ Unlimited</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — CSV Upload</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — Live Platform Retrieval</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>⚡ Neural Analysis — Quantum Matrix Engine 5.6</td>
      <td><span class="check-limit">Up to 3 props</span></td>
      <td><span class="check-yes">✓ Unlimited</span></td>
    </tr>
    <tr>
      <td>🧬 Entry Builder (parlays + EV)</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🛡️ Risk Shield</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📋 AI Game Reports</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔮 Player Simulator</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📈 Bet Tracker &amp; Model Health</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

    # ── Education Box ─────────────────────────────────────────
    st.markdown(get_education_box_html(
        "💡 How the Subscription Works",
        """
        <strong>1. Click "Subscribe Now"</strong> — you'll be taken to Stripe's
        secure checkout page (we never see your card details).<br><br>
        <strong>2. Enter your payment info</strong> — Stripe handles everything.
        You'll receive a receipt email immediately.<br><br>
        <strong>3. Get redirected back here</strong> — your premium features
        unlock instantly. No waiting.<br><br>
        <strong>Returning subscriber?</strong> Use the "Restore Access" button
        and enter your email to reactivate on any device.<br><br>
        <strong>Cancel anytime</strong> — no contracts, no hidden fees.
        Cancel from the Customer Portal and you keep access until the end
        of your billing period.
        """,
    ), unsafe_allow_html=True)

# ============================================================
# SECTION: Footer
# ============================================================

st.divider()
st.markdown(get_premium_footer_html(), unsafe_allow_html=True)
