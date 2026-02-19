
import gspread
from google.oauth2.service_account import Credentials

GSHEET_KEY = "1mhZ71My6VegbBFLZb2URvaI7eWW4ekQgncr4s_C_CpM"
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

try:
    creds = Credentials.from_service_account_file("credentials_apps.json", scopes=scope)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(GSHEET_KEY)
    ws = ss.worksheet("PRODUCTOS")
    headers = ws.row_values(1)
    print("HEADERS EN PRODUCTOS:")
    print(headers)
except Exception as e:
    print(f"Error: {e}")
