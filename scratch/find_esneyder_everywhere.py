from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    # Let's search for the substring 'esneyder' (case insensitive) in EVERY column of EVERY table in the DB.
    # To do this safely and quickly, we get all tables and query them using SQL.
    tables_res = db.session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
    tables = [r[0] for r in tables_res]
    
    for t in tables:
        try:
            cols_res = db.session.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}'")).fetchall()
            cols = [c[0] for c in cols_res]
            for col in cols:
                # We cast everything to text to search
                sql = f"SELECT COUNT(*) FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%ESNEYDER%'"
                cnt = db.session.execute(text(sql)).scalar()
                if cnt > 0:
                    print(f"Table '{t}', Column '{col}' has {cnt} matches for ESNEYDER")
                    # print rows
                    rows_sql = f"SELECT * FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%ESNEYDER%' LIMIT 3"
                    rows = db.session.execute(text(rows_sql)).fetchall()
                    for r in rows:
                        print("  Row:", dict(r._mapping))
        except Exception as e:
            print(f"Error on {t}: {e}")
            
    print("FINISHED SEARCH")
