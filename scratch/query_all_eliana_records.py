from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT id_pulido, fecha, codigo, responsable, pnc_pulido, cantidad_real, lote
        FROM db_pulido
        WHERE responsable LIKE '%Eliana%'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("All Eliana Pulido rows in db_pulido:")
    for r in rows:
        print(dict(r._mapping))

    sql_pnc = """
        SELECT pn.id_pnc_pulido, pn.id_pulido, pn.codigo, pn.cantidad, pn.criterio, p.fecha
        FROM db_pnc_pulido pn
        JOIN db_pulido p ON pn.id_pulido = p.id_pulido
        WHERE p.responsable LIKE '%Eliana%'
    """
    rows_pnc = db.session.execute(text(sql_pnc)).fetchall()
    print("\nAll Eliana Pulido rows in db_pnc_pulido:")
    for r in rows_pnc:
        print(dict(r._mapping))
