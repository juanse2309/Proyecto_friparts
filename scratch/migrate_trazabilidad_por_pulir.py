import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.app import app
from backend.core.sql_database import db

with app.app_context():
    try:
        # Check if column already exists
        res = db.session.execute(db.text("SELECT column_name FROM information_schema.columns WHERE table_name='db_trazabilidad_lotes' AND column_name='por_pulir'")).fetchone()
        if not res:
            print("Adding column 'por_pulir' to db_trazabilidad_lotes...")
            db.session.execute(db.text("ALTER TABLE db_trazabilidad_lotes ADD COLUMN por_pulir INTEGER DEFAULT 0;"))
            db.session.commit()
            print("Column added successfully.")
        else:
            print("Column 'por_pulir' already exists.")

        # Initialize por_pulir to cantidad_inyectada
        print("Initializing por_pulir to cantidad_inyectada...")
        db.session.execute(db.text("UPDATE db_trazabilidad_lotes SET por_pulir = cantidad_inyectada WHERE por_pulir = 0 OR por_pulir IS NULL;"))
        db.session.commit()
        print("Initialization complete.")
    except Exception as e:
        db.session.rollback()
        print("Error during migration:", e)
        sys.exit(1)
