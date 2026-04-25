import sqlite3
conn = sqlite3.connect('db/smartpicks.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for (t,) in tables:
    cols = conn.execute(f'PRAGMA table_info({t})').fetchall()
    count = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t} ({count} rows): {[c[1] for c in cols]}')
conn.close()
