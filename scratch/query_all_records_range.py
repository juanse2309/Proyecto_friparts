from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

with app.app_context():
    sql = """
        SELECT DISTINCT responsable FROM db_pulido
    """
    rows = db.session.execute(text(sql)).fetchall()
    print("All distinct responsables in db_pulido:")
    for r in rows:
        print(r[0])

    sql2 = """
        SELECT id_pulido, fecha, codigo, responsable, pnc_pulido, cantidad_real, lote
        FROM db_pulido
        WHERE fecha >= '2026-06-10'
          AND fecha <= '2026-06-16'
    """
    rows2 = db.session.execute(text(sql2)).fetchall()
    print("\nAll records in db_pulido (June 10-16):")
    for r in rows2:
        print(dict(r._mapping))
