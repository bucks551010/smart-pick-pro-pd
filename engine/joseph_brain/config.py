"""Joseph Brain — Configuration Constants.

All thresholds, mappings, personality responses, and classification
tables that drive Joseph's analysis and persona live here.
"""

# ═══════════════════════════════════════════════════════════════
# D) VERDICT THRESHOLDS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Edge is in percentage points (e.g. 8.0 = 8 %), confidence is 0-100 scale.
VERDICT_THRESHOLDS = {
    "LOCK": {"min_edge": 10.0, "min_confidence": 75.0},
    "SMASH": {"min_edge": 8.0, "min_confidence": 60.0},
    "LEAN": {"min_edge": 4.0, "min_confidence": 55.0},
    "FADE": {"max_edge": 3.0, "max_confidence": 50.0},
    "STAY_AWAY": {"max_edge": 1.0, "max_confidence": 35.0},
    "OVERRIDE": {"min_edge": 0.0, "min_confidence": 0.0},
}

JOSEPH_CONFIG = {
    "max_picks_per_slate": 10,
    "min_edge_threshold": 2.0,
    "parlay_max_legs": 6,
    "parlay_min_legs": 2,
    "default_entry_fee": 10.0,
    "commentary_style": "emphatic",
    "enable_overrides": True,
    "enable_ambient": True,
    "rant_min_fragments": 3,
    "rant_max_fragments": 5,
}

# ═══════════════════════════════════════════════════════════════
# E) CONSTANTS — Dawg Factor, Verdict Emojis, Ticket Names
# ═══════════════════════════════════════════════════════════════

DAWG_FACTOR_TABLE = {
    # ── Motivation / Narrative ──────────────────────────────────
    "revenge_game":          +2.5,
    "contract_year":         +1.5,
    "nationally_televised":  +1.0,
    "rivalry":               +0.5,
    "playoff_implications":  +0.5,
    "elimination_game":      +3.0,   # Win-or-go-home games
    "clinch_scenario":       +1.5,   # Playing to clinch a playoff spot
    "milestone_watch":       +1.0,   # Player near career milestone
    # ── Playoff-Specific ────────────────────────────────────────
    "playoff_game":          +2.0,   # Any playoff game (heightened stakes)
    "game_seven":            +4.0,   # Game 7 — winner-take-all
    "series_clinch":         +2.5,   # Chance to close out a series
    "facing_elimination":    +3.5,   # Down 3-2 or 3-1, must win
    "conf_finals":           +2.0,   # Conference Finals stage
    "nba_finals":            +3.0,   # The Finals — biggest stage
    "playoff_home_crowd":    +1.5,   # Playoff home-court energy
    "playoff_road_hostile":  -1.0,   # Hostile road environment
    "series_momentum":       +1.5,   # Won last 2 in series
    "series_deficit":        -1.0,   # Down in series, pressure mounts
    "playoff_rest_edge":     +1.5,   # Extra rest between rounds
    "playoff_fatigue":       -2.0,   # Deep run, heavy minutes toll
    "closeout_superstar":    +2.5,   # Superstar in closeout game (historically elite)
    "playoff_revenge":       +3.0,   # Last year's playoff elimination rematch
    # ── Pace / Tempo ────────────────────────────────────────────
    "pace_up":               +0.5,
    "pace_down":             -0.5,
    # ── Fatigue / Rest ──────────────────────────────────────────
    "back_to_back":          -1.5,
    "altitude":              -1.0,
    "blowout_risk":          -2.0,
    "trap_game":             -3.0,
    "three_in_four_nights":  -2.0,   # 3 games in 4 nights
    "well_rested":           +1.0,   # 3+ days rest
    # ── Form / Momentum ────────────────────────────────────────
    "trending_up":           +1.5,   # Recent hot streak
    "trending_down":         -1.5,   # Recent cold streak
    "clutch_performer":      +1.0,   # Proven in close games
    # ── Matchup Context ─────────────────────────────────────────
    "market_high_total":     +1.0,   # Vegas says high-scoring game
    "market_low_total":      -1.0,   # Vegas says low-scoring game
    "opp_top5_defense":      -1.5,   # Facing an elite defense
    "opp_bottom5_defense":   +1.5,   # Facing a bad defense
    "missing_key_teammate":  -1.0,   # Key teammate out (usage shift)
    "starter_returning":     -0.5,   # Key player back = fewer touches
    # ── Line Type / Market Intelligence ─────────────────────────
    "goblin_line":           +1.5,   # Easier alternate line — higher hit probability
    "demon_line":            -1.5,   # Harder alternate line — lower hit probability
    "qeg_pick":              +2.0,   # Quantum Edge Goblin: verified high-edge play
    "opportunity_boost":     +1.5,   # Teammate injury creates usage surge
    "line_moving_up":        -0.5,   # Line rising — books pricing OVER harder
    "line_moving_down":      +0.5,   # Line dropping — easier to hit OVER
}

VERDICT_EMOJIS = {
    "LOCK": "\U0001f512",
    "SMASH": "\U0001f525",
    "LEAN": "\u2705",
    "FADE": "\u26a0\ufe0f",
    "STAY_AWAY": "\U0001f6ab",
}

TICKET_NAMES = {
    2: "POWER PLAY",
    3: "TRIPLE THREAT",
    4: "THE QUAD",
    5: "HIGH FIVE",
    6: "THE FULL SEND",
}

# ── Market Total Thresholds (from Odds API consensus) ──────────────────────────
MARKET_HIGH_TOTAL_THRESHOLD = 228.0
MARKET_LOW_TOTAL_THRESHOLD  = 212.0
MARKET_CONSENSUS_MIN_BOOKS  = 5

# ═══════════════════════════════════════════════════════════════
# Stat type → DB column key mapping (single source of truth)
# ═══════════════════════════════════════════════════════════════

_STAT_DB_KEY_MAP = {
    "points": "PTS", "rebounds": "REB", "assists": "AST",
    "steals": "STL", "blocks": "BLK", "threes": "FG3M",
    "fg3m": "FG3M", "turnovers": "TOV",
    "personal_fouls": "PF", "fouls": "PF", "pf": "PF",
    "minutes": "MIN", "min": "MIN",
    "ftm": "FTM", "free_throws_made": "FTM",
    "fta": "FTA", "free_throws_attempted": "FTA",
    "fgm": "FGM", "field_goals_made": "FGM",
    "fga": "FGA", "field_goals_attempted": "FGA",
    "offensive_rebounds": "OREB", "oreb": "OREB",
    "defensive_rebounds": "DREB", "dreb": "DREB",
}

# ═══════════════════════════════════════════════════════════════
# Ask-Joseph question-answering constants
# ═══════════════════════════════════════════════════════════════

_ASK_STAT_KEYWORDS = {
    "points": "points", "pts": "points", "scoring": "points",
    "rebounds": "rebounds", "boards": "rebounds", "reb": "rebounds",
    "assists": "assists", "dimes": "assists", "ast": "assists",
    "threes": "three_pointers_made", "3s": "three_pointers_made",
    "steals": "steals", "blocks": "blocks",
    "turnovers": "turnovers", "fantasy": "fantasy",
    "pra": "pts_reb_ast", "combos": "pts_reb_ast",
    "double": "double_double",
}

_ASK_TEAM_ALIASES = {
    "lakers": "lal", "celtics": "bos", "warriors": "gsw",
    "nuggets": "den", "bucks": "mil", "sixers": "phi",
    "76ers": "phi", "heat": "mia", "suns": "phx",
    "knicks": "nyk", "nets": "bkn", "bulls": "chi",
    "cavs": "cle", "cavaliers": "cle", "hawks": "atl",
    "raptors": "tor", "mavericks": "dal", "mavs": "dal",
    "rockets": "hou", "timberwolves": "min", "wolves": "min",
    "thunder": "okc", "pelicans": "nop", "pels": "nop",
    "spurs": "sas", "jazz": "uta", "blazers": "por",
    "trail blazers": "por", "pacers": "ind", "kings": "sac",
    "magic": "orl", "pistons": "det", "hornets": "cha",
    "grizzlies": "mem", "clippers": "lac", "wizards": "was",
}

_ASK_PERSONALITY_MAP = {
    "goat": (
        "The GOAT? Let me tell you something — it's Michael Jeffrey Jordan. "
        "Six rings. Six Finals MVPs. ZERO Game 7s in the Finals. "
        "You can talk about LeBron's longevity, Kobe's mentality, "
        "Kareem's sky hook — but MJ is the STANDARD. "
        "And I, Joseph M. Smith, will FIGHT anyone who disagrees!"
    ),
    "best player": (
        "Right NOW? It's a two-man race between Nikola Jokic and "
        "Luka Doncic. Jokic does things with the basketball that "
        "shouldn't be POSSIBLE for a man his size. Luka is a "
        "generational TALENT. But don't sleep on Shai Gilgeous-Alexander — "
        "that man is ascending to SUPERSTARDOM!"
    ),
    "best team": (
        "The BEST team? That changes game to game — but I'll tell you this: "
        "the team with the best DEFENSE will win in the playoffs. "
        "Every. Single. Time. Offense gets you regular season wins. "
        "DEFENSE gets you RINGS!"
    ),
    "mvp": (
        "MVP is about NARRATIVE as much as performance. "
        "You need the stats, the wins, AND the story. "
        "That's why I analyze the DATA and not just the highlights. "
        "Check the Neural Analysis and I'll show you who the REAL MVP-caliber players are tonight!"
    ),
    "favorite team": (
        "Joseph M. Smith doesn't have FAVORITES — I have ANALYSIS. "
        "I go where the DATA takes me. Tonight, my favorite team is "
        "whoever has the most SMASH plays on the board. "
        "Run the analysis and I'll TELL you who that is!"
    ),
    "favorite player": (
        "I don't play FAVORITES with players — I play favorites with NUMBERS. "
        "My favorite player tonight is whoever has the best edge in the analysis. "
        "That's the beauty of being data-driven — NO BIAS, just FACTS!"
    ),
    "hello": (
        "What's up! Joseph M. Smith here, LIVE from The Studio! "
        "I've got game logs, shot charts, matchup data, and a FIRE personality. "
        "Ask me anything — I'm ready to WORK!"
    ),
    "who are you": (
        "I'm Joseph M. Smith — the SUPREME NBA analyst. "
        "I combine machine-learning models with my INSTINCT to deliver "
        "the best picks in the game. I've got data, I've got personality, "
        "and I've got RECEIPTS. Ask me about any player, any game, "
        "or my track record and I'll DELIVER!"
    ),
    "thank": (
        "You're WELCOME! That's what Joseph M. Smith is here for — "
        "to give you the REAL analysis that nobody else will. "
        "Keep asking questions and I'll keep delivering the GOODS!"
    ),
    "love you": (
        "I appreciate the love! But you know what REALLY shows love? "
        "Following my SMASH plays and cashing tickets! "
        "Let's make MONEY together!"
    ),
    "you suck": (
        "EXCUSE ME?! Joseph M. Smith has been doing this since BEFORE "
        "analytics was cool! My track record SPEAKS for itself. "
        "The game logs don't lie. The splits don't lie. "
        "And Joseph M. Smith DOESN'T lie! Check the receipts!"
    ),
    "funny": (
        "I'm not here to be FUNNY — I'm here to be RIGHT! "
        "But if making you money HAPPENS to make you laugh, "
        "then consider me a COMEDIAN and an ANALYST!"
    ),
    "playoff": (
        "PLAYOFF basketball is a DIFFERENT sport! The intensity goes up TEN NOTCHES. "
        "Stars play 40+ minutes, rotations SHRINK to 7-8 guys, "
        "defenses are LOCKED IN on the scouting report, and only the REAL ones survive. "
        "Role players disappear. Superstars FEAST. The refs swallow their whistles in the fourth. "
        "That's why my playoff analysis factors in postseason history, series fatigue, "
        "clutch splits, and ELIMINATION-game performance. Regular season numbers mean NOTHING now!"
    ),
    "game 7": (
        "GAME SEVEN! The two most beautiful words in ALL of sports! "
        "Winner goes home happy, loser goes home for the SUMMER. "
        "Every possession is LIFE or DEATH. Stars either become LEGENDS or GHOSTS. "
        "I factor in Game 7 history, elimination-game shooting splits, and the PRESSURE cooker effect. "
        "Some players SHRINK. Some players GROW. Joseph M. Smith knows the DIFFERENCE!"
    ),
    "series": (
        "Series basketball is CHESS, not checkers! Teams make adjustments game to game — "
        "the coaching matters MORE, the film study matters MORE, and matchup hunting becomes an ART. "
        "I track how players perform as a series DEEPENS. Some guys get BETTER with more games "
        "because they figure out the defense. Others get WORSE because the defense figures THEM out. "
        "That's the kind of analysis only Joseph M. Smith provides!"
    ),
    "elimination": (
        "ELIMINATION GAME! This is where you find out what a player is MADE of! "
        "Historically, SUPERSTARS elevate — LeBron, Jordan, Kobe, Duncan — they ALL turned it up "
        "when their season was on the line. But role players? They VANISH. "
        "My model adjusts for elimination-game history and I'm telling you — "
        "TRUST the stars. FADE the role players. That's the playoff FORMULA!"
    ),
    "finals": (
        "The NBA FINALS! The BIGGEST stage in basketball! "
        "Only SIXTEEN teams make the playoffs. Only TWO make the Finals. "
        "The pressure is IMMENSE. The minutes are HEAVY. The defense is SUFFOCATING. "
        "I adjust for Finals-level intensity — tighter rotations, slower pace, "
        "and the fact that EVERY player on that court is playing for their LEGACY!"
    ),
    "trade": (
        "Trades change EVERYTHING. New team, new role, new matchups. "
        "When a trade happens, I recalculate from SCRATCH. "
        "You can't just plug old numbers into a new situation — "
        "that's AMATEUR hour. Joseph M. Smith adjusts for CONTEXT!"
    ),
    "draft": (
        "The draft is where FUTURES are made. I look at college translations, "
        "physical profiles, and historical comps. "
        "But tonight we're focused on the CURRENT slate. "
        "Ask me about any player on tonight's games!"
    ),
    "over under": (
        "Over/Under is where the MONEY is! I analyze usage rates, pace, "
        "defensive matchups, and recent trends to find the props that are "
        "MISPRICED. My Neural Analysis crunches ALL of that for you. "
        "Run it and I'll show you where the value is!"
    ),
    "spread": (
        "Spreads are about matchups, pace, and home-court advantage. "
        "I factor in defensive ratings, offensive efficiency, and "
        "recent form to give you the REAL number. "
        "Ask me about a specific game and I'll break it down!"
    ),
}

# ═══════════════════════════════════════════════════════════════
# Mapping from raw stat keys to STAT_BODY_TEMPLATES categories
# ═══════════════════════════════════════════════════════════════

_STAT_CATEGORY_MAP = {
    # Core stats
    "points": "points", "pts": "points", "scoring": "points",
    "rebounds": "rebounds", "reb": "rebounds", "boards": "rebounds",
    "assists": "assists", "ast": "assists", "dimes": "assists",
    "steals": "steals", "stl": "steals",
    "blocks": "blocks", "blk": "blocks",
    "threes": "threes", "fg3m": "threes", "three_pointers_made": "threes",
    "3pm": "threes", "3s": "threes",
    "turnovers": "turnovers", "tov": "turnovers",
    # Fouls
    "personal_fouls": "fouls", "fouls": "fouls", "pf": "fouls",
    # Minutes
    "minutes": "minutes", "min": "minutes",
    # Free throws / field goals
    "ftm": "free_throws", "free_throws_made": "free_throws",
    "fta": "free_throws", "free_throws_attempted": "free_throws",
    "fgm": "field_goals", "field_goals_made": "field_goals",
    "fga": "field_goals", "field_goals_attempted": "field_goals",
    # Sub-rebounds
    "offensive_rebounds": "rebounds", "oreb": "rebounds",
    "defensive_rebounds": "rebounds", "dreb": "rebounds",
    # Combo stats
    "points_rebounds": "combo", "pts_reb": "combo",
    "points_assists": "combo", "pts_ast": "combo",
    "rebounds_assists": "combo", "reb_ast": "combo",
    "points_rebounds_assists": "combo", "pts_reb_ast": "combo", "pra": "combo",
    "blocks_steals": "combo", "blk_stl": "combo",
    # Double/Triple doubles
    "double_double": "double_double",
    "triple_double": "double_double",
    # Fantasy
    "fantasy": "fantasy", "fantasy_points": "fantasy",
    "fantasy_score_pp": "fantasy", "fantasy_score_dk": "fantasy",
    "fantasy_score_ud": "fantasy",
}


