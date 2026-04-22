# ============================================================
# FILE: pages/15_💎_Subscription_Level.py
# PURPOSE: Smart Pick Pro subscription management page.
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
    page_title="Premium — Smart Pick Pro",
    page_icon="💎",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Subscription")
from utils.seo import inject_page_seo
inject_page_seo("Subscription")

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_premium_footer_html
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ────────────────────────────
from utils.components import inject_joseph_floating, inject_mobile_responsive_css, inject_aria_enhancements, render_sidebar_auth
st.session_state["joseph_page_context"] = "page_premium"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()
inject_mobile_responsive_css()
inject_aria_enhancements()

# ─── Premium Page Mega CSS ────────────────────────────────────
st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════════
   SMART PICK PRO — PREMIUM SUBSCRIPTION PAGE CSS
   ═══════════════════════════════════════════════════════════ */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --spp-green: #00D559;
    --spp-green-dim: rgba(0, 213, 89, 0.12);
    --spp-gold: #F9C62B;
    --spp-gold-dim: rgba(249, 198, 43, 0.12);
    --spp-purple: #c084fc;
    --spp-purple-dim: rgba(192, 132, 252, 0.12);
    --spp-blue: #2D9EFF;
    --spp-red: #F24336;
    --spp-bg-dark: #0a1428;
    --spp-bg-card: rgba(14, 20, 40, 0.95);
    --spp-text-primary: #EEF0F6;
    --spp-text-secondary: #A0AABE;
    --spp-text-dim: #607080;
    --spp-border: rgba(255,255,255,0.06);
}

/* ── Hero Section ─────────────────────────────────────── */
.prem-hero {
    background: linear-gradient(135deg, #060e1f 0%, #0d1f3c 30%, #0a1428 60%, #0f1a30 100%);
    border: 1px solid rgba(0, 213, 89, 0.2);
    border-radius: 24px;
    padding: 56px 48px 48px;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 40px;
    box-shadow: 0 0 80px rgba(0,213,89,0.06), 0 16px 64px rgba(0,0,0,0.7);
}
.prem-hero::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg,
        transparent 0%, #00D559 15%, #F9C62B 40%, #c084fc 65%, #2D9EFF 85%, transparent 100%);
    background-size: 300% 100%;
    animation: heroBarSlide 6s ease infinite;
}
.prem-hero::after {
    content: '';
    position: absolute;
    top: -50%; left: -50%; width: 200%; height: 200%;
    background: radial-gradient(ellipse at 50% 50%, rgba(0,213,89,0.04) 0%, transparent 60%);
    animation: heroGlow 8s ease-in-out infinite alternate;
    pointer-events: none;
}
@keyframes heroBarSlide {
    0%   { background-position: 300% 0; }
    100% { background-position: -300% 0; }
}
@keyframes heroGlow {
    0%   { opacity: 0.4; transform: scale(1); }
    100% { opacity: 1; transform: scale(1.1); }
}
.prem-hero-inner { position: relative; z-index: 2; }
.prem-hero-icon {
    font-size: 4.5rem;
    display: block;
    animation: iconFloat 3.5s ease-in-out infinite;
    margin-bottom: 8px;
    filter: drop-shadow(0 0 20px rgba(0,213,89,0.4));
}
@keyframes iconFloat {
    0%, 100% { transform: translateY(0) scale(1);   }
    50%      { transform: translateY(-10px) scale(1.05); }
}
.prem-hero-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 2.8rem;
    font-weight: 900;
    background: linear-gradient(135deg, #00D559 0%, #2D9EFF 50%, #c084fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 10px;
    letter-spacing: -0.5px;
}
.prem-hero-sub {
    color: #b0bcd0;
    font-size: 1.15rem;
    max-width: 640px;
    margin: 0 auto 28px;
    line-height: 1.75;
}
.prem-hero-badges {
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
}
.prem-hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 213, 89, 0.08);
    border: 1px solid rgba(0, 213, 89, 0.25);
    color: #00D559;
    border-radius: 100px;
    padding: 6px 18px;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    backdrop-filter: blur(8px);
}
.prem-hero-badge.gold {
    background: rgba(249, 198, 43, 0.08);
    border-color: rgba(249, 198, 43, 0.25);
    color: #F9C62B;
}
.prem-hero-badge.purple {
    background: rgba(192, 132, 252, 0.08);
    border-color: rgba(192, 132, 252, 0.25);
    color: #c084fc;
}

/* ── Stats Bar ────────────────────────────────────────── */
.stats-bar {
    display: flex;
    justify-content: center;
    gap: 40px;
    flex-wrap: wrap;
    margin: 32px auto 0;
    padding: 20px 0 0;
    border-top: 1px solid rgba(0,213,89,0.1);
}
.stat-item { text-align: center; }
.stat-number {
    font-family: 'Inter', monospace;
    font-size: 2rem;
    font-weight: 900;
    color: #00D559;
    line-height: 1;
    display: block;
    text-shadow: 0 0 20px rgba(0,213,89,0.3);
}
.stat-label {
    color: #708090;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
}

/* ── Section Header ───────────────────────────────────── */
.section-header {
    text-align: center;
    margin: 48px 0 32px;
}
.section-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--spp-text-primary);
    margin: 0 0 8px;
}
.section-subtitle {
    color: var(--spp-text-secondary);
    font-size: 1rem;
    max-width: 520px;
    margin: 0 auto;
    line-height: 1.6;
}

/* ── 4-Tier Pricing Grid ──────────────────────────────── */
.pricing-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin: 0 0 40px;
    align-items: start;
}
@media (max-width: 1000px) {
    .pricing-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
    .pricing-grid { grid-template-columns: 1fr; }
}
.p-card {
    background: var(--spp-bg-card);
    border: 2px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 32px 24px 28px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.p-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 12px 48px rgba(0,0,0,0.5);
}
.p-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    transition: opacity 0.3s ease;
}

.p-card.rookie  { border-color: rgba(160,170,190,0.25); }
.p-card.rookie::before  { background: linear-gradient(90deg, #708090, #A0AABE); }
.p-card.rookie:hover { border-color: rgba(160,170,190,0.5); box-shadow: 0 8px 40px rgba(112,128,144,0.15); }

.p-card.sharp   { border-color: rgba(249,198,43,0.3); }
.p-card.sharp::before   { background: linear-gradient(90deg, #F9C62B, #ff8c00); }
.p-card.sharp:hover { border-color: rgba(249,198,43,0.6); box-shadow: 0 8px 40px rgba(249,198,43,0.15); }

.p-card.smart   { border-color: rgba(0,213,89,0.35); }
.p-card.smart::before   { background: linear-gradient(90deg, #00D559, #2D9EFF); }
.p-card.smart:hover { border-color: rgba(0,213,89,0.6); box-shadow: 0 8px 40px rgba(0,213,89,0.15); }

.p-card.insider { border-color: rgba(192,132,252,0.35); }
.p-card.insider::before { background: linear-gradient(90deg, #c084fc, #9333ea); }
.p-card.insider:hover { border-color: rgba(192,132,252,0.6); box-shadow: 0 8px 40px rgba(192,132,252,0.15); }

.p-card-ribbon {
    position: absolute;
    top: 16px; right: -32px;
    font-size: 0.58rem;
    font-weight: 800;
    padding: 5px 40px;
    transform: rotate(40deg);
    letter-spacing: 1.5px;
    color: #fff;
    z-index: 3;
}
.p-card.smart .p-card-ribbon   { background: linear-gradient(135deg, #00D559, #00a847); }
.p-card.insider .p-card-ribbon { background: linear-gradient(135deg, #c084fc, #7c3aed); }

.p-card-icon { font-size: 2.8rem; margin-bottom: 10px; display: block; }
.p-card-name {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 0.95rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin: 0 0 4px;
}
.p-card.rookie  .p-card-name { color: #A0AABE; }
.p-card.sharp   .p-card-name { color: #F9C62B; }
.p-card.smart   .p-card-name { color: #00D559; }
.p-card.insider .p-card-name { color: #c084fc; }

.p-card-tagline {
    color: #506070;
    font-size: 0.78rem;
    font-style: italic;
    margin: 0 0 20px;
    min-height: 18px;
}

.p-card-price-wrap { margin: 0 0 6px; line-height: 1; }
.p-card-currency { font-size: 1.2rem; font-weight: 700; vertical-align: super; }
.p-card-amount   { font-family: 'Inter', monospace; font-size: 3rem; font-weight: 900; line-height: 1; }
.p-card-cents    { font-size: 1.2rem; font-weight: 700; vertical-align: super; }

.p-card.rookie  .p-card-currency, .p-card.rookie  .p-card-amount, .p-card.rookie  .p-card-cents { color: #A0AABE; }
.p-card.sharp   .p-card-currency, .p-card.sharp   .p-card-amount, .p-card.sharp   .p-card-cents { color: #F9C62B; }
.p-card.smart   .p-card-currency, .p-card.smart   .p-card-amount, .p-card.smart   .p-card-cents { color: #00D559; text-shadow: 0 0 24px rgba(0,213,89,0.35); }
.p-card.insider .p-card-currency, .p-card.insider .p-card-amount, .p-card.insider .p-card-cents { color: #c084fc; text-shadow: 0 0 24px rgba(192,132,252,0.35); }

.p-card-period { color: #506070; font-size: 0.82rem; margin: 4px 0 8px; }
.p-card-annual-note {
    display: inline-block;
    border-radius: 100px;
    padding: 3px 14px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    margin-bottom: 18px;
}
.p-card.sharp   .p-card-annual-note { background: rgba(249,198,43,0.1); border: 1px solid rgba(249,198,43,0.25); color: #F9C62B; }
.p-card.smart   .p-card-annual-note { background: rgba(0,213,89,0.1); border: 1px solid rgba(0,213,89,0.25); color: #00D559; }
.p-card.insider .p-card-annual-note { background: rgba(192,132,252,0.1); border: 1px solid rgba(192,132,252,0.25); color: #c084fc; }

.p-card-divider {
    width: 60%;
    height: 1px;
    margin: 0 auto 16px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
}

.p-card-features {
    list-style: none;
    padding: 0;
    margin: 0 0 20px;
    text-align: left;
}
.p-card-features li {
    color: #c0d0e8;
    font-size: 0.82rem;
    padding: 7px 0 7px 26px;
    position: relative;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    line-height: 1.5;
}
.p-card-features li:last-child { border-bottom: none; }
.p-card-features li::before {
    content: '✓';
    position: absolute;
    left: 2px;
    font-weight: 800;
    font-size: 0.85rem;
}
.p-card.rookie  .p-card-features li::before { color: #A0AABE; }
.p-card.sharp   .p-card-features li::before { color: #F9C62B; }
.p-card.smart   .p-card-features li::before { color: #00D559; }
.p-card.insider .p-card-features li::before { color: #c084fc; }

.p-card-features li.included-note {
    color: #708090;
    font-size: 0.75rem;
    font-style: italic;
    padding-left: 8px;
    border-bottom: none;
}
.p-card-features li.included-note::before { content: ''; }

.p-card-payment {
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,0.05);
    font-size: 0.72rem;
    color: #506070;
}
.p-card-payment .secure-icon { color: #00D559; }

/* ── Feature Comparison Table ─────────────────────────── */
.feat-table-wrap {
    overflow-x: auto;
    margin: 0 0 40px;
    border-radius: 16px;
    border: 1px solid rgba(0,213,89,0.12);
    background: var(--spp-bg-card);
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}
.feat-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
    min-width: 700px;
}
.feat-table thead th {
    position: sticky;
    top: 0;
    background: rgba(10, 20, 40, 0.98);
    padding: 16px 18px;
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    border-bottom: 2px solid rgba(0,213,89,0.15);
    text-align: center;
    z-index: 2;
}
.feat-table thead th:first-child { text-align: left; padding-left: 24px; }
.feat-table thead th.th-rookie  { color: #A0AABE; }
.feat-table thead th.th-sharp   { color: #F9C62B; }
.feat-table thead th.th-smart   { color: #00D559; }
.feat-table thead th.th-insider { color: #c084fc; }

.feat-table tbody td {
    padding: 12px 18px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    color: #b0c0d8;
    text-align: center;
    vertical-align: middle;
}
.feat-table tbody td:first-child {
    text-align: left;
    padding-left: 24px;
    color: #d0e0f8;
    font-weight: 500;
}
.feat-table tbody tr:hover td { background: rgba(0,213,89,0.03); }
.feat-table .feat-category td {
    background: rgba(0,213,89,0.04);
    color: #00D559;
    font-weight: 700;
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 10px 18px 10px 24px;
    border-bottom: 1px solid rgba(0,213,89,0.1);
}
.feat-yes   { color: #00D559; font-weight: 700; }
.feat-no    { color: #2a3548; }
.feat-limit { color: #ff9d00; font-weight: 700; font-size: 0.82rem; }
.feat-table tbody tr:last-child td { border-bottom: none; }

/* ── Testimonial Cards ────────────────────────────────── */
.testimonial-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin: 0 0 40px;
}
@media (max-width: 800px) {
    .testimonial-grid { grid-template-columns: 1fr; }
}
.testimonial-card {
    background: var(--spp-bg-card);
    border: 1px solid var(--spp-border);
    border-radius: 16px;
    padding: 24px;
    position: relative;
}
.testimonial-card::before {
    content: '"';
    font-size: 3rem;
    color: rgba(0,213,89,0.15);
    font-family: Georgia, serif;
    position: absolute;
    top: 10px; left: 16px;
    line-height: 1;
}
.testimonial-text {
    color: #c0d0e0;
    font-size: 0.88rem;
    line-height: 1.7;
    margin: 0 0 16px;
    padding-top: 12px;
}
.testimonial-author {
    display: flex;
    align-items: center;
    gap: 10px;
}
.testimonial-avatar {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    font-weight: 700;
}
.testimonial-author-info p { margin: 0; }
.testimonial-author-name {
    color: var(--spp-text-primary);
    font-weight: 700;
    font-size: 0.85rem;
}
.testimonial-author-plan { font-size: 0.72rem; font-weight: 600; }

/* ── Trust Badges ─────────────────────────────────────── */
.trust-row {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 32px;
    margin: 0 0 40px;
    padding: 24px 0;
    border-top: 1px solid rgba(255,255,255,0.04);
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.trust-item {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--spp-text-secondary);
    font-size: 0.85rem;
    font-weight: 600;
}
.trust-item .trust-icon { font-size: 1.4rem; }

/* ── FAQ ──────────────────────────────────────────────── */
.faq-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin: 0 0 40px;
}
@media (max-width: 700px) {
    .faq-grid { grid-template-columns: 1fr; }
}
.faq-item {
    background: var(--spp-bg-card);
    border: 1px solid var(--spp-border);
    border-radius: 14px;
    padding: 22px 24px;
}
.faq-q {
    color: var(--spp-text-primary);
    font-weight: 700;
    font-size: 0.9rem;
    margin: 0 0 8px;
    display: flex;
    align-items: flex-start;
    gap: 8px;
}
.faq-q-icon { color: #00D559; font-weight: 900; flex-shrink: 0; }
.faq-a {
    color: var(--spp-text-secondary);
    font-size: 0.84rem;
    line-height: 1.65;
    margin: 0;
    padding-left: 22px;
}

/* ── Subscriber Dashboard ─────────────────────────────── */
.sub-dash {
    background: linear-gradient(135deg, #060e1f 0%, #0d1f3c 50%, #0a1428 100%);
    border: 1.5px solid rgba(0, 213, 89, 0.3);
    border-radius: 20px;
    padding: 36px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 40px rgba(0,213,89,0.08);
}
.sub-dash::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #00D559, #2D9EFF, #c084fc);
}
.sub-dash-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
}
.sub-dash-icon {
    font-size: 2.5rem;
    animation: iconFloat 3s ease-in-out infinite;
}
.sub-dash-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    color: #00D559;
    margin: 0;
}
.sub-dash-subtitle {
    color: var(--spp-text-secondary);
    font-size: 0.88rem;
    margin: 2px 0 0;
}
.sub-dash-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}
@media (max-width: 800px) {
    .sub-dash-grid { grid-template-columns: repeat(2, 1fr); }
}
.sub-dash-stat {
    background: rgba(0,213,89,0.04);
    border: 1px solid rgba(0,213,89,0.12);
    border-radius: 14px;
    padding: 18px 16px;
    text-align: center;
}
.sub-dash-stat-value {
    font-family: 'Inter', monospace;
    font-size: 1.3rem;
    font-weight: 800;
    color: #00D559;
    display: block;
    margin-bottom: 4px;
}
.sub-dash-stat-label {
    color: #708090;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

/* ── Restore Section ──────────────────────────────────── */
.restore-card {
    background: var(--spp-bg-card);
    border: 1px solid rgba(0,213,89,0.15);
    border-radius: 16px;
    padding: 28px 32px;
    text-align: center;
    margin: 0 auto 40px;
    max-width: 560px;
}
.restore-card-icon { font-size: 2rem; margin-bottom: 8px; display: block; }
.restore-card-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--spp-text-primary);
    margin: 0 0 6px;
}
.restore-card-text {
    color: var(--spp-text-secondary);
    font-size: 0.85rem;
    margin: 0 0 16px;
}

/* ── Money-Back Guarantee Badge ───────────────────────── */
.guarantee-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    background: rgba(0,213,89,0.04);
    border: 1px solid rgba(0,213,89,0.15);
    border-radius: 14px;
    padding: 16px 24px;
    margin: 0 auto 40px;
    max-width: 600px;
    text-align: center;
}
.guarantee-icon { font-size: 2rem; }
.guarantee-text {
    color: var(--spp-text-secondary);
    font-size: 0.85rem;
    line-height: 1.5;
}
.guarantee-text strong { color: #00D559; }

</style>
""", unsafe_allow_html=True)

# ============================================================
# SECTION: Handle Stripe Checkout Redirect
# ============================================================

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

# Check for cancelled checkout
params = st.query_params
if params.get("cancelled"):
    st.warning("Checkout cancelled. You can try again anytime!")

# Process successful checkout redirect
newly_subscribed = handle_checkout_redirect()

# ── Profile Setup Imports ─────────────────────────────────────
from tracking.database import save_user_profile, load_user_profile, is_profile_complete
from utils.auth_gate import get_logged_in_email as _get_profile_email

_profile_email = st.session_state.get("_sub_customer_email", "") or _get_profile_email() or ""

# ── Helper: Check if profile wizard should be shown ──────────
def _should_show_profile_setup() -> bool:
    """Return True when a premium user hasn't completed the onboarding profile."""
    if st.session_state.get("_profile_just_completed"):
        return False
    if not _profile_email:
        return False
    sub = get_subscription_status()
    if not sub.get("is_premium"):
        return False
    return not is_profile_complete(_profile_email)

_show_profile_wizard = newly_subscribed or _should_show_profile_setup()

if _show_profile_wizard:
    if newly_subscribed:
        st.balloons()

    # ── Premium Profile Setup CSS ─────────────────────────────
    st.markdown("""
<style>
/* ── Profile Wizard — Premium Glassmorphism ──────────────── */
@keyframes profFadeIn   { from{ opacity:0; transform:translateY(24px); } to{ opacity:1; transform:translateY(0); } }
@keyframes profGradShift { 0%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } 100%{ background-position:0% 50%; } }
@keyframes profPulse { 0%,100%{ box-shadow: 0 0 20px rgba(0,213,89,0.15); } 50%{ box-shadow: 0 0 40px rgba(0,213,89,0.30), 0 0 60px rgba(45,158,255,0.10); } }
@keyframes profConfetti { 0%{ opacity:0; transform:scale(0.5) rotate(-10deg); } 50%{ opacity:1; transform:scale(1.05) rotate(2deg); } 100%{ opacity:1; transform:scale(1) rotate(0); } }

.prof-wizard {
    background: linear-gradient(135deg, rgba(22,27,39,0.92) 0%, rgba(13,15,20,0.95) 100%);
    backdrop-filter: blur(32px) saturate(1.3);
    -webkit-backdrop-filter: blur(32px) saturate(1.3);
    border: 1px solid rgba(0,213,89,0.20);
    border-radius: 24px;
    padding: 0;
    margin: 0 auto 32px;
    max-width: 720px;
    overflow: hidden;
    animation: profFadeIn 0.7s cubic-bezier(0.22,1,0.36,1) both, profPulse 4s ease-in-out infinite;
    position: relative;
}
.prof-wizard::before {
    content: '';
    position: absolute; top:0; left:0; right:0; height:4px;
    background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);
    background-size: 300% 100%;
    animation: profGradShift 5s ease infinite;
}
.prof-wizard-header {
    text-align: center;
    padding: 40px 32px 20px;
    position: relative;
}
.prof-wizard-badge {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: 80px; height: 80px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(0,213,89,0.12) 0%, rgba(45,158,255,0.08) 100%);
    border: 2px solid rgba(0,213,89,0.35);
    font-size: 2.4rem;
    margin-bottom: 16px;
    animation: profConfetti 0.8s cubic-bezier(0.22,1,0.36,1) 0.3s both;
    box-shadow: 0 0 30px rgba(0,213,89,0.20);
}
.prof-wizard-title {
    font-size: 1.6rem;
    font-weight: 900;
    font-family: 'Inter', sans-serif;
    background: linear-gradient(135deg, #FFFFFF 0%, #00D559 50%, #2D9EFF 100%);
    background-size: 200% 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: profGradShift 6s ease infinite;
    margin: 0; line-height: 1.3;
}
.prof-wizard-subtitle {
    font-size: 0.92rem;
    color: rgba(160,180,208,0.90);
    margin-top: 8px;
    line-height: 1.5;
}
.prof-wizard-subtitle strong { color: #00D559; font-weight: 700; }
.prof-wizard-body {
    padding: 8px 40px 36px;
}
.prof-wizard-body .stSelectbox > div > div,
.prof-wizard-body .stMultiSelect > div > div,
.prof-wizard-body .stTextInput > div > div > input {
    background: rgba(22,27,39,0.80) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 12px !important;
    color: #E0E8FF !important;
    font-family: 'Inter', sans-serif !important;
}
.prof-wizard-body .stSelectbox > div > div:hover,
.prof-wizard-body .stMultiSelect > div > div:hover,
.prof-wizard-body .stTextInput > div > div > input:focus {
    border-color: rgba(0,213,89,0.40) !important;
    box-shadow: 0 0 12px rgba(0,213,89,0.10) !important;
}
.prof-wizard-body label {
    color: #A0B4D0 !important;
    font-weight: 700 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}
.prof-step-label {
    display: inline-flex;
    align-items: center; gap: 8px;
    font-size: 0.72rem;
    font-weight: 800;
    color: rgba(0,213,89,0.70);
    text-transform: uppercase;
    letter-spacing: 0.10em;
    margin-bottom: 4px;
}
.prof-step-num {
    display: inline-flex;
    align-items: center; justify-content: center;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: rgba(0,213,89,0.12);
    border: 1px solid rgba(0,213,89,0.30);
    font-size: 0.68rem; font-weight: 900;
    color: #00D559;
}
.prof-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.15), rgba(45,158,255,0.10), transparent);
    margin: 20px 0;
}

/* ── Save Button Override (inside wizard) ────────────────── */
.prof-wizard-body .stButton > button[kind="primary"] {
    font-size: 1.05rem !important;
    padding: 16px 36px !important;
    min-height: 54px !important;
    background: linear-gradient(135deg, #00D559 0%, #00C04B 40%, #2D9EFF 100%) !important;
    background-size: 250% 250% !important;
    animation: profGradShift 5s ease infinite !important;
    color: #0D0F14 !important;
    font-weight: 900 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border-radius: 100px !important;
    border: none !important;
    box-shadow: 0 4px 24px rgba(0,213,89,0.35) !important;
    transition: all 0.22s cubic-bezier(0.22,1,0.36,1) !important;
}
.prof-wizard-body .stButton > button[kind="primary"]:hover {
    transform: translateY(-3px) scale(1.02) !important;
    box-shadow: 0 8px 36px rgba(0,213,89,0.50), 0 0 60px rgba(0,213,89,0.15) !important;
}

/* ── Skip Link ────────────────────────────────────────────── */
.prof-skip-link {
    text-align: center;
    margin-top: 12px;
}
.prof-skip-link a {
    color: #6B7A9A;
    font-size: 0.78rem;
    text-decoration: none;
    transition: color 0.2s ease;
}
.prof-skip-link a:hover { color: #A0B4D0; }

@media (max-width: 640px) {
    .prof-wizard { margin: 0 -8px 24px; border-radius: 16px; }
    .prof-wizard-header { padding: 28px 20px 14px; }
    .prof-wizard-body { padding: 8px 20px 28px; }
    .prof-wizard-title { font-size: 1.25rem; }
    .prof-wizard-badge { width: 64px; height: 64px; font-size: 1.8rem; }
}
</style>
""", unsafe_allow_html=True)

    # ── Profile Wizard Header ─────────────────────────────────
    _plan = st.session_state.get("_sub_plan_name", "Premium")
    _tier_icon = "👑" if "insider" in _plan.lower() else ("💎" if "smart money" in _plan.lower() else "🔥")

    st.markdown(f"""
<div class="prof-wizard">
  <div class="prof-wizard-header">
    <div class="prof-wizard-badge">{_tier_icon}</div>
    <div class="prof-wizard-title">Welcome to {_plan}!</div>
    <div class="prof-wizard-subtitle">
        {"<strong>Payment confirmed.</strong> " if newly_subscribed else ""}Let's personalize your experience.<br>
        Set up your profile so Smart Pick Pro works exactly how you want it.
    </div>
  </div>
  <div class="prof-wizard-body" id="prof-wizard-form">
""", unsafe_allow_html=True)

    # ── Step 1: Identity ──────────────────────────────────────
    st.markdown('<div class="prof-step-label"><span class="prof-step-num">1</span> YOUR IDENTITY</div>', unsafe_allow_html=True)

    _existing_profile = load_user_profile(_profile_email) or {}
    _default_name = _existing_profile.get("display_name", "") or st.session_state.get("_auth_user_name", "") or ""

    prof_display_name = st.text_input(
        "Display Name",
        value=_default_name,
        placeholder="e.g. SharpShooter23",
        key="_prof_display_name",
        help="This is how you'll appear in the app",
    )

    st.markdown('<div class="prof-divider"></div>', unsafe_allow_html=True)

    # ── Step 2: Favorite Team ─────────────────────────────────
    st.markdown('<div class="prof-step-label"><span class="prof-step-num">2</span> FAVORITE TEAM</div>', unsafe_allow_html=True)

    _NBA_TEAMS = [
        "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
        "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
        "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers",
        "LA Clippers", "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
        "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans",
        "New York Knicks", "Oklahoma City Thunder", "Orlando Magic",
        "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
        "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors",
        "Utah Jazz", "Washington Wizards",
    ]
    _saved_team = _existing_profile.get("favorite_team", "")
    _team_idx = (_NBA_TEAMS.index(_saved_team) + 1) if _saved_team in _NBA_TEAMS else 0
    prof_team = st.selectbox(
        "Favorite NBA Team",
        options=["— Select a team —"] + _NBA_TEAMS,
        index=_team_idx,
        key="_prof_favorite_team",
    )

    st.markdown('<div class="prof-divider"></div>', unsafe_allow_html=True)

    # ── Step 3: Preferred Platforms ───────────────────────────
    st.markdown('<div class="prof-step-label"><span class="prof-step-num">3</span> BETTING PLATFORMS</div>', unsafe_allow_html=True)

    _PLATFORMS = ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6", "Sleeper", "Betr", "Chalkboard"]
    _saved_plats = (_existing_profile.get("preferred_platforms") or "").split(",") if _existing_profile.get("preferred_platforms") else ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"]
    _saved_plats = [p for p in _saved_plats if p in _PLATFORMS]
    prof_platforms = st.multiselect(
        "Which platforms do you use?",
        options=_PLATFORMS,
        default=_saved_plats,
        key="_prof_platforms",
        help="We'll prioritize lines from these platforms",
    )

    st.markdown('<div class="prof-divider"></div>', unsafe_allow_html=True)

    # ── Step 4: Experience & Style ────────────────────────────
    st.markdown('<div class="prof-step-label"><span class="prof-step-num">4</span> BETTING PROFILE</div>', unsafe_allow_html=True)

    _exp_opts = ["Beginner — Just getting started", "Intermediate — I know the basics", "Advanced — Seasoned bettor", "Pro — I do this full-time"]
    _saved_exp = _existing_profile.get("experience_level", "")
    _exp_idx = next((i for i, o in enumerate(_exp_opts) if o.startswith(_saved_exp.split(" —")[0] if _saved_exp else "")), 0)
    prof_c1, prof_c2 = st.columns(2)
    with prof_c1:
        prof_experience = st.selectbox(
            "Experience Level",
            options=_exp_opts,
            index=_exp_idx,
            key="_prof_experience",
        )
    with prof_c2:
        _style_opts = ["Conservative — Low risk, steady gains", "Balanced — Mix of safe & aggressive", "Aggressive — High risk, high reward", "Sniper — Selective, high-conviction only"]
        _saved_style = _existing_profile.get("betting_style", "")
        _style_idx = next((i for i, o in enumerate(_style_opts) if o.startswith(_saved_style.split(" —")[0] if _saved_style else "")), 1)
        prof_style = st.selectbox(
            "Betting Style",
            options=_style_opts,
            index=_style_idx,
            key="_prof_style",
        )

    st.markdown('<div class="prof-divider"></div>', unsafe_allow_html=True)

    # ── Step 5: Daily Budget ──────────────────────────────────
    st.markdown('<div class="prof-step-label"><span class="prof-step-num">5</span> DAILY BUDGET</div>', unsafe_allow_html=True)

    _budget_opts = ["$5 – $25", "$25 – $50", "$50 – $100", "$100 – $250", "$250+", "Prefer not to say"]
    _saved_budget = _existing_profile.get("daily_budget", "")
    _budget_idx = _budget_opts.index(_saved_budget) if _saved_budget in _budget_opts else 0
    prof_budget = st.selectbox(
        "Typical daily betting budget",
        options=_budget_opts,
        index=_budget_idx,
        key="_prof_budget",
        help="Helps us calibrate bankroll recommendations",
    )

    # ── Save Profile Button ───────────────────────────────────
    st.markdown("")  # spacer
    if st.button("🚀 COMPLETE SETUP & ENTER APP", type="primary", use_container_width=True, key="_prof_save_btn"):
        _profile_data = {
            "display_name": prof_display_name.strip() or _profile_email.split("@")[0],
            "favorite_team": prof_team if prof_team != "— Select a team —" else "",
            "preferred_platforms": ",".join(prof_platforms),
            "experience_level": prof_experience.split(" —")[0],
            "betting_style": prof_style.split(" —")[0],
            "daily_budget": prof_budget,
        }
        _saved_ok = save_user_profile(_profile_email, _profile_data)
        if _saved_ok:
            # Apply platform selection to session
            if prof_platforms:
                st.session_state["selected_platforms"] = prof_platforms
            st.session_state["_profile_just_completed"] = True
            st.rerun()
        else:
            st.error("Could not save profile. Please try again.")

    # ── Skip link ─────────────────────────────────────────────
    _skip_c1, _skip_c2, _skip_c3 = st.columns([1, 2, 1])
    with _skip_c2:
        if st.button("Skip for now →", key="_prof_skip_btn", use_container_width=True):
            st.session_state["_profile_just_completed"] = True
            st.rerun()

    # Close the wizard div
    st.markdown('</div></div>', unsafe_allow_html=True)

# ── Profile completed success toast ───────────────────────────
if st.session_state.get("_profile_just_completed") and not _show_profile_wizard:
    _p = load_user_profile(_profile_email)
    if _p and _p.get("profile_complete"):
        _welcome_name = _p.get("display_name") or _profile_email.split("@")[0]
        st.markdown(f"""
<div style="
    background: linear-gradient(135deg, rgba(0,213,89,0.08) 0%, rgba(45,158,255,0.04) 100%);
    border: 1px solid rgba(0,213,89,0.25);
    border-radius: 16px;
    padding: 20px 28px;
    text-align: center;
    margin-bottom: 20px;
    animation: profFadeIn 0.5s ease both;
">
    <span style="font-size:1.5rem;">✨</span>
    <span style="color:#FFFFFF; font-weight:800; font-size:1.05rem; margin-left:8px;">
        Welcome, {_welcome_name}!
    </span>
    <span style="color:#A0B4D0; font-size:0.88rem; margin-left:8px;">
        Your profile is set up. All premium features are unlocked.
    </span>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SECTION: Subscriber Dashboard (already premium)
# ============================================================

sub_status = get_subscription_status()

if sub_status["is_premium"]:
    plan_name = sub_status["plan_name"] or "Premium"
    status_label = (sub_status["status"] or "active").capitalize()
    period_end = sub_status["period_end"]
    next_billing = "—"
    days_remaining = "—"
    if period_end:
        try:
            end_dt = datetime.datetime.fromisoformat(period_end)
            next_billing = end_dt.strftime("%b %d, %Y")
            delta = end_dt - datetime.datetime.now(datetime.timezone.utc)
            days_remaining = str(max(delta.days, 0))
        except Exception:
            next_billing = period_end[:10] if period_end else "—"

    st.markdown(f"""
<div class="sub-dash">
  <div class="sub-dash-header">
    <span class="sub-dash-icon">💎</span>
    <div>
      <p class="sub-dash-title">Welcome Back, Premium Member</p>
      <p class="sub-dash-subtitle">Your Smart Pick Pro subscription is active and all features are unlocked.</p>
    </div>
  </div>
  <div class="sub-dash-grid">
    <div class="sub-dash-stat">
      <span class="sub-dash-stat-value">{plan_name}</span>
      <span class="sub-dash-stat-label">Current Plan</span>
    </div>
    <div class="sub-dash-stat">
      <span class="sub-dash-stat-value" style="color:#00D559;">● {status_label}</span>
      <span class="sub-dash-stat-label">Status</span>
    </div>
    <div class="sub-dash-stat">
      <span class="sub-dash-stat-value">{next_billing}</span>
      <span class="sub-dash-stat-label">Next Billing</span>
    </div>
    <div class="sub-dash-stat">
      <span class="sub-dash-stat-value">{days_remaining}</span>
      <span class="sub-dash-stat-label">Days Remaining</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Action Buttons ────────────────────────────────────────
    customer_id = st.session_state.get("_sub_customer_id", "")
    if customer_id and is_stripe_configured():
        col_portal, col_cancel, col_logout, _ = st.columns([1, 1, 1, 1])
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
        with col_cancel:
            if st.button("❌ Cancel Subscription", use_container_width=True, key="_cancel_sub_btn"):
                st.session_state["_show_cancel_confirm"] = True
        with col_logout:
            if st.button("🚪 Sign Out", use_container_width=True):
                logout_premium()
                st.rerun()

        # ── Cancel Confirmation Dialog ────────────────────────
        if st.session_state.get("_show_cancel_confirm"):
            st.warning(
                "⚠️ **Are you sure you want to cancel?** "
                "You'll keep access until the end of your current billing period."
            )
            _cc1, _cc2, _cc3 = st.columns([1, 1, 2])
            with _cc1:
                if st.button("✅ Yes, Cancel", type="primary", key="_confirm_cancel"):
                    with st.spinner("Redirecting to cancellation portal…"):
                        portal = create_customer_portal_session(customer_id)
                        if portal["success"]:
                            st.session_state.pop("_show_cancel_confirm", None)
                            st.markdown(
                                f'<meta http-equiv="refresh" content="0; url={portal["url"]}">',
                                unsafe_allow_html=True,
                            )
                            st.info(
                                f"Redirecting to Stripe… [Click here if not redirected]({portal['url']})"
                            )
                        else:
                            st.error(f"Could not open portal: {portal['error']}")
            with _cc2:
                if st.button("🔙 Keep My Plan", key="_keep_plan"):
                    st.session_state.pop("_show_cancel_confirm", None)
                    st.rerun()
    elif is_stripe_configured():
        st.info(
            "To manage your subscription, visit "
            "[Stripe Customer Portal](https://billing.stripe.com) directly."
        )

    st.divider()

    # ── Quick-Access Feature Grid ─────────────────────────────
    st.markdown("### 🚀 Your Premium Features")
    st.markdown(
        '<p style="color:#A0AABE;font-size:0.9rem;margin-top:-8px;margin-bottom:16px;">'
        'Jump directly to any premium tool below.</p>',
        unsafe_allow_html=True,
    )
    feat_cols = st.columns(3)
    features = [
        ("🧬", "Entry Builder",      "pages/8_🧬_Entry_Builder.py"),
        ("🛡️", "Risk Shield",        "pages/9_🛡️_Risk_Shield.py"),
        ("📋", "Game Report",        "pages/6_📋_Game_Report.py"),
        ("🔮", "Player Simulator",   "pages/7_🔮_Player_Simulator.py"),
        ("📈", "Bet Tracker",        "pages/12_📈_Bet_Tracker.py"),
        ("🔬", "Prop Scanner",       "pages/2_🔬_Prop_Scanner.py"),
        ("💰", "Smart Money Bets",   "pages/4_💰_Smart_Money_Bets.py"),
        ("🗺️", "Correlation Matrix", "pages/11_🗺️_Correlation_Matrix.py"),
        ("🎙️", "The Studio",         "pages/5_🎙️_The_Studio.py"),
    ]
    for i, (icon, name, page) in enumerate(features):
        with feat_cols[i % 3]:
            if st.button(f"{icon} {name}", use_container_width=True, key=f"_prem_link_{i}"):
                st.switch_page(page)

    st.markdown(get_premium_footer_html(), unsafe_allow_html=True)
    st.stop()

# ============================================================
# SECTION: Non-Premium View — Full Pricing Page
# ============================================================

# ── HERO ──────────────────────────────────────────────────────
st.markdown("""
<div class="prem-hero">
  <div class="prem-hero-inner">
    <span class="prem-hero-icon">💎</span>
    <p class="prem-hero-title">Smart Pick Pro Premium</p>
    <p class="prem-hero-sub">
      The sharpest AI-powered NBA prop analysis platform on the market.
      Four tiers designed for every level — from casual fans to full-time sharps.
    </p>
    <div class="prem-hero-badges">
      <span class="prem-hero-badge">🤖 AI-Powered Analysis</span>
      <span class="prem-hero-badge gold">🏀 NBA 2025-26 Season</span>
      <span class="prem-hero-badge purple">⚡ Real-Time Props</span>
    </div>
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-number">300+</span>
        <span class="stat-label">Daily Props Analyzed</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">15+</span>
        <span class="stat-label">Premium Tools</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">24/7</span>
        <span class="stat-label">Live Data Feeds</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">4</span>
        <span class="stat-label">Subscription Tiers</span>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── PRICING SECTION HEADER + BILLING TOGGLE ─────────────────
st.markdown("""
<style>
/* ── Billing Toggle ─────────────────────────────────────── */
.billing-toggle-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin: 40px 0 0;
}
.billing-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    font-weight: 700;
    color: rgba(255,255,255,.45);
    letter-spacing: .02em;
    transition: color .2s;
}
.billing-label.active { color: #fff; }
.billing-save-badge {
    display: inline-flex;
    align-items: center;
    background: linear-gradient(135deg, #00D559, #00a847);
    color: #000;
    font-size: .58rem;
    font-weight: 900;
    letter-spacing: .1em;
    padding: 3px 10px;
    border-radius: 100px;
    margin-left: 6px;
    text-transform: uppercase;
}

/* ── Pricing cards — premium 2026 redesign ─────────────── */
.pricing-grid-v2 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
    margin: 32px 0 12px;
    align-items: stretch;
}
@media (max-width: 1100px) { .pricing-grid-v2 { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px)  { .pricing-grid-v2 { grid-template-columns: 1fr; } }

.pc2 {
    background: rgba(10,16,32,.92);
    border-radius: 22px;
    padding: 0;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
    transition: transform .25s cubic-bezier(.22,1,.36,1), box-shadow .25s;
    border: 1.5px solid rgba(255,255,255,.07);
}
.pc2:hover { transform: translateY(-8px); }
.pc2-top-bar { height: 3px; width: 100%; }
.pc2.rookie  .pc2-top-bar { background: linear-gradient(90deg,#708090,#A0AABE); }
.pc2.sharp   .pc2-top-bar { background: linear-gradient(90deg,#F9C62B,#ff8c00); }
.pc2.smart   .pc2-top-bar { background: linear-gradient(90deg,#00D559,#2D9EFF); }
.pc2.insider .pc2-top-bar { background: linear-gradient(90deg,#c084fc,#9333ea); }

.pc2.sharp:hover   { border-color:rgba(249,198,43,.4);  box-shadow: 0 20px 60px rgba(249,198,43,.14); }
.pc2.smart:hover   { border-color:rgba(0,213,89,.45);   box-shadow: 0 20px 60px rgba(0,213,89,.16); }
.pc2.insider:hover { border-color:rgba(192,132,252,.45);box-shadow: 0 20px 60px rgba(192,132,252,.15); }

/* Popular badge */
.pc2-badge {
    position: absolute;
    top: 16px; right: -28px;
    font-size: .52rem;
    font-weight: 900;
    letter-spacing: .12em;
    padding: 5px 36px;
    transform: rotate(42deg);
    text-transform: uppercase;
    color: #fff;
    z-index: 4;
}
.pc2.smart   .pc2-badge { background: linear-gradient(135deg,#00D559,#00a847); }
.pc2.insider .pc2-badge { background: linear-gradient(135deg,#c084fc,#7c3aed); }

.pc2-body { padding: 28px 24px 24px; flex: 1; display: flex; flex-direction: column; }

.pc2-icon { font-size: 2.4rem; margin-bottom: 8px; display: block; }
.pc2-tier {
    font-family: 'Inter', sans-serif;
    font-size: .72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .2em;
    margin: 0 0 2px;
}
.pc2.rookie  .pc2-tier { color: #A0AABE; }
.pc2.sharp   .pc2-tier { color: #F9C62B; }
.pc2.smart   .pc2-tier { color: #00D559; }
.pc2.insider .pc2-tier { color: #c084fc; }

.pc2-tagline {
    font-size: .72rem;
    color: rgba(255,255,255,.28);
    font-style: italic;
    margin: 0 0 22px;
}

/* Price display */
.pc2-price-row { margin: 0 0 4px; line-height: 1; display: flex; align-items: flex-start; gap: 2px; }
.pc2-curr { font-size: 1rem; font-weight: 700; padding-top: 6px; }
.pc2-amt  { font-family: 'Inter', monospace; font-size: 2.8rem; font-weight: 900; line-height: 1; }
.pc2-cents{ font-size: 1rem; font-weight: 700; padding-top: 6px; }
.pc2.rookie  .pc2-curr, .pc2.rookie  .pc2-amt, .pc2.rookie  .pc2-cents { color: #A0AABE; }
.pc2.sharp   .pc2-curr, .pc2.sharp   .pc2-amt, .pc2.sharp   .pc2-cents { color: #F9C62B; }
.pc2.smart   .pc2-curr, .pc2.smart   .pc2-amt, .pc2.smart   .pc2-cents { color: #00D559; text-shadow: 0 0 24px rgba(0,213,89,.3); }
.pc2.insider .pc2-curr, .pc2.insider .pc2-amt, .pc2.insider .pc2-cents { color: #c084fc; text-shadow: 0 0 24px rgba(192,132,252,.3); }

.pc2-period { color: rgba(255,255,255,.3); font-size: .72rem; margin: 2px 0 6px; }
.pc2-savings {
    display: inline-flex; align-items: center;
    background: rgba(0,213,89,.1); border: 1px solid rgba(0,213,89,.2);
    color: #00D559; font-size: .58rem; font-weight: 800;
    padding: 3px 10px; border-radius: 100px; margin-bottom: 16px;
    letter-spacing: .06em;
}
.pc2.sharp .pc2-savings { background:rgba(249,198,43,.1);border-color:rgba(249,198,43,.2);color:#F9C62B; }
.pc2.insider .pc2-savings { background:rgba(192,132,252,.1);border-color:rgba(192,132,252,.2);color:#c084fc; }

.pc2-divider { height:1px; background:linear-gradient(90deg,transparent,rgba(255,255,255,.07),transparent); margin: 0 0 16px; }

/* Feature list */
.pc2-features { list-style:none; padding:0; margin:0 0 20px; flex:1; }
.pc2-features li {
    font-size: .78rem; color: rgba(255,255,255,.6);
    padding: 6px 0 6px 22px; position: relative;
    border-bottom: 1px solid rgba(255,255,255,.03);
    line-height: 1.45;
}
.pc2-features li:last-child { border-bottom:none; }
.pc2-features li::before { content:'✓'; position:absolute; left:0; font-weight:800; font-size:.8rem; }
.pc2.rookie  .pc2-features li::before { color:#A0AABE; }
.pc2.sharp   .pc2-features li::before { color:#F9C62B; }
.pc2.smart   .pc2-features li::before { color:#00D559; }
.pc2.insider .pc2-features li::before { color:#c084fc; }
.pc2-features li.note { color:rgba(255,255,255,.28); font-style:italic; padding-left:0; font-size:.7rem; }
.pc2-features li.note::before { content:''; }

/* CTA area */
.pc2-cta { padding: 0 24px 24px; margin-top: auto; }
.pc2-security { text-align:center; font-size:.62rem; color:rgba(255,255,255,.22); margin-top:8px; }
</style>

<div class="section-header" style="margin-top:24px;">
  <p class="section-title" style="font-size:2.2rem;letter-spacing:-.5px;">Choose Your Edge</p>
  <p class="section-subtitle">
    Start free. Scale up when you're ready. Every paid plan is backed by our
    no-questions-asked cancellation guarantee.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Billing toggle (monthly vs annual) ───────────────────────
_billing_col1, _billing_col2, _billing_col3 = st.columns([2, 1, 2])
with _billing_col2:
    _annual = st.toggle("Annual billing (save 10%)", key="_annual_billing", value=False)

# ── Build pricing data for selected billing cycle ────────────
if _annual:
    _sharp_price   = "8.99"
    _sharp_period  = "per month, billed $107.89/yr"
    _sharp_savings = "💰 SAVE $11.99/yr"
    _sharp_lookup  = "sharp_iq_annual"
    _smart_price   = "22.49"
    _smart_period  = "per month, billed $269.89/yr"
    _smart_savings = "💰 SAVE $29.99/yr"
    _smart_lookup  = "smart_money_annual"
else:
    _sharp_price   = "9.99"
    _sharp_period  = "per month"
    _sharp_savings = "💰 $107.89/yr if billed annually"
    _sharp_lookup  = "sharp_iq"
    _smart_price   = "24.99"
    _smart_period  = "per month"
    _smart_savings = "💰 $269.89/yr if billed annually"
    _smart_lookup  = "smart_money"

_sharp_dollars, _sharp_cents = _sharp_price.split(".")
_smart_dollars, _smart_cents = _smart_price.split(".")

st.markdown(f"""
<div class="pricing-grid-v2">

  <!-- ── Smart Rookie ── -->
  <div class="pc2 rookie">
    <div class="pc2-top-bar"></div>
    <div class="pc2-body">
      <span class="pc2-icon">⭐</span>
      <p class="pc2-tier">Smart Rookie</p>
      <p class="pc2-tagline">"Welcome to the smart side."</p>
      <div class="pc2-price-row">
        <span class="pc2-curr">$</span>
        <span class="pc2-amt">0</span>
      </div>
      <p class="pc2-period">free forever</p>
      <div style="height:30px;"></div>
      <div class="pc2-divider"></div>
      <ul class="pc2-features">
        <li>12 QAM Props per session</li>
        <li>💦 Live Sweat — real-time</li>
        <li>📡 Live Games feed</li>
        <li>📡 Smart NBA Data</li>
        <li>⚙️ Settings & preferences</li>
        <li>🔬 Prop Scanner — 5 manual props</li>
      </ul>
    </div>
    <div class="pc2-cta">
      <p class="pc2-security">🔓 No credit card required</p>
    </div>
  </div>

  <!-- ── Sharp IQ ── -->
  <div class="pc2 sharp">
    <div class="pc2-top-bar"></div>
    <div class="pc2-body">
      <span class="pc2-icon">🔥</span>
      <p class="pc2-tier">Sharp IQ</p>
      <p class="pc2-tagline">"Your IQ just passed the books."</p>
      <div class="pc2-price-row">
        <span class="pc2-curr">$</span>
        <span class="pc2-amt">{_sharp_dollars}</span>
        <span class="pc2-cents">.{_sharp_cents}</span>
      </div>
      <p class="pc2-period">{_sharp_period}</p>
      <span class="pc2-savings">{_sharp_savings}</span>
      <div class="pc2-divider"></div>
      <ul class="pc2-features">
        <li>35 QAM Props per session</li>
        <li>🔬 Unlimited Prop Scanner</li>
        <li>📄 CSV Upload & Live Retrieval</li>
        <li>🧬 Entry Builder</li>
        <li>🛡️ Risk Shield</li>
        <li>📋 Game Report</li>
        <li>🔮 Player Simulator</li>
        <li>📈 Bet Tracker</li>
      </ul>
    </div>
    <div class="pc2-cta" id="cta-sharp"></div>
    <p class="pc2-security" style="padding:0 24px 20px;text-align:center;font-size:.62rem;color:rgba(255,255,255,.22);">🔒 Stripe · Cancel anytime</p>
  </div>

  <!-- ── Smart Money ── -->
  <div class="pc2 smart">
    <div class="pc2-top-bar"></div>
    <span class="pc2-badge">MOST POPULAR</span>
    <div class="pc2-body">
      <span class="pc2-icon">💎</span>
      <p class="pc2-tier">Smart Money</p>
      <p class="pc2-tagline">"You are the smart money."</p>
      <div class="pc2-price-row">
        <span class="pc2-curr">$</span>
        <span class="pc2-amt">{_smart_dollars}</span>
        <span class="pc2-cents">.{_smart_cents}</span>
      </div>
      <p class="pc2-period">{_smart_period}</p>
      <span class="pc2-savings">{_smart_savings}</span>
      <div class="pc2-divider"></div>
      <ul class="pc2-features">
        <li class="note">Everything in Sharp IQ, plus:</li>
        <li>All 300+ QAM Props — unlimited</li>
        <li>💰 Smart Money Bets</li>
        <li>🗺️ Correlation Matrix</li>
        <li>📊 Proving Grounds</li>
        <li>🎙️ The Studio</li>
        <li>Priority analysis queue</li>
      </ul>
    </div>
    <div class="pc2-cta" id="cta-smart"></div>
    <p class="pc2-security" style="padding:0 24px 20px;text-align:center;font-size:.62rem;color:rgba(255,255,255,.22);">🔒 Stripe · Cancel anytime</p>
  </div>

  <!-- ── Insider Circle ── -->
  <div class="pc2 insider">
    <div class="pc2-top-bar"></div>
    <span class="pc2-badge">75 SEATS</span>
    <div class="pc2-body">
      <span class="pc2-icon">👑</span>
      <p class="pc2-tier">Insider Circle</p>
      <p class="pc2-tagline">"You knew before everyone."</p>
      <div class="pc2-price-row">
        <span class="pc2-curr">$</span>
        <span class="pc2-amt">499</span>
        <span class="pc2-cents">.99</span>
      </div>
      <p class="pc2-period">one-time · lifetime access</p>
      <span class="pc2-savings">🔥 Limited to 75 founding members</span>
      <div class="pc2-divider"></div>
      <ul class="pc2-features">
        <li class="note">Everything in Smart Money, plus:</li>
        <li>👑 Insider Circle exclusive features</li>
        <li>All 300+ QAM Props + 👑 badge</li>
        <li>Lifetime access — pay once, forever</li>
        <li>Early access to every new tool</li>
        <li>Founding member status</li>
      </ul>
    </div>
    <div class="pc2-cta" id="cta-insider"></div>
    <p class="pc2-security" style="padding:0 24px 20px;text-align:center;font-size:.62rem;color:rgba(255,255,255,.22);">🔒 One-time payment · Lifetime access</p>
  </div>

</div>
""", unsafe_allow_html=True)

# ── SUBSCRIBE BUTTONS (below the visual cards) ───────────────
st.markdown("""
<style>
.sub-btn-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
    margin: 0 0 12px;
}
@media (max-width: 1100px) { .sub-btn-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px)  { .sub-btn-grid { grid-template-columns: 1fr; } }
</style>
<div class="sub-btn-grid">
""", unsafe_allow_html=True)

_btn_cols = st.columns(4)

with _btn_cols[0]:
    st.success("✅ You're on Free — no upgrade needed to start")

with _btn_cols[1]:
    if is_stripe_configured():
        with st.form("checkout_sharp_v2"):
            _email_s = st.text_input("Email", placeholder="you@example.com", key="_email_sharp2", label_visibility="collapsed")
            _lbl_s = f"🔥 Get Sharp IQ — ${_sharp_price}/mo" if not _annual else f"🔥 Get Sharp IQ Annual — ${_sharp_price}/mo"
            if st.form_submit_button(_lbl_s, type="primary", use_container_width=True):
                with st.spinner("Creating secure checkout…"):
                    result = create_checkout_session(customer_email=_email_s.strip() if _email_s else "", price_lookup=_sharp_lookup)
                if result["success"]:
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={result["url"]}">', unsafe_allow_html=True)
                    st.info(f"Redirecting… [Click here]({result['url']})")
                else:
                    st.error(f"Checkout error: {result['error']}")
    else:
        st.info("Stripe not configured — coming soon!")

with _btn_cols[2]:
    if is_stripe_configured():
        with st.form("checkout_smart_v2"):
            _email_m = st.text_input("Email", placeholder="you@example.com", key="_email_smart2", label_visibility="collapsed")
            _lbl_m = f"💎 Get Smart Money — ${_smart_price}/mo" if not _annual else f"💎 Get Smart Money Annual — ${_smart_price}/mo"
            if st.form_submit_button(_lbl_m, type="primary", use_container_width=True):
                with st.spinner("Creating secure checkout…"):
                    result = create_checkout_session(customer_email=_email_m.strip() if _email_m else "", price_lookup=_smart_lookup)
                if result["success"]:
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={result["url"]}">', unsafe_allow_html=True)
                    st.info(f"Redirecting… [Click here]({result['url']})")
                else:
                    st.error(f"Checkout error: {result['error']}")
    else:
        st.info("Stripe not configured — coming soon!")

with _btn_cols[3]:
    if is_stripe_configured():
        with st.form("checkout_insider_v2"):
            _email_i = st.text_input("Email", placeholder="you@example.com", key="_email_insider2", label_visibility="collapsed")
            if st.form_submit_button("👑 Get Lifetime Access — $499.99", type="primary", use_container_width=True):
                with st.spinner("Creating secure checkout…"):
                    result = create_checkout_session(customer_email=_email_i.strip() if _email_i else "", price_lookup="insider_circle")
                if result["success"]:
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={result["url"]}">', unsafe_allow_html=True)
                    st.info(f"Redirecting… [Click here]({result['url']})")
                else:
                    st.error(f"Checkout error: {result['error']}")
    else:
        st.info("Stripe not configured — coming soon!")

st.markdown("</div>", unsafe_allow_html=True)

# ── MONEY-BACK GUARANTEE ─────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;justify-content:center;gap:14px;
  background:linear-gradient(135deg,rgba(0,213,89,.04),rgba(45,158,255,.04));
  border:1px solid rgba(0,213,89,.15);border-radius:16px;
  padding:20px 32px;margin:16px auto 40px;max-width:640px;text-align:center;">
  <span style="font-size:2.2rem;">🛡️</span>
  <div>
    <p style="margin:0 0 4px;font-family:'Inter',sans-serif;font-weight:800;color:#fff;font-size:.9rem;">
      Risk-Free Guarantee
    </p>
    <p style="margin:0;color:rgba(255,255,255,.45);font-size:.78rem;line-height:1.6;">
      Cancel any monthly or annual subscription anytime — no questions asked.
      Insider Circle is a one-time lifetime payment.
      All payments processed securely through <strong style="color:rgba(255,255,255,.7);">Stripe</strong>.
    </p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── FULL FEATURE COMPARISON TABLE ─────────────────────────────
st.markdown("""
<div class="section-header">
  <p class="section-title">📊 Full Feature Comparison</p>
  <p class="section-subtitle">
    See exactly what's included in every tier. No hidden features, no surprises.
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="feat-table-wrap">
<table class="feat-table">
  <thead>
    <tr>
      <th style="width:30%;">Feature</th>
      <th class="th-rookie">⭐ Rookie</th>
      <th class="th-sharp">🔥 Sharp IQ</th>
      <th class="th-smart">💎 Smart Money</th>
      <th class="th-insider">👑 Insider</th>
    </tr>
  </thead>
  <tbody>
    <!-- Core Analytics -->
    <tr class="feat-category"><td colspan="5">📡 Core Analytics</td></tr>
    <tr>
      <td>💦 Live Sweat — Real-Time Tracking</td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>📡 Live Games Feed</td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>📡 Smart NBA Data</td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>⚙️ Settings & Preferences</td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>

    <!-- Prop Analysis -->
    <tr class="feat-category"><td colspan="5">🔬 Prop Analysis Engine</td></tr>
    <tr>
      <td>⚡ Quantum Analysis Matrix (QAM)</td>
      <td><span class="feat-limit">10 props</span></td>
      <td><span class="feat-limit">25 props</span></td>
      <td><span class="feat-yes">All 300+</span></td>
      <td><span class="feat-yes">All 300+ 👑</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — Manual Entry</td>
      <td><span class="feat-limit">5 props</span></td>
      <td><span class="feat-yes">Unlimited</span></td>
      <td><span class="feat-yes">Unlimited</span></td>
      <td><span class="feat-yes">Unlimited</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — CSV Upload</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — Live Platform Retrieval</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>

    <!-- Premium Tools -->
    <tr class="feat-category"><td colspan="5">🧬 Premium Tools</td></tr>
    <tr>
      <td>🧬 Entry Builder</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>🛡️ Risk Shield</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>📋 Game Report</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔮 Player Simulator</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>📈 Bet Tracker</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>

    <!-- Elite Tools -->
    <tr class="feat-category"><td colspan="5">💰 Elite Tools</td></tr>
    <tr>
      <td>💰 Smart Money Bets</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>🗺️ Correlation Matrix</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>📊 Proving Grounds</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>🎙️ The Studio</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>

    <!-- Insider Exclusive -->
    <tr class="feat-category"><td colspan="5">👑 Insider Exclusive</td></tr>
    <tr>
      <td>👑 Insider Circle Access</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>Early Access to New Tools</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>
    <tr>
      <td>Founding Member Status</td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-no">✗</span></td>
      <td><span class="feat-yes">✓</span></td>
    </tr>

    <!-- Payment Row -->
    <tr style="border-top:2px solid rgba(0,213,89,0.12);">
      <td><strong>Payment</strong></td>
      <td style="color:#A0AABE;">Free forever</td>
      <td style="color:#F9C62B;">$9.99/mo · $107.89/yr</td>
      <td style="color:#00D559;">$24.99/mo · $269.89/yr</td>
      <td style="color:#c084fc;">$499.99 one-time</td>
    </tr>
  </tbody>
</table>
</div>
""", unsafe_allow_html=True)

# ── TESTIMONIALS ──────────────────────────────────────────────
st.markdown("""
<div class="section-header">
  <p class="section-title">What Our Members Say</p>
  <p class="section-subtitle">
    Real feedback from Smart Pick Pro subscribers.
  </p>
</div>

<div class="testimonial-grid">
  <div class="testimonial-card">
    <p class="testimonial-text">
      The QAM analysis is incredible. I went from randomly picking props to having a structured,
      data-driven approach. Sharp IQ paid for itself in the first week.
    </p>
    <div class="testimonial-author">
      <div class="testimonial-avatar" style="background:rgba(249,198,43,0.15);color:#F9C62B;">M</div>
      <div class="testimonial-author-info">
        <p class="testimonial-author-name">Marcus R.</p>
        <p class="testimonial-author-plan" style="color:#F9C62B;">🔥 Sharp IQ Member</p>
      </div>
    </div>
  </div>

  <div class="testimonial-card">
    <p class="testimonial-text">
      Smart Money Bets + Correlation Matrix completely changed my game. Being able to see which props
      correlate together and build smarter parlays is a huge advantage.
    </p>
    <div class="testimonial-author">
      <div class="testimonial-avatar" style="background:rgba(0,213,89,0.15);color:#00D559;">T</div>
      <div class="testimonial-author-info">
        <p class="testimonial-author-name">Tyler K.</p>
        <p class="testimonial-author-plan" style="color:#00D559;">💎 Smart Money Member</p>
      </div>
    </div>
  </div>

  <div class="testimonial-card">
    <p class="testimonial-text">
      The Insider Circle lifetime deal was a no-brainer. I get every new feature automatically and the
      exclusive access alone is worth it. Best investment I've made for prop betting.
    </p>
    <div class="testimonial-author">
      <div class="testimonial-avatar" style="background:rgba(192,132,252,0.15);color:#c084fc;">J</div>
      <div class="testimonial-author-info">
        <p class="testimonial-author-name">Jordan W.</p>
        <p class="testimonial-author-plan" style="color:#c084fc;">👑 Insider Circle Member</p>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── TRUST SIGNALS ─────────────────────────────────────────────
st.markdown("""
<div class="trust-row">
  <div class="trust-item">
    <span class="trust-icon">🔒</span>
    <span>256-bit SSL Encryption</span>
  </div>
  <div class="trust-item">
    <span class="trust-icon">💳</span>
    <span>Powered by Stripe</span>
  </div>
  <div class="trust-item">
    <span class="trust-icon">🔄</span>
    <span>Cancel Anytime</span>
  </div>
  <div class="trust-item">
    <span class="trust-icon">📱</span>
    <span>Works on All Devices</span>
  </div>
  <div class="trust-item">
    <span class="trust-icon">⚡</span>
    <span>Instant Access</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── FAQ SECTION ───────────────────────────────────────────────
st.markdown("""
<div class="section-header">
  <p class="section-title">Frequently Asked Questions</p>
  <p class="section-subtitle">
    Everything you need to know before subscribing.
  </p>
</div>

<div class="faq-grid">
  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> How does billing work?</p>
    <p class="faq-a">Monthly and annual plans are billed through Stripe, the same payment processor used by Amazon and Google. You can cancel anytime — no contracts, no hidden fees.</p>
  </div>

  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> Can I upgrade or downgrade my plan?</p>
    <p class="faq-a">Yes! Use the "Manage Subscription" button on this page after subscribing. Stripe handles all plan changes, prorated billing, and refunds automatically.</p>
  </div>

  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> What happens after I subscribe?</p>
    <p class="faq-a">You'll be redirected back to Smart Pick Pro with full access instantly activated. All premium features will be unlocked in the sidebar. Your receipt is emailed automatically.</p>
  </div>

  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> What is the Insider Circle?</p>
    <p class="faq-a">A one-time $499.99 payment for lifetime access to every feature, including exclusive Insider Circle tools. Limited to 75 founding members — once they're gone, they're gone.</p>
  </div>

  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> Is my payment information secure?</p>
    <p class="faq-a">Absolutely. We never see or store your card details. All payments are processed through Stripe with bank-level 256-bit SSL encryption and PCI DSS compliance.</p>
  </div>

  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> How do I restore access on a new device?</p>
    <p class="faq-a">Use the "Restore Access" section below — just enter the email you subscribed with and your premium features will be instantly reactivated.</p>
  </div>

  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> What's included in the free Smart Rookie plan?</p>
    <p class="faq-a">Live Sweat, Live Games, Smart NBA Data, Settings, up to 10 QAM props, and up to 5 manual Prop Scanner entries. No credit card required — free forever.</p>
  </div>

  <div class="faq-item">
    <p class="faq-q"><span class="faq-q-icon">Q</span> Do you offer refunds?</p>
    <p class="faq-a">Monthly and annual plans can be cancelled at any time with no penalty. You'll retain access through the end of your billing period. Insider Circle is a one-time lifetime purchase.</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── RESTORE ACCESS ────────────────────────────────────────────
st.markdown("""
<div class="restore-card">
  <span class="restore-card-icon">🔑</span>
  <p class="restore-card-title">Already a subscriber?</p>
  <p class="restore-card-text">Enter the email you used when subscribing to restore your premium access on this device.</p>
</div>
""", unsafe_allow_html=True)

restore_col1, restore_col2, restore_col3 = st.columns([1, 2, 1])
with restore_col2:
    restore_email = st.text_input(
        "Email address",
        key="_restore_email",
        placeholder="you@example.com",
        label_visibility="collapsed",
    )
    if st.button("🔑 Restore My Access", key="_restore_btn", use_container_width=True, type="primary"):
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

# ── FOOTER ────────────────────────────────────────────────────
st.divider()
st.markdown(get_premium_footer_html(), unsafe_allow_html=True)
