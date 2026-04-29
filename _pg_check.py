import sys
import os
sys.path.insert(0, '.')

PG_URL = os.environ.get("DATABASE_URL", "")
if not PG_URL:
    raise SystemExit("DATABASE_URL environment variable is not set.")

try:
    import psycopg2
    conn = psycopg2.connect(PG_URL)
    cur = conn.cursor()
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    tables = [r[0] for r in cur.fetchall()]
    print('Tables:', tables)
    for t in ['analysis_sessions', 'all_analysis_picks', 'bets', 'slate_cache', 'worker_state']:
        if t in tables:
            cur.execute(f'SELECT COUNT(*) FROM {t}')
            cnt = cur.fetchone()[0]
            if cnt > 0 and t == 'all_analysis_picks':
                cur.execute(f"SELECT pick_date, COUNT(*) FROM {t} GROUP BY pick_date ORDER BY pick_date DESC LIMIT 5")
                dates = cur.fetchall()
                print(f'  {t}: {cnt} rows | by date: {dates}')
            elif cnt > 0 and t == 'analysis_sessions':
                cur.execute(f"SELECT session_id, analysis_timestamp, prop_count FROM {t} ORDER BY session_id DESC LIMIT 3")
                rows = cur.fetchall()
                print(f'  {t}: {cnt} rows | latest: {rows}')
            else:
                print(f'  {t}: {cnt} rows')
        else:
            print(f'  {t}: NOT IN DB')
    conn.close()
except ImportError:
    print('psycopg2 not installed — trying pg8000')
    import pg8000.native
    conn = pg8000.native.Connection(
        user='postgres',
        password='PFGBNTCQyoVyUegKuTeuPPJujxuJAXGL',
        host='crossover.proxy.rlwy.net',
        port=29694,
        database='railway',
    )
    tables = [r[0] for r in conn.run("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    print('Tables:', tables)
    for t in ['analysis_sessions', 'all_analysis_picks', 'bets']:
        if t in tables:
            cnt = conn.run(f'SELECT COUNT(*) FROM {t}')[0][0]
            print(f'  {t}: {cnt} rows')
        else:
            print(f'  {t}: NOT IN DB')
except Exception as e:
    print(f'ERROR: {e}')
