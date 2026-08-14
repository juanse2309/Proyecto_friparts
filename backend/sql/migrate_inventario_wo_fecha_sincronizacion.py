"""
Migración: agrega `fecha_sincronizacion` a inventario_wo.

Antes de este cambio, inventario_wo (tabla de staging que puebla
backend/integration/agente_wo.py) no guardaba cuándo se recibió cada fila, así
que era imposible saber -- desde el botón "Sincronizar Stock con World Office"
del dashboard -- si el stock que se iba a aplicar sobre db_productos era de
hace 5 minutos o de hace 3 semanas.

Semántica de la columna nueva:
  - fecha_sincronizacion -> timestamp (hora del servidor Postgres, vía NOW())
    en el que ese código_producto fue insertado/actualizado por
    WoSyncService._procesar_inventario (POST /api/wo/recibir_datos, llamado
    únicamente por el agente local agente_wo.py).

No destructiva: ADD COLUMN IF NOT EXISTS, sin backfill. Las filas ya
existentes en inventario_wo quedan con fecha_sincronizacion en NULL -- no hay
forma de reconstruir retroactivamente cuándo llegaron.
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE inventario_wo
                ADD COLUMN IF NOT EXISTS fecha_sincronizacion TIMESTAMP;
        """))

        db.session.commit()
        print("Migración exitosa: 'fecha_sincronizacion' agregada a inventario_wo.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
