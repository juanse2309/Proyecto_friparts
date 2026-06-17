from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT pnc.id_pnc_pulido, p.fecha, p.responsable, pnc.codigo, pnc.cantidad, pnc.criterio, pnc.codigo_ensamble
        FROM db_pnc_pulido pnc
        JOIN db_pulido p ON pnc.id_pulido = p.id_pulido
        WHERE p.fecha BETWEEN '2026-06-10' AND '2026-06-16'
        ORDER BY pnc.cantidad DESC
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("ALL db_pnc_pulido rows between 10 and 16:")
    for r in rows:
        print(dict(r._mapping))
