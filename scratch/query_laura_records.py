from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT id_pulido, fecha, codigo, responsable, pnc_pulido, cantidad_real, lote
        FROM db_pulido
        WHERE responsable LIKE '%Laura%'
          AND fecha >= '2026-06-10'
          AND fecha <= '2026-06-16'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Laura's rows in db_pulido (June 10-16):")
    for r in rows:
        print(dict(r._mapping))
