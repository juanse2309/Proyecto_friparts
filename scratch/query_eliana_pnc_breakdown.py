from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    # Let's inspect the columns of db_pulido and db_pnc_pulido
    # Let's run a query to get all PNC records for Eliana Pulido between 2026-06-10 and 2026-06-16
    sql = """
        SELECT p.id_pulido, p.fecha, p.codigo, p.responsable, p.pnc_pulido, p.lote
        FROM db_pulido p
        WHERE p.responsable LIKE '%Eliana%'
          AND p.fecha >= '2026-06-10'
          AND p.fecha <= '2026-06-16'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Eliana Pulido rows in db_pulido (June 10-16):")
    total_db_pulido_pnc = 0
    for r in rows:
        row_dict = dict(r._mapping)
        print(row_dict)
        total_db_pulido_pnc += float(row_dict.get('pnc_pulido') or 0)
    print(f"Total pnc_pulido sum in db_pulido: {total_db_pulido_pnc}")

    sql_pnc = """
        SELECT pn.id_pnc_pulido, pn.id_pulido, pn.codigo, pn.cantidad, pn.criterio, p.fecha, p.responsable
        FROM db_pnc_pulido pn
        JOIN db_pulido p ON pn.id_pulido = p.id_pulido
        WHERE p.responsable LIKE '%Eliana%'
          AND p.fecha >= '2026-06-10'
          AND p.fecha <= '2026-06-16'
    """
    rows_pnc = db.session.execute(text(sql_pnc)).fetchall()
    print("\nEliana Pulido rows in db_pnc_pulido (June 10-16):")
    total_db_pnc_pulido_cantidad = 0
    for r in rows_pnc:
        row_dict = dict(r._mapping)
        print(row_dict)
        total_db_pnc_pulido_cantidad += float(row_dict.get('cantidad') or 0)
    print(f"Total cantidad sum in db_pnc_pulido: {total_db_pnc_pulido_cantidad}")
