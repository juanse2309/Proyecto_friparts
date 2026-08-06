"""
Migración: agrega `responsable` y `validado_por` a db_pnc_inyeccion y db_pnc_pulido.

Antes de este cambio ninguna tabla de PNC guardaba personas: el panel de calidad
mostraba un literal hardcodeado ('Inyección' / 'Pulido') y la única firma de
auditoría vivía en la cabecera db_inyeccion.validado_por, que además podía ser
sobrescrita desde el payload del frontend.

Semántica de las columnas nuevas:
  - db_pnc_inyeccion.responsable -> operario de inyección dueño del lote.
  - db_pnc_pulido.responsable    -> operaria de pulido que produjo la merma.
  - validado_por (ambas)         -> identidad autenticada (JWT) que auditó el lote.

No destructiva: ADD COLUMN IF NOT EXISTS, sin backfill. Las filas históricas
quedan en NULL a propósito — no existe fuente de verdad para atribuirles una
persona y rellenarlas con la del lote sería inventar trazabilidad.
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE db_pnc_inyeccion
                ADD COLUMN IF NOT EXISTS responsable  VARCHAR(150),
                ADD COLUMN IF NOT EXISTS validado_por VARCHAR(150);
        """))

        db.session.execute(text("""
            ALTER TABLE db_pnc_pulido
                ADD COLUMN IF NOT EXISTS responsable  VARCHAR(150),
                ADD COLUMN IF NOT EXISTS validado_por VARCHAR(150);
        """))

        db.session.commit()
        print("Migración exitosa: 'responsable' y 'validado_por' agregadas a db_pnc_inyeccion y db_pnc_pulido.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
