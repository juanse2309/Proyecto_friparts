from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    # Group by responsable in db_pnc for all dates
    sql = """
        SELECT 
            UPPER(TRIM(responsable)) as responsable,
            SUM(cantidad) as total_pnc,
            COUNT(*) as record_count
        FROM db_pnc
        GROUP BY 1
        ORDER BY total_pnc DESC
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("db_pnc ALL TIME PNC BY RESPONSABLE:")
    for r in rows:
        print(f"- {r[0]}: {r[1]} PNC ({r[2]} rows)")

    # Group by responsable in db_pnc for dates 2026-06-10 to 2026-06-16
    sql_dates = """
        SELECT 
            UPPER(TRIM(responsable)) as responsable,
            SUM(cantidad) as total_pnc,
            COUNT(*) as record_count
        FROM db_pnc
        WHERE fecha BETWEEN '2026-06-10' AND '2026-06-16'
        GROUP BY 1
        ORDER BY total_pnc DESC
    """
    rows_dates = db.session.execute(text(sql_dates)).fetchall()
    print("\ndb_pnc PNC BY RESPONSABLE (2026-06-10 to 2026-06-16):")
    for r in rows_dates:
        print(f"- {r[0]}: {r[1]} PNC ({r[2]} rows)")
