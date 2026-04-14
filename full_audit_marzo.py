
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

def full_audit():
    print("🚀 Inicia Auditoría FULL...")
    ws = sheets_client.get_worksheet('RAW_VENTAS')
    
    # Intentamos bajar columnas A, C, F, H, I
    print("📡 Descargando columnas A:I...")
    # Usamos batch_get para ser más eficientes o simplemente un rango A:I
    data = ws.get("A1:I52000")
    
    header = data[0]
    rows = data[1:]
    
    actual_sum = 0.0
    propuesta_sum = 0.0
    
    missing_sum = 0.0
    missing_samples = []
    
    actual_samples = []
    
    for i, r in enumerate(rows):
        if len(r) < 3: continue
        f = r[2]
        dt = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                dt = datetime.strptime(f, fmt)
                break
            except: continue
            
        if dt and dt.year == 2026 and dt.month == 3:
            valor = clean_cur(r[5])
            
            # Clasificacion (Col 7)
            c7 = r[7].strip().lower() if len(r) > 7 else ""
            es_act = "pedido" in c7
            
            # Tipo (Col 8)
            c8 = r[8].strip() if len(r) > 8 else ""
            es_prop = c8.lower() == "pedidos"
            
            if es_act:
                actual_sum += valor
                if len(actual_samples) < 5: actual_samples.append(r)
                
            if es_prop:
                propuesta_sum += valor
                
            if es_prop and not es_act:
                missing_sum += valor
                if len(missing_samples) < 10: missing_samples.append(r)

    print("\n--- RESULTADOS FINALES ---")
    print(f"💰 Suma Actual (Col 7): ${actual_sum:,.2f}")
    print(f"💰 Suma Propuesta (Col 8): ${propuesta_sum:,.2f}")
    print(f"⚠️ Diferencia (Solo en Col 8): ${missing_sum:,.2f}")
    
    print("\n--- MUESTRA: DETECTADOS POR COL 8 PERO NO POR COL 7 ---")
    if not missing_samples:
        print("No se hallaron registros que cumplan la condición (Col 8=='Pedidos' y Col 7!='pedido').")
    for r in missing_samples[:5]:
        t = r[8] if len(r) > 8 else "N/A"
        print(f"[{r[2]}] | Doc: {r[3]} | Total: {r[5]} | Col 7: '{r[7]}' | Col 8: '{t}'")
        
    print("\n--- MUESTRA: DETECTADOS POR COL 7 (VENTAS ACTUALES) ---")
    for r in actual_samples[:5]:
        t = r[8] if len(r) > 8 else "N/A"
        print(f"[{r[2]}] | Doc: {r[3]} | Total: {r[5]} | Col 7: '{r[7]}' | Col 8: '{t}'")

if __name__ == "__main__":
    full_audit()
