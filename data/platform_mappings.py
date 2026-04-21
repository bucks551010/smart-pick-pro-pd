# ============================================================
# FILE: data/platform_mappings.py
# PURPOSE: Platform-specific stat name mappings, fantasy scoring
#          formulas, and combo stat definitions for major sportsbooks.
# USAGE:
#   from data.platform_mappings import normalize_stat_type, COMBO_STATS
# ============================================================

# Standard library only


# ============================================================
# SECTION: Platform Stat Name Mappings
# Each platform uses different names for the same stats.
# These maps convert platform-native names to our internal keys.
# ============================================================

# Legacy PrizePicks stat type mappings (backward compat)
PRIZEPICKS_STAT_MAP = {
    "Points": "points",
    "Rebounds": "rebounds",
    "Assists": "assists",
    "3-Point Made": "threes",
    "3-Pointers Made": "threes",
    "Three Pointers Made": "threes",
    "3-PT Made": "threes",        # current PrizePicks API name (2025+)
    "3-Pt Made": "threes",
    "3PM": "threes",
    "Steals": "steals",
    "Blocks": "blocks",
    "Blocked Shots": "blocks",    # current PrizePicks API name (2025+)
    "Turnovers": "turnovers",
    "Pts+Rebs": "points_rebounds",
    "Pts+Asts": "points_assists",
    "Rebs+Asts": "rebounds_assists",
    "Pts+Rebs+Asts": "points_rebounds_assists",
    "Fantasy Score": "fantasy_score_pp",
    "Blks+Stls": "blocks_steals",
    "Free Throws Made": "ftm",
    "FG Attempted": "fga",
    "Field Goals Attempted": "fga",    # full-word form from some API versions
    "FG Made": "fgm",
    "Field Goals Made": "fgm",         # full-word form from some API versions
    "FT Attempted": "fta",
    "Free Throws Attempted": "fta",    # full-word form from some API versions
    "Double Double": "double_double",
    "Double-Double": "double_double",  # PrizePicks hyphen form
    "Triple Double": "triple_double",
    "Triple-Double": "triple_double",  # PrizePicks hyphen form
    "Minutes": "minutes",
    "Personal Fouls": "personal_fouls",
    "Offensive Rebounds": "offensive_rebounds",
    "Defensive Rebounds": "defensive_rebounds",
    # Space-separated combo variants (PrizePicks sometimes emits spaces around +)
    "Pts + Rebs": "points_rebounds",
    "Pts + Asts": "points_assists",
    "Rebs + Asts": "rebounds_assists",
    "Blks + Stls": "blocks_steals",
    # Singular abbreviation for PRA
    "Pts+Reb+Ast": "points_rebounds_assists",
    # "(Combo)" multi-leg variants — map to the same underlying stat so they
    # are analyzed identically to the single-stat version.
    "Points (Combo)": "points",
    "Rebounds (Combo)": "rebounds",
    "Assists (Combo)": "assists",
    "3-PT Made (Combo)": "threes",
}

# DraftKings Pick6 stat type mappings (also used for standard sportsbooks)
DRAFTKINGS_STAT_MAP = {
    "Points": "points",
    "Rebounds": "rebounds",
    "Assists": "assists",
    "Three Pointers Made": "threes",
    "3PM": "threes",
    "Steals": "steals",
    "Blocks": "blocks",
    "Turnovers": "turnovers",
    "Points + Rebounds": "points_rebounds",
    "Points + Assists": "points_assists",
    "Rebounds + Assists": "rebounds_assists",
    "Pts + Rebs + Asts": "points_rebounds_assists",
    "Double Double": "double_double",
    "Triple Double": "triple_double",
    "Fantasy Points": "fantasy_score_dk",
    "Free Throws Made": "ftm",
    "FTM": "ftm",
    "FG Attempted": "fga",
    "Field Goals Attempted": "fga",    # full-word form from some API versions
    "FGA": "fga",
    "FG Made": "fgm",
    "Field Goals Made": "fgm",         # full-word form from some API versions
    "FGM": "fgm",
    "FT Attempted": "fta",
    "Free Throws Attempted": "fta",    # full-word form from some API versions
    "FTA": "fta",
    "Minutes": "minutes",
    "Personal Fouls": "personal_fouls",
    "Offensive Rebounds": "offensive_rebounds",
    "Defensive Rebounds": "defensive_rebounds",
}

# Legacy Underdog Fantasy stat type mappings (backward compat)
UNDERDOG_STAT_MAP = {
    "Points": "points",
    "Total Points": "points",       # Underdog alternate label
    "Player Points": "points",
    "Rebounds": "rebounds",
    "Player Rebounds": "rebounds",  # Underdog alternate label
    "Assists": "assists",
    "Player Assists": "assists",    # Underdog alternate label
    "3-Pointers Made": "threes",
    "3s Made": "threes",
    "Steals": "steals",
    "Blocks": "blocks",
    "Turnovers": "turnovers",
    "Points + Rebounds": "points_rebounds",
    "Points + Assists": "points_assists",
    "Rebounds + Assists": "rebounds_assists",
    "Pts + Rebs + Asts": "points_rebounds_assists",
    "Points + Rebounds + Assists": "points_rebounds_assists",
    "Fantasy Points": "fantasy_score_ud",
    "Free Throws Made": "ftm",
    "FTM": "ftm",
    "FG Attempted": "fga",
    "Field Goals Attempted": "fga",
    "FGA": "fga",
    "FG Made": "fgm",
    "Field Goals Made": "fgm",
    "FGM": "fgm",
    "FT Attempted": "fta",
    "Free Throws Attempted": "fta",
    "FTA": "fta",
    "Double Double": "double_double",
    "Double Doubles": "double_double",  # Underdog plural form
    "Triple Double": "triple_double",
    "Triple Doubles": "triple_double",
    # Alternate labels that map to standard stats
    "Total Points": "points",
    "Player Points": "points",
    "Player Rebounds": "rebounds",
    "Player Assists": "assists",
    # Shooting attempts, quarter props, and novelty are intentionally omitted
    # so they are silently dropped by the VALID_STAT_TYPES filter.
    "Minutes": "minutes",
    "Personal Fouls": "personal_fouls",
    "Offensive Rebounds": "offensive_rebounds",
    "Defensive Rebounds": "defensive_rebounds",
    "Blocks + Steals": "blocks_steals",
    "Blks+Stls": "blocks_steals",
}

# Combined reverse-lookup: all platform names → internal key
# Used for auto-detection when platform is unknown
ALL_PLATFORM_STAT_NAMES = {}
for _map in (PRIZEPICKS_STAT_MAP, DRAFTKINGS_STAT_MAP, UNDERDOG_STAT_MAP):
    for _k, _v in _map.items():
        ALL_PLATFORM_STAT_NAMES[_k.lower()] = _v

# Reverse lookup: internal stat key → human-readable display name.
# Built from PrizePicks map (preferred display names) with fallbacks
# from DraftKings for any keys not already present.
_INTERNAL_TO_DISPLAY: dict[str, str] = {}
for _map in (PRIZEPICKS_STAT_MAP, DRAFTKINGS_STAT_MAP, UNDERDOG_STAT_MAP):
    for _display, _internal in _map.items():
        if _internal not in _INTERNAL_TO_DISPLAY:
            _INTERNAL_TO_DISPLAY[_internal] = _display

# ============================================================
# END SECTION: Platform Stat Name Mappings
# ============================================================


# ============================================================
# SECTION: Fantasy Scoring Formulas
# Different platforms score fantasy differently.
# ============================================================

FANTASY_SCORING = {
    "fantasy_score_pp": {   # PrizePicks
        "points": 1.0,
        "rebounds": 1.2,
        "assists": 1.5,
        "steals": 3.0,
        "blocks": 3.0,
        "turnovers": -1.0,
    },
    "fantasy_score_dk": {   # DraftKings
        "points": 1.0,
        "rebounds": 1.25,
        "assists": 1.5,
        "steals": 2.0,
        "blocks": 2.0,
        "turnovers": -0.5,
        "threes": 0.5,      # DK gives bonus for 3-pointers
    },
    "fantasy_score_ud": {   # Underdog Fantasy
        "points": 1.0,
        "rebounds": 1.2,
        "assists": 1.5,
        "steals": 3.0,
        "blocks": 3.0,
        "turnovers": -1.0,
    },
}

# ============================================================
# END SECTION: Fantasy Scoring Formulas
# ============================================================


# ============================================================
# SECTION: Combo Stat Definitions
# Maps internal combo stat keys to their component stats.
# ============================================================

COMBO_STATS = {
    "points_rebounds": ["points", "rebounds"],
    "points_assists": ["points", "assists"],
    "rebounds_assists": ["rebounds", "assists"],
    "points_rebounds_assists": ["points", "rebounds", "assists"],
    "blocks_steals": ["blocks", "steals"],
}

# All internal stat types that are combo/fantasy (not simple counters)
COMBO_AND_FANTASY_STAT_TYPES = frozenset(COMBO_STATS.keys()) | frozenset(FANTASY_SCORING.keys()) | {
    "double_double",
    "triple_double",
}

# ============================================================
# END SECTION: Combo Stat Definitions
# ============================================================


# ============================================================
# SECTION: Platform Detection & Normalization
# ============================================================

# Map platform names (lower-cased) to their stat dictionaries
_PLATFORM_MAPS = {
    "prizepicks": PRIZEPICKS_STAT_MAP,
    "underdog": UNDERDOG_STAT_MAP,
    "underdog fantasy": UNDERDOG_STAT_MAP,
    "draftkings": DRAFTKINGS_STAT_MAP,
    "draftkings pick6": DRAFTKINGS_STAT_MAP,
}


def normalize_stat_type(raw_stat_name, platform=None):
    """
    Convert a platform-native stat name to our internal stat key.

    Tries platform-specific map first, then falls back to the
    combined lookup across all platforms.

    Args:
        raw_stat_name (str): Stat name as it appears on the platform,
            e.g., "Pts+Rebs", "3PM", "Fantasy Points"
        platform (str, optional): Platform name for preferential lookup.
            e.g., "PrizePicks", "Underdog Fantasy", "DraftKings Pick6".

    Returns:
        str: Internal stat key (e.g., "points_rebounds"), or the
             lower-cased raw name if no match is found.

    Example:
        normalize_stat_type("Pts+Rebs", "PrizePicks") → "points_rebounds"
        normalize_stat_type("3PM", "DraftKings")       → "threes"
    """
    if not raw_stat_name:
        return ""

    # Try platform-specific map
    if platform:
        plat_key = platform.lower().replace(" ", "")
        plat_map = _PLATFORM_MAPS.get(plat_key, {})
        if raw_stat_name in plat_map:
            return plat_map[raw_stat_name]

    # Try combined lookup (case-insensitive)
    lower_name = raw_stat_name.strip().lower()
    if lower_name in ALL_PLATFORM_STAT_NAMES:
        return ALL_PLATFORM_STAT_NAMES[lower_name]

    # Return lowercased name as fallback (may already be internal key)
    return lower_name


def display_stat_name(internal_key: str) -> str:
    """Convert an internal stat key to a human-readable display name.

    Args:
        internal_key: Internal stat key (e.g., ``"personal_fouls"``,
            ``"points_rebounds_assists"``).

    Returns:
        Human-readable name (e.g., ``"Personal Fouls"``,
        ``"Pts+Rebs+Asts"``).  Falls back to title-casing with
        underscores replaced by spaces if no mapping exists.

    Example:
        display_stat_name("personal_fouls")  → "Personal Fouls"
        display_stat_name("threes")          → "3-Point Made"
        display_stat_name("points")          → "Points"
    """
    if not internal_key:
        return ""
    hit = _INTERNAL_TO_DISPLAY.get(internal_key)
    if hit:
        return hit
    # Fallback: title-case with underscores → spaces
    return internal_key.replace("_", " ").title()


def detect_platform_from_stat_names(stat_names):
    """
    Auto-detect the most likely platform from a list of stat names.

    Counts how many stat names match each platform's map and returns
    the platform with the highest hit count.

    Args:
        stat_names (list of str): Raw stat names from a prop upload.

    Returns:
        str or None: Platform name (e.g., "PrizePicks", "DraftKings Pick6"), or
                     None if no platform matches confidently.

    Example:
        detect_platform_from_stat_names(["Pts+Rebs", "Blks+Stls"])
        → "PrizePicks"  # legacy stat names still detected
    """
    scores = {"PrizePicks": 0, "Underdog Fantasy": 0, "DraftKings Pick6": 0}
    for name in stat_names:
        for plat, stat_map in _PLATFORM_MAPS.items():
            if name in stat_map:
                if plat == "prizepicks":
                    scores["PrizePicks"] += 1
                elif plat in ("draftkings", "draftkings pick6"):
                    scores["DraftKings Pick6"] += 1
                elif plat in ("underdog", "underdog fantasy"):
                    scores["Underdog Fantasy"] += 1

    best_platform = max(scores, key=scores.get)
    return best_platform if scores[best_platform] > 0 else None


def is_combo_stat(stat_type):
    """
    Return True if the stat type is a combo (multi-stat) prop.

    Args:
        stat_type (str): Internal stat key

    Returns:
        bool: True if combo stat (e.g., points_rebounds, PRA)
    """
    return stat_type in COMBO_STATS


def is_fantasy_stat(stat_type):
    """
    Return True if the stat type is a fantasy score prop.

    Args:
        stat_type (str): Internal stat key

    Returns:
        bool: True if fantasy score stat (e.g., fantasy_score_pp)
    """
    return stat_type in FANTASY_SCORING


def get_combo_components(stat_type):
    """
    Return the component stats for a combo stat type.

    Args:
        stat_type (str): Internal stat key, e.g., "points_rebounds"

    Returns:
        list of str: Component stat keys, or empty list if not a combo.

    Example:
        get_combo_components("points_rebounds") → ["points", "rebounds"]
    """
    return COMBO_STATS.get(stat_type, [])


def calculate_fantasy_score(stat_values, platform_stat_type):
    """
    Calculate a fantasy score from individual stat values.

    Args:
        stat_values (dict): Stat key → value, e.g.
            {"points": 25, "rebounds": 8, "assists": 5, ...}
        platform_stat_type (str): Internal fantasy stat key,
            e.g., "fantasy_score_pp", "fantasy_score_dk"

    Returns:
        float: Calculated fantasy score, or 0.0 if formula not found.

    Example:
        calculate_fantasy_score(
            {"points": 25, "rebounds": 8, "assists": 5,
             "steals": 2, "blocks": 1, "turnovers": 2},
            "fantasy_score_pp"
        ) → 56.5
    """
    formula = FANTASY_SCORING.get(platform_stat_type, {})
    if not formula:
        return 0.0

    score = 0.0
    for stat, multiplier in formula.items():
        score += stat_values.get(stat, 0.0) * multiplier
    return round(score, 2)

# ============================================================
# END SECTION: Platform Detection & Normalization
# ============================================================
