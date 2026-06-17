from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    tables_res = db.session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
    tables = [r[0] for r in tables_res]
    
    for t in tables:
        try:
            cols_res = db.session.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}'")).fetchall()
            cols = [c[0] for c in cols_res]
            for col in cols:
                sql = f"SELECT COUNT(*) FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%MARIN%'"
                cnt = db.session.execute(text(sql)).scalar()
                if cnt > 0:
                    print(f"Table '{t}', Column '{col}' has {cnt} matches for MARIN")
                    rows_sql = f"SELECT * FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%MARIN%' LIMIT 3"
                    rows = db.session.execute(text(rows_sql)).fetchall()
                    for r in rows:
                        print("  Row:", dict(r._mapping))
        except Exception as e:
            print(f"Error on {t}: {e}")
            
    print("FINISHED SEARCH")
