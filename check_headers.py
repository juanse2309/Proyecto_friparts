from backend.core.database import sheets_client
import json

try:
    ws = sheets_client.get_worksheet("USUARIOS_CLIENTES")
    headers = ws.row_values(1)
    row2 = ws.row_values(2)
    print("=== USUARIOS_CLIENTES ===")
    print(f"HEADERS: {json.dumps(headers)}")
    print(f"ROW 2: {json.dumps(row2)}")
except Exception as e:
    print(f"ERROR: {str(e)}")
