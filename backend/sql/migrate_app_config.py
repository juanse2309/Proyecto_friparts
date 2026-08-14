"""
Migración: crea la tabla app_config (clave/valor de propósito general).

Primer uso: reemplaza el flag de sincronización comercial que vivía en
data/sync_comercial_flag.json (backend/routes/wo_routes.py:
solicitar_sync/verificar_sync). En Render el filesystem es efímero -- ese
archivo se perdía en cada redeploy, y tampoco se comparte si la app llega a
escalar a más de una instancia. Una fila en Postgres sobrevive ambos casos.

No destructiva: CREATE TABLE IF NOT EXISTS, sin backfill (no había datos
persistentes que migrar -- el archivo solo importaba mientras el flag
estuviera pendiente, entre "solicitar_sync" y la siguiente corrida del
agente local).
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS app_config (
                clave VARCHAR(100) PRIMARY KEY,
                valor TEXT,
                actualizado_en TIMESTAMP DEFAULT NOW()
            );
        """))

        db.session.commit()
        print("Migración exitosa: tabla 'app_config' creada.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
