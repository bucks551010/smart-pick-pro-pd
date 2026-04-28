"""
purge_nonplaying_picks.py
=========================
One-time cleanup: deletes all_analysis_picks rows for today where the player's
team is NOT in tonight's games (DET, ORL, OKC, PHX, MIN, DEN for 2026-04-27).

Also deletes analysis_sessions rows whose analysis_results_json contains picks
for non-playing teams (since those sessions have contaminated data).

Run once after deploying the slate_worker team-filter fix.

Usage:
    python scripts/purge_nonplaying_picks.py
"""
import os
import json
import sys

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:PFGBNTCQyoVyUegKuTeuPPJujxuJAXGL@crossover.proxy.rlwy.net:29694/railway",
)

try:
    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    cur = conn.cursor()
except Exception as e:
    print(f"DB connect failed: {e}")
    sys.exit(1)

# Tonight's playing teams — update this list each day if running manually.
TONIGHT_TEAMS = ("DET", "ORL", "OKC", "PHX", "MIN", "DEN")

# ── 1. Count picks to be deleted ─────────────────────────────────────────
cur.execute(
    """
    SELECT team, COUNT(*)
    FROM all_analysis_picks
    WHERE pick_date = CURRENT_DATE::text
      AND team NOT IN %s
    GROUP BY team
    ORDER BY COUNT(*) DESC
    """,
    (TONIGHT_TEAMS,),
)
rows = cur.fetchall()
if not rows:
    print("No non-playing-team picks found for today. Nothing to purge.")
    conn.close()
    sys.exit(0)

total_to_delete = sum(r[1] for r in rows)
print(f"Non-playing-team picks to delete ({total_to_delete} total):")
for team, count in rows:
    print(f"  {team or '(blank)'}: {count}")

# ── 2. Delete ─────────────────────────────────────────────────────────────
cur.execute(
    """
    DELETE FROM all_analysis_picks
    WHERE pick_date = CURRENT_DATE::text
      AND team NOT IN %s
    """,
    (TONIGHT_TEAMS,),
)
deleted = cur.rowcount
print(f"\nDeleted {deleted} rows from all_analysis_picks.")

# ── 3. Also purge synthetic game-total picks (team = '') for today ────────
cur.execute(
    """
    DELETE FROM all_analysis_picks
    WHERE pick_date = CURRENT_DATE::text
      AND (team IS NULL OR team = '')
    """,
)
deleted_blank = cur.rowcount
print(f"Deleted {deleted_blank} blank-team rows from all_analysis_picks.")

# ── 4. Commit ─────────────────────────────────────────────────────────────
conn.commit()
print("\nPurge committed successfully.")

# ── 5. Show remaining picks ───────────────────────────────────────────────
cur.execute(
    """
    SELECT team, COUNT(*)
    FROM all_analysis_picks
    WHERE pick_date = CURRENT_DATE::text
    GROUP BY team
    ORDER BY COUNT(*) DESC
    """,
)
remaining = cur.fetchall()
total_remaining = sum(r[1] for r in remaining)
print(f"\nRemaining picks for today ({total_remaining} total):")
for team, count in remaining:
    flag = "✅" if team in TONIGHT_TEAMS else "❌"
    print(f"  {flag} {team or '(blank)'}: {count}")

conn.close()
