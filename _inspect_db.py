import sqlite3
conn = sqlite3.connect("db/smartpicks.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for row in tables:
    t = row[0]
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        # Sample latest rows for relevant tables
        if any(k in t.lower() for k in ["bet", "analysis", "pick", "prop", "session"]):
            rows = conn.execute("SELECT * FROM " + t + " ORDER BY rowid DESC LIMIT 3").fetchall()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(" + t + ")").fetchall()]
            print(f"\n=== {t} ({cnt} rows) ===")
            print("cols:", cols)
            for r in rows:
                print(dict(zip(cols, r)))
        else:
            print(f"{t}: {cnt} rows")
    except Exception as e:
        print(f"{t}: ERR {e}")
conn.close()
