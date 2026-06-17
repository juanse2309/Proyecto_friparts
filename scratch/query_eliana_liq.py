from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT id_pulido, fecha, codigo, responsable, pnc_pulido, lote
        FROM db_pulido
        WHERE responsable LIKE '%Eliana%'
          AND id_pulido LIKE 'LIQ-%'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Eliana Pulido LIQ rows in db_pulido:")
    for r in rows:
        print(dict(r._mapping))

    sql_pnc = """
        SELECT id_pnc_pulido, id_pulido, codigo, cantidad, criterio
        FROM db_pnc_pulido
        WHERE id_pulido LIKE 'LIQ-20260605-MAQUINANo.4%'
    """
    rows_pnc = db.session.execute(text(sql_pnc)).fetchall()
    print("\nPncPulido rows:")
    for r in rows_pnc:
        print(dict(r._mapping))
