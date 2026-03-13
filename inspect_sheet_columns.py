
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from backend.core.database import sheets_client

def inspect_sheet():
    try:
        ss = sheets_client.spreadsheet
        for sheet_name in ["RAW_VENTAS", "DB_DASHBOARD_VENTAS"]:
            print(f"\n--- {sheet_name} ---")
            ws = ss.worksheet("DB_DASHBOARD_VENTAS")
        data = ws.get_all_values()
        for i in range(2, 12): # Rows 3 to 12
            if i < len(data):
                row = data[i]
                print(f"\nRow {i+1}:")
                # Show columns A-C (Monthly summary)
                print(f"  Monthly: {row[0]} | Ped: {row[1]} | Ven: {row[2]}")
                # Show columns N-R (Units gap)
                if len(row) > 17:
                    print(f"  Units Block: Cli: {row[13]} | Prd: {row[14]} | Ped: {row[15]} | Ven: {row[16]}")
                # Show columns T-X (Money gap)
                if len(row) > 23:
                    print(f"  Money Block: Cli: {row[19]} | Prd: {row[20]} | Ped: {row[21]} | Ven: {row[22]}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_sheet()
