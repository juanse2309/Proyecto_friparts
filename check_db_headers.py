
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.core.database import sheets_client

def check_sheet():
    try:
        # Check DB_Productos
        sheet_name = "DB_Productos"
        print(f"Checking sheet: {sheet_name}...")
        
        try:
            ws = sheets_client.get_worksheet(sheet_name)
            headers = ws.row_values(1)
            print(f"Headers found in {sheet_name}:")
            print(headers)
            
            required_stock_cols = ["POR PULIR", "P. TERMINADO", "PRODUCTO ENSAMBLADO"]
            missing = [c for c in required_stock_cols if c not in headers]
            
            if missing:
                print(f"\nWARNING: Missing stock columns: {missing}")
                print("Switching to this sheet would BREAK stock management.")
            else:
                print("\nSUCCESS: All stock columns present. Safe to switch?")
                
        except Exception as e:
            print(f"\nError: Could not access {sheet_name}. Does it exist?")
            print(e)

    except Exception as e:
        print(f"Critical error: {e}")

if __name__ == "__main__":
    check_sheet()
