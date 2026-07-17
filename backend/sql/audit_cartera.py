from backend.app import app
from backend.core.sql_database import db
from sqlalchemy import text

with app.app_context():
    try:
        # 1. Total de registros y saldo sumado
        res_totales = db.session.execute(text("SELECT COUNT(*), SUM(saldo_documento) FROM cartera_wo")).fetchone()
        print(f"Total registros: {res_totales[0]}")
        print(f"Saldo total: {res_totales[1]}")
        
        # 2. Facturas vencidas antes de 2026-07-17
        res_vencidas = db.session.execute(text("SELECT COUNT(*) FROM cartera_wo WHERE fecha_vencimiento < '2026-07-17'")).scalar()
        print(f"Facturas con fecha_vencimiento < '2026-07-17': {res_vencidas}")
        
        # 3. Fechas nulas o 1900-01-01
        res_1900 = db.session.execute(text("SELECT COUNT(*) FROM cartera_wo WHERE fecha_vencimiento = '1900-01-01' OR fecha_vencimiento IS NULL")).scalar()
        print(f"Facturas con fecha 1900-01-01 o NULL: {res_1900}")
        
        # 4. Top 5 clientes críticos reales (vencidos antes de hoy usando CURRENT_DATE vs fecha estática)
        print("\n--- TOP 5 CLIENTES CRÍTICOS (CURRENT_DATE) ---")
        query_top = text("""
            SELECT nombre, SUM(CASE WHEN fecha_vencimiento < CURRENT_DATE THEN saldo_documento ELSE 0 END) as saldo_vencido 
            FROM cartera_wo 
            GROUP BY nombre 
            HAVING SUM(CASE WHEN fecha_vencimiento < CURRENT_DATE THEN saldo_documento ELSE 0 END) > 0 
            ORDER BY saldo_vencido DESC 
            LIMIT 5
        """)
        for row in db.session.execute(query_top).fetchall():
            print(f"Cliente: {row[0]}, Vencido: {row[1]}")

        # 5. CURRENT_DATE value in Postgres
        res_date = db.session.execute(text("SELECT CURRENT_DATE, CURRENT_TIMESTAMP")).fetchone()
        print(f"\nFecha servidor DB: {res_date[0]} (Timestamp: {res_date[1]})")

    except Exception as e:
        print("Error:", e)
