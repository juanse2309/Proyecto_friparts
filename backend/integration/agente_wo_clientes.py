"""
agente_wo_clientes.py
======================
Agente local de extracción del catálogo de Clientes/Direcciones (sucursales)
desde World Office hacia FRITECH. Corre en la máquina de planta con acceso
directo al SQL Server de WO (mismo patrón que agente_wo_cartera.py).

Fuente confirmada por inspección directa del esquema de WO:
  Vista_Tabla_Direcciones — 2753 filas, 2721 NITs distintos, 30 NITs con
  más de una dirección (sucursales). Un mismo Identificacion (NIT) puede
  repetirse en varias filas: cada fila es una sede distinta del mismo
  tercero (ej. NIT 830008309 tiene sede en Bogotá y en Funza), así que la
  llave real de sincronización es IdTerceroDireccion (PK de WO por
  dirección), NO Identificacion. NUNCA deduplicar por NIT — se perderían
  sedes reales.

Envía el resultado en una sola petición a POST /api/wo/sincronizar_clientes
(mismo patrón que agente_wo_cartera.py); el batching de 500 en la escritura
a Postgres lo hace ClienteRepository.upsert_clientes_wo del lado del backend,
dentro de una unica transaccion. Enviar en varias peticiones HTTP separadas
(chunking a nivel de red) rompe el circuit breaker del endpoint, que compara
el tamaño de cada request contra el total acumulado en la tabla.
"""
import os
import sys
import pyodbc
import requests
from dotenv import load_dotenv

load_dotenv()

DB_DRIVER   = os.getenv("WO_DB_DRIVER",  "{ODBC Driver 17 for SQL Server}")
DB_SERVER   = os.getenv("WO_SERVER",     r"SERVERWO\WORLDOFFICE17")
DB_DATABASE = os.getenv("WO_DB",         "FRIPARTS2021")
DB_UID      = os.getenv("WO_USER",       "wo_cliente")
DB_PWD      = os.getenv("WO_PASSWORD")
if not DB_PWD:
    raise RuntimeError("WO_PASSWORD no está configurada")

API_URL = os.getenv("API_RENDER_URL_CLIENTES", "https://proyecto-friparts.onrender.com/api/wo/sincronizar_clientes")
API_KEY = os.getenv("WO_SYNC_API_KEY") or os.getenv("SYNC_TOKEN")
if not API_KEY:
    raise RuntimeError("WO_SYNC_API_KEY / SYNC_TOKEN no está configurada")

conn_str = (
    f"DRIVER={DB_DRIVER};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_DATABASE};"
    f"UID={DB_UID};"
    f"PWD={DB_PWD};"
    "Timeout=30;"
)

SQL_DIRECCIONES = """
    SELECT
        IdTerceroDireccion,
        Identificacion,
        Nombres_tercero,
        Direccion,
        Ciudad,
        Telefonos
    FROM Vista_Tabla_Direcciones
    WHERE Identificacion IS NOT NULL AND LTRIM(RTRIM(Identificacion)) != ''
"""


def enviar_datos(datos, url_api, headers):
    payload = {"datos": datos}
    try:
        response = requests.post(url_api, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        print(f"[OK] {len(datos)} registros enviados correctamente.")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Falló el envío: {e}")
        if getattr(e, "response", None) is not None:
            print(e.response.text)
        raise e


def ejecutar_extraccion():
    print("=" * 60)
    print("[>>] INICIANDO EXTRACCION DE CLIENTES/DIRECCIONES DESDE WO")
    print("=" * 60)

    conn = None
    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        cursor = conn.cursor()

        print(">> Ejecutando consulta sobre Vista_Tabla_Direcciones...")
        cursor.execute(SQL_DIRECCIONES)
        columnas = [column[0] for column in cursor.description]

        datos = []
        for row in cursor.fetchall():
            item = dict(zip(columnas, row))

            id_direccion_wo = item.get("IdTerceroDireccion")
            nit = str(item.get("Identificacion") or "").strip()
            if id_direccion_wo is None or not nit:
                continue

            datos.append({
                "id_direccion_wo": int(id_direccion_wo),
                "identificacion":  nit,
                "nombre":          str(item.get("Nombres_tercero") or "").strip(),
                "direccion":       str(item.get("Direccion") or "").strip(),
                "telefonos":       str(item.get("Telefonos") or "").strip(),
                "ciudad":          str(item.get("Ciudad") or "").strip(),
            })

        conn.close()

        print(f"[OK] Extraccion completada. {len(datos)} direcciones de clientes encontradas.")

        if not datos:
            print("[!] No se encontraron registros. Se aborta el envío (el backend además rechaza catálogos vacíos).")
            return

        print("\n>> Enviando datos a Render...")
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
            "X-Sync-Token": API_KEY,
        }

        enviar_datos(datos, API_URL, headers)
        print("[OK] Sincronización de clientes finalizada exitosamente.")

    except Exception as e:
        print(f"[FATAL] Error fatal en el proceso: {e}")
        sys.exit(1)
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_err:
                print(f"[INFO] La conexión a SQL Server ya estaba cerrada o no requiere cierre explícito: {close_err}")


def main():
    ejecutar_extraccion()


if __name__ == "__main__":
    main()
