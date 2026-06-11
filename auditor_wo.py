# -*- coding: utf-8 -*-
"""
Auditor Estructural de Base de Datos - World Office
--------------------------------------------------
Este script se conecta a la base de datos de World Office y extrae
el catálogo completo de vistas y tablas disponibles.
Ayuda a identificar el nombre exacto de las vistas o tablas comerciales.

Requisitos:
    pip install pyodbc python-dotenv
"""

import os
import sys
import logging
import pyodbc
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
import io
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    ]
)
logger = logging.getLogger("AuditorWO")

def realizar_auditoria():
    server_env = os.getenv("WO_DB_SERVER", r"SERVERWO\WORLDOFFICE17")
    db_env = os.getenv("WO_DB_DATABASE", "FRIPARTS2021")
    uid_env = os.getenv("WO_DB_UID", "wo_cliente")
    pwd_env = os.getenv("WO_DB_PWD", "wo_cliente")
    driver_env = os.getenv("WO_DB_DRIVER", "{SQL Server}")

    # Cadenas de conexión para intentar
    cadenas_conexion = [
        {
            "nombre": "SQL Server Legacy (Con Credenciales)",
            "str": f"DRIVER={{SQL Server}};SERVER={server_env};DATABASE={db_env};UID={uid_env};PWD={pwd_env};Timeout=30;"
        },
        {
            "nombre": "ODBC Driver 17 (Con Credenciales)",
            "str": f"DRIVER={driver_env};SERVER={server_env};DATABASE={db_env};UID={uid_env};PWD={pwd_env};Timeout=30;"
        },
        {
            "nombre": "SQL Server Legacy (Trusted Connection)",
            "str": f"DRIVER={{SQL Server}};SERVER={server_env};DATABASE={db_env};Trusted_Connection=yes;Timeout=30;"
        },
        {
            "nombre": "ODBC Driver 17 (Trusted Connection)",
            "str": f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_env};DATABASE={db_env};Trusted_Connection=yes;Timeout=30;"
        }
    ]

    conn = None
    for opcion in cadenas_conexion:
        try:
            logger.info(f"Intentando conectar con {opcion['nombre']}...")
            conn = pyodbc.connect(opcion["str"])
            logger.info(f"✅ Conectado exitosamente usando: {opcion['nombre']}")
            break
        except pyodbc.Error as e_conn:
            logger.warning(f"⚠️ Intento fallido con {opcion['nombre']}. Detalles: {e_conn}")

    if not conn:
        logger.critical("❌ Todos los intentos de conexión fallaron.")
        try:
            logger.info(f"🔍 Drivers ODBC disponibles: {pyodbc.drivers()}")
        except Exception as e_drv:
            logger.error(f"No se pudo consultar pyodbc.drivers(): {e_drv}")
        return False

    try:
        cursor = conn.cursor()
        print("\n" + "="*80)
        print("🔍 INICIANDO AUDITORÍA ESTRUCTURAL EN WORLD OFFICE")
        print(f"Base de Datos: {db_env}")
        print("="*80 + "\n")

        # 1. Obtener todas las VISTAS
        print("--- 📋 VISTAS DISPONIBLES ---")
        cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS ORDER BY TABLE_NAME")
        vistas = cursor.fetchall()
        for row in vistas:
            print(f"  [Vista] {row.TABLE_SCHEMA}.{row.TABLE_NAME}")
        
        print(f"\nTotal Vistas: {len(vistas)}")

        # 2. Obtener todas las TABLAS
        print("\n--- 🗄️ TABLAS BASE DISPONIBLES ---")
        cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
        tablas = cursor.fetchall()
        for row in tablas:
            print(f"  [Tabla] {row.TABLE_SCHEMA}.{row.TABLE_NAME}")

        print(f"\nTotal Tablas Base: {len(tablas)}")

        # 3. Búsqueda inteligente de posibles candidatos para facturas, pedidos y detalles
        print("\n" + "="*80)
        print("🎯 BÚSQUEDA DE CANDIDATOS POTENCIALES (DOCUMENTOS / DETALLES / COMERCIAL / VENTAS)")
        print("="*80)
        
        palabras_clave = ["documento", "detalle", "venta", "factura", "pedido", "comercial", "movimiento", "transaccion", "vista", "v_"]
        candidatos = []
        
        # Filtrar vistas y tablas
        for schema, name in [(v.TABLE_SCHEMA, v.TABLE_NAME) for v in vistas] + [(t.TABLE_SCHEMA, t.TABLE_NAME) for t in tablas]:
            name_lower = name.lower()
            if any(pc in name_lower for pc in palabras_clave):
                candidatos.append(f"{schema}.{name}")

        if candidatos:
            for c in sorted(candidatos):
                print(f"  ⭐ Candidato: {c}")
        else:
            print("  No se encontraron coincidencias directas en los nombres.")

        print("\n✅ Auditoría de esquema completada con éxito.")
        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error durante la extracción de metadatos: {e}")
        if conn:
            conn.close()
        return False

if __name__ == '__main__':
    realizar_auditoria()
