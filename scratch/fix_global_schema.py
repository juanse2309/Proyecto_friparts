from backend.app import app
from backend.models.sql_models import db
from sqlalchemy import text

def run_sql(query):
    try:
        db.session.execute(text(query))
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Failed query: {query}\nError: {e}")
        return False

def fix_global_schema():
    with app.app_context():
        # --- TABLA: db_inyeccion ---
        print("--- Standardizing db_inyeccion ---")
        # Asegurar columnas de métricas existen o se crean (si no están en DB pero sí en modelo)
        for col in ['duracion_segundos', 'tiempo_total_minutos', 'segundos_por_unidad', 'departamento']:
            # Check if exists
            res = db.session.execute(text(f"SELECT 1 FROM information_schema.columns WHERE table_name='db_inyeccion' AND column_name='{col}'")).fetchone()
            if not res:
                col_type = "INTEGER" if "segundos" in col else "NUMERIC(10,2)"
                if col == "departamento": col_type = "TEXT"
                run_sql(f"ALTER TABLE db_inyeccion ADD COLUMN {col} {col_type}")
        
        # Casting de tipos
        run_sql("""
            ALTER TABLE db_inyeccion ALTER COLUMN segundos_por_unidad TYPE NUMERIC(10,2) 
            USING (CASE WHEN segundos_por_unidad ~ '^-?[0-9.]+([eE][+-]?[0-9]+)?$' THEN segundos_por_unidad::numeric ELSE 0 END)
        """)
        run_sql("UPDATE db_inyeccion SET departamento = 'Inyeccion' WHERE departamento IS NULL OR departamento = ''")

        # --- TABLA: db_ensambles ---
        print("--- Standardizing db_ensambles ---")
        for col in ['duracion_segundos', 'tiempo_total_minutos', 'segundos_por_unidad', 'departamento']:
            res = db.session.execute(text(f"SELECT 1 FROM information_schema.columns WHERE table_name='db_ensambles' AND column_name='{col}'")).fetchone()
            if not res:
                col_type = "INTEGER" if "segundos" in col else "NUMERIC(10,2)"
                if col == "departamento": col_type = "TEXT"
                run_sql(f"ALTER TABLE db_ensambles ADD COLUMN {col} {col_type}")

        # Fix horas en Ensamble
        for col in ['hora_inicio', 'hora_fin']:
            success = run_sql(f"ALTER TABLE db_ensambles ALTER COLUMN {col} TYPE TIMESTAMP WITHOUT TIME ZONE USING NULLIF({col}, '')::timestamp")
            if not success:
                print(f"Hard reset for {col} in db_ensambles")
                run_sql(f"ALTER TABLE db_ensambles DROP COLUMN {col}")
                run_sql(f"ALTER TABLE db_ensambles ADD COLUMN {col} TIMESTAMP WITHOUT TIME ZONE")

        run_sql("UPDATE db_ensambles SET departamento = 'Ensamble' WHERE departamento IS NULL OR departamento = ''")

        print("--- Global Schema Standardization completed ---")

if __name__ == "__main__":
    fix_global_schema()
