from backend.core.database import sheets_client
from backend.config.settings import Hojas
import json

def inspect_headers():
    try:
        ws = sheets_client.get_worksheet(Hojas.PEDIDOS)
        headers = ws.row_values(1)
        print("HEADERS_PEDIDOS:" + json.dumps(headers))
        
        # Also check first row of data
        first_row = ws.row_values(2)
        print("DATA_PEDIDOS:" + json.dumps(first_row))
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    inspect_headers()
