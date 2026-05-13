from backend.app import app
from backend.core.sql_database import db
from sqlalchemy import text

with app.app_context():
    res = db.session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'db_pulido'")).all()
    print("Schema for db_pulido:")
    for row in res:
        print(f"  - {row[0]}: {row[1]}")
