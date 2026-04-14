
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
from backend.core.database import sheets_client

def diag():
    ws = sheets_client.get_worksheet('RAW_VENTAS')
    total = ws.row_count
    # Read last 5000 rows, more columns
    data = ws.get(f"A{total-5000}:L{total}")
    
    marzo_rows = []
    for r in data:
        if len(r) < 3: continue
        if "03/2026" in r[2] or "2026-03" in r[2]:
            marzo_rows.append(r)
            
    print(f"Marzo rows: {len(marzo_rows)}")
    
    col_counts = {}
    for r in marzo_rows:
        for idx, val in enumerate(r):
            if "pedido" in str(val).lower():
                col_counts[idx] = col_counts.get(idx, 0) + 1
                
    print("\n--- Columnas que contienen 'pedido' (case insensitive) ---")
    for idx, count in col_counts.items():
        print(f"Col {idx}: {count} veces")

    # Specifically check Col 8 and Col 9
    print("\n--- Muestra de Col 8 y 9 para los primeros 10 registros de Marzo ---")
    for r in marzo_rows[:10]:
        c7 = r[7] if len(r) > 7 else "N/A"
        c8 = r[8] if len(r) > 8 else "N/A"
        c9 = r[9] if len(r) > 9 else "N/A"
        print(f"[{r[2]}] | {r[3]} | C7: '{c7}' | C8: '{c8}' | C9: '{c9}'")

if __name__ == "__main__":
    diag()
