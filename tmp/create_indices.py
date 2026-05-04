import os
import sys

# Agregar el directorio actual al path para que los imports funcionen
sys.path.append(os.getcwd())

from backend.app import app
from backend.core.sql_database import db
from sqlalchemy import text

def create_indices():
    with app.app_context():
        try:
            print("Creando indices...")
            # PostgreSQL syntax: CREATE INDEX IF NOT EXISTS
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_ventas_nombres ON db_ventas(nombres);"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_ventas_clasificacion ON db_ventas(clasificacion);"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_costos_referencia ON db_costos(referencia);"))
            db.session.commit()
            print("¡Indices creados exitosamente!")
        except Exception as e:
            print(f"Error creando indices: {e}")
            db.session.rollback()

if __name__ == "__main__":
    create_indices()
