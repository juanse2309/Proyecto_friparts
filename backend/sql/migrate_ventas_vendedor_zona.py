"""
Migración: agrega columnas nativas 'vendedor' y 'zona' a db_ventas y db_ventas_staging.
No destructiva: usa ADD COLUMN IF NOT EXISTS, preserva las filas históricas existentes.
Las filas ya cargadas quedarán con vendedor/zona en NULL hasta el próximo backfill
completo de agente_wo_comercial.py (ver diff del SELECT en ese script).
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE db_ventas
                ADD COLUMN IF NOT EXISTS vendedor VARCHAR(150),
                ADD COLUMN IF NOT EXISTS zona VARCHAR(100);
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_db_ventas_vendedor ON db_ventas (vendedor);
            CREATE INDEX IF NOT EXISTS ix_db_ventas_zona ON db_ventas (zona);
        """))

        db.session.execute(text("""
            ALTER TABLE db_ventas_staging
                ADD COLUMN IF NOT EXISTS vendedor VARCHAR(150),
                ADD COLUMN IF NOT EXISTS zona VARCHAR(100);
        """))

        db.session.commit()
        print("Migración exitosa: columnas 'vendedor' y 'zona' agregadas a db_ventas y db_ventas_staging.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
