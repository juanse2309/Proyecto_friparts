import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

server_env = os.getenv("WO_DB_SERVER", r"SERVERWO\WORLDOFFICE17")
db_env = os.getenv("WO_DB_DATABASE", "FRIPARTS2021")
uid_env = os.getenv("WO_DB_UID", "wo_cliente")
pwd_env = os.getenv("WO_DB_PWD", "wo_cliente")

conn_str = f"DRIVER={{SQL Server}};SERVER={server_env};DATABASE={db_env};UID={uid_env};PWD={pwd_env};Timeout=30;"

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    views_to_check = [
        "Vista_Tabla_Encabezados",
        "Vista_Tabla_Movimientos_Inventario",
        "Vista_Auxiliar_Movimientos_Inventario",
        "Vista_Tabla_Documentos_Cruces"
    ]
    
    for view in views_to_check:
        try:
            cursor.execute(f"SELECT TOP 1 * FROM [{db_env}].[dbo].[{view}]")
            columns = [column[0] for column in cursor.description]
            print(f"\n--- Columnas en {view} ---")
            
            # Buscar prefijo o tipo documento
            col_target = None
            for c in columns:
                if "prefijo" in c.lower() or "tipodocumento" in c.lower() or "documento" in c.lower():
                    col_target = c
                    break
            
            if col_target:
                print(f"Columna encontrada: {col_target}. Ejecutando DISTINCT...")
                cursor.execute(f"SELECT DISTINCT {col_target} FROM [{db_env}].[dbo].[{view}]")
                rows = cursor.fetchall()
                print("Valores únicos:")
                for r in rows:
                    print(f"- {r[0]}")
            else:
                print("No se encontró columna tipo/prefijo documento.")
        except Exception as e:
            print(f"Error consultando {view}:", e)

    cursor.close()
    conn.close()
except Exception as e:
    print("Error de conexión:", e)
