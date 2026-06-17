from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    # Let's list all tables and query each to find where 'ESNEYDER' appears
    res = db.session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
    tables = [r[0] for r in res]
    print(f"Total tables: {len(tables)}")
    for t in tables:
        try:
            # check columns
            cols_res = db.session.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}'")).fetchall()
            cols = [c[0] for c in cols_res]
            for col in cols:
                sql = f"SELECT COUNT(*) FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%ESNEYDER%'"
                cnt = db.session.execute(text(sql)).scalar()
                if cnt > 0:
                    print(f"MATCH FOUND: Table={t}, Col={col} -> {cnt} rows")
                    row_sql = f"SELECT * FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%ESNEYDER%' LIMIT 5"
                    rows = db.session.execute(text(row_sql)).fetchall()
                    for r in rows:
                        print("  Row:", dict(r._mapping))
        except Exception as e:
            print(f"Error on {t}: {e}")
