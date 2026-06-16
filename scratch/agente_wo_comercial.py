import os
import pyodbc
import requests
import json
from datetime import datetime

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

def ejecutar_extraccion():
    print("=" * 60)
    print("[>>] INICIANDO EXTRACCION COMERCIAL (AÑO ACTUAL) DESDE WO")
    print("=" * 60)
    
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
          AND E.Tipo_de_Documento IN ('FV', 'PED')
          AND E.Anulado = 0
          AND D.Cantidad > 0;
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
            
            # Mapeo de Clasificación
            tipo_doc = item.get('tipo_doc', '').strip()
            if tipo_doc == 'FV':
                item['clasificacion'] = 'venta'
                total_ventas += float(item.get('total_ingresos', 0))
            elif tipo_doc == 'PED':
                item['clasificacion'] = 'pedido'
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
        print("\n>> Enviando datos a Render...")
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
            "X-Sync-Token": API_KEY
        }
        
        payload = {"datos": datos}
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            print("[OK] Sincronizacion comercial exitosa.")
            print(response.json())
        else:
            print(f"[ERROR] Error al sincronizar. Codigo HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"[FATAL] Error fatal en el proceso: {e}")

if __name__ == "__main__":
    ejecutar_extraccion()
