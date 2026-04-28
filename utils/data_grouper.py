# ============================================================
# FILE: utils/data_grouper.py
# PURPOSE: Aggregate raw platform prop data by player so each
#          player becomes a single "Trading Card" entity with
#          all of their available bets compiled together.
#
# USAGE:
#   from utils.data_grouper import group_props_by_player
#   grouped = group_props_by_player(analysis_results, players_data, todays_games)
#   # grouped["LeBron James"] == {"vitals": {...}, "props": [prop1, prop2, ...]}
# ============================================================

import html as _html
import logging as _logging

_logger = _logging.getLogger(__name__)

# Tier ranking for intra-player prop sorting (lower = better tier first)
_TIER_RANK = {"Platinum": 0, "Gold": 1, "Silver": 2, "Bronze": 3}


def group_props_by_player(
    analysis_results: list,
    players_data: list | None = None,
    todays_games: list | None = None,
) -> dict:
    """Group analysis results by player name.

    Each player key maps to a dict containing:
    - ``vitals``: enriched player data from
      :func:`data.player_profile_service.enrich_player_data`
    - ``props``: list of every prop/analysis-result dict for that player

    Parameters
    ----------
    analysis_results : list[dict]
        Flat list of prop analysis result dicts. Each must contain
        at least ``"player_name"``.
    players_data : list[dict] | None
        Full players dataset for enrichment.
    todays_games : list[dict] | None
        Today's games for opponent resolution.

    Returns
    -------
    dict[str, dict]
        Mapping of ``player_name`` → ``{"vitals": dict, "props": list}``.
    """
    if not analysis_results:
        return {}

    try:
        from data.player_profile_service import enrich_player_data
    except ImportError:
        def enrich_player_data(name, *_a, **_kw):
            return {
                "player_name": _html.escape(str(name)),
                "headshot_url": "",
                "position": "N/A",
                "team": "N/A",
                "team_logo_url": "",
                "next_opponent": "TBD",
                "season_stats": {"ppg": 0.0, "rpg": 0.0, "apg": 0.0, "avg_minutes": 0.0},
            }

    aggregated: dict[str, dict] = {}

    for result in analysis_results:
        if not isinstance(result, dict):
            continue
        name = str(result.get("player_name", "")).strip()
        if not name:
            continue

        if name not in aggregated:
            vitals = enrich_player_data(
                name,
                players_data or [],
                todays_games or [],
            )
            aggregated[name] = {"vitals": vitals, "props": []}

        aggregated[name]["props"].append(result)

    # Backfill team into vitals from props when enrich_player_data didn't resolve it.
    # This guards against the player_profile_service fallback returning "N/A" for team,
    # which is truthy and would otherwise prevent downstream code from reading
    # player_team/team off the prop rows.
    for data in aggregated.values():
        v_team = (data["vitals"].get("team") or "").strip()
        if not v_team or v_team.upper() == "N/A":
            for p in data["props"]:
                t = (p.get("player_team") or p.get("team") or "").strip()
                if t and t.upper() not in ("N/A", ""):
                    data["vitals"]["team"] = t
                    break

    # Sort props within each player: highest confidence / best tier first
    for data in aggregated.values():
        data["props"].sort(
            key=lambda p: (
                _TIER_RANK.get(p.get("tier", "Bronze"), 3),
                -(p.get("confidence_score", 0) or 0),
            ),
        )

    return aggregated
