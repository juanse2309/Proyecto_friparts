
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())
from backend.core.database import sheets_client

def find_marzo():
    ws = sheets_client.get_worksheet('RAW_VENTAS')
    total = ws.row_count
    print(f"Total rows: {total}")
    
    # Scan backwards in small steps
    step = 100
    for current_max in range(total, total - 5000, -step):
        start = max(1, current_max - step)
        print(f"Checking {start}:{current_max}...")
        try:
            # Range format for surgical fetch
            data = ws.get(f"A{start}:I{current_max}")
            if not data: continue
            
            # Check for March 2026
            for i, row in enumerate(reversed(data)):
                if len(row) < 3: continue
                f = row[2]
                if "03/2026" in f or "2026-03" in f:
                    print(f"Found March row at relative index {i} in block!")
                    # Just print 10 rows from here
                    print("Row Sample:")
                    # Convert reversed index back
                    found_idx = len(data) - 1 - i
                    # Print 10 around it
                    for j in range(max(0, found_idx-5), min(len(data), found_idx+5)):
                        r = data[j]
                        c7 = r[7] if len(r) > 7 else "EMPTY"
                        c8 = r[8] if len(r) > 8 else "EMPTY"
                        print(f"[{r[2]}] | {r[3]} | {r[5]} | Col7: {c7} | Col8: {c8}")
                    return
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    find_marzo()
