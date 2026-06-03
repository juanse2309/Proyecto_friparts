import sys
import os
from backend.app import app
from backend.core.sql_database import db

with app.app_context():
    try:
        db.session.execute(db.text('ALTER TABLE db_inyeccion ADD COLUMN validado_por VARCHAR(150);'))
        db.session.commit()
        print('Added validado_por')
    except Exception as e:
        db.session.rollback()
        print('validado_por might exist:', str(e))
