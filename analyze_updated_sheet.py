
import gspread
from google.oauth2.service_account import Credentials
import json

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

def analyze_sheet():
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    
    headers = ws.row_values(1)
    print("HEADERS:", headers)
    
    # Get first 5 rows of data
    data = ws.get_all_records()
    print("\nSAMPLE DATA (First 5):")
    for i, row in enumerate(data[:5]):
        print(f"Row {i+2}: {row}")

if __name__ == "__main__":
    analyze_sheet()
