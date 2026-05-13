
import sys
import os
project_root = r"e:\OneDrive\RYZEN\Documentos\Proyectos de programacion\proyecto_bujes - copia"
sys.path.append(project_root)

from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    res = db.session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
    print("--- Tablas en la DB ---")
    for r in res:
        print(f"- {r[0]}")
