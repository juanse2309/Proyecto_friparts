
from backend.core.sql_database import db
from backend.app import app
from backend.models.sql_models import RegistroAsistencia
from sqlalchemy import text

with app.app_context():
    # Revertir registros procesados erróneamente (posteriores al corte del 28 de abril)
    # Estos registros deberían ser PENDIENTE para el nuevo periodo.
    sql = text("""
        UPDATE db_asistencia 
        SET estado_pago = 'PENDIENTE' 
        WHERE fecha >= '2026-04-29' 
        AND estado_pago = 'PROCESADO'
    """)
    result = db.session.execute(sql)
    db.session.commit()
    print(f"✅ Se han restaurado {result.rowcount} registros a estado PENDIENTE.")
