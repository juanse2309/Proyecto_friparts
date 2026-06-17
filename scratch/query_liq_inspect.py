from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT pn.id_pnc_pulido, pn.id_pulido, pn.codigo, pn.cantidad, pn.criterio, p.responsable, p.fecha
        FROM db_pnc_pulido pn
        LEFT JOIN db_pulido p ON UPPER(pn.id_pulido) = UPPER(p.id_pulido)
        WHERE pn.id_pulido LIKE 'LIQ-%'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("LIQ- rows in db_pnc_pulido:")
    for r in rows:
        row_dict = dict(r._mapping)
        if row_dict.get('cantidad'):
            row_dict['cantidad'] = float(row_dict['cantidad'])
        if row_dict.get('fecha'):
            row_dict['fecha'] = row_dict['fecha'].isoformat()
        print(row_dict)
