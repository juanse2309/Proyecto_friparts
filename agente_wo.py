# -*- coding: utf-8 -*-
"""
Agente Sincronizador Local - World Office <-> FriTech
---------------------------------------------------
Este script se ejecuta localmente en la red on-premise de la empresa.
Extrae datos de la base de datos de SQL Server y los envía de forma segura
al endpoint de FriTech en la nube (Render).

Requisitos:
    pip install pyodbc requests python-dotenv

Ejecución:
    python agente_wo.py
"""

import os
import sys
import json
import logging
from decimal import Decimal
import datetime
import pyodbc
import requests
from dotenv import load_dotenv

# Cargar variables de entorno locales si existe un archivo .env
load_dotenv()

# Configurar logging local para monitoreo
# Forzar UTF-8 en la salida de consola (evita crash con emojis en Windows cp1252)
import io
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    ]
)
logger = logging.getLogger("AgenteWO")

# ====================================================================
# CONFIGURACIÓN DE CONEXIÓN Y SEGURIDAD
# ====================================================================
# Configuración de base de datos SQL Server (World Office)
DB_DRIVER = os.getenv("WO_DB_DRIVER", "{ODBC Driver 17 for SQL Server}")
DB_SERVER = os.getenv("WO_DB_SERVER", r"SERVERWO\WORLDOFFICE17")
DB_DATABASE = os.getenv("WO_DB_DATABASE", "FRIPARTS2021")
DB_UID = os.getenv("WO_DB_UID", "wo_cliente")
DB_PWD = os.getenv("WO_DB_PWD", "wo_cliente")

# URL de la API de FriTech en Render
# NOTA: Cambiar esta URL por la URL real de producción en Render cuando esté desplegado.
FRITECH_API_URL = os.getenv("FRITECH_API_URL", "https://proyecto-friparts.onrender.com/api/wo/recibir_datos")

# API Key para autenticar contra la app en la nube
WO_SYNC_API_KEY = os.getenv("WO_SYNC_API_KEY", "FriParts-WO-Sync-2026!")


# ====================================================================
# SERIALIZACIÓN PERSONALIZADA PARA JSON
# ====================================================================
class SQLServerJSONEncoder(json.JSONEncoder):
    """
    Encoder de JSON personalizado para manejar tipos de datos típicos de SQL Server:
    - Decimal (para valores monetarios o de precisión)
    - datetime / date
    - bytes
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        return super(SQLServerJSONEncoder, self).default(obj)


# ====================================================================
# FUNCIONES DE EXTRACT & SYNC
# ====================================================================
def probar_y_sincronizar_productos():
    """
    Realiza una extracción de prueba de 5 productos de la vista V_PRODUCTOS
    y los envía al backend en la nube.
    """
    # Construir el string de conexión a SQL Server
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        f"UID={DB_UID};"
        f"PWD={DB_PWD};"
        # Opciones recomendadas para redes locales/on-premise
        "Timeout=30;"
    )

    logger.info("📡 Iniciando proceso de sincronización local...")
    logger.info(f"🔑 Servidor SQL Server: {DB_SERVER}")
    logger.info(f"📂 Base de Datos: {DB_DATABASE}")
    logger.info(f"🌐 Enviando datos a: {FRITECH_API_URL}")

    conn = None
    try:
        # 1. Establecer conexión con la BD local
        logger.info("Conectando a la base de datos SQL Server de World Office...")
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # 2. PASO DIAGNÓSTICO: Leer las columnas reales de Vista_Existencias antes de ejecutar la query
        nombre_vista = "Vista_Existencias"
        logger.info("Inspeccionando columnas reales de Vista_Existencias...")
        cursor.execute("SELECT TOP 1 * FROM [FRIPARTS2021].[dbo].[Vista_Existencias]")
        columnas_reales = [col[0] for col in cursor.description]
        logger.info(f"[AUDITORIA] Columnas reales encontradas: {columnas_reales}")
        cursor.fetchall()  # Vaciar el cursor antes del siguiente query

        # 3. Auto-detectar el nombre de la columna de código e inventario
        # Buscar la columna que contenga 'codigo' o 'inventario' (case-insensitive)
        col_codigo = None
        col_stock = None
        for c in columnas_reales:
            cn = c.lower().replace('ó', 'o').replace('é', 'e').replace('á', 'a')
            if col_codigo is None and ('codigo' in cn or 'inventario' in cn or 'referencia' in cn or 'articulo' in cn):
                col_codigo = c
            if col_stock is None and ('existencia' in cn or 'stock' in cn or 'saldo' in cn or 'cantidad' in cn):
                col_stock = c

        if not col_codigo or not col_stock:
            logger.error(f"No se encontraron las columnas esperadas. Disponibles: {columnas_reales}")
            logger.error("Edita agente_wo.py y ajusta manualmente col_codigo y col_stock.")
            return False

        logger.info(f"[AUDITORIA] Columna de Codigo: '{col_codigo}' | Columna de Stock: '{col_stock}'")

        # 4. Ejecutar la consulta consolidada con SUM para agrupar por producto
        # Razón: la vista tiene una fila por bodega; sin GROUP BY los saldos en cero sobreescriben los reales.
        query = (
            f"SELECT [{col_codigo}] AS codigo_producto, "
            f"SUM([{col_stock}]) AS stock_wo "
            f"FROM [FRIPARTS2021].[dbo].[Vista_Existencias] "
            f"WHERE [{col_codigo}] IS NOT NULL "
            f"GROUP BY [{col_codigo}]"
        )
        logger.info(f"Ejecutando consulta: {query}")
        cursor.execute(query)

        # Mapear filas a una lista de diccionarios asegurando los tipos de datos
        registros = []
        for row in cursor.fetchall():
            codigo_val = str(row[0] or '').strip()
            if not codigo_val:
                continue
            try:
                stock_val = float(row[1])
            except (ValueError, TypeError):
                stock_val = 0.0
            registros.append({'codigo_producto': codigo_val, 'stock_wo': stock_val})

        logger.info(f"Extraccion exitosa. {len(registros)} registros obtenidos de Vista_Existencias.")
        
        # Cerrar conexión de base de datos
        cursor.close()
        conn.close()
        conn = None

        # 3. Enviar datos a la nube
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": WO_SYNC_API_KEY
        }
        
        # Envolver los datos agregando el nombre de la vista consultada
        payload = {
            "nombre_vista": nombre_vista,
            "datos": registros
        }
        
        # DEBUG LOCAL: Verificar que los datos tienen stock real antes de enviar
        print("MUESTRA DEL PAYLOAD A ENVIAR (primeros 5):")
        for item in registros[:5]:
            print(f"  Ref: {item.get('codigo_producto')} | stock_wo: {item.get('stock_wo')}")
        
        # Serializar los datos usando el encoder robusto
        payload_json = json.dumps(payload, cls=SQLServerJSONEncoder)
        
        logger.info(f"[DEBUG] URL de Envío Exacta: {FRITECH_API_URL}")
        logger.info(f"[DEBUG] Headers de Envío: {headers}")
        logger.info(f"[DEBUG] Tamaño del Payload: {len(payload_json)} bytes")
        
        try:
            logger.info(f"Enviando datos al servidor en la nube ({FRITECH_API_URL})...")
            response = requests.post(
                FRITECH_API_URL, 
                data=payload_json, 
                headers=headers,
                timeout=30
            )
            
            logger.info(f"[DEBUG] Código de Respuesta del Servidor: {response.status_code}")
            logger.info(f"[DEBUG] Respuesta Completa del Servidor: {response.text}")
            
            # 4. Procesar respuesta del servidor
            if response.status_code == 200:
                logger.info("🎉 ¡Sincronización exitosa!")
                return True
            elif response.status_code == 401:
                logger.error("❌ Error 401: No autorizado. Verifica la API Key (WO_SYNC_API_KEY).")
            else:
                logger.error(f"❌ Error en el servidor (Status {response.status_code})")
                
            return False
            
        except requests.exceptions.RequestException as e_net:
            logger.error(f"❌ Error de red / conexión al backend (requests.post falló): {e_net}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
    except pyodbc.Error as e_sql:
        logger.error(f"❌ Error de base de datos (SQL Server): {e_sql}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado en el agente de sincronización: {e}")
        return False
    finally:
        # Asegurar el cierre de la conexión en caso de falla
        if conn:
            try:
                conn.close()
                logger.info("Conexión de base de datos cerrada en cláusula cleanup.")
            except Exception:
                pass


if __name__ == '__main__':
    # Ejecutar la prueba
    exito = probar_y_sincronizar_productos()
    if exito:
        logger.info("Proceso terminado con éxito.")
        sys.exit(0)
    else:
        logger.error("Proceso terminado con errores.")
        sys.exit(1)
