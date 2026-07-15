# -*- coding: utf-8 -*-
"""
Agente Sincronizador Local Comercial - World Office <-> FriTech
-------------------------------------------------------------
Este script se ejecuta localmente en la red on-premise de la empresa.
Extrae los datos comerciales de ventas (FV), pedidos (PD) y devoluciones (NC) del año actual
de la base de datos de SQL Server de World Office y los envía al endpoint
de FriTech en la nube (Render).

Requisitos:
    pip install pyodbc requests python-dotenv

Ejecución:
    python agente_wo_comercial.py
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

# Configurar logging local
import io
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    ]
)
logger = logging.getLogger("AgenteWOComercial")

# ====================================================================
# CONFIGURACIÓN DE CONEXIÓN Y SEGURIDAD
# ====================================================================
DB_DRIVER = os.getenv("WO_DB_DRIVER", "{SQL Server}")
DB_SERVER = os.getenv("WO_DB_SERVER", r"SERVERWO\WORLDOFFICE17")
DB_DATABASE = os.getenv("WO_DB_DATABASE", "FRIPARTS2021")
DB_UID = os.getenv("WO_DB_UID", "wo_cliente")
DB_PWD = os.getenv("WO_DB_PWD", "wo_cliente")

# URLs de la API de FriTech en Render
FRITECH_API_URL = os.getenv("FRITECH_API_URL", "https://proyecto-friparts.onrender.com/api/wo/recibir_datos")
FRITECH_COMERCIAL_API_URL = os.getenv("FRITECH_COMERCIAL_API_URL")

if not FRITECH_COMERCIAL_API_URL:
    if "recibir_datos" in FRITECH_API_URL:
        FRITECH_COMERCIAL_API_URL = FRITECH_API_URL.replace("recibir_datos", "recibir_comercial")
    else:
        FRITECH_COMERCIAL_API_URL = "https://proyecto-friparts.onrender.com/api/wo/recibir_comercial"

# API Key para autenticar contra la app en la nube
WO_SYNC_API_KEY = os.getenv("WO_SYNC_API_KEY", "FriParts-WO-Sync-2026!")


# ====================================================================
# SERIALIZACIÓN PERSONALIZADA PARA JSON
# ====================================================================
class SQLServerJSONEncoder(json.JSONEncoder):
    """
    Encoder de JSON personalizado para manejar tipos de datos típicos de SQL Server.
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
def sincronizar_datos_comerciales():
    """
    Extrae los datos comerciales de ventas, pedidos y devoluciones del año actual 
    de World Office y los envía al backend en Render.
    """
    # Obtener parámetros de entorno
    driver_env = os.getenv("WO_DB_DRIVER", "{ODBC Driver 17 for SQL Server}")
    server_env = os.getenv("WO_DB_SERVER", r"SERVERWO\WORLDOFFICE17")
    db_env = os.getenv("WO_DB_DATABASE", "FRIPARTS2021")
    uid_env = os.getenv("WO_DB_UID", "wo_cliente")
    pwd_env = os.getenv("WO_DB_PWD", "wo_cliente")

    # Lista de cadenas de conexión para intentar de forma robusta
    cadenas_conexion = [
        {
            "nombre": "ODBC Driver 17 (Trusted Connection)",
            "str": f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_env};DATABASE={db_env};Trusted_Connection=yes;Timeout=30;"
        },
        {
            "nombre": "SQL Server Legacy (Trusted Connection)",
            "str": f"DRIVER={{SQL Server}};SERVER={server_env};DATABASE={db_env};Trusted_Connection=yes;Timeout=30;"
        },
        {
            "nombre": "SQL Server Legacy (Con Credenciales de agente_wo.py)",
            "str": f"DRIVER={{SQL Server}};SERVER={server_env};DATABASE={db_env};UID={uid_env};PWD={pwd_env};Timeout=30;"
        },
        {
            "nombre": "ODBC Driver 17 (Con Credenciales)",
            "str": f"DRIVER={driver_env};SERVER={server_env};DATABASE={db_env};UID={uid_env};PWD={pwd_env};Timeout=30;"
        }
    ]

    logger.info("📡 Iniciando proceso de sincronización comercial...")
    logger.info(f"🔑 Servidor SQL Server: {server_env}")
    logger.info(f"📂 Base de Datos: {db_env}")
    logger.info(f"🌐 Enviando datos a: {FRITECH_COMERCIAL_API_URL}")

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
        logger.critical("❌ Todos los intentos de conexión SQL Server fallaron.")
        try:
            available_drivers = pyodbc.drivers()
            logger.info(f"🔍 Drivers ODBC disponibles en este equipo: {available_drivers}")
        except Exception as e_drv:
            logger.error(f"No se pudo consultar pyodbc.drivers(): {e_drv}")
        return False

    try:
        cursor = conn.cursor()

        # 1. Crear Diccionario de Mapeo en Memoria (Catálogo Maestro)
        logger.info("Cargando catálogo maestro de inventarios en memoria...")
        cursor.execute("SELECT Autonumerico, Codigo_Producto FROM [FRIPARTS2021].[dbo].[Vista_Tabla_Inventarios]")
        mapping = {}
        for row in cursor.fetchall():
            mapping[str(row[0])] = row[1]

        sql_query = """
        SELECT 
            E.Fecha AS fecha,
            (E.prefijo + '-' + CAST(E.Numero_de_Documento AS VARCHAR)) AS documento,
            E.Nombre_tercero_externo AS nombres,
            D.Producto AS productos, -- ESTE ES EL ID QUE USAREMOS PARA EL MAPEO
            CAST(D.Cantidad AS FLOAT) AS cantidad,
            CAST((D.Cantidad * D.Valor_Unitario * (1 - (D.Descuento/100.0))) AS FLOAT) AS total_ingresos,
            CAST(D.Valor_Unitario AS FLOAT) AS precio_promedio,
            E.Tipo_de_Documento AS tipo_doc
        FROM [FRIPARTS2021].[dbo].[Vista_Tabla_Encabezados] E
        INNER JOIN [FRIPARTS2021].[dbo].[Vista_Tabla_Movimientos_Inventario] D 
            ON E.Autonumerico = D.Pertenece_A
        WHERE YEAR(E.Fecha) >= YEAR(GETDATE()) - 1
          AND E.Tipo_de_Documento IN ('FV', 'PED', 'COT', 'NC', 'NCV', 'NCCL')
          AND E.Anulado = 0;
        """

        logger.info("Ejecutando consulta comercial SQL Server...")
        cursor.execute(sql_query)
        
        registros = []
        cant_pd = 0
        cant_fv = 0
        cant_nc = 0
        total_ingresos_fv = 0.0

        # Obtener columnas descriptivas
        columns = [column[0] for column in cursor.description]

        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            
            # Sanitizar ingresos/subtotal
            subtotal = row_dict.get('total_ingresos') or 0.0
            try:
                subtotal_f = float(subtotal)
            except (ValueError, TypeError):
                subtotal_f = 0.0
            
            # Mapeo de Clasificación y Ajuste Matemático
            tipo_doc = row_dict.get('tipo_doc', '').strip()
            
            if tipo_doc == 'PED':
                row_dict['clasificacion'] = 'pedido'
                cant_pd += 1
            elif tipo_doc in ['FV', 'COT', 'NC', 'NCV', 'NCCL']:
                row_dict['clasificacion'] = 'venta'
                
                # Ajuste matemático para devoluciones/notas crédito
                if tipo_doc in ['NC', 'NCV', 'NCCL']:
                    # Se asume que total_ingresos viene en positivo, lo volvemos negativo
                    subtotal_f = subtotal_f * -1
                    row_dict['total_ingresos'] = subtotal_f
                    cant_nc += 1
                
                # Para el control de seguridad local (solo FV suma al control)
                if tipo_doc == 'FV':
                    cant_fv += 1
                    total_ingresos_fv += subtotal_f
                elif tipo_doc == 'COT':
                    # Opcional, lo sumamos a cant_fv localmente para mantener el log consistente
                    cant_fv += 1
            else:
                row_dict['clasificacion'] = 'desconocido'
                
            # Mapeo de Producto en Memoria (POLÍTICA FAIL-FAST sin Fallback)
            prod_id = str(row_dict.get('productos', '')).strip()
            mapped_prod = mapping.get(prod_id)
            
            if not mapped_prod or str(mapped_prod).strip() == "":
                error_msg = f"Fallo de Mapeo: Producto con ID Interno '{prod_id}' no tiene SKU real. Documento: {row_dict.get('documento', 'N/A')}. Omitiendo."
                logger.warning(error_msg)
                with open("sync_errors.log", "a", encoding="utf-8") as f_err:
                    f_err.write(f"{datetime.datetime.now()} - {error_msg}\n")
                continue
                
            row_dict['productos'] = str(mapped_prod).strip()

            registros.append(row_dict)

        logger.info(f"Extracción completada: {len(registros)} registros encontrados.")
        logger.info(f"Desglose: {cant_pd} pedidos (PD), {cant_fv} ventas (FV), {cant_nc} devoluciones (NC).")
        
        # ====================================================================
        # FRENO DE SEGURIDAD CONTABLE
        # ====================================================================
        print("\n" + "="*80)
        print(" [SECURITY] FRENO DE SEGURIDAD - AUDITORÍA FINANCIERA")
        print(f" TOTAL DE INGRESOS CALCULADO PARA VENTAS ('FV'): ${total_ingresos_fv:,.2f}")
        print(" POR FAVOR, VALIDE ESTE NÚMERO CONTRA EL BALANCE DE WORLD OFFICE ANTES DE VALIDAR LOS REPORTES EN EL B2B.")
        print("="*80 + "\n")

        cursor.close()
        conn.close()
        conn = None

        if not registros:
            logger.warning("No se encontraron registros comerciales válidos para el año actual. Cancelando envío.")
            return True

        # Preparar envío HTTP
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": WO_SYNC_API_KEY
        }

        payload = {
            "nombre_vista": "Vista_Documentos_Detalle",
            "datos": registros
        }

        payload_json = json.dumps(payload, cls=SQLServerJSONEncoder)

        logger.info(f"[DEBUG] Tamaño del Payload: {len(payload_json)} bytes")

        import time as _time
        MAX_INTENTOS = 3
        for intento in range(1, MAX_INTENTOS + 1):
            try:
                logger.info(f"Enviando datos al servidor (intento {intento}/{MAX_INTENTOS})...")
                response = requests.post(
                    FRITECH_COMERCIAL_API_URL,
                    data=payload_json,
                    headers=headers,
                    timeout=90
                )

                logger.info(f"[DEBUG] Código de Respuesta del Servidor: {response.status_code}")
                logger.info(f"[DEBUG] Respuesta Completa del Servidor: {response.text}")

                if response.status_code == 200:
                    logger.info("🎉 ¡Sincronización comercial exitosa!")
                    return True
                elif response.status_code == 401:
                    logger.error("Error 401: No autorizado. Verifica la API Key (WO_SYNC_API_KEY).")
                    return False
                elif response.status_code == 400:
                    logger.error(f"Error 400 (datos inválidos): {response.text}")
                    return False
                else:
                    logger.warning(f"Error en el servidor (Status {response.status_code}). Reintentando...")

            except requests.exceptions.RequestException as e_net:
                logger.warning(f"Error de red (intento {intento}): {e_net}")

            if intento < MAX_INTENTOS:
                espera = 5 * intento
                logger.info(f"Esperando {espera}s antes del siguiente intento...")
                _time.sleep(espera)

        logger.error(f"Fallaron los {MAX_INTENTOS} intentos de envío al servidor.")
        return False

    except pyodbc.Error as e_sql:
        logger.error(f"❌ Error de base de datos (SQL Server): {e_sql}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado en el agente comercial: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
                logger.info("Conexión de base de datos cerrada.")
            except Exception:
                pass


if __name__ == '__main__':
    exito = sincronizar_datos_comerciales()
    if exito:
        logger.info("Proceso comercial terminado con éxito.")
        sys.exit(0)
    else:
        logger.error("Proceso comercial terminado con errores.")
        sys.exit(1)
