import sqlite3
conn = sqlite3.connect('db/smartpicks.db')

# Check for prop_results / bet_results / picks / analysis tables
for tbl in ['prop_results', 'bet_results', 'analysis_results', 'picks', 'prop_picks', 'users', 'sessions']:
    try:
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
        count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"{tbl} ({count} rows): {cols}")
    except Exception as e:
        print(f"{tbl}: NOT FOUND")

# Sample Team_Game_Stats
print("\nTeam_Game_Stats cols:", [c[1] for c in conn.execute("PRAGMA table_info(Team_Game_Stats)").fetchall()])
print("Team_Roster cols:", [c[1] for c in conn.execute("PRAGMA table_info(Team_Roster)").fetchall()])
print("Standings cols:", [c[1] for c in conn.execute("PRAGMA table_info(Standings)").fetchall()])
conn.close()
