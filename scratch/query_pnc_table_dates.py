from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT id_pnc_pulido, id_pulido, codigo, cantidad, criterio, fecha
        FROM db_pnc_pulido
        WHERE fecha >= '2026-06-10'
          AND fecha <= '2026-06-16'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Direct db_pnc_pulido rows (June 10-16):")
    total = 0
    for r in rows:
        row_dict = dict(r._mapping)
        print(row_dict)
        total += float(row_dict.get('cantidad') or 0)
    print(f"Total: {total}")
