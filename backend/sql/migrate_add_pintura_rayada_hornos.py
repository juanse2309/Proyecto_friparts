"""
Migración: crea las tablas db_pintura, db_rayada y db_hornos para los nuevos
subprocesos de Ensamble (Pintura, Rayada, Hornos).

No destructiva: CREATE TABLE IF NOT EXISTS, sin tocar ninguna tabla existente.
Columnas alineadas 1:1 con backend/models/sql_models.py
(ProduccionPintura, ProduccionRayada, ProduccionHorno).
"""
from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS db_pintura (
                id                      SERIAL PRIMARY KEY,
                id_pintura              VARCHAR(80),
                id_ensamble             TEXT,
                id_codigo               TEXT,
                responsable             TEXT,
                insumo_pintura          VARCHAR(100),
                cantidad                INTEGER DEFAULT 0,
                ml_insumo_utilizado     NUMERIC(18, 2) DEFAULT 0,
                rendimiento_ml_unidad   NUMERIC(10, 4) DEFAULT 0,
                op_numero               TEXT,
                fecha                   TIMESTAMP,
                hora_inicio             TIMESTAMP,
                hora_fin                TIMESTAMP,
                hora_pausa              TIMESTAMP,
                tiempo_pausa_acumulado  INTEGER DEFAULT 0,
                duracion_segundos       INTEGER DEFAULT 0,
                tiempo_total_minutos    NUMERIC(10, 2) DEFAULT 0,
                segundos_por_unidad     NUMERIC(10, 2) DEFAULT 0,
                pnc_cantidad            INTEGER DEFAULT 0,
                observaciones           TEXT,
                estado                  VARCHAR(50) DEFAULT 'EN_PROCESO',
                departamento            VARCHAR(100) DEFAULT 'Pintura'
            );
            CREATE INDEX IF NOT EXISTS ix_db_pintura_id_pintura  ON db_pintura (id_pintura);
            CREATE INDEX IF NOT EXISTS ix_db_pintura_id_ensamble ON db_pintura (id_ensamble);
            CREATE INDEX IF NOT EXISTS ix_db_pintura_id_codigo   ON db_pintura (id_codigo);
            CREATE INDEX IF NOT EXISTS ix_db_pintura_fecha       ON db_pintura (fecha);

            CREATE TABLE IF NOT EXISTS db_rayada (
                id                      SERIAL PRIMARY KEY,
                id_rayada               VARCHAR(80),
                id_ensamble             TEXT,
                id_codigo               TEXT,
                responsable             TEXT,
                cantidad                INTEGER DEFAULT 0,
                op_numero               TEXT,
                fecha                   TIMESTAMP,
                hora_inicio             TIMESTAMP,
                hora_fin                TIMESTAMP,
                hora_pausa              TIMESTAMP,
                tiempo_pausa_acumulado  INTEGER DEFAULT 0,
                duracion_segundos       INTEGER DEFAULT 0,
                tiempo_total_minutos    NUMERIC(10, 2) DEFAULT 0,
                segundos_por_unidad     NUMERIC(10, 2) DEFAULT 0,
                pnc_cantidad            INTEGER DEFAULT 0,
                observaciones           TEXT,
                estado                  VARCHAR(50) DEFAULT 'EN_PROCESO',
                departamento            VARCHAR(100) DEFAULT 'Rayada'
            );
            CREATE INDEX IF NOT EXISTS ix_db_rayada_id_rayada   ON db_rayada (id_rayada);
            CREATE INDEX IF NOT EXISTS ix_db_rayada_id_ensamble ON db_rayada (id_ensamble);
            CREATE INDEX IF NOT EXISTS ix_db_rayada_id_codigo   ON db_rayada (id_codigo);
            CREATE INDEX IF NOT EXISTS ix_db_rayada_fecha       ON db_rayada (fecha);

            CREATE TABLE IF NOT EXISTS db_hornos (
                id                      SERIAL PRIMARY KEY,
                id_horno_registro       VARCHAR(80),
                id_ensamble             TEXT,
                id_codigo               TEXT,
                horno_numero            VARCHAR(50),
                responsable             TEXT,
                cantidad                INTEGER DEFAULT 0,
                temperatura_ingreso_c   NUMERIC(6, 2),
                temperatura_salida_c    NUMERIC(6, 2),
                op_numero               TEXT,
                fecha                   TIMESTAMP,
                hora_inicio             TIMESTAMP,
                hora_fin                TIMESTAMP,
                duracion_segundos       INTEGER DEFAULT 0,
                tiempo_total_minutos    NUMERIC(10, 2) DEFAULT 0,
                pnc_cantidad            INTEGER DEFAULT 0,
                observaciones           TEXT,
                estado                  VARCHAR(50) DEFAULT 'EN_HORNO',
                departamento            VARCHAR(100) DEFAULT 'Hornos'
            );
            CREATE INDEX IF NOT EXISTS ix_db_hornos_id_horno_registro ON db_hornos (id_horno_registro);
            CREATE INDEX IF NOT EXISTS ix_db_hornos_id_ensamble       ON db_hornos (id_ensamble);
            CREATE INDEX IF NOT EXISTS ix_db_hornos_id_codigo         ON db_hornos (id_codigo);
            CREATE INDEX IF NOT EXISTS ix_db_hornos_fecha             ON db_hornos (fecha);
        """))

        db.session.commit()
        print("Migración exitosa: 'db_pintura', 'db_rayada' y 'db_hornos' creadas (o ya existían).")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
