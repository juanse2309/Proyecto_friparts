from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    # Let's inspect the columns of db_pnc
    try:
        res = db.session.execute(text("SELECT * FROM db_pnc LIMIT 1"))
        print("db_pnc columns:", res.keys())
        
        # Let's run a query to get Eliana Pulido records in db_pnc
        sql = """
            SELECT * FROM db_pnc
            WHERE responsable ILIKE '%eliana%'
              AND fecha >= '2026-06-10'
              AND fecha <= '2026-06-16'
        """
        rows = db.session.execute(text(sql)).fetchall()
        print("Eliana Pulido rows in db_pnc (June 10-16):")
        for r in rows:
            print(dict(r._mapping))
    except Exception as e:
        print("Error querying db_pnc:", e)
