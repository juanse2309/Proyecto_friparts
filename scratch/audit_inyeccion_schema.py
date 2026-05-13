from backend.app import app
from backend.core.sql_database import db
from sqlalchemy import text

with app.app_context():
    res = db.session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'db_inyeccion'")).all()
    print("Schema for db_inyeccion:")
    for row in res:
        print(f"  - {row[0]}: {row[1]}")
