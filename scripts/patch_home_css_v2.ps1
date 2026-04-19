
# patch_home_css_v2.ps1 — uses line numbers to splice new CSS into Smart_Picks_Pro_Home.py
$file = "c:\Users\Josep\Documents\SmartAI-NBA-main\SmartAI-NBA-main\Smart_Picks_Pro_Home.py"
$lines = [System.IO.File]::ReadAllLines($file, [System.Text.Encoding]::UTF8)

$styleStartLine = 43   # 0-based index of the line containing <style>
$styleEndLine   = 1233 # 0-based index of the line containing </style>

Write-Host "CSS block at lines $($styleStartLine+1) to $($styleEndLine+1) (0-based $styleStartLine to $styleEndLine)"
Write-Host "First: $($lines[$styleStartLine])"
Write-Host "Last:  $($lines[$styleEndLine])"

$newCssLines = @'
<style>
/* ===========================================================
   SMART PICK PRO — LANDING PAGE CSS
   PrizePicks + DraftKings Pick 6 AI Style  (Phase 1)
   =========================================================== */

/* ── Landing Page Animations ──────────────────────────────── */
@keyframes lpFadeInUp   { from{ opacity:0; transform:translateY(28px); } to{ opacity:1; transform:translateY(0); } }
@keyframes lpSlideInLeft{ from{ opacity:0; transform:translateX(-24px); } to{ opacity:1; transform:translateX(0); } }
@keyframes lpOrbFloat  { 0%,100%{ transform:translate(0,0) scale(1); } 25%{ transform:translate(20px,-14px) scale(1.06); } 75%{ transform:translate(-18px,10px) scale(0.97); } }
@keyframes lpOrbFloat2 { 0%,100%{ transform:translate(0,0) scale(1); } 33%{ transform:translate(-28px,16px) scale(1.08); } 66%{ transform:translate(14px,-22px) scale(0.94); } }
@keyframes lpGradShift  { 0%{ background-position:0% 50%; } 50%{ background-position:100% 50%; } 100%{ background-position:0% 50%; } }
@keyframes lpScanLine   { 0%{ top:-2px; } 100%{ top:100%; } }
@keyframes lpConnFlow   { 0%{ background-position:-200% 0; } 100%{ background-position:200% 0; } }
@keyframes lpSubtleFloat{ 0%,100%{ transform:translateY(0); } 50%{ transform:translateY(-5px); } }
@keyframes lpCheckBounce{ 0%{ transform:scale(0); } 50%{ transform:scale(1.2); } 100%{ transform:scale(1); } }

/* Staggered entrance helpers */
.lp-anim    { animation: lpFadeInUp 0.65s cubic-bezier(0.22,1,0.36,1) both; }
.lp-anim-d1 { animation-delay: 0.10s; }
.lp-anim-d2 { animation-delay: 0.20s; }
.lp-anim-d3 { animation-delay: 0.30s; }
.lp-anim-d4 { animation-delay: 0.40s; }
.lp-anim-d5 { animation-delay: 0.50s; }
.lp-anim-d6 { animation-delay: 0.60s; }

/* ── Ambient Floating Orbs ────────────────────────────────── */
.lp-orbs-container {
    position: fixed; top:0; left:0; width:100%; height:100vh;
    pointer-events:none; z-index:0; overflow:hidden;
}
.lp-orb { position:absolute; border-radius:50%; filter:blur(90px); opacity:0.06; }
.lp-orb-1 {
    width:420px; height:420px;
    background: radial-gradient(circle, #00D559 0%, transparent 70%);
    top:-100px; right:-60px;
    animation: lpOrbFloat 22s ease-in-out infinite;
}
.lp-orb-2 {
    width:360px; height:360px;
    background: radial-gradient(circle, #2D9EFF 0%, transparent 70%);
    bottom:8%; left:-80px;
    animation: lpOrbFloat2 28s ease-in-out infinite;
}
.lp-orb-3 {
    width:300px; height:300px;
    background: radial-gradient(circle, #F9C62B 0%, transparent 70%);
    top:42%; right:12%;
    animation: lpOrbFloat 32s ease-in-out infinite reverse;
    opacity: 0.04;
}

/* ── Gradient Divider ─────────────────────────────────────── */
.lp-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.20) 20%, rgba(45,158,255,0.16) 50%, rgba(249,198,43,0.12) 80%, transparent);
    border: none;
    margin: 36px 0;
    position: relative;
}
.lp-divider::after {
    content: '';
    position: absolute; top:-1px; left:50%; transform:translateX(-50%);
    width:6px; height:3px; background:#00D559; border-radius:2px;
    box-shadow: 0 0 8px rgba(0,213,89,0.5);
}

/* ── Hero HUD ─────────────────────────────────────────────── */
.hero-hud {
    background: linear-gradient(135deg, rgba(22,27,39,0.80) 0%, rgba(13,15,20,0.90) 100%);
    backdrop-filter: blur(28px) saturate(1.2);
    -webkit-backdrop-filter: blur(28px) saturate(1.2);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 40px 48px;
    margin-bottom: 16px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06);
    position: relative; overflow: hidden;
    display: flex; align-items: center; gap: 32px;
}
.hero-hud::before {
    content: '';
    position: absolute; top:0; left:0; right:0; height:3px;
    background: linear-gradient(90deg, #00D559, #2D9EFF, #F9C62B, #00D559);
    background-size: 300% 100%;
    animation: lpGradShift 6s ease infinite;
}
.hero-hud::after {
    content: '';
    position: absolute; left:0; right:0; height:2px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.06), transparent);
    animation: lpScanLine 5s linear infinite;
    pointer-events: none;
}
.hero-hud-inner-glow {
    position: absolute; top:0; left:0; right:0; bottom:0;
    background:
        radial-gradient(ellipse at 20% 50%, rgba(0,213,89,0.04) 0%, transparent 60%),
        radial-gradient(ellipse at 80% 50%, rgba(45,158,255,0.03) 0%, transparent 60%);
    pointer-events: none;
}
.hero-hud-text { flex:1; min-width:0; position:relative; z-index:1; }
.hero-tagline {
    font-size: clamp(1.5rem, 3vw, 2.4rem);
    font-weight: 900;
    font-family: 'Inter', sans-serif;
    background: linear-gradient(135deg, #FFFFFF 0%, #00D559 40%, #2D9EFF 70%, #F9C62B 100%);
    background-size: 200% 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: lpGradShift 8s ease infinite;
    letter-spacing: -0.01em;
    margin: 0; line-height: 1.2;
}
.hero-subtext {
    font-size: clamp(0.9rem, 1.4vw, 1.05rem);
    color: rgba(255,255,255,0.82);
    font-family: 'Inter', sans-serif;
    letter-spacing: 0.01em;
    margin-top: 12px; line-height: 1.6;
}
.hero-subtext strong { color: #00D559; font-weight: 700; }
.hero-date {
    font-size: 0.80rem;
    color: rgba(107,122,154,0.85);
    margin-top: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.03em;
}
.hero-date .game-count-live { color: #00D559; font-weight: 600; }
@media (max-width: 640px) {
    .hero-hud { flex-direction: column; text-align: center; padding: 28px 22px; gap: 20px; }
    .hero-tagline { font-size: 1.3rem; }
}

/* ── Section Header ───────────────────────────────────────── */
.section-header {
    font-size: 1.1rem;
    font-weight: 800;
    font-family: 'Inter', sans-serif;
    color: #FFFFFF;
    letter-spacing: -0.01em;
    margin: 32px 0 16px;
    display: flex; align-items: center; gap: 10px;
}
.section-header::after {
    content: '';
    flex: 1; height: 1px;
    background: linear-gradient(90deg, rgba(0,213,89,0.22), transparent);
}

/* ── Status Card ──────────────────────────────────────────── */
.status-card {
    background: #161B27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 20px 22px;
    text-align: center;
    box-shadow: 0 2px 14px rgba(0,0,0,0.35);
    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
    position: relative; overflow: hidden;
}
.status-card::before {
    content: '';
    position: absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    opacity: 0; transition: opacity 0.25s ease;
}
.status-card:hover::before { opacity: 1; }
.status-card:hover {
    border-color: rgba(0,213,89,0.24);
    transform: translateY(-4px);
    box-shadow: 0 6px 24px rgba(0,213,89,0.10), 0 10px 30px rgba(0,0,0,0.45);
}
.status-card-value {
    font-size: 2.2rem; font-weight: 900; color: #FFFFFF;
    font-family: 'Bebas Neue', 'Inter', sans-serif;
    font-variant-numeric: tabular-nums;
}
.status-card-label {
    font-size: 0.72rem; color: #6B7A9A;
    text-transform: uppercase; letter-spacing: 1.2px;
    margin-top: 6px; font-weight: 600;
}

/* ── Pillar Card ──────────────────────────────────────────── */
.pillar-card {
    background: #161B27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 24px 22px;
    height: 100%;
    box-shadow: 0 4px 18px rgba(0,0,0,0.35);
    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
    position: relative; overflow: hidden;
    display: flex; flex-direction: column; gap: 10px;
}
.pillar-card::before {
    content: '';
    position: absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    opacity: 0; transition: opacity 0.25s ease;
}
.pillar-card:hover::before { opacity: 1; }
.pillar-card:hover {
    border-color: rgba(0,213,89,0.22);
    transform: translateY(-4px);
    box-shadow: 0 8px 28px rgba(0,213,89,0.08), 0 12px 36px rgba(0,0,0,0.45);
}
.pillar-icon {
    font-size: 1.8rem;
    width: 52px; height: 52px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0,213,89,0.08);
    border-radius: 14px;
    border: 1px solid rgba(0,213,89,0.18);
    flex-shrink: 0;
}
.pillar-title { font-size: 1.0rem; font-weight: 800; color: #FFFFFF; font-family: 'Inter', sans-serif; }
.pillar-body  { font-size: 0.84rem; color: #A0AABE; line-height: 1.55; }

/* ── Proof Card ───────────────────────────────────────────── */
.proof-card {
    background: #161B27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 20px 22px;
    text-align: center;
    transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
    box-shadow: 0 2px 12px rgba(0,0,0,0.3);
}
.proof-card:hover {
    border-color: rgba(249,198,43,0.28);
    transform: translateY(-3px);
    box-shadow: 0 6px 24px rgba(249,198,43,0.08), 0 8px 28px rgba(0,0,0,0.4);
}
.proof-card-number {
    font-size: 2.4rem; font-weight: 900;
    font-family: 'Bebas Neue', 'Inter', sans-serif;
    color: #F9C62B;
    font-variant-numeric: tabular-nums; line-height: 1;
}
.proof-card-label { font-size: 0.72rem; color: #6B7A9A; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; font-weight: 600; }

/* ── Pipeline / AI Steps ──────────────────────────────────── */
.pipeline-step {
    background: #161B27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 18px 20px;
    display: flex; gap: 14px; align-items: flex-start;
    box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    transition: border-color 0.22s ease, transform 0.22s ease;
    position: relative; overflow: hidden;
}
.pipeline-step::before {
    content: '';
    position: absolute; top:0; left:0; bottom:0; width:3px;
    background: linear-gradient(180deg, #00D559, #2D9EFF);
    opacity: 0.55;
}
.pipeline-step:hover { border-color: rgba(0,213,89,0.22); transform: translateX(3px); }
.pipeline-step-num   { font-family: 'Bebas Neue', 'Inter', sans-serif; font-size: 1.6rem; font-weight: 900; color: #00D559; line-height: 1; flex-shrink: 0; width: 32px; }
.pipeline-step-title { font-size: 0.92rem; font-weight: 700; color: #FFFFFF; }
.pipeline-step-body  { font-size: 0.80rem; color: #A0AABE; margin-top: 3px; line-height: 1.5; }

/* ── Connector animated line ──────────────────────────────── */
.lp-connector {
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(0,213,89,0.35), #2D9EFF, rgba(0,213,89,0.35), transparent);
    background-size: 200% 100%;
    animation: lpConnFlow 2.5s linear infinite;
    border-radius: 100px; margin: 4px 0;
}

/* ── Matchup Chip ─────────────────────────────────────────── */
.matchup-chip {
    background: #161B27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 10px 16px;
    font-size: 0.82rem; color: #A0AABE;
    transition: border-color 0.2s ease, background 0.2s ease;
}
.matchup-chip:hover { border-color: rgba(0,213,89,0.22); background: #1C2232; }
.matchup-vs { color: #6B7A9A; font-size: 0.72rem; margin: 0 4px; }

/* ── Navigation Cards ─────────────────────────────────────── */
.nav-card {
    background: #161B27;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 22px 20px;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.35);
    transition: border-color 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;
    cursor: pointer; text-decoration: none;
    display: block; height: 100%;
    position: relative; overflow: hidden;
}
.nav-card::before {
    content: '';
    position: absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
    opacity: 0; transition: opacity 0.22s ease;
}
.nav-card:hover::before { opacity: 1; }
.nav-card:hover {
    border-color: rgba(0,213,89,0.28);
    transform: translateY(-5px);
    box-shadow: 0 8px 28px rgba(0,213,89,0.10), 0 12px 36px rgba(0,0,0,0.45);
}
.nav-card-icon  { font-size: 1.8rem; margin-bottom: 10px; display: block; filter: drop-shadow(0 0 8px rgba(0,213,89,0.25)); }
.nav-card-title { font-size: 0.96rem; font-weight: 800; color: #FFFFFF; font-family: 'Inter', sans-serif; }
.nav-card-desc  { font-size: 0.78rem; color: #6B7A9A; margin-top: 5px; line-height: 1.45; }

/* ── Team chips + badges (LP override) ───────────────────── */
.team-chip {
    display: inline-block;
    background: rgba(45,158,255,0.08); color: rgba(255,255,255,0.90);
    border: 1px solid rgba(255,255,255,0.08);
    padding: 3px 10px; border-radius: 100px;
    font-size: 0.83rem; font-weight: 600; margin: 3px;
    transition: border-color 0.2s ease;
}
.team-chip:hover { border-color: rgba(0,213,89,0.25); }
.live-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(0,213,89,0.08); color: #00D559;
    border: 1px solid rgba(0,213,89,0.30);
    padding: 3px 10px; border-radius: 100px;
    font-size: 0.78rem; font-weight: 700;
}
.live-badge::before {
    content: '';
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: #00D559;
    animation: thePulse 1.8s ease-in-out infinite;
    flex-shrink: 0;
}

/* ── Comp Table ───────────────────────────────────────────── */
.comp-table {
    width: 100%; border-collapse: collapse;
    border-radius: 12px; overflow: hidden;
    background: #161B27; border: 1px solid rgba(255,255,255,0.07);
}
.comp-table th { padding: 10px 14px; font-size: 0.70rem; font-weight: 700; color: #6B7A9A; text-transform: uppercase; letter-spacing: 1px; background: #0D0F14; border-bottom: 1px solid rgba(255,255,255,0.07); text-align: left; }
.comp-table td { padding: 10px 14px; font-size: 0.84rem; color: #E0E8FF; border-bottom: 1px solid rgba(255,255,255,0.04); font-variant-numeric: tabular-nums; }
.comp-table tr:hover td { background: rgba(0,213,89,0.04); }
.comp-table tr:last-child td { border-bottom: none; }
.comp-table .check   { color: #00D559; font-weight: 700; }
.comp-table .cross   { color: #F24336; font-weight: 700; }
.comp-table .partial { color: #F9C62B; font-weight: 700; }

/* ── Joseph Welcome Card ──────────────────────────────────── */
.joseph-welcome-card {
    background: linear-gradient(135deg, #161B27 0%, #1C2232 100%);
    border: 1px solid rgba(0,213,89,0.22);
    border-radius: 18px;
    padding: 22px 26px;
    display: flex; align-items: center; gap: 20px;
    margin-bottom: 18px;
    box-shadow: 0 4px 20px rgba(0,213,89,0.06), 0 4px 20px rgba(0,0,0,0.4);
    position: relative; overflow: hidden;
}
.joseph-welcome-card::before {
    content: '';
    position: absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg, #00D559, #2D9EFF);
}
.joseph-welcome-avatar {
    width: 60px; height: 60px; border-radius: 50%; object-fit: cover;
    border: 2px solid rgba(0,213,89,0.40);
    box-shadow: 0 0 14px rgba(0,213,89,0.25);
    flex-shrink: 0;
}
.joseph-welcome-text { flex: 1; min-width: 0; }
.joseph-welcome-greeting { font-size: 0.72rem; font-weight: 700; color: #00D559; text-transform: uppercase; letter-spacing: 0.08em; }
.joseph-welcome-msg { font-size: 0.90rem; color: #E0E8FF; margin-top: 4px; line-height: 1.55; }

/* ── LP Footer ────────────────────────────────────────────── */
.lp-footer { text-align: center; font-size: 0.72rem; color: #6B7A9A; padding: 28px 0 14px; border-top: 1px solid rgba(255,255,255,0.06); }
.lp-footer a { color: #2D9EFF; text-decoration: none; }
.lp-footer a:hover { text-decoration: underline; }

/* ── Responsive ───────────────────────────────────────────── */
@media (max-width: 768px) {
    .hero-hud { padding: 26px 18px; gap: 16px; }
    .pillar-card, .nav-card, .proof-card { padding: 16px 14px; }
    .status-card { padding: 14px 12px; }
    .status-card-value { font-size: 1.6rem; }
    .pillar-icon { width: 42px; height: 42px; font-size: 1.4rem; border-radius: 10px; }
    .pipeline-step { padding: 12px 10px; }
    .matchup-chip { padding: 8px 10px; font-size: 0.78rem; }
    .lp-divider { margin: 20px 0; }
    .lp-footer { font-size: 0.68rem; }
    .joseph-welcome-card { padding: 16px 14px; gap: 14px; }
    .joseph-welcome-avatar { width: 48px; height: 48px; }
    .joseph-welcome-msg { font-size: 0.82rem; }
}
@media (max-width: 480px) {
    .joseph-welcome-card { flex-direction: column; text-align: center; }
    .comp-table th, .comp-table td { padding: 8px 8px; font-size: 0.78rem; }
}
</style>
'@ -split "`n"

# Build new file: lines before CSS + new CSS lines + lines after CSS
$before = $lines[0..($styleStartLine - 1)]
$after  = $lines[($styleEndLine + 1)..($lines.Length - 1)]
$result = $before + $newCssLines + $after

[System.IO.File]::WriteAllLines($file, $result, [System.Text.Encoding]::UTF8)
Write-Host "Done. Lines: $($result.Count)"
