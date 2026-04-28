import sqlite3
conn = sqlite3.connect('db/smartpicks.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('TABLES:', len(tables))
for (t,) in tables:
    count = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'  {t}: {count} rows')
conn.close()
