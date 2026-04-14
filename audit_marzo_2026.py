
import os
import sys
from datetime import datetime
from collections import defaultdict

# Añadir el path del proyecto para importar las utilidades
sys.path.append(os.getcwd())

from backend.core.database import sheets_client

def clean_number(val):
    if not val: return 0
    try:
        s = str(val).replace('.', '').replace(',', '').strip()
        return int(s) if s else 0
    except: return 0

def clean_currency(val):
    if not val: return 0.0
    try:
        s = str(val).replace('$', '').replace('.', '').replace(',', '').strip()
        return float(s) if s else 0.0
    except: return 0.0

def run_audit():
    print("🔍 Iniciando Auditoría de RAW_VENTAS para Marzo 2026...")
    ws = sheets_client.get_worksheet("RAW_VENTAS")
    if not ws:
        print("❌ No se encontró la hoja RAW_VENTAS")
        return

    raw_values = ws.get_all_values()
    headers = raw_values[0]
    print(f"📋 Cabeceras encontradas: {headers}")
    print(f"📏 Columnas totales: {len(headers)}")

    marzo_rows = []
    
    # 1. Filtrar Marzo 2026
    for i in range(1, len(raw_values)):
        row = raw_values[i]
        if len(row) < 3: continue
        
        fecha_str = row[2].strip()
        dt_obj = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                dt_obj = datetime.strptime(fecha_str, fmt)
                break
            except: continue
        
        if dt_obj and dt_obj.year == 2026 and dt_obj.month == 3:
            marzo_rows.append(row)

    print(f"📅 Registros encontrados en Marzo 2026: {len(marzo_rows)}")

    total_actual_pedidos = 0.0
    total_propuesto_pedidos = 0.0
    
    ventas_samples = []
    pedidos_samples = []
    saltados_samples = []

    for row in marzo_rows:
        # Lógica Actual: Index 7 (Clasificacion)
        clasificacion = row[7].strip().lower() if len(row) > 7 else ""
        es_pedido_actual = "pedido" in clasificacion
        
        # Lógica Propuesta: Index 8 (Tipo)
        tipo = row[8].strip() if len(row) > 8 else ""
        es_pedido_propuesto = tipo.capitalize() == "Pedidos"
        
        valor = clean_currency(row[5]) if len(row) > 5 else 0.0

        if es_pedido_actual:
            total_actual_pedidos += valor
            if len(pedidos_samples) < 5:
                pedidos_samples.append(row)
        else:
            if len(ventas_samples) < 5:
                ventas_samples.append(row)
        
        if es_pedido_propuesto:
            total_propuesto_pedidos += valor
            if not es_pedido_actual:
                if len(saltados_samples) < 10:
                    saltados_samples.append(row)

    print("\n--- RESULTADOS TOTALES ---")
    print(f"💰 Total Pedidos (Lógica Actual - Index 7): ${total_actual_pedidos:,.2f}")
    print(f"💰 Total Pedidos (Lógica Propuesta - Index 8): ${total_propuesto_pedidos:,.2f}")
    print(f"📊 Diferencia: ${total_propuesto_pedidos - total_actual_pedidos:,.2f}")

    print("\n--- MUESTRA: PEDIDOS DETECTADOS (Lógica Actual) ---")
    for r in pedidos_samples:
        t = r[8] if len(r) > 8 else "N/A"
        print(f"Row: {r[0:3]} | Col7: {r[7]} | Col8: {t} | Total: {r[5]}")

    print("\n--- MUESTRA: VENTAS DETECTADOS (Lógica Actual) ---")
    for r in ventas_samples:
        t = r[8] if len(r) > 8 else "N/A"
        print(f"Row: {r[0:3]} | Col7: {r[7]} | Col8: {t} | Total: {r[5]}")

    print("\n--- MUESTRA: REGISTROS 'SALTADOS' (Están en Col8 como Pedidos pero no en Col7) ---")
    if not saltados_samples:
        print("No se encontraron registros saltados bajo estas condiciones.")
    for r in saltados_samples:
        print(f"Row: {r[0:3]} | Col7: {r[7]} | Col8: {r[8]} | Total: {r[5]}")

if __name__ == "__main__":
    run_audit()
