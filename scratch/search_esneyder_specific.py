from backend.core.sql_database import db
from backend.app import app
from sqlalchemy import text

tables = ['db_pnc', 'db_asistencia', 'usuarios_raw', 'db_ventas', 'db_pedidos', 'db_ensambles']

with app.app_context():
    for t in tables:
        try:
            # check columns of t
            res = db.session.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}'")).fetchall()
            cols = [r[0] for r in res]
            for col in cols:
                sql = f"SELECT COUNT(*) FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%ESNEYDER%' OR UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%MARIN%'"
                cnt = db.session.execute(text(sql)).scalar()
                if cnt > 0:
                    print(f"Match in {t}.{col} -> {cnt} rows")
                    row_sql = f"SELECT * FROM \"{t}\" WHERE UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%ESNEYDER%' OR UPPER(CAST(\"{col}\" AS TEXT)) LIKE '%MARIN%' LIMIT 10"
                    rows = db.session.execute(text(row_sql)).fetchall()
                    for r in rows:
                        print("  Row:", dict(r._mapping))
        except Exception as e:
            print(f"Error on {t}: {e}")
