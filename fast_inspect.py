
import os
import sys
from datetime import datetime

# Añadir el path del proyecto para importar las utilidades
sys.path.append(os.getcwd())

from backend.core.database import sheets_client

def run_debug():
    ws = sheets_client.get_worksheet("RAW_VENTAS")
    total_count = ws.row_count
    # Fetch only last 300 rows and specifically indices 2, 3, 5, 7, 8
    # Range A to I (headers 0 to 8)
    r_str = f"A{total_count-300}:I{total_count}"
    print(f"📡 Fetching {r_str}")
    data = ws.get(r_str)
    
    print("Row | Fecha | Total | Col 7 (Clas) | Col 8 (Tipo)")
    for i, r in enumerate(data):
        if len(r) < 8: continue
        # Date at index 2
        f = r[2]
        # Total at index 5
        t = r[5]
        # Col 7
        c7 = r[7]
        # Col 8
        c8 = r[8] if len(r) > 8 else "MISSING"
        
        # Only print March 2026 or interesting rows
        if "2026" in f:
            print(f"{i} | {f} | {t} | {c7} | {c8}")

if __name__ == "__main__":
    run_debug()
