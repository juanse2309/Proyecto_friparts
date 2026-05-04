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

def fix_schema():
    with app.app_context():
        print("--- Fixing db_pulido schema (Atomic Version) ---")
        
        # 1. segundos_por_unidad
        run_sql("""
            ALTER TABLE db_pulido ALTER COLUMN segundos_por_unidad TYPE NUMERIC(10,2) 
            USING (CASE 
                WHEN segundos_por_unidad ~ '^-?[0-9.]+([eE][+-]?[0-9]+)?$' THEN segundos_por_unidad::numeric 
                ELSE 0 
            END)
        """)

        # 2. duracion_segundos
        run_sql("""
            ALTER TABLE db_pulido ALTER COLUMN duracion_segundos TYPE INTEGER 
            USING (CASE 
                WHEN duracion_segundos::text ~ '^[0-9]+$' THEN duracion_segundos::text::integer 
                ELSE 0 
            END)
        """)

        # 3. cantidad_recibida
        run_sql("""
            ALTER TABLE db_pulido ALTER COLUMN cantidad_recibida TYPE NUMERIC(18,2) 
            USING (CASE 
                WHEN cantidad_recibida::text ~ '^-?[0-9.]+([eE][+-]?[0-9]+)?$' THEN cantidad_recibida::text::numeric 
                ELSE 0 
            END)
        """)

        # 4. hora_inicio / hora_fin
        for col in ['hora_inicio', 'hora_fin']:
            success = run_sql(f"ALTER TABLE db_pulido ALTER COLUMN {col} TYPE TIMESTAMP WITHOUT TIME ZONE USING NULLIF({col}, '')::timestamp")
            if not success:
                print(f"Retrying {col} with DROP/ADD")
                run_sql(f"ALTER TABLE db_pulido DROP COLUMN {col}")
                run_sql(f"ALTER TABLE db_pulido ADD COLUMN {col} TIMESTAMP WITHOUT TIME ZONE")

        print("--- Schema fix completed ---")

if __name__ == "__main__":
    fix_schema()
