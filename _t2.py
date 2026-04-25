import sqlite3
conn = sqlite3.connect('db/smartpicks.db')

for tbl in ['Player_Game_Logs', 'Players', 'League_Dash_Player_Stats', 'Games', 'Defense_Vs_Position', 'Player_Bio', 'Player_Clutch_Stats', 'Player_Estimated_Metrics', 'Player_Hustle_Stats']:
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
    count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"\n{tbl} ({count} rows):")
    print("  cols:", cols)

# Sample game_logs
print("\n--- Player_Game_Logs sample row ---")
cols = [c[1] for c in conn.execute("PRAGMA table_info(Player_Game_Logs)").fetchall()]
row = conn.execute("SELECT * FROM Player_Game_Logs LIMIT 1").fetchone()
if row:
    for k, v in zip(cols, row):
        print(f"  {k}: {v}")

conn.close()
