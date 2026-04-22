# ============================================================
# FILE: pages/login.py
# PURPOSE: Login / signup portal - accessible at smartpickpro.ai/login
#          Drops straight into the auth portal (no full landing page).
#          Authenticated visitors are immediately forwarded to the app.
# URL:     smartpickpro.ai/login
# ============================================================

import streamlit as st

st.set_page_config(
    page_title="Smart Pick Pro - Sign In",
    page_icon="basketball",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# -- Inject GA4 analytics --------------------------------------------------
try:
    from utils.analytics import inject_ga4, track_page_view
    inject_ga4()
    track_page_view("Login")
except Exception:
    pass

# -- Auth gate -------------------------------------------------------------
# If already authenticated, go straight to the app home page.
from utils.auth_gate import require_login, is_logged_in

if is_logged_in():
    st.switch_page("Smart_Picks_Pro_Home.py")
    st.stop()

# Force ?auth=login so require_login() renders the focused login portal
# rather than the full marketing landing page.
try:
    if not st.query_params.get("auth"):
        st.query_params["auth"] = "login"
except Exception:
    pass

# require_login() renders the auth portal and returns False when not logged in.
# It returns True if the user just authenticated successfully.
if require_login():
    st.switch_page("Smart_Picks_Pro_Home.py")
    st.stop()

st.stop()
