import os
import sys
import io
import logging
import pyodbc
import requests
import json
from dotenv import load_dotenv

# Cargar variables de entorno desde .env o el sistema
load_dotenv()

# Log persistente en disco (mismo patrón que agente_wo.py): sin esto, la
# única prueba de que este agente corrió -- y si falló -- era la consola de
# la tarea programada, que nadie mira. Forzar UTF-8 evita crash con emojis
# en la consola cp1252 de Windows.
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agente_wo_cartera.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')),
        logging.FileHandler(_LOG_PATH, encoding='utf-8')
    ]
)
logger = logging.getLogger("AgenteWOCartera")

DB_DRIVER = os.getenv("WO_DB_DRIVER", "{ODBC Driver 17 for SQL Server}")
DB_SERVER = os.getenv("WO_SERVER", r"SERVERWO\WORLDOFFICE17")
DB_DATABASE = os.getenv("WO_DB", "FRIPARTS2021")
DB_UID = os.getenv("WO_USER", "wo_cliente")
DB_PWD = os.getenv("WO_PASSWORD")
if not DB_PWD:
    raise RuntimeError("WO_PASSWORD no está configurada")

API_URL = os.getenv("SYNC_API_URL", "https://proyecto-friparts.onrender.com")
SYNC_TOKEN = os.getenv("SYNC_TOKEN")
if not SYNC_TOKEN:
    raise RuntimeError("SYNC_TOKEN no está configurada")

conn_str = (
    f"DRIVER={DB_DRIVER};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_DATABASE};"
    f"UID={DB_UID};"
    f"PWD={DB_PWD};"
    "Timeout=60;"
)

def extraer_cartera():
    logger.info(f"[*] Conectando a la base de datos de World Office ({DB_SERVER} -> {DB_DATABASE})...")
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        VALOR_MONEDA = os.getenv('FILTRO_MONEDA', 'USD')
        VALOR_EMPRESA = os.getenv('FILTRO_EMPRESA', 'FRIPARTS')

        # --- ESTRATEGIA HÍBRIDA: Extracción separada y Merge en Pandas ---
        logger.info("=" * 60)
        logger.info("[*] INICIANDO EXTRACCIÓN Y HOMOLOGACIÓN EN MEMORIA (PANDAS)")
        logger.info("=" * 60)

        import pandas as pd

        # 1. Extracción de Encabezados (TODOS los vendedores, sin filtrar)
        logger.info("[*] 1. Extrayendo encabezados de TODOS los vendedores (visualización comercial global)...")
        query_encabezados = "SELECT Numero_de_Documento, Tipo_de_Documento, Nombre_Empresa, Nombres_tercero_interno, Fecha FROM Vista_Tabla_Encabezados"
        cursor.execute(query_encabezados)
        cols_e = [col[0] for col in cursor.description]
        df_e = pd.DataFrame.from_records(cursor.fetchall(), columns=cols_e)
        logger.info(f"[+] Registros de encabezados obtenidos: {len(df_e)}")

        # 2. Extracción de Cartera Detallada (Solo Activa)
        logger.info("[*] 2. Extrayendo cartera activa detallada (Saldos > 0)...")
        query_detalle = "SELECT Documento, DocumentoNumero, Identificacion, Nombres_terceros, Saldo, Vencimiento FROM Vista_CuentasPorCobrar_Detallada WHERE Saldo > 0 AND DocumentoNumero IS NOT NULL"
        cursor.execute(query_detalle)
        cols_v = [col[0] for col in cursor.description]
        df_v = pd.DataFrame.from_records(cursor.fetchall(), columns=cols_v)
        logger.info(f"[+] Registros de cartera obtenidos: {len(df_v)}")

        # 3. Normalización y Mapeo en Pandas
        logger.info("[*] 3. Aplicando diccionario de homologación de documentos...")
        mapeo_docs = {
            'FACTURA DE VENTA': 'FV',
            'FACTURA ELECTRONICA': 'FE',
            'COMPROBANTE DE EGRESO': 'CE',
            'NOTA DEBITO': 'ND',
            'SALDOS INICIALES': 'SI'
        }
        
        # Limpiar espacios y estandarizar a mayúsculas
        df_v['Documento'] = df_v['Documento'].astype(str).str.strip().str.upper()
        df_e['Tipo_de_Documento'] = df_e['Tipo_de_Documento'].astype(str).str.strip().str.upper()
        
        # Aplicar el diccionario al detalle de cartera
        df_v['Tipo_Mapeado'] = df_v['Documento'].map(mapeo_docs).fillna(df_v['Documento'])
        
        # Convertir números de documento a string para merge seguro
        df_v['DocumentoNumero'] = df_v['DocumentoNumero'].astype(str).str.strip()
        df_e['Numero_de_Documento'] = df_e['Numero_de_Documento'].astype(str).str.strip()
        
        # 4. Merge Seguro
        logger.info("[*] 4. Cruzando datos (Merge)...")
        merged = pd.merge(
            df_v,
            df_e,
            left_on=['DocumentoNumero', 'Tipo_Mapeado'],
            right_on=['Numero_de_Documento', 'Tipo_de_Documento'],
            how='inner'
        )
        logger.info(f"[+] Merge exitoso. Total de facturas cruzadas: {len(merged)}")
        
        # 5. Ensamblaje del JSON
        datos = []
        for _, row in merged.iterrows():
            fv = row.get('Vencimiento')
            fv_str = pd.to_datetime(fv).strftime('%Y-%m-%d') if pd.notnull(fv) else None

            fe = row.get('Fecha')
            fe_str = pd.to_datetime(fe).strftime('%Y-%m-%d') if pd.notnull(fe) else None

            datos.append({
                "documento": str(row.get('DocumentoNumero', 'N/A')).strip(),
                "identificacion": str(row.get('Identificacion', '')).strip(),
                "nombre": str(row.get('Nombres_terceros', '')).strip(),
                "vendedor": str(row.get('Nombres_tercero_interno', '') or '').strip(),
                "moneda": VALOR_MONEDA,
                "empresa": str(row.get('Nombre_Empresa', VALOR_EMPRESA)).strip(),
                "fecha_emision": fe_str,
                "fecha_vencimiento": fv_str,
                "saldo_documento": str(row.get('Saldo', '0'))
            })
            
        conn.close()

        if not datos:
            logger.warning("[!] La extracción no arrojó registros para este vendedor tras el merge.")
            return

        logger.info(f"[*] Extracción finalizada: {len(datos)} facturas activas preparadas.")
        logger.info("[*] Enviando datos al backend de FRITECH...")

        if len(datos) > 0:
            logger.debug(f"[DEBUG] Ejemplo de registro a enviar: {json.dumps(datos[0], indent=2)}")

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": SYNC_TOKEN
        }

        endpoint = f"{API_URL}/api/wo/sincronizar_cartera"
        payload = {"datos": datos}

        response = requests.post(endpoint, json=payload, headers=headers, timeout=60)

        if response.status_code in (200, 202):
            # El servidor ahora acepta y procesa en background (HTTP 202);
            # ya no devuelve 'procesados' en la respuesta inmediata.
            logger.info(f"[+] Sincronización aceptada por el servidor (HTTP {response.status_code}): {response.json().get('message', '')}")
        else:
            logger.error(f"[-] Error en sincronización: HTTP {response.status_code}")
            logger.error(response.text)

    except Exception as e:
        logger.error(f"[-] Error crítico en el Agente de Cartera: {e}")

if __name__ == "__main__":
    extraer_cartera()
