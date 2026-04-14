
import os
import sys
from datetime import datetime

# Añadir el path del proyecto para importar las utilidades
sys.path.append(os.getcwd())

from backend.core.database import sheets_client

def run_debug():
    print("🔍 Inspeccionando últimos registros de RAW_VENTAS...")
    ws = sheets_client.get_worksheet("RAW_VENTAS")
    total_rows = ws.row_count
    
    # Leer las últimas 3000 filas (debería cubrir Marzo/Abril)
    start_row = max(1, total_rows - 3000)
    range_str = f"A{start_row}:J{total_rows}"
    print(f"📡 Cargando rango {range_str}...")
    
    rows = ws.get(range_str)
    if not rows:
        print("❌ No se obtuvieron datos.")
        return

    print(f"✅ Se obtuvieron {len(rows)} filas.")
    
    marzo_rows = []
    for r in rows:
        if len(r) < 3: continue
        fecha_str = r[2]
        # Intentar parsear fecha
        dt = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                dt = datetime.strptime(fecha_str, fmt)
                break
            except: continue
        
        if dt and dt.year == 2026 and dt.month == 3:
            marzo_rows.append(r)

    print(f"📅 Filas de Marzo 2026 encontradas en este bloque: {len(marzo_rows)}")
    
    # Mostrar muestras
    print("\n--- MUESTRA DE DATOS MARZO 2026 ---")
    print("Indice: 0:Nombres | 2:Fecha | 3:Documento | 5:Total | 7:Clasificacion | 8:Tipo")
    for i, r in enumerate(marzo_rows[:20]):
        col7 = r[7] if len(r) > 7 else "empty"
        col8 = r[8] if len(r) > 8 else "empty"
        print(f"Row {i}: [{r[2]}] | Doc: {r[3]} | Total: {r[5]} | Col7: '{col7}' | Col8: '{col8}'")

if __name__ == "__main__":
    run_debug()
