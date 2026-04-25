import sqlite3
# Checkpoint WAL into main DB so all data is in the single file
conn = sqlite3.connect("db/smartai_nba.db")
result = conn.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
print("WAL checkpoint result (busy, log, checkpointed):", result)
conn.close()
print("Done — smartai_nba.db is now fully checkpointed")
