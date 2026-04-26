# ============================================================
# FILE: pages/home.py
# PURPOSE: Marketing landing page — accessible at smartpickpro.ai/home
#          Unauthenticated visitors see the full marketing landing page.
#          Authenticated visitors are immediately forwarded to the app home.
# URL:     smartpickpro.ai/home
# ============================================================

import streamlit as st

st.set_page_config(
    page_title="Smart Pick Pro — AI-Powered Sports Intelligence",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject GA4 analytics ─────────────────────────────────────────────────────
try:
    from utils.analytics import inject_ga4, track_page_view
    inject_ga4()
    track_page_view("Landing Page")
except Exception:
    pass

# ── SEO meta tags ────────────────────────────────────────────────────────────
try:
    from utils.seo import inject_page_seo
    inject_page_seo("Home")
except Exception:
    pass

# ── Auth gate ────────────────────────────────────────────────────────────────
# require_login() shows the full marketing landing page if not authenticated
# and returns False.  If already authenticated it returns True immediately.
from utils.auth_gate import require_login

if require_login():
    # User is already logged in — send them to the app home page.
    st.switch_page("Smart_Picks_Pro_Home.py")
    st.stop()

# require_login() rendered the full marketing landing page and returned False.
st.stop()
