import psycopg2

conn_str = 'postgresql://admin_juan:5uM2TSjhKB2nIRPR41xJlmgJ5tKgaonX@dpg-d7f5mrpf9bms73a0a1g0-a.virginia-postgres.render.com/fritech_db'

try:
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    cols_to_add = [
        ("quemado_manchado", "NUMERIC DEFAULT 0"),
        ("incompleto_falta_llenado", "NUMERIC DEFAULT 0"),
        ("rebaba_excesiva", "NUMERIC DEFAULT 0"),
        ("burbuja_porosidad", "NUMERIC DEFAULT 0"),
        ("deformacion_rechupado", "NUMERIC DEFAULT 0")
    ]
    for col_name, col_type in cols_to_add:
        cur.execute(f"ALTER TABLE db_pnc_inyeccion ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
    conn.commit()
    print("Columns added successfully!")
    
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'db_pnc_inyeccion'")
    rows = cur.fetchall()
    print("COLUMNS IN DB:")
    for r in rows:
        if not r[0].startswith("col_"):
            print(f"  {r[0]} ({r[1]})")
    cur.close()
    conn.close()
except Exception as e:
    print("Error:", e)
