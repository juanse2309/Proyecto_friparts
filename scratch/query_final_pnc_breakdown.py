from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT pn.codigo, pn.cantidad, pn.criterio, p.responsable, p.fecha, pn.id_pulido
        FROM db_pnc_pulido pn
        JOIN db_pulido p ON pn.id_pulido = p.id_pulido
        WHERE p.fecha >= '2026-06-10'
          AND p.fecha <= '2026-06-16'
        ORDER BY p.responsable, pn.codigo
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("Breakdown of all PNC records in date range:")
    for r in rows:
        row_dict = dict(r._mapping)
        if row_dict.get('cantidad'):
            row_dict['cantidad'] = float(row_dict['cantidad'])
        if row_dict.get('fecha'):
            row_dict['fecha'] = row_dict['fecha'].isoformat()
        print(row_dict)
