
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
from backend.core.database import sheets_client

def clean_cur(val):
    try:
        s = str(val).replace('$', '').replace('.', '').replace(',', '').strip()
        return float(s) if s else 0.0
    except: return 0.0

def final_audit():
    print("🔬 Auditoría Final de Verificación...")
    ws = sheets_client.get_worksheet('RAW_VENTAS')
    
    # Bajamos un rango un poco más ancho (A:J)
    data = ws.get("A50000:J51200")
    if not data:
        print("No data found")
        return

    marzo_rows = []
    for r in data:
        if len(r) < 3: continue
        f = r[2]
        if "03/2026" in f or "2026-03" in f:
            marzo_rows.append(r)
            
    print(f"Marzo 2026 rows: {len(marzo_rows)}")
    
    sum_c7 = 0.0
    sum_c8 = 0.0
    sum_ped_doc = 0.0 # Suma si el documento empieza por PED
    
    for r in marzo_rows:
        val = clean_cur(r[5])
        
        c7 = r[7].strip().lower() if len(r) > 7 else ""
        c8 = r[8].strip().lower() if len(r) > 8 else ""
        doc = r[3].strip().upper() if len(r) > 3 else ""
        
        if "pedido" in c7: sum_c7 += val
        if "pedido" in c8: sum_c8 += val
        if doc.startswith("PED"): sum_ped_doc += val

    print(f"\n📊 Resultados:")
    print(f"Suma por Col 7 (Clasificacion): ${sum_c7:,.2f}")
    print(f"Suma por Col 8 (Tipo):          ${sum_c8:,.2f}")
    print(f"Suma por Documento (PED...):    ${sum_ped_doc:,.2f}")
    
    # Mostrar si hay algo en Col 8 que no sea vacío
    non_empty_c8 = [r[8] for r in marzo_rows if len(r) > 8 and r[8].strip()]
    print(f"Valores no vacíos en Col 8: {len(non_empty_c8)}")
    if non_empty_c8:
        print(f"Primeros valores: {non_empty_c8[:5]}")

if __name__ == "__main__":
    final_audit()
