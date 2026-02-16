
import gspread
from google.oauth2.service_account import Credentials

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def find_shifted_headers():
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    
    # Check around column 800-1100
    all_headers = ws.row_values(1)
    print(f"TOTAL HEADERS FOUND: {len(all_headers)}")
    
    # Look for the first non-'0' after index 4
    for i, h in enumerate(all_headers):
        if i > 4 and h != '0' and h != '':
            print(f"Shifted data starts at index {i} (Col {i+1}): {h}")
            print(f"Subsequent headers: {all_headers[i:i+10]}")
            break

if __name__ == "__main__":
    find_shifted_headers()
