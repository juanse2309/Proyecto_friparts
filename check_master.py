from backend.core.database import sheets_client
import json

try:
    ws = sheets_client.get_worksheet("CLIENTES")
    headers = ws.row_values(1)
    # Buscar FRIPARTS o el NIT 900315300
    records = ws.get_all_records()
    found = [r for r in records if "900315300" in str(r.get("NIT", "")) or "FRIPARTS" in str(r.get("CLIENTE", ""))]
    
    print("=== CLIENTES (MASTER) ===")
    print(f"HEADERS: {json.dumps(headers)}")
    if found:
        print(f"FOUND: {json.dumps(found[0])}")
    else:
        print("NOT FOUND")
except Exception as e:
    print(f"ERROR: {str(e)}")
