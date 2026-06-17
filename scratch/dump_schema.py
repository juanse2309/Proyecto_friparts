import os
import pyodbc
import json
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
    
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS")
    vistas = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
    tablas = [row[0] for row in cursor.fetchall()]

    data = {"vistas": vistas, "tablas": tablas}
    
    with open("schema_dump.json", "w") as f:
        json.dump(data, f, indent=2)
        
    print("Esquema guardado en schema_dump.json")

    cursor.close()
    conn.close()
except Exception as e:
    print("Error de conexión:", e)
