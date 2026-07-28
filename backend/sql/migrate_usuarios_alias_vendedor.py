"""
Migración: agrega db_usuarios.alias_vendedor_wo (nombre exacto de World Office
para comparar contra db_ventas.vendedor sin depender del nombre de login/display).
No destructiva: ADD COLUMN IF NOT EXISTS + UPDATE solo si el alias esta vacio.

Backfill inicial: el unico usuario con rol 'comercial' hoy es Andres Borbon Rey
(id=0), cuyo nombre en World Office es 'ANDRES HERNANDO BORBON REY' (confirmado
por auditoria read-only contra db_ventas.vendedor).
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE db_usuarios
                ADD COLUMN IF NOT EXISTS alias_vendedor_wo VARCHAR(150);
        """))

        db.session.execute(text("""
            UPDATE db_usuarios
            SET alias_vendedor_wo = 'ANDRES HERNANDO BORBON REY'
            WHERE id = 0
              AND (alias_vendedor_wo IS NULL OR TRIM(alias_vendedor_wo) = '');
        """))

        db.session.commit()
        print("Migración exitosa: columna 'alias_vendedor_wo' agregada y backfill de Andrés Borbón Rey aplicado.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
