
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
from backend.core.database import sheets_client

def analyze_marzo():
    ws = sheets_client.get_worksheet('RAW_VENTAS')
    total = ws.row_count
    
    # Scan last 5000 rows
    step = 500
    all_rows = []
    for current_max in range(total, total - 5000, -step):
        start = max(1, current_max - step)
        try:
            data = ws.get(f"A{start}:I{current_max}")
            if data: all_rows.extend(data)
        except: break

    # Filter March 2026
    marzo_rows = []
    for row in all_rows:
        if len(row) < 3: continue
        f = row[2]
        if "03/2026" in f or "2026-03" in f:
            marzo_rows.append(row)

    print(f"Total Marzo rows found: {len(marzo_rows)}")
    
    # 5 Sample Pedidos (in Col 7)
    print("\n--- SAMPLES: PEDIDOS IN COL 7 ---")
    count = 0
    for r in marzo_rows:
        c7 = r[7] if len(r) > 7 else ""
        c8 = r[8] if len(r) > 8 else ""
        if "pedido" in c7.lower():
            print(f"[{r[2]}] | {r[3]} | {r[5]} | Col 7: '{c7}' | Col 8: '{c8}'")
            count += 1
            if count >= 5: break

    # 5 Sample Pedidos (ONLY in Col 8)
    print("\n--- SAMPLES: PEDIDOS ONLY IN COL 8 (Potentially Missing) ---")
    count = 0
    for r in marzo_rows:
        c7 = r[7] if len(r) > 7 else ""
        c8 = r[8] if len(r) > 8 else ""
        if "pedidos" in c8.lower() and "pedido" not in c7.lower():
            print(f"[{r[2]}] | {r[3]} | {r[5]} | Col 7: '{c7}' | Col 8: '{c8}'")
            count += 1
            if count >= 10: break

    # 5 Sample Ventas (in neither)
    print("\n--- SAMPLES: VENTAS (Neither) ---")
    count = 0
    for r in marzo_rows:
        c7 = r[7] if len(r) > 7 else ""
        c8 = r[8] if len(r) > 8 else ""
        if "pedido" not in c7.lower() and "pedidos" not in c8.lower():
            print(f"[{r[2]}] | {r[3]} | {r[5]} | Col 7: '{c7}' | Col 8: '{c8}'")
            count += 1
            if count >= 5: break

if __name__ == "__main__":
    analyze_marzo()
