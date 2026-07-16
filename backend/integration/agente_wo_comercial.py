import os
import pyodbc
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno locales si existe un archivo .env (y para que tome el token correcto)
load_dotenv()

# ====================================================================
# CONFIGURACIÓN DE CONEXIÓN Y SEGURIDAD
# ====================================================================
DB_DRIVER   = os.getenv("WO_DB_DRIVER",  "{ODBC Driver 17 for SQL Server}")
DB_SERVER   = os.getenv("WO_SERVER",     r"SERVERWO\WORLDOFFICE17")
DB_DATABASE = os.getenv("WO_DB",         "FRIPARTS2021")
DB_UID      = os.getenv("WO_USER",       "wo_cliente")
DB_PWD      = os.getenv("WO_PASSWORD",   "wo_cliente")

API_URL = os.getenv("API_RENDER_URL_COMERCIAL", "https://proyecto-friparts.onrender.com/api/wo/recibir_comercial")
API_KEY = os.getenv("WO_SYNC_API_KEY", "FriParts-WO-Sync-2026!")

# Construir el string de conexión a SQL Server exactamente como en agente_wo.py
conn_str = (
    f"DRIVER={{SQL Server}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_DATABASE};"
    f"UID={DB_UID};"
    f"PWD={DB_PWD};"
    # Opciones recomendadas para redes locales/on-premise
    "Timeout=30;"
)

CHUNK_SIZE = 2000

def enviar_datos_por_lotes(datos, url_api, headers):
    """
    Divide el payload masivo en lotes pequeños para evitar 
    timeouts en Render y locks en PostgreSQL.
    """
    total_registros = len(datos)
    for i in range(0, total_registros, CHUNK_SIZE):
        lote = datos[i:i + CHUNK_SIZE]
        payload = {
            "is_chunk": True,
            "index": i // CHUNK_SIZE,
            "total_chunks": (total_registros + CHUNK_SIZE - 1) // CHUNK_SIZE,
            "data": lote
        }
        
        try:
            # Enviamos cada lote con un timeout prudente
            response = requests.post(url_api, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            print(f"[OK] Lote {(i // CHUNK_SIZE) + 1}/{(total_registros + CHUNK_SIZE - 1) // CHUNK_SIZE} enviado correctamente.")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Falló el envío del lote {i // CHUNK_SIZE}: {e}")
            if e.response is not None:
                print(e.response.text)
            raise e

def ejecutar_extraccion():
    print("=" * 60)
    print("[>>] INICIANDO EXTRACCION COMERCIAL (AÑO ACTUAL) DESDE WO")
    print("=" * 60)
    
    conn = None
    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        cursor = conn.cursor()
        
        # 1. Crear Diccionario de Mapeo en Memoria (Catálogo Maestro)
        print(">> Cargando catálogo maestro de inventarios en memoria...")
        cursor.execute("SELECT Autonumerico, Codigo_Producto FROM [FRIPARTS2021].[dbo].[Vista_Tabla_Inventarios]")
        mapping = {}
        for row in cursor.fetchall():
            # Autonumerico puede venir como numérico o string, lo forzamos a string para cruzar
            mapping[str(row[0])] = row[1]
            
        # 2. Consulta SQL Definitiva simplificada
        sql = """
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
        
        print(">> Ejecutando consulta SQL...")
        cursor.execute(sql)
        
        columnas = [column[0] for column in cursor.description]
        datos = []
        total_ventas = 0.0
        
        for row in cursor.fetchall():
            item = dict(zip(columnas, row))
            
            # Formatear la fecha para que sea serializable en JSON
            if item['fecha']:
                item['fecha'] = item['fecha'].strftime('%Y-%m-%d')
            
            # Mapeo de Clasificación y Ajuste Matemático
            tipo_doc = item.get('tipo_doc', '').strip()
            
            if tipo_doc == 'PED':
                item['clasificacion'] = 'pedido'
            elif tipo_doc in ['FV', 'COT', 'NC', 'NCV', 'NCCL']:
                item['clasificacion'] = 'venta'
                
                # Ajuste matemático para devoluciones/notas crédito
                if tipo_doc in ['NC', 'NCV', 'NCCL']:
                    # Se asume que total_ingresos viene en positivo, lo volvemos negativo
                    item['total_ingresos'] = float(item.get('total_ingresos', 0)) * -1
                
                # Para el control de seguridad local (solo FV suma al control)
                if tipo_doc == 'FV':
                    total_ventas += float(item.get('total_ingresos', 0))
            else:
                item['clasificacion'] = 'desconocido'
            # Mapeo de Producto en Memoria
            prod_id = str(item.get('productos', '')).strip()
            # Buscar en el diccionario el código real, si no lo halla, usar el original
            mapped_prod = mapping.get(prod_id, prod_id)
            
            # Priorización de datos reales: asignamos exactamente lo que devolvió el mapeo (o el original si falló) sin prefijos inventados
            item['productos'] = str(mapped_prod or '').strip()
            
            # Eliminar la columna tipo_doc original
            if 'tipo_doc' in item:
                del item['tipo_doc']
                
            datos.append(item)
            
        conn.close()
        
        print(f"[OK] Extraccion completada. {len(datos)} registros encontrados.")
        
        # 🔒 FRENO DE SEGURIDAD OBLIGATORIO
        print("\n" + "=" * 60)
        print(f"[SECURITY] FRENO DE SEGURIDAD - AUDITORIA FINANCIERA:")
        print(f"   TOTAL VENTAS (FEV) = $ {total_ventas:,.2f}")
        print("=" * 60)
        
        import sys
        is_auto = "--auto" in sys.argv or os.getenv("AUTO_SYNC") == "True"
        if not is_auto:
            confirmacion = input("\nPresiona ENTER para enviar los datos a Render (o Ctrl+C para cancelar)...")
        else:
            print("\n[INFO] Modo automático detectado. Omitiendo freno de seguridad manual...")
        
        # Envío POST
        print("\n>> Enviando datos a Render por lotes...")
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
            "X-Sync-Token": API_KEY
        }
        
        enviar_datos_por_lotes(datos, API_URL, headers)
        print("[OK] Sincronización comercial finalizada exitosamente.")
            
    except Exception as e:
        print(f"[FATAL] Error fatal en el proceso: {e}")
        sys.exit(1)
    finally:
        # Garantía de cierre de recursos: Cero fugas de sockets en SQL Server
        if 'conn' in locals() and conn:
            try:
                conn.close()
                print("[INFO] Conexión a SQL Server cerrada limpiamente.")
            except Exception as close_err:
                print(f"[INFO] La conexión a SQL Server ya estaba cerrada o no requiere cierre explícito: {close_err}")

def main():
    import sys
    modo_forzado = "--forzar" in sys.argv
    
    check_url = "https://proyecto-friparts.onrender.com/api/wo/verificar_sync"
    sync_requerida = False
    
    print(f"Verificando si hay solicitud de sincronización en el servidor...")
    try:
        resp = requests.get(check_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("sync_pendiente"):
                print("[>>] Solicitud de sincronización pendiente detectada.")
                sync_requerida = True
            else:
                print("[>>] No hay solicitud pendiente.")
        else:
            print(f"[WARN] No se pudo verificar el flag (HTTP {resp.status_code}).")
    except Exception as e:
        print(f"[WARN] Error al conectar con el servidor para verificar flag: {e}")
        
    if sync_requerida or modo_forzado or ("--auto" in sys.argv):
        if sync_requerida:
            os.environ["AUTO_SYNC"] = "True"
            
        ejecutar_extraccion()
        
        if sync_requerida:
            print(">> Limpiando flag de sincronización en el servidor...")
            try:
                requests.post("https://proyecto-friparts.onrender.com/api/wo/solicitar_sync", json={"sync_pendiente": False}, timeout=10)
                print("[OK] Flag limpio.")
            except Exception as e:
                print(f"[WARN] No se pudo limpiar el flag: {e}")
    else:
        print("[>>] Ejecución cancelada. Usa --forzar o --auto para extraer de todas formas.")

if __name__ == "__main__":
    main()
