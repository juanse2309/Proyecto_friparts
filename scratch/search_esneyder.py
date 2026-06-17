from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    # Get all text columns in the database
    sql_cols = """
        SELECT table_name, column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND data_type IN ('character varying', 'text', 'character')
    """
    cols = db.session.execute(text(sql_cols)).fetchall()
    
    print(f"Searching {len(cols)} text columns...")
    for t_name, c_name in cols:
        try:
            sql_search = f'SELECT COUNT(*) FROM "{t_name}" WHERE UPPER("{c_name}") LIKE :pat'
            cnt = db.session.execute(text(sql_search), {"pat": "%ESNEYDER%"}).scalar()
            if cnt > 0:
                print(f"MATCH: Table '{t_name}', Column '{c_name}' -> {cnt} rows")
                # Show rows
                sql_rows = f'SELECT * FROM "{t_name}" WHERE UPPER("{c_name}") LIKE :pat LIMIT 5'
                rows = db.session.execute(text(sql_rows), {"pat": "%ESNEYDER%"}).fetchall()
                for r in rows:
                    print("  Row:", dict(r._mapping))
        except Exception as e:
            pass
            # print(f"Error on {t_name}.{c_name}: {e}")
            
    print("\nSearch complete.")
