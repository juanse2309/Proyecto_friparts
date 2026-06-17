from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT id_lote, cantidad_inyectada, por_pulir, estado_actual, responsable, fecha_creacion
        FROM db_trazabilidad_lotes
        WHERE id_lote LIKE '20260605-MAQUINANo.4-303915%'
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("TrazabilidadLote rows:")
    for r in rows:
        print(dict(r._mapping))
