import sys
import os
from backend.app import app
from backend.core.sql_database import db

with app.app_context():
    try:
        db.session.execute(db.text('ALTER TABLE db_inyeccion ADD COLUMN programado_por VARCHAR(150);'))
        db.session.commit()
        print('Added programado_por')
    except Exception as e:
        db.session.rollback()
        print('programado_por might exist:', str(e))
    
    try:
        db.session.execute(db.text('ALTER TABLE db_inyeccion ADD COLUMN iniciado_por VARCHAR(150);'))
        db.session.commit()
        print('Added iniciado_por')
    except Exception as e:
        db.session.rollback()
        print('iniciado_por might exist:', str(e))

    try:
        db.session.execute(db.text('ALTER TABLE db_inyeccion ADD COLUMN finalizado_por VARCHAR(150);'))
        db.session.commit()
        print('Added finalizado_por')
    except Exception as e:
        db.session.rollback()
        print('finalizado_por might exist:', str(e))
