from backend.core.sql_database import db
from backend.app import app
from backend.core.repository_service import SHEET_TO_TABLE # just to import something or test it
from sqlalchemy import text

with app.app_context():
    # Let's run get_ranking_operarios_pulido logic for Eliana Pulido
    sql = """
        SELECT 
            UPPER(TRIM(p.responsable)) as responsable,
            COALESCE(SUM(NULLIF(regexp_replace(p.pnc_pulido::text, '[^0-9]', '', 'g'), '')::INTEGER), 0) as pnc
        FROM db_pulido p
        WHERE p.fecha BETWEEN '2026-06-10' AND '2026-06-16'
        GROUP BY UPPER(TRIM(p.responsable))
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Ranking operarios pulido PNC (June 10-16):")
    for r in rows:
        print(dict(r._mapping))
