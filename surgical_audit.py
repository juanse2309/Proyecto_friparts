
import os
import sys
from datetime import datetime

# Añadir el path del proyecto para importar las utilidades
sys.path.append(os.getcwd())

from backend.core.database import sheets_client

def run_surgical_audit():
    print("🔬 Iniciando auditoría quirúrgica...")
    ws = sheets_client.get_worksheet("RAW_VENTAS")
    total = ws.row_count
    
    # Intentamos leer de atrás hacia adelante en bloques de 1000
    # para evitar el timeout de la carga masiva.
    current_end = total
    all_marzo_rows = []
    
    # Solo buscamos en los últimos 5000 registros (debería ser suficiente para marzo)
    for _ in range(5):
        start = max(1, current_end - 1000)
        range_str = f"A{start}:I{current_end}"
        print(f"📡 Cargando {range_str}...")
        try:
            data = ws.get(range_str)
            if not data: break
            
            marzo_in_chunk = []
            for r in data:
                if len(r) < 3: continue
                f = r[2]
                dt = None
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        dt = datetime.strptime(f, fmt)
                        break
                    except: continue
                
                if dt and dt.year == 2026 and dt.month == 3:
                    marzo_in_chunk.append(r)
            
            all_marzo_rows.extend(marzo_in_chunk)
            
            # Si encontramos datos de Marzo y luego empezamos a ver Febrero, paramos.
            # (Aunque aquí extendemos, el orden de chunk importa)
            
            current_end = start - 1
            if start == 1: break
        except Exception as e:
            print(f"⚠️ Error en bloque: {e}")
            break

    print(f"📊 Registros de Marzo 2026 encontrados: {len(all_marzo_rows)}")
    
    if not all_marzo_rows:
        return

    total_col7 = 0.0
    total_col8 = 0.0
    
    def clean_cur(val):
        try:
            return float(str(val).replace('$', '').replace('.', '').replace(',', '').strip() or 0)
        except: return 0.0

    samples_v = []
    samples_p = []
    
    for r in all_marzo_rows:
        val = clean_cur(r[5])
        
        # Col 7 - Clasificacion
        c7 = r[7].strip().lower() if len(r) > 7 else ""
        # Col 8 - Tipo
        c8 = r[8].strip() if len(r) > 8 else ""
        
        if "pedido" in c7: total_col7 += val
        if c8.capitalize() == "Pedidos": total_col8 += val
        
        # Guardar muestras para el chat
        if c8.capitalize() == "Pedidos" and "pedido" not in c7:
            if len(samples_p) < 5: samples_p.append(r)
        elif "pedido" not in c7 and c8.capitalize() != "Pedidos":
            if len(samples_v) < 5: samples_v.append(r)

    print("\n--- RESUMEN MARZO 2026 ---")
    print(f"Suma Col 7 ('pedido' in clas): ${total_col7:,.2f}")
    print(f"Suma Col 8 (capitalize == 'Pedidos'): ${total_col8:,.2f}")
    print(f"Diferencia: ${total_col8 - total_col7:,.2f}")
    
    print("\n--- MUESTRA: VENTAS ---")
    for r in samples_v[:5]:
        print(f"Fecha: {r[2]} | Total: {r[5]} | Col 7: {r[7]} | Col 8: {r[8] if len(r)>8 else 'N/A'}")
        
    print("\n--- MUESTRA: PEDIDOS (DETECTADOS EN COL 8) ---")
    for r in samples_p[:5]:
        print(f"Fecha: {r[2]} | Total: {r[5]} | Col 7: {r[7]} | Col 8: {r[8] if len(r)>8 else 'N/A'}")

if __name__ == "__main__":
    run_surgical_audit()
