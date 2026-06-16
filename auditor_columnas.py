import pyodbc
import os

# ====================================================================
# CONEXIÓN A SQL SERVER - WORLD OFFICE
# Lee credenciales desde variables de entorno (.env) con fallback
# a los valores reales de FRIPARTS.
# ====================================================================
DB_DRIVER   = os.getenv("WO_DB_DRIVER",  "SQL Server")
DB_SERVER   = os.getenv("WO_SERVER",     r"SERVERWO\WORLDOFFICE17")
DB_DATABASE = os.getenv("WO_DB",         "FRIPARTS2021")
DB_UID      = os.getenv("WO_USER",       "wo_cliente")
DB_PWD      = os.getenv("WO_PASSWORD",   "wo_cliente")

conn_str = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_DATABASE};"
    f"UID={DB_UID};"
    f"PWD={DB_PWD};"
)

print(f"[OK] Conectando a  {DB_SERVER} / {DB_DATABASE} como '{DB_UID}' ...")

try:
    conn = pyodbc.connect(conn_str, timeout=10)
    cursor = conn.cursor()

    print("\n[>>] FORENSE DE DATOS COMERCIALES - WORLD OFFICE\n")

    # ── 1. Prefijos reales en Vista_Tabla_Encabezados ──────────────────
    print("=" * 60)
    print("1. PREFIJOS DISTINTOS EN ENCABEZADOS (TOP 20)")
    print("=" * 60)
    cursor.execute("""
        SELECT DISTINCT TOP 20 prefijo, Tipo_de_Documento, COUNT(*) as total
        FROM [dbo].[Vista_Tabla_Encabezados]
        GROUP BY prefijo, Tipo_de_Documento
        ORDER BY total DESC
    """)
    for row in cursor.fetchall():
        print(f"  prefijo='{row[0]}'  |  Tipo_de_Documento='{row[1]}'  |  total={row[2]}")
    print()

    # ── 2. Buscar llave de JOIN: Autonumerico vs Numero_de_Documento ───
    print("=" * 60)
    print("2. BUSCANDO LLAVE DE JOIN (Encabezado <-> Movimientos)")
    print("=" * 60)
    cursor.execute("""
        SELECT TOP 1
            E.Autonumerico,
            E.prefijo,
            E.Numero_de_Documento,
            D.Pertenece_A,
            D.Producto,
            D.Cantidad
        FROM [dbo].[Vista_Tabla_Encabezados] E
        JOIN [dbo].[Vista_Tabla_Movimientos_Inventario] D
            ON E.Autonumerico = D.Pertenece_A
    """)
    row = cursor.fetchone()
    if row:
        print(f"  [JOIN ENCONTRADO] Autonumerico={row[0]} | prefijo='{row[1]}' | NumDoc={row[2]}")
        print(f"  Pertenece_A={row[3]} | Producto='{row[4]}' | Cantidad={row[5]}")
        print("  --> La llave es: Encabezado.Autonumerico = Movimientos.Pertenece_A\n")
    else:
        print("  [!] JOIN por Autonumerico no funciona. Probando Numero_de_Documento...")
        cursor.execute("""
            SELECT TOP 1
                E.Autonumerico, E.prefijo, E.Numero_de_Documento,
                D.Pertenece_A, D.Producto
            FROM [dbo].[Vista_Tabla_Encabezados] E
            JOIN [dbo].[Vista_Tabla_Movimientos_Inventario] D
                ON E.Numero_de_Documento = D.Pertenece_A
        """)
        row2 = cursor.fetchone()
        if row2:
            print(f"  [JOIN ENCONTRADO] NumDoc={row2[2]} = Pertenece_A={row2[3]}")
            print("  --> La llave es: Encabezado.Numero_de_Documento = Movimientos.Pertenece_A\n")
        else:
            print("  [!] Ninguna llave directa funciona. Mostrando muestra de Pertenece_A...\n")
            cursor.execute("SELECT TOP 5 Pertenece_A, Producto, Cantidad FROM [dbo].[Vista_Tabla_Movimientos_Inventario]")
            for r in cursor.fetchall():
                print(f"  Pertenece_A={r[0]} | Producto='{r[1]}' | Cantidad={r[2]}")
            print()

    # ── 3. Muestra de 3 encabezados reales con su tipo ─────────────────
    print("=" * 60)
    print("3. MUESTRA DE 3 ENCABEZADOS (FV o PED si existen)")
    print("=" * 60)
    cursor.execute("""
        SELECT TOP 3
            Autonumerico, prefijo, Tipo_de_Documento,
            Numero_de_Documento, Fecha, Nombre_tercero_externo,
            Identificacion_Tercero, Anulado
        FROM [dbo].[Vista_Tabla_Encabezados]
        WHERE prefijo IN ('FV','PD','PED','FAC')
           OR Tipo_de_Documento LIKE '%Venta%'
           OR Tipo_de_Documento LIKE '%Pedido%'
        ORDER BY Fecha DESC
    """)
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(f"  Auto={r[0]} | pref='{r[1]}' | Tipo='{r[2]}' | N={r[3]} | Fecha={r[4]} | Cliente='{r[5]}' | NIT={r[6]} | Anulado={r[7]}")
    else:
        print("  [WARN] No hay FV/PD en prefijos. Mostrando cualquier TOP 3:")
        cursor.execute("""
            SELECT TOP 3 Autonumerico, prefijo, Tipo_de_Documento,
                         Numero_de_Documento, Fecha, Nombre_tercero_externo
            FROM [dbo].[Vista_Tabla_Encabezados]
            ORDER BY Fecha DESC
        """)
        for r in cursor.fetchall():
            print(f"  Auto={r[0]} | pref='{r[1]}' | Tipo='{r[2]}' | N={r[3]} | Fecha={r[4]} | Cliente='{r[5]}'")
    print()

    conn.close()
    print("[DONE] Forense finalizado.")

except Exception as e:
    print(f"\n[FATAL] Error de conexion: {e}")