# ============================================================
# FILE: pages/13_⚙️_Settings.py
# PURPOSE: Configure the SmartBetPro NBA engine settings:
#          simulation depth, edge thresholds, platform selection,
#          and entry fee defaults. Settings persist in session state
#          AND are saved to the database so they survive browser
#          reloads.
# CONNECTS TO: All engine pages use settings from session state
# CONCEPTS COVERED: Session state, configuration, settings UI
# ============================================================

import streamlit as st  # Main UI framework
from tracking.database import save_user_settings

# ============================================================
# SECTION: Page Setup
# ============================================================

st.set_page_config(
    page_title="Settings — SmartBetPro NBA",
    page_icon="⚙️",
    layout="wide",
)

# ── Login Gate ─────────────────────────────────────────────────
from utils.auth_gate import require_login as _require_login
if not _require_login():
    st.stop()

# ── Analytics ─────────────────────────────────────────────────
from utils.analytics import inject_ga4, track_page_view
inject_ga4()
track_page_view("Settings")
from utils.seo import inject_page_seo
inject_page_seo("Settings")

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ────────────────────────────
from utils.components import inject_joseph_floating, render_sidebar_auth
st.session_state["joseph_page_context"] = "page_settings"
inject_joseph_floating()
with st.sidebar:
    render_sidebar_auth()

st.title("⚙️ Settings")
st.markdown("Configure the SmartBetPro NBA prediction engine.")

with st.expander("📖 How to Use This Page", expanded=False):
    st.markdown("""
    ### Settings — Tune Your Prediction Engine
    
    Configure the SmartBetPro prediction engine to match your betting style and risk tolerance.
    
    **Quick Start — Preset Profiles**
    - **🛡️ Conservative**: Fewer picks, higher confidence. Best for beginners.
    - **⚖️ Balanced**: Middle ground — good mix of volume and quality.
    - **🔥 Aggressive**: More picks, lower thresholds. For experienced bettors.
    
    **Key Settings Explained**
    - **Simulation Depth**: How many Quantum Matrix simulations to run (higher = more accurate, slower)
    - **Minimum Edge Threshold**: Only show props where the model finds at least this much edge
    - **Sensitivity Sliders**: Fine-tune how much weight the model gives to pace, fatigue, blowout risk, etc.
    
    💡 **Pro Tips:**
    - Start with the Conservative preset and adjust from there
    - Higher simulation depth (3000+) gives more precise results but takes longer
    - Minimum edge threshold of 5-8% works well for most bettors
    """)

st.divider()

# ============================================================
# SECTION: Preset Profiles
# ============================================================

st.subheader("⚡ Quick Start — Preset Profiles")
st.markdown(
    "Apply a pre-configured profile to instantly tune all settings for your strategy."
)

_PRIMARY_PLATFORMS = [
    "PrizePicks", "Underdog Fantasy", "DraftKings Pick6",
]

_ALL_PLATFORMS = list(_PRIMARY_PLATFORMS)

_PROFILES = {
    "🛡️ Conservative": {
        "description": "Fewer, higher-confidence picks. Lower risk, steadier returns.",
        "simulation_depth": 2000,
        "minimum_edge_threshold": 8.0,
        "entry_fee": 10.0,
        "selected_platforms": list(_PRIMARY_PLATFORMS),
        "home_court_boost": 0.02,
        "blowout_sensitivity": 1.5,
        "fatigue_sensitivity": 1.5,
        "pace_sensitivity": 1.0,
    },
    "⚖️ Balanced": {
        "description": "Recommended defaults. Good mix of volume and confidence.",
        "simulation_depth": 2000,
        "minimum_edge_threshold": 5.0,
        "entry_fee": 10.0,
        "selected_platforms": list(_PRIMARY_PLATFORMS),
        "home_court_boost": 0.025,
        "blowout_sensitivity": 1.0,
        "fatigue_sensitivity": 1.0,
        "pace_sensitivity": 1.0,
    },
    "🚀 Aggressive": {
        "description": "More picks, lower edge threshold. High volume, higher variance.",
        "simulation_depth": 500,
        "minimum_edge_threshold": 2.0,
        "entry_fee": 25.0,
        "selected_platforms": list(_ALL_PLATFORMS),
        "home_court_boost": 0.03,
        "blowout_sensitivity": 0.5,
        "fatigue_sensitivity": 0.5,
        "pace_sensitivity": 1.5,
    },
}

_prof_cols = st.columns(3)
for _ci, (_pname, _pdata) in enumerate(_PROFILES.items()):
    with _prof_cols[_ci]:
        st.markdown(
            f'<div style="background:#14192b;border-radius:8px;padding:14px 16px;'
            f'border:1px solid rgba(0,213,89,0.15);margin-bottom:8px;">'
            f'<div style="font-size:1rem;font-weight:700;color:#F9C62B;">{_pname}</div>'
            f'<div style="color:#A0AABE;font-size:0.82rem;margin-top:4px;">{_pdata["description"]}</div>'
            f'<div style="color:#8b949e;font-size:0.75rem;margin-top:6px;">'
            f'Edge ≥ {_pdata["minimum_edge_threshold"]}% · '
            f'{_pdata["simulation_depth"]:,} sims · '
            f'{len(_pdata["selected_platforms"])} platform(s)</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button(f"Apply {_pname}", key=f"profile_{_ci}", width="stretch"):
            for _k, _v in _pdata.items():
                if _k != "description":
                    st.session_state[_k] = _v
            save_user_settings(st.session_state)
            st.success(f"✅ {_pname} profile applied!")
            st.rerun()

st.divider()

# ============================================================
# END SECTION: Preset Profiles
# ============================================================

st.markdown(get_education_box_html(
    "📖 What Do These Settings Do?",
    """
    <strong>Simulation Depth</strong>: How many game simulations to run per prop. 
    More = more accurate but slower. 2,000 is the recommended balance.<br><br>
    <strong>Minimum Edge Threshold</strong>: Only show picks with at least this much edge. 
    5% = only show picks where we have at least a 5% probability advantage over the line.<br><br>
    <strong>Entry Fee</strong>: Default dollar amount for EV calculations in Entry Builder.<br><br>
    <strong>Platforms</strong>: Which betting platforms to analyze for. 
    Different platforms have different payout structures.
    """
), unsafe_allow_html=True)

# ============================================================
# END SECTION: Page Setup
# ============================================================

st.divider()

# ============================================================
# SECTION: Simulation Settings
# ============================================================

st.subheader("🎲 Simulation Settings")

col1, col2 = st.columns(2)

with col1:
    # Simulation depth: how many games to simulate per player
    # More simulations = more accurate probability, but slower
    simulation_depth_options = {
        "Fast (500 sims)": 500,
        "Standard (1,000 sims)": 1000,
        "Recommended (2,000 sims)": 2000,
        "High Accuracy (5,000 sims)": 5000,
    }

    current_depth = st.session_state.get("simulation_depth", 2000)
    # Find the current label for the default
    current_label = "Recommended (2,000 sims)"
    for label, value in simulation_depth_options.items():
        if value == current_depth:
            current_label = label
            break

    selected_depth_label = st.selectbox(
        "Simulation Depth",
        options=list(simulation_depth_options.keys()),
        index=list(simulation_depth_options.keys()).index(current_label),
        help=(
            "How many games to simulate per player.\n"
            "More = more accurate, but takes longer.\n"
            "500 is fine for quick checks; 5000 for precision."
        ),
    )
    # Store the numeric value in session state
    st.session_state["simulation_depth"] = simulation_depth_options[selected_depth_label]
    st.caption(f"Current: **{st.session_state['simulation_depth']:,} simulations** per prop")

with col2:
    # Random seed for reproducibility (optional)
    st.info(
        "💡 **About Simulation Depth:**\n\n"
        "Quantum Matrix Engine 5.6 simulation runs thousands of random game scenarios. "
        "More simulations = the probability estimate converges to the true value.\n\n"
        "With 500 sims: ±3-4% accuracy\n"
        "With 1,000 sims: ±2-3% accuracy\n"
        "With 5,000 sims: ±1% accuracy"
    )

# ============================================================
# END SECTION: Simulation Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Edge and Filter Settings
# ============================================================

st.subheader("📐 Edge & Filter Settings")

edge_col1, edge_col2 = st.columns(2)

with edge_col1:
    # Minimum edge threshold: how much edge needed to show/recommend a pick
    current_edge_threshold = st.session_state.get("minimum_edge_threshold", 5.0)

    new_edge_threshold = st.slider(
        "Minimum Edge Threshold (%)",
        min_value=0.0,
        max_value=20.0,
        value=float(current_edge_threshold),
        step=0.5,
        help=(
            "Minimum edge (distance from the -110 breakeven of 52.38%) required "
            "to display a pick in 'Top Picks' view.\n"
            "5% = need at least 57.4% probability (52.38% + 5%).\n"
            "Higher = fewer but stronger picks."
        ),
    )
    st.session_state["minimum_edge_threshold"] = new_edge_threshold
    st.caption(
        f"Picks need at least **{new_edge_threshold}% edge** "
        f"(≥{52.38 + new_edge_threshold:.1f}% probability at -110 odds)"
    )

with edge_col2:
    st.info(
        "💡 **What is Edge?**\n\n"
        "Edge = how far your probability is from the **-110 breakeven** (52.38%).\n\n"
        "At standard -110 odds you need to win 52.38% of the time just to break even, "
        "so the true edge is your model probability **minus 52.38%**, not minus 50%.\n\n"
        "- 63% probability = +10.6% edge (63% − 52.38%)\n"
        "- 55% probability = +2.6% edge (55% − 52.38%)\n"
        "- 52% probability = −0.4% edge (no value at -110)\n\n"
        "For sportsbooks with different juice (e.g. -130), the breakeven is higher (~56.5%), "
        "so the displayed edge automatically adjusts to the actual odds.\n\n"
        "We recommend at least **5% edge** to justify a bet."
    )

# ============================================================
# END SECTION: Edge and Filter Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Entry Fee
# ============================================================

st.subheader("💰 Entry Fee")

current_entry_fee = st.session_state.get("entry_fee", 10.0)

new_entry_fee = st.number_input(
    "Default Entry Fee ($)",
    min_value=1.0,
    max_value=500.0,
    value=float(current_entry_fee),
    step=5.0,
    help="Default entry fee used for EV calculations in Entry Builder",
)
st.session_state["entry_fee"] = new_entry_fee
st.caption(f"Default entry fee: **${new_entry_fee:.2f}**")

# ============================================================
# END SECTION: Entry Fee
# ============================================================

st.divider()

# ============================================================
# SECTION: Sportsbook Platform Settings
# ============================================================

st.subheader("🎰 Sportsbook Platforms")

st.markdown(
    "Select which sportsbooks to include in analysis. "
    "Props are fetched from PrizePicks, Underdog Fantasy, and DraftKings Pick6."
)

current_platforms = st.session_state.get("selected_platforms", list(_PRIMARY_PLATFORMS))

new_platforms = st.multiselect(
    "Sportsbook Platforms",
    options=_PRIMARY_PLATFORMS,
    default=[p for p in current_platforms if p in _PRIMARY_PLATFORMS],
    help="Supported platforms — PrizePicks, Underdog Fantasy, DraftKings Pick6",
    label_visibility="collapsed",
)

if new_platforms:
    st.session_state["selected_platforms"] = new_platforms
st.caption(f"Active: **{', '.join(st.session_state.get('selected_platforms', []))}**")

# ============================================================
# END SECTION: Sportsbook Platform Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Model Tuning Settings
# ============================================================

st.subheader("🔬 Model Tuning (Advanced)")

with st.expander("Advanced Adjustment Factors"):
    st.markdown(
        "These multipliers adjust how much weight the model gives to each factor. "
        "The default values work well for most users."
    )

    tune_col1, tune_col2 = st.columns(2)

    with tune_col1:
        # Home court advantage boost
        home_court_boost = st.slider(
            "Home Court Advantage Boost",
            min_value=0.0,
            max_value=0.10,
            value=st.session_state.get("home_court_boost", 0.025),
            step=0.005,
            format="%.3f",
            help="Extra multiplier for home games (default: 0.025 = +2.5%)",
        )
        st.session_state["home_court_boost"] = home_court_boost

        # Blowout risk adjustment
        blowout_sensitivity = st.slider(
            "Blowout Risk Sensitivity",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.get("blowout_sensitivity", 1.0),
            step=0.1,
            help="Multiplier on blowout risk (1.0 = default, 2.0 = double sensitivity)",
        )
        st.session_state["blowout_sensitivity"] = blowout_sensitivity

    with tune_col2:
        # Back-to-back fatigue multiplier
        fatigue_sensitivity = st.slider(
            "Back-to-Back Fatigue Sensitivity",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.get("fatigue_sensitivity", 1.0),
            step=0.1,
            help="Multiplier on fatigue penalty (1.0 = default)",
        )
        st.session_state["fatigue_sensitivity"] = fatigue_sensitivity

        # Pace impact sensitivity
        pace_sensitivity = st.slider(
            "Pace Impact Sensitivity",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.get("pace_sensitivity", 1.0),
            step=0.1,
            help="How much game pace affects stat projections",
        )
        st.session_state["pace_sensitivity"] = pace_sensitivity

    # Reset to defaults button
    if st.button("🔄 Reset Advanced Settings to Defaults"):
        st.session_state["home_court_boost"] = 0.025
        st.session_state["blowout_sensitivity"] = 1.0
        st.session_state["fatigue_sensitivity"] = 1.0
        st.session_state["pace_sensitivity"] = 1.0
        save_user_settings(st.session_state)
        st.success("Advanced settings reset to defaults!")
        st.rerun()

# ============================================================
# END SECTION: Model Tuning Settings
# ============================================================

st.divider()

# ============================================================
# SECTION: Display Current Settings Summary
# ============================================================

st.subheader("📋 Current Settings Summary")

settings_summary = {
    "Simulation Depth": f"{st.session_state.get('simulation_depth', 1000):,} simulations",
    "Minimum Edge": f"{st.session_state.get('minimum_edge_threshold', 5.0)}%",
    "Entry Fee": f"${st.session_state.get('entry_fee', 10.0):.2f}",
    "Active Sportsbooks": ", ".join(st.session_state.get("selected_platforms", [])),
    "Home Court Boost": f"{st.session_state.get('home_court_boost', 0.025)*100:.1f}%",
    "Blowout Sensitivity": f"{st.session_state.get('blowout_sensitivity', 1.0):.1f}x",
    "Fatigue Sensitivity": f"{st.session_state.get('fatigue_sensitivity', 1.0):.1f}x",
    "Pace Sensitivity": f"{st.session_state.get('pace_sensitivity', 1.0):.1f}x",
}

summary_rows = [{"Setting": k, "Value": v} for k, v in settings_summary.items()]
st.dataframe(summary_rows, width="stretch", hide_index=True)

# Reset ALL settings button
st.divider()
if st.button("🔄 Reset ALL Settings to Defaults", type="secondary"):
    # Clear all settings from session state
    settings_keys_to_clear = [
        "simulation_depth", "minimum_edge_threshold", "entry_fee",
        "selected_platforms", "home_court_boost", "blowout_sensitivity",
        "fatigue_sensitivity", "pace_sensitivity",
    ]
    for key in settings_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    # Persist the cleared (default) state to DB
    save_user_settings(st.session_state)
    st.success("All settings reset to defaults! Refresh the page to see changes.")
    st.rerun()

# ── Auto-save settings to database on every render ────────────────
# Streamlit re-runs the page script on every widget interaction.
# By saving at the bottom we capture whatever the user just changed.
save_user_settings(st.session_state)

# ============================================================
# END SECTION: Display Current Settings Summary
# ============================================================

st.divider()

# ============================================================
# SECTION: Account Management — Change Password + Edit Profile
# ============================================================

st.subheader("👤 Account Management")

from utils.auth_gate import get_logged_in_email, change_user_password
from tracking.database import load_user_profile, save_user_profile

_acct_email = get_logged_in_email()

_acct_tab_pw, _acct_tab_profile = st.tabs(["🔒 Change Password", "✏️ Edit Profile"])

# ── Change Password ───────────────────────────────────────────
with _acct_tab_pw:
    st.markdown("Update your account password. You'll need to enter your current password first.")
    with st.form("change_password_form", clear_on_submit=True):
        _cp_current = st.text_input("Current Password", type="password", key="_cp_current")
        _cp_new = st.text_input("New Password", type="password", key="_cp_new",
                                help="At least 8 characters, must include a letter and a number.")
        _cp_confirm = st.text_input("Confirm New Password", type="password", key="_cp_confirm")
        _cp_submit = st.form_submit_button("🔒 Change Password", type="primary", use_container_width=True)

    if _cp_submit:
        if not _cp_current or not _cp_new or not _cp_confirm:
            st.error("Please fill in all fields.")
        elif _cp_new != _cp_confirm:
            st.error("New passwords do not match.")
        elif _acct_email:
            _ok, _msg = change_user_password(_acct_email, _cp_current, _cp_new)
            if _ok:
                st.success(f"✅ {_msg}")
            else:
                st.error(_msg)
        else:
            st.error("You must be logged in to change your password.")

# ── Edit Profile ──────────────────────────────────────────────
with _acct_tab_profile:
    _existing_profile = load_user_profile(_acct_email) if _acct_email else None
    if not _existing_profile:
        st.info("No profile found yet. Complete the fields below to create one.")
        _existing_profile = {}

    _nba_teams = [
        "", "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
        "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
        "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers",
        "LA Clippers", "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
        "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans",
        "New York Knicks", "Oklahoma City Thunder", "Orlando Magic", "Philadelphia 76ers",
        "Phoenix Suns", "Portland Trail Blazers", "Sacramento Kings", "San Antonio Spurs",
        "Toronto Raptors", "Utah Jazz", "Washington Wizards",
    ]
    _exp_levels = ["Beginner", "Intermediate", "Advanced", "Professional"]
    _bet_styles = ["Conservative", "Balanced", "Aggressive"]
    _budget_opts = ["$0-$25", "$25-$50", "$50-$100", "$100-$250", "$250+"]
    _platform_opts = ["PrizePicks", "Underdog Fantasy", "DraftKings Pick6"]

    with st.form("edit_profile_form"):
        _ep_name = st.text_input(
            "Display Name",
            value=_existing_profile.get("display_name", ""),
            max_chars=50,
        )
        _ep_team_idx = 0
        _existing_team = _existing_profile.get("favorite_team", "")
        if _existing_team in _nba_teams:
            _ep_team_idx = _nba_teams.index(_existing_team)
        _ep_team = st.selectbox("Favorite Team", _nba_teams, index=_ep_team_idx)

        _existing_platforms = _existing_profile.get("preferred_platforms", "")
        _default_platforms = [p.strip() for p in _existing_platforms.split(",") if p.strip()] if _existing_platforms else []
        _ep_platforms = st.multiselect("Preferred Platforms", _platform_opts, default=_default_platforms)

        _ep_exp_idx = 0
        _existing_exp = _existing_profile.get("experience_level", "")
        if _existing_exp in _exp_levels:
            _ep_exp_idx = _exp_levels.index(_existing_exp)
        _ep_exp = st.selectbox("Experience Level", _exp_levels, index=_ep_exp_idx)

        _ep_style_idx = 0
        _existing_style = _existing_profile.get("betting_style", "")
        if _existing_style in _bet_styles:
            _ep_style_idx = _bet_styles.index(_existing_style)
        _ep_style = st.selectbox("Betting Style", _bet_styles, index=_ep_style_idx)

        _ep_budget_idx = 0
        _existing_budget = _existing_profile.get("daily_budget", "")
        if _existing_budget in _budget_opts:
            _ep_budget_idx = _budget_opts.index(_existing_budget)
        _ep_budget = st.selectbox("Daily Budget", _budget_opts, index=_ep_budget_idx)

        _ep_submit = st.form_submit_button("💾 Save Profile", type="primary", use_container_width=True)

    if _ep_submit and _acct_email:
        _profile_data = {
            "display_name": _ep_name.strip(),
            "favorite_team": _ep_team,
            "preferred_platforms": ", ".join(_ep_platforms),
            "experience_level": _ep_exp,
            "betting_style": _ep_style,
            "daily_budget": _ep_budget,
        }
        if save_user_profile(_acct_email, _profile_data):
            st.success("✅ Profile updated successfully!")
            st.rerun()
        else:
            st.error("Failed to save profile. Please try again.")
    elif _ep_submit and not _acct_email:
        st.error("You must be logged in to edit your profile.")

# ============================================================
# END SECTION: Account Management
# ============================================================
