import os
import pyodbc
import requests
import json
from dotenv import load_dotenv

# Cargar variables de entorno desde .env o el sistema
load_dotenv()

DB_SERVER = os.getenv("WO_SERVER", r"SERVERWO\WORLDOFFICE17")
DB_DATABASE = os.getenv("WO_DB", "FRIPARTS2021")
DB_UID = os.getenv("WO_USER", "wo_cliente")
DB_PWD = os.getenv("WO_PASSWORD", "wo_cliente")

API_URL = os.getenv("SYNC_API_URL", "http://172.16.1.109:5005")
SYNC_TOKEN = os.getenv("SYNC_TOKEN", "FriParts-WO-Sync-2026!")

conn_str = (
    f"DRIVER={{SQL Server}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_DATABASE};"
    f"UID={DB_UID};"
    f"PWD={DB_PWD};"
    "Timeout=60;"
)

def extraer_cartera():
    print(f"[*] Conectando a la base de datos de World Office ({DB_SERVER} -> {DB_DATABASE})...")
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        VALOR_MONEDA = os.getenv('FILTRO_MONEDA', 'USD')
        VALOR_EMPRESA = os.getenv('FILTRO_EMPRESA', 'FRIPARTS')

        # --- ESTRATEGIA HÍBRIDA: Extracción separada y Merge en Pandas ---
        print("\n" + "="*60)
        print("[*] INICIANDO EXTRACCIÓN Y HOMOLOGACIÓN EN MEMORIA (PANDAS)")
        print("="*60)
        
        import pandas as pd
        
        # 1. Extracción de Encabezados (Filtrado por Vendedor 431)
        print("\n[*] 1. Extrayendo encabezados para vendedor '431' (CARLOS FELIPE RICO NAVAS)...")
        query_encabezados = "SELECT Numero_de_Documento, Tipo_de_Documento, Nombre_Empresa FROM Vista_Tabla_Encabezados WHERE Elaborado_Vendedor = 431"
        cursor.execute(query_encabezados)
        cols_e = [col[0] for col in cursor.description]
        df_e = pd.DataFrame.from_records(cursor.fetchall(), columns=cols_e)
        print(f"[+] Registros de encabezados obtenidos: {len(df_e)}")
        
        # 2. Extracción de Cartera Detallada (Solo Activa)
        print("\n[*] 2. Extrayendo cartera activa detallada (Saldos > 0)...")
        query_detalle = "SELECT Documento, DocumentoNumero, Identificacion, Nombres_terceros, Saldo, Vencimiento FROM Vista_CuentasPorCobrar_Detallada WHERE Saldo > 0 AND DocumentoNumero IS NOT NULL"
        cursor.execute(query_detalle)
        cols_v = [col[0] for col in cursor.description]
        df_v = pd.DataFrame.from_records(cursor.fetchall(), columns=cols_v)
        print(f"[+] Registros de cartera obtenidos: {len(df_v)}")
        
        # 3. Normalización y Mapeo en Pandas
        print("\n[*] 3. Aplicando diccionario de homologación de documentos...")
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
        print("\n[*] 4. Cruzando datos (Merge)...")
        merged = pd.merge(
            df_v, 
            df_e, 
            left_on=['DocumentoNumero', 'Tipo_Mapeado'], 
            right_on=['Numero_de_Documento', 'Tipo_de_Documento'], 
            how='inner'
        )
        print(f"[+] Merge exitoso. Total de facturas cruzadas: {len(merged)}")
        
        # 5. Ensamblaje del JSON
        datos = []
        for _, row in merged.iterrows():
            fv = row.get('Vencimiento')
            fv_str = pd.to_datetime(fv).strftime('%Y-%m-%d') if pd.notnull(fv) else None
            
            datos.append({
                "documento": str(row.get('DocumentoNumero', 'N/A')).strip(),
                "identificacion": str(row.get('Identificacion', '')).strip(),
                "nombre": str(row.get('Nombres_terceros', '')).strip(),
                "vendedor": 'CARLOS FELIPE RICO NAVAS',
                "moneda": VALOR_MONEDA,
                "empresa": str(row.get('Nombre_Empresa', VALOR_EMPRESA)).strip(),
                "fecha_vencimiento": fv_str,
                "saldo_documento": str(row.get('Saldo', '0'))
            })
            
        conn.close()
        
        if not datos:
            print("[!] La extracción no arrojó registros para este vendedor tras el merge.")
            return

        print(f"\n[*] Extracción finalizada: {len(datos)} facturas activas preparadas.")
        print("[*] Enviando datos al backend de FRITECH...")
        
        if len(datos) > 0:
            print(f"[DEBUG] Ejemplo de registro a enviar: {json.dumps(datos[0], indent=2)}")
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": SYNC_TOKEN
        }
        
        endpoint = f"{API_URL}/api/wo/sincronizar_cartera"
        payload = {"datos": datos}
        
        response = requests.post(endpoint, json=payload, headers=headers)
        
        if response.status_code == 200:
            print(f"[+] Sincronización exitosa: {response.json().get('procesados')} registros procesados.")
        else:
            print(f"[-] Error en sincronización: HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"[-] Error crítico en el Agente de Cartera: {e}")

if __name__ == "__main__":
    extraer_cartera()
