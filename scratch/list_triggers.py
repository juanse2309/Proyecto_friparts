
import sys
import os
project_root = r"e:\OneDrive\RYZEN\Documentos\Proyectos de programacion\proyecto_bujes - copia"
sys.path.append(project_root)

from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    res = db.session.execute(text("SELECT trigger_name, event_manipulation, event_object_table FROM information_schema.triggers")).fetchall()
    print("--- Triggers in DB ---")
    for r in res:
        print(r)
