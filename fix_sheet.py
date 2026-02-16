
import gspread
from google.oauth2.service_account import Credentials
import time

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def fix_sheet():
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    
    all_headers = ws.row_values(1)
    print(f"Total headers: {len(all_headers)}")
    
    # Range of '0' columns: from index 4 (Col E) to the one before index 1001 (Col 1002)
    # We want to keep A, B, C, D.
    # We want to keep from index 1001 onwards.
    # So we delete everything between index 4 and 1000 inclusive.
    # That is Column 5 to Column 1001.
    
    start_col = 5
    end_col = 1001
    
    print(f"Deleting columns {start_col} to {end_col}...")
    try:
        ws.delete_columns(start_col, end_col)
        print("Columns deleted successfully.")
    except Exception as e:
        print(f"Error deleting columns: {e}")
        return

    # Verify final headers
    time.sleep(1)
    new_headers = ws.row_values(1)
    print("NEW HEADERS:", new_headers[:20])

if __name__ == "__main__":
    fix_sheet()
