"""Quick audit of tier distribution, team distribution, and session data."""
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
    cur = conn.cursor()
except Exception as e:
    print(f"DB connect failed: {e}")
    sys.exit(1)

# Tier distribution
cur.execute("SELECT tier, COUNT(*) FROM all_analysis_picks WHERE pick_date = CURRENT_DATE::text GROUP BY tier ORDER BY COUNT(*) DESC")
rows = cur.fetchall()
print("=== Tier Distribution (all_analysis_picks today) ===")
for r in rows:
    print(f"  {r[0]}: {r[1]}")

# Teams distribution
cur.execute("SELECT team, COUNT(*) FROM all_analysis_picks WHERE pick_date = CURRENT_DATE::text GROUP BY team ORDER BY COUNT(*) DESC")
rows = cur.fetchall()
print()
print("=== Team Distribution (all_analysis_picks today) ===")
for r in rows:
    print(f"  {r[0]}: {r[1]}")

# Non-playing teams (not in DET/ORL/OKC/PHX/MIN/DEN)
tonight_teams = {"DET", "ORL", "OKC", "PHX", "MIN", "DEN"}
cur.execute("SELECT player_name, team, stat_type, tier FROM all_analysis_picks WHERE pick_date = CURRENT_DATE::text ORDER BY player_name")
all_picks = cur.fetchall()
bad_picks = [r for r in all_picks if r[1] not in tonight_teams]
print()
print(f"=== Non-playing-team picks: {len(bad_picks)} (teams not in DET/ORL/OKC/PHX/MIN/DEN) ===")
for r in bad_picks[:20]:
    print(f"  {r[0]} team={r[1]} stat={r[2]} tier={r[3]}")

# Latest session
cur.execute("SELECT session_id, analysis_timestamp, selected_picks_json, analysis_results_json FROM analysis_sessions ORDER BY session_id DESC LIMIT 1")
row = cur.fetchone()
if row:
    selected = json.loads(row[2]) if row[2] else []
    results = json.loads(row[3]) if row[3] else []
    print()
    print(f"=== Session {row[0]} ({row[1]}) selected_picks={len(selected)} analysis_results={len(results)} ===")
    # Tier breakdown in session results
    tier_counts = {}
    for p in results:
        t = p.get("tier", "unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1
    print("  Session tier breakdown:")
    for t, c in sorted(tier_counts.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")
    # Show selected picks
    print(f"  Selected picks:")
    for p in selected[:10]:
        print(f"    {p.get('player_name','?')} {p.get('team','?')} {p.get('stat_type','?')} tier={p.get('tier','?')} conf={p.get('confidence_score','?')}")
    # Show top 10 by confidence in results
    top10 = sorted(results, key=lambda r: r.get("confidence_score", 0), reverse=True)[:10]
    print("  Top 10 by confidence_score in analysis_results:")
    for p in top10:
        print(f"    {p.get('player_name','?')} {p.get('team','?')} opp={p.get('opponent','')} {p.get('stat_type','?')} tier={p.get('tier','?')} conf={p.get('confidence_score','?')} edge={p.get('edge_percentage','?')}")

conn.close()
print("\nAudit complete.")
