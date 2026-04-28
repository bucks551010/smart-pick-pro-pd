# ============================================================
# FILE: styles/studio_theme.py
# PURPOSE: All CSS for The Studio page — extracted from inline
#          _STUDIO_CSS in The_Studio.py for maintainability.
# USAGE:
#   from styles.studio_theme import get_studio_css, get_font_preload
#   st.markdown(get_font_preload(), unsafe_allow_html=True)
#   st.markdown(get_studio_css(), unsafe_allow_html=True)
# ============================================================


def get_font_preload() -> str:
    """Return HTML <link> tags to preload Google Fonts used in Studio.

    Prevents FOUT (Flash of Unstyled Text) for Orbitron, Montserrat,
    and JetBrains Mono.
    """
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?'
        'family=Inter:wght@400;600;700;800&'
        'family=JetBrains+Mono:wght@400;700&'
        'family=Montserrat:wght@400;600;700&'
        'family=Orbitron:wght@400;600;700&'
        'display=swap" rel="stylesheet">'
    )


def get_studio_css() -> str:
    """Return the complete Studio CSS as a ``<style>`` block.

    Includes:
    * CSS custom properties
    * Hero banner with animated scanline overlay
    * Mode selector cards with sweep micro-interaction
    * Glassmorphic depth layering (three tiers)
    * Fade-in content transition on mode switch
    * Quick-nav styling
    * Metric cards, game cards, ticket cards
    * Payout table
    * Skeleton shimmer loader
    * Animated confidence gauge stroke
    * Responsive breakpoints for mobile
    """
    return """<style>
/* ── CSS Custom Properties ── */
:root{
    --studio-muted:#94a3b8;
    --studio-accent:#ff5e00;
    --studio-accent-secondary:#ff9e00;
    --studio-text:#e2e8f0;
    --studio-bg-deep:rgba(7,10,19,0.88);
    --studio-bg-card:rgba(15,23,42,0.75);
    --studio-border:rgba(148,163,184,0.18);
    --studio-green:#22c55e;
    --studio-cyan:#00f0ff;
    --studio-red:#ff4444;
    --studio-yellow:#eab308;
}

/* ════════════════════════════════════════════════════════════
   A. Hero Banner — scanline overlay + broadcast bars
   ════════════════════════════════════════════════════════════ */
.studio-hero{
    background:var(--studio-bg-deep);
    backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
    border:1px solid rgba(255,94,0,0.35);
    border-radius:18px;padding:32px 24px;
    text-align:center;margin-bottom:28px;
    position:relative;overflow:hidden;
    /* C. Tier 1 — deepest glass, hero elevation */
    box-shadow:0 8px 60px rgba(0,0,0,0.5),0 0 60px rgba(255,94,0,0.08),
               inset 0 1px 0 rgba(255,158,0,0.1);
    z-index:3;
}
/* Scanline animated overlay */
.studio-hero .studio-scanlines{
    position:absolute;inset:0;pointer-events:none;z-index:0;
    background:repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(255,94,0,0.03) 2px,
        rgba(255,94,0,0.03) 4px
    );
    animation:studioScanlineDrift 8s linear infinite;
}
@keyframes studioScanlineDrift{
    0%{background-position:0 0}
    100%{background-position:0 100px}
}
/* Top broadcast bar */
.studio-hero::before{
    content:'';position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,#ff5e00,#ff9e00,#ff5e00);
    background-size:200% 100%;
    animation:studioShimmer 3s linear infinite;
    z-index:1;
}
/* Bottom broadcast bar */
.studio-hero::after{
    content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,#ff9e00,#ff5e00,#ff9e00);
    background-size:200% 100%;
    animation:studioShimmer 3s linear infinite reverse;
    z-index:1;
}
@keyframes studioShimmer{
    0%{background-position:-200% 0}100%{background-position:200% 0}
}
.studio-hero-title{
    font-family:'Orbitron',sans-serif;font-size:1.8rem;
    color:var(--studio-accent);font-weight:700;margin:14px 0 6px;
    letter-spacing:1px;
    text-shadow:0 0 20px rgba(255,94,0,0.3),0 0 40px rgba(255,94,0,0.1);
    position:relative;z-index:1;
}
.studio-hero-subtitle{
    color:var(--studio-muted);font-size:0.95rem;
    font-family:'Montserrat',sans-serif;
    letter-spacing:0.3px;
    position:relative;z-index:1;
}

/* ── ON AIR badge ── */
.studio-on-air{
    display:inline-flex;align-items:center;gap:6px;
    padding:4px 14px;border-radius:20px;
    background:rgba(255,32,32,0.15);border:1px solid rgba(255,32,32,0.4);
    font-family:'Orbitron',sans-serif;font-size:0.7rem;
    font-weight:700;color:#ff2020;letter-spacing:1px;
    margin:10px auto 4px;
    animation:studioOnAirPulse 2s ease-in-out infinite;
    position:relative;z-index:1;
}
.studio-on-air-dot{
    width:8px;height:8px;border-radius:50%;background:#ff2020;
    box-shadow:0 0 6px rgba(255,32,32,0.6);
    animation:studioOnAirDotPulse 1.4s ease-in-out infinite;
}
@keyframes studioOnAirPulse{
    0%,100%{box-shadow:0 0 8px rgba(255,32,32,0.2)}
    50%{box-shadow:0 0 16px rgba(255,32,32,0.4)}
}
@keyframes studioOnAirDotPulse{
    0%,100%{opacity:1;transform:scale(1)}
    50%{opacity:0.4;transform:scale(0.8)}
}
.studio-avatar-lg{
    width:120px;height:120px;border-radius:50%;
    border:3px solid #ff5e00;object-fit:cover;
    box-shadow:0 0 24px rgba(255,94,0,0.3),0 0 48px rgba(255,94,0,0.12);
    margin:0 auto;display:block;
    animation:studioAvatarPulse 4s ease-in-out infinite;
    position:relative;z-index:1;
}
@keyframes studioAvatarPulse{
    0%,100%{box-shadow:0 0 24px rgba(255,94,0,0.3),0 0 48px rgba(255,94,0,0.12)}
    50%{box-shadow:0 0 32px rgba(255,94,0,0.5),0 0 64px rgba(255,94,0,0.2)}
}

/* ════════════════════════════════════════════════════════════
   B. Mode Selector Cards — sweep animation on active
   ════════════════════════════════════════════════════════════ */
.studio-mode-cards{
    display:flex;gap:12px;margin:8px 0 20px;flex-wrap:wrap;
    justify-content:center;
}
.studio-mode-card{
    flex:1;min-width:180px;max-width:280px;
    background:var(--studio-bg-card);
    backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
    border:2px solid var(--studio-border);
    border-radius:14px;padding:18px 16px;text-align:center;
    cursor:pointer;transition:all 0.25s ease;
    position:relative;overflow:hidden;
}
.studio-mode-card:hover{
    border-color:rgba(255,94,0,0.4);
    box-shadow:0 4px 20px rgba(255,94,0,0.1);
    transform:translateY(-2px);
}
.studio-mode-card.active{
    border-color:var(--studio-accent);
    box-shadow:0 0 24px rgba(255,94,0,0.15);
}
/* Sweep animation on active card */
.studio-mode-card.active::before{
    content:'';
    position:absolute;
    top:0;left:-100%;
    width:100%;height:100%;
    background:linear-gradient(90deg,transparent,rgba(255,94,0,0.08),transparent);
    animation:studioModeSweep 2s ease-in-out infinite;
}
/* Active bottom underline reveal */
.studio-mode-card.active::after{
    content:'';position:absolute;bottom:0;left:0;right:0;height:2px;
    background:linear-gradient(90deg,transparent,var(--studio-accent),transparent);
    animation:studioUnderlineReveal 0.4s ease-out forwards;
}
@keyframes studioModeSweep{
    0%{left:-100%}
    50%{left:100%}
    100%{left:100%}
}
@keyframes studioUnderlineReveal{
    from{transform:scaleX(0)}
    to{transform:scaleX(1)}
}
.studio-mode-icon{font-size:1.6rem;margin-bottom:6px}
.studio-mode-title{
    font-family:'Orbitron',sans-serif;font-size:0.82rem;
    color:var(--studio-accent);font-weight:700;
    letter-spacing:0.3px;margin-bottom:4px;
}
.studio-mode-tag{
    color:var(--studio-muted);font-size:0.72rem;
    font-family:'Montserrat',sans-serif;
}

/* ════════════════════════════════════════════════════════════
   C. Glassmorphic Depth Layering — three tiers
   ════════════════════════════════════════════════════════════ */
/* Tier 2: Game cards — mid-glass */
.studio-game-card{
    background:var(--studio-bg-card);
    backdrop-filter:blur(8px);
    -webkit-backdrop-filter:blur(8px);
    border:1px solid var(--studio-border);
    border-left:3px solid rgba(255,94,0,0.4);
    border-radius:12px;padding:16px 20px;
    cursor:pointer;transition:all 0.25s ease;
    margin-bottom:10px;
    /* E. Fade-in on mode switch */
    animation:studioFadeIn 0.35s ease-out both;
}
.studio-game-card:hover{
    border-color:rgba(255,94,0,0.5);
    box-shadow:0 4px 24px rgba(255,94,0,0.12);
    transform:translateY(-1px);
}
.studio-game-card .team-badge{
    display:inline-block;padding:2px 8px;border-radius:4px;
    font-family:'Orbitron',sans-serif;font-size:0.72rem;
    font-weight:700;letter-spacing:0.5px;margin-right:4px;
}

/* Tier 2: Ticket cards — mid-glass with accent glow */
.studio-ticket-card{
    background:var(--studio-bg-deep);
    backdrop-filter:blur(12px);
    -webkit-backdrop-filter:blur(12px);
    border:1px solid rgba(255,94,0,0.3);
    border-radius:14px;padding:22px 26px;
    margin:16px 0;position:relative;overflow:hidden;
    box-shadow:0 4px 30px rgba(255,94,0,0.06),
               0 0 1px rgba(255,94,0,0.3);
    z-index:2;
    /* E. Fade-in on mode switch */
    animation:studioFadeIn 0.35s ease-out both;
}
.studio-ticket-card::before{
    content:'';position:absolute;top:0;left:0;right:0;height:2px;
    background:linear-gradient(90deg,transparent,#ff5e00,transparent);
    opacity:0.6;
}
.studio-ticket-header{
    font-family:'Orbitron',sans-serif;
    color:var(--studio-accent);font-size:1.15rem;
    font-weight:700;margin-bottom:12px;
    text-shadow:0 0 8px rgba(255,94,0,0.2);
}
.studio-ticket-leg{
    padding:8px 0;border-bottom:1px solid rgba(148,163,184,0.08);
    color:var(--studio-text);font-size:0.9rem;
    font-family:'Montserrat',sans-serif;
    transition:background 0.15s ease;
}
.studio-ticket-leg:last-child{border-bottom:none}
.studio-ticket-leg:hover{background:rgba(255,94,0,0.03);border-radius:4px}
.studio-section-title{
    font-family:'Orbitron',sans-serif;
    color:var(--studio-accent);font-size:1.2rem;font-weight:700;
    margin:28px 0 14px;letter-spacing:0.5px;
    text-shadow:0 0 10px rgba(255,94,0,0.15);
    padding-left:12px;
    border-left:3px solid #ff5e00;
}

/* Tier 3: Metric cards — surface glass */
.studio-metric-row{
    display:flex;gap:14px;flex-wrap:wrap;margin:14px 0;
}
.studio-metric-card{
    flex:1;min-width:140px;
    background:var(--studio-bg-card);
    border:1px solid rgba(255,94,0,0.2);
    border-radius:10px;padding:14px 18px;
    text-align:center;
    transition:all 0.2s ease;
    position:relative;overflow:hidden;
    z-index:1;
    /* E. Fade-in */
    animation:studioFadeIn 0.35s ease-out both;
}
.studio-metric-card::before{
    content:'';position:absolute;top:0;left:0;right:0;height:2px;
    background:linear-gradient(90deg,transparent,#ff5e00,transparent);
    opacity:0.4;
}
.studio-metric-card:hover{
    border-color:rgba(255,94,0,0.4);
    box-shadow:0 0 16px rgba(255,94,0,0.1);
    transform:translateY(-1px);
}
.studio-metric-value{
    font-family:'JetBrains Mono',monospace;
    font-variant-numeric:tabular-nums;
    font-size:1.4rem;color:var(--studio-accent);font-weight:700;
    text-shadow:0 0 8px rgba(255,94,0,0.2);
}
.studio-metric-label{
    color:var(--studio-muted);font-size:0.78rem;
    margin-top:4px;font-family:'Montserrat',sans-serif;
    text-transform:uppercase;letter-spacing:0.5px;
}

/* ════════════════════════════════════════════════════════════
   E. Fade-In Content Transition on Mode Switch
   ════════════════════════════════════════════════════════════ */
@keyframes studioFadeIn{
    from{opacity:0;transform:translateY(8px)}
    to{opacity:1;transform:translateY(0)}
}
.studio-fade-in{
    animation:studioFadeIn 0.35s ease-out both;
}

/* ════════════════════════════════════════════════════════════
   F. Animated Confidence Gauge Stroke
   ════════════════════════════════════════════════════════════ */
@keyframes studioGaugeFill{
    from{stroke-dasharray:0 226.2}
    to{stroke-dasharray:var(--gauge-dash) var(--gauge-gap)}
}
.studio-gauge-ring{
    animation:studioGaugeFill 0.8s ease-out forwards;
}

/* ════════════════════════════════════════════════════════════
   G. Skeleton Shimmer Loader
   ════════════════════════════════════════════════════════════ */
@keyframes studioShimmerLoader{
    0%{background-position:-200% 0}
    100%{background-position:200% 0}
}
.studio-skeleton-card{
    background:rgba(15,23,42,0.7);
    border:1px solid rgba(255,94,0,0.1);
    border-radius:12px;padding:18px 22px;
    margin-bottom:10px;min-height:80px;
    position:relative;overflow:hidden;
}
.studio-skeleton-card::after{
    content:'';position:absolute;inset:0;
    background:linear-gradient(
        90deg,
        transparent 0%,
        rgba(255,94,0,0.04) 40%,
        rgba(255,94,0,0.08) 50%,
        rgba(255,94,0,0.04) 60%,
        transparent 100%
    );
    background-size:200% 100%;
    animation:studioShimmerLoader 1.5s linear infinite;
}
.studio-skeleton-line{
    height:12px;border-radius:6px;
    background:rgba(148,163,184,0.12);
    margin-bottom:8px;
}
.studio-skeleton-line.short{width:40%}
.studio-skeleton-line.medium{width:70%}
.studio-skeleton-line.long{width:90%}

/* ════════════════════════════════════════════════════════════
   H. Quick-Nav Anchor Links
   ════════════════════════════════════════════════════════════ */
.studio-quick-nav{
    display:flex;gap:8px;flex-wrap:wrap;
    justify-content:center;margin:14px 0 6px;
}
.studio-quick-nav a{
    padding:6px 16px;border-radius:20px;font-size:0.78rem;
    font-family:'Orbitron',sans-serif;font-weight:600;
    color:var(--studio-accent);background:rgba(255,94,0,0.08);
    border:1px solid rgba(255,94,0,0.25);text-decoration:none;
    transition:all 0.2s ease;letter-spacing:0.3px;
}
.studio-quick-nav a:hover{
    background:rgba(255,94,0,0.15);
    box-shadow:0 0 12px rgba(255,94,0,0.1);
}

/* ════════════════════════════════════════════════════════════
   Payout Table
   ════════════════════════════════════════════════════════════ */
.studio-payout-table{
    width:100%;border-collapse:separate;border-spacing:0;
    font-family:'Montserrat',sans-serif;font-size:0.83rem;
    margin:12px 0;
}
.studio-payout-table th{
    background:rgba(255,94,0,0.1);color:var(--studio-accent);
    padding:8px 12px;text-align:center;
    font-family:'Orbitron',sans-serif;font-size:0.72rem;
    letter-spacing:0.4px;
    border-bottom:1px solid rgba(255,94,0,0.2);
}
.studio-payout-table td{
    padding:6px 12px;text-align:center;color:var(--studio-text);
    border-bottom:1px solid var(--studio-border);
    font-family:'JetBrains Mono',monospace;
    font-variant-numeric:tabular-nums;
}
.studio-payout-table td.highlight{color:var(--studio-green);font-weight:700}

/* ════════════════════════════════════════════════════════════
   I. Responsive Breakpoints for Mobile
   ════════════════════════════════════════════════════════════ */
@media (max-width:768px){
    .studio-mode-cards{flex-direction:column}
    .studio-mode-card{min-width:100%;max-width:100%;padding:14px 16px}
    .studio-metric-row{flex-wrap:wrap}
    .studio-metric-card{min-width:100%;padding:12px 14px}
    .studio-hero-title{font-size:1.3rem}
    .studio-avatar-lg{width:80px;height:80px}
    .studio-quick-nav{gap:6px;flex-wrap:wrap}
    .studio-quick-nav a{padding:5px 10px;font-size:0.7rem;min-height:44px;display:inline-flex;align-items:center}
    .joseph-dawg-table,
    .joseph-override-table,
    .studio-payout-table{
        display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%;
    }
}
@media (max-width:480px){
    .studio-hero-title{font-size:1.1rem}
    .studio-avatar-lg{width:60px;height:60px}
    .studio-mode-card{padding:12px;border-radius:10px}
    .studio-metric-card{padding:10px 12px;border-radius:8px}
    .studio-quick-nav a{padding:4px 8px;font-size:0.65rem}
}
/* Landscape — compact layout for limited vertical space */
@media (max-width:896px) and (orientation:landscape){
    .studio-mode-cards{flex-direction:row;flex-wrap:wrap}
    .studio-mode-card{min-width:calc(50% - 8px);max-width:calc(50% - 8px);padding:10px 12px}
    .studio-metric-row{flex-wrap:wrap}
    .studio-metric-card{min-width:calc(50% - 8px);padding:10px 12px}
    .studio-hero-title{font-size:1.1rem}
    .studio-avatar-lg{width:64px;height:64px}
    .studio-quick-nav a{padding:4px 10px;font-size:0.68rem;min-height:38px}
    .joseph-dawg-table,
    .joseph-override-table,
    .studio-payout-table{
        display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%;
    }
}
</style>"""
