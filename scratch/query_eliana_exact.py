from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT id_pulido, fecha, codigo, responsable, pnc_pulido, cantidad_real, lote
        FROM db_pulido
        WHERE responsable ILIKE '%eliana%'
          AND fecha >= '2026-06-10'
          AND fecha <= '2026-06-16'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Eliana Pulido rows using ILIKE (June 10-16):")
    total = 0
    for r in rows:
        row_dict = dict(r._mapping)
        print(row_dict)
        total += int(row_dict.get('pnc_pulido') or 0)
    print(f"Total: {total}")
