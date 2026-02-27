
import os
from backend.core.database import sheets_client
from backend.config.settings import Hojas

def inspect_providers():
    try:
        ws = sheets_client.get_worksheet(Hojas.DB_PROVEEDORES)
        if not ws:
            print(f"Error: Worksheet {Hojas.DB_PROVEEDORES} not found.")
            # List all worksheets to help debug
            spreadsheet = sheets_client.gc.open_by_key(sheets_client.GSHEET_KEY)
            worksheets = [w.title for w in spreadsheet.worksheets()]
            print(f"Available worksheets: {worksheets}")
            return

        headers = ws.row_values(1)
        print(f"Headers in {Hojas.DB_PROVEEDORES}: {headers}")
        
        records = ws.get_all_records()
        print(f"Number of records: {len(records)}")
        # Inspect OC Sheet
        ws_oc = sheets_client.get_worksheet(Hojas.ORDENES_DE_COMPRA)
        if ws_oc:
            headers_oc = ws_oc.row_values(1)
            print(f"\nHeaders in {Hojas.ORDENES_DE_COMPRA}: {headers_oc}")
        else:
            print(f"\nWorksheet {Hojas.ORDENES_DE_COMPRA} not found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_providers()
