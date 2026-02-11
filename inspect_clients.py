from backend.core.database import sheets_client
import json

def inspect_clients():
    try:
        # DB_Clientes is the sheet name according to app.py Hojas.CLIENTES
        ws = sheets_client.get_worksheet("DB_Clientes")
        headers = ws.row_values(1)
        print("HEADERS_CLIENTES:" + json.dumps(headers))
        
        first_rows = ws.get_all_values()[:5]
        print("DATA_CLIENTES:" + json.dumps(first_rows))
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    inspect_clients()
