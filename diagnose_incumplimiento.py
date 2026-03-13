
from backend.core.database import sheets_client
from backend.config.settings import Hojas
import json

def diagnostic():
    try:
        ws = sheets_client.get_worksheet("DB_DASHBOARD_VENTAS")
        data = ws.get_all_values()
        
        target_client = "IMRE"
        print(f"Searching for '{target_client}' in DB_DASHBOARD_VENTAS:")
        found = False
        for i, row in enumerate(data):
            if i < 2: continue # Skip headers
            col_u = row[20] if len(row) > 20 else ""
            if target_client.lower() in col_u.lower():
                found = True
                # Q=16, R=17 | W=22, X=23
                print(f"Row {i+1}:")
                print(f"  Unidades - Ped (Q): {row[16] if len(row)>16 else 'N/A'}, Ven (R): {row[17] if len(row)>17 else 'N/A'}")
                print(f"  Dinero   - Ped (W): {row[22] if len(row)>22 else 'N/A'}, Ven (X): {row[23] if len(row)>23 else 'N/A'}")
                
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    diagnostic()
