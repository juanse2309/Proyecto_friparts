from backend.core.database import sheets_client
import json

def debug_clients():
    sheet_names = ["CLIENTES", "DB_Clientes"]
    
    for name in sheet_names:
        print(f"\n--- Probando hoja: '{name}' ---")
        try:
            ws = sheets_client.get_worksheet(name)
            if ws:
                headers = ws.row_values(1)
                print(f"✅ Hoja encontrada: {name}")
                print(f"📊 Headers: {json.dumps(headers)}")
                
                # Preview row 2
                vals = ws.row_values(2)
                print(f"📄 Row 2 Preview: {json.dumps(vals)}")
            else:
                print(f"❌ Hoja no encontrada (get_worksheet returned None): {name}")
                
        except Exception as e:
            print(f"❌ Error accediendo a '{name}': {str(e)}")

if __name__ == "__main__":
    debug_clients()
