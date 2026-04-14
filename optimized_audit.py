
import os
import sys
from datetime import datetime

# Añadir el path del proyecto para importar las utilidades
sys.path.append(os.getcwd())

from backend.core.database import sheets_client

def clean_currency(val):
    if not val: return 0.0
    try:
        s = str(val).replace('$', '').replace('.', '').replace(',', '').strip()
        return float(s) if s else 0.0
    except: return 0.0

def run_audit():
    print("🚀 Iniciando auditoría optimizada...")
    ws = sheets_client.get_worksheet("RAW_VENTAS")
    
    # Intentar obtener solo las columnas necesarias para ahorrar memoria/tiempo
    # Fecha(C), Total(F), Clasif(H), Tipo(I)
    # A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8, I=9
    print("📡 Descargando datos necesarios...")
    data = ws.get("A1:I52000") # Rango amplio para cubrir todo
    
    headers = data[0]
    rows = data[1:]
    
    actual_pedidos = 0.0
    propuesto_pedidos = 0.0
    
    v_marzo_rows = []
    p_marzo_rows = []
    
    print(f"📊 Procesando {len(rows)} filas...")
    
    for i, r in enumerate(rows):
        if len(r) < 8: continue
        
        f = r[2]
        # Parse date
        dt = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                dt = datetime.strptime(f, fmt)
                break
            except: continue
            
        if dt and dt.year == 2026 and dt.month == 3:
            valor = clean_currency(r[5])
            
            # Lógica Actual (Index 7)
            clas = r[7].strip().lower()
            es_act = "pedido" in clas
            
            # Lógica Propuesta (Index 8)
            tipo = r[8].strip() if len(r) > 8 else ""
            es_prop = tipo.lower() == "pedidos" # Caso insensible por ahora para debug
            
            if es_act: actual_pedidos += valor
            if es_prop: propuesto_pedidos += valor
            
            # Guardar muestras
            if es_prop and not es_act:
                if len(p_marzo_rows) < 10:
                    p_marzo_rows.append(r)
            elif not es_prop and not es_act:
                if len(v_marzo_rows) < 10:
                    v_marzo_rows.append(r)

    print("\n✅ Auditoría Completa")
    print(f"💰 Suma Pedidos (Lógica Actual Col 7): ${actual_pedidos:,.2f}")
    print(f"💰 Suma Pedidos (Lógica Propuesta Col 8): ${propuesto_pedidos:,.2f}")
    
    print("\n--- MUESTRA: REGISTROS QUE SON 'PEDIDOS' EN COL 8 PERO NO EN COL 7 ---")
    for r in p_marzo_rows[:5]:
        print(f"Fecha: {r[2]} | Total: {r[5]} | Col 7: '{r[7]}' | Col 8: '{r[8]}'")
        
    print("\n--- MUESTRA: REGISTROS QUE SON 'VENTAS' EN AMBAS ---")
    for r in v_marzo_rows[:5]:
        t = r[8] if len(r) > 8 else "N/A"
        print(f"Fecha: {r[2]} | Total: {r[5]} | Col 7: '{r[7]}' | Col 8: '{t}'")

if __name__ == "__main__":
    run_audit()
