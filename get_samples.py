
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
from backend.core.database import sheets_client

def get_samples():
    ws = sheets_client.get_worksheet('RAW_VENTAS')
    total = ws.row_count
    # Fetch a larger chunk for March
    data = ws.get(f"A{total-5000}:J{total}")
    
    marzo_rows = []
    for r in data:
        if len(r) < 3: continue
        f = r[2]
        if "03/2026" in f or "2026-03" in f:
            marzo_rows.append(r)
            
    pedidos = [r for r in marzo_rows if len(r) > 7 and "pedido" in r[7].lower()]
    ventas = [r for r in marzo_rows if len(r) > 7 and "venta" in r[7].lower()]
    
    print("--- 5 MUESTRAS DE PEDIDOS (Marzo 2026) ---")
    for r in pedidos[:5]:
        print(f"{r}")
        
    print("\n--- 5 MUESTRAS DE VENTAS (Marzo 2026) ---")
    for r in ventas[:5]:
        print(f"{r}")

if __name__ == "__main__":
    get_samples()
