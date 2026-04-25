import sqlite3
conn = sqlite3.connect("db/smartai_nba.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for row in tables:
    t = row[0]
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
        cols = [c[1] for c in conn.execute("PRAGMA table_info(" + t + ")").fetchall()]
        print(f"{t} ({cnt} rows): {cols}")
        if cnt > 0 and any(k in t.lower() for k in ["bet", "analysis", "pick", "prop", "session", "joseph"]):
            rows = conn.execute("SELECT * FROM " + t + " ORDER BY rowid DESC LIMIT 2").fetchall()
            for r in rows:
                d = dict(zip(cols, r))
                print("  >>", {k: str(v)[:60] for k,v in d.items()})
    except Exception as e:
        print(f"{t}: ERR {e}")
conn.close()
