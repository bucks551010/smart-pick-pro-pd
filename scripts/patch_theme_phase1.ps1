
# patch_theme_phase1.ps1  — replaces the get_global_css() CSS block with the
# PrizePicks + DraftKings Pick 6 AI theme (Phase 1: core foundation).

$file = "c:\Users\Josep\Documents\SmartAI-NBA-main\SmartAI-NBA-main\styles\theme.py"
$raw  = [System.IO.File]::ReadAllText($file, [System.Text.Encoding]::UTF8)

# Locate the SECOND <style> tag (the one inside the return """""" of get_global_css)
$firstIdx  = $raw.IndexOf('<style>')
$cssStart  = $raw.IndexOf('<style>', $firstIdx + 1)   # second occurrence

# The matching </style> — find the first one AFTER cssStart
$cssEnd = $raw.IndexOf('</style>', $cssStart) + '</style>'.Length

Write-Host "Replacing CSS block: $cssStart -> $cssEnd (length $($cssEnd - $cssStart))"

$newCss = @'
<style>
/* ===========================================================
   SMART PICK PRO — AI Theme  (Phase 1: Core Foundation)
   Inspired by PrizePicks + DraftKings Pick 6
   ===========================================================

   Design tokens:
     --pp-green   #00D559   PrizePicks primary green
     --dk-gold    #F9C62B   DraftKings gold
     --ai-blue    #2D9EFF   AI electric blue
     --danger     #F24336   Under / Less red
     --bg-base    #0D0F14   Main background
     --bg-card    #161B27   Card background
     --bg-card-2  #1C2232   Elevated card
     --text       #FFFFFF / #A0AABE / #6B7A9A
   =========================================================== */

/* ── Google Fonts ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Bebas+Neue&family=Oswald:wght@400;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* ── CSS Custom Properties ────────────────────────────────── */
:root {
  --pp-green:      #00D559;
  --pp-green-dim:  rgba(0,213,89,0.12);
  --dk-gold:       #F9C62B;
  --dk-gold-dim:   rgba(249,198,43,0.12);
  --ai-blue:       #2D9EFF;
  --ai-blue-dim:   rgba(45,158,255,0.12);
  --danger:        #F24336;
  --danger-dim:    rgba(242,67,54,0.12);
  --bg-base:       #0D0F14;
  --bg-card:       #161B27;
  --bg-card-2:     #1C2232;
  --bg-sidebar:    #0A0D14;
  --border:        rgba(255,255,255,0.07);
  --border-light:  rgba(255,255,255,0.12);
  --text-1:        #FFFFFF;
  --text-2:        #A0AABE;
  --text-3:        #6B7A9A;
  --radius-sm:     8px;
  --radius-md:     12px;
  --radius-lg:     16px;
  --radius-xl:     20px;
  --radius-pill:   100px;
}

/* ── Keyframes ────────────────────────────────────────────── */
@keyframes ppPulseGreen {
  0%,100%{ box-shadow: 0 0 0 0 rgba(0,213,89,0.50); }
  50%    { box-shadow: 0 0 0 6px rgba(0,213,89,0); }
}
@keyframes ppPulseGold {
  0%,100%{ box-shadow: 0 0 0 0 rgba(249,198,43,0.50); }
  50%    { box-shadow: 0 0 0 6px rgba(249,198,43,0); }
}
@keyframes ppLiveDot {
  0%,100%{ opacity:1; transform:scale(1); }
  50%    { opacity:0.5; transform:scale(1.4); }
}
@keyframes ppFadeUp {
  from{ opacity:0; transform:translateY(12px); }
  to  { opacity:1; transform:translateY(0); }
}
@keyframes ppShimmer {
  0%  { background-position: -200% center; }
  100%{ background-position:  200% center; }
}
@keyframes ppBorderGlow {
  0%,100%{ box-shadow: 0 0 0 1px rgba(0,213,89,0.14), 0 4px 20px rgba(0,0,0,0.4); }
  50%    { box-shadow: 0 0 0 1px rgba(0,213,89,0.38), 0 4px 24px rgba(0,213,89,0.10); }
}
@keyframes ppGradientShift {
  0%  { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100%{ background-position: 0% 50%; }
}
@keyframes ppScanLine {
  0%  { top: -2px; }
  100%{ top: 100%; }
}

/* ── Legacy animation aliases kept for Python helper functions ── */
@keyframes borderGlow        { 0%,100%{ box-shadow:0 0 0 1px rgba(0,213,89,0.14),0 4px 20px rgba(0,0,0,0.4); } 50%{ box-shadow:0 0 0 1px rgba(0,213,89,0.38),0 4px 24px rgba(0,213,89,0.10); } }
@keyframes fadeInUp          { from{ opacity:0; transform:translateY(10px); } to{ opacity:1; transform:translateY(0); } }
@keyframes ssFadeInUp        { from{ opacity:0; transform:translateY(16px); } to{ opacity:1; transform:translateY(0); } }
@keyframes headerShimmer     { 0%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } 100%{ background-position:0% 50%; } }
@keyframes gradientShift     { 0%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } 100%{ background-position:0% 50%; } }
@keyframes live-dot-pulse    { 0%,100%{ opacity:1; transform:scale(1); } 50%{ opacity:0.4; transform:scale(1.35); } }
@keyframes thePulse          { 0%,100%{ box-shadow:0 0 4px 1px rgba(0,213,89,0.60); opacity:1; } 50%{ box-shadow:0 0 10px 3px rgba(0,213,89,0.90); opacity:0.7; } }
@keyframes pulse-platinum    { 0%,100%{ box-shadow:0 0 10px rgba(45,158,255,0.30); } 50%{ box-shadow:0 0 24px rgba(45,158,255,0.60); } }
@keyframes pulse-gold        { 0%,100%{ box-shadow:0 0 10px rgba(249,198,43,0.35); } 50%{ box-shadow:0 0 24px rgba(249,198,43,0.65); } }
@keyframes nba-shimmer-platinum { 0%{ background-position:-300% center; } 100%{ background-position:300% center; } }
@keyframes nba-gold-gleam    { 0%,80%,100%{ filter:brightness(1); } 40%{ filter:brightness(1.35) drop-shadow(0 0 6px #F9C62B); } }
@keyframes nba-silver-sheen  { 0%{ background-position:-200% 0; } 100%{ background-position:200% 0; } }
@keyframes nba-bronze-pulse  { 0%,100%{ box-shadow:0 0 8px rgba(205,127,50,0.30); } 50%{ box-shadow:0 0 18px rgba(205,127,50,0.65); } }
@keyframes nba-live-pulse    { 0%,100%{ box-shadow:0 0 0 0 rgba(242,67,54,0.7); opacity:1; } 50%{ box-shadow:0 0 0 8px rgba(242,67,54,0); opacity:0.85; } }
@keyframes analysis-spin     { 0%{ transform:rotate(0deg); } 100%{ transform:rotate(360deg); } }
@keyframes aiSpin            { 0%{ transform:rotate(0deg); } 100%{ transform:rotate(360deg); } }
@keyframes card-flip-in      { 0%{ opacity:0; transform:rotateY(-90deg) scale(0.95); } 100%{ opacity:1; transform:rotateY(0deg) scale(1); } }
@keyframes fade-in-up        { from{ opacity:0; transform:translateY(16px); } to{ opacity:1; transform:translateY(0); } }
@keyframes slide-in-left     { from{ opacity:0; transform:translateX(-24px); } to{ opacity:1; transform:translateX(0); } }
@keyframes slide-in-right    { from{ opacity:0; transform:translateX(24px); } to{ opacity:1; transform:translateX(0); } }
@keyframes count-up-glow     { 0%{ text-shadow:none; } 50%{ text-shadow:0 0 16px rgba(0,213,89,0.5); } 100%{ text-shadow:none; } }
@keyframes numberGlow        { 0%,100%{ text-shadow:0 0 8px rgba(0,213,89,0.30); } 50%{ text-shadow:0 0 24px rgba(0,213,89,0.70); } }
@keyframes goldBreathe       { 0%,100%{ box-shadow:0 0 14px rgba(249,198,43,0.20); } 50%{ box-shadow:0 0 32px rgba(249,198,43,0.55); } }
@keyframes amberPulse        { 0%,100%{ border-color:rgba(249,198,43,0.18); box-shadow:0 0 12px rgba(249,198,43,0.04); } 50%{ border-color:rgba(249,198,43,0.55); box-shadow:0 0 22px rgba(249,198,43,0.12); } }
@keyframes pulseRing         { 0%{ transform:scale(0.8); opacity:0.6; } 50%{ transform:scale(1.1); opacity:1; } 100%{ transform:scale(0.8); opacity:0.6; } }
@keyframes connectorFlow     { 0%{ background-position:-200% 0; } 100%{ background-position:200% 0; } }
@keyframes scanLine          { 0%{ top:-2px; } 100%{ top:100%; } }
@keyframes cardShine         { 0%{ left:-100%; } 100%{ left:200%; } }
@keyframes data-stream       { 0%{ background-position:0 0; } 100%{ background-position:0 -100px; } }
@keyframes freshness-pulse-green  { 0%,100%{ box-shadow:0 0 0 0 rgba(0,213,89,0.6); } 50%{ box-shadow:0 0 0 5px rgba(0,213,89,0); } }
@keyframes freshness-pulse-yellow { 0%,100%{ box-shadow:0 0 0 0 rgba(249,198,43,0.6); } 50%{ box-shadow:0 0 0 5px rgba(249,198,43,0); } }
@keyframes freshness-pulse-red    { 0%,100%{ box-shadow:0 0 0 0 rgba(242,67,54,0.6); } 50%{ box-shadow:0 0 0 5px rgba(242,67,54,0); } }

/* ── Streamlit Chrome Reset ───────────────────────────────── */
#MainMenu { visibility: hidden !important; }
footer    { display: none !important; }
.stDeployButton { display: none !important; }
.block-container { padding-top: 1rem !important; }

@media (min-width: 769px) {
  header[data-testid="stHeader"] { display: none !important; }
  [data-testid="stSidebar"] {
    transform: none !important;
    visibility: visible !important;
    transition: none !important;
  }
  [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebar"] button[kind="header"] { display: none !important; }
}
@media (max-width: 768px) {
  header[data-testid="stHeader"] {
    background: transparent !important;
    height: 48px !important; min-height: 48px !important; max-height: 48px !important;
    padding: 0 !important; margin: 0 !important;
    border: none !important; box-shadow: none !important;
    overflow: visible !important;
    pointer-events: none !important;
    position: fixed !important; top: 0 !important; left: 0 !important; right: 0 !important;
    z-index: 9998 !important;
  }
  header[data-testid="stHeader"] button,
  header[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"],
  header[data-testid="stHeader"] [data-testid="collapsedControl"],
  header[data-testid="stHeader"] [data-testid="stToolbar"],
  header[data-testid="stHeader"] a {
    pointer-events: auto !important;
    visibility: visible !important;
  }
}

/* ── Base / Body ──────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  font-size: 16px;
  color: #A0AABE;
  background-color: #0D0F14;
}
.stApp {
  background-color: #0D0F14;
  background-image:
    radial-gradient(ellipse at 0% 0%,   rgba(0,213,89,0.04)  0%, transparent 50%),
    radial-gradient(ellipse at 100% 100%, rgba(45,158,255,0.03) 0%, transparent 50%);
}
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(ellipse at 15% 5%,  rgba(0,213,89,0.035)  0%, transparent 40%),
    radial-gradient(ellipse at 85% 95%, rgba(45,158,255,0.025) 0%, transparent 45%),
    #0D0F14;
}

/* Tabular nums for numeric readouts */
[style*="JetBrains"], .stat-readout, .prob-value, .edge-badge,
.dist-p10, .dist-p50, .dist-p90, .dist-label, .summary-value,
.status-card-value, .nba-stat-number, .verdict-confidence,
code, pre, .monospace {
  font-variant-numeric: tabular-nums !important;
}

/* Default text */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stCaptionContainer"],
.stTextInput label, .stSelectbox label, .stSlider label,
.stCheckbox label, .stRadio label {
  color: #A0AABE !important;
  font-size: 1rem !important;
}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] h5,
[data-testid="stMarkdownContainer"] h6,
.stHeadingWithActionElements,
h1, h2, h3, h4, h5, h6 {
  color: #FFFFFF !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: -0.01em !important;
}

/* ── Scrollbar ────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: rgba(13,15,20,0.9); }
::-webkit-scrollbar-thumb { background: rgba(0,213,89,0.25); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,213,89,0.50); }
::selection     { background: rgba(0,213,89,0.25); color: #fff; }
::-moz-selection{ background: rgba(0,213,89,0.25); color: #fff; }

/* ── Sidebar — PrizePicks dark style ──────────────────────── */
[data-testid="stSidebar"] {
  background: #0A0D14 !important;
  border-right: 1px solid rgba(255,255,255,0.06) !important;
  box-shadow: 2px 0 24px rgba(0,0,0,0.5) !important;
  min-width: 280px !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] a {
  color: #A0AABE !important;
}
[data-testid="stSidebar"] .stPageLink,
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
  font-size: 0.88rem !important;
  white-space: nowrap !important;
  overflow: visible !important;
  text-overflow: unset !important;
}
/* Active nav link — PP green left bar */
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] a[aria-current="page"] {
  background: rgba(0,213,89,0.08) !important;
  border-left: 3px solid #00D559 !important;
  color: #00D559 !important;
  font-weight: 700 !important;
}
[data-testid="stSidebar"]::after {
  content: "⚡ Smart Pick Pro AI Engine";
  display: block;
  position: fixed;
  bottom: 18px; left: 0;
  width: 100%;
  padding: 0 20px;
  box-sizing: border-box;
  text-align: center;
  font-size: 0.65rem;
  font-family: 'Inter', sans-serif;
  font-weight: 700;
  color: rgba(0,213,89,0.50) !important;
  letter-spacing: 0.06em;
  pointer-events: none;
  text-transform: uppercase;
}

/* ── Streamlit Metric Cards ───────────────────────────────── */
[data-testid="stMetric"] {
  background: #161B27;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.35);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
[data-testid="stMetric"]:hover {
  border-color: rgba(0,213,89,0.22);
  box-shadow: 0 4px 20px rgba(0,213,89,0.08), 0 6px 24px rgba(0,0,0,0.45);
  transform: translateY(-2px);
}
[data-testid="stMetricValue"] {
  color: #FFFFFF !important;
  font-size: 1.6rem !important;
  font-family: 'Bebas Neue', 'Inter', sans-serif !important;
  font-variant-numeric: tabular-nums !important;
  letter-spacing: 0.04em !important;
}
[data-testid="stMetricLabel"] {
  color: #6B7A9A !important;
  font-size: 0.75rem !important;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  font-weight: 600 !important;
}
[data-testid="stMetricDelta"] {
  font-family: 'Inter', sans-serif !important;
  font-weight: 700 !important;
  font-variant-numeric: tabular-nums !important;
}

/* ── Alerts ───────────────────────────────────────────────── */
.stAlert {
  background: #161B27 !important;
  border-radius: 10px !important;
  border: none !important;
  color: #E0E8FF !important;
  font-size: 0.93rem !important;
  padding: 14px 18px !important;
}
[data-testid="stAlert"][data-baseweb*="negative"],
div[data-testid="stNotification"][data-type="error"]   { border-left: 3px solid #F24336 !important; background: rgba(242,67,54,0.06)  !important; }
[data-testid="stAlert"][data-baseweb*="warning"],
div[data-testid="stNotification"][data-type="warning"] { border-left: 3px solid #F9C62B !important; background: rgba(249,198,43,0.06) !important; }
[data-testid="stAlert"][data-baseweb*="positive"],
div[data-testid="stNotification"][data-type="success"] { border-left: 3px solid #00D559 !important; background: rgba(0,213,89,0.06)  !important; }
[data-testid="stAlert"][data-baseweb*="informational"],
div[data-testid="stNotification"][data-type="info"]    { border-left: 3px solid #2D9EFF !important; background: rgba(45,158,255,0.06) !important; }

/* ── Buttons — PrizePicks pill style ──────────────────────── */
button[kind="primary"] {
  background: #00D559 !important;
  color: #0D0F14 !important;
  border: none !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: 0.03em !important;
  border-radius: 100px !important;
  box-shadow: 0 4px 16px rgba(0,213,89,0.30) !important;
  transition: transform 0.18s ease, box-shadow 0.18s ease !important;
}
button[kind="primary"]:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 24px rgba(0,213,89,0.45) !important;
}
.stButton > button {
  border-radius: 100px !important;
  font-weight: 700 !important;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease !important;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 4px 16px rgba(0,213,89,0.15) !important;
}

/* ── Tabs ─────────────────────────────────────────────────── */
[data-testid="stTab"] button {
  font-size: 0.88rem !important;
  font-weight: 600 !important;
  color: #6B7A9A !important;
  transition: color 0.2s ease !important;
}
[data-testid="stTab"] button[aria-selected="true"] {
  color: #00D559 !important;
  border-bottom: 2px solid #00D559 !important;
  font-weight: 700 !important;
}

/* ── Expanders ────────────────────────────────────────────── */
.stExpander {
  background: #161B27 !important;
  border: 1px solid rgba(255,255,255,0.07) !important;
  border-radius: 12px !important;
}
.stExpander summary,
.stExpander [data-testid="stExpanderToggleIcon"] + span {
  color: #E0E8FF !important;
  font-size: 0.95rem !important;
  font-weight: 600 !important;
}
.stExpander details,
[data-testid="stExpander"] details,
[data-testid="stExpanderDetails"] {
  overflow: visible !important;
  max-height: none !important;
}

/* ── DataFrames ───────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: none !important;
  border-radius: 12px !important;
  overflow: hidden !important;
}
[data-testid="stDataFrame"] td {
  font-size: 0.90rem !important;
  color: #E0E8FF !important;
  font-variant-numeric: tabular-nums !important;
  border-color: rgba(255,255,255,0.04) !important;
}
[data-testid="stDataFrame"] th {
  font-size: 0.72rem !important;
  color: #6B7A9A !important;
  text-transform: uppercase !important;
  letter-spacing: 1px !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 700 !important;
  background: #0D0F14 !important;
  border-color: rgba(255,255,255,0.05) !important;
}
[data-testid="stDataFrame"] tr:hover td  { background: rgba(0,213,89,0.04) !important; }
[data-testid="stDataFrame"] table        { border-collapse: collapse !important; }
[data-testid="stDataFrame"] th,
[data-testid="stDataFrame"] td           { border: none !important; }
.stDataFrame, .stTable { background: #161B27 !important; color: #E0E8FF !important; }

/* ── Live pulse dot ───────────────────────────────────────── */
.the-pulse {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #00D559;
  animation: thePulse 1.8s ease-in-out infinite;
  vertical-align: middle;
  margin-right: 6px;
  flex-shrink: 0;
}
.ss-fade-in-up  { animation: ssFadeInUp 0.4s ease both; }
.qds-fade-in    { animation: ssFadeInUp 0.5s ease both; animation-fill-mode: both; }
.fade-in-up     { animation: fade-in-up    0.4s ease both; }
.slide-in-left  { animation: slide-in-left  0.35s ease both; }
.slide-in-right { animation: slide-in-right 0.35s ease both; }
.pick-reveal    { animation: card-flip-in 0.45s cubic-bezier(0.25,0.46,0.45,0.94) both; perspective: 800px; }

/* ── Input focus ──────────────────────────────────────────── */
input:focus, textarea:focus, select:focus,
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  outline: none !important;
  box-shadow: 0 0 0 2px rgba(0,213,89,0.40) !important;
  border-color: rgba(0,213,89,0.55) !important;
}

/* ── Glass Card base ──────────────────────────────────────── */
.glass-card {
  background: #161B27;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  transition: border-color 0.22s ease, box-shadow 0.22s ease, transform 0.22s ease;
}
.glass-card:hover {
  border-color: rgba(0,213,89,0.22);
  box-shadow: 0 6px 28px rgba(0,213,89,0.08), 0 8px 32px rgba(0,0,0,0.5);
  transform: translateY(-3px);
}

/* ── SmartAI Card ─────────────────────────────────────────── */
.smartai-card {
  background: #161B27;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  animation: ppBorderGlow 4s ease-in-out infinite, fadeInUp 0.35s ease both;
  transition: border-color 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;
  position: relative;
  overflow: hidden;
}
.smartai-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);
  background-size: 200% 100%;
  animation: ppShimmer 4s ease infinite;
}
.smartai-card:hover {
  border-color: rgba(0,213,89,0.30);
  transform: translateY(-4px);
  box-shadow: 0 8px 32px rgba(0,213,89,0.10), 0 8px 32px rgba(0,0,0,0.5);
}

/* ── Neural Header ────────────────────────────────────────── */
.neural-header {
  background: linear-gradient(135deg, #161B27 0%, #1C2232 50%, #161B27 100%);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 24px 30px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}
.neural-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);
  background-size: 200% 100%;
  animation: ppShimmer 4s linear infinite;
}
.neural-header-title {
  font-size: 1.8rem;
  font-weight: 900;
  font-family: 'Inter', sans-serif;
  color: #FFFFFF;
  letter-spacing: -0.01em;
  line-height: 1.15;
}
.neural-header-subtitle {
  font-size: 0.84rem;
  color: #6B7A9A;
  margin-top: 6px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 600;
}
.circuit-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #00D559;
  margin: 0 6px;
  vertical-align: middle;
  animation: ppLiveDot 1.8s ease-in-out infinite;
  box-shadow: 0 0 8px rgba(0,213,89,0.9);
}

/* ── SPP Hero Header ──────────────────────────────────────── */
.spp-hero-header { display: flex; align-items: center; gap: 22px; text-align: left; }
.spp-hero-logo {
  max-width: 80%; height: auto; object-fit: contain; border-radius: 50%;
  box-shadow: 0 0 18px rgba(0,213,89,0.28), 0 0 8px rgba(45,158,255,0.18);
  flex-shrink: 0;
}
.nba-edition-label {
  font-size: 1.05rem; letter-spacing: 0.22em;
  color: #F24336;
  font-family: 'Bebas Neue', 'Oswald', sans-serif;
  font-weight: 700; margin-top: 4px;
}

/* ── Player Name / Team Pill ──────────────────────────────── */
.player-name {
  font-size: 1.2rem; font-weight: 800;
  font-family: 'Inter', sans-serif;
  color: #FFFFFF; letter-spacing: -0.01em;
}
.team-pill {
  display: inline-block;
  padding: 2px 10px; border-radius: 100px;
  font-weight: 700; font-size: 0.74rem;
  color: #fff;
  background: rgba(45,158,255,0.15);
  margin-left: 8px; vertical-align: middle;
  border: 1px solid rgba(45,158,255,0.28);
}
.position-tag { color: #6B7A9A; font-size: 0.80rem; margin-left: 8px; vertical-align: middle; }

/* ── Tier Badges — pill shaped ────────────────────────────── */
.tier-badge {
  display: inline-block; padding: 5px 16px; border-radius: 100px;
  font-weight: 800; font-size: 0.78rem; font-family: 'Inter', sans-serif;
  letter-spacing: 0.06em; text-transform: uppercase;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.tier-badge:hover { transform: scale(1.04); }
.tier-platinum {
  background: rgba(45,158,255,0.14) !important;
  border: 1px solid rgba(45,158,255,0.42) !important;
  color: #2D9EFF !important;
  animation: pulse-platinum 2.5s ease-in-out infinite, nba-shimmer-platinum 3s linear infinite !important;
}
.tier-gold {
  background: rgba(249,198,43,0.14) !important;
  border: 1px solid rgba(249,198,43,0.42) !important;
  color: #F9C62B !important;
  animation: pulse-gold 2.8s infinite, nba-gold-gleam 4s ease-in-out infinite !important;
}
.tier-silver {
  background: rgba(160,170,190,0.12) !important;
  border: 1px solid rgba(160,170,190,0.30) !important;
  color: #A0AABE !important;
  animation: nba-silver-sheen 3s linear infinite !important;
}
.tier-bronze {
  background: rgba(205,127,50,0.12) !important;
  border: 1px solid rgba(205,127,50,0.32) !important;
  color: #CD7F32 !important;
  animation: nba-bronze-pulse 2.5s ease-in-out infinite !important;
}

/* ── Live / Sample badges ─────────────────────────────────── */
.live-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(0,213,89,0.10); color: #00D559;
  border: 1px solid rgba(0,213,89,0.32);
  padding: 4px 12px; border-radius: 100px;
  font-size: 0.74rem; font-weight: 700;
  letter-spacing: 0.05em; text-transform: uppercase;
}
.live-badge::before {
  content: '';
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #00D559;
  animation: thePulse 1.8s ease-in-out infinite;
  flex-shrink: 0;
}
.sample-badge {
  display: inline-block;
  background: rgba(249,198,43,0.10); color: #F9C62B;
  border: 1px solid rgba(249,198,43,0.28);
  padding: 4px 12px; border-radius: 100px;
  font-size: 0.74rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.game-live-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: #F24336; color: #FFFFFF;
  font-family: 'Inter', sans-serif;
  font-size: 0.74rem; font-weight: 800;
  letter-spacing: 0.10em; padding: 4px 12px; border-radius: 100px;
  animation: nba-live-pulse 1.5s ease-in-out infinite;
  text-transform: uppercase;
}
.game-live-badge::before {
  content: '';
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: #FFFFFF;
  animation: live-dot-pulse 1.2s ease-in-out infinite;
}

/* ── MORE / LESS direction badges ─────────────────────────── */
.dir-over {
  background: rgba(0,213,89,0.12); color: #00D559;
  padding: 5px 16px; border-radius: 100px;
  font-weight: 800; font-size: 0.82rem;
  border: 1px solid rgba(0,213,89,0.32);
  font-family: 'Inter', sans-serif;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.dir-under {
  background: rgba(242,67,54,0.12); color: #F24336;
  padding: 5px 16px; border-radius: 100px;
  font-weight: 800; font-size: 0.82rem;
  border: 1px solid rgba(242,67,54,0.32);
  font-family: 'Inter', sans-serif;
  text-transform: uppercase; letter-spacing: 0.06em;
}

/* ── AI Verdict Cards ─────────────────────────────────────── */
.verdict-bet {
  background: rgba(0,213,89,0.06);
  border: 1.5px solid rgba(0,213,89,0.38);
  border-radius: 16px; padding: 16px 20px;
  animation: ppBorderGlow 2.5s ease-in-out infinite;
  box-shadow: 0 4px 20px rgba(0,213,89,0.07);
}
.verdict-avoid {
  background: rgba(242,67,54,0.06);
  border: 1.5px solid rgba(242,67,54,0.38);
  border-radius: 16px; padding: 16px 20px;
  box-shadow: 0 4px 20px rgba(242,67,54,0.07);
}
.verdict-risky {
  background: rgba(249,198,43,0.06);
  border: 1.5px solid rgba(249,198,43,0.32);
  border-radius: 16px; padding: 16px 20px;
  box-shadow: 0 4px 20px rgba(249,198,43,0.07);
}
.verdict-label {
  font-size: 1.3rem; font-weight: 900;
  font-family: 'Bebas Neue', 'Inter', sans-serif;
  letter-spacing: 0.12em; text-transform: uppercase;
}
.verdict-label-bet   { color: #00D559; }
.verdict-label-avoid { color: #F24336; }
.verdict-label-risky { color: #F9C62B; }
.verdict-confidence  { font-size: 0.78rem; color: #6B7A9A; margin-top: 4px; font-weight: 600; }
.verdict-explanation {
  font-size: 0.88rem; color: rgba(224,232,255,0.90);
  margin-top: 10px; line-height: 1.6;
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: 10px;
}

/* ── Stat Readout ─────────────────────────────────────────── */
.stat-readout {
  background: rgba(22,27,39,0.95);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px; padding: 8px 14px; margin: 4px 0;
  display: flex; justify-content: space-between; align-items: center;
  transition: background 0.2s ease;
}
.stat-readout:hover { background: rgba(28,34,50,0.95); }
.stat-readout-label { color: #6B7A9A; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; }
.stat-readout-value { color: #00D559; font-size: 0.96rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-readout-context { color: #6B7A9A; font-size: 0.74rem; margin-left: 10px; }

/* ── Education Box ────────────────────────────────────────── */
.education-box {
  background: #161B27; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 14px 18px; margin: 10px 0;
  transition: background 0.2s ease;
}
.education-box:hover { background: #1C2232; }
.education-box-title { font-size: 0.88rem; font-weight: 700; color: #2D9EFF; display: flex; align-items: center; gap: 7px; cursor: pointer; user-select: none; }
.education-box-content { font-size: 0.83rem; color: rgba(160,170,190,0.90); margin-top: 9px; line-height: 1.6; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 9px; }

/* ── Probability Gauge ────────────────────────────────────── */
.prob-gauge-wrap { background: rgba(13,15,20,0.80); border-radius: 10px; height: 14px; overflow: hidden; margin-top: 6px; border: 1px solid rgba(255,255,255,0.06); }
.prob-gauge-fill-over  { background: linear-gradient(90deg, #00D559, #2D9EFF); height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.prob-gauge-fill-under { background: linear-gradient(90deg, #F24336, #ff6b6b); height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.prob-value { font-size: 1.15rem; font-weight: 800; color: #FFFFFF; font-family: 'Bebas Neue', 'Inter', sans-serif; font-variant-numeric: tabular-nums; letter-spacing: 0.04em; }
.edge-badge { padding: 3px 10px; border-radius: 100px; font-size: 0.78rem; font-weight: 700; }
.edge-positive { background: rgba(0,213,89,0.12);  color: #00D559; border: 1px solid rgba(0,213,89,0.32);  }
.edge-negative { background: rgba(242,67,54,0.12); color: #F24336; border: 1px solid rgba(242,67,54,0.32); }

/* ── Force Bar ────────────────────────────────────────────── */
.force-bar-wrap { display: flex; height: 8px; border-radius: 100px; overflow: hidden; background: rgba(13,15,20,0.80); margin-top: 5px; border: 1px solid rgba(255,255,255,0.05); }
.force-bar-over  { background: linear-gradient(90deg, #00D559, #2D9EFF); }
.force-bar-under { background: linear-gradient(90deg, #F24336, #ff6b6b); }

/* ── Distribution Range ───────────────────────────────────── */
.dist-range-wrap { text-align: right; }
.dist-p10  { color: #F24336; font-size: 0.80rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.dist-p50  { color: #FFFFFF;  font-size: 0.90rem; font-weight: 800; font-variant-numeric: tabular-nums; }
.dist-p90  { color: #00D559; font-size: 0.80rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.dist-sep  { color: #3A4460; font-size: 0.80rem; margin: 0 3px; }
.dist-label{ color: #6B7A9A; font-size: 0.68rem; }

/* ── Form Dots ────────────────────────────────────────────── */
.form-dot-over  { display:inline-block; width:10px; height:10px; border-radius:50%; background:#00D559; box-shadow:0 0 5px rgba(0,213,89,0.65); margin:1px; vertical-align:middle; }
.form-dot-under { display:inline-block; width:10px; height:10px; border-radius:50%; background:#F24336; box-shadow:0 0 5px rgba(242,67,54,0.60); margin:1px; vertical-align:middle; }

/* ── Summary Cards ────────────────────────────────────────── */
.summary-card {
  background: #161B27; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 16px 20px; text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.summary-card:hover { border-color: rgba(0,213,89,0.28); box-shadow: 0 4px 20px rgba(0,213,89,0.10), 0 6px 24px rgba(0,0,0,0.4); transform: translateY(-2px); }
.summary-value { font-size: 2rem; font-weight: 900; color: #FFFFFF; line-height: 1.1; font-family: 'Bebas Neue', 'Inter', sans-serif; font-variant-numeric: tabular-nums; letter-spacing: 0.04em; }
.summary-label { font-size: 0.72rem; color: #6B7A9A; text-transform: uppercase; letter-spacing: 1.2px; margin-top: 5px; font-weight: 600; }

/* ── Best Bet Card ────────────────────────────────────────── */
.best-bet-card {
  background: #161B27; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 16px 20px; margin-bottom: 10px;
  position: relative; box-shadow: 0 2px 12px rgba(0,0,0,0.3);
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}
.best-bet-card:hover { border-color: rgba(0,213,89,0.30); transform: translateX(3px); box-shadow: 0 4px 20px rgba(0,213,89,0.10), 0 6px 20px rgba(0,0,0,0.4); }
.best-bet-rank { position: absolute; top: -10px; left: 16px; background: linear-gradient(135deg, #00D559, #2D9EFF); color: #0D0F14; font-weight: 900; font-size: 0.72rem; padding: 2px 10px; border-radius: 100px; font-family: 'Inter', sans-serif; letter-spacing: 0.05em; }

/* ── Player Analysis Card ─────────────────────────────────── */
.player-analysis-card {
  background: #161B27; border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px; padding: 20px 24px; margin-bottom: 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  animation: ppBorderGlow 4s ease-in-out infinite, fadeInUp 0.3s ease both;
  transition: border-color 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;
  position: relative; overflow: hidden;
}
.player-analysis-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);
  background-size: 200% 100%; animation: ppShimmer 4s ease infinite;
}
.player-analysis-card:hover { border-color: rgba(0,213,89,0.30); transform: translateY(-4px); box-shadow: 0 8px 32px rgba(0,213,89,0.10), 0 8px 32px rgba(0,0,0,0.5); }
.add-to-slip-btn { background: #00D559; color: #0D0F14; border: none; border-radius: 100px; padding: 7px 18px; font-weight: 800; font-size: 0.78rem; cursor: pointer; font-family: 'Inter', sans-serif; transition: opacity 0.2s ease, transform 0.2s ease; box-shadow: 0 4px 14px rgba(0,213,89,0.32); letter-spacing: 0.04em; text-transform: uppercase; }
.add-to-slip-btn:hover { opacity: 0.88; transform: scale(1.03); }

/* ── Roster Health ────────────────────────────────────────── */
.health-matched   { display:inline-block; background:rgba(0,213,89,0.10);  border:1px solid rgba(0,213,89,0.32);  color:#00D559; padding:2px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; margin:2px; }
.health-fuzzy     { display:inline-block; background:rgba(249,198,43,0.10); border:1px solid rgba(249,198,43,0.32); color:#F9C62B; padding:2px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; margin:2px; cursor:help; }
.health-unmatched { display:inline-block; background:rgba(242,67,54,0.10);  border:1px solid rgba(242,67,54,0.32);  color:#F24336; padding:2px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; margin:2px; }

/* ── Stat Chip ────────────────────────────────────────────── */
.stat-chip { display:inline-block; background:rgba(45,158,255,0.08); border:1px solid rgba(45,158,255,0.16); border-radius:100px; padding:4px 12px; margin-right:6px; margin-top:4px; color:#E0E8FF; font-size:0.82rem; font-weight:600; transition:background 0.2s ease; }
.stat-chip:hover { background: rgba(45,158,255,0.15); }
.stat-label { color: #6B7A9A; font-size: 0.72rem; }

/* ── Progress Ring ────────────────────────────────────────── */
.progress-ring-wrap { display:inline-flex; flex-direction:column; align-items:center; gap:4px; }
.progress-ring-label { font-size:0.72rem; color:#6B7A9A; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; }

/* ── Signal Strength Bar ──────────────────────────────────── */
.signal-bar-wrap { display:inline-flex; align-items:flex-end; gap:3px; height:22px; vertical-align:middle; }
.signal-bar-seg { width:7px; border-radius:2px; background:rgba(45,158,255,0.10); transition:background 0.2s ease; }
.signal-bar-seg.active { background: linear-gradient(180deg, #00D559, #2D9EFF); box-shadow: 0 0 4px rgba(0,213,89,0.5); }
.signal-strength-label { font-size:0.72rem; color:#6B7A9A; margin-left:6px; vertical-align:middle; font-weight:600; }

/* ── Inline Tooltip ───────────────────────────────────────── */
.edu-tooltip { position:relative; display:inline-block; border-bottom:1px dashed rgba(45,158,255,0.5); color:#2D9EFF; cursor:help; font-weight:600; }
.edu-tooltip .tooltip-text { visibility:hidden; opacity:0; width:260px; background:#161B27; border:1px solid rgba(255,255,255,0.10); color:#E0E8FF; font-size:0.80rem; font-weight:400; line-height:1.5; border-radius:12px; padding:10px 14px; position:absolute; z-index:999; bottom:130%; left:50%; transform:translateX(-50%); transition:opacity 0.18s ease; box-shadow:0 4px 24px rgba(0,0,0,0.5); pointer-events:none; }
.edu-tooltip:hover .tooltip-text { visibility:visible; opacity:1; }

/* ── Smart Tooltip ────────────────────────────────────────── */
.smart-tooltip-wrap { position:relative; cursor:help; }
.smart-tooltip { visibility:hidden; opacity:0; max-width:300px; min-width:140px; background:#161B27; border:1px solid rgba(255,255,255,0.10); border-radius:12px; padding:10px 14px; font-size:0.82rem; color:#A0AABE; line-height:1.5; position:absolute; z-index:9999; bottom:calc(100% + 8px); left:50%; transform:translateX(-50%) translateY(4px); box-shadow:0 4px 24px rgba(0,0,0,0.5); transition:opacity 0.18s ease, visibility 0.18s ease, transform 0.18s ease; pointer-events:none; }
.smart-tooltip::after { content:''; position:absolute; top:100%; left:50%; transform:translateX(-50%); border:6px solid transparent; border-top-color:rgba(255,255,255,0.10); }
.smart-tooltip-wrap:hover .smart-tooltip { visibility:visible; opacity:1; transform:translateX(-50%) translateY(0); }

/* ── Platform Badge ───────────────────────────────────────── */
.platform-badge { display:inline-block; padding:3px 10px; border-radius:100px; font-size:0.76rem; font-weight:700; transition:opacity 0.2s ease; }

/* ── Status Card ──────────────────────────────────────────── */
.status-card {
  background: #161B27; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px; padding: 20px 22px; text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3);
  transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
  position: relative; overflow: hidden;
}
.status-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, #00D559, #2D9EFF); opacity:0; transition:opacity 0.25s ease; }
.status-card:hover::before { opacity:1; }
.status-card:hover { border-color:rgba(0,213,89,0.22); transform:translateY(-3px); box-shadow:0 6px 24px rgba(0,213,89,0.10), 0 8px 28px rgba(0,0,0,0.4); }
.status-card-value { font-size:2.2rem; font-weight:900; color:#FFFFFF; font-family:'Bebas Neue','Inter',sans-serif; font-variant-numeric:tabular-nums; letter-spacing:0.04em; }
.status-card-label { font-size:0.70rem; color:#6B7A9A; text-transform:uppercase; letter-spacing:1.2px; margin-top:6px; font-weight:600; }

/* ── Team Chip ────────────────────────────────────────────── */
.team-chip { display:inline-block; background:rgba(45,158,255,0.08); color:#E0E8FF; border:1px solid rgba(255,255,255,0.08); padding:3px 10px; border-radius:100px; font-size:0.83rem; font-weight:600; margin:3px; transition:border-color 0.2s ease; }
.team-chip:hover { border-color: rgba(45,158,255,0.25); }

/* ── Correlation Warning ──────────────────────────────────── */
.corr-warning { background:rgba(249,198,43,0.08); border:1px solid rgba(249,198,43,0.26); border-radius:8px; padding:8px 14px; color:#F9C62B; font-size:0.83rem; margin-top:8px; }

/* ── GRT Picks Table ──────────────────────────────────────── */
.grt-summary-bar { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; padding:0 2px; }
.grt-chip { display:inline-flex; align-items:center; gap:4px; padding:5px 14px; border-radius:100px; font-size:0.70rem; font-weight:700; letter-spacing:0.5px; text-transform:uppercase; white-space:nowrap; }
.grt-table-wrap { border-radius:12px; overflow:hidden; border:1px solid rgba(255,255,255,0.07); background:#161B27; box-shadow:0 4px 20px rgba(0,0,0,0.3); }
.grt-table { width:100%; border-collapse:collapse; table-layout:fixed; }
.grt-th { padding:10px 12px; font-size:0.68rem; font-family:'Inter',sans-serif; font-weight:700; color:#6B7A9A; text-transform:uppercase; letter-spacing:1.2px; background:#0D0F14; border-bottom:1px solid rgba(255,255,255,0.06); text-align:left; white-space:nowrap; }
.grt-th-rank { width:44px; text-align:center; }
.grt-th-center { text-align:center; }
.grt-th-right { text-align:right; }
.grt-row { transition:background 0.15s ease; border-bottom:1px solid rgba(255,255,255,0.03); }
.grt-row:hover { background: rgba(0,213,89,0.04); }
.grt-td { padding:10px 12px; font-size:0.85rem; color:#E0E8FF; font-family:'Inter',sans-serif; vertical-align:middle; border-bottom:1px solid rgba(255,255,255,0.03); }
.grt-td-rank { text-align:center; width:44px; }
.grt-td-center { text-align:center; }
.grt-td-right { text-align:right; }
.grt-td-player { display:flex; align-items:center; gap:8px; }
.grt-team-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.grt-player-name { font-family:'Inter',sans-serif; font-weight:700; font-size:0.85rem; color:#FFFFFF; white-space:nowrap; }
.grt-team-label { font-size:0.68rem; color:#6B7A9A; font-weight:600; margin-left:2px; letter-spacing:0.5px; }
.grt-mono { font-variant-numeric:tabular-nums; }
.grt-dir { display:inline-block; padding:3px 12px; border-radius:100px; font-size:0.68rem; font-weight:800; font-family:'Inter',sans-serif; letter-spacing:0.5px; text-transform:uppercase; }
.grt-dir-over  { background:rgba(0,213,89,0.12);  color:#00D559; border:1px solid rgba(0,213,89,0.28);  }
.grt-dir-under { background:rgba(242,67,54,0.12); color:#F24336; border:1px solid rgba(242,67,54,0.28); }
.grt-safe-wrap { display:flex; flex-direction:column; align-items:center; gap:3px; min-width:56px; }
.grt-safe-num { font-size:0.82rem; font-weight:700; font-variant-numeric:tabular-nums; line-height:1; }
.grt-safe-track { width:100%; max-width:52px; height:3px; background:rgba(255,255,255,0.06); border-radius:100px; overflow:hidden; }
.grt-safe-fill { height:100%; border-radius:100px; transition:width 0.3s ease; }
.grt-tier { display:inline-block; padding:3px 10px; border-radius:100px; font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; }
.grt-rank { display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:8px; font-size:0.72rem; font-weight:700; color:#6B7A9A; background:rgba(255,255,255,0.04); }
.grt-rank-top { color:#00D559; background:rgba(0,213,89,0.12); border:1px solid rgba(0,213,89,0.28); }
@media (max-width: 768px) {
  .grt-table { font-size:0.78rem; }
  .grt-th, .grt-td { padding:8px 6px; }
  .grt-player-name { font-size:0.78rem; }
  .grt-summary-bar { gap:6px; }
  .grt-chip { padding:4px 10px; font-size:0.65rem; }
}

/* ── Data Freshness Badge ─────────────────────────────────── */
.data-freshness-badge { display:inline-flex; align-items:center; gap:5px; font-size:0.70rem; font-weight:700; letter-spacing:0.10em; padding:3px 10px; border-radius:100px; vertical-align:middle; text-transform:uppercase; }
.data-freshness-badge.fresh    { background:rgba(0,213,89,0.10);  color:#00D559; border:1px solid rgba(0,213,89,0.32);  animation:freshness-pulse-green  2s   ease-in-out infinite; }
.data-freshness-badge.stale    { background:rgba(249,198,43,0.10); color:#F9C62B; border:1px solid rgba(249,198,43,0.32); animation:freshness-pulse-yellow 2.5s ease-in-out infinite; }
.data-freshness-badge.outdated { background:rgba(242,67,54,0.10);  color:#F24336; border:1px solid rgba(242,67,54,0.32);  animation:freshness-pulse-red    1.8s ease-in-out infinite; }

/* ── NBA-specific elements ────────────────────────────────── */
.nba-game-day-banner {
  border-top: 3px solid transparent;
  border-image: linear-gradient(90deg, #00D559 0%, #FFFFFF 33%, #2D9EFF 66%, #00D559 100%) 1;
  background: #161B27; border-radius: 0 0 12px 12px;
  padding: 12px 24px; text-align: center;
  font-family: 'Bebas Neue', sans-serif; font-size: 1.4rem;
  letter-spacing: 0.25em; color: #FFFFFF; position: relative; overflow: hidden;
}
.nba-game-day-banner::before { content: '🏀'; margin-right: 12px; }
.nba-game-day-banner::after  { content: '🏀'; margin-left:  12px; }
.nba-stat-highlight { display:inline-flex; flex-direction:column; align-items:flex-start; border-left:4px solid #00D559; padding:8px 16px 8px 14px; background:rgba(0,213,89,0.06); border-radius:0 12px 12px 0; margin:4px 8px; transition:border-color 0.2s ease, background 0.2s ease; }
.nba-stat-highlight:hover { border-color:#2D9EFF; background:rgba(45,158,255,0.06); }
.nba-stat-number { font-family:'Bebas Neue',sans-serif; font-size:2.2rem; font-weight:700; color:#FFFFFF; line-height:1; letter-spacing:0.03em; }
.nba-stat-label  { font-family:'Oswald','Inter',sans-serif; font-size:0.70rem; font-weight:600; color:#6B7A9A; letter-spacing:0.12em; text-transform:uppercase; margin-top:2px; }
.stApp::after { content:''; display:block; position:fixed; bottom:-120px; right:-120px; width:360px; height:360px; border-radius:50%; border:40px solid rgba(0,213,89,0.02); pointer-events:none; z-index:0; }

/* ── Premium Metric Card ──────────────────────────────────── */
.premium-metric-card {
  background: #161B27; border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px; padding: 22px 26px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
  animation: count-up-glow 1.5s ease 0.2s both;
  position: relative; overflow: hidden;
}
.premium-metric-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559); background-size:200% 100%; animation:ppShimmer 4s ease infinite; }
.premium-metric-card:hover { transform:translateY(-5px) scale(1.01); border-color:rgba(0,213,89,0.30); box-shadow:0 8px 32px rgba(0,213,89,0.12), 0 12px 40px rgba(0,0,0,0.5); }

/* ── Spinners ─────────────────────────────────────────────── */
.ai-spinner       { width:36px; height:36px; border:3px solid rgba(0,213,89,0.12); border-top:3px solid #00D559; border-radius:50%; animation:aiSpin 0.9s linear infinite; margin:0 auto; }
.analysis-loading { display:inline-block; width:38px; height:38px; border:3px solid rgba(0,213,89,0.12); border-top-color:#00D559; border-radius:50%; animation:analysis-spin 0.9s linear infinite; vertical-align:middle; margin:0 10px; }

/* ── Data Stream ──────────────────────────────────────────── */
.data-stream { background-image: repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,213,89,0.025) 3px, rgba(0,213,89,0.025) 4px); background-size: 100% 100px; animation: data-stream 2s linear infinite; }

/* ── Correlation Stats ────────────────────────────────────── */
.corr-stats-bar { display:flex; flex-wrap:wrap; gap:12px; margin:16px 0; }
.corr-stat-card { flex:1; min-width:120px; background:#161B27; border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:10px 14px; text-align:center; }
.corr-stat-label { color:#6B7A9A; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; }
.corr-stat-value { font-size:1.15rem; font-weight:800; font-variant-numeric:tabular-nums; }
.corr-insight { background:#161B27; border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:12px 16px; margin:12px 0; }
.corr-insight-title { font-weight:700; font-size:0.85rem; color:#FFFFFF; }
.corr-insight-body  { color:#A0AABE; font-size:0.82rem; margin-top:4px; }
.corr-heatmap-wrap  { overflow-x:auto; -webkit-overflow-scrolling:touch; margin:0 -4px; padding:0 4px; }
@media (max-width: 768px) {
  .corr-stats-bar { gap:8px; }
  .corr-stat-card { min-width:calc(50% - 8px); flex:1 1 calc(50% - 8px); padding:8px 10px; }
  .corr-stat-value { font-size:1rem; }
  .corr-insight { padding:10px 12px; margin:8px 0; }
  .corr-heatmap-wrap { margin:0 -8px; padding:0 8px 8px; }
  .corr-heatmap-wrap .stPlotlyChart,
  .corr-heatmap-wrap [data-testid="stPlotlyChart"] { min-width:480px; }
}
@media (max-width: 480px) {
  .corr-stats-bar { flex-direction:column; gap:6px; }
  .corr-stat-card { min-width:100%; flex:1 1 100%; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; }
  .corr-heatmap-wrap .stPlotlyChart,
  .corr-heatmap-wrap [data-testid="stPlotlyChart"] { min-width:400px; }
}

/* ── Print ────────────────────────────────────────────────── */
@media print {
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"],
  .stButton, .stDownloadButton, [data-testid="stSidebarNav"] { display:none !important; }
  html, body, .stApp, [class*="css"] { background:#ffffff !important; color:#111111 !important; }
  .smartai-card, .premium-metric-card { background:#f5f5f5 !important; border:1px solid #cccccc !important; box-shadow:none !important; }
  section[data-testid="stMain"], .main .block-container { max-width:100% !important; padding:0 !important; }
}

/* ── Mobile ───────────────────────────────────────────────── */
@media (max-width: 768px) {
  html, body, [class*="css"] { font-size:14px !important; }
  .neural-header-title { font-size:1.4rem !important; }
  .smartai-card, .premium-metric-card { padding:14px 16px !important; }
  .nba-stat-number { font-size:1.7rem !important; }
  button, .stButton > button { min-height:44px !important; padding:10px 16px !important; }
  input, select, textarea, [role="button"], .stSelectbox > div { min-height:44px !important; }
  [data-testid="stMetricValue"] { font-size:1.2rem !important; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:8px !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width:calc(50% - 8px) !important; flex:1 1 calc(50% - 8px) !important; }
  [data-testid="stSidebar"] { min-width:0 !important; width:280px !important; max-width:85vw !important; z-index:9999 !important; position:fixed !important; top:0 !important; left:0 !important; height:100vh !important; height:100dvh !important; overflow-y:auto !important; overflow-x:hidden !important; -webkit-overflow-scrolling:touch !important; transition:transform 0.3s cubic-bezier(0.4,0,0.2,1), visibility 0.3s !important; box-shadow:4px 0 24px rgba(0,0,0,0.6) !important; }
  [data-testid="stSidebar"] > div:first-child { height:100% !important; overflow-y:auto !important; overflow-x:hidden !important; -webkit-overflow-scrolling:touch !important; display:flex !important; flex-direction:column !important; padding-bottom:24px !important; }
  [data-testid="stSidebar"][aria-expanded="false"] { transform:translateX(-100%) !important; visibility:hidden !important; box-shadow:none !important; }
  [data-testid="stSidebar"][aria-expanded="true"]  { transform:translateX(0) !important; visibility:visible !important; }
  [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], button[kind="header"],
  header[data-testid="stHeader"] button[kind="header"],
  header[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"],
  header[data-testid="stHeader"] > div > button {
    display:flex !important; visibility:visible !important; opacity:1 !important;
    position:fixed !important; top:10px !important; left:10px !important;
    z-index:10000 !important; background:rgba(22,27,39,0.97) !important;
    border:1px solid rgba(0,213,89,0.35) !important; border-radius:10px !important;
    padding:8px 10px !important; min-width:44px !important; min-height:44px !important;
    width:44px !important; height:44px !important; cursor:pointer !important;
    box-shadow:0 2px 16px rgba(0,0,0,0.5) !important;
    align-items:center !important; justify-content:center !important;
  }
  [data-testid="stSidebarCollapsedControl"] svg, [data-testid="collapsedControl"] svg,
  button[kind="header"] svg, header[data-testid="stHeader"] button svg { width:22px !important; height:22px !important; color:#00D559 !important; }
  [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebar"] button[kind="header"] { position:absolute !important; top:8px !important; right:8px !important; z-index:10001 !important; min-width:44px !important; min-height:44px !important; }
  section[data-testid="stMain"] { margin-left:0 !important; width:100% !important; }
  .main .block-container { padding-left:12px !important; padding-right:12px !important; padding-top:60px !important; max-width:100% !important; }
  .stApp, section[data-testid="stMain"] { overflow-x:hidden !important; }
  .stDataFrame, [data-testid="stDataFrame"], .comp-table, .qds-strategy-table { overflow-x:auto !important; -webkit-overflow-scrolling:touch !important; max-width:100% !important; }
  [data-testid="stPopover"] > div { max-width:92vw !important; max-height:80vh !important; overflow-y:auto !important; }
  [data-testid="stExpander"] summary { min-height:44px !important; padding:10px 14px !important; }
  [data-testid="stTabs"] [role="tablist"] { overflow-x:auto !important; -webkit-overflow-scrolling:touch !important; flex-wrap:nowrap !important; gap:4px !important; }
  [data-testid="stTabs"] button[role="tab"] { min-height:44px !important; white-space:nowrap !important; flex-shrink:0 !important; padding:8px 14px !important; font-size:0.85rem !important; }
  img:not(.qcm-headshot):not(.upc-headshot):not(.bet-card-headshot):not(.gm-card-headshot):not(.gm-modal-headshot):not(.joseph-welcome-avatar):not(.upc-joseph-avatar):not(.upc-joseph-resp-avatar):not(.qds-player-img):not(.sweat-card-headshot):not(.joseph-floating-avatar):not(.joseph-avatar):not(.joseph-avatar-sm):not(.joseph-sidebar-avatar):not(.joseph-inline-avatar):not(.joseph-popover-avatar):not(.qam-mu-logo):not(.pc-head):not(.pc-id-avatar) { max-width:100% !important; height:auto !important; }
  iframe { max-width:100% !important; }
  [data-testid="stPageLink"] a { min-height:44px !important; display:flex !important; align-items:center !important; }
  [data-testid="stMetricLabel"] { font-size:0.75rem !important; }
  .glass-card { padding:14px 16px !important; border-radius:12px !important; }
  .qds-prop-card { padding:14px !important; margin-bottom:14px !important; }
  .qds-player-img { width:56px !important; height:56px !important; }
  .qds-container { max-width:100% !important; padding:0 10px !important; }
  .qds-na-card { padding:14px !important; margin-bottom:14px !important; }
  .qds-na-metrics-grid { grid-template-columns:repeat(2, 1fr) !important; gap:8px !important; }
  .qds-na-strategy-table, .qds-strategy-table { display:block !important; overflow-x:auto !important; -webkit-overflow-scrolling:touch !important; max-width:100% !important; }
  .qds-game-teams { padding:10px 14px !important; gap:10px !important; }
  .qds-na-matchup { gap:10px !important; padding:10px !important; }
  .qds-na-verdict { padding:10px 14px !important; }
  .qds-report-title-text { font-size:clamp(1.1rem, 3.5vw, 1.6rem) !important; }
  [data-testid="stSidebar"]::after { display:none !important; }
}
@media (max-width: 480px) {
  [data-testid="stSidebar"] { width:100vw !important; max-width:100vw !important; border-right:none !important; }
  .main .block-container { padding-left:8px !important; padding-right:8px !important; }
  [data-testid="stHorizontalBlock"] { flex-direction:column !important; gap:8px !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { width:100% !important; flex:1 1 100% !important; min-width:100% !important; }
}
@media (max-width: 896px) and (orientation: landscape) {
  .main .block-container { padding-top:48px !important; padding-left:10px !important; padding-right:10px !important; }
  [data-testid="stSidebar"] { width:260px !important; max-width:50vw !important; }
  [data-testid="stHorizontalBlock"] { flex-direction:row !important; flex-wrap:wrap !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width:calc(33% - 8px) !important; flex:1 1 auto !important; }
  html, body, [class*="css"] { font-size:13px !important; }
}
</style>
'@

$before = $raw.Substring(0, $cssStart)
$after  = $raw.Substring($cssEnd)
$result = $before + $newCss + $after

[System.IO.File]::WriteAllText($file, $result, [System.Text.Encoding]::UTF8)
Write-Host "Done. New file length: $($result.Length)"
