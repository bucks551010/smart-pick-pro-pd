# ============================================================
# FILE: styles/live_theme.py
# PURPOSE: Glassmorphic card and neon progress-bar CSS for the
#          Live Sweat dashboard.
# USAGE:
#   from styles.live_theme import get_live_sweat_css
#   st.markdown(get_live_sweat_css(), unsafe_allow_html=True)
# ============================================================

# ── NBA Player ID lookup for headshot URLs ───────────────────
# Maps common player names → nba.com player IDs for headshots.
_PLAYER_ID_MAP: dict[str, int] = {
    "lebron james": 2544,
    "stephen curry": 201939,
    "kevin durant": 201142,
    "giannis antetokounmpo": 203507,
    "nikola jokic": 203999,
    "luka doncic": 1629029,
    "jayson tatum": 1628369,
    "anthony edwards": 1630162,
    "shai gilgeous-alexander": 1628983,
    "damian lillard": 203081,
    "jimmy butler": 202710,
    "bam adebayo": 1628389,
    "devin booker": 1626164,
    "donovan mitchell": 1628378,
    "trae young": 1629027,
    "ja morant": 1629630,
    "tyrese haliburton": 1630169,
    "jalen brunson": 1628973,
    "victor wembanyama": 1641705,
    "anthony davis": 203076,
    "paul george": 202331,
    "kawhi leonard": 202695,
    "james harden": 201935,
    "joel embiid": 203954,
    "karl-anthony towns": 1626157,
    "kyrie irving": 202681,
    "de'aaron fox": 1628368,
    "zion williamson": 1629627,
    "chet holmgren": 1631096,
    "paolo banchero": 1631094,
    "lamelo ball": 1630163,
    "desmond bane": 1630217,
    "dejounte murray": 1627749,
    "domantas sabonis": 1627734,
    "lauri markkanen": 1628374,
    "scottie barnes": 1630567,
    "alperen sengun": 1630578,
    "franz wagner": 1630532,
    "cade cunningham": 1630595,
    "tyrese maxey": 1630178,
}


def get_player_headshot_url(player_name: str) -> str:
    """Return the NBA CDN headshot URL for a player, or empty string."""
    pid = _PLAYER_ID_MAP.get(str(player_name).lower().strip())
    if pid:
        return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"
    return ""


def get_live_sweat_css() -> str:
    """Return a ``<style>`` block with Live Sweat dashboard classes."""
    return """<style>
/* ── Animated Card Entrance ──────────────────────────────── */
@keyframes slideUp {
    0%   { opacity: 0; transform: translateY(30px); }
    100% { opacity: 1; transform: translateY(0); }
}

/* ── Live Sweat Card ──────────────────────────────────────── */
.sweat-card {
    background: rgba(15, 23, 42, 0.8);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 15px;
    margin-bottom: 14px;
    transition: box-shadow 0.3s ease;
    animation: slideUp 0.5s ease-out both;
}
.sweat-card:hover {
    box-shadow: 0 0 18px rgba(0, 240, 255, 0.15);
}

/* ── Staggered card entrance (100ms per card) ────────────── */
.sweat-card:nth-child(1) { animation-delay: 0ms; }
.sweat-card:nth-child(2) { animation-delay: 100ms; }
.sweat-card:nth-child(3) { animation-delay: 200ms; }
.sweat-card:nth-child(4) { animation-delay: 300ms; }
.sweat-card:nth-child(5) { animation-delay: 400ms; }
.sweat-card:nth-child(6) { animation-delay: 500ms; }
.sweat-card:nth-child(7) { animation-delay: 600ms; }
.sweat-card:nth-child(8) { animation-delay: 700ms; }
.sweat-card:nth-child(9) { animation-delay: 800ms; }
.sweat-card:nth-child(10) { animation-delay: 900ms; }

/* ── Dynamic Card Glow by Pace ───────────────────────────── */
.sweat-card.glow-green {
    border: 1px solid rgba(34, 197, 94, 0.5);
    box-shadow: 0 0 16px rgba(34, 197, 94, 0.3), 0 0 40px rgba(34, 197, 94, 0.1);
}
.sweat-card.glow-red {
    border: 1px solid rgba(239, 68, 68, 0.5);
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.3), 0 0 40px rgba(239, 68, 68, 0.1);
    animation: slideUp 0.5s ease-out both, panicPulse 1.5s ease-in-out infinite;
}
.sweat-card.glow-gold {
    border: 1px solid rgba(234, 179, 8, 0.5);
    box-shadow: 0 0 18px rgba(234, 179, 8, 0.4), 0 0 50px rgba(234, 179, 8, 0.15);
    animation: slideUp 0.5s ease-out both, victoryShimmer 2s ease-in-out infinite;
}
@keyframes panicPulse {
    0%, 100% { box-shadow: 0 0 16px rgba(239, 68, 68, 0.3), 0 0 40px rgba(239, 68, 68, 0.1); }
    50%      { box-shadow: 0 0 24px rgba(239, 68, 68, 0.5), 0 0 60px rgba(239, 68, 68, 0.2); }
}
@keyframes victoryShimmer {
    0%, 100% { box-shadow: 0 0 18px rgba(234, 179, 8, 0.4), 0 0 50px rgba(234, 179, 8, 0.15); }
    50%      { box-shadow: 0 0 28px rgba(234, 179, 8, 0.6), 0 0 70px rgba(234, 179, 8, 0.25); }
}

/* ── Sweat Cards Grid Layout ─────────────────────────────── */
.sweat-cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 14px;
}
.sweat-cards-grid .sweat-card {
    margin-bottom: 0;
}

/* ── Sticky Metrics Bar ──────────────────────────────────── */
.sticky-metrics-bar {
    position: sticky;
    top: 0;
    z-index: 99;
    background: rgba(15, 23, 42, 0.95);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    padding: 8px 0;
    border-bottom: 1px solid rgba(0, 240, 255, 0.1);
    margin-bottom: 12px;
}

/* ── Live Heartbeat Indicator ────────────────────────────── */
.live-heartbeat {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}
.live-heartbeat-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #00ff9d;
    animation: heartbeat 1s ease-in-out infinite;
    flex-shrink: 0;
}
@keyframes heartbeat {
    0%, 100% { transform: scale(1); opacity: 1; box-shadow: 0 0 6px #00ff9d; }
    50%      { transform: scale(1.3); opacity: 0.7; box-shadow: 0 0 12px #00ff9d, 0 0 24px rgba(0,255,157,0.3); }
}

/* ── Confetti Animation ──────────────────────────────────── */
@keyframes confettiFall {
    0%   { transform: translateY(-100vh) rotate(0deg); opacity: 1; }
    100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
}
.confetti-container {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    z-index: 9999;
    overflow: hidden;
}
.confetti-piece {
    position: absolute;
    top: -20px;
    font-size: 1.5rem;
    animation: confettiFall 3s ease-in forwards;
}

/* ── Victory Lap Overlay ─────────────────────────────────── */
@keyframes victoryFadeIn {
    0%   { opacity: 0; transform: scale(0.8); }
    20%  { opacity: 1; transform: scale(1.05); }
    80%  { opacity: 1; transform: scale(1); }
    100% { opacity: 0; transform: scale(0.9); }
}
.victory-lap-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(135deg, rgba(234,179,8,0.85), rgba(255,215,0,0.75));
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    pointer-events: none;
    animation: victoryFadeIn 3s ease-in-out forwards;
}
.victory-lap-text {
    font-size: 2.5rem;
    font-weight: 900;
    color: #1a1a2e;
    text-shadow: 0 2px 8px rgba(255,255,255,0.3);
    text-align: center;
    max-width: 80%;
}
.victory-lap-emoji {
    font-size: 4rem;
    margin-bottom: 16px;
}

/* ── Player Headshot ─────────────────────────────────────── */
.sweat-card-headshot {
    width: 48px;
    height: 36px;
    object-fit: cover;
    border-radius: 6px;
    margin-right: 10px;
    flex-shrink: 0;
    background: rgba(255,255,255,0.05);
}

/* ── Stat Sparkline ──────────────────────────────────────── */
.sparkline-container {
    display: inline-block;
    vertical-align: middle;
    margin-left: 6px;
}

/* ── Sweat Score Gauge ───────────────────────────────────── */
.sweat-score-gauge {
    text-align: center;
    padding: 16px;
    margin-bottom: 16px;
    background: rgba(15, 23, 42, 0.8);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
}
.sweat-score-number {
    font-size: 3.5rem;
    font-weight: 900;
    font-variant-numeric: tabular-nums;
    line-height: 1;
    margin-bottom: 4px;
}
.sweat-score-label {
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(255,255,255,0.6);
}
@keyframes gaugeGlow {
    0%, 100% { text-shadow: 0 0 20px currentColor; }
    50%      { text-shadow: 0 0 40px currentColor, 0 0 60px currentColor; }
}
.sweat-score-animate {
    animation: gaugeGlow 2s ease-in-out infinite;
}

/* ── Emoji Reactions ─────────────────────────────────────── */
.sweat-reactions {
    display: flex;
    gap: 4px;
    margin-top: 6px;
}
.sweat-reaction-btn {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
    color: #fff;
}
.sweat-reaction-btn:hover {
    background: rgba(255,255,255,0.15);
    transform: scale(1.1);
}

/* ── Danger Zone Timeline ────────────────────────────────── */
.danger-zone {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    padding: 8px 12px;
    margin-top: 6px;
    font-size: 0.78rem;
    color: #f87171;
    display: flex;
    align-items: center;
    gap: 6px;
}
.danger-zone-urgent {
    animation: pulse-red 1.2s ease-in-out infinite;
}

/* ── Parlay Health Card ──────────────────────────────────── */
.parlay-health-card {
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(0, 240, 255, 0.2);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 16px;
}
.parlay-leg-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 0.8rem;
    color: #c8d8f0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.parlay-leg-weakest {
    color: #f87171;
    font-weight: 700;
}

/* ── Joseph Animated Avatar ──────────────────────────────── */
.joseph-avatar-container {
    display: inline-block;
    margin-right: 10px;
    vertical-align: middle;
}
.joseph-avatar-img {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid rgba(0, 240, 255, 0.4);
}
.joseph-avatar-victory {
    animation: josephBounce 0.6s ease-in-out infinite;
}
.joseph-avatar-panic {
    animation: josephShake 0.3s ease-in-out infinite;
}
.joseph-avatar-rage {
    animation: josephShake 0.15s ease-in-out infinite;
    border-color: rgba(239, 68, 68, 0.7);
}
@keyframes josephBounce {
    0%, 100% { transform: translateY(0); }
    50%      { transform: translateY(-4px); }
}
@keyframes josephShake {
    0%, 100% { transform: translateX(0); }
    25%      { transform: translateX(-3px); }
    75%      { transform: translateX(3px); }
}

/* ── Bet of the Night Card ───────────────────────────────── */
.bet-of-the-night {
    border: 2px solid rgba(234, 179, 8, 0.6) !important;
    box-shadow: 0 0 20px rgba(234, 179, 8, 0.3), 0 0 50px rgba(234, 179, 8, 0.1);
    position: relative;
}
.bet-of-the-night-badge {
    position: absolute;
    top: -10px;
    right: 12px;
    background: linear-gradient(135deg, #eab308, #f59e0b);
    color: #1a1a2e;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    z-index: 2;
}

/* ── Escalating Drama System ─────────────────────────────── */
@keyframes screenShake {
    0%, 100% { transform: translate(0, 0); }
    10% { transform: translate(-2px, -1px); }
    30% { transform: translate(2px, 1px); }
    50% { transform: translate(-1px, 2px); }
    70% { transform: translate(1px, -2px); }
    90% { transform: translate(-2px, 1px); }
}
.drama-meltdown {
    animation: slideUp 0.5s ease-out both, screenShake 0.5s ease-in-out infinite;
}
.drama-red-tint {
    position: relative;
}
.drama-red-tint::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(239, 68, 68, 0.08);
    border-radius: 12px;
    pointer-events: none;
    animation: pulse-red 1.2s ease-in-out infinite;
}

/* ── Scrolling Ticker Tape (Joseph Headlines) ────────────── */
.joseph-ticker-bar {
    background: linear-gradient(90deg, rgba(234,179,8,0.15), rgba(0,240,255,0.08), rgba(234,179,8,0.15));
    border: 1px solid rgba(234, 179, 8, 0.2);
    border-radius: 8px;
    overflow: hidden;
    padding: 6px 0;
    margin-bottom: 14px;
    position: relative;
}
.joseph-ticker-scroll {
    display: flex;
    animation: josephTickerScroll 25s linear infinite;
    white-space: nowrap;
}
.joseph-ticker-scroll:hover {
    animation-play-state: paused;
}
@keyframes josephTickerScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.joseph-ticker-item {
    flex-shrink: 0;
    padding: 0 24px;
    font-size: 0.8rem;
    font-weight: 700;
    color: #facc15;
    letter-spacing: 0.5px;
}
.joseph-ticker-separator {
    flex-shrink: 0;
    color: rgba(255,255,255,0.2);
    padding: 0 8px;
}

/* ── Defense Rating Badge ────────────────────────────────── */
.defense-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
    margin-left: 6px;
}
.defense-badge-weak {
    background: rgba(34, 197, 94, 0.2);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.3);
}
.defense-badge-mid {
    background: rgba(234, 179, 8, 0.15);
    color: #facc15;
    border: 1px solid rgba(234, 179, 8, 0.3);
}
.defense-badge-strong {
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

/* ── Minutes Share Indicator ─────────────────────────────── */
.minutes-share {
    display: inline-block;
    font-size: 0.68rem;
    color: rgba(255,255,255,0.45);
    margin-left: 4px;
}

/* ── Per-Quarter Breakdown Table ──────────────────────────── */
.quarter-breakdown {
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    font-size: 0.72rem;
}
.quarter-breakdown th {
    color: rgba(255,255,255,0.5);
    font-weight: 600;
    text-transform: uppercase;
    padding: 4px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    text-align: center;
}
.quarter-breakdown td {
    color: #c8d8f0;
    padding: 4px 8px;
    text-align: center;
    font-variant-numeric: tabular-nums;
}

/* ── Progress bar base track ─────────────────────────────── */
.progress-base {
    background: rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    height: 22px;
    width: 100%;
    overflow: hidden;
    position: relative;
}

/* ── Progress fill variants ──────────────────────────────── */
.progress-fill-blue {
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
    height: 100%;
    border-radius: 8px;
    transition: width 0.6s ease;
}

.progress-fill-orange {
    background: linear-gradient(90deg, #f97316, #fb923c);
    height: 100%;
    border-radius: 8px;
    transition: width 0.6s ease;
}

.progress-fill-red {
    background: linear-gradient(90deg, #ef4444, #f87171);
    height: 100%;
    border-radius: 8px;
    animation: pulse-red 1.2s ease-in-out infinite;
    transition: width 0.6s ease;
}

.progress-fill-green {
    background: linear-gradient(90deg, #22c55e, #4ade80);
    height: 100%;
    border-radius: 8px;
    box-shadow: 0 0 14px rgba(34, 197, 94, 0.6), 0 0 28px rgba(34, 197, 94, 0.3);
    transition: width 0.6s ease;
}

/* ── Progress percentage label ───────────────────────────── */
.progress-pct-label {
    position: absolute;
    right: 8px;
    top: 0;
    height: 22px;
    line-height: 22px;
    font-size: 0.7rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.9);
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
    pointer-events: none;
    z-index: 1;
}

/* ── Animations ──────────────────────────────────────────── */
@keyframes pulse-red {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.65; }
}

/* ── Stat label / value layout ───────────────────────────── */
.sweat-stat-label {
    color: rgba(255, 255, 255, 0.55);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.sweat-stat-value {
    color: #f0f4f8;
    font-size: 1.3rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
}

/* ── Direction badges ────────────────────────────────────── */
.sweat-badge-over {
    display: inline-block;
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}
.sweat-badge-under {
    display: inline-block;
    background: rgba(168, 85, 247, 0.2);
    color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}

/* ── Alert badges ────────────────────────────────────────── */
.sweat-badge-blowout {
    display: inline-block;
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}
.sweat-badge-foul {
    display: inline-block;
    background: rgba(234, 179, 8, 0.2);
    color: #facc15;
    border: 1px solid rgba(234, 179, 8, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}
.sweat-badge-cashed {
    display: inline-block;
    background: rgba(34, 197, 94, 0.2);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
}
.sweat-badge-lost {
    display: inline-block;
    background: rgba(239, 68, 68, 0.22);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.45);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
}
.sweat-badge-ot {
    display: inline-block;
    background: rgba(245, 158, 11, 0.2);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-right: 6px;
}

/* ── Cashed overlay ──────────────────────────────────────── */
.sweat-card-cashed {
    background: rgba(34, 197, 94, 0.12);
    border: 1px solid rgba(34, 197, 94, 0.4);
}

.sweat-card-lost {
    background: rgba(239, 68, 68, 0.10);
    border: 1px solid rgba(239, 68, 68, 0.35);
}

/* ── Awaiting tipoff card ────────────────────────────────── */
.sweat-card-waiting {
    background: rgba(30, 41, 59, 0.6);
    border: 1px dashed rgba(255, 255, 255, 0.12);
    opacity: 0.7;
}

/* ── Score Ticker — ESPN-style with auto-scroll ──────────── */
.espn-ticker-container {
    position: relative;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(8,12,24,0.98) 0%, rgba(13,18,40,0.95) 100%);
    border: 1px solid rgba(0,240,255,0.15);
    border-radius: 12px;
    padding: 0;
    margin-bottom: 16px;
}
.espn-ticker-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: linear-gradient(90deg, rgba(0,240,255,0.12), transparent);
    border-bottom: 1px solid rgba(0,240,255,0.10);
    font-size: 0.75rem;
    font-weight: 700;
    color: #00f0ff;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.espn-ticker-live-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #ff3b30;
    animation: espnPulse 1.5s ease-in-out infinite;
    flex-shrink: 0;
}
@keyframes espnPulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 4px #ff3b30; }
    50% { opacity: 0.4; box-shadow: none; }
}
.espn-ticker-track {
    display: flex;
    overflow-x: auto;
    scroll-behavior: smooth;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    gap: 0;
    padding: 0;
}
.espn-ticker-track::-webkit-scrollbar { display: none; }
/* Auto-scroll animation */
.espn-ticker-scroll {
    display: flex;
    animation: espnScroll var(--scroll-duration, 30s) linear infinite;
    gap: 0;
}
.espn-ticker-scroll:hover {
    animation-play-state: paused;
}
@keyframes espnScroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
/* Individual game card */
.espn-game-card {
    flex-shrink: 0;
    width: 280px;
    border-right: 1px solid rgba(255,255,255,0.06);
    padding: 12px 16px 10px;
    background: transparent;
    transition: background 0.2s;
    cursor: default;
}
.espn-game-card:hover {
    background: rgba(0,240,255,0.04);
}
.espn-game-status {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.espn-status-live { color: #ff3b30; }
.espn-status-final { color: #8a9bb8; }
.espn-status-sched { color: #00f0ff; }
/* Team row */
.espn-team-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 3px 0;
    gap: 8px;
}
.espn-team-abbr {
    font-weight: 700;
    font-size: 0.88rem;
    color: #c0d0e8;
    min-width: 40px;
}
.espn-team-score {
    font-weight: 900;
    font-size: 1.15rem;
    min-width: 32px;
    text-align: right;
    font-variant-numeric: tabular-nums;
}
.espn-team-winning { color: #ffffff; }
.espn-team-losing { color: #6b7a94; }
/* Leaders section */
.espn-leaders {
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid rgba(255,255,255,0.06);
}
.espn-leader-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.68rem;
    color: #8a9bb8;
    padding: 1px 0;
}
.espn-leader-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-right: 8px;
}
.espn-leader-stat {
    font-weight: 700;
    color: #00ff9d;
    font-variant-numeric: tabular-nums;
}
/* Arrow navigation buttons */
.espn-ticker-nav {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    z-index: 10;
    background: rgba(13,18,40,0.92);
    border: 1px solid rgba(0,240,255,0.25);
    color: #00f0ff;
    border-radius: 50%;
    width: 28px; height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 0.8rem;
    opacity: 0;
    transition: opacity 0.2s;
}
.espn-ticker-container:hover .espn-ticker-nav { opacity: 0.85; }
.espn-ticker-nav:hover { opacity: 1 !important; background: rgba(0,240,255,0.15); }
.espn-ticker-nav-left { left: 4px; }
.espn-ticker-nav-right { right: 4px; }
/* Responsive — Mobile-optimized cards */
@media (max-width: 768px) {
    .espn-game-card { width: 200px; padding: 10px 12px 8px; }
    .espn-ticker-nav { display: none; }
    .sweat-cards-grid {
        grid-template-columns: 1fr;
        gap: 10px;
    }
    .sweat-card {
        padding: 12px;
    }
    .sweat-card-headshot {
        width: 40px;
        height: 30px;
    }
    .sweat-stat-value {
        font-size: 1.1rem;
    }
    .sweat-score-number {
        font-size: 2.5rem;
    }
    .sweat-reaction-btn {
        padding: 4px 10px;
        font-size: 1rem;
    }
    /* Ticker horizontal scroll instead of overflow */
    .espn-ticker-track {
        -webkit-overflow-scrolling: touch;
    }
}
@media (max-width: 480px) {
    .espn-game-card { width: 160px; padding: 8px 10px 6px; }
    .espn-team-abbr { font-size: 0.78rem; }
    .espn-team-score { font-size: 0.95rem; }
    .sweat-stat-value { font-size: 0.95rem; }
    .sweat-score-number { font-size: 2rem; }
    .sweat-card { padding: 10px; border-radius: 10px; }
    .sweat-card-headshot { width: 36px; height: 27px; }
    .sweat-reaction-btn { padding: 3px 8px; font-size: 0.9rem; min-height: 44px; }
}
/* Landscape — compact for limited vertical space.
   Use min-width: 481px to avoid overlap with ≤480px portrait rule. */
@media (min-width: 481px) and (max-width: 896px) and (orientation: landscape) {
    .espn-game-card { width: 180px; padding: 8px 10px 6px; }
    .sweat-cards-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .sweat-card { padding: 10px; }
    .sweat-score-number { font-size: 2rem; }
    .sweat-card-headshot { width: 36px; height: 27px; }
}
/* Landscape small phones (≤480px width in landscape) */
@media (max-width: 480px) and (orientation: landscape) {
    .espn-game-card { width: 160px; }
    .sweat-cards-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .sweat-card { padding: 8px; }
    .sweat-score-number { font-size: 1.8rem; }
}
</style>"""


def render_progress_bar(pct: float, color_tier: str) -> str:
    """
    Return an HTML snippet for a neon progress bar with percentage label.

    Parameters
    ----------
    pct : float
        Percentage (0-100+) of target achieved.
    color_tier : str
        One of ``blue``, ``orange``, ``red``, ``green``.
    """
    clamped = max(0, min(pct, 100))
    css_class = f"progress-fill-{color_tier}"
    return (
        f'<div class="progress-base">'
        f'<div class="{css_class}" style="width:{clamped:.1f}%;"></div>'
        f'<span class="progress-pct-label">{pct:.0f}%</span>'
        f'</div>'
    )


def render_sparkline_svg(quarter_values: list[float], width: int = 80,
                        height: int = 20, color: str = "#00f0ff") -> str:
    """Render a tiny inline SVG sparkline from quarter stat values."""
    if not quarter_values or len(quarter_values) < 2:
        return ""
    max_val = max(quarter_values) or 1
    n = len(quarter_values)
    x_step = width / max(1, n - 1)
    points = []
    for i, v in enumerate(quarter_values):
        x = round(i * x_step, 1)
        y = round(height - (v / max_val) * (height - 2), 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    return (
        f'<span class="sparkline-container">'
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{polyline}"/>'
        f'</svg></span>'
    )


def render_confetti_html() -> str:
    """Return HTML for a gold-coin confetti animation."""
    import random as _rnd
    pieces = []
    emojis = ["💰", "🪙", "💵", "✨", "🏆"]
    for i in range(20):
        left = _rnd.randint(5, 95)
        delay = _rnd.uniform(0, 1.5)
        emoji = emojis[i % len(emojis)]
        pieces.append(
            f'<span class="confetti-piece" style="left:{left}%;'
            f'animation-delay:{delay:.1f}s;">{emoji}</span>'
        )
    return f'<div class="confetti-container">{"".join(pieces)}</div>'


def render_victory_lap(quote: str) -> str:
    """Return HTML for a full-page gold victory lap overlay."""
    import html as _html
    safe_quote = _html.escape(str(quote))
    return (
        f'<div class="victory-lap-overlay">'
        f'<div class="victory-lap-emoji">🏆💰👑</div>'
        f'<div class="victory-lap-text">{safe_quote}</div>'
        f'</div>'
    )


def render_sweat_score_gauge(score: int) -> str:
    """Render the Sweat Score (0-100) animated gauge HTML."""
    score = max(0, min(100, int(score)))
    if score >= 80:
        color = "#22c55e"
        label = "LOCKED IN 🔒"
    elif score >= 50:
        color = "#f97316"
        label = "SWEATING 💦"
    elif score >= 25:
        color = "#ef4444"
        label = "DANGER ZONE 🚨"
    else:
        color = "#dc2626"
        label = "FULL PANIC 😱"
    return (
        f'<div class="sweat-score-gauge">'
        f'<div class="sweat-score-number sweat-score-animate" '
        f'style="color:{color};">{score}</div>'
        f'<div class="sweat-score-label">{label}</div>'
        f'<div class="sweat-score-label" style="margin-top:4px;">'
        f'SWEAT SCORE</div>'
        f'</div>'
    )


def render_joseph_ticker_bar(headlines: list[str]) -> str:
    """Render a scrolling ticker bar with Joseph's headlines."""
    import html as _html
    if not headlines:
        return ""
    items_html = ""
    for h in headlines:
        safe = _html.escape(str(h))
        items_html += f'<span class="joseph-ticker-item">🎙️ {safe}</span>'
        items_html += '<span class="joseph-ticker-separator">•</span>'
    # Duplicate for infinite scroll
    return (
        f'<div class="joseph-ticker-bar">'
        f'<div class="joseph-ticker-scroll">'
        f'{items_html}{items_html}'
        f'</div></div>'
    )


def render_danger_zone(stat_needed: float, minutes_left: float,
                       stat_type: str = "") -> str:
    """Render a danger zone countdown timeline."""
    import html as _html
    safe_stat = _html.escape(str(stat_type).replace("_", " ").upper())
    urgent_cls = "danger-zone-urgent" if minutes_left < 5 else ""
    return (
        f'<div class="danger-zone {urgent_cls}">'
        f'⏱️ Needs <strong>{stat_needed:.0f} more {safe_stat}</strong> '
        f'in <strong>{minutes_left:.1f} min</strong>'
        f'</div>'
    )


def render_sweat_card(
    player_name: str,
    stat_type: str,
    current_stat: float,
    target_stat: float,
    projected_final: float,
    pct_of_target: float,
    color_tier: str,
    blowout_risk: bool = False,
    foul_trouble: bool = False,
    cashed: bool = False,
    lost: bool = False,
    minutes_played: float = 0.0,
    direction: str = "OVER",
    minutes_remaining: float = 0.0,
    is_overtime: bool = False,
    quarter_values: list[float] | None = None,
    est_total_minutes: float = 0.0,
    defense_rank: int = 0,
    is_bet_of_night: bool = False,
    drama_level: int = 0,
) -> str:
    """
    Render one glassmorphic sweat card as an HTML string.

    New parameters
    --------------
    quarter_values : list of per-quarter stat accumulations for sparkline.
    est_total_minutes : projected total minutes for minutes-share display.
    defense_rank : opponent defensive rank (1-30); 0 = unknown.
    is_bet_of_night : if True, renders with gold border & badge.
    drama_level : 0-3; ≥3 triggers meltdown CSS.
    """
    import html as _html

    safe_name = _html.escape(str(player_name))
    safe_stat = _html.escape(str(stat_type).replace("_", " ").title())

    # Determine glow class based on pace
    glow = ""
    if cashed:
        glow = "glow-gold"
    elif lost:
        glow = "glow-red"
    elif color_tier == "green":
        glow = "glow-green"
    elif color_tier in ("red", "orange"):
        glow = "glow-red"

    card_class = "sweat-card"
    if cashed:
        card_class += " sweat-card-cashed"
    elif lost:
        card_class += " sweat-card-lost"
    if glow:
        card_class += f" {glow}"
    if is_bet_of_night:
        card_class += " bet-of-the-night"
    if drama_level >= 3:
        card_class += " drama-meltdown drama-red-tint"

    # "Bet of the Night" badge
    bon_badge = ""
    if is_bet_of_night:
        bon_badge = '<span class="bet-of-the-night-badge">🏆 BET OF THE NIGHT</span>'

    # Player headshot
    headshot_url = get_player_headshot_url(player_name)
    headshot_html = ""
    if headshot_url:
        headshot_html = (
            f'<img class="sweat-card-headshot" '
            f'src="{_html.escape(headshot_url)}" alt="" '
            f'onerror="this.style.display=\'none\'">'
        )

    # Direction badge
    dir_upper = str(direction).upper().strip()
    if dir_upper == "UNDER":
        dir_badge = '<span class="sweat-badge-under">⬇ UNDER</span>'
    else:
        dir_badge = '<span class="sweat-badge-over">⬆ OVER</span>'

    # Alert badges
    badges = ""
    if cashed:
        badges += '<span class="sweat-badge-cashed">✅ CASHED</span>'
    elif lost:
        badges += '<span class="sweat-badge-lost">❌ LOST</span>'
    if is_overtime:
        badges += '<span class="sweat-badge-ot">⏱️ OT</span>'
    if blowout_risk:
        badges += '<span class="sweat-badge-blowout">🚨 Blowout Risk</span>'
    if foul_trouble:
        badges += '<span class="sweat-badge-foul">⚠️ Foul Trouble</span>'

    # Defense rating badge
    def_badge = ""
    if defense_rank and 1 <= defense_rank <= 30:
        if defense_rank <= 10:
            def_badge = f'<span class="defense-badge defense-badge-strong">🛡️ vs. #{defense_rank} DEF</span>'
        elif defense_rank >= 21:
            def_badge = f'<span class="defense-badge defense-badge-weak">🔓 vs. #{defense_rank} DEF</span>'
        else:
            def_badge = f'<span class="defense-badge defense-badge-mid">🛡️ vs. #{defense_rank} DEF</span>'

    # Sparkline
    sparkline_html = ""
    if quarter_values and len(quarter_values) >= 2:
        spark_color = "#22c55e" if color_tier == "green" else "#ef4444" if color_tier == "red" else "#00f0ff"
        sparkline_html = render_sparkline_svg(quarter_values, color=spark_color)

    progress_html = render_progress_bar(pct_of_target, color_tier)

    remaining_txt = f" · {minutes_remaining:.0f} MIN left" if minutes_remaining > 0 else ""

    # Minutes share indicator
    minutes_share = ""
    if est_total_minutes > 0 and minutes_played > 0:
        minutes_share = (
            f'<span class="minutes-share">'
            f'({minutes_played:.0f}/{est_total_minutes:.0f} min projected)</span>'
        )

    return (
        f'<div class="{card_class}">'
        f'{bon_badge}'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
        f'<div style="display:flex;align-items:center;">'
        f'{headshot_html}'
        f'<div>'
        f'<div style="font-size:1.1rem;font-weight:700;color:#c8d8f0;">{safe_name}{sparkline_html}</div>'
        f'<div class="sweat-stat-label">{safe_stat} {dir_badge}{def_badge}</div>'
        f'</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div class="sweat-stat-value">{current_stat:.1f} / {target_stat:.1f}</div>'
        f'<div class="sweat-stat-label">{minutes_played:.0f} MIN{remaining_txt} {minutes_share}</div>'
        f'</div>'
        f'</div>'
        f'{progress_html}'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">'
        f'<div class="sweat-stat-label">Projected: <strong style="color:#00f0ff;">{projected_final:.1f}</strong></div>'
        f'<div>{badges}</div>'
        f'</div>'
        f'</div>'
    )


def render_waiting_card(player_name: str, stat_type: str,
                        target_stat: float, direction: str = "OVER") -> str:
    """
    Render a dimmed card for a bet whose game hasn't tipped off yet.
    """
    import html as _html

    safe_name = _html.escape(str(player_name))
    safe_stat = _html.escape(str(stat_type).replace("_", " ").title())
    dir_upper = str(direction).upper().strip()
    dir_label = "UNDER" if dir_upper == "UNDER" else "OVER"

    return (
        f'<div class="sweat-card sweat-card-waiting">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div>'
        f'<div style="font-size:1.05rem;font-weight:700;color:#8a9bb8;">{safe_name}</div>'
        f'<div class="sweat-stat-label">{safe_stat} · {dir_label} {target_stat:.1f}</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div class="sweat-stat-label" style="color:#64748b;">🕐 Awaiting Tip-Off</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


# ============================================================
# SECTION: Pillar 4 — Panic Room Card
# ============================================================

def get_panic_room_css() -> str:
    """
    Return a ``<style>`` block with the Panic Room vibe-glow
    card classes.  Each ``vibe_status`` maps to a distinct
    background glow for the Streamlit container.
    """
    return """<style>
/* ── Panic Room Vibe-Glow Cards ──────────────────────────── */
.panic-room-card {
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 16px;
    transition: box-shadow 0.4s ease, border 0.4s ease;
    border: 1px solid rgba(255, 255, 255, 0.06);
}

/* Panic — pulsing red glow */
.panic-room-card.panic-glow {
    border: 1px solid rgba(239, 68, 68, 0.5);
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.3), 0 0 40px rgba(239, 68, 68, 0.1);
    animation: panicPulse 1.5s ease-in-out infinite;
}
@keyframes panicPulse {
    0%, 100% { box-shadow: 0 0 16px rgba(239, 68, 68, 0.3), 0 0 40px rgba(239, 68, 68, 0.1); }
    50%      { box-shadow: 0 0 24px rgba(239, 68, 68, 0.5), 0 0 60px rgba(239, 68, 68, 0.2); }
}

/* Hype — neon orange glow */
.panic-room-card.hype-glow {
    border: 1px solid rgba(255, 158, 0, 0.5);
    box-shadow: 0 0 16px rgba(255, 158, 0, 0.35), 0 0 40px rgba(255, 158, 0, 0.12);
}

/* Disgust — sickly green glow */
.panic-room-card.disgust-glow {
    border: 1px solid rgba(132, 204, 22, 0.4);
    box-shadow: 0 0 14px rgba(132, 204, 22, 0.25), 0 0 36px rgba(132, 204, 22, 0.08);
}

/* Victory — golden glow */
.panic-room-card.victory-glow {
    border: 1px solid rgba(234, 179, 8, 0.5);
    box-shadow: 0 0 18px rgba(234, 179, 8, 0.4), 0 0 50px rgba(234, 179, 8, 0.15);
    animation: victoryShimmer 2s ease-in-out infinite;
}
@keyframes victoryShimmer {
    0%, 100% { box-shadow: 0 0 18px rgba(234, 179, 8, 0.4), 0 0 50px rgba(234, 179, 8, 0.15); }
    50%      { box-shadow: 0 0 28px rgba(234, 179, 8, 0.6), 0 0 70px rgba(234, 179, 8, 0.25); }
}

/* Sweating — blue-cyan anxious glow */
.panic-room-card.sweating-glow {
    border: 1px solid rgba(56, 189, 248, 0.4);
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.25), 0 0 36px rgba(56, 189, 248, 0.08);
}

/* ── Ticker Tape Headline ────────────────────────────────── */
.panic-room-headline {
    font-family: 'Orbitron', monospace, sans-serif;
    font-size: 1.05rem;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 8px;
    color: #f8fafc;
    text-shadow: 0 0 8px currentColor;
}
.panic-glow .panic-room-headline   { color: #f87171; }
.hype-glow .panic-room-headline    { color: #ff9e00; }
.disgust-glow .panic-room-headline { color: #a3e635; }
.victory-glow .panic-room-headline { color: #facc15; }
.sweating-glow .panic-room-headline{ color: #38bdf8; }

/* ── Vibe Badge ──────────────────────────────────────────── */
.panic-room-vibe-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    margin-bottom: 10px;
    background: rgba(255,255,255,0.08);
    color: #e2e8f0;
}

/* ── Rant Body ───────────────────────────────────────────── */
.panic-room-rant {
    color: #e2e8f0;
    font-size: 0.95rem;
    line-height: 1.7;
    font-family: 'Montserrat', sans-serif;
}
</style>"""


def render_panic_room_card(
    vibe_status: str,
    ticker_headline: str,
    joseph_rant: str,
    player_name: str = "",
    game_state: str = "",
) -> str:
    """
    Render the Pillar 4 Panic Room vibe-check card as an HTML string.

    Parameters
    ----------
    vibe_status : str
        One of ``VALID_VIBE_STATUSES``.  Drives the glow colour.
    ticker_headline : str
        ALL-CAPS headline (max 5 words).
    joseph_rant : str
        Joseph's dramatic, reality-anchored rant text.
    player_name : str
        Player name for the card header (optional).
    game_state : str
        Current game-state label (optional — shown as a sub-badge).
    """
    import html as _html
    from agent.response_parser import generate_vibe_css_class, get_vibe_emoji

    glow_class = generate_vibe_css_class(vibe_status)
    emoji = get_vibe_emoji(vibe_status)
    safe_headline = _html.escape(str(ticker_headline))
    safe_rant = _html.escape(str(joseph_rant))
    safe_player = _html.escape(str(player_name)) if player_name else ""
    safe_state = _html.escape(str(game_state).replace("_", " ").title()) if game_state else ""

    header_html = ""
    if safe_player:
        header_html = (
            f'<div style="color:#94a3b8;font-size:0.78rem;margin-bottom:4px;'
            f'letter-spacing:0.5px;">🎙️ {safe_player}</div>'
        )

    state_badge = ""
    if safe_state:
        state_badge = (
            f' <span style="color:#64748b;font-size:0.68rem;'
            f'margin-left:6px;">({safe_state})</span>'
        )

    return (
        f'<div class="panic-room-card {glow_class}">'
        f'{header_html}'
        f'<div class="panic-room-vibe-badge">{emoji} {_html.escape(vibe_status)}{state_badge}</div>'
        f'<div class="panic-room-headline">{safe_headline}</div>'
        f'<div class="panic-room-rant">{safe_rant}</div>'
        f'</div>'
    )


# ============================================================
# SECTION: Quarter Breakdown Table
# ============================================================

def render_quarter_breakdown(quarter_stats: list[float],
                             projected_q4: float = 0.0) -> str:
    """
    Render a per-quarter stat breakdown mini-table.

    Parameters
    ----------
    quarter_stats : list[float]
        Stats accumulated each quarter (Q1, Q2, Q3, ...).
    projected_q4 : float
        Projected Q4 stat (if game not over).
    """
    if not quarter_stats:
        return ""
    headers = "".join(f"<th>Q{i+1}</th>" for i in range(len(quarter_stats)))
    cells = "".join(f"<td>{v:.0f}</td>" for v in quarter_stats)
    if projected_q4 > 0 and len(quarter_stats) < 4:
        headers += "<th>Q4 (proj)</th>"
        cells += f'<td style="color:#facc15;font-style:italic;">{projected_q4:.0f}</td>'
    return (
        f'<table class="quarter-breakdown">'
        f'<tr>{headers}</tr>'
        f'<tr>{cells}</tr>'
        f'</table>'
    )


# ============================================================
# SECTION: Parlay Health Card
# ============================================================

def render_parlay_health(legs: list[dict]) -> str:
    """
    Render a parlay health rollup card.

    Each leg dict should have: player_name, stat_type, pct_of_target,
    on_pace, cashed.
    """
    import html as _html
    if not legs:
        return ""

    # Find weakest leg
    active_legs = [l for l in legs if not l.get("cashed")]
    weakest_idx = -1
    if active_legs:
        weakest = min(active_legs, key=lambda l: l.get("pct_of_target", 0))
        weakest_idx = next(
            (i for i, l in enumerate(legs) if l is weakest), -1
        )

    # Composite probability estimate (simplified product-of-paces)
    probs = []
    for l in legs:
        pct = l.get("pct_of_target", 50)
        p = min(1.0, pct / 100.0) if l.get("on_pace") else min(0.9, pct / 120.0)
        if l.get("cashed"):
            p = 1.0
        probs.append(p)
    composite = 1.0
    for p in probs:
        composite *= p
    composite_pct = composite * 100

    leg_rows = ""
    for i, l in enumerate(legs):
        name = _html.escape(str(l.get("player_name", "")))
        stat = _html.escape(str(l.get("stat_type", "")).replace("_", " ").title())
        pct = l.get("pct_of_target", 0)
        status = "✅" if l.get("cashed") else ("🟢" if l.get("on_pace") else "🔴")
        weak_cls = ' parlay-leg-weakest' if i == weakest_idx else ''
        leg_rows += (
            f'<div class="parlay-leg-row{weak_cls}">'
            f'<span>{status} {name} — {stat}</span>'
            f'<span>{pct:.0f}%</span>'
            f'</div>'
        )

    return (
        f'<div class="parlay-health-card">'
        f'<div style="font-size:1rem;font-weight:700;color:#00f0ff;margin-bottom:8px;">'
        f'🎰 Parlay Health — {composite_pct:.0f}% Composite</div>'
        f'{leg_rows}'
        f'</div>'
    )


# ============================================================
# SECTION: Sound Alerts & Keyboard Shortcuts (JS injection)
# ============================================================

def get_sound_alerts_js(enabled: bool = False) -> str:
    """Return a ``<script>`` block for cash/warning sound effects.

    Uses the Web Audio API to generate simple tones — no external
    files required.  Only active when *enabled* is ``True``.
    """
    if not enabled:
        return ""
    return """<script>
(function(){
    if(window._sweatSoundsInit) return;
    window._sweatSoundsInit = true;
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    window._playTone = function(freq, dur, type){
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = type || 'sine';
        o.frequency.value = freq;
        g.gain.value = 0.15;
        o.connect(g); g.connect(ctx.destination);
        o.start(); o.stop(ctx.currentTime + dur);
    };
    window._cashSound = function(){
        _playTone(523, 0.1, 'sine');
        setTimeout(()=>_playTone(659, 0.1, 'sine'), 100);
        setTimeout(()=>_playTone(784, 0.15, 'sine'), 200);
    };
    window._warningBuzz = function(){
        _playTone(220, 0.3, 'sawtooth');
    };
})();
</script>"""


def get_keyboard_shortcuts_js() -> str:
    """Return a ``<script>`` block with keyboard shortcuts.

    R = refresh, Esc = collapse all expanders.
    """
    return """<script>
(function(){
    if(window._sweatKeysInit) return;
    window._sweatKeysInit = true;
    document.addEventListener('keydown', function(e){
        if(e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        if(e.key === 'r' || e.key === 'R'){
            const btn = document.querySelector('[data-testid="stButton"] button');
            if(btn) btn.click();
        }
        if(e.key === 'Escape'){
            document.querySelectorAll('details[open]').forEach(d => d.removeAttribute('open'));
        }
    });
})();
</script>"""


def get_live_mode_avatar_css() -> str:
    """Return CSS for the 'Live Mode' animated border on Joseph's avatar.

    Produces a pulsing orange glow that activates only on the Live Sweat
    page to indicate active in-game tracking.
    """
    return """<style>
/* ── Live Mode Animated Avatar Border ────────────────────── */
/* Pulsing orange glow ring that activates during in-game tracking */
.joseph-avatar-live-mode {
    border-radius: 50%;
    border: 3px solid #ff5e00;
    box-shadow: 0 0 16px rgba(255, 94, 0, 0.6),
                0 0 32px rgba(255, 94, 0, 0.3),
                0 0 48px rgba(255, 94, 0, 0.15);
    animation: josephLivePulse 1.8s ease-in-out infinite;
}
@keyframes josephLivePulse {
    0%, 100% {
        box-shadow: 0 0 16px rgba(255, 94, 0, 0.6),
                    0 0 32px rgba(255, 94, 0, 0.3),
                    0 0 48px rgba(255, 94, 0, 0.15);
        border-color: #ff5e00;
    }
    50% {
        box-shadow: 0 0 24px rgba(255, 94, 0, 0.8),
                    0 0 48px rgba(255, 94, 0, 0.5),
                    0 0 72px rgba(255, 94, 0, 0.25);
        border-color: #ff9e00;
    }
}
/* ── Direction-Based Theme Colors ────────────────────────── */
/* Orange (#ff5e00) for OVER bets, Icy blue (#00c8ff) for UNDER bets */
.sweat-card.direction-over {
    --direction-color: #ff5e00;
    --direction-glow: rgba(255, 94, 0, 0.3);
    border-left: 3px solid #ff5e00;
}
.sweat-card.direction-under {
    --direction-color: #00c8ff;
    --direction-glow: rgba(0, 200, 255, 0.3);
    border-left: 3px solid #00c8ff;
}
.sweat-card.direction-over .sweat-direction-badge {
    background: rgba(255, 94, 0, 0.15);
    color: #ff5e00;
    border: 1px solid rgba(255, 94, 0, 0.3);
}
.sweat-card.direction-under .sweat-direction-badge {
    background: rgba(0, 200, 255, 0.15);
    color: #00c8ff;
    border: 1px solid rgba(0, 200, 255, 0.3);
}
</style>"""
