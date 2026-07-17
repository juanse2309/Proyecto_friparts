from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    try:
        # Backup table
        db.session.execute(text("CREATE TABLE IF NOT EXISTS cartera_wo_backup AS SELECT * FROM cartera_wo;"))
        print("Backup creado con éxito: cartera_wo_backup")
        
        # Drop and create
        db.session.execute(text("DROP TABLE IF EXISTS cartera_wo;"))
        db.session.execute(text("""
            CREATE TABLE cartera_wo (
                documento VARCHAR PRIMARY KEY,
                identificacion VARCHAR,
                nombre VARCHAR,
                vendedor VARCHAR,
                moneda VARCHAR,
                empresa VARCHAR,
                fecha_vencimiento DATE,
                saldo_documento NUMERIC,
                ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        db.session.commit()
        print("Tabla cartera_wo migrada exitosamente.")
    except Exception as e:
        db.session.rollback()
        print("Error en migración:", e)
