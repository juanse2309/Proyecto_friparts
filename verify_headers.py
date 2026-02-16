
import gspread
from google.oauth2.service_account import Credentials

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def verify_final_headers():
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    
    all_headers = ws.row_values(1)
    print(f"FINAL HEADERS ({len(all_headers)}):")
    for i, h in enumerate(all_headers):
        print(f"{i+1}: {h}")

if __name__ == "__main__":
    verify_final_headers()
