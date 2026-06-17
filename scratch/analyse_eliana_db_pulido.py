from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT id_pulido, fecha, codigo, responsable, pnc_pulido, cantidad_real, lote
        FROM db_pulido
        WHERE responsable LIKE '%Eliana%'
          AND fecha >= '2026-06-10'
          AND fecha <= '2026-06-16'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Eliana Pulido rows in db_pulido (June 10-16):")
    total_pnc = 0
    total_real = 0
    for r in rows:
        row_dict = dict(r._mapping)
        print(row_dict)
        total_pnc += int(row_dict.get('pnc_pulido') or 0)
        total_real += int(row_dict.get('cantidad_real') or 0)
    print(f"Total pnc_pulido: {total_pnc}")
    print(f"Total cantidad_real: {total_real}")
