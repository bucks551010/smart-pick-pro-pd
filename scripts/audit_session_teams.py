"""Check teams distribution within the latest session's analysis_results."""
import os
import json
import sys

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:PFGBNTCQyoVyUegKuTeuPPJujxuJAXGL@crossover.proxy.rlwy.net:29694/railway",
)

import psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("SELECT session_id, analysis_timestamp, analysis_results_json FROM analysis_sessions ORDER BY session_id DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print("No session found")
    sys.exit(1)

session_id, ts, results_json = row
results = json.loads(results_json) if results_json else []
print(f"Session {session_id} at {ts}: {len(results)} picks")

tonight_teams = {"DET", "ORL", "OKC", "PHX", "MIN", "DEN"}

team_counts = {}
non_playing = []
for r in results:
    team = r.get("team", "") or r.get("player_team", "")
    team_counts[team] = team_counts.get(team, 0) + 1
    if team not in tonight_teams:
        non_playing.append(r)

print("\nTeam breakdown in session:")
for t, c in sorted(team_counts.items(), key=lambda x: -x[1]):
    flag = "✅" if t in tonight_teams else "❌"
    print(f"  {flag} {t}: {c}")

print(f"\nNon-playing-team picks in session: {len(non_playing)}")
for r in non_playing[:20]:
    print(f"  {r.get('player_name','?')} team={r.get('team','')} opp={r.get('opponent','')} {r.get('stat_type','')} tier={r.get('tier','')} conf={r.get('confidence_score','')}")

# Check if any game-type (DET @ ORL Total) synthetic props exist
synthetic = [r for r in results if "@" in r.get("player_name", "")]
print(f"\nSynthetic game-total props in session: {len(synthetic)}")
for r in synthetic[:5]:
    print(f"  {r.get('player_name','?')} team={r.get('team','')} opp={r.get('opponent','')} {r.get('stat_type','')} tier={r.get('tier','')} conf={r.get('confidence_score','')}")

conn.close()
